nanobot - an extensible IRC bot
==============================

[![Tests](https://github.com/nanonyme/nanobot/actions/workflows/test.yml/badge.svg)](https://github.com/nanonyme/nanobot/actions/workflows/test.yml)

- [General architecture](#general-architecture)
- [Plugin System](#plugin-system)
- [Functionality](#functionality)
- [License](#license)

General architecture
--------------------

nanobot architecture is based on two processes: IRC process and
application process. The idea behind the separation is that there is
exactly one clean way in Python to reload code which is to restart the
process. Since reconnecting on code change is a nuisance, only the app
process is supposed to be restarted normally. 

The two processes talk with each other using Perspective Broker (PB)
which is a very easy way in Twisted to design IPC in terms of defining
proxy objects whose methods return deferreds that eventually result in
data or errors. Since the application process can be restarted, the
IRC side buffers messages until the application process is responsive.

Application process gets events from IRC and can handle them
appropriately using proxy objects. Currently there is only one proxy
object available and it describes the IRC connection. The proxy API is
not yet finished but the idea is that once it is, application side can
manipulate the bot as it wishes (disconnect, reconnect, join, part,
messaging, etc) without any need for changes on the IRC process
side. For connecting to new servers and changing settings another
proxy object for the IRC bot itself will most likely need to be created.

Plugin System
-------------

nanobot now features a plugin system that allows you to extend the bot's
functionality without modifying the core code. Plugins can register handlers
for IRC events and interact with the IRC server through a comprehensive API.

### Creating a Plugin

Plugins should inherit from the `Plugin` base class and implement the `load()`
method to register their event handlers:

```python
from plugin import Plugin
from twisted.logger import Logger

log = Logger()

class MyPlugin(Plugin):
    def load(self):
        # Register handlers for IRC events
        self.register_handler('privmsg', self.on_message)
        self.register_handler('user_joined', self.on_user_joined)
        
    def on_message(self, protocol, user, channel, message):
        # Handle incoming messages
        nick = user.split('!')[0]
        if 'hello' in message.lower():
            protocol.msg(channel, f"Hi {nick}!")
            
    def on_user_joined(self, protocol, user, channel):
        # Welcome new users
        nick = user.split('!')[0]
        protocol.msg(channel, f"Welcome {nick}!")

def load(registry, config):
    plugin = MyPlugin('my_plugin', registry, config.get('config', {}))
    plugin.load()
    return plugin
```

### Available Events

Plugins can register handlers for the following IRC events:

- `signed_on` - Bot successfully connected and signed on
- `privmsg(user, channel, message)` - Message received
- `user_joined(user, channel)` - User joined a channel
- `user_left(user, channel)` - User left a channel
- `user_quit(user, quitMessage)` - User quit IRC
- `user_kicked(kickee, channel, kicker, message)` - User was kicked
- `action(user, channel, data)` - User performed an action (/me)
- `topic_updated(user, channel, newTopic)` - Channel topic changed
- `user_renamed(oldname, newname)` - User changed nickname

### RemoteProtocol API

Plugins can interact with IRC through the protocol object passed to handlers.
Available methods include:

- `msg(user, message)` - Send a message
- `join(channel, key=None)` - Join a channel
- `leave(channel, reason=None)` - Leave a channel
- `topic(channel, topic=None)` - Get or set channel topic
- `mode(chan, set, modes, limit=None, user=None, mask=None)` - Set channel or user modes
- `kick(channel, user, reason=None)` - Kick a user from a channel
- `invite(user, channel)` - Invite a user to a channel
- `quit(message=None)` - Disconnect from IRC
- `describe(channel, action)` - Send an action (/me)
- `notice(user, message)` - Send a notice
- `away(message=None)` - Set away status
- `back()` - Remove away status

### Plugin Configuration

Configure plugins in your `config.json`:

```json
{
   "plugins": [
      {
         "name": "my_plugin",
         "module": "plugins.my_plugin",
         "enabled": true,
         "config": {
            "option1": "value1",
            "option2": "value2"
         }
      }
   ]
}
```

See `config.json.example` for a complete configuration example.

Functionality
-------------

The bot isn't currently capable of much. It has a proof-of-concept URL
title resolving using asynchronic HTTP client functionality of Twisted
combined with lxml push-driven parsing.  The push-driven parsing
allows for most buffering to happen inside lxml. The bot also has
support for some commands currently including a reincarnate command
where the app process dies and is spawned again by the IRC process
(which is sort of a supervisor). Credentials are kept in an sqlite3
database.

License
-------

Please see <https://github.com/nanonyme/nanobot/blob/master/LICENCE.md>
