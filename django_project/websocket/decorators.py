from functools import wraps

def ws_login_required(uhp_func):
    """Mandate user authentication for WebSocket views.
    
    This decorator should be used on the 'user_has_permission'
    function (which all WebSocket views must override).
    """
    @wraps(uhp_func)
    async def func(self):
        return self.user.is_authenticated and uhp_func(self)
    
    return func