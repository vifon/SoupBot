IRCBot
======

IRCBot is a yet another extensible IRC bot.  It's implemented using
`asyncio` and raw sockets for IRC communication.  It uses YAML for
configuration.

DEPENDENCIES
------------

- Python 3.6+
- libraries listed in `requirements.txt`

RUNNING
-------

1. (optional) Prepare a virtualenv:

        $ virtualenv .venv
        $ . .venv/bin/activate

2. Install the dependencies:

        $ pip install -r requirements.txt
        $ pip install -r requirements-plugins.txt  # needed only for some plugins

3. Edit the config (example in `bot_config.example.yml`) and run:

        $ ./bot.py your_config.yml

**Docker**

    # docker build -t ircbot .
    # docker run -d -v $PWD/bot_config.yml:/home/app/config.yml:ro ircbot

EXTENDING
---------

The `plugins` section in the config file may contain an arbitrary
Python module path with a class name on its end, e.g
`irc.plugins.my_new_plugin.MyPluginClass` though it doesn't need to
start with `irc.plugins`.  To create a new plugin class, inherit from
`irc.plugin.IRCPlugin` or one of its subclasses and override the
`react()` method-coroutine.  The existing plugins should be enough of
an example, `irc.plugins.pong.PongPlugin` is a good start.  Each
plugin works asynchronously and shouldn't interfere with the others as
long as the `react()` method isn't making any lengthy synchronous
calls.

COPYRIGHT
---------

Copyright (C) 2020  Wojciech Siewierski

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
