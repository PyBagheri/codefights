from django.views.generic import ListView, DetailView
from gamespecs.models import GameInfo, GameTemplate


class GamesListView(ListView):
    template_name = 'games_list.html'
    
    model = GameInfo
    context_object_name = 'games_list'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        return queryset.filter(is_visible=True)


class GameDetailsView(DetailView):
    template_name = 'game_details.html'
    
    model = GameInfo
    context_object_name = 'game_info'
        
    def get_queryset(self):
        queryset = super().get_queryset()
        
        return queryset.filter(is_visible=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['templates'] = GameTemplate.objects.filter(game=context['game_info'])
        
        return context
    
