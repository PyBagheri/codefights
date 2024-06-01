class GameExplanation:
    # Each Game class must define this staticmethod so that it can be used
    # upon rendering fight pages to the players. Note that this is not used
    # upon simulation; only for showing results.
    @staticmethod
    def get_explanation_text(explanation):
        return NotImplementedError
