# This module provides some primitive coderunner facilities as
# some sort of an interface to the actual simulator for testing
# purposes, so that wecan test the games independently of the
# simulator.

import json


def take_through_json(data):
    return json.loads(json.dumps(data))


# Note that the only reason we're using excpetion handling here
# is to make sure that the game can act properly when a player's
# code causes problems (which is part of the testing). It's not
# meant to check if stuff like illegal actions, ... are actually
# handled or not (that is a test of the simulator, not the game
# classes).
class CRController:
    def __init__(self, code, game_settings, limits):
        # Any exception here corresponds to the player
        # getting eliminated.
        try:
            ls = {}
            exec(code, ls, ls)
            
            main_class = ls.get('Main')
            self.main_instance = main_class()
            
            setattr(self.main_instance, 'context', game_settings)
            
            self.is_alive = True
        except Exception:
            self.is_alive = False
        
    
    def run_command(self, f_name, f_args):
        resolved_names = {}
        
        if f_name in resolved_names:
            f = resolved_names[f_name]
        else:
            f = getattr(self.main_instance, f_name, None)
            
            if f is None:
                self.is_alive = False  # just in case
                return None  # player eliminated
                
            resolved_names[f_name] = f
        
        try:
            return (take_through_json(f(*f_args)),)  # value in tuple
        except Exception:
            return -1  # exception occured; player can still continue

