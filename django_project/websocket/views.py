from typing import Dict, Tuple, Callable, NewType, Any, Coroutine
from collections.abc import AsyncGenerator
from django.contrib.auth import get_user_model
import redis.asyncio
import asyncio


User = NewType('User', get_user_model())

RedisChannelName = NewType('RedisChannelName', str)

WSResponse = NewType('WSResponse', str)
WSMessage = NewType('WSMessage', str)


class WSView:
    """Base class for WebSocket views.

    This class implements the mechanisms for handling signals
    through Redis PubSub.
    
    Signals are specified by each subclass in two categories:
    one-off signals and realtime siganls.
    
    One-off signals are sent to the WebSocket client at most once
    for each connection. If at the time of connection a one-off signal
    happens to be ready, its corresponding response is immediately
    rendered and sent back to the client and is no more listened for.
    Otherwise, it will be listened to along with the other signals.
    The renderer methods for one-off signals must have their single
    non-self argument (the pubsub message) optional. There would be
    no message if the signal is ready at the time of connection.
    
    Realtime signals care only about after the connection has been
    fully established, and they might be triggered many times.
    """
    
    def __init__(self, scope: dict, user: User, *args, **kwargs) -> None:
        self.scope = scope
        self.user = user
        self.args = args
        self.kwargs = kwargs
    
    async def user_has_permission(self) -> Coroutine[Any, Any, bool]:
        """Check if the user has access to this WebSocket view.

        This method must be overriden by the child classes to ensure
        proper access control. If this method returns False, the
        'websocket_application' will terminate the connection.
        """
        return NotImplementedError
    
    @staticmethod
    def format_signals(signals, **kwargs):
        """Format Redis channel names (keys of the signal dict) using the given kwargs."""
        return {k.format(**kwargs):v for k,v in signals.items()}
    
    def get_signals_context(self):
        """Provide context for formatting Redis channel names (signal dict's keys).
        
        If you want extra context, override this method and union your context
        with the result of super().get_signals_context().
        """
        return {'user': self.user, **self.kwargs}
    
    def get_oneoff_signals(self) -> Dict[RedisChannelName,
                                         Tuple[Callable[['WSView'], bool],
                                               Callable[['WSView', WSMessage | None], WSResponse]]]:
        """Return the information for one-off signals belonging to this WebSocket view.
        
        If the class-level property 'oneoff_signals' is present, this method
        will format it using the context given by get_signals_context() and
        return it. An example of how 'oneoff_signals' should be:
        
        oneoff_signals = {
            'signal_1':           (check_signal1, render_signal1),
            'signal_2_{context}': (check_signal2, render_signal2),
            ...
        }
        
        The keys of the dictionary are the Redis PubSub channel names
        with format specifiers, and the values are tuples whose elements
        are instance methods defined in the WebSocket view class: the
        first one will check whether the conditions for the signal are
        met, and the second will render a response to be sent to the
        client, indicating the corresponding signal.
        
        Note that the response-rendering methods for one-off signals
        must have their single non-self argument (the pubsub message)
        optional. There would be no message if the signal is ready at
        the time of connection. If no message is provided, but the
        method needs the message data, it has to figure out the required
        data itself (the data must exist according to the definition of
        one-off signals: they are available for each connection even if
        they have happended before the WebSocket connection).
        """
        result = getattr(self, 'oneoff_signals', None)
        return self.format_signals(result, **self.get_signals_context()) if result else []

    def get_realtime_signals(self) -> Dict[RedisChannelName,
                                           Callable[['WSView', WSMessage], WSResponse]]:
        """Return the information for realtime signals belonging to this WebSocket view.
        
        If the class-level property 'realtime_signals' is present, this method
        will format it using the context given by get_signals_context() and
        return it. An example of how 'realtime_signals' should be:
        
        realtime_signals = {
            'signal_1':           render_signal1,
            'signal_2_{context}': render_signal2,
            ...
        }
        
        The keys of the dictionary are the Redis PubSub channel names
        with formta specifiers, and the values are instance methods
        defined in the WebSocket view class which will render a response
        to be sent to the client, indicating the corresponding signal.
        """
        result = getattr(self, 'realtime_signals', None)
        return self.format_signals(result, **self.get_signals_context()) if result else []
    
    async def serve_signals(self, redis_client: redis.asyncio.Redis) -> AsyncGenerator[WSResponse]:
        """Return an async iterator that delivers rendered responses on each signal.

        Args:
            redis_client (redis.asyncio.Redis): The Redis client that provides connection
                with the Redis server.

        Returns:
            AsyncGenerator[WSResponse]: An asynchronous generator that delivers rendered
                responses on each signal.
                
        What this method does, respectively:
        1. Get the list of all signals.
        2. Subscribe to all the corresponding Redis PubSub channels.
        3. Before starting to listen to the channels, for each one-off
           signal, check if it has already happened or not. If so, render
           and send the corresponding response for that signal and
           unsubscribe it from the PubSub (Note that once the PubSub
           is created, the messages will be buffered and kept even if
           we don't listen for them yet).
        4. Start listening to PubSub messages, and yield rendered response
           for each one of them. Ignore the one-off signals that have
           already been delivered to the client.
        
        An example of using this method:
        
        async for response in ws_view.serve_signals(redis_client):
            await send({'type': 'websocket.send', 'text': response})
        """
        async with redis_client.pubsub(ignore_subscribe_messages=True) as pubsub:
            # Leading underline to avoid name clashes with the class-level attrs.
            _realtime_signals = self.get_realtime_signals()
            _oneoff_signals = self.get_oneoff_signals()
            
            # The task will be cancelled if the WebSocket connection is
            # terminated. But we still should let the CM do its cleanups.
            try:
                for signal in _realtime_signals:
                    await pubsub.subscribe(signal)
                
                yielded_oneoffs = []
                for signal in _oneoff_signals:
                    # We must first subscribe to the one-off signal's
                    # channel and then check if it has already happened.
                    # This way we're guaranteed to catch the event. If
                    # subscription happens after the condition checking,
                    # the signal might arrive in between them and get lost.
                    await pubsub.subscribe(signal)
                    
                    check, render = _oneoff_signals[signal]
                    if await check.__get__(self)():
                        yielded_oneoffs.append(signal)
                        await pubsub.unsubscribe(signal)
                        yield await render.__get__(self)()
            
                async for message in pubsub.listen():
                    channel = message['channel'].decode()
                    
                    # Avoid re-sending one-off signals; The messages
                    # that have already arrived won't go away with
                    # unsubscribing.
                    if channel in yielded_oneoffs:
                        continue
                    
                    data = message['data'].decode()
                    if render := _realtime_signals.get(channel, None):  # realtime signal
                        yield await render.__get__(self)(data)
                    else:  # oneoff signal
                        yield await _oneoff_signals[channel][1].__get__(self)(data)
                        await pubsub.unsubscribe(channel)
            except asyncio.CancelledError:
                pass  # let the context manager do its cleanups.
    
    async def process_message(self, message: WSMessage) -> Coroutine[Any, Any, WSResponse | None]:
        """Render response to WebSocket messages from the client.

        Args:
            message (WSMessage): The message sent from the client as a string.

        Returns:
            WSResponse | None: The function can decide to return a string to be
                sent back to the client as a response, or return None for no response.
        
        By default, this method returns None. This is suitable when
        a WebSocket view only uses signal utilities and thus doesn't
        want to define/override 'process_message'.
        """
        return None
