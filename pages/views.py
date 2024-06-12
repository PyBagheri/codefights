from django.http import Http404
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View

from pages.models import PageContent


class ContentView(TemplateView):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        
        try:
            context['content'] = PageContent.objects.get(
                page_name=self.page_name
            ).content
        except PageContent.DoesNotExist:
            # Shouldn't really happen, as we specify the names ourselves.
            raise Http404
        
        return context
            
    


class Handler404(View):
    template_name = '404.html'
    
    def get(self, request, *args, **kwargs):
        return render(
            request=request,
            template_name=self.template_name,
            status=404
        )


class Handler500(View):
    template_name = '500.html'
    
    def get(self, request, *args, **kwargs):
        return render(
            request=request,
            template_name=self.template_name,
            status=500
        )


class HomeView(ContentView):
    template_name = 'home.html'
    page_name = 'home'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        return super().get(request, *args, **kwargs)


class GuideView(ContentView):
    template_name = 'guide.html'
    page_name = 'guide'


# TODO: Add a form for the user to be able to change their
# email address (and possibly other things too, except the
# username).
class SettingsView(TemplateView):
    template_name = 'settings.html'
