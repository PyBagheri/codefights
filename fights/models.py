from django.urls import reverse
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from common.values import TerminationReasons

from gamespecs.models import GameInfo
from accounts.models import User

import uuid


class TerminationReasonsChoices(models.TextChoices):
    ILLEGAL_SYSCALL = TerminationReasons.ILLEGAL_SYSCALL, 'Illegal Syscall'
    ENOMEM =          TerminationReasons.ENOMEM,          'Memory Limit Exceeded'
    UNKNOWN_KILL =    TerminationReasons.UNKNOWN_KILL,    'Unknown Kill'
    UNKNOWN_SIGNAL =  TerminationReasons.UNKNOWN_SIGNAL,  'Unknown Signal'
    UNEXP_CONT =      TerminationReasons.UNEXP_CONT,      'Unexpected Continuation'
    SABOTAGE =        TerminationReasons.SABOTAGE,        'Code Sabotage'
    XCPUTIME =        TerminationReasons.XCPUTIME,        'CPU Time Exeeded'
    SECCOMP =         TerminationReasons.SECCOMP,         'Seccomp'


class FightQuerySet(models.QuerySet):
    def finished(self):
        return self.filter(finished_at__isnull=False)
    
    def not_started(self):
        return self.filter(started_at__isnull=True)
    
    def ongoing(self):
        return self.filter(finished_at__isnull=True,
                           started_at__isnull=False)
    
    def unfinished(self):
        return self.filter(finished_at__isnull=True)
    
    def has_player(self, player):
        # This will make an INNER JOIN from the Fight table to the
        # PlayerFight table with the given condition. Without this
        # condition we'd get duplicate rows (as there are multiple
        # players per fight).
        return self.filter(players__in=[player])
    
    def from_uuid(self, uuid):
        try:
            return self.filter(uuid=uuid).first()
        except ValidationError:
            return self.none()
    
    def prefetch_players(self, *, user_fields=None):
        players_queryset = User.objects.all()
        
        if user_fields:
            players_queryset = players_queryset.only(*user_fields)
        
        return self.prefetch_related(
            models.Prefetch(
                'players',
                queryset=players_queryset
            )
        )
    
    def prefetch_playerfights_with_players(self, *, playerfight_fields=None, user_fields=None, order_by=None):
        """Prefetch the PlayerFight objects for the Fight queryset, as well as their players.

        Parameters
        ----------
        playerfight_fields : List[str], optional
            A list of the PlayerFight fields to be selected in fetching. If None,
            it would select all the fields.
        
        user_fields : List[str], optional
            A list of the User fields for each PlayerFight's 'player' to be selected
            in fetching. If None, it would select all the fields.
        """
        
        playerfight_queryset = PlayerFight.objects.select_related('player')
        
        if order_by:
            playerfight_queryset = playerfight_queryset.order_by(order_by)
        
        final_fields = []
        
        # Since .only() operates on all relations and we cannot seperate them, if
        # one of the given fields lists are empty, then we have to manually retrieve
        # the field names of the other and include them in .only() to reach the
        # promised behavior (that if the argument is None, it means all fields).
        if playerfight_fields or user_fields:
            if playerfight_fields:
                final_fields.extend(playerfight_fields)
            else:
                final_fields.extend([
                    field.name for field in PlayerFight._meta.local_fields
                ])
        
            if user_fields:
                final_fields.extend([f'player__{field}' for field in user_fields])
            else:
                final_fields.extend([
                    f'player__{field.name}' for field in User._meta.local_fields
                ])
        
        # The reason 'fight__id' is selected is so that prefetch_related() can
        # actually associate each playerfight with its corresponding fight in
        # the queryset of fights. If we don't include it, we'd get an extra
        # query for EACH playerfight to find its fight id, which effectively
        # destroys most of the benefit we get from prefetching. To observe this
        # behavior, you may evaluate the queries and check db.connection.queries
        # for the queries that django would issue.
        #
        # Also note that if we don't use .only(), all the fields of the playerfights
        # will be selected, including their fight id. Therefore we're fine not
        # including 'fight' in the select_related() above.
        if final_fields:
            playerfight_queryset = playerfight_queryset.select_related(
                'fight'
            ).only(
                'fight__id',
                *final_fields
            )
        
        return self.prefetch_related(
            models.Prefetch(
                'playerfight_set',
                queryset=playerfight_queryset
            )
        )


class PublicFightsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_public=True)


class Fight(models.Model):
    class Meta:
        indexes = [
            # We index all the Fight's that have not been finished yet.
            # Note that generally only a small portion of the fights will
            # be unfinished, so this index can be helpful.
            models.Index(
                'id',  # dummy
                condition=models.Q(finished_at__isnull=True),
                name='unfinished_fights_idx'
            ),
            
            # NOTE: Maybe we should have a multi-column index of
            # the 'id' and the 'uuid', as querying PlayerFight's
            # of a certain fight uses its the fight's id.
            models.Index('uuid', name='fight_uuid_idx'),
            
            models.Index('finished_at', name='fight_finished_at_idx')
        ]
    
    game = models.ForeignKey(GameInfo, on_delete=models.CASCADE)
    
    # Must be either blank or JSON. Currently we don't need the
    # game settings anywhere other than game classes and their
    # frontends, so this is basically just a storage. For this
    # reason, we use a TextField instead of JSONField.
    game_settings = models.TextField(default='', blank=True, null=True)
    
    players = models.ManyToManyField(settings.AUTH_USER_MODEL, through='fights.PlayerFight')
    
    # Before the fight simulation is done, the result is going to be null.
    # result = models.OneToOneField(GameResult, on_delete=models.CASCADE, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # This should be updated when the simulation starts. It may not
    # start after creation if some players have not accepted their
    # invitations.
    started_at = models.DateTimeField(blank=True, null=True)
    
    # This should be updated when the simulation is finished.
    finished_at = models.DateTimeField(blank=True, null=True)
    
    is_public = models.BooleanField(default=True)
    
    # PostgreSQL doesn't save the dashes of the UUID. Plus, we can
    # access the undashed version by instance.uuid.hex.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    
    def set_started_now(self):
        self.started_at = timezone.now()
        self.save(update_fields=['started_at'])
    
    def get_absolute_url(self):
        return reverse('view_fight', kwargs={'uuid': self.uuid.hex})
    
    def __str__(self):
        if self.finished_at is None:
            if self.started_at is None:
                title = 'Not started'
            else:
                title = 'Simulating'
        else:
            title = 'Finished'
        
        return f'{self.id}. {self.game.title} ({title})' + (' [Public]' if self.is_public else '')
    
    objects = models.Manager.from_queryset(FightQuerySet)()
    public = PublicFightsManager.from_queryset(FightQuerySet)()


class PlayerFightQuerySet(models.QuerySet):
    def of_finished_fight(self):
        return self.filter(fight__finished_at__isnull=False)
    
    def of_unfinished_fight(self):
        return self.filter(fight__finished_at__isnull=True)
    
    def of_not_started_fight(self):
        return self.filter(fight__started_at__isnull=True)
    
    def of_ongoing_fight(self):
        return self.filter(fight__finished_at__isnull=True,
                           fight__started_at__isnull=False)
    
    def of_player(self, player):
        return self.filter(player=player)
    
    def prefetch_playerfights_with_players_of_fight(self, *, playerfight_fields=None, user_fields=None, order_by=None):
        """Prefetch the PlayerFight's and the players for each Fight of the PlayerFight queryset.
        
        This is best applicable when each PlayerFight belongs to a different Fight,
        as otherwise some prefetch queries might be unnecesserily issued more than
        once. Also note that if the the queryset does not in some way select the
        fight (e.g., .select_related('fight').only(...)), then this method would
        prefetch the entire fight. So if you don't want to fetch the entire fight,
        select the needed fields explicitly in the queryset.

        Parameters
        ----------
        playerfight_fields : List[str], optional
            A list of the PlayerFight fields to be selected in fetching. If None,
            it would select all the fields.
        
        user_fields : List[str], optional
            A list of the User fields for each PlayerFight's 'player' to be selected
            in fetching. If None, it would select all the fields.
        """
        
        playerfight_queryset = PlayerFight.objects.select_related('player')
        
        if order_by:
            playerfight_queryset = playerfight_queryset.order_by(order_by)
        
        final_fields = []
        
        # Since .only() operates on all relations and we cannot seperate them, if
        # one of the given fields lists are empty, then we have to manually retrieve
        # the field names of the other and include them in .only() to reach the
        # promised behavior (that if the argument is None, it means all fields).
        if playerfight_fields or user_fields:
            if playerfight_fields:
                final_fields.extend(playerfight_fields)
            else:
                final_fields.extend([
                    field.name for field in PlayerFight._meta.local_fields
                ])
        
            if user_fields:
                final_fields.extend([f'player__{field}' for field in user_fields])
            else:
                final_fields.extend([
                    f'player__{field.name}' for field in User._meta.local_fields
                ])
        
        # The reason 'fight__id' is selected is so that prefetch_related() can
        # actually associate each playerfight with its corresponding fight in
        # the queryset of fights. If we don't include it, we'd get an extra
        # query for EACH playerfight to find its fight id, which effectively
        # destroys most of the benefit we get from prefetching. To observe this
        # behavior, you may evaluate the queries and check db.connection.queries
        # for the queries that django would issue.
        #
        # Also note that if we don't use .only(), all the fields of the playerfights
        # will be selected, including their fight id. Therefore we're fine not
        # including 'fight' in the select_related() above.
        if final_fields:
            playerfight_queryset = playerfight_queryset.select_related(
                'fight'
            ).only(
                'fight__id',
                *final_fields
            )
        
        return self.prefetch_related(
            models.Prefetch(
                'fight__playerfight_set',
                queryset=playerfight_queryset
            )
        )



def get_sentinel_user():
    # For deleted users.
    return get_user_model().objects.get_or_create(username="_")[0]


class PlayerFight(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fight', 'player'], name='unique_fight_and_player')
        ]
    
    def get_code_upload_path(self, _):
        return settings.FIGHT_CODES_DIR / f'{get_random_string(length=32)}.py'

    fight = models.ForeignKey(Fight, on_delete=models.CASCADE)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET(get_sentinel_user))
    
    code_file = models.FileField(upload_to=get_code_upload_path)
    
    # Empty string will mean that the execution was fully successful for
    # the player code through the entire length of the simulation.
    termination_reason = models.CharField(choices=TerminationReasonsChoices, blank=True)
    
    # This can be a JSON that contains extra details on how the termination
    # has happened. Currently this is only used in case of an illegal syscall.
    # Since this will be an small JSON, we're using the possibly slow JSONB.
    termination_reason_extra = models.JSONField(blank=True, null=True)
    
    # In some cases, there might be no waitpid state reported and thus
    # we pass NULL. Note that only a status of 0 would mean an entirely
    # successful run.
    final_waitpid_state = models.IntegerField(null=True, blank=True)
    
    # We could have separate models (and thus tables) for each game and save
    # game results for each type of game separately. This way we could avoid
    # having empty columns when the game doesn't support a certain feature.
    # This, however, comes at a great cost when it comes to joining fights
    # with mixed game types. Space-wise, these null columns shouldn't be a
    # problem at all (as a ballpark estimate would show). Therefore, we decided
    # to do it this way.
    
    # If the game doesn't have a support for scores, this must be null.
    score = models.IntegerField(blank=True, null=True)
    
    # If the game is a Victory-Draw game, this must be null for a draw,
    # 1 for win and 0 for lost.
    won_or_rank = models.IntegerField(blank=True, null=True)
    
    def __str__(self):       
        return f'{self.id}. {self.fight.game.title} (@{self.player.username})'
    
    objects = models.Manager.from_queryset(PlayerFightQuerySet)()
    

class HostingQuerySet(models.QuerySet):
    def of_host(self, host):
        return self.filter(host=host)
    
    def prefetch_pending_and_accepted_invitations(self, *, invitation_fields=None, user_fields=None):
        accepted_queryset = Invitation.accepted.select_related('target', 'hosting')
        pending_queryset = Invitation.pending.select_related('target', 'hosting')
        
        final_fields = []
        
        # Since .only() operates on all relations and we cannot seperate them, if
        # one of the given fields lists are empty, then we have to manually retrieve
        # the field names of the other and include them in .only() to reach the
        # promised behavior (that if the argument is None, it means all fields).
        if invitation_fields or user_fields:
            if invitation_fields:
                final_fields.extend(invitation_fields)
            else:
                final_fields.extend([
                    field.name for field in Invitation._meta.local_fields
                ])
        
            if user_fields:
                final_fields.extend([f'target__{field}' for field in user_fields])
            else:
                final_fields.extend([
                    f'target__{field.name}' for field in User._meta.local_fields
                ])
        
        # The reason 'hosting__id' is selected is so that prefetch_related()
        # can actually associate each invitation with its corresponding hosting
        # in the queryset of hostings. If we don't include it, we'd get an extra
        # query for EACH invitation to find its hosting id, which effectively
        # destroys most of the benefit we get from prefetching. To observe this
        # behavior, you may evaluate the queries and check db.connection.queries
        # for the queries that django would issue.
        if final_fields:
            final_fields.append('hosting__id')
            
            accepted_queryset = accepted_queryset.only(*final_fields)
            pending_queryset = pending_queryset.only(*final_fields)

        
        return self.prefetch_related(
            models.Prefetch(
                'invitation_set',
                queryset=accepted_queryset,
                to_attr='accepted_invitations'
            ),
            models.Prefetch(
                'invitation_set',
                queryset=pending_queryset,
                to_attr='pending_invitations'
            )
        )


class Hosting(models.Model):
    host = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    
    fight = models.OneToOneField(Fight, on_delete=models.CASCADE)
    
    def get_pending_and_accepted_invitations(self, *, invitation_fields=None, user_fields=None):
        """Get a dictionary of both the pending and the accepted invitations.
        
        This is useful for constructing context data.
        """
        accepted_queryset = self.invitation_set.accepted()
        pending_queryset = self.invitation_set.pending()
        
        final_fields = []
        
        # Since .only() operates on all relations and we cannot seperate them, if
        # one of the given fields lists are empty, then we have to manually retrieve
        # the field names of the other and include them in .only() to reach the
        # promised behavior (that if the argument is None, it means all fields).
        if invitation_fields or user_fields:
            if invitation_fields:
                final_fields.extend(invitation_fields)
            else:
                final_fields.extend([
                    field.name for field in Invitation._meta.local_fields
                ])
        
            if user_fields:
                final_fields.extend([f'target__{field}' for field in user_fields])
            else:
                final_fields.extend([
                    f'target__{field.name}' for field in User._meta.local_fields
                ])
        
        
        if final_fields:
            final_fields.append('hosting__id')
            
            accepted_queryset = accepted_queryset.only(*final_fields)
            pending_queryset = pending_queryset.only(*final_fields)
                
        
        return {
            'accepted_invitations': accepted_queryset,
            'pending_invitations': pending_queryset
        }
    
    def __str__(self):       
        return f'{self.id}. @{self.host.username} hosting {self.invitation_set.count()} players ({self.fight.game.title})'
    
    objects = models.Manager.from_queryset(HostingQuerySet)()


class FilteredInvitationQuerySet(models.QuerySet):
    def from_uuid_and_target(self, *, uuid, target):
        try:
            return self.filter(uuid=uuid, target=target).first()
        except ValidationError:
            return self.none()
    
    def of_fight(self, fight=None, *, fight_id=None):
        if fight_id is None:
            return self.filter(hosting__fight=fight)
        elif fight is None:
            self.filter(hosting__fight__id=fight_id)
        else:
            raise ValueError("exactly one of 'fight' or 'fight_id' must be None")
        
    def get_target_players(self, *, fields=None):
        """Get a list of all the target players of the given invitation queryset.
        
        It must be noted that if 'fields' is specified, then one should lookup
        only those attributes on each given player object. If attempted to get
        or evaluate the player object itself (e.g., repr(targets[0])) or if any
        field other than the ones specified is looked up on a target player, it
        would make another query to the database the retrieve the full player
        object.
        """
        if fields is None:
            # will select all the fields on the target User object.
            return [inv.target for inv in self.select_related('target')]
        else:
            return [inv.target for inv in self.select_related('target').only(
                *[f'target__{field}' for field in fields]
            )]


class InvitationQuerySet(FilteredInvitationQuerySet):
    def accepted(self):
        return self.filter(is_accepted=True)
    
    def pending(self):
        return self.filter(is_accepted=False)
    
    def of_target(self, target):
        return self.filter(target=target)
    
    def prefetch_pending_and_accepted_invitations_of_hosting(self, *, user_fields=None):
        """Prefetch the pending and accepted invitations of hostings of the invitation queryset.
        
        This is best applicable when each Invitation belongs to a different target,
        as otherwise some prefetch queries might be unnecesserily issued more than
        once. Also note that if the the queryset does not in some way select the
        hosting (e.g., .select_related('hosting').only(...)), then this method would
        prefetch the entire hosting. So if you don't want to fetch the entire hosting,
        select the needed fields explicitly in the queryset.

        Parameters
        ----------
        user_fields : List[str], optional
            A list of the User fields for each Invitation's 'target' to be selected
            in fetching. If None, it would select all the fields.
        """

        accepted_queryset = Invitation.accepted.select_related('target')
        pending_queryset = Invitation.pending.select_related('target')
        
        # The reason 'hosting__id' is selected is so that prefetch_related()
        # can actually associate each invitation with its corresponding hosting
        # in the queryset of hostings. If we don't include it, we'd get an extra
        # query for EACH invitation to find its hosting id, which effectively
        # destroys most of the benefit we get from prefetching. To observe this
        # behavior, you may evaluate the queries and check db.connection.queries
        # for the queries that django would issue.
        if user_fields:
            only_fields = ['hosting__id'] + [f'target__{field}' for field in user_fields]
        
            accepted_queryset = accepted_queryset.select_related('hosting').only(*only_fields)
            pending_queryset = pending_queryset.select_related('hosting').only(*only_fields)
        
        
        return self.prefetch_related(
            models.Prefetch(
                'hosting__invitation_set',
                queryset=accepted_queryset,
                to_attr='accepted_invitations'
            ),
            models.Prefetch(
                'hosting__invitation_set',
                queryset=pending_queryset,
                to_attr='pending_invitations'
            )
        )


class AcceptedInvitationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_accepted=True)


class PendingInvitationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_accepted=False)


class Invitation(models.Model):
    class Meta:
        indexes = [
            models.Index('target', 'uuid', name='invitation_target_and_uuid_idx')
        ]
    
    hosting = models.ForeignKey(Hosting, on_delete=models.CASCADE)
    
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # PostgreSQL doesn't save the dashes of the UUID. Plus, we can
    # access the undashed version by instance.uuid.hex.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    
    # This serves two purposes:
    # 1. One can attend a fight, and given that the fight would
    #    not auto-start, can later change their code before the
    #    fight starts.
    # 2. Makes canceling attendances easier, query-wise.
    is_accepted = models.BooleanField(default=False)
    
    def mark_accepted(self):
        self.is_accepted = True
        self.save(update_fields=['is_accepted'])
    
    def mark_pending(self):
        self.is_accepted = False
        self.save(update_fields=['is_accepted'])
    
    def get_absolute_url(self):
        return reverse('view_invitation', kwargs={'uuid': self.uuid.hex})
    
    def __str__(self):       
        return f'{self.id}. @{self.target.username} invited by @{self.hosting.host.username} ({self.hosting.fight.game.title})'
    
    objects = models.Manager.from_queryset(InvitationQuerySet)()
    accepted = AcceptedInvitationsManager.from_queryset(FilteredInvitationQuerySet)()
    pending = PendingInvitationsManager.from_queryset(FilteredInvitationQuerySet)()
