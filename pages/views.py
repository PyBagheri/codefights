from typing import Any
from django.shortcuts import render
from django.views.generic import TemplateView, View


class Handler404(TemplateView):
    template_name = '404.html'


class Handler500(TemplateView):
    template_name = '500.html'


class GuideView(TemplateView):
    template_name = 'guide.html'


# TODO: Add a form for the user to be able to change their
# email address (and possibly other things too, except the
# username).
class SettingsView(TemplateView):
    template_name = 'settings.html'
