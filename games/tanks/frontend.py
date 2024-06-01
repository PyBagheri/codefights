from games._base.frontend import GameExplanation
import json


class TanksExplanation(GameExplanation):
    X_TICK_LIMIT = 'X'
    
    @staticmethod
    def get_explanation_text(explanation):
        if explanation and json.loads(explanation) == TanksExplanation.X_TICK_LIMIT:
            return 'Tick limit was exceeded.'
