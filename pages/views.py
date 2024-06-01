from typing import Any
from django.shortcuts import render
from django.views.generic import TemplateView


class Handler404(TemplateView):
    template_name = '404.html'


class Handler500(TemplateView):
    template_name = '500.html'


class GuideView(TemplateView):
    template_name = 'guide.html'
    