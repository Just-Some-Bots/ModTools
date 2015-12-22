# Mod Tools

## What does it do?

Its a tool kit I use to moderate a few releatively large servers that help me out. I strung this together for personal use so
any kind of professional coding went out the door on day one. It was made to assist with keeping order whether at home
or on mobile and to keep dirty Star Wars spoilers down and out. Everything was done using IDs as well for extra assurance in
these tools.

## How do I set it up?

Install Python here - https://www.python.org/downloads/

It was coded in 3.5.1 but 3.5 will work fine.


Make sure you have installed the requirements

    pip install -r requirements.txt

Make sure you meet the non-code requirements of having existing accounts for
both discord.

Create a roll on your server named "Muted" with that exact capitilization and set it's speak permission to denied on every channel.


  Options.txt set up
Line 1: the email of your discord account
Line 2: the password of your discord account
  (The next four are messages sent when something is filtered. Its currently set up for anti Force Awakens)
Line 3: Sent if a user is whitelisted send them this message if they break the filter
Line 4: Sent if a user broke the filter for the first time; deletes user's message
Line 5: Sent if a user broke the filter for the 2nd time; deletes user's message and kicks them from the filter
Line 6: Sent if a user broke the filter for the 3nd time; deletes user's entire message history and bans them from the server
Line 7: Number of days required to be on the server until you're except from the filter. Setting at 0 disables the filter.
Line 8: Accepts True or False. Decides whether to keep the whitelist clean and remove people who are now except from the filter
Line 9: Whether or not to send a message to people who are whitelisted by a moderator.


## What are its commands?

`[modifier] !remove [@username]` : will remove all posts by 'username' on the server. The modifier is option and accepts 
'kick' and 'ban' as options

`!whitelist [@username]` : will cause the filter to ignore this user when they post things that are filtered by it

`!modlist [@username]` : will add the user to the list of people who can also use these commands

`[time in seconds] !mute [@username]` : add the user to a "Muted" group if one exists. Will unmute if theres a 
time leading the !mute command

`!unmute [@username]` : used to unmute muted people if not timer was defined.

`!purge [@username]` : remove someone's ID from all files.
    Removes user entries from broken filter counts, the modlist, and the whitelists

## Sounds cool, How do I use it?
Simply download the bot, shift click in the directory and start command prompt, then call it:

    python modbot.py

It'll let you know if it's connected and what channels are connected.

Once started, let it run 24/7. If any errors occur, copy them down to report here, then restart the bot.

## NOTE: Only one moderator per server should be running this bot or major issues will occur. 
