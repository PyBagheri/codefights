from django.urls import path
from fights.views import (
    PublicFightsView,
    CreateFightView,
    ViewInvitationView,
    DashboardView,
    DismissInvitationView,
    CancelHostedFightView,
    StartHostedFightView,
    CancelFightAttendanceView,
    ViewFightView,
    PlayerFightsView,
    InvitationsListView
)
from fights.apis import SearchPlayerToInviteAPIView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('public/', PublicFightsView.as_view(), name='public_fights'),
    path('all/', PlayerFightsView.as_view(), name='player_fights_list'),
    path('create/<slug:game_slug>/', CreateFightView.as_view(), name='create_fight'),
    path('invitations/all/', InvitationsListView.as_view(), name='invitations_list'),
    path('invitations/<str:uuid>/', ViewInvitationView.as_view(), name='view_invitation'),
    path('view/<str:uuid>/', ViewFightView.as_view(), name='view_fight'),
    
    path('api/search/player/', SearchPlayerToInviteAPIView.as_view()),
    path('api/invitation/<str:uuid>/dismiss/', DismissInvitationView.as_view(), name='api_dismiss_invitation'),
    path('api/invitation/<str:uuid>/cancel/', CancelFightAttendanceView.as_view(), name='api_cancel_attendance'),
    path('api/hosting/cancel/', CancelHostedFightView.as_view(), name='api_cancel_hosted'),
    path('api/hosting/start/', StartHostedFightView.as_view(), name='api_start_hosted_fight')
]
