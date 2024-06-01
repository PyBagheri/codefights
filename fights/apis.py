from django.http import JsonResponse
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.models import User

from fights.forms import SearchPlayerToInviteAPIForm

import json


class SearchPlayerToInviteAPIView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            json_body = json.loads(request.body.decode())
        except json.decoder.JSONDecodeError:
            return JsonResponse({'success': False})
        
        form = SearchPlayerToInviteAPIForm(json_body)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            
            # You can't invite yourself :/
            if username == request.user.username:
                return JsonResponse({'success': False})
            
            try:
                User.active.get(username=username)
                return JsonResponse({'success': True})
            except User.DoesNotExist:
                return JsonResponse({'success': False})
        else:
            return JsonResponse({'success': False})

