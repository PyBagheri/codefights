# A parent for all game classes.
class Game:
    def __init__(self, game_settings):
        self.game_settings = game_settings
        self.player_count = game_settings['player_count']
        
    def set_controllers(self, cr_controllers, initial_players):
        self.cr_controllers = cr_controllers
        self.players_alive = initial_players