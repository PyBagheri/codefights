import random
from copy import deepcopy

from games._base.game import Game
from games._base.report import VictoryDrawResult

from games.tanks.frontend import TanksExplanation


MAX_GAME_TICKS = 100

# For now, the game board is 10*10.
BOARD_HEIGHT, BOARD_WIDTH = 10, 10

UP, RIGHT, DOWN, LEFT = 'U', 'R', 'D', 'L'

# Decisions
D_MOVE, D_FIRE, D_NOTHING = 'M', 'F', 'N'

# Damages; in percentage per tick
MISSILE_1_DAMAGE = 20  # it hits randomly in a radius around the given target.
MISSILE_2_DAMAGE = 50  # must stay still for this; it's 100% accurate.
CRASH_DAMAGE = 10  # happens when two tanks are in the same square.

MISSILE_RAND_RADIUS = 1  # 1 square around the given dest

DECIDE_FUNC_NAME = 'decide_tick'


# For now, this is only a 2-player game. It should
# be made multiplayer later.
#
# TODO (maybe as a separate game):
# 1) Make multiplayer.
# 2) Add mines; each tank can leave behind a certain
#    number of mines throughout the game.
# 3) Add speed boost; each tank can boost itself to
#    go faster for a certain amount of ticks, for a
#    certain number of times throughout the game. but
#    after the boost, it cannot move (just an idea).
class Tanks(Game):  
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        assert self.player_count == 2  # for now
    
    def get_limits(self):
        return {
            'cpu_sec': 1,
            'cpu_nsec': 0,
            'mem_bytes': 70_000_000  # 70MB
        }
    
    # This function is game-specific; not part of the
    # general interface of game classes. Even though
    # later we might factor a similar funtionality into
    # a parent class for all games.
    def get_decision(self, i, f, args):
        res = self.cr_controllers[i].run_command(f_name=f, f_args=list(args))
        if res is None:  # player eliminated
            self.players_alive.remove(i)
            return None
        
        if res == (None,) or res == -1:  # -1 for errored
            return D_NOTHING
        else:
            return res[0]
    
    @staticmethod
    def randomize_dest(dest):
        choices = []
        for dx in range(-MISSILE_RAND_RADIUS, MISSILE_RAND_RADIUS+1):
            for dy in range(-MISSILE_RAND_RADIUS, MISSILE_RAND_RADIUS+1):
                x = dest[0]+dx
                y = dest[1]+dy
                
                if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                    choices.append([x, y])
        
        return random.choice(choices)
        
    # Returns True to indicate that a win or a draw has happened,
    # False otherwise.
    def check_win_or_draw(self):
        p1_died = False
        p2_died = False


        if self.players_states[self.players_alive[0]]['health'] <= 0:
            p1_died = True
        if self.players_states[self.players_alive[1]]['health'] <= 0:
            p2_died = True
        
        
        if p1_died and p2_died:
            self.result = VictoryDrawResult.DRAW
            return True
        elif p1_died:
            self.result = VictoryDrawResult.get_win_lose_list(
                self.player_count,
                self.players_alive[1]
            )
            return True
        elif p2_died:
            self.result = VictoryDrawResult.get_win_lose_list(
                self.player_count,
                self.players_alive[0]
            )
            return True
        
        return False
        
        
    # MUST be performed before applying the decisions.
    def apply_damages(self):
        # Missile damage
        for pi, value in self.missiles.items():
            if value is None:
                continue
            
            
            dest, rdest = value
            
            # 'rdest' is the randomized destination. When we have
            # no randomization, then 'rdest' is None.
            if rdest:
                dest = rdest
            
            # It can also affect the player that fired the missile.
            for tank_pi in self.board[dest[0]][dest[1]]:
                if self.players_states[pi]['moved']:
                    self.players_states[tank_pi]['health'] -= MISSILE_1_DAMAGE
                else:
                    self.players_states[tank_pi]['health'] -= MISSILE_2_DAMAGE
        
            self.missiles[pi] = None


        
        
        # Crash damage
        for pi in self.players_alive:
            x = self.players_states[pi]['x']
            y = self.players_states[pi]['y']
            
            # If there are other tanks in the same square too, apply damage.
            if len(self.board[x][y]) > 1:
                self.players_states[pi]['health'] -= CRASH_DAMAGE

    
    # We can have at most two decisions for a tick (move and/or fire).
    #
    # This function should also take care of validations. One thing to
    # note is that all the responses are received as JSON, and thus we
    # know that what we get is JSON-serializable.
    def apply_decisions(self, i, decisions):
        if decisions == D_NOTHING:
            return
        elif not isinstance(decisions, list) or not decisions:
            return
        
        # If we have only one decision, then turn
        # it put it in an list for simpler code.
        if not isinstance(decisions[0], list):
            decisions = [decisions]
        
        for d in decisions:
            # D_FIRE and D_MOVE with their single argument
            if len(d) != 2:
                return
            
            if d[0] == D_FIRE:
                destination = d[1]
                if not isinstance(destination, list) or  \
                   not len(destination) == 2 or  \
                   not all([isinstance(n, int) for n in destination]):
                       return
                
                self.missiles[i] = [destination, None]
                
            
            elif d[0] == D_MOVE:
                direction = d[1]
                if direction not in (UP, RIGHT, DOWN, LEFT):
                    return
                
                prev_x = x = self.players_states[i]['x']
                prev_y = y = self.players_states[i]['y']

                # The velocity is "per tick".
                if direction == UP:
                    y += 1
                elif direction == RIGHT:
                    x += 1
                elif direction == DOWN:
                    y -= 1
                else:  # LEFT
                    x -= 1

                # If the requested movement is out of the board,
                # simply ignore it.
                if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                    self.players_states[i]['x'] = x
                    self.players_states[i]['y'] = y
                    
                    self.board[prev_x][prev_y].remove(i)
                    self.board[x][y].append(i)
                    
                    self.players_states[i]['head'] = direction
                    self.players_states[i]['moved'] = True
        
        # If attempted to fire a missile while also having a move
        # command, then randomize the missile destination to within
        # a certain radius around the given destination.
        if self.players_states[i]['moved'] and self.missiles[i]:
            self.missiles[i][1] = self.randomize_dest(self.missiles[i][0])
            
        self.players_states[i]['targeted'] = self.missiles[i]

    
    def simulate(self):
        tick = 0
        self.flow = []
        self.explanation = ''
        
        
        # 'board' shows the list of tanks in each square in the game board.
        self.board = [[[] for _ in range(BOARD_HEIGHT)] for _ in range(BOARD_WIDTH)]
        
        # Active missiles for each player. Each value is a tuple, whose
        # first item is the given target by the player, and the second
        # item is None, unless the player has fired a missile while moving,
        # which means that the target will be randomized in a radius around
        # the given target and the result will be put as the second item.
        self.missiles = {pi: None for pi in self.players_alive}
        
        # 'targeted' and 'moved' can have different meanings
        # depending on how we want to use them and when. For
        # the players:
        # 'targeted' shows the coordinates of the square
        # that was attacked at the current tick (i.e., it
        # was fired in the previous tick, as each missile
        # takes one tick to arrive at the target) as well
        # as the coordinate that was intended by the opponent
        # if the target coords was randomized (due to moving
        # while firing). This is basically a value from the
        # self.missiles dict. If no missile was fired, then
        # this would be None.
        #
        # 'moved' determines whether the player has made a
        # move in the previous tick.
        #
        # For when we use the flow (in the front-end), 'targeted'
        # and 'moved' refer to the decisions made in the current
        # tick, which will be affecting the next tick's state.
        # The decision to add the states to the flow at the end
        # of the tick just makes the job at the front-end simpler.
        self.players_states = [
            # Player 1
            {'x': 0,
             'y': 0,
             'health': 100,
             'head': RIGHT,
             'moved': False,
             'targeted': None},
            
            # Player 2
            {'x': BOARD_WIDTH-1,
             'y': BOARD_HEIGHT-1,
             'health': 100,
             'head': LEFT,
             'moved': False,
             'targeted': None}
        ]
        
        # The initial states.
        self.flow.append(deepcopy([list(i.values()) for i in self.players_states]))
        
        
        if not self.players_alive:
            self.result = VictoryDrawResult.DRAW
            return
        
        if len(self.players_alive) == 1:
            self.result = VictoryDrawResult.get_win_lose_list(
                self.player_count,
                self.players_alive[0]
            )
            return
        
        
        self.board[0][0].append(self.players_alive[0])
        self.board[BOARD_WIDTH-1][BOARD_HEIGHT-1].append(
            self.players_alive[1]
        )

        
        while tick < MAX_GAME_TICKS:
            # Apply damages from the actions of the previous tick.
            self.apply_damages()
            
            if self.check_win_or_draw():
                break

            # TODO: the decisions must be validated in the get_decision().

            decision1 = self.get_decision(
                self.players_alive[0],
                DECIDE_FUNC_NAME,
                (tick, self.players_states[0], self.players_states[1])
            )
            
            decision2 = self.get_decision(
                self.players_alive[1],
                DECIDE_FUNC_NAME,
                (tick, self.players_states[1], self.players_states[0])
            )
            
            if decision1 is None and decision2 is None:
                self.result = VictoryDrawResult.DRAW
                return
            elif decision1 is None:  # player 1 eliminated
                self.result = VictoryDrawResult.get_win_lose_list(
                    self.player_count,
                    self.players_alive[1]
                )
                return
            elif decision2 is None:  # player 2 eliminated
                self.result = VictoryDrawResult.get_win_lose_list(
                    self.player_count,
                    self.players_alive[0]
                )
                return
            
            # Reset the one-off values.
            for pi in self.players_alive:
                self.players_states[pi]['moved'] = False
                self.players_states[pi]['targeted'] = None
                               
            self.apply_decisions(self.players_alive[0], decision1)
            self.apply_decisions(self.players_alive[1], decision2)
                        
            if self.check_win_or_draw():
                break

            self.flow.append(deepcopy([list(i.values()) for i in self.players_states]))
            
            tick += 1
        else:  # the max tick count has been reached.
            self.result = VictoryDrawResult.DRAW
            self.explanation = TanksExplanation.X_TICK_LIMIT
            return

        # Reset the one-off values.
        for pi in self.players_alive:
            self.players_states[pi]['moved'] = False
            self.players_states[pi]['targeted'] = None
        
        # The final states.
        self.flow.append(deepcopy([list(i.values()) for i in self.players_states]))
        

    def get_report(self):
        return self.result, self.explanation, self.flow
