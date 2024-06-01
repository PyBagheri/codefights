import json
from pathlib import Path

from games._tests.coderunner import CRController
from games import GAME_CLASSES


GAMES_ROOT = Path(__file__).parent.parent


def run_game_and_report(game_class, game_settings, codes):
    game_instance = game_class(game_settings, len(codes))
    
    cr_controllers = []
    for code in codes:
        crc = CRController(code, game_settings, game_instance.get_limits())
        cr_controllers.append(crc)
        
    initial_players = []
    for i in range(game_settings['player_count']):
        if cr_controllers[i].is_alive:
            initial_players.append(i)
    
    game_instance.set_controllers(cr_controllers, initial_players)
    
    game_instance.simulate()
    
    return game_instance.get_report()


def get_game_test_codes(game_name, codes_files):
    codes_dir = GAMES_ROOT / game_name / 'tests/codes'
    codes = []
    
    for filename in codes_files:
        with open(codes_dir / filename, 'r') as f:
            codes.append(f.read())
    
    return codes


def get_game_test_report(game_name, filename):
    reports_dir = GAMES_ROOT / game_name / 'tests/reports'
    
    with open(reports_dir / filename, 'r') as f:
        return f.read()
    

# A parent for game tests that provides tools for testing
# a game's report with what's expected.
class GameReportTest:
    def run_and_test_game_report(self,
                                 game_name,
                                 game_settings,
                                 codes_files,
                                 expected_report_file):
        player_codes = get_game_test_codes(game_name, codes_files)
        expected_report = get_game_test_report(game_name, expected_report_file)
        
        # We compare the JSON's rather than using assertSequenceEqual
        # because it takes away the distinction between lists and tuples
        # by converting every array-like object to a JSON list.
        self.assertEqual(
            json.dumps(
                run_game_and_report(GAME_CLASSES[game_name],
                                    game_settings,
                                    player_codes)
            ),
            
            # We do this to make sure both JSON's are consistent in
            # whitespaces and separators.
            json.dumps(json.loads(expected_report))
        )

