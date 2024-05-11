import unittest

from games.testing.base import GameReportTest


class TanksTest(GameReportTest, unittest.TestCase):
    def test_draw_both_lost(self):
        game_settings = {"player_count": 2}
        codes = ('move_to_x0y9.py', 'move_to_x0y9.py')
        expected_report = [['D', 'L'], [[[0, 0, 100, 'R', False, None], [9, 9, 100, 'L', False, None]], [[0, 1, 100, 'U', True, None], [8, 9, 100, 'L', True, None]], [[0, 2, 100, 'U', True, None], [7, 9, 100, 'L', True, None]], [[0, 3, 100, 'U', True, None], [6, 9, 100, 'L', True, None]], [[0, 4, 100, 'U', True, None], [5, 9, 100, 'L', True, None]], [[0, 5, 100, 'U', True, None], [4, 9, 100, 'L', True, None]], [[0, 6, 100, 'U', True, None], [3, 9, 100, 'L', True, None]], [[0, 7, 100, 'U', True, None], [2, 9, 100, 'L', True, None]], [[0, 8, 100, 'U', True, None], [1, 9, 100, 'L', True, None]], [[0, 9, 100, 'U', True, None], [0, 9, 100, 'L', True, None]], [[0, 9, 90, 'U', False, None], [0, 9, 90, 'L', False, None]], [[0, 9, 80, 'U', False, None], [0, 9, 80, 'L', False, None]], [[0, 9, 70, 'U', False, None], [0, 9, 70, 'L', False, None]], [[0, 9, 60, 'U', False, None], [0, 9, 60, 'L', False, None]], [[0, 9, 50, 'U', False, None], [0, 9, 50, 'L', False, None]], [[0, 9, 40, 'U', False, None], [0, 9, 40, 'L', False, None]], [[0, 9, 30, 'U', False, None], [0, 9, 30, 'L', False, None]], [[0, 9, 20, 'U', False, None], [0, 9, 20, 'L', False, None]], [[0, 9, 10, 'U', False, None], [0, 9, 10, 'L', False, None]], [[0, 9, 0, 'U', False, None], [0, 9, 0, 'L', False, None]]]]
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)

    def test_draw_tick_limit_exceed(self):
        game_settings = {"player_count": 2}
        codes = ('move_to_x0y9.py', 'move_to_x9y9.py')
        expected_report = [['D', 'X'], [[[0, 0, 100, 'R', False, None], [9, 9, 100, 'L', False, None]], [[0, 1, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 2, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 3, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 4, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 5, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 6, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 7, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 8, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', True, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]], [[0, 9, 100, 'U', False, None], [9, 9, 100, 'L', False, None]]]]
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)
    
    def test_win_by_missile(self):
        game_settings = {"player_count": 2}
        codes = ('fire_enemy_no_move.py', 'do_nothing.py')
        expected_report = [['W', 0], [[[0, 0, 100, 'R', False, None], [9, 9, 100, 'L', False, None]], [[0, 0, 100, 'R', False, [[9, 9], None]], [9, 9, 100, 'L', False, None]], [[0, 0, 100, 'R', False, [[9, 9], None]], [9, 9, 50, 'L', False, None]], [[0, 0, 100, 'R', False, None], [9, 9, 0, 'L', False, None]]]]
        
        self.run_and_test_game_report('tanks', game_settings, codes, expected_report)
