from django.db import models, transaction
from django.http import Http404, HttpRequest, HttpResponseBadRequest
from django.http.response import HttpResponse as HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin

from fights.models import Fight, PlayerFight, Invitation, Hosting, TerminationReasons
from accounts.models import User
from gamespecs.models import GameInfo

from common.forms import BeforeAfterUUIDForm
from fights.forms import (
    CreateFightForm,
    AcceptInvitationForm,
    ConfirmationForm
)

from fights.services import (
    CreateFightService,
    CheckUserAttendedFightsFullService,
    AcceptInvitationService,
    StartHostedFightService,
    DismissInvitationService,
    CancelHostedFightService,
    CancelAcceptedInvitationService
)

from games.frontend import EXPLANATION_INDEX

# cache
ConclusionSystems = GameInfo.ConclusionSystems


class BeforeAfterPaginator:
    def __init__(self, *, items_queryset, selection_queryset=None, selection_field, orders, comparison_fields=None, items_per_page):
        if selection_queryset is None:
            selection_queryset = items_queryset
        
        # Each item in the comparison_fields must be an iterable
        # of length 2, where the first item shows the field name
        # and the second one indicates if we should include results
        # when the value is equal too (i.e., use __gt/__lt or __gte/__lte).
        if comparison_fields is None:
            comparison_fields = []
            for order in orders:
                if order.startswith('-') or order.startswith('+'):
                    comparison_fields.append((order[1:], False))
                else:
                    comparison_fields.append((order, False))
        
        self.comparison_fields = comparison_fields
        
        self.items_queryset = items_queryset
        self.selection_queryset = selection_queryset
        self.selection_field = selection_field
        self.orders = orders
        self.items_per_page = items_per_page
    
    def paginate(self, *, after=None, before=None):
        if before and after:
            raise Http404
        
        self.has_next_page = self.has_previous_page = False
        
        # Will be converted to list at some point.
        items = self.items_queryset
        
        if after:
            items = items.order_by(*self.orders).reverse()
        else:
            items = items.order_by(*self.orders)
        
        if before:
            selected_item = self.selection_queryset.filter(
                **{self.selection_field: before}
            ).first()
            
            if not selected_item:
                raise Http404
            
            filter_dict = {}
            for field_name, count_equal in self.comparison_fields:
                comparison_value = selected_item  # to be traversed
                for attr in field_name.split('__'):
                    comparison_value = getattr(comparison_value, attr)
                
                filter_dict[field_name + ('__lte' if count_equal else '__lt')] = comparison_value
            
            # TODO: Check if this is enough; In the case where we
            # use a timestamp, maybe there is an overlap because, 
            # for example, a fight finished at the same time as the
            # fight we compare to its finished_at. If this wasn't
            # enough, *maybe* compare the id's too.
            items = items.filter(**filter_dict)

            items = list(items[:self.items_per_page+1])
            
            if len(items) == self.items_per_page+1:
                items = items[:-1]
                self.page_last_item = items[-1]
                self.has_next_page = True
            
            self.page_first_item = items[0]
            self.has_previous_page = True
        elif after:
            selected_item = self.selection_queryset.filter(
                **{self.selection_field: after}
            ).first()
            
            if not selected_item:
                raise Http404
            
            filter_dict = {}
            for field_name, count_equal in self.comparison_fields:
                comparison_value = selected_item  # to be traversed
                for attr in field_name.split('__'):
                    comparison_value = getattr(comparison_value, attr)
                
                filter_dict[field_name + ('__gte' if count_equal else '__gt')] = comparison_value
            
            
            # TODO: Check if this is enough; In the case where we
            # use a timestamp, maybe there is an overlap because, 
            # for example, a fight finished at the same time as the
            # fight we compare to its finished_at. If this wasn't
            # enough, *maybe* compare the id's too.
            items = items.filter(**filter_dict)
            
            # We want the reversal to happen in Python, not the DB, so we
            # evaluate it by list(...) first.
            items = list(reversed(list(items[:self.items_per_page+1])))
            
            if len(items) == self.items_per_page+1:
                items = items[1:]
                self.page_first_item = items[0]
                self.has_previous_page = True
                    
            self.page_last_item = items[-1]
            self.has_next_page = True
        else:
            items = list(items[:self.items_per_page+1])
            
            if len(items) == self.items_per_page+1:
                items = items[:-1]
                self.page_last_item = items[-1]
                self.has_next_page = True
        
        self.items = items


class PublicFightsView(TemplateView):
    template_name = 'public_fights.html'
    items_per_page = 10
    
    def get_context_data(self, **kwargs):
        ba_form = BeforeAfterUUIDForm(self.request.GET)
        
        if not ba_form.is_valid():
            raise Http404
        
        context = super().get_context_data(**kwargs)
        
        fights_list = Fight.public.finished().select_related('game').only(
            'finished_at',
            'game__title',
            'game__conclusion_system'
        ).prefetch_playerfights_with_players(
            playerfight_fields=['won_or_rank'],
            user_fields=['username'],
            order_by='won_or_rank'  # only useful for rank-based games
        )
        
        paginator = BeforeAfterPaginator(
            items_queryset=fights_list,
            selection_queryset=Fight.public.finished().only('finished_at', 'uuid'),
            selection_field='uuid',
            orders=['-finished_at'],
            items_per_page=self.items_per_page
        )
        
        paginator.paginate(
            before=ba_form.cleaned_data['before'],
            after=ba_form.cleaned_data['after']
        )
        
        
        # TODO: Separating winners from losers or sorting by ranks
        # should be done in JS rather than templates or views.
        for fight in paginator.items:
            # playerfights = PlayerFight.objects.filter(
            #     fight_id=fight.id
            # ).select_related('player').only('won_or_rank', 'player__username')
            
            match fight.game.conclusion_system:
                case ConclusionSystems.VICTORY_DRAW:
                    winners = []
                    losers = []
                    
                    for playerfight in fight.playerfight_set.all():
                        if playerfight.won_or_rank:
                            winners.append(playerfight.player.username)
                        else:
                            losers.append(playerfight.player.username)
                    
                    fight.winners = winners
                    fight.losers = losers
                
                case ConclusionSystems.RANK_BASED:
                    pass

        
        context.update({
            'paginator': paginator,
            
            'ConclusionSystems': ConclusionSystems,
        })
        
        return context


class CreateFightView(LoginRequiredMixin, View):
    template_name = 'create_fight.html'
    
    def get(self, request, *args, **kwargs):
        game_info = self.get_game_info_or_404()
        
        context = self.get_base_context(request)
        context.update(game_info=game_info)
        
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        game_info = self.get_game_info_or_404()
        
        form = CreateFightForm(request.POST, request.FILES)
        
        context = {
            'game_info': game_info,
            'form': form
        }
        
        # CreateFightService will itself check whether the user can
        # create a fight or not. Only when the form fails to validate,
        # we do this check again (through get_base_context()). Note
        # that CreateFightService has to acquire certain locks before
        # this check to ensure that no other fight is created in the
        # mean time; Thus We can't just have one check and use it in
        # the service too.
        if not form.is_valid():
            context.update(self.get_base_context(request))
            return render(request, self.template_name, context)
        
        result = CreateFightService(
            game_info=game_info,
            host=request.user,
            host_code=form.cleaned_data['code'],
            invited_players=User.active.from_username_list(
                form.cleaned_data['usernames_list']
            ),
            is_public=form.cleaned_data['is_public']
        ).execute()
        
        match result:
            case CreateFightService.SUCCESS:
                pass
            
            case CreateFightService.ERROR_ATTENDED_FIGHTS_FULL:
                context['attended_fights_full'] = True
                return render(request, self.template_name, context)
            
            case CreateFightService.ERROR_BAD_REQUEST:
                return HttpResponseBadRequest()
        
        return redirect('dashboard')

    def get_game_info_or_404(self):
        game_info = GameInfo.objects.from_slug_if_visible(
            slug=self.kwargs['game_slug']
        )

        if not game_info:
            raise Http404
        
        return game_info

    def get_base_context(self, request):
        """Get the base context data for showing the create fight page.
        
        The context returned by this method might also be extended as needed.
        Note that, in case we've somehow determined the contexts calculated
        in this method, we don't really need to call it.
        """
        
        return {
            'attended_fights_full':
                CheckUserAttendedFightsFullService(request.user).execute()
        }


class ViewInvitationView(LoginRequiredMixin, View):
    template_name = 'view_invitation.html'

    def get(self, request, *args, **kwargs):
        context = self.get_base_context(request)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = AcceptInvitationForm(request.POST, request.FILES)
        
        context = {'form': form}
        
        if not form.is_valid():
            context.update(self.get_base_context(request))
            return render(request, self.template_name, context)
        
        service = AcceptInvitationService(
            uuid=self.kwargs['uuid'], target=request.user,
            code=form.cleaned_data['code']
        )
        
        result = service.execute(store_invitation=True)
        
        match result:
            case AcceptInvitationService.SUCCESS:
                pass
            
            case AcceptInvitationService.ERROR_NO_SUCH_INVITATION:
                raise Http404
            
            case AcceptInvitationService.ERROR_ATTENDED_FIGHTS_FULL:
                # We used 'store_invitation' in the execute() so that the
                # queried invitation is saved on the service instance, so
                # we can now use it. Note that, as explained, the service
                # must query the invitation itself using a row lock to
                # ensure that it won't be deleted while the processing is
                # being done. Therefore, this option helps us use the cached
                # version rather than having to query the invitation again.
                context.update(
                    self.get_base_context(request, invitation=service.invitation)
                )
                return render(request, self.template_name, context)
            
        return redirect('dashboard')
    
    def get_base_context(self, request, *, invitation=None):
        """Get the base context data for showing the invitation view page.
        
        The context returned by this method might also be extended as needed.
        Note that, in case the invitation is cached, we can pass it to this
        method to avoid another DB query.
        
        Parameters
        ----------
        invitation : Invitation, optional
            If the invitation is cached, it may be passed as this parameter
            to avoid querying the invitation again.
        """
        
        if invitation is None:
            invitation = Invitation.objects.select_related(
                'hosting__fight',
                'hosting__fight__game',
                'hosting__host'
            ).only(
                'uuid',
                'is_accepted',
                
                'hosting__fight__is_public',
                'hosting__fight__created_at',
                
                'hosting__fight__game__title',
                'hosting__fight__game__slug',
                
                'hosting__host__username',
            ).from_uuid_and_target(
                uuid=self.kwargs['uuid'],
                target=request.user
            )
            
            if not invitation:
                raise Http404
        
        context = {
            'invitation': invitation
        }
        
        try:
            context.update(
                invitation.hosting.get_pending_and_accepted_invitations(
                    user_fields=['username']
                )
            )
        # The hosting might have been deleted in the mean time
        # before we reference (and thus cache) it.
        except Hosting.DoesNotExist:
            raise Http404
        
        context['attended_fights_full'] =  \
            CheckUserAttendedFightsFullService(request.user).execute()

        return context


class StartHostedFightView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = ConfirmationForm(request.POST)
        
        if not form.is_valid() or form.cleaned_data['confirmed'] == False:
            return HttpResponseBadRequest()

        result = StartHostedFightService(host=request.user).execute()
        
        match result:
            case StartHostedFightService.SUCCESS:
                pass
            
            case StartHostedFightService.ERROR_NO_SUCH_HOSTING:
                raise Http404
            
            case StartHostedFightService.ERROR_BAD_REQUEST:
                return HttpResponseBadRequest()
        
        return redirect('dashboard')


class DismissInvitationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = ConfirmationForm(request.POST)
        
        if not form.is_valid() or form.cleaned_data['confirmed'] == False:
            return HttpResponseBadRequest()
        
        DismissInvitationService(
            uuid=self.kwargs['uuid'],
            target=request.user
        ).execute()
        
        # We don't care about possible errors; just redirect to dashboard.
        return redirect('dashboard')


class CancelHostedFightView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = ConfirmationForm(request.POST)
        
        if not form.is_valid() or form.cleaned_data['confirmed'] == False:
            return HttpResponseBadRequest()
        
        CancelHostedFightService(host=request.user).execute()
        
        # We don't care about possible errors; just redirect to dashboard.
        return redirect('dashboard')


class CancelFightAttendanceView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = ConfirmationForm(request.POST)
        
        if not form.is_valid() or form.cleaned_data['confirmed'] == False:
            return HttpResponseBadRequest()
        
        result = CancelAcceptedInvitationService(
            uuid=self.kwargs['uuid'],
            target=request.user
        ).execute()
        
        match result:
            case CancelAcceptedInvitationService.SUCCESS:
                pass
            
            case CancelAcceptedInvitationService.ERROR_NO_SUCH_INVITATION:
                raise Http404
        
        return redirect('dashboard')


class ViewFightView(TemplateView):
    template_name = 'view_fight.html'
    
    def get_context_data(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            condition = models.Q(players__in=[self.request.user]) | models.Q(is_public=True)
        else:
            condition = models.Q(is_public=True)
        
        fight = Fight.objects.filter(            
            condition,
        ).prefetch_playerfights_with_players(
            playerfight_fields=[
                'won_or_rank',
                'score',
                
                # Currently only used for the current player,
                # if they have participated in this fight.
                'termination_reason',
                'code_file'
            ],
            user_fields=['username'],
            
            # We need the playerfights sorted by id so that we
            # can tell which index belongs to which player.
            order_by='id'
        ).select_related(
            'result',
            'game',
        ).only(
            'uuid',
            'is_public',
            'game_settings',
            
            'result__explanation',
            'result__data',
            
            'game__slug',
            'game__name',  # to access the explanation index
            'game__title',
            'game__conclusion_system',
        ).from_uuid(
            self.kwargs['uuid']
        )
        
        
        if not fight:
            raise Http404
        

        context = {
            'fight': fight,
            'ConclusionSystems': ConclusionSystems,
        }
        
        if self.request.user.is_authenticated:
            for playerfight in fight.playerfight_set.all():
                if self.request.user.id == playerfight.player.id:
                    context.update({
                        'my_playerfight': playerfight
                    })
        
                    # Other reasons are specialized and the user shall not
                    # see them. Plus, in some cases if the player code has
                    # problems, the coderunner would command to exit, which
                    # would cause an IllegalSyscall error (and they are not
                    # allowed to exit on their own); so we don't show the
                    # IllegalSyscall cases either.
                    #
                    # TODO: Check certain code problems upon uploading the code
                    # to make sure it's alright, before even it's sent to the
                    # simulator. This can be done using Python's 'ast' module,
                    # with which we can dissect and assess the abstract syntax
                    # tree of the code. This makes is so that, for example, when
                    # the code doesn't have the 'Main' class, it wouldn't result
                    # in an IllegalSyscall error (as explained above).
                    if playerfight.termination_reason in [TerminationReasons.XCPUTIME, 
                                                          TerminationReasons.ENOMEM]:
                        context['show_termination_reason'] = True
                        
                    break
        
        if fight.result.explanation:
            context['explanation'] = EXPLANATION_INDEX[fight.game.name].get_explanation_text(
                fight.result.explanation
            )
        
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # TODO: Rather than making two queries for accepted and pending
        # players, we should have it all in a single Prefetch() query
        # and include 'is_accepted', and let the frontend JS put each
        # player in the right place (rather than separating them here).
        # The same applies for the rest of the Prefetch()'s below
        #
        # NOTE: If, later, multiple hostings/ongoing fights were allowed,
        # paginate them too (or do something else). Also maybe paginate
        # the invitations too.
        hostings = Hosting.objects.of_host(
            self.request.user
        ).prefetch_pending_and_accepted_invitations(
            user_fields=['username']
        ).select_related(
            'fight', 'fight__game'
        ).only(
            'fight__created_at',
            
            'fight__game__slug',
            'fight__game__title'
        ).order_by('-fight__created_at')
        
        
        ongoing_fights = Fight.objects.ongoing().has_player(
            self.request.user
        ).prefetch_players(
            user_fields=['username']
        ).select_related(
            'game'
        ).only(
            'uuid',
            'started_at',
            
            'game__slug',
            'game__title'
        ).order_by('-started_at')
        
        
        invitations = Invitation.objects.of_target(
            self.request.user
        ).prefetch_pending_and_accepted_invitations_of_hosting(
            user_fields=['username']
        ).select_related(
            'hosting__host',
            'hosting__fight',
            'hosting__fight__game'
        ).only(
            'is_accepted',
            'uuid',
            
            'hosting__host__username',
            
            'hosting__fight__created_at',
            
            'hosting__fight__game__slug',
            'hosting__fight__game__title',
        ).order_by('-is_accepted', '-hosting__fight__created_at')
                
        
        past_playerfights = PlayerFight.objects.of_finished_fight().of_player(
            self.request.user
        ).prefetch_playerfights_with_players_of_fight(
            playerfight_fields=['won_or_rank'],
            user_fields=['username']
        ).select_related(
            'fight', 'fight__game'
        ).only(
            'won_or_rank',
            
            'fight__finished_at',
            'fight__uuid',
            
            'fight__game__slug',
            'fight__game__title',
            'fight__game__conclusion_system'
        ).order_by('-fight__finished_at')[:5]
        
        
        context.update({
            'hostings': hostings,
            'ongoing_fights': ongoing_fights,
            'invitations': invitations,
            'past_playerfights': past_playerfights,
            
            'can_attend_fights': 
                CheckUserAttendedFightsFullService(self.request.user).execute(),
            
            'ConclusionSystems': ConclusionSystems,
        })
        
        return context


class PlayerFightsView(LoginRequiredMixin, TemplateView):
    template_name = 'player_fights_list.html'
    items_per_page = 10
        
    def get_context_data(self, **kwargs):
        ba_form = BeforeAfterUUIDForm(self.request.GET)
        
        if not ba_form.is_valid():
            raise Http404

        context = super().get_context_data(**kwargs)
        
        past_playerfights = PlayerFight.objects.of_finished_fight().of_player(
            self.request.user
        ).prefetch_playerfights_with_players_of_fight(
            playerfight_fields=['won_or_rank'],
            user_fields=['username']
        ).select_related(
            'fight', 'fight__game'
        ).only(
            'won_or_rank',
            
            'fight__finished_at',
            'fight__uuid',
            
            'fight__game__slug',
            'fight__game__title',
            'fight__game__conclusion_system',
        )
        
        paginator = BeforeAfterPaginator(
            items_queryset=past_playerfights,
            selection_queryset=PlayerFight.objects.of_finished_fight().of_player(
                self.request.user
            ).select_related('fight').only(
                # These fields will be used for comparison and selection
                # in the paginator.
                'fight__finished_at',
                'fight__uuid'
            ),
            selection_field='fight__uuid',
            orders=['-fight__finished_at'],
            items_per_page=self.items_per_page
        )

        paginator.paginate(
            before=ba_form.cleaned_data['before'],
            after=ba_form.cleaned_data['after']
        )

        context.update({
            'paginator': paginator,
            
            'ConclusionSystems': ConclusionSystems,
        })
            
        
        return context



class InvitationsListView(TemplateView):
    template_name = 'invitations_list.html'
    items_per_page = 10
        
    def get_context_data(self, **kwargs):
        ba_form = BeforeAfterUUIDForm(self.request.GET)
        
        if not ba_form.is_valid():
            raise Http404
        
        context = super().get_context_data(**kwargs)
        
        invitations = Invitation.objects.of_target(
            self.request.user
        ).prefetch_pending_and_accepted_invitations_of_hosting(
            user_fields=['username']
        ).select_related(
            'hosting__host',
            'hosting__fight',
            'hosting__fight__game'
        ).only(
            'is_accepted',
            'uuid',
            
            'hosting__host__username',
            
            'hosting__fight__created_at',
            
            'hosting__fight__game__slug',
            'hosting__fight__game__title',
        )
        
        paginator = BeforeAfterPaginator(
            items_queryset=invitations,
            selection_queryset=Invitation.objects.of_target(
                self.request.user
            ).select_related('hosting__fight').only(
                'uuid',  # for before/after selection
                'hosting__fight__created_at'  # for before/after comparison
            ),
            selection_field='uuid',
            orders=['-is_accepted', '-hosting__fight__created_at'],
            comparison_fields=[
                ('is_accepted', True),
                ('hosting__fight__created_at', False)
            ],
            items_per_page=self.items_per_page
        )

        paginator.paginate(
            before=ba_form.cleaned_data['before'],
            after=ba_form.cleaned_data['after']
        )
        
        context.update({
            'paginator': paginator,
            
            'ConclusionSystems': ConclusionSystems,
        })
        
        return context
