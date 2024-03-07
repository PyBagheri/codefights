from django.conf import settings
from django.core.handlers.asgi import ASGIRequest
from django.middleware.csrf import CsrfViewMiddleware
from importlib import import_module
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, load_backend
from asgiref.sync import sync_to_async
from django.urls import resolve, Resolver404
from django.core.exceptions import BadRequest



session_engine = import_module(settings.SESSION_ENGINE)

# Note that 'CsrfViewMiddleware' is a middleware factory;
# we have to instantiate it to get the actual middleware.
# Here we only want to use it for token validation, and
# we don't care about the actual response, thus for the
# 'get_response', we give a dummy lambda function.
csrf_middleware = CsrfViewMiddleware(lambda _: None)


# TODO:
# 1. Limit the number of simultaneous WS connection from an IP.
async def websocket_application(scope, receive, send):
    '''
    Authenticate and validate WebSocket connections and pass
    them to corresponding functions in applications.
    
    The assumption here is that the WSGI version of the website
    will provide the user with session and CSRF cookies and
    the 'csrfmiddlewaretoken'.
    
    The cookies will be sent upon the handshake for the WebSocket,
    and the next message must be the 'csrfmiddlewaretoken'. Note
    that WebSocket handshake is only defined by with the GET method,
    thus we cannot send the 'csrfmiddlewaretoken' as non-cookie data,
    unless we use GET query strings (which are prone to being logged
    since they are part of the URL). Plus, WebSocket browser API's
    don't support custom headers, but we could send the token through
    the Sec-WebSocket-Protocol header (which is not what it's intended for);
    In the end, I preferred to use a separate message to communicate the
    'csrfmiddlewaretoken' value.
    
    Therefore, this piece of code is not intended to authenticate
    the user by credentials (e.g., username and password) or to
    provide the 'csrfmiddlewaretoken'. This is the responsibility
    of the WSGI version of the website.
    
    One thing to note is that the CSRF middleware also checks if the
    request has a trusted "Origin" header (a real browser won't let
    the client to change the value of this header. A fake/manipulated
    browser can, but the intent is mainly to protect the client
    from cross-origin attacks; either way, we should not use it to
    protect the server). Also, if the connection is secure (HTTPS)
    but the "Origin" header is not set, the CSRF middleware requires
    a "Referrer" header. To protect the users yet and keep the
    CSRF middleware functional, we might set the "Referrer-Policy"
    header to 'same-origin' mode (according to the docs).
    '''
    
    # Once the authentication and CSRF validation is over,
    # this will be set to the corresponding user object.
    user = None
    
    while True:
        event = await receive()
        
        # A new handshake.
        if event['type'] == 'websocket.connect':
            # A bit of hacking: let the CSRF middleware think that
            # we are passing it a POST request, so it directly jumps onto
            # validating the token.
            scope['method'] = 'POST'
            
            # no 'body_file' argument, since we don't care about communication for this,
            # we just want to parse the ASGI 'scope' into a request object that we can pass
            # to the CSRF middleware to check if the token is OK.
            request = ASGIRequest(scope, None)
                        
            session_id = request.COOKIES.get(settings.SESSION_COOKIE_NAME, None)
            
            if not session_id:
                await send({'type': 'websocket.close'})
                return
                
            # This doesn't immediately raise an error if
            # the session id cookie is invalid. We have to 
            # check a key to see.
            session = session_engine.SessionStore(session_id)
            
            try:
                # session key is the user id. session[BACKEND_SESSION_KEY] refers
                # to the path of the backend that has originally authenticated
                # the user.
                user = await sync_to_async(
                    lambda: load_backend(session[BACKEND_SESSION_KEY]).get_user(session[SESSION_KEY])
                )()
                                
                # Authentication has been successful. I explicitly
                # put this inside the try block to avoid future bugs;
                # connection must never be accepted, unless the user
                # is authenticated. Otherwise we might face DOS attacks.
                await send({'type': 'websocket.accept'})
            except KeyError:
                # Invalid session id cookie
                await send({'type': 'websocket.close'})
                return
            

            # Time for CSRF validation. The immediately next
            # message must be the 'csrfmiddlewaretoken'.
            #
            # If the ASGI web server crashes, the sockets will
            # get destroyed, and thus after the server is restarted,
            # a previously connected client cannot send data (which
            # will emerge as the 'websocket.receive' event) and
            # bypass the CSRF validation.
            first_next_event = await receive()
            
            # The actual request is a WebSocket one, not HTTP.
            # Here we are (ab)using the CSRF middleware by making
            # it think that this is an HTTP POST request, since
            # Django, and thus its default middlewares, don't support
            # WebSocket requests.
            request.POST = {'csrfmiddlewaretoken': first_next_event['text']}    

            # Again, we only care about the CSRF validation, not the
            # actual response. Therefore, our view (the 'callback' parameter)
            # is set to a dummy lambda function, with empty args and kwargs.
            # (note that the first argument to the view is always the request,
            # which is not included in the 'callback_args' argument).
            #
            # The 'process_view' function will eventually return None if the
            # validation is successful.
            # See: https://github.com/django/django/blob/main/django/middleware/csrf.py
            if csrf_middleware.process_view(request, lambda _: None, (), ()) is not None:
                await send({'type': 'websocket.close'})
                return

        elif event['type'] == 'websocket.disconnect':
            # possible cleanups or signals.
            break

        elif event['type'] == 'websocket.receive':
            # At this stage, the security checks are over
            # and 'user' is guaranteed to exist.
            
            path = scope['path']
            if settings.APPEND_SLASH and not path.endswith('/'):
                path += '/'
            
            try:
                # 'path' will contain a leading slash, but
                # the urlconf entries should not, as 'resolve'
                # will take care of it.
                ws_view, args, kwargs = resolve(path, urlconf=settings.WEBSOCKET_ROOT_URLCONF)                
            except Resolver404:
                # Don't bother keeping the socket open.
                # maybe someone is fiddling with the API :/
                await send({'type': 'websocket.close'})
                return
            
            # Basically, our WebSocket will be a private API
            # for the moment. Thus there shouldn't be any
            # wrong or bad requests, unless someone is messing
            # with the API, in which case we don't bother keeping
            # the connection open.
            #
            # It's the WebSocket view's responsibility to raise
            # a BadRequest error in case of a "bad" request.
            try:
                response = await ws_view(user, event['text'], *args, **kwargs)
                
                # Note that 'response' might be an empty string,
                # so it's important to check only againts None
                # for the case the view doesn't return anything
                # or just returns None.
                if response is not None:
                    await send({'type': 'websocket.send', 'text': response})
            except BadRequest:
                await send({'type': 'websocket.close'})
                return
