import sys
import importlib


def overrides(*, this, target):
    this_module = sys.modules[this]
    target_module = importlib.import_module(target)
            
    def module_getattr(key):
        if key in this_module.__dict__:
            return getattr(this_module, key)
        
        if hasattr(target_module, key):
            return getattr(target_module, key)
        
        raise AttributeError

    def module_dir():
        dir1set = {n for n in dir(target_module) if n.isupper()}
        dir2set = {n for n in this_module.__dict__ if n.isupper()}
        return list(dir1set.union(dir2set))
    
    # See https://stackoverflow.com/questions/2447353/getattr-on-a-module
    setattr(this_module, '__getattr__', module_getattr)
    setattr(this_module, '__dir__', module_dir)
