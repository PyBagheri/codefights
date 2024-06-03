from typing import Any, Coroutine
from django_project.websocket.views import WSView
from django_project.websocket.decorators import ws_login_required

# async def fffff(user ,data):
#     print('LLLLLLLLLLLLLLLLLLLLL', user ,data)
#     return 'OOOOOOOOOOOOOOOOOOOOOOOOOOOOOoo you\'re %s' % user



class TestView(WSView):
    # signal methods
    async def check_shalgham(self):
        return True
    
    async def check_gojah(self):
        return False
    
    async def render_shalgham(self, message=None):
        return '{"hi": "shalgham activated for userid %s"}' % self.user.id
    
        
    async def render_gojah(self, message=None):
        return '{"hi": "shalgham activated for userid %s with message %s"}' % (self.user.id, str(message))
    
    oneoff_signals = {
        'shalgham_{user.id}': (check_shalgham, render_shalgham),
        'gojah_{user.id}': (check_gojah, render_gojah)
    }
    
    
    
    async def render_rl1(self, message):
        return '{"hi": "rl1 %s for userid %s"}' % (message, self.user.id,)
    
    async def render_rl2(self, message):
        return '{"hi": "rl2 %s for userid %s"}' % (message, self.user.id,)
    
    realtime_signals = {
        'rl1': render_rl1,
        'rl2': render_rl2,
    }
    
    # @ws_login_required
    async def user_has_permission(self):
        return True
    
    async def process_message(self, message):
        if message == 'shoot':
            return 'shoot back u little shoop'
