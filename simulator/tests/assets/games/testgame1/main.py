from games._base.game import Game

# a 1-player test game
class TestGame1(Game):
    def get_limits(self):
        return {
            'cpu_sec': 5,
            'cpu_nsec': 0,
            'mem_bytes': 70_000_000
        }
    
    def simulate(self):
        if not self.players_alive:
            self.report = -1  # just to test
            
        cr1 = self.cr_controllers[0]
        
        # We send test arguments through game settings.
        res = cr1.run_command(
            f_name='testfunc1',
            f_args=self.game_settings['test_args']
        )
        
        self.report = res
    
    def get_report(self):
        return self.report
    