var game_body, board, info, control;
var settings, result, flow;
var game_ticks, current_tick;
var current_timeouts = [];

var paused = false;

var health_texts = [], current_tick_text;
var pp_button_icon;

setTrackedTimeout = function (...args) {
    if (paused) return;

    current_timeouts.push(setTimeout(...args));
}


// Indices by names
const I = {'x': 0, 'y': 1, 'health': 2, 'head': 3, 'moved': 4, 'targeted': 5}


// Later change these to be a part of the game settings
// rather than hardcoded values.
const BOARD_WIDTH = 10;
const BOARD_HEIGHT = 10;

const MOVE_ROTATOINS = {
    "U": "0deg",
    "R": "90deg",
    "D": "180deg",
    "L": "-90deg",
};

const MAX_GAME_TICKS = 100;

const RESULT_DRAW_MAX_TICK = "X";
const RESULT_DRAW_BOTH_LOST = "L";
const RESULT_WIN = "W";

const UP = "U";
const RIGHT = "R";
const DOWN = "D";
const LEFT = "L";

// Decisions
const D_MOVE = "M";
const D_FIRE = "F";
const D_NOTHING = "N";

const MISSILE_RAND_RADIUS = 1;

const INITIAL_DELAY = 1000;  // 1s

const MOVE_DURATION = 1000;
const TURN_DURATION = 200;
const TURN_DELAY = 100;  // necessary for some unknown reason :/

// Keep; might be useful later.
const NEXT_TICK_DELAY = 0;

const TIME_BETWEEN_TICKS = TURN_DURATION +
    TURN_DELAY +
    MOVE_DURATION +
    NEXT_TICK_DELAY;

// head-direction matrix.
const HD_MATRIX = {
    "U": { "U": 0, "R": 90, "D": 180, "L": -90 },
    "R": { "U": -90, "R": 0, "D": 90, "L": 180 },
    "D": { "U": -180, "R": -90, "D": 0, "L": 90 },
    "L": { "U": 90, "R": -180, "D": -90, "L": 0 },
}

const TANK_COLORS = ["#bf3b3b", "darkblue"];

const PREHIT_BG_COLORS = ["pink", "lightblue"];
const OVERLAPPING_PREHIT_BG_COLORS = "#e3a0e3";

const HIT_BG_COLORS = ["red", "blue"];
const OVERLAPPING_HIT_BG_COLORS = "purple";

const CRASH_BOX_SHADOW = "0 0 10px 5px red";

const MISSILE_SHOW_DELAY = 200;
const HIT_COLOR_DURATION = 200;

const INDICATION_COLOR_DURATION = TIME_BETWEEN_TICKS -
    NEXT_TICK_DELAY -
    HIT_COLOR_DURATION -
    MISSILE_SHOW_DELAY;

const HEALTH_ZOOM_DURATION = 250;

var square_inner_size;


function update_square_size() {
    // -1 for the border of 1px;
    square_inner_size = board.childNodes[0].childNodes[0]
        .getBoundingClientRect().height - 1;
}


function control_prev() {
    // we do this rather then return, so that one can
    // get the game to its very beginning while tick 0
    // is still playing.
    if (current_tick != 0) {
        current_tick -= 1;
    }

    if (paused) {
        reset_board(false);
        run_simulation(current_tick, false, false);
        preview_tick(current_tick);
    } else {
        reset_board(false);
        run_simulation(current_tick, false, true);
    }
}


function control_next() {
    if (current_tick === game_ticks-1) return;

    current_tick += 1;

    if (paused) {
        reset_board(false);
        run_simulation(current_tick, false, false);
        preview_tick(current_tick);
    } else {
        reset_board(false);
        run_simulation(current_tick, false, true);
    }
}


function control_next10() {
    // tired of coding at this point ...
    for (let i = 0; i < 10; i++) {
        control_next();
    }
}


function control_prev10() {
    for (let i = 0; i < 10; i++) {
        control_prev();
    }
}


function control_zero() {
    if (paused) {
        reset_board(false);
        run_simulation(0, false, false);
        preview_tick(0);
    } else {
        reset_board(false);
        run_simulation(0, false, true);
    }
}


function control_pauseplay() {
    if (paused) {
        paused = false;

        pp_button_icon.setAttribute("name", "md-pause");

        reset_board(false);
        run_simulation(current_tick, false, true);
    } else {
        paused = true;

        pp_button_icon.setAttribute("name", "md-play");

        reset_board(false);
        run_simulation(current_tick, false, false);

        preview_tick(current_tick);
    }
}


function setup_board() {
    let board_square = document.createElement("div");
    board_square.classList.add("board-square");

    for (let i = 0; i < BOARD_WIDTH; i++) {
        let board_column = document.createElement("div");
        board_column.classList.add("board-column");

        board.appendChild(board_column);

        for (let j = 0; j < BOARD_HEIGHT; j++) {
            board_column.appendChild(board_square.cloneNode());
        }
    }

    new ResizeObserver(update_square_size).observe(board.childNodes[0].childNodes[0]);
}


// The interface for the website's machinery.
function setup(_settings, _result, _flow) {
    settings = _settings;
    result = _result;
    flow = _flow;

    // The first item is the initial conditions (not a tick),
    // and the last item is the final conditions, but it actually
    // represents the last tick (which didn't make it to getting
    // decisions from the players).
    game_ticks = flow.length - 1;

    game_body = document.getElementById("game-body");

    board = game_body.querySelector(".board");
    info = game_body.querySelector(".info");
    control = game_body.querySelector(".control");

    control.querySelector(".prev").addEventListener('click', control_prev);
    control.querySelector(".next").addEventListener('click', control_next);

    control.querySelector(".prev10").addEventListener('click', control_prev10);
    control.querySelector(".next10").addEventListener('click', control_next10);

    let pp_button = control.querySelector(".pause-play");
    pp_button_icon = pp_button.querySelector("ion-icon");
    pp_button.addEventListener('click', control_pauseplay);

    control.querySelector(".zero").addEventListener('click', control_zero);

    // -1 because the ticks start from 0.
    control.querySelector(".tick-count").innerText = game_ticks - 1;

    current_tick_text = control.querySelector(".current-tick");

    info.querySelectorAll(".health").forEach((health, i) => {
        health.style.color = TANK_COLORS[i];
        health_texts.push(health);
    });

    setup_board();
}


function reset_board(reset_pause=true) {
    current_timeouts.forEach(timeout => {
        clearTimeout(timeout);
    });

    current_timeouts = [];

    let new_board = document.createElement("div");
    new_board.classList.add("board");

    board.replaceWith(new_board);
    board = new_board;
    setup_board();

    health_texts.forEach(s => {
        s.innerText = "";
    });

    current_tick_text.innerText = "";

    if (reset_pause) {
        paused = false;
    }
}


function get_tank_rotation(current_rotation, head, direction) {
    if (current_rotation === "") {
        current_rotation = 0;
    } else {
        // remove 'deg'
        current_rotation = Number(
            current_rotation.substring(0, current_rotation.length - 3)
        );
    }

    let diff = HD_MATRIX[head][direction];
    current_rotation += diff;

    // second item is whether or not rotation has changed.
    return [current_rotation + "deg", (diff != 0)];
}


function promiseTrackedTimeout(f, timeout, ...args) {
    return new Promise(function(success, failure) {
        setTrackedTimeout(function(...args) {
            f(...args);

            success();
        }, timeout, ...args);
    });
}


// not affected by pause or reset
function promiseUntrackedTimeout(f, timeout, ...args) {
    return new Promise(function(success, failure) {
        setTimeout(function(...args) {
            f(...args);

            success();
        }, timeout, ...args);
    });
}


function do_missile_animation(missile, pi) {
    let promises = [];

    // Note: When there is an overlap, it means that the square
    // was colored when we were applying the previous player's 
    // states. We only let one of these do the color reset, e.g.,
    // when applying the first player's states, but not in the
    // second.

    if (missile[1] != null) {
        for (let i = -MISSILE_RAND_RADIUS; i <= MISSILE_RAND_RADIUS; i++) {
            for (let j = -MISSILE_RAND_RADIUS; j <= MISSILE_RAND_RADIUS; j++) {
                let x = missile[0][0] + i;
                let y = missile[0][1] + j;

                if (0 <= x && x < BOARD_WIDTH && 0 <= y && y < BOARD_HEIGHT) {
                    let potential_square = board.childNodes[x].childNodes[y];

                    let overlaps = (potential_square.style.backgroundColor != "");
                    if (overlaps === false) {
                        potential_square.style.backgroundColor = PREHIT_BG_COLORS[pi];
                    } else {
                        potential_square.style.backgroundColor = OVERLAPPING_PREHIT_BG_COLORS;
                    }

                    if (x === missile[1][0] && y === missile[1][1]) {
                        promises.push(promiseTrackedTimeout(function (potential_square, overlaps) {
                            if (overlaps === false) {
                                potential_square.style.backgroundColor = HIT_BG_COLORS[pi];

                                promises.push(promiseTrackedTimeout(function () {
                                    potential_square.style.backgroundColor = "";
                                }, HIT_COLOR_DURATION));

                            } else {
                                potential_square.style.backgroundColor = OVERLAPPING_HIT_BG_COLORS;
                            }
                        }, INDICATION_COLOR_DURATION, potential_square, overlaps));
                    } else if (overlaps === false) {
                        promises.push(promiseTrackedTimeout(function (potential_square) {
                            potential_square.style.backgroundColor = "";
                        }, INDICATION_COLOR_DURATION, potential_square));
                    }
                }
            }
        }
    } else {
        let attacked_square = board.childNodes[missile[0][0]].childNodes[missile[0][1]];

        let overlaps = (attacked_square.style.backgroundColor != "");
        if (overlaps === false) {
            attacked_square.style.backgroundColor = PREHIT_BG_COLORS[pi];
        } else {
            attacked_square.style.backgroundColor = OVERLAPPING_PREHIT_BG_COLORS
        }

        promises.push(promiseTrackedTimeout(function (attacked_square, overlaps) {
            if (overlaps === false) {
                attacked_square.style.backgroundColor = HIT_BG_COLORS[pi];

                promises.push(promiseTrackedTimeout(function () {
                    attacked_square.style.backgroundColor = "";
                }, HIT_COLOR_DURATION));
            } else {
                attacked_square.style.backgroundColor = OVERLAPPING_HIT_BG_COLORS;
            }
        }, INDICATION_COLOR_DURATION, attacked_square, overlaps));
    }

    return Promise.all(promises);
}


function do_crash_animation(x, y) {
    let square = board.childNodes[x].childNodes[y];

    square.style.boxShadow = CRASH_BOX_SHADOW;

    return promiseTrackedTimeout(function (square) {
        square.style.boxShadow = "";
    }, INDICATION_COLOR_DURATION, square);
}



function do_health_animation(i) {
    let health = health_texts[i];

    health.style.transform = "scale(3)";

    return promiseUntrackedTimeout(function (health) {
        health.style.transform = "";
    }, HEALTH_ZOOM_DURATION, health);
}


function preview_tick(tick) {
    let tick_states = flow[tick+1];

    for (let pi = 0; pi < tick_states.length; pi++) {
        let player_next_state = tick_states[pi];
        let missile = player_next_state[I['targeted']];

        // TODO: maybe later add preview animation for crash too.

        if (missile) {
            if (missile[1] != null) {
                for (let i = -MISSILE_RAND_RADIUS; i <= MISSILE_RAND_RADIUS; i++) {
                    for (let j = -MISSILE_RAND_RADIUS; j <= MISSILE_RAND_RADIUS; j++) {
                        let x = missile[0][0] + i;
                        let y = missile[0][1] + j;

                        if (0 <= x && x < BOARD_WIDTH && 0 <= y && y < BOARD_HEIGHT) {
                            let potential_square = board.childNodes[x].childNodes[y];

                            if (x === missile[1][0] && y === missile[1][1]) continue;
                            if (potential_square.attributes["data-striked"]) continue;

                            let overlaps = (potential_square.style.backgroundColor != "");
                            if (overlaps === false) {
                                potential_square.style.backgroundColor = PREHIT_BG_COLORS[pi];
                            } else {
                                potential_square.style.backgroundColor = OVERLAPPING_PREHIT_BG_COLORS;
                            }
                        }
                    }
                }

                let striked_square = board.childNodes[missile[1][0]].childNodes[missile[1][1]];

                if (!striked_square.attributes["data-striked"]) {
                    striked_square.style.backgroundColor = HIT_BG_COLORS[pi];
                    striked_square.attributes["data-striked"] = "yes";
                } else {
                    striked_square.style.backgroundColor = OVERLAPPING_HIT_BG_COLORS;
                }
            } else {
                let attacked_square = board.childNodes[missile[0][0]].childNodes[missile[0][1]];

                let overlaps = (attacked_square.style.backgroundColor != "");

                if (overlaps === false) {
                    attacked_square.style.backgroundColor = HIT_BG_COLORS[pi];
                } else {
                    attacked_square.style.backgroundColor = OVERLAPPING_HIT_BG_COLORS;
                }
            }
        }
    }
}


var states;  // current states
var player_tanks = [];
var player_tanks_bodies = [];

function start_from_tick(i) {
    // Honsetly the only thing that the last tick does is
    // update the health texts; that's why we allow it to be.
    // Note that the last tick is not useless, as it contains
    // the healthes (which might be negative, but usefulness
    // of it is more in easing the indexing).
    if (i === game_ticks+1) return;

    new Promise(function (success, failure) {
        if (i === game_ticks) {
            current_tick_text.innerText = String(i-1);
            current_tick = i-1;

            success();  // let the promise die (note the "if" above).
            return;
        }

        let promises = [];

        let next_states = flow[i];

        current_tick_text.innerText = String(i - 1);
        current_tick = i-1;

        if (next_states[0][I['x']] === next_states[1][I['x']] &&
            next_states[0][I['y']] === next_states[1][I['y']]) {
            promises.push(promiseTrackedTimeout(function() {
                promises.push(do_crash_animation(next_states[0][I['x']],
                                                 next_states[0][I['y']]));
            }, TIME_BETWEEN_TICKS-NEXT_TICK_DELAY));
        }

        for (let pi = 0; pi < next_states.length; pi++) {
            let player_next_state = next_states[pi];

            // The missiles that were fired in the current tick
            // will have animations in both the current and the
            // next tick.
            if (player_next_state[I['targeted']] != null) {
                promises.push(promiseTrackedTimeout(function() {
                    promises.push(do_missile_animation(player_next_state[I['targeted']], pi));
                }, MISSILE_SHOW_DELAY));
            }


            // There is no tick after the last tick; so no health update.
            if (health_texts[pi].innerText != String(flow[i+1][pi][I['health']])) {
                promises.push(promiseTrackedTimeout(function() {
                    health_texts[pi].innerText = String(flow[i+1][pi][I['health']]);

                    // Waiting for the health animation makes it so that when
                    // there is a damage, there is an extra delay. It was not
                    // intended initially, but I think it's cool. Plus, it
                    // prevents setTimeout()s from messing up.
                    promises.push(do_health_animation(pi));
                }, TIME_BETWEEN_TICKS-NEXT_TICK_DELAY));
            }


            if (player_next_state[I['moved']] === true) {
                let direction = player_next_state[I['head']];

                let source_square = board.childNodes[states[pi][I['x']]]
                                         .childNodes[states[pi][I['y']]];

                let dest_square = board.childNodes[player_next_state[I['x']]]
                                       .childNodes[player_next_state[I['y']]];

                let transform;
                if (direction === UP) {
                    transform = "translateY(-" + square_inner_size + "px)";
                } else if (direction === RIGHT) {
                    transform = "translateX(" + square_inner_size + "px)";
                } else if (direction === DOWN) {
                    transform = "translateY(" + square_inner_size + "px)";
                } else if (direction === LEFT) {
                    transform = "translateX(-" + square_inner_size + "px)";
                }

                let r = get_tank_rotation(player_tanks_bodies[pi].style.rotate,
                                          states[pi][I['head']],
                                          direction);

                promises.push(promiseTrackedTimeout(function () {
                    player_tanks_bodies[pi].style.rotate = r[0];
                }, TURN_DELAY));

                let delay = r[1] ? TURN_DURATION : 0;

                promises.push(promiseTrackedTimeout(function () {
                    player_tanks[pi].style.transform = transform;

                    promises.push(promiseTrackedTimeout(function () {
                        source_square.removeChild(player_tanks[pi]);

                        player_tanks[pi].style.transform = "";

                        dest_square.appendChild(player_tanks[pi]);
                    }, MOVE_DURATION));
                }, delay));
            }

            states[pi] = player_next_state;

        }

        Promise.all(promises).then(success, null);
    }).then(()=>{setTrackedTimeout(start_from_tick, TIME_BETWEEN_TICKS, i+1)}, null);
}


function run_simulation(starting_tick, initial_delay=true, keep_going=true) {
    // flow[0] is really just the initial states and not
    // part of the actual actions. Still, this indexing
    // is correct.
    states = [...flow[starting_tick]];  // new copy; current state

    let starting_flow_index = starting_tick + 1;

    let player_count = states.length;

    let tank = document.createElement("div");
    tank.classList.add("tank");

    let tank_body = document.createElement("div");
    tank_body.classList.add("tank-body");

    let tank_arrow = document.createElement("div");
    tank_arrow.classList.add("tank-arrow");

    tank_body.appendChild(tank_arrow);
    tank.appendChild(tank_body);

    // -1 for the border of 1px;
    square_inner_size = board.childNodes[0].childNodes[0]
        .getBoundingClientRect().height - 1;

    player_tanks = [];
    player_tanks_bodies = [];

    for (let i = 0; i < player_count; i++) {
        let tank_clone = tank.cloneNode(deep = true);
        let tank_clone_body = tank_clone.childNodes[0];

        tank_clone_body.style.rotate = MOVE_ROTATOINS[states[i][I['head']]];
        tank_clone_body.style.backgroundColor = TANK_COLORS[i];

        board.childNodes[states[i][I['x']]]
             .childNodes[states[i][I['y']]].appendChild(tank_clone);

        player_tanks.push(tank_clone);
        player_tanks_bodies.push(tank_clone_body);

        // Healthes must come from the next tick because the damages 
        // of the missiles fired in a tick get applied in the next
        // tick.
        health_texts[i].innerText = String(flow[starting_flow_index][i][I['health']]);
    }

    current_tick_text.innerText = String(starting_tick);
    current_tick = starting_tick;

    let delay = initial_delay ? INITIAL_DELAY : 0;

    if (keep_going) {
        setTrackedTimeout(start_from_tick, delay, starting_flow_index);
    }
}
