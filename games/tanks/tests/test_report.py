import unittest

from games._tests import GameReportTest


class TanksTest(GameReportTest, unittest.TestCase):
    def test_draw_both_lost(self):
        game_settings = {"player_count": 2}
        codes = ('move_to_x0y9.py', 'move_to_x0y9.py')
        expected_report = 'draw_both_lost.json'
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)

    def test_draw_tick_limit_exceed(self):
        game_settings = {"player_count": 2}
        codes = ('move_to_x0y9.py', 'move_to_x9y9.py')
        expected_report = 'draw_tick_limit_exceed.json'
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)
    
    def test_win_by_missile(self):
        game_settings = {"player_count": 2}
        codes = ('fire_enemy_no_move.py', 'do_nothing.py')
        expected_report = 'win_by_missile.json'
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)
