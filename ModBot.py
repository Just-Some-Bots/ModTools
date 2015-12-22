import asyncio
import discord
import re
import datetime
import youtube_dl

client = discord.Client()


with open('options.txt') as f:
    options = f.readlines()
for i, item in enumerate(options):
    options[i] = item.rstrip()

with open('bannedwords.txt') as f:
    bannedwords = f.readlines()
for i, item in enumerate(bannedwords):
    bannedwords[i] = item.rstrip()
with open('userstrikes.txt') as f:
    userstrikes = f.readlines()
for i, item in enumerate(userstrikes):
    userstrikes[i] = item.rstrip()
with open('userbans.txt') as f:
    userbans = f.readlines()
for i, item in enumerate(userbans):
    userbans[i] = item.rstrip()
with open('whitelist.txt') as f:
    whitelist = f.readlines()
for i, item in enumerate(whitelist):
    whitelist[i] = item.rstrip()
with open('modlist.txt') as f:
    modlist = f.readlines()
for i, item in enumerate(modlist):
    modlist[i] = item.rstrip()

@client.async_event
def on_ready():
    print('Connected!')
    print('Username: ' + client.user.name)
    print('ID: ' + client.user.id)
    print('--Server List--')
    for server in client.servers:
        print(server.name)

@client.async_event
def on_message(message):
    if message.author == client.user or message.author.id in modlist:
        if '!remove' in message.content.lower():
            do_log(message.author.name,message.content, True)
            f = open('log.txt', 'a')
            f.write(message.author.name + ' has used the command \'' + message.content+ '\' at ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\r")
            f.close()
            msg = message.content
            substrStart = msg.find('!remove') + 8
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            culprit = discord.utils.get(message.server.members, id=msg)
            if 'kick' in message.content.lower():
                yield from client.kick(culprit)
                f = open('userbans.txt', 'a')
                f.write(message.author.id)
                f.close()
            if 'ban' in message.content.lower():
                yield from client.ban(culprit)
            logs = yield from client.logs_from(message.channel)
            for messages in logs:
                if messages.author.id == msg:
                    yield from client.delete_message(messages)
        elif '!whitelist' in message.content.lower():
            do_log(message.author.name,message.content, True)
            msg = message.content
            substrStart = msg.find('!whitelist') + 11
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            f = open('whitelist.txt', 'a')
            f.write(msg + "\r")
            f.close()
            whitelist.append(msg)
            yield from client.delete_message(message)
        elif '!modlist' in message.content.lower():
            do_log(message.author.name,message.content, True)
            msg = message.content
            substrStart = msg.find('!modlist') + 9
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            f = open('modlist.txt', 'a')
            f.write(msg + "\r")
            f.close()
            modlist.append(msg)
            yield from client.delete_message(message)
        elif '!mute' in message.content.lower():
            do_log(message.author.name,message.content, True)
            msg = message.content
            substrStart = msg.find('!mute') + 6
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            asshole = discord.utils.get(message.server.members, id=msg)
            mutedrole = discord.utils.get(message.server.roles, name='Muted')
            yield from client.add_roles(asshole, mutedrole)
            msg = message.content
            if msg.find('!mute') != 0:
                timer = message.content
                timer = timer[ :msg.find('!mute')]
                timer.strip()
                timer = int(timer)
                yield from asyncio.sleep(timer)
                muteeroles = asshole.roles
                if mutedrole in muteeroles: muteeroles.remove(mutedrole)
                yield from client.replace_roles(asshole, *muteeroles)
        elif '!unmute' in message.content.lower():
            do_log(message.author.name,message.content, True)
            msg = message.content
            substrStart = msg.find('!unmute') + 8
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            reformedDick = discord.utils.get(message.server.members, id=msg)
            mutedrole = discord.utils.get(message.server.roles, name='Muted')
            muteeroles = reformedDick.roles
            if mutedrole in muteeroles: muteeroles.remove(mutedrole)
            yield from client.replace_roles(reformedDick, *muteeroles)
        elif '!purge' in message.content.lower():
            do_log(message.author.name,message.content, True)
            msg = message.content
            substrStart = msg.find('!purge') + 7
            msg = msg[substrStart: ]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            #thegraced = discord.utils.get(message.server.members, id=msg)
            this = msg
            while this in userstrikes: userstrikes.remove(this)
            while this in userbans: userbans.remove(this)
            while this in whitelist: whitelist.remove(this)
            while this in modlist: modlist.remove(this)
            f = open('userstrikes.txt', 'w')
            for line in userstrikes:
                f.write(line + "\r")
            f.close()
            f = open('userbans.txt', 'w')
            for line in userbans:
                f.write(line + "\r")
            f.close()
            f = open('whitelist.txt', 'w')
            for line in whitelist:
                f.write(line + "\r")
            f.close()
            f = open('modlist.txt', 'w')
            for line in modlist:
                f.write(line + "\r")
            f.close()
            yield from client.delete_message(message)
        else: return
    msg = do_format(message.content.lower())
    try:
        if is_long_member(message.author.joined_at):
            this = message.author.id
            if this in whitelist and options[7] == '1':
                while this in whitelist: whitelist.remove(this)
                f = open('whitelist.txt', 'w')
                for line in whitelist:
                    f.write(line + "\r")
                f.close()
        else:
            if msg in bannedwords:
                if message.author.id in whitelist:
                    yield from client.send_message(message.author, options[2]+'\n\n'+options[6])
                elif message.author.id in userbans:
                    yield from client.delete_message(message)
                    yield from client.ban(message.author)
                    try:
                        yield from client.send_message(message.author, options[5]+'\n\n'+options[6])
                    except:
                        print('Couldn\'t send message')
                    do_log(message.author.name,message.content, False)
                    logs = yield from client.logs_from(message.channel)
                    for messages in logs:
                        if messages.author.id == message.author.id:
                            yield from client.delete_message(messages)
                elif message.author.id in userstrikes:
                    yield from client.delete_message(message)
                    yield from client.kick(message.author)
                    try:
                        yield from client.send_message(message.author, options[4]+'\n\n'+options[6])
                    except:
                        print('Couldn\'t send message')
                    do_log(message.author.name,message.content, False)
                    f = open('userbans.txt', 'a')
                    f.write(message.author.id + "\r")
                    f.close()
                    userbans.append(message.author.id)
                else:
                    yield from client.delete_message(message)
                    try:
                        yield from client.send_message(message.author, options[3]+'\n\n'+options[6])
                    except:
                        print('Couldn\'t send message')
                    do_log(message.author.name,message.content, False)
                    f = open('userstrikes.txt', 'a')
                    f.write(message.author.id + "\r")
                    f.close()
                    userstrikes.append(message.author.id)
    except:
        return

def do_log(author,message, yah):
    f = open('log.txt', 'a')
    if yah:
        f.write(author + ' has used the command \'' + message+ '\' at ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\r")
    else:
        f.write(author + ' broke the filter by typing \'' + message+ '\' at ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\r")
    f.close()
        

def do_format(message):
    replacements = ( ('4','a'), ('3','e'), ('1','l'), ('0','o'), ('7','t') )
    endMsg = re.sub('À|à|Á|á|Â|â|Ã|ã|Ä|ä', 'a', message)
    endMsg = re.sub('È|è|É|é|Ê|ê|Ë|ë', 'e', endMsg)
    endMsg = re.sub('Ì|ì|Í|í|Î|î|Ï|ï', 'i', endMsg)
    endMsg = re.sub('Ò|ò|Ó|ó|Ô|ô|Õ|õ|Ö', 'o', endMsg)
    endMsg = re.sub('Ù|ù|Ú|ú|Û|û|Ü|ü', 'u', endMsg)
    endMsg = re.sub('Ý|ý|Ÿ|ÿ', 'y', endMsg)
    endMsg = re.sub('Ñ|ñ', 'n', endMsg)
    for old, new in replacements:
        endMsg = endMsg.replace(old, new)
    endMsg = re.sub('[^0-9a-zA-Z]+', '', endMsg)
    endMsg = re.sub(r'([a-z])\1+', r'\1', endMsg)
    return endMsg

def is_long_member(dateJoined):
    try:
        convDT = dateJoined.date()
        today = datetime.date.today()
        margin = datetime.timedelta(days = 5)
        return today - margin > convDT
    except:
        return False

def main_task():
    yield from client.login(options[0], options[1])
    yield from client.connect()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_task())
loop.close()
