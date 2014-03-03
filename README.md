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

Functionality 
------------- 

The bot isn't currently capable of much. It has a proof-of-concept URL
title resolving using asynchronic HTTP client functionality of Twisted
combined with lxml push-driven parsing.  The push-driven parsing
allows for most buffering to happen inside lxml. The bot also has
support for some commands currently including a reincarnate command
where the app process dies and is spawned again by the IRC process
(which is sort of a supervisor). Credentials are kept in a sqlite3
database.

License
-------

Please see <https://github.com/nanonyme/nanobot/blob/master/LICENCE.md>