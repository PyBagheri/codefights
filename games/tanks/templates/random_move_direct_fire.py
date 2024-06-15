import random

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
# also making a move command.
MISSILE_RAND_RADIUS = 1


class Main:
    def decide_tick(self, tick, my_state, enemy_state):
        enemy_loc = enemy_state['x'], enemy_state['y']
        
        move = random.choice([UP, RIGHT, DOWN, LEFT])
        
        return [D_MOVE, move], [D_FIRE, enemy_loc]
