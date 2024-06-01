# A parent for all game classes.
class Game:
    def __init__(self, game_settings, player_count):
        self.game_settings = game_settings
        self.player_count = player_count
        
    def set_controllers(self, cr_controllers, initial_players):
        self.cr_controllers = cr_controllers
        self.players_alive = initial_players
    
    def simulate(self):
        return NotImplementedError
    
    # Report conventions:
    #
    # A game report must be an iterable of length 3 or 4, depending on
    # whether the game has scores or not. These items must be valid JSON
    # array element. The items are, respectively:
    # 1) the "result": shows the result of the game. This will NOT be
    #    directly saved into the database; instead, depending on the
    #    conclusion system of the game and whether or not it has scores,
    #    we populate the specified fields with the values provided by
    #    the "result".
    # 2) [OPTIONAL] the "scores": if the game has scores, then this must
    #    be the second element in the report. It's an array of integers
    #    where the integer at each index is the score of the player of that
    #    index. It will be saved as an array into the database.
    # 3) the "explanation": extra information about the result. It can be
    #    any valid JSON array element. The way this value is interpreted
    #    depends on each game's get_explanation_text() method on their
    #    GameExplanation frontend. It will be dumped as JSON and then saved
    #    to the database, regardless of its type. If there is no explanation,
    #    this must be an empty string.
    # 4) the "data": a detailed explanation of how the simulation has
    #    gone, step by step. This will be used to represent the fight
    #    and its steps and decisions. Again, interpretation of this
    #    information depends on the game and its different parts (e.g.,
    #    the frontend interface of the game). It will be dumped as JSON
    #    and then saved to the database, regardless of its type.
    #
    #
    # Construction of "result":
    # Currently, we have only two conclusion systems: victory-draw and
    # rank-based. For each one we have:
    #
    #   - victory-draw: "result" will be either be the constant given by
    #     games._base.report.VictorDrawResult.DRAW, or an array that indicates,
    #     for each index, whether the corresponding player has won or not.
    #     The items are either VictorDrawResult.WINNER or VictorDrawResult.LOSER.
    #
    #   - rank-based: "result" will be an array of ranks (integers), where
    #     each element indicates the rank of the corresponding player of that
    #     index.
    def get_report(self):
        return NotImplementedError

