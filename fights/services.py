import redis
import json

from django.db import transaction, models
from django.conf import settings
from utils import postgres

from fights.models import Fight, Invitation, PlayerFight, Hosting


# We'll want everything in text form, so enable auto-decoding.
redis_client = redis.from_url(settings.REDIS_SERVER_URL,
                              decode_responses=True)


class AdvisoryLocks:
    class Targets:
        CREATE_OR_ATTEND_FIGHT = 0
    
    @staticmethod
    def lock_create_or_attend_fight(user):
        """Acquire a lock on whether a user can create or attend a fight. Block until released if already acquired.
        
        Parameters
        ----------
        user : User
            The user instance to hold the lock for.
        
        Notes
        -----
        Since the number of simultaneous fights must be monitored to not
        exceed a certain number (currently only one), here we create an
        advisory PostgreSQL lock to prevent another transaction from
        attending or creating another fight. Another way would be to hold
        a row-level lock (SELECT FOR UPDATE) on the user object, or to
        create another table for such locks that has rows for each user
        and can hold row-level locks on it. However, using advisory locks
        is a better solution, as they are stored in memory and don't
        require disk writes.
        
        Here we use a transaction-level lock, which will be released after
        the transaction, therefore this lock must only be held inside a lock.
        The checks on whether the user can create a fight or not must be done
        after acquiring this lock in the transaction to avoid race conditions.
        """
        
        # We use the user's database id as the lock's second argument.
        postgres.pg_advisory_xact_lock(
            AdvisoryLocks.Targets.CREATE_OR_ATTEND_FIGHT,
            user.pk
        )


class CheckUserAttendedFightsFullService:
    def __init__(self, user):
        self.user = user
    
    def execute(self) -> bool:
        # >= instead of == for safe measure.
        return Fight.objects.filter(
            players__in=[self.user],
        ).unfinished().count() >= settings.MAX_USER_ATTENDED_FIGHTS


class CreateFightService:
    # Results
    SUCCESS = 0
    ERROR_ATTENDED_FIGHTS_FULL = 1
    ERROR_BAD_REQUEST = 2
    
    def __init__(self, *,
            game_info,
            host,
            host_code,
            invited_players,
            is_public
        ):
        self.game_info = game_info
        self.host = host
        self.host_code = host_code
        self.invited_players = invited_players
        self.is_public = is_public
    
    def execute(self):
        with transaction.atomic(durable=True):
            AdvisoryLocks.lock_create_or_attend_fight(self.host)
            
            if CheckUserAttendedFightsFullService(self.host).execute():
                return CreateFightService.ERROR_ATTENDED_FIGHTS_FULL
            
            # +1 for the host.
            players_count = len(self.invited_players) + 1
            
            if any([
                players_count < self.game_info.min_players,
                players_count > self.game_info.max_players,
                
                self.host in self.invited_players
            ]):
                return CreateFightService.ERROR_BAD_REQUEST
            
            fight = Fight.objects.create(
                game=self.game_info,
                # game_settings=...    TO BE IMPLEMENTED
                
                is_public=self.is_public
            )
            
            PlayerFight.objects.create(
                fight=fight,
                player=self.host,
                code_file=self.host_code
            )
            
            hosting = Hosting.objects.create(host=self.host, fight=fight)
            
            Invitation.objects.bulk_create([
                Invitation(hosting=hosting, target=player) for player in self.invited_players
            ])

        return CreateFightService.SUCCESS


class StartHostedFightService:
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_HOSTING = 1
    ERROR_BAD_REQUEST = 2
    
    def __init__(self, host):
        self.host = host
    
    def execute(self, *, no_simulation=False):   
        # Explanation of the lock orders and purposes:
        #
        # If the fight is deleted, so is the hosting row, because of
        # a cascade delete. So, either no hosting will be found, or
        # both the hosting and the fight exist and will be locked by
        # select_for_update(). Note that we used select_related() to
        # make a join to the fight's table and select all its fields,
        # which causes it to lock too.
        #
        # 1. We first lock the hosting and the fight so that the fight
        # cannot be canceled (and thus deleted) during this operation.
        #
        # 2. We then delete the hosting, and thus all the invitations.
        # Since we use row locks upon joining invitations, once these
        # deletions succeed, we can be sure that there is no PlayerFight
        # being created concurrently from an invitation. This means that
        # the set of PlayerFight's won't change after we query them next.
        #
        # 3. We then lock the corresponding PlayerFight's. This is so
        # that no one can concurrently cancel their attendance in another
        # transaction. In fact, if a cancel request faces a lock on the
        # PlayerFight, it should immediately dismiss the request because
        # it means that the fight has already begun.
        with transaction.atomic(durable=True):
            # We need to lock both the Hosting and the Fight object, so
            # we use select_related('fight'); plus, we also need almost
            # all the fields of the Fight, so we're good.
            #
            # Currently, we only support one hosting at a time. Therefore
            # we query the hosting like this. This might change later.
            hosting = Hosting.objects.select_related('fight').select_for_update().filter(
                host=self.host
            ).first()
        
            if not hosting:
                return StartHostedFightService.ERROR_NO_SUCH_HOSTING
            
            fight = hosting.fight  # cache
            
            # Delete the hosting, which will in turn delete all the invitations
            # by a cascade delete. This will block until all concurrent invitation
            # acceptances or attendance cancelings are processed. Therefore, it's
            # important that this MUST happen before actually starting the fight.
            hosting.delete()
            
            playerfights = PlayerFight.objects.select_for_update().filter(
                fight=fight
            )
            
            players_count = len(playerfights)
            
            # The GameInfo will be queried only once (note that we have
            # already cached the fight through select_related('fight')).
            if not (fight.game.min_players <= players_count and
                    players_count <= fight.game.max_players):
                return StartHostedFightService.ERROR_BAD_REQUEST
            
            # After this transaction, the fight should not be deleted
            # normally, because here we mark it as started.
            fight.set_started_now()

        # The parameter 'no_simulation' must only be used for debugging.
        if not no_simulation:
            SendFightForSimulationService(fight=fight).execute()
        
        return StartHostedFightService.SUCCESS


class CancelHostedFightService:
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_HOSTING = 1
    
    def __init__(self, host):
        self.host = host
    
    def execute(self):
        # It's crucial to have the fight not started (started_at null).
        # This is because if after we query the hosting for the fight id,
        # the fight gets started, then we shouldn't cancel (=delete) the
        # fight.
        #
        # We don't care about locking the fight here, but merely not
        # blocking (and not doing anything) in case the fight is locked
        # (thus we don't even have a transaction). For that, select_for_update()
        # is necessary.
        #
        # Note that this will also cascade delete the hosting and the
        # invitations.
        deleted = Fight.objects.select_for_update(skip_locked=True).filter(
            pk=models.Subquery(
                Hosting.objects.filter(host=self.host).values('fight__id')
            )
        ).not_started().delete()[0]
    
        if deleted == 0:
            return CancelHostedFightService.ERROR_NO_SUCH_HOSTING
        
        return CancelHostedFightService.SUCCESS



class SendFightForSimulationService:
    def __init__(self, fight):
        self.fight = fight
    
    def execute(self):
        data = {
            'fight_id': self.fight.id,
            'game': self.fight.game.name,
            'game_settings': self.fight.game_settings,
            
            # Each item from this .values_list() will be a 1-tuple. We order by
            # ID, so that when the results arrive, we know which code belonged
            # to which player.
            'codes_filenames': [
                q[0] for q in self.fight.playerfight_set.values_list(
                    'code_file'
                ).order_by('id')
            ]
        }

        redis_client.xadd(settings.REDIS_SIMULATOR_STREAM,
            {'data': json.dumps(data)}
        )


class PerformHostingAutoActionService:
    """A service to perform actions on a hosted fight when necessary."""
    
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_HOSTING = 1
    
    # TODO: In the future, in order to allow more than one concurrent
    # hostings, we'll probably have to use UUID's on 'Hosting' too, so
    # this would get both the host and the hosting's UUID in order to
    # resolve and lock the related hosting object. The same applies to
    # the services for accepting and canceling a hosted fight.
    def __init__(self, host):
        self.host = host
    
    def execute(self):
        # This atomic block doesn't have to be durable (=outermost), as
        # we don't make changes to the database in this transaction (other
        # than locking the row). We only need this transaction for locking
        # the hosting. It wouldn't matter if this is an inner atomic block,
        # because it counts as being in the same transaction (as django
        # uses savepoints for inner atomic blocks), so if the hosting is
        # already locked in a parent atomic block, then the following lock
        # would immediately return with the result, as locking the same
        # row in the same transaction makes no difference.
        with transaction.atomic():
            # It's important to lock the hosting object to make sure
            # it's not deleted along the way.
            hosting = Hosting.objects.select_for_update().of_host(
                self.host
            ).select_related(
                'fight__game'
            ).only(
                'fight__game__min_players'
            ).first()
            
            if not hosting:
                return PerformHostingAutoActionService.ERROR_NO_SUCH_HOSTING
            
            inv_count = hosting.invitation_set.count()
            
            # Since the hosting object is locked, the only way the following
            # services might return an error is for a bad request, which would
            # only happen if the invitations change after we check the conditions
            # here; in that case, the action is voided and we ignore it.
            #
            # Note that we use transaction.on_commit() so that the following
            # services are only executed after this transaction; this is because
            # their transactions might have durable=True.
            #
            # Invitations may get deleted by a dismissal. +1 for the host.
            if inv_count+1 < hosting.fight.game.min_players:
                transaction.on_commit(CancelHostedFightService(hosting.host).execute)
            elif hosting.invitation_set.pending().count() == 0:
                transaction.on_commit(StartHostedFightService(hosting.host).execute)
        
        return PerformHostingAutoActionService.SUCCESS


class AcceptInvitationService:
    """A service for accepting an invitation, given its UUID and target user.
    
    This service does not accept invitation objects directly, and must
    be initialized by the UUID and the target user. The reason for this
    behavior is that the invitation object has to be locked during the
    service execution to avoid race conditions; therefore, querying the
    invitation object from the database must be done by the service itself
    to make sure select_for_update() is applied.
    """
    
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_INVITATION = 1
    ERROR_ATTENDED_FIGHTS_FULL = 2
    
    def __init__(self, *, uuid, target, code):
        self.uuid = uuid
        self.target = target
        self.code = code
    
    def execute(self, *, store_invitation=False):
        with transaction.atomic(durable=True):
            # It's crucial to lock the invitation so that if the invitation
            # is to be deleted in some code, they will block until all of the
            # concurrent attendance submissions are processed. Deletion of
            # invitation may occur on dismissal of the invitation, or starting
            # or canceling the corresponding fight.
            #
            # This lock also helps so that two acceptance requests to the
            # same invitation cannot happen at the same time. Nonetheless,
            # this was guaranteed by the advisory lock anyways.
            #
            # Also note that since we also select the hosting object, it will also
            # be locked by select_for_update(). We don't need this to prevent the
            # fight from being deleted while we're processing the invitation acceptance
            # request (as explained above), because locking the invitation is enough
            # to block the deletion of the fight and the hosting (as they attempt a
            # cascade delete on the invitations), and this prevents that transaction
            # from committing, and therefore the fight and the hosting remain intact
            # while we're processing here.
            invitation = Invitation.pending.select_for_update().select_related(
                'hosting', 'hosting__host'
            ).only(
                'hosting__host__id',  # for autoaction service
                'hosting__fight__id'  # for querying PlayerFight's
            ).from_uuid_and_target(
                uuid=self.uuid,
                target=self.target
            )
            
            if not invitation:
                return AcceptInvitationService.ERROR_NO_SUCH_INVITATION
        
            AdvisoryLocks.lock_create_or_attend_fight(self.target)
            
            if CheckUserAttendedFightsFullService(self.target).execute():
                return AcceptInvitationService.ERROR_ATTENDED_FIGHTS_FULL

            PlayerFight.objects.create(
                fight=invitation.hosting.fight,
                player=self.target,
                code_file=self.code
            )
            
            # Must be inside this transaction, so that the invitation cannot
            # be deleted while being updated.
            invitation.mark_accepted()
            
            PerformHostingAutoActionService(invitation.hosting.host).execute()

        
        # Note that we're only storing the cached version of the invitation.
        # It might have been deleted in the mean time after we exit the
        # transaction and enter this 'if' block.
        if store_invitation:
            self.invitation = invitation
        
        
        return AcceptInvitationService.SUCCESS


class DismissInvitationService:
    """A service for dismissing an invitation, given its UUID and target user.
    
    This service does not accept invitation objects directly, and must
    be initialized by the UUID and the target user. The reason for this
    behavior is to have everything in a single query to avoid race
    conditions.
    """
    
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_INVITATION = 1

    def __init__(self, *, uuid, target):
        self.uuid = uuid
        self.target = target
    
    def execute(self):
        # If no such invitation exists, simply does nothing. Currently
        # we don't let accepted invitations to be dismissed; one first
        # have to cancel their attendance, and then dismiss the invitation.
        invitation = Invitation.pending.select_related(
            'hosting__host'
        ).only(
            'hosting__host__id'  # for autoaction service's query
        ).from_uuid_and_target(
            uuid=self.uuid,
            target=self.target
        )
        
        if invitation.delete()[0] == 0:
            return DismissInvitationService.ERROR_NO_SUCH_INVITATION

        PerformHostingAutoActionService(invitation.hosting.host).execute()
        
        return DismissInvitationService.SUCCESS


class CancelAcceptedInvitationService:
    # Results
    SUCCESS = 0
    ERROR_NO_SUCH_INVITATION = 1
    
    def __init__(self, *, uuid, target):
        self.uuid = uuid
        self.target = target
    
    def execute(self):
        with transaction.atomic(durable=True):
            # We lock the invitation. This is to:
            # 1. Make fight start blocks until the invitation update is processed.
            #    We will delete the hosting (and thus the invitations) first before
            #    starting the fight.
            # 2. Prevent the .save() from creating a new invitation when it's
            #    actually deleted.
            #
            # We also don't want this to block in case the invitation is
            # locked, so we used skip_locked=True.
            #
            # Note: the only way that an invitation can get accepted=True would
            # be after the attendance transaction is over, and the only way it
            # would be false would be for the canceling transaction (this) to
            # be over; therefore, canceling attendance and accepting on the same
            # invitation would not overlap.
            invitation = Invitation.accepted.select_for_update(
                skip_locked=True
            ).select_related(
                'hosting__fight'
            ).only(
                'hosting__fight__id'  # for querying the PlayerFight.
            ).from_uuid_and_target(
                uuid=self.uuid,
                target=self.target
            )
            
            if not invitation:
                return CancelAcceptedInvitationService.ERROR_NO_SUCH_INVITATION
            
            PlayerFight.objects.filter(
                player=self.target,
                fight=invitation.hosting.fight
            ).delete()
            
            # Must be inside the transaction to make sure that the invitation
            # was not removed while performing this.
            invitation.mark_pending()

        return CancelAcceptedInvitationService.SUCCESS
