from utils.settings import overrides


###################### Override the settings here #######################
GAMES_INDEX_MODULE = 'simulator.tests.assets.games.index'
#########################################################################


overrides(this=__name__, target='simulator.settings')
