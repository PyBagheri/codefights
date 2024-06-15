# Codefights: Let the codes battle

[**Codefights**](https://codefights.b32.ir) is a platform where user-uploaded codes can fight in different games. Users specify their game strategies in advance through their code, and the strategies face each other in a simulation.

<p align="center">
<img src="https://github.com/PyBagheri/codefights/assets/22708670/7b974be8-3b25-4b79-a97a-cab2a019989f" alt="Tanks" width="500px">
</p>


### Want to try?
I'm currently hosting Codefights here: [**codefights.b32.ir**](https://codefights.b32.ir). Be sure to give it a try! See the [**Guide**](https://codefights.b32.ir/guide/) section on code format and structure. **For the time being, we only support the Python programming language**.

Currently, only one game has been developed for the platform: [**Tanks**](https://codefights.b32.ir/games/tanks/). However, the structure of the project allows for developing new games.

# The Idea
This platform may host many **games**. Each game defines its own set of rules on how the codes should be playing the game, as well as certain conditions and limits, such as:
- The max and the min number of players
- Limits on the CPU time and RAM consumption.
- Possible user-modifiable game settings (under development)

 Each game, then, can be played by users as a **fight**. Currently the only way to create a fight is for one user to start a **hosting**, which in turn sends **invitations** to the target players. A fight may be started or canceled when the conditions are met, or if the **host** decides so.

 Once a fight starts, a simulation request is sent to the **simulator**. Once the simulation is over, the results are passed over to the **result processor** to be committed to the database.

 Finally, the result of the fight may be viewed by each player through the frontends provided by each game.

 For further details, see the [**Guide**](https://codefights.b32.ir/guide/).

# The Structure of the Project
Aside from the Django part, the structure of the project contains certain other components.
#### The Workers
Codefights has two main workers: the **simulator** and the **result processor**. 

Each fight is sent to the simulator, and once the simulation is over, the results are sent to the result processor to be committed to the database. These inter-service communications are done through Redis Streams. These two workers could be one together, but since the simulator runs as root and needs high levels of system privileges, I decided to keep them as separate services to avoid unnecessarily running the result processing as root.

#### The Games
The `games/` directory contains the games that are served on the platform, as well the base classes and tools for developing and testing each game.


#### The Global Config Module
Since certain configs had to be shared among different services, a global config module was necessary. The location of this module is set through the environment variable `GLOBAL_CONFIG_MODULE` in Python's importing format. Conventionally, we keep this module in the root of the project and simply specify its name in the environment variable. By default, each service will look for `config.py` (the module `config`) in the root of the project.
Since we need different configs for development and production, the config files/templates have been separated. When run in Docker containers, we bind-mount the proper config module as `config.py` to the root of the project.

#### Docker
We have multiple Dockerfiles for each project-specific service, but we also use some 3rd-party images (e.g., for `nginx`, `redis` and `postgres`), and some of them needed some tweaking, mainly to fix ownership and permission problems with bind mounts, and to also alter certain configurations. For this purpose, we made a thin overlaying Dockerfile for them too. Currently the images used for the services `nginx` and `redis` are altered in this way.


# The Simulator
The simulator has two parts: the controller and the coderunner. The controller is in charge of setting up each player's code in a sandbox and passing a handler of each player to the game class. This way, each game can communicate with each player's code without having to deal with lower-level things. The coderunner has a forkserver with has some basic setups done (inlcuding partial sandboxing) so that we don't have to do it everytime. The forkserver is commanded by the controller to spawn new coderunner instances, and each instance does some further setup (such as making a communication pipe), enters the full sandboxed mode, and finally runs the player's code. The controller connects to the each coderunner instance and creates the handlers, to be passed to the games.

While each code is running, it's watched closely for problems. This includes running illegal codes, as well as running out of CPU time or RAM limits. For security reasons, the simulator cannot distinguish runtime errors from illegal actions with 100% certainty, but if the code is sane, it can be done with a good level of confidence. For the time being, we don't support distinguishing runtime errors from other problems.

The main technologies used for sandboxing include:
- `ptrace`: for disallowing illegal syscalls and watching the signals. It's also used for starting/stopping each coderunner instance when needed.
- **AppArmor**: mainly used to control the files (codes, executables and libraries) that the coderunner will have access too. It also disallows some of the other illegal actions, but they are already covered by `ptrace`.
- `seccomp`: just as an added layer of security, especially in case of bugs in the tracer.
- **Linux namespace isolation (using Docker)**: We run the forkserver and the coderunner inside a Docker container. Docker handles separation and isolation of many Linux namespaces for us. For this reason, the controller must have access to the host's Docker API.

The use of `ptrace` requires certain privileges and conditions. For this reason, the simulator container run as root and also shares its PID namespace with the host.

Some testing tools and facilities have been prepared in `simulator/tests`. In order to use them, make sure to set up the `GLOBAL_CONFIG_MODULE` environment variable to `config_dev`, as well as the permissions for connecting to the Redis server's unix socket.

# Games

Each game is a subdirectory in `games/`, and as a minimum, contains these parts:
- `main.py`
- `frontend.py`
- `web/`

We optionally place a `templates/` directory in each game which contains the starter templates that can be downloaded and tweaked by players, but they are not registered on their own and must be uploaded in an instance of the `GameTemplate` model in the `gamespecs` app.

We place tests under the directory `tests/` in each game. There are some testing tools prepared for the job in the `games._tests` package, including a minimal coderunner with no safety regards so that each game can be tested separetely from the simulator.

### `main.py`

This module contains the main code of the game. A game's logic must be defind as a subclass of the base game class `games._base.game.Game`, and should at least implements the following additional methods:

- `get_limits(self)`
- `simulate(self)`
- `get_report(self)`

Currently the base game class implements the following methods which are necessary:

- `__init__(self, game_settings, player_count)`
- `set_controllers(self, cr_controllers, initial_players)`

The purpose of the parameters are self-explanatory. "cr" stands for "coderunner".  Currently both of these methods only set the instance attributes to the given values; the reason they are separate methods (rather than just a single `__init__`) is that the class has to be initialized first with the game settings and the number of players, so that `get_limits()` can decide on the limits (which might vary based on these factors); these limits are used to set up the coderunners before controllers can be passed to the game instance.

### `frontend.py`
This contains some logical parts of the frontend of the game. Currently the only frontend feature we support is **explanation**, which is a note for each fight based on its result, and is shown in the webpage of the fight. For example, in the game Tanks, if the tick limit is exceeded (which results in a draw) it's shown as an explanation. Explanations are also implemented as classes, which must be subclasses of `games._base.frontend.GameExplanation`. The explanations are based on the `explanation` field of the model `gamespecs.GameResult`. See the comments on the `GameExplanation` class as well as the `GameResult` model for more information.

### `web/`
This directory contains the web frontend codes to be rendered as the frontend of the game. Conventionally, this directory should contain two subdirectories:
- `templates/`
- `static/`

which contain the HTML files and the static files (css, js, ...), respectively.


> [!WARNING]
> This `templates/` contains the HTML files, which is different from the optional `templates/` in the root of the game directory which contains starter Python codes for the players.


### Registering Games
Firstly, it should be noted that each game has a "name" and a "title". The name of a game is an string that may only contain lowecase english letters and the underline character, and it also must not start with an underline (as it conflicts with the directories like `games/_base` and `games/_tests`). By convention, the name of the game should be the same as the name of its directory.  The title, on the other hand, is simply for display purposes on the website.

There are three steps to register a game into the system.

First, the game class must be included in dictionary `GAME_CLASSES` in the `games/index.py` module. The key of the item should be the name of the game (which, by convention, must be equal to the name of the game's directory), and the value should be the game class itself. The module `games/index.py` is imported by the simulator to access the game classes through their name.

Second, the explanation class of the game, as well as its web templates and static directories' paths must be included in the module `games/frontend.py` (check its code for the format). This module will is imported by the webapp to display the frontend of the game based on result of the fight.

Finally, in order for the game to be shown in the website, it must be registered as an instance of the model `gamespecs.models.GameInfo`.


This README is not a full documentation yet. For more information on how these different parts should act together, check the codes of [**Tanks**](/games/tanks/).


### Developing new games

The technical details of developing a new game are pretty much explained above (again, see the game [**Tanks**](/games/tanks/) for more information). 

Regarding the gameplays, you should have already noticed that this type of games are quite different than the games developed for real players. For example, things like reaction time or click speed are no more relevant. It's more like a battle of strategies, which means that the games should be oriented in that way; this requires some puzzle-making skills and creative thinking. In my opinion, the game [**Tanks**](/games/tanks/) doesn't fit this theme that well, but is a proof-of-concept game as the first game on the platform; though I'd still say it has some good potentials for a strategy fight.


# Setup for Development

If you use Docker, the file `compose.dev.yaml`, together with the development global config module (`config_dev.py`) should be mostly sufficient for the development, but further setup is required. The first time you run "up" the services, the named volumes will be created; then the following should be done:
- Create the database named in the global config module. By default, it's set to `codefights_dev`.
- Migrate the migrations.
- Create a superuser and manually set its `is_active` to True.


Some values have been hardcoded in the global config and the compose file for convenience.

Even though the codes are into the images, they are bind-mounted in there too, so that we don't have to build the image again. Also note that for development, the `nginx` service is not available, and we use Django's own builtin webserver (which by default doesn't serve media files).

The C extensions used in the simulator are built when building the images. If you change them, you have to rebuild the image, or alternatively, add another bind mount to them and build them manually.

You will need to register the AppArmor profile for the coderunner in `simulator/apparmor/cr-container-profile` manually in the kernel.


# Notes for Production

The templates for the compose config and the global config module have been placed in the root of the project, whose blanks may be filled in appropriate for the production environment and settings.

The external volumes need to be created manually. We also save some log files on the host which are done through bind mounts. These files and directories need to be owned by a user whose UID and primary GID will be passed as build args upon building images; this prevents ownership and permission issues and conflicts between the host and inside the containers.

Make sure to enable the autocommit on `sysctl`, as redis requires for functioning correctly.

Just as for in development, the AppArmor profile for the coderunner has to registered manually, and the C extensions are automatically compiled in the image builds. Also the setup for creating database and superuser, as well as migrating to database are required for production too. Further, as pointed out, we must create a system user in the host with proper UID and primary GID. We must also create a non-superuser database user to be used in production (whose username is specified in the global config module).

# Shortcomings and Future Plans

It's the first version and has many problems and shortcomings, mostly because I rushed some parts of it. For example:

- Messy config files.
- Limited tests for robustness and security.
- Limited user interface options (I rushed it; should be improved later)
- Messy UI and desktop only (I'm not a UI expert; currently it's just to show the concept, but should be improved later)
- No WebSocket used (even though the mechanism for it is mostly developed)

# Contact

If you find any bugs, or you want to contact me for other reasons, feel free to email me: `py.persian@gmail.com`.

# License

This project and repository is licensed under the GNU GPLv3. See [COPYING](./COPYING).