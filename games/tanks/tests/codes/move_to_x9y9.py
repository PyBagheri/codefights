MAX_GAME_TICKS = 100

BOARD_WIDTH, BOARD_HEIGHT = 10, 10

UP, RIGHT, DOWN, LEFT = 'U', 'R', 'D', 'L'

# Decisions
D_MOVE, D_FIRE, D_NOTHING = 'M', 'F', 'N'

# Damages; in percentage per tick
MISSILE_1_DAMAGE = 20
MISSILE_2_DAMAGE = 50
CRASH_DAMAGE = 10

# The radius (in squares) around the target that
# a random square will be chosen from. This is
# only for when the missile has been fired while
# also make a move command.
MISSILE_RAND_RADIUS = 1


class Main:
    def __init__(self) -> None:
        self.tt = 0
    
    def go_toward(self, state, x, y):
        # first fix x and then y.
        if state['x'] > x:
            return LEFT
        elif state['x'] < x:
            return RIGHT
        
        # x is fixed; now y.
        if state['y'] > y:
            return DOWN
        elif state['y'] < y:
            return UP
        
        return None
    
    def decide_tick(self, tick, my_state, enemy_state):
        move = self.go_toward(my_state, 9, 9)
        
        if move:
            return [D_MOVE, move]
