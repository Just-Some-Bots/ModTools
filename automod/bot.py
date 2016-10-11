import asyncio
import aiohttp
import discord
import traceback
import inspect
import os
import re
import shlex
import json
import random
import sys
import contextlib
import logging

from PIL import Image
from fuzzywuzzy import fuzz
from io import BytesIO, StringIO
from datetime import datetime, timedelta

from automod.config import Config
from automod.register import Register
from automod.response import Response
from automod.version import VERSION
from automod.utils import load_json, write_json, load_file, write_file, compare_strings, do_slugify, clean_string, \
    snowflake_time, strict_compare_strings, load_json_async, write_json_norm

from .exceptions import CommandError
from .constants import BOT_HANDLER_ROLE, RHINO_SERVER, RHINO_SERVER_CHANNEL, DOCUMENTATION_FOR_BOT, TWITCH_EMOTES, \
    RHINO_PATREON, SHITTY_BOT_IDS, CARBON_POST_URL, CARBON_POST_KEY, RHINO_STREAMTIP, BTTV_EMOTES, \
    OLD_MEM_SIMILARITY_PCT, NEW_MEM_SIMILARITY_PCT, SHITTY_BAN_LIST


# logger = logging.getLogger('discord')
# logger.setLevel(logging.DEBUG)
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
# handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
# logger.addHandler(handler)

def strfdelta(tdelta):
    t = {'days': 'days',
         'hours': 'hours',
         'minutes': 'minutes',
         'seconds': 'seconds'
         }

    d = {'days': tdelta.days}
    d['hours'], rem = divmod(tdelta.seconds, 3600)
    d['minutes'], d['seconds'] = divmod(rem, 60)
    if d['days'] is 1:
        t['days'] = 'day'
    if d['hours'] is 1:
        t['hours'] = 'hour'
    if d['minutes'] is 1:
        t['minutes'] = 'minute'
    if d['seconds'] is 1:
        t['seconds'] = 'second'
    if d['days'] is 0:
        if d['hours'] is 0:
            if d['minutes'] is 0:
                if d['seconds'] is 0:
                    return 'Eternity'
                return '{} {}'.format(d['seconds'], t['seconds'], )
            return '{} {} {} {}'.format(d['minutes'], t['minutes'], d['seconds'], t['seconds'], )
        return '{} {} {} {} {} {}'.format(d['hours'], t['hours'], d['minutes'], t['minutes'], d['seconds'],
                                          t['seconds'], )
    return '{} {} {} {} {} {} {} {}'.format(d['days'], t['days'], d['hours'], t['hours'], d['minutes'], t['minutes'],
                                            d['seconds'], t['seconds'], )


class AutoMod(discord.Client):
    def __init__(self, config_file='config/options.txt'):
        super().__init__()
        self.config = Config(config_file)

        self.register_instances = {}
        self.user_invite_dict = {}
        self.globalbans = set(map(int, load_file(self.config.globalbans_file)))
        self.banonjoin = set(map(int, load_file(self.config.banonjoin_file)))
        self.user_dict = {}


        self.server_index = self.load_configs()

        self.slow_mode_dict = {}

        self.uber_ready = False

        self.pmlist = []
        self.harasslist = {}

        self.status_update_count = [datetime.utcnow(), {}]

        self.tear_down_wall = []

        self.action_dict = {
            'actions_taken': 0,
            'commands_ran': 0,
            'messages_deleted': 0,
            'messages_processed': 0,
            'twitch_memes_killed': 0,
            'messages_sent': 0,
            'at_everyones': 0,
            'seconds_slowed': 0
        }
        self.start_time = datetime.utcnow()

        self.numpty_purge_list = []

        self.emote_list = []

        self.ban_dict = {}

        self.loop = None

        self.writing = False

        print('end of init')

    async def json_write_handler(self, filename, contents):
        if self.writing:
            while self.writing == True:
                await asyncio.sleep(3)
        if not self.writing:
            self.writing = True
            await write_json(filename, contents)
            self.writing = False



    async def backup_config(self, server_config_list):
        for key, current_config in server_config_list.items():
            current_config[11] = {}
            savedir = 'configs/' + str(key)
            if not os.path.exists(savedir):
                os.makedirs(savedir)
            savedir += '/config.json'
            try:
                write_json_norm(savedir, current_config)
            except:
                print('Server ID: {}\n\nConfig:\n{}'.format(savedir, current_config))

    async def safe_send_message(self, dest, content, *, server=None, tts=False, expire_in=0, also_delete=None,
                                quiet=False):
        final_dest = None
        for servers in self.servers:
            this = discord.utils.get(servers.channels, id=str(dest.id))
            if this:
                final_dest = this
        if not final_dest and isinstance(dest, discord.User):
            final_dest = dest
        elif not final_dest:
            if server:
                if server.id in self.server_index and dest.id == self.server_index[server.id][8]:
                    self.server_index[server.id][8] = None
                    self.server_index[server.id][10][0] = False
                    print("The Cunts on %s deleted their Mod Log. Removing..." % server.name)
                elif server.id in self.server_index and dest.id == self.server_index[server.id][9]:
                    self.server_index[server.id][9] = None
                    self.server_index[server.id][10][1] = False
                    print("The Cunts on %s deleted their Server Log. Removing..." % server.name)
                else:
                    print(
                            "What the actual fuck is going on here %s : %s : %s" % (dest.id, server.name, server.id))
            else:
                print("What the actual fuck is going on here %s : %s" % (dest.id, content))
            return
        try:
            msg = None
            msg = await self.send_message(final_dest, content, tts=tts)
            self.action_dict['messages_sent'] += 1

            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        except discord.Forbidden:
            if not quiet:
                if server:
                    print(
                            "Warning: Cannot send message to %s:%s, no permission" % (final_dest.name, server.name))
                else:
                    print("Warning: Cannot send message to %s:%s, no permission" % (
                        final_dest.name, final_dest.server.name))
        except discord.NotFound:
            if not quiet:
                if server:
                    print(
                            "Warning: Cannot send message to %s:%s, invalid channel?" % (final_dest.name, server.name))
                else:
                    print("Warning: Cannot send message to %s:%s, invalid channel?" % (
                        final_dest.name, final_dest.server.name))
        except discord.HTTPException:
            if not quiet:
                print("Warning: I'm being rate limited")
        finally:
            if msg: return msg

    async def safe_send_file(self, dest, fp, *, filename=None, comment=None, tts=False, expire_in=0, also_delete=None,
                             quiet=False):
        final_dest = None
        for servers in self.servers:
            this = discord.utils.get(servers.channels, id=str(dest.id))
            if this:
                final_dest = this
        if not final_dest:
            return
        try:
            msg = None
            msg = await self.send_file(final_dest, fp, filename=filename, content=comment, tts=tts)
            self.action_dict['messages_sent'] += 1

            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        except discord.Forbidden:
            if not quiet:
                print(
                        "Warning: Cannot send message to %s:%s, no permission" % (
                            final_dest.name, final_dest.server.name))
        except discord.NotFound:
            if not quiet:
                print("Warning: Cannot send message to %s:%s, invalid channel?" % (
                    final_dest.name, final_dest.server.name))
        except discord.HTTPException:
            if not quiet:
                print("Warning: I'm being rate limited")
        finally:
            if msg: return msg

    async def safe_delete_message(self, message, *, quiet=False):
        try:
            await self.delete_message(message)
            self.action_dict['messages_deleted'] += 1
            return True

        except discord.Forbidden:
            if not quiet:
                print("Warning: Cannot delete message \"%s\", no permission on %s" % (
                    message.clean_content, message.server.name))
        except discord.NotFound:
            if not quiet:
                print("Warning: Cannot delete message \"%s\", message not found on %s" % (
                    message.clean_content, message.server.name))
        return False

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        try:
            return await self.edit_message(message, new)

        except discord.NotFound:
            if not quiet:
                print("Warning: Cannot edit message \"%s\", message not found" % message.clean_content)
            if send_if_fail:
                if not quiet:
                    print("Sending instead")
                return await self.safe_send_message(message.channel, new)

    # noinspection PyMethodOverriding
    def run(self):
        loop = asyncio.get_event_loop()
        self.loop = loop
        try:
            loop.run_until_complete(self.start(self.config.token))
        finally:
            try:
                try:
                    self.loop.run_until_complete(self.logout())
                except:
                    pass
                pending = asyncio.Task.all_tasks()
                gathered = asyncio.gather(*pending)

                try:
                    gathered.cancel()
                    loop.run_until_complete(gathered)
                    gathered.exception()
                except:
                    pass
            except Exception as e:
                print("Error in cleanup:", e)

            loop.close()

    def load_configs(self):
        server_index = {}
        for root, dirs, files in os.walk('configs', topdown=False):
            for name in dirs:
                fullname = os.path.join(name, 'config.json')
                fileroute = os.path.join(root, fullname)
                try:
                    server_index[name] = load_json(fileroute)
                except:
                    print('Server ID: {}'.format(fileroute))
        return server_index


    async def has_roles(self, channel, user, check_server, command=None, register=False):
        if register is False:
            if check_server.id not in self.server_index:
                return
        perms = user.permissions_in(channel)
        if len(check_server.roles) != 1:
            try:
                for role in user.roles:
                    try:
                        if command:
                            try:
                                if role.id in self.server_index[check_server.id][16][1][command][1] or user.id in \
                                        self.server_index[check_server.id][16][1][command][0]:
                                    return False
                            except:
                                pass
                            try:
                                if role.id in self.server_index[check_server.id][16][0][command][1] or user.id in \
                                        self.server_index[check_server.id][16][0][command][0]:
                                    return True
                            except:
                                pass
                        if perms.administrator:
                            return True
                        elif role.name in self.server_index[check_server.id][14] or user.id in \
                                self.server_index[check_server.id][15]:
                            return True
                    except:
                        pass
            except:
                return False
        elif perms.administrator:
            return True
        else:
            raise CommandError('No valid roles detected on server {}'.format(check_server.name))

    async def is_checked(self, user, server):
        try:
            for role in user.roles:
                if server.id in self.server_index:
                    if role.name in self.server_index[server.id][3] or user.id in self.server_index[server.id][4]:
                        return False
        except:
            pass
        return True

    async def is_long_member(self, date_joined, server):
        if server.id not in self.server_index:
            return
        config = self.server_index[server.id]
        try:
            today = datetime.utcnow()
            margin = timedelta(hours=config[7])
            return today - margin > date_joined
        except:
            return False

    async def unshorten_url(self, url):
        try:
            import requests
            r = requests.head(url, allow_redirects=True)
            return r.url
        except:
            return url

    async def strict_limit_post(self, author, server, content, limit_post_flag=None):
        try:
            config = self.server_index[server.id]
            author_index = config[11][author.id]
            last_post_time = author_index[0]
            last_timeframe_content = author_index[2]
            now = datetime.utcnow()

            urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)

            if urls:
                for url in urls:
                    unshortened_url = await self.unshorten_url(url)
                    if unshortened_url:
                        content = content.replace(url, unshortened_url)

            match2 = re.split("[\n]{4,}", content)
            match = re.split(r"(.)\1{9,}", content)

            if self.server_index[server.id][10][4]:
                if len(match) > 1 or len(match2) > 1:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 2

            content = do_slugify(content)

            match2 = re.split("[\n]{4,}", content)
            match = re.split(r"(.)\1{9,}", content)

            if self.server_index[server.id][10][4]:
                if len(match) > 1 or len(match2) > 1:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 2

            if self.server_index[server.id][10][5]:
                if now - last_post_time < timedelta(minutes=10) and not limit_post_flag:
                    for last_content in last_timeframe_content:
                        if strict_compare_strings(last_content, content) > 79:
                            author_index[1] -= 1
                            self.server_index[server.id][11][author.id] = author_index
                            return 1

            if now - last_post_time < timedelta(seconds=config[2]):
                if self.server_index[server.id][10][3]:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    if author_index[1] <= 0:
                        return 3
            else:
                author_index[1] = config[1]
                author_index[2] = []
                author_index[3] = 0
            self.server_index[server.id][11][author.id] = author_index
            return 0
        except:
            print('wtf is this error, kurruption on {} ({})'.format(server.name, server.id))

    async def limit_post(self, author, server, content, limit_post_flag=None):
        try:
            config = self.server_index[server.id]
            author_index = config[11][author.id]
            last_post_time = author_index[0]
            last_timeframe_content = author_index[2]
            now = datetime.utcnow()

            urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)

            if urls:
                for url in urls:
                    unshortened_url = await self.unshorten_url(url)
                    if unshortened_url:
                        content = content.replace(url, unshortened_url)

            match2 = re.split("[\n]{4,}", content)
            match = re.split(r"(.)\1{9,}", content)

            if self.server_index[server.id][10][4]:
                if len(match) > 1 or len(match2) > 1:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 2

            content = do_slugify(content)

            match2 = re.split("[\n]{4,}", content)
            match = re.split(r"(.)\1{9,}", content)
            if self.server_index[server.id][10][4]:
                if len(match) > 1 or len(match2) > 1:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 2

            if self.server_index[server.id][10][5]:
                if now - last_post_time < timedelta(minutes=1) and not limit_post_flag:
                    for last_content in last_timeframe_content:
                        if compare_strings(last_content, content) > 95:
                            author_index[1] -= 1
                            self.server_index[server.id][11][author.id] = author_index
                            return 1

            this = config[2] + 1
            if now - last_post_time < timedelta(seconds=this):
                if self.server_index[server.id][10][3]:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    if author_index[1] <= 0:
                        return 3
            else:
                author_index[1] = config[1] + 2
                author_index[2] = []
                author_index[3] = 0
            self.server_index[server.id][11][author.id] = author_index
            return 0
        except Exception as e:
            print('wtf is this error, kurruption on {} ({})\n {}'.format(server.name, server.id, e))
            return 0

    async def check_names(self, name):
        pass

    async def on_ready(self):
        if not self.uber_ready:
            print('start of on_ready!')
            print('parsing userdict')
            self.user_dict = await load_json_async('config/userchanges.json')
            print('finished!')
            await self.dispatch_uber_ready()
            asyncio.ensure_future(self.backup_list())
        else:
            print('on ready triggered again!')

    async def on_resume(self):
        print('RESUMED')

    # async def on_ready(self):
    async def dispatch_uber_ready(self):
        print('start of uber_ready!')

        print('Connected!\n')
        print('Username: ' + self.user.name)
        print('ID: ' + self.user.id)

        print('Starting Member Update')
        member_list = self.get_all_members()
        for member in member_list:
            if member.id not in self.user_dict:
                self.user_dict[member.id] = {'names': [member.name],
                                             'avatar_changes': 0,
                                             'actions_taken_against': 0,
                                             'severs_banned_in': 0}
            elif member.name not in self.user_dict[member.id]['names']:
                self.user_dict[member.id]['names'].append(member.name)

        print('Starting Ban Update')
        temp_servers = list(self.servers)
        for server in temp_servers:
            try:
                self.ban_dict[server.id] = await self.get_bans(server)
            except:
                self.ban_dict[server.id] = []
                pass
        print('Updates Complete')

        print('--Servers Currently not Registered--')
        for server in self.servers:
            if server.id not in self.server_index:
                print("{} : {}".format(server.name, server.id))

        await self.json_write_handler('config/userchanges.json', self.user_dict)

        self.uber_ready = True
        print('~\n')

        print('\ngrabbing emote list')
        resp = ''
        try:
            with aiohttp.ClientSession() as session:
                async with session.get('https://twitchemotes.com/api_cache/v2/global.json') as r:
                    resp = await r.json()
            self.emote_list = [x.lower() for x in list(resp["emotes"].keys())]

            self.emote_list += BTTV_EMOTES
            print('success!')
        except:
            self.emote_list = TWITCH_EMOTES
            print('unsuccessfully got emote list')

    async def leave_dead_servers(self):
        server_leave_array = []
        for server in self.servers:
            if server.id not in self.server_index:
                rh1 = discord.utils.get(server.members, id=self.user.id)
                if datetime.utcnow() - timedelta(hours=24) > rh1.joined_at:
                    server_leave_array.append(server)

        if server_leave_array:
            for dbserver in server_leave_array:
                if dbserver.owner == dbserver.me:
                    await self.delete_server(dbserver)
                else:
                    await self.leave_server(dbserver)
                print('Leaving Deadbeat Server : {}'.format(dbserver.name))

    async def backup_list(self):
        var = True
        while var:
            if self.uber_ready:
                await asyncio.sleep(900)
                print('-----------BACKING UP JSONS-----------')
                await self.backup_config(self.server_index)
                await self.json_write_handler('config/userchanges.json', self.user_dict)
                await self.leave_dead_servers()
                print('done')
            else:
                await asyncio.sleep(5)

    async def write_to_modlog(self, message, author, server, reason):
        self.action_dict['actions_taken'] += 1
        if server.id in self.server_index:
            config = self.server_index[server.id]
        else:
            return
        if not config[8] or not config[10][0]:
            return
        if not reason:
            reason = "***No Reason Specified***"
            content = message.clean_content
        else:
            content = message.clean_content.replace('\"{}\"'.format(reason), '')
        await self.safe_send_message(discord.Object(id=config[8]),
                                     'At *{}* in **<#{}>**, **{}** has used the command ```{}```Reason: `{}`'
                                     ''.format(datetime.utcnow().strftime("%H:%M:%S on %a %b %d"), message.channel.id,
                                               clean_string(author.name), content, reason), server=server)

    async def _write_to_modlog(self, autoaction, offender, server, reason, channel=None):
        self.action_dict['actions_taken'] += 1
        await self.user_index_check(offender)
        self.user_dict[offender.id]['actions_taken_against'] += 1
        if server.id in self.server_index:
            config = self.server_index[server.id]
        else:
            return
        if not config[8] or not config[10][0]:
            return
        if not reason:
            reason = "***No Reason Specified***"
        if not channel:
            await self.safe_send_message(discord.Object(id=config[8]), 'At *{}*, I automatically {} **{}** due to {}'
                                                                       ''.format(
                    datetime.utcnow().strftime("%H:%M:%S on %a %b %d"), autoaction, clean_string(offender.name),
                    reason))
        else:
            await self.safe_send_message(discord.Object(id=config[8]),
                                         'At *{}*, I automatically {} **{}** in <#{}> for {}'
                                         ''.format(datetime.utcnow().strftime("%H:%M:%S on %a %b %d"), autoaction,
                                                   clean_string(offender.name), channel.id, reason), server=server)

    # TODO: Make this code that is mine, not stuff taken from code written by @Sharpwaves
    async def do_server_log(self, message=None, log_flag=None, member=None, before=None, after=None, server=None, reason=None, banned_id=None):
        if not self.uber_ready: return
        if message and not log_flag:
            return
            # if message.server.id in self.server_index:
            #     config = self.server_index[message.server.id]
            # else:
            #     return
            # if not self.server_index[message.server.id][10][1]:
            #     return
            # if not self.server_index[message.server.id][9]:
            #     return
            # if message.channel.id in config[12]:
            #     return
            # channel_trimmed = message.channel.name.upper()[:10]
            # if len(message.clean_content) > 1800:
            #     msg = '**`[{}]` __{}|__ {}:** {}'.format(datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, message.author.name, message.clean_content)
            #     split = [msg[i:i + 1800] for i in range(0, len(msg), 1800)]
            #     for x in split:
            #         await self.safe_send_message(discord.Object(id=config[9]), x)
            # else:
            #     msg = '**`[{}]` __{}|__ {} uploaded an attachment:** {}'.format(datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, message.author.name, message.attachments[0]['url'])
            #     await self.safe_send_message(discord.Object(id=config[9]), msg)
            #     if message.clean_content != '':
            #         msg = '**`[{}]` __{}|__ {}:** {}'.format(datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, message.author.name, message.clean_content)
            #         await self.safe_send_message(discord.Object(id=config[9]), msg)
        elif log_flag:
            if log_flag == 'join':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not self.server_index[member.server.id][10][1]:
                    return
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` ✅ __***{}#{}***__ *({})* **JOINED THE SERVER** ✅'
                                             ''.format(datetime.utcnow().strftime("%H:%M:%S"),
                                                       clean_string(member.name.upper()), member.discriminator, member.id),
                                             server=member.server)
                if datetime.utcnow() - timedelta(hours=24) < member.created_at:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '‼ **New account** __**{}#{}**__ *({})* **joined server** *({})*'
                                                 ''.format(clean_string(member.name.upper()), member.discriminator,
                                                           member.id, strfdelta(datetime.utcnow() - member.created_at)))

            elif log_flag == 'remove':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not self.server_index[member.server.id][10][1]:
                    return
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` ❌ __***{}#{}***__ *({})* **LEFT THE SERVER** ❌'
                                             ''.format(datetime.utcnow().strftime("%H:%M:%S"),
                                                       clean_string(member.name.upper()), member.discriminator, member.id),
                                             server=member.server)
            elif log_flag == 'ban':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not self.server_index[member.server.id][10][1]:
                    return
                if self.server_index[member.server.id][10][0]:
                    try:
                        await self.safe_send_message(discord.Object(id=config[8]),
                                                     'At *{}*, **{}#{}** was banned from the server'.format(
                                                     datetime.utcnow().strftime("%H:%M:%S on %a %b %d"),
                                                             clean_string(member.name), member.discriminator))
                    except:
                        self.server_index[server.id][8] = None
                        self.server_index[server.id][10][0] = False
                        print("The Cunts on %s deleted their Mod Log. Removing..." % server.name)
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` 🚫 __***{}#{}***__ *({})* **WAS BANNED FROM THE SERVER** 🚫'
                                             ''.format(datetime.utcnow().strftime("%H:%M:%S"),
                                                       clean_string(member.name.upper()), member.discriminator, member.id),
                                             server=member.server)
            elif log_flag == 'autoban':
                if server.id in self.server_index:
                    config = self.server_index[server.id]
                else:
                    return
                if not self.server_index[server.id][10][1]:
                    return
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` 🚫 **USER ID** *{}* ** WAS AUTOMATICALL BANNED FROM THE SERVE'
                                             'R** 🚫\n\t**REASON:** `{}'.format(datetime.utcnow().strftime("%H:%M:%S"),
                                                                                banned_id,
                                                                                reason),
                                             server=server)
            elif log_flag == 'unban':
                if server.id in self.server_index:
                    config = self.server_index[server.id]
                else:
                    return
                if not self.server_index[server.id][10][1]:
                    return
                if self.server_index[server.id][10][0]:
                    try:
                        await self.safe_send_message(discord.Object(id=config[8]),
                                                     'At *{}*, **{}#{}** was unbanned from the server'.format(
                                                     datetime.utcnow().strftime("%H:%M:%S on %a %b %d"),
                                                     clean_string(member.name), member.discriminator))
                    except:
                        self.server_index[server.id][8] = None
                        self.server_index[server.id][10][0] = False
                        print("The Cunts on %s deleted their Mod Log. Removing..." % server.name)
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` ✅ __***{}#{}***__ *({})* **WAS UNBANNED FROM THE SERVER** ✅'
                                             ''.format(datetime.utcnow().strftime("%H:%M:%S"),
                                                       clean_string(member.name.upper()), member.discriminator,
                                                       member.id), server=server)
            elif log_flag == 'edit':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                if before.channel.id in config[12]:
                    return
                channel_trimmed = after.channel.name.upper()[:10]
                if (len(before.clean_content) + len(after.clean_content)) > 1800:
                    msg = '**`[{}]` __{}|__ {}#{}** *edited their message*\n**Before:** {}\n**+After:** {}'.format(
                            datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, clean_string(after.author.name),
                             before.author.discriminator, before.clean_content, after.clean_content)
                    split = [msg[i:i + 1800] for i in range(0, len(msg), 1800)]
                    for x in split:
                        await self.safe_send_message(discord.Object(id=config[9]), x, server=before.server)
                else:
                    msg = '**`[{}]` __{}|__ {}#{}** *edited their message*\n**Before:** {}\n**+After:** {}'.format(
                            datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, clean_string(after.author.name),
                             before.author.discriminator, before.clean_content, after.clean_content)
                    await self.safe_send_message(discord.Object(id=config[9]), msg, server=before.server)
            elif log_flag == 'delete':
                if message.server.id in self.server_index:
                    config = self.server_index[message.server.id]
                else:
                    return
                if not self.server_index[message.server.id][10][1]:
                    return
                if not self.server_index[message.server.id][9]:
                    return
                if message.channel.id in config[12]:
                    return
                if message.content == '':
                    return
                channel_trimmed = message.channel.name.upper()[:10]
                if len(message.clean_content) > 1800:
                    msg = '**`[{}]` __{}|__** *{}#{}* **deleted their message:** {}'.format(
                            datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed, clean_string(message.author.name),
                             message.author.discriminator, clean_string(message.clean_content))
                    split = [msg[i:i + 1800] for i in range(0, len(msg), 1800)]
                    for x in split:
                        await self.safe_send_message(discord.Object(id=config[9]), x, server=message.server)
                else:
                    if message.clean_content != '':
                        msg = '**`[{}]` __{}|__ {}#{} deleted their message:** {}'.format(
                                datetime.utcnow().strftime("%H:%M:%S"), channel_trimmed,
                                clean_string(message.author.name), message.author.discriminator, clean_string(message.clean_content))
                        await self.safe_send_message(discord.Object(id=config[9]), msg, server=message.server)
            elif log_flag == 'avatar':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                no_avatar_file = open(os.path.join(sys.path[0], 'avatars/no_avatar.jpg'), 'rb')
                before_img = after_img = Image.open(no_avatar_file)
                try:
                    if before.avatar_url:
                        async with aiohttp.get(before.avatar_url) as r:
                            data = await r.read()
                            img = BytesIO(data)
                            before_img = Image.open(img)
                    if after.avatar_url:
                        async with aiohttp.get(after.avatar_url) as r:
                            data = await r.read()
                            img = BytesIO(data)
                            after_img = Image.open(img)
                except OSError:
                    no_avatar_file.close()
                    return
                result = Image.new('RGB', (256, 128))
                result.paste(before_img, (0, 0))
                result.paste(after_img, (128, 0))
                try:
                    no_avatar_file.close()
                except:
                    pass
                combined = BytesIO()
                result.save(combined, 'jpeg', quality=55)
                combined.seek(0)
                await self.safe_send_file(discord.Object(id=config[9]), combined, filename='before_after_avatar.jpg',
                                          comment='`[{}]` ⚠ **{}#{}** *changed their avatar*'.format(
                                                  datetime.utcnow().strftime("%H:%M:%S"), clean_string(after.name), after.discriminator))
            elif log_flag == 'name':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` ⚠ `{}#{}` *changed their name to* `{}`'.format(
                                                     datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                     after.discriminator, clean_string(after.name)), server=before.server)
            elif log_flag == 'nickname':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                if before.nick and after.nick:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *changed their nickname* `{}`->`{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(before.nick),
                                                         clean_string(after.nick)), server=before.server)
                elif before.nick:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *removed their nickname* `{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(before.nick)), server=before.server)
                elif after.nick:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *added a nickname* `{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(after.nick)), server=before.server)
            elif log_flag == 'vchanchange':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                if before.voice_channel and not after.voice_channel:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *left voice channel* `{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(before.voice_channel.name)), server=before.server)
                elif after.voice_channel and not before.voice_channel:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *joined voice channel* `{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(after.voice_channel.name)), server=before.server)
                elif before.voice_channel and after.voice_channel:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *changed voice channels* `{}`->`{}`'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator, clean_string(before.voice_channel.name),
                                                         clean_string(after.voice_channel.name)), server=before.server)
            elif log_flag == 'mutechange':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                if before.mute:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *was unmuted in voice*'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator), server=before.server)
                elif after.mute:
                    await self.safe_send_message(discord.Object(id=config[9]),
                                                 '`[{}]` ⚠ `{}#{}` *was muted in voice*'.format(
                                                         datetime.utcnow().strftime("%H:%M:%S"), clean_string(before.name),
                                                         after.discriminator), server=before.server)
            elif log_flag == 'role':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if not self.server_index[before.server.id][10][1]:
                    return
                if not self.server_index[before.server.id][9]:
                    return
                before_roles = '`None`' if len(before.roles) == 1 else '`{}`'.format(
                        '`, `'.join(x.name for x in before.roles[1:]))
                after_roles = '`None`' if len(after.roles) == 1 else '`{}`'.format(
                        '`, `'.join(x.name for x in after.roles[1:]))
                await self.safe_send_message(discord.Object(id=config[9]),
                                             '`[{}]` ⚠ **{}#{}\'s roles have changed**\n**Before:** {}\n**+After:** {}'.format(
                                                     datetime.utcnow().strftime("%H:%M:%S"), clean_string(after.name),
                                                     after.discriminator, clean_string(before_roles), clean_string(after_roles)), server=before.server)

    async def cmd_register(self, message, author, server):
        """
        Usage: {command_prefix}register
        If the user who starts the registration has the `AutoManager` role, start the registration process.
        """
        if await self.has_roles(message.channel, author, server, register=True):
            if author.id == self.user.id:
                return True
            if server.id in self.server_index:
                return Response('your server is already registered!', reply=True)
            error_response = ''
            if author.id in self.register_instances:
                error_response = 'YOU!'
            for register_instance in self.register_instances.values():
                if register_instance.user.id == author.id:
                    error_response = register_instance.user.name
            if not error_response:
                register = Register(author, server)
                self.register_instances[author.id] = register
                print('Registration Started for "{}" by: {}'.format(server.name, author.name))
                return await register.do_next_step()
            else:
                return Response('there is an existing registration instance for your server started by {}'.format(
                        error_response
                ),
                        reply=True
                )

    async def cmd_mute(self, message, server, author, mentions, option, time=None, reason=None):
        """
        Usage: {command_prefix}mute [ + | - | add | remove ] @UserName <time> ["reason"]
        Mutes or Unmutes the user(s) listed. If a time is defined then add
        """
        if await self.has_roles(message.channel, author, server, command='mute'):
            if option not in ['+', '-', 'add', 'remove']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            if not mentions:
                raise CommandError('Invalid user specified')
            if option in ['+', 'add']:
                if time and not reason and not time.isdigit():
                    reason = time
                    time = None
                if time:
                    try:
                        float(time)
                    except ValueError:
                        raise CommandError('Time provided invalid:\n{}\n'.format(time))

                mutedrole = discord.utils.get(server.roles, name='Muted')
                if not mutedrole:
                    raise CommandError('No Muted role created')
                for user in mentions:
                    try:
                        await self.add_roles(user, mutedrole)
                        await self.server_voice_state(user, mute=True)
                        self.user_dict[user.id]['actions_taken_against'] += 1
                        await self.write_to_modlog(message, author, server, reason)
                    except discord.Forbidden:
                        raise CommandError('Not enough permissions to mute user : {}'.format(user.name))
                    except:
                        raise CommandError('Unable to mute user defined:\n{}\n'.format(user.name))
                if time:
                    # self.server_index[message.server.id][13][message.author.id] = [float(time), datetime.utcnow()]
                    await asyncio.sleep(float(time))
                    for user in mentions:
                        muteeroles = user.roles
                        if mutedrole in muteeroles:
                            muteeroles.remove(mutedrole)
                        await self.replace_roles(user, *muteeroles)
                        await self.server_voice_state(user, mute=False)
                        await self._write_to_modlog('unmuted', user, server, 'the mute timing out')
            else:
                if time and not reason:
                    reason = time
                    time = None
                mutedrole = discord.utils.get(server.roles, name='Muted')
                for user in mentions:
                    muteeroles = user.roles
                    if mutedrole in muteeroles:
                        muteeroles.remove(mutedrole)
                    try:
                        await self.replace_roles(user, *muteeroles)
                        await self.server_voice_state(user, mute=False)
                        await self.write_to_modlog(message, author, server, reason)
                    except:
                        raise CommandError('Unable to unmute user defined:\n{}\n'.format(user.name))

    async def cmd_role(self, message, author, server, mentions, option, rolename, reason=None):
        """
        Usage: {command_prefix}role [ + | - | add | remove ] @UserName ["role name"] ["reason"]
        Adds or removes the role to the user(s) defined.
        """
        if await self.has_roles(message.channel, author, server, command='role'):
            if option not in ['+', '-', 'add', 'remove']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            if not mentions:
                raise CommandError('Invalid user specified')
            if option in ['+', 'add']:
                role = discord.utils.get(server.roles, name=rolename)
                if not role:
                    raise CommandError('No role named `{}` exists!'.format(rolename))
                for user in mentions:
                    try:
                        await self.add_roles(user, role)
                        await self.write_to_modlog(message, author, server, reason)
                    except:
                        raise CommandError('Unable to assign {} the role `{}`'.format(user.name, rolename))
            else:
                role = discord.utils.get(server.roles, name=rolename)
                for user in mentions:
                    stopdroprole = user.roles
                    if role in stopdroprole:
                        stopdroprole.remove(role)
                    try:
                        await self.replace_roles(user, *stopdroprole)
                        await self.write_to_modlog(message, author, server, reason)
                    except:
                        raise CommandError('Unable remove the role `{}` from user {}'.format(rolename, user.name))

    async def cmd_slowmode(self, message, author, server, channel_id, time_between, reason=None):
        """
        Usage: {command_prefix}slowmode #channel <time between messages> ["reason"]
        Puts the channel mentioned into a slowmode where users can only send messages every x seconds.
        To turn slow mode off, set the time between messages to "0"
        """
        if await self.has_roles(message.channel, author, server, command='slowmode'):
            if channel_id in self.server_index[message.server.id][12]:
                raise CommandError('ERROR: Channel ID is ignored. Unignore the channel before setting to slow mode')
            try:
                time_between = int(time_between)
            except:
                raise CommandError('ERROR: The time limit between messages isn\'t a number, please specify a real number')
            try:
                if channel_id in self.slow_mode_dict.keys():
                    if time_between == 0:
                        await self.delete_role(server, self.slow_mode_dict[channel_id]['channel_muted_role'])
                        del self.slow_mode_dict[channel_id]
                        await self.safe_send_message(discord.Object(channel_id), 'This channel is no longer in slow mode!')
                    else:
                        self.slow_mode_dict[channel_id]['time_between'] = time_between
                        await self.safe_send_message(discord.Object(channel_id), 'The delay between allowed messages is now **%s seconds**!' % time_between)
                else:
                    slowed_channel = discord.utils.get(server.channels, id=channel_id)
                    channel_muted_role = await self.create_role(server,
                                                                name=slowed_channel.name + 'SLOWROLE',
                                                                permissions=discord.Permissions(permissions=66560))
                    overwrite = discord.PermissionOverwrite()
                    overwrite.read_messages = True
                    overwrite.send_messages = False
                    await self.edit_channel_permissions(slowed_channel, channel_muted_role, overwrite)
                    await self.safe_send_message(discord.Object(channel_id), 'This channel is now in slow mode with a delay of **%s seconds**!' % time_between)
                    self.slow_mode_dict[channel_id] = {'time_between': time_between,
                                                       'channel_muted_role': channel_muted_role}
                await self.write_to_modlog(message, author, server, reason)
            except:
                raise CommandError('ERROR: Please make sure the syntax is correct and resubmit the command!')

    async def cmd_purge(self, message, author, server, channel, mentions, count=None, reason=None):
        """
        Usage: {command_prefix}purge <number of messages to purge> @UserName ["reason"]
        Removes all messages from chat unless a user is specified;
        then remove all messages by the user.
        """
        if await self.has_roles(message.channel, author, server, command='purge'):
            if server.id not in self.numpty_purge_list:
                if count and not reason and count.startswith('\"'):
                    reason = count
                    count = None
                if not mentions and not count:
                    raise CommandError('Usage: {}purge <number of messages to purge> @UserName [\"reason>\"]\n'
                                       'Removes all messages from chat unless a user is specified\n'
                                       'then remove all messages by the user.'.format(self.config.command_prefix))
                elif not mentions:
                    try:
                        count = int(count)
                    except ValueError:
                        raise CommandError('Invalid message count found : {}'.format(count))
                    self.numpty_purge_list.append(server.id)
                    await self.safe_delete_message(message)
                    try:
                        await self.purge_from(channel, limit=count, before=message)
                    except discord.Forbidden:
                        raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                           'try again!')
                    finally:
                        self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
                elif not count:
                    if not mentions:
                        raise CommandError('Invalid user specified')
                    self.numpty_purge_list.append(server.id)
                    await self.safe_delete_message(message)

                    def delete_this_msg(m):
                        return m.author in mentions

                    try:
                        await self.purge_from(channel, limit=5000, check=delete_this_msg, before=message)
                    except discord.Forbidden:
                        raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                           'try again!')
                    finally:
                        self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
                elif count and mentions:
                    try:
                        count = int(count)
                    except ValueError:
                        raise CommandError('Invalid message count found : {}'.format(count))
                    if count > 100 and author.id is not self.config.master_id:
                        raise CommandError('Message Purge count too large, please keep it under 100')
                    self.numpty_purge_list.append(server.id)
                    msg_count = 0
                    await self.safe_delete_message(message)

                    def delete_this_msg(m):
                        nonlocal msg_count
                        if m.author in mentions and msg_count < count:
                            msg_count += 1
                            return True
                        return False

                    try:
                        await self.purge_from(channel, limit=5000, check=delete_this_msg, before=message)
                    except discord.Forbidden:
                        raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                           'try again!')
                    finally:
                        self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
            else:
                raise CommandError('ERROR: You are already purging on your server, please wait till this is finished')

    async def cmd_snailpurge(self, message, author, server, channel, mentions, count=None, reason=None):
        """
        Usage: {command_prefix}snailpurge <number of messages to purge> @UserName ["reason"]
        Removes all messages from chat unless a user is specified;
        then remove all messages by the user.
        """
        if await self.has_roles(message.channel, author, server, command='purge'):

            if server.id not in self.numpty_purge_list:
                if count and not reason and count.startswith('\"'):
                    reason = count
                    count = None
                if not mentions and not count:
                    raise CommandError('Usage: {}purge <number of messages to purge> @UserName [\"reason>\"]\n'
                                       'Removes all messages from chat unless a user is specified\n'
                                       'then remove all messages by the user.'.format(self.config.command_prefix))
                elif not mentions:
                    try:
                        count = int(count)
                    except ValueError:
                        raise CommandError('Invalid message count found : {}'.format(count))
                    self.numpty_purge_list.append(server.id)
                    async for msg in self.logs_from(channel, count, before=message):
                        await asyncio.sleep(0.3)
                        did_delete = await self.safe_delete_message(msg)
                        if not did_delete:
                            self.numpty_purge_list.remove(server.id)
                            raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                               'try again!')
                    self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
                    await asyncio.sleep(0.3)
                    await self.safe_delete_message(message)
                elif not count:
                    if not mentions:
                        raise CommandError('Invalid user specified')
                    self.numpty_purge_list.append(server.id)
                    async for msg in self.logs_from(channel, before=message):
                        if msg.author in mentions:
                            await asyncio.sleep(0.3)
                            did_delete = await self.safe_delete_message(msg)
                            if not did_delete:
                                self.numpty_purge_list.remove(server.id)
                                raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                                   'try again!')

                    self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
                    await asyncio.sleep(0.3)
                    await self.safe_delete_message(message)
                elif count and mentions:
                    try:
                        count = int(count)
                    except ValueError:
                        raise CommandError('Invalid message count found : {}'.format(count))
                    if count > 100 and author.id is not self.config.master_id:
                        raise CommandError('Message Purge count too large, please keep it under 100')
                    msg_count = 0
                    self.numpty_purge_list.append(server.id)
                    async for msg in self.logs_from(channel, before=message):
                        if msg.author in mentions and msg_count < count:
                            await asyncio.sleep(0.3)
                            did_delete = await self.safe_delete_message(msg)
                            if not did_delete:
                                self.numpty_purge_list.remove(server.id)
                                raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                                   'try again!')
                            msg_count += 1
                    self.numpty_purge_list.remove(server.id)
                    await self.write_to_modlog(message, author, server, reason)
                    await asyncio.sleep(0.3)
                    await self.safe_delete_message(message)
            else:
                raise CommandError('ERROR: You are already purging on your server, please wait till this is finished')

    async def cmd_ban(self, message, author, server, mentions, reason=None):
        """
        Usage: {command_prefix}ban @UserName ["reason"]
        Bans the user(s) from the server, accepts multiple mentions
        """
        if await self.has_roles(message.channel, author, server, command='ban'):
            if not mentions:
                raise CommandError('Usage: {command_prefix}ban @UserName ["reason"]\nBans the user(s) from the server, accepts multiple mentions')
            for user in mentions:
                await self.ban(user, 7)
                self.user_dict[user.id]['actions_taken_against'] += 1
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_unban(self, message, author, server, leftover_args):
        """
        Usage: {command_prefix}unban [id] ["reason"]
        Unbans the user(s) from the server, accepts a list of user ids with spaces between each
        """
        if await self.has_roles(message.channel, author, server, command='unban'):
            reason = None
            if not leftover_args:
                raise CommandError('Usage: {command_prefix}unban [id] ["reason"]\nForces the ID to be banned from a server')
            try:
                int(leftover_args[-1])
            except:
                try:
                    reason = leftover_args[-1]
                    del leftover_args[-1]
                except TypeError:
                    raise CommandError('Please use a **USER ID** when using this command and not a name')
            for id in leftover_args:
                await self.unban(server, discord.Object(id=id))
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_forceban(self, message, author, server, leftover_args):
        """
        Usage: {command_prefix}forceban [id id id] ["reason"]
        Forces the users to be banned whether they're in the server or not
        """
        if await self.has_roles(message.channel, author, server, command='forceban'):
            reason = None
            try:
                int(leftover_args[-1])
            except:
                reason = leftover_args[-1]
                del leftover_args[-1]
            for this_id in leftover_args:
                await self.http.ban(this_id, server.id, 7)
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_massforceban(self, message, author, server, leftover_args):
        """
        Usage: {command_prefix}forceban [id id id] ["reason"]
        Forces the users to be banned whether they're in the server or not
        """
        if await self.has_roles(message.channel, author, server, command='forceban'):
            ban_list = ''.join(leftover_args).split(',')
            for this_id in ban_list:
                await self.http.ban(this_id, server.id, 0)
            await self.write_to_modlog(message, author, server, 'mass force ban')

    async def cmd_softban(self, message, author, server, mentions, reason=None):
        """
        Usage: {command_prefix}softban @UserName ["reason"]
        Bans and then unbans the user from the server.
        """
        if await self.has_roles(message.channel, author, server, command='ban'):
            if not mentions:
                raise CommandError('Usage: {}softban @UserName ["reason"]\nBans and then unbans the user from the'
                                   ' server.'.format(self.config.command_prefix))
            for user in mentions:
                await self.ban(user, 7)
                await self.unban(server, user)
                self.user_dict[user.id]['actions_taken_against'] += 1
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_tempban(self, message, author, server, mentions, time, reason=None):
        """
        Usage: {command_prefix}tempban @UserName <time> "reason"
        Bans and then unbans the user from the server.
        """
        if await self.has_roles(message.channel, author, server, command='ban'):
            if not mentions and not time:
                raise CommandError('Usage: {}tempban @UserName <time> "reason"\nBans and then unbans the user from the'
                                   ' server.'.format(self.config.command_prefix))
            try:
                time = int(time)
            except:
                raise CommandError('Usage: {}tempban @UserName <time> "reason"\nBans and then unbans the user from the'
                                   ' server.'.format(self.config.command_prefix))
            for user in mentions:
                await self.ban(user, 7)
                await self.write_to_modlog(message, author, server, reason)

            await asyncio.sleep(time)

            for user in mentions:
                await self.unban(server, user)
                await self._write_to_modlog('unbanned', user, server, 'the ban timing out')
                self.user_dict[user.id]['actions_taken_against'] += 1

    async def cmd_kick(self, message, author, server, mentions, reason=None):
        """
        Usage: {command_prefix}kick @Username ["reason"]
        Kicks the user from the server.
        """
        if await self.has_roles(message.channel, author, server, command='kick'):
            if not mentions:
                raise CommandError('Invalid user specified')
            for user in mentions:
                await self.kick(user)
                self.user_dict[user.id]['actions_taken_against'] += 1
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_whitelist(self, message, author, server, mentions, option, agent=None, reason=None):
        """
        Usage: {command_prefix}whitelist [ + | - | add | remove ] @UserName *OR* ["role name"] ["reason"]
        Adds or removes the user(s) or the role to the whitelist so they're ignored by the filters.
        """
        if await self.has_roles(message.channel, author, server, command='whitelist'):
            if option not in ['+', '-', 'add', 'remove']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            config = self.server_index[server.id]
            if option in ['+', 'add']:
                if mentions:
                    for user in mentions:
                        config[4].append(user.id)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=agent)
                        if not role:
                            int('this')
                        config[3].append(role.name)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(agent))
            else:
                if mentions:
                    for user in mentions:
                        try:
                            config[4].remove(user.id)
                        except ValueError:
                            raise CommandError('User `{}` is not whitelisted'.format(agent))
                else:
                    try:
                        role = discord.utils.get(server.roles, name=agent)
                        if not role:
                            int('this')
                        config[3].remove(role.name)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_modlist(self, message, author, server, mentions, option, agent=None, reason=None):
        """
        Usage: {command_prefix}modlist [ + | - | add | remove ] @UserName *OR* ["role name"] ["reason"]
        Adds or removes the user(s) or the role to the list of people I allow to use my commands!
        """
        if await self.has_roles(message.channel, author, server, command='modlist'):
            if option not in ['+', '-', 'add', 'remove']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            config = self.server_index[server.id]
            if option in ['+', 'add']:
                if mentions:
                    for user in mentions:
                        config[15].append(user.id)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=agent)
                        if not role:
                            int('this')
                        config[14].append(role.name)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(agent))
            else:
                if mentions:
                    for user in mentions:
                        config[15].remove(user.id)
                elif agent:
                    try:
                        role = discord.utils.get(server.roles, name=agent)
                        if not role:
                            int('this')
                        config[14].remove(role.name)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_blacklist(self, message, author, server, option, string_arg, reason=None):
        """
        Usage: {command_prefix}blacklist [ + | - | add | remove | clear] ["string"] ["reason"]
        Adds or removes the specified word / words (string) to the blacklist!
        """
        if await self.has_roles(message.channel, author, server, command='blacklist'):
            if option not in ['+', '-', 'add', 'remove', 'clear']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            config = self.server_index[server.id]
            if option in ['+', 'add']:
                if do_slugify(string_arg) == '' or len(do_slugify(string_arg)) < 4:
                    raise CommandError('Word not accepted to prevent harm to the server: {}'.format(string_arg))
                config[5].append(do_slugify(string_arg))
            elif option in ['clear']:
                config[5] = []
            else:
                try:
                    config[5].remove(string_arg)
                except ValueError:
                    raise CommandError('No such item in blacklist : {}'.format(string_arg))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)
            return Response('.', ignore_flag=True)

    async def cmd_settokens(self, message, author, server, tokens, reason=None):
        """
        Usage: {command_prefix}settokens <number> ["reason"]
        Sets the number of tokens a user has to spend in a reset period
        """
        if await self.has_roles(message.channel, author, server, command='settokens'):
            try:
                tokens = int(tokens)
            except:
                raise CommandError('Non number detected: {}'.format(tokens))
            if tokens < 1:
                raise CommandError('Cannot use a number less than 1, received : {}'.format(tokens))
            self.server_index[server.id][1] = tokens
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_settokenreset(self, message, author, server, time, reason=None):
        """
        Usage: {command_prefix}settokenreset <time in seconds> ["reason"]
        Sets the time frame in which a user can spend their tokens until they're rate limited
        """
        if await self.has_roles(message.channel, author, server, command='settokenreset'):
            try:
                time = int(time)
            except:
                raise CommandError('Non number detected: {}'.format(time))
            if time < 1:
                raise CommandError('Cannot use a number less than 1, received : {}'.format(time))
            self.server_index[server.id][2] = time
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_setpunishment(self, message, author, server, new_punishment, reason=None):
        """
        Usage: {command_prefix}setpunishment <new punishment> ["reason"]
        Sets the punishment to be used when a blacklisted word is detected
        Only accepts : 'kick', 'ban', 'mute', or 'nothing'
        """
        if await self.has_roles(message.channel, author, server, command='setpunishment'):
            if 'kick' != new_punishment and 'ban' != new_punishment and 'mute' != new_punishment and 'nothing' != new_punishment:
                raise CommandError('Improper option inputted: {}'.format(new_punishment))
            if new_punishment == self.server_index[server.id][6]:
                return
            self.server_index[server.id][6] = new_punishment
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_setlongtimemember(self, message, author, server, time, reason=None):
        """
        Usage: {command_prefix}setlongtimemember <time> ["reason"]
        Sets what the time in hours will be until a user is considered a 'long time member' of the server
        and be subjected to less strict filtering.
        """
        if await self.has_roles(message.channel, author, server, command='setlongtimemember'):
            try:
                time = int(time)
            except:
                raise CommandError('Non number detected: {}'.format(time))
            if time < 0:
                raise CommandError('Cannot use a number less than 0, received : {}'.format(time))
            if time > 1000000:
                raise CommandError('Cannot use a number greater than 1000000, received : {}'.format(time))
            self.server_index[server.id][7] = time
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_modlog(self, message, author, server, option, new_id=None, reason=None):
        """
        Usage: {command_prefix}modlog [set | + | - | true | false | yes | no | y | n] <new channel ID> ["reason"]
        If the first choice is set, it will change the mod log to the provided channel
        If the first choice is anything else, it'll toggle whether the modlog is used or not!
        "+, true, yes, y" will enable it and "-, false, no, n" will disable it
        """
        if await self.has_roles(message.channel, author, server, command='modlog'):
            if option not in ['set', '+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError(
                        'Invalid option "%s" specified, use +, -, true, false, yes, no, set, y or n' % option)
            if option in ['set']:
                try:
                    channel = discord.utils.get(server.channels, id=new_id)
                    if not channel:
                        int('this')
                except:
                    raise CommandError('Invalid Channel ID: {}'.format(new_id))
                self.server_index[server.id][8] = channel.id
            elif option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][0] = True
            else:
                self.server_index[server.id][10][0] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_setannouncements(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}setannouncements <new channel ID> ["reason"]
        Sets which channel will be used for announcements / broadcasts relating to RH1-N0
        Defaults to default server channel
        """
        if await self.has_roles(message.channel, author, server, command='setannouncements'):

            try:
                channel = discord.utils.get(server.channels, id=new_id)
                if not channel:
                    int('this')
            except:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            self.server_index[server.id][17] = channel.id
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_ratelimit(self, message, author, server, option, reason=None):
        """
        Usage: {command_prefix}ratelimit [+ | - | true | false | yes | no | y | n] ["reason"]
        Changes whether the bot will rate limit people or not!
        """
        if await self.has_roles(message.channel, author, server, command='ratelimit'):
            if option not in ['+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError('Invalid option "%s" specified, use +, -, true, false, yes, no, y or n' % option)
            if option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][3] = True
            else:
                self.server_index[server.id][10][3] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_dupeletters(self, message, author, server, option, reason=None):
        """
        Usage: {command_prefix}dupeletters [+ | - | true | false | yes | no | y | n] ["reason"]
        Changes whether the bot will remove messages for having duplicate letters or not
        """
        if await self.has_roles(message.channel, author, server, command='dupeletters'):
            if option not in ['+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError('Invalid option "%s" specified, use +, -, true, false, yes, no, y or n' % option)
            if option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][4] = True
            else:
                self.server_index[server.id][10][4] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_dupemessages(self, message, author, server, option, reason=None):
        """
        Usage: {command_prefix}dupemessages [+ | - | true | false | yes | no | y | n] ["reason"]
        Changes whether the bot will remove messages for being similar or the
        same as other messages
        """
        if await self.has_roles(message.channel, author, server, command='dupemessages'):
            if option not in ['+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError('Invalid option "%s" specified, use +, -, true, false, yes, no, y or n' % option)
            if option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][5] = True
            else:
                self.server_index[server.id][10][5] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_serverlog(self, message, author, server, option, new_id=None, reason=None):
        """
        Usage: {command_prefix}serverlog [set | + | - | true | false | yes | no | y | n] ["reason"]
        If the first choice is set, will change the server log to the provided channel
        If the first choice is anything else, it'll toggle whether the server log is used or not!
        "+, true, yes, y" will enable it and "-, false, no, n" will disable it
        """
        if await self.has_roles(message.channel, author, server, command='serverlog'):
            if option not in ['set', '+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError(
                        'Invalid option "%s" specified, use +, -, true, false, yes, no, y, set, or n' % option)
            if option in ['set']:
                try:
                    channel = discord.utils.get(server.channels, id=new_id)
                    if not channel:
                        int('this')
                except:
                    raise CommandError('Invalid Channel ID: {}'.format(new_id))
                self.server_index[server.id][9] = channel.id
            elif option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][1] = True
            elif option in ['-', 'false', 'no', 'n']:
                self.server_index[server.id][10][1] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_twitchemotes(self, message, author, server, option, reason=None):
        """
        Usage: {command_prefix}twitchemotes [+ | - | true | false | yes | no | y | n] ["reason"]
        Enables or Disables the removal of twitch emote phrases
        """
        if await self.has_roles(message.channel, author, server, command='twitchemotes'):
            if option not in ['+', '-', 'true', 'false', 'yes', 'no', 'y', 'n']:
                raise CommandError('Invalid option "%s" specified, use +, -, true, false, yes, no, y or n' % option)
            if option in ['+', 'true', 'yes', 'y']:
                self.server_index[server.id][10][2] = True
            else:
                self.server_index[server.id][10][2] = False
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_serverinfo(self, message, author, server):
        """
        Usage: {command_prefix}serverinfo
        Gets all the info for the server the command was called from and PM it to
        the person who used the command
        """
        if await self.has_roles(message.channel, author, server, command='serverinfo'):
            config = self.server_index[server.id]
            if config[9] == 0:
                server_log = 'Not Assigned'
            else:
                try:
                    server_log = discord.utils.get(server.channels, id=config[9]).name
                except:
                    server_log = "DELETED PLEASE FIX"
            if config[8] == 0:
                mod_log = 'Not Assigned'
            else:
                try:
                    mod_log = discord.utils.get(server.channels, id=config[8]).name
                except:
                    mod_log = "DELETED PLEASE FIX"
            msg = '*{}\'s Server Config*\n**Created in bot version number: {}**\n----------------------------------\n' \
                  'Number of Tokens: `{}`' \
                  '\n\nToken Reset Time: `{} second(s)`' \
                  '\n\nWhitelisted roles: `{}`' \
                  '\n\nWhitelisted Users: `{}`' \
                  '\n\nBlacklisted words: `{}`' \
                  '\n\nAutomatic action to take: `{}`' \
                  '\n\nTime till user considered an old user: `{} hours`' \
                  '\n\nChannel ID for Mod Log: `{}`' \
                  '\n\nChannel ID for Server Log: `{}`' \
                  '\n\nShould I use the Mod Log?: `{}`' \
                  '\n\nIgnored Channel IDs: `{}`' \
                  '\n\nRoles which can use all my commands: `{}`' \
                  '\n\nUsers who can use all my commands: `{}`' \
                  '\n\nShould I use the Server Log?: `{}`' \
                  '\n\nShould I remove messages containing Twitch Emotes?: `{}`' \
                  '\n\nShould I be rate limiting?: `{}`' \
                  '\n\nShould I be checking for duplicate characters?: `{}`' \
                  '\n\nShould I be checking for duplicate messages?: `{}`' \
                  '\n\nDynamic Permissions: ```ALLOWED:\n{}\nDENIED:\n{}```' \
                  '\n\n**END OF SERVER CONFIG**'.format(server.name, config[0],
                                                        config[1], config[2], config[3],
                                                        [discord.utils.get(self.get_all_members(), id=user).name for user in config[4] if discord.utils.get(self.get_all_members(), id=user)],
                                                        config[5], config[6],
                                                        config[7], mod_log, server_log, config[10][0],
                                                        [discord.utils.get(self.get_all_channels(), id=chan).name for chan in config[12] if discord.utils.get(self.get_all_channels(), id=chan)],
                                                        config[14], ['<@' + user + '>' for user in config[15]],
                                                        config[10][1],
                                                        config[10][2], config[10][3],
                                                        config[10][4], config[10][5],
                                                        json.dumps(config[16][0],
                                                                   indent=2),
                                                        json.dumps(config[16][1],
                                                                   indent=2))
            if len(message.clean_content) > 1800:
                split = [msg[i:i + 1800] for i in range(0, len(msg), 1800)]
                for x in split:
                    await self.safe_send_message(discord.Object(id=config[9]), x)
            else:
                await self.safe_send_message(author, msg)

    async def cmd_alertrhino(self, message, author, server, string_arg):
        """
        Usage: {command_prefix}alertrhino ["message"]
        Used to send a message to SexualRhinoceros if the bot isn't working for one reason or another!
        """
        if await self.has_roles(message.channel, author, server, command='alertrhino'):
            inv = await self.create_invite(server, max_uses=3)
            print('Alert Command on Server: {}'.format(server.name))
            for servers in self.servers:
                if servers.id == RHINO_SERVER:
                    for channel in servers.channels:
                        if channel.id == RHINO_SERVER_CHANNEL:
                            await self.safe_send_message(channel,
                                                         'Help requested by **{}** at *{}({})* for reason `{}`\n\t{}'
                                                         ''.format(author.name, server.name, server.id, string_arg,
                                                                   inv))
                            return Response('Rhino has been alerted!', reply=True)

    async def cmd_nick(self, message, author, server, nickname, reason=None):
        """
        Usage: {command_prefix}nick ["nickname"] ["reason"]
        Sets the nickname for RH1 on the server
        """
        if await self.has_roles(message.channel, author, server, command='nick'):
            try:
                await self.change_nickname(server.me, nickname)
            except discord.Forbidden:
                raise CommandError('ERROR: I do not have permission to set my own nick name on your server!')

    async def cmd_setnick(self, message, author, server, mentions, rolename=None, nickname=None, reason=None):
        """
        Usage: {command_prefix}setnick [@username OR "role name"]  ["nickname"] ["reason"]
        Sets the nickname for the user on the server
        """
        if await self.has_roles(message.channel, author, server, command='setnick'):
            usage = 'Usage: {}setnick [@username OR "role name"]  ["nickname"]\n' \
                    'Sets the nickname for the user on the server'.format(self.config.command_prefix)
            if not rolename:
                raise CommandError('ERROR: No rolename nor nickname were detected!\n\n%s' % usage)
            if mentions:
                if rolename and nickname:
                    reason = nickname
                    nickname = rolename
                    rolename = None
                elif not nickname and rolename:
                    nickname = rolename
                    rolename = None
                member_list = mentions
            elif rolename and nickname:
                if discord.utils.get(server.roles, name=rolename):
                    member_list = [members for members in server.members if discord.utils.get(server.roles, name=rolename) in members.roles]
                else:
                    raise CommandError('ERROR: Could not find rolename `%s`, please make sure you typed it case'
                                       ' accurate' % rolename)
            else:
                return CommandError('ERROR: No User or Role passed!')

            for user in member_list:
                try:
                        await self.change_nickname(user, nickname)
                except discord.Forbidden:
                    raise CommandError('ERROR: I do not have permission to manage nick names on your server!')
                except discord.HTTPException:
                    print('lol nickname rate limits')
            await self.write_to_modlog(message, author, server, reason)


    async def cmd_clearnick(self, message, author, server, mentions, rolename=None, reason=None):
        """
        Usage: {command_prefix}clearnick [@username OR "role name"]
        Clears the nickname of the user
        """
        if await self.has_roles(message.channel, author, server, command='clearnick'):
            usage = 'Usage: {}clearnick [@username OR "role name"]\n' \
                    'Clears the nickname of the user'.format(self.config.command_prefix)
            if mentions:
                if rolename:
                    reason = rolename
                    rolename = None
                member_list = mentions
            elif rolename:
                if discord.utils.get(server.roles, name=rolename):
                    member_list = [members for members in server.members if discord.utils.get(server.roles, name=rolename) in members.roles]
                else:
                    raise CommandError('ERROR: Could not find rolename `%s`, please make sure you typed it case'
                                       ' accurate' % rolename)
            else:
                raise CommandError('ERROR: No rolename was detected!\n\n%s' % usage)

            for user in member_list:
                try:
                    if user.nick != '':
                        await self.change_nickname(user, '')
                except discord.Forbidden:
                    raise CommandError('ERROR: I do not have permission to manage nick names on your server!')
                except discord.HTTPException:
                    print('lol nickname rate limits')
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_ping(self, message, author, server):
        """
        Usage: {command_prefix}ping
        Replies with "PONG!"; Use to test bot's responsiveness
        """
        if await self.has_roles(message.channel, author, server, command='ping'):
            if author.id == '94408525366697984':
                return Response(':banana:!', reply=True)
            elif author.id == '103057791312203776':
                return Response('Pew Pew! The Cavalry\'s Here!', reply=True)
            elif author.id == '91910066407481344':
                return Response('o/ ^^', reply=True)
            elif author.id == '68934448753676288':
                return Response('PONG! To the coolest guy ever!', reply=True)
            elif author.id == '90302230506258432':
                return Response('HAMMERDOWN!!', reply=True)
            elif author.id == '111281541090422784':
                return Response('👌🏽( ͡° ͜ ▴ ͡°👌🏽)', reply=True)
            elif author.id == '116662052847747072':
                return Response('I live!', reply=True)
            elif author.id == '112535542876377088':
                return Response('meow', reply=True)
            elif author.id == '87737926150033408':
                return Response('hue', reply=True)
            elif author.id == '146613143592894464':
                return Response('tar -zxvf PONG.tar.gz', reply=True)
            elif author.id == '109032564840226816':
                return Response('ONWARDS AOSHIMA!', reply=True)
            elif author.id == '81857014405271552':
                return Response('BRRRING', reply=True)
            elif author.id == '106391128718245888':
                return Response('Let\'s break it DOWN!', reply=True)
            elif author.id == '141989359254503425':
                return Response('Merhaba, @PikaDru™#8209! Adım RH1-N0.', reply=True)
            elif author.id == '124692511871598592':
                emoji1 = str(discord.utils.get(self.get_all_emojis(), id='213244178971230208'))
                emoji2 = str(discord.utils.get(self.get_all_emojis(), id='213244196155293696'))
                return Response('ayy bot aliev, {} >>> {}'.format(emoji1, emoji2), reply=True)
            else:
                return Response('PONG!', reply=True)

    async def cmd_olduserinfoplsnouse(self, message, mentions, author, server, option=None):
        """
        Usage: TELL RHINO TO ADD THIS
        """
        if await self.has_roles(message.channel, author, server, command='adad'):
            join_str = None
            user = None
            if mentions:
                user = mentions[0]
                join_str = user.joined_at.strftime("%c")
            elif not mentions and option:
                if discord.utils.get(server.members, name=option):
                    user = discord.utils.get(server.members, name=option)
                    join_str = user.joined_at.strftime("%c")
                elif discord.utils.get(server.members, id=option):
                    user = discord.utils.get(server.members, id=option)
                    join_str = user.joined_at.strftime("%c")
                if not user:
                    join_str = 'NOT IN SERVER'
                    for servers in self.servers:
                        if discord.utils.get(servers.members, name=option):
                            user = discord.utils.get(servers.members, name=option)
                        elif discord.utils.get(servers.members, id=option):
                            user = discord.utils.get(servers.members, id=option)
            elif not option:
                user = author
                join_str = user.joined_at.strftime("%c")
            if not user:
                raise CommandError('Could not find user info on "%s"' % option)
            await self.user_index_check(user)
            await self.safe_send_message(message.channel,
                    '```​          User: {}#{}\n         Names: {}\n            ID: {}\n    Created At'
                    ': {}\n        Joined: {}\n     # of Bans: {}\n   Infractions: {}\nShared Servers: {}\n        Avatar: {} \n```'.format(
                            clean_string(user.name), user.discriminator,
                            clean_string(', '.join(self.user_dict[user.id]['names'][-20:])), user.id,
                            snowflake_time(user.id).strftime("%c"), join_str,
                            self.user_dict[user.id]['severs_banned_in'],
                            self.user_dict[user.id]['actions_taken_against'],
                            len([servers for servers in self.servers if discord.utils.get(servers.members,
                                                                                                     id=user.id)]),
                            clean_string(user.avatar_url)
                    )
            )

    async def cmd_userinfo(self, message, mentions, author, server, option=None):
        """
        Usage: TELL RHINO TO ADD THIS
        """
        if await self.has_roles(message.channel, author, server, command='userinfo'):
            join_str = None
            user = None
            if mentions:
                user = mentions[0]
                join_str = user.joined_at.strftime("%c")
            elif not mentions and option:
                if discord.utils.get(server.members, name=option):
                    user = discord.utils.get(server.members, name=option)
                    join_str = user.joined_at.strftime("%c")
                elif discord.utils.get(server.members, id=option):
                    user = discord.utils.get(server.members, id=option)
                    join_str = user.joined_at.strftime("%c")
                if not user:
                    join_str = 'NOT IN SERVER'
                    for servers in self.servers:
                        if discord.utils.get(servers.members, name=option):
                            user = discord.utils.get(servers.members, name=option)
                        elif discord.utils.get(servers.members, id=option):
                            user = discord.utils.get(servers.members, id=option)
            elif not option:
                user = author
                join_str = user.joined_at.strftime("%c")
            if not user:
                raise CommandError('Could not find user info on "%s"' % option)
            await self.user_index_check(user)
            try:
                this = sorted(list(self.user_dict[user.id]['names'][-20:]), key=str.lower)
                new_this = [clean_string(this[0])]
                for elem in this[1:]:
                    if len(new_this[-1]) + len(elem) < 61:
                        new_this[-1] = new_this[-1] + ', ' + clean_string(elem)
                    else:
                        new_this.append(elem)
                names = clean_string('%s' % '\n                '.join(new_this))
            except Exception as e:
                raise CommandError('ERROR: Something wrong in name sorting, please alert Rhino about this!')
            final_dict = ['​          user: {}#{}'.format(clean_string(user.name), user.discriminator),
                          '         names: {}'.format(names),
                          '            id: {}'.format(user.id),
                          '    created at: {}'.format(snowflake_time(user.id).strftime("%c")),
                          '        joined: {}'.format(join_str),
                          '     # of bans: {}'.format(self.user_dict[user.id]['severs_banned_in']),
                          '   infractions: {}'.format(self.user_dict[user.id]['actions_taken_against']),
                          'shared servers: {}'.format(len([servers for servers in self.servers if discord.utils.get(
                                                           servers.members, id=user.id)])),
                          '        avatar: {}'.format(clean_string(user.avatar_url))
                          ]
            try:
                final = '\n'.join(final_dict)
                if len(final) > 1800:
                    final_this = [final_dict[0]]
                    for elem in final_dict[1:]:
                        if len(final_this[-1]) + len(elem) < 1800:
                            final_this[-1] = final_this[-1] + '\n' + elem
                        else:
                            final_this.append(elem)
                    for x in final_this:
                        await self.safe_send_message(message.channel, '```xl\n{}```'.format(x))
                else:
                    await self.safe_send_message(message.channel, '```xl\n{}```'.format(final))
            except Exception as e:
                raise CommandError('ERROR: Something wrong in final message sorting, please alert Rhino about this!')

    async def cmd_perms(self, message, author, server, mentions, switch, command=None, role_to_add=None,
                           reason=None):
        """
        Usage: {command_prefix}perms [allow | deny | clear] ["command"] [@username / "role name"] ["reason"]
        DO NOT USE THIS UNLESS YOU DIRECTLY ARE TOLD TO BY RHINO, YOU CAN MESS EVERYTHING UP EASILY
        """
        if await self.has_roles(message.channel, author, server, command='perms'):
            if switch not in ['allow', 'deny', 'clear']:
                raise CommandError('Invalid option "%s" specified, use allow, deny, or clear' % switch)
            if switch in ['allow']:
                if not command:
                    raise CommandError('Invalid syntax, command required for `allow` statements')
                handler = getattr(self, 'cmd_%s' % command, None)
                if not handler:
                    raise CommandError('Invalid command "%s" specified, please use an active command' % switch)
                if mentions:
                    for users in mentions:
                        if command in self.server_index[server.id][16][0]:
                            self.server_index[server.id][16][0][command][0].append(users.id)
                        else:
                            self.server_index[server.id][16][0][command] = [[users.id], []]
                        if command in self.server_index[server.id][16][1] and users.id in \
                                self.server_index[server.id][16][1][command][0]:
                            self.server_index[server.id][16][1][command][0].remove(users.id)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        if command in self.server_index[server.id][16][0]:
                            self.server_index[server.id][16][0][command][1].append(role.id)
                        else:
                            self.server_index[server.id][16][0][command] = [[], [role.id]]
                        if command in self.server_index[server.id][16][1] and role.id in \
                                self.server_index[server.id][16][1][command][1]:
                            self.server_index[server.id][16][1][command][1].remove(role.id)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))
            elif switch in ['deny']:
                if not command:
                    raise CommandError('Invalid syntax, command required for `deny` statements')
                handler = getattr(self, 'cmd_%s' % command, None)
                if not handler:
                    raise CommandError('Invalid command "%s" specified, please use an active command' % switch)
                if mentions:
                    for users in mentions:
                        if command in self.server_index[server.id][16][1]:
                            self.server_index[server.id][16][1][command][0].append(users.id)
                        else:
                            self.server_index[server.id][16][1][command] = [[users.id], []]
                        if command in self.server_index[server.id][16][0] and users.id in \
                                self.server_index[server.id][16][0][command][0]:
                            self.server_index[server.id][16][0][command][0].remove(users.id)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        if command in self.server_index[server.id][16][1]:
                            self.server_index[server.id][16][1][command][1].append(role.id)
                        else:
                            self.server_index[server.id][16][1][command] = [[], [role.id]]
                        if command in self.server_index[server.id][16][0] and role.id in \
                                self.server_index[server.id][16][0][command][1]:
                            self.server_index[server.id][16][0][command][1].remove(role.id)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))
            else:
                if mentions:
                    if command:
                        raise CommandError('Invalid syntax, command not used in `clear` statements')
                    for users in mentions:
                        for command, user_role_list in self.server_index[server.id][16][0].items():
                            if users.id in user_role_list[0]:
                                self.server_index[server.id][16][0][command][0].remove(users.id)
                        for command, user_role_list in self.server_index[server.id][16][1].items():
                            if users.id in user_role_list[0]:
                                self.server_index[server.id][16][1][command][0].remove(users.id)
                else:
                    if command and not role_to_add:
                        role_to_add = command
                        command = None
                    else:
                        raise CommandError('Invalid syntax')
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        for command, user_role_list in self.server_index[server.id][16][0].items():
                            if role.id in user_role_list[1]:
                                self.server_index[server.id][16][0][command][1].remove(role.id)
                        for command, user_role_list in self.server_index[server.id][16][1].items():
                            if role.id in user_role_list[1]:
                                self.server_index[server.id][16][1][command][1].remove(role.id)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_help(self, message, author, server):
        """
        Usage: {command_prefix}help
        Replies with the link to the commands page!
        """
        if await self.has_roles(message.channel, author, server, command='help'):
            return Response('<https://github.com/SexualRhinoceros/ModTools/wiki/Command-List>', reply=True)

    async def cmd_cls(self, message, author, server, channel):
        """
        Usage: {command_prefix}eval "evaluation string"
        runs a command thru the eval param for testing
        """
        if author.id == self.config.master_id:
            await self.safe_delete_message(message)

            def delete_this_msg(m):
                return m.author == self.user

            try:
                await self.purge_from(channel, limit=5000, check=delete_this_msg, before=message)
            except discord.Forbidden:
                raise CommandError('I cannot delete messages, please give me permissions to do so and'
                                   'try again!')

    async def cmd_info(self, message, author, server):
        """
        Usage: {command_prefix}info
        Sends a whole buncha info pertaining to the bot to the chat!
        """
        return Response(
                'I was coded by SexualRhinoceros and am currently on v{} ! \nFor documentation on my commands or info on how to get my in your'
                ' server, check out this link! {}'.format(VERSION, DOCUMENTATION_FOR_BOT), reply=True)

    async def cmd_donate(self, message, author, server):
        """
        Usage: {command_prefix}donate
        Sends a whole buncha info pertaining to rhino's patreon to the chat!
        """
        return Response('Thanks for considering donating! If you want to support me monthly, check out my'
                        ' Patreon here\n\t{}\nor for one time, you can find my paypal here\n\t{}'
                        ''.format(RHINO_PATREON, RHINO_STREAMTIP),
                        reply=True)

    async def cmd_ignore(self, message, author, server, option, new_id, reason=None):
        """
        Usage: {command_prefix}ignore [ + | - | add | remove ] <channel ID> ["reason"]
        Adds or removes the channel ID to the list of ignored channels when outputting to the server log
        """
        if await self.has_roles(message.channel, author, server, command='ignore'):
            if option not in ['+', '-', 'add', 'remove']:
                raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)
            try:
                channel = discord.utils.get(server.channels, id=new_id)
                if not channel:
                    int('this')
            except:
                raise CommandError('Invalid Channel: {}'.format(new_id))
            if option in ['+', 'add']:
                self.server_index[server.id][12].append(channel.id)
            else:
                try:
                    self.server_index[server.id][12].remove(channel.id)
                except ValueError:
                    raise CommandError('No such channel in ignore list : {}'.format(new_id))
            await self.write_to_modlog(message, author, server, reason)

    async def cmd_rolecolor(self, message, author, server, rolename, new_hex, reason=None):
        """
        Usage: {command_prefix}rolecolor ["role name"] "#hex color code" ["reason"]
        Changes the color of a role to whatever hexadecimal color code is provided
        """
        if await self.has_roles(message.channel, author, server, command='rolecolor'):
            check = re.compile('^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')
            if check.match(new_hex):
                try:
                    role = discord.utils.get(server.roles, name=rolename)
                    if not role:
                        int('this')
                except:
                    raise CommandError('Invalid Role: {}'.format(rolename))
                new_int = new_hex.replace('#', '0x')
                new_int = int(new_int, 0)
                await self.edit_role(server, role, colour=discord.Colour(value=new_int))
                await self.write_to_modlog(message, author, server, reason)
            else:
                raise CommandError('Invalid Hex Code: {}'.format(new_hex))

    async def cmd_dropdeadbeats(self, message, author, server):
        """
        Usage: {command_prefix}dropdeadbeats
        Removes the bot from all dead beat servers who never register
        """
        if author.id == self.config.master_id:
            server_leave_array = []
            for server in self.servers:
                if server.id not in self.server_index:
                    rh1 = discord.utils.get(server.members, id=self.user.id)
                    if datetime.utcnow() - timedelta(hours=24) > rh1.joined_at:
                        server_leave_array.append(server)

            servers_list = []
            if server_leave_array:
                for dbserver in server_leave_array:
                    print('Leaving Deadbeat Server : {}'.format(dbserver.name))
                    servers_list.append(dbserver.name)
                    await self.leave_server(dbserver)
            return Response('Dropped servers: ```%s```' % ', '.join(servers_list), reply=True)
        return

    async def cmd_fixpurgelist(self, author):
        """
        Usage: {command_prefix}forcebackup
        Forces a back up of all server configs
        """
        if author.id in [member.id for member in discord.utils.get(self.servers, id='129489631539494912').members if discord.utils.get(discord.utils.get(self.servers, id='129489631539494912').roles, id='129667505923948544') in member.roles]:
            self.numpty_purge_list = []
        return

    async def cmd_testurl(self, author, url):
        """
        Usage: {command_prefix}forcebackup
        Forces a back up of all server configs
        """
        if author.id == self.config.master_id:
            fixed_url = await self.unshorten_url(url)
            return Response(fixed_url, reply=True)
        return

    async def cmd_servers(self, message, mentions, author, server, option=None):
        """
        Usage: {command_prefix}ping
        Replies with "PONG!"; Use to test bot's responsiveness
        """
        if author.id in [self.config.master_id, '98295630480314368', '134122930828214273']:
            user = None
            if mentions:
                user = mentions[0]
            elif not mentions and option:
                if discord.utils.get(server.members, name=option):
                    user = discord.utils.get(server.members, name=option)
                elif discord.utils.get(server.members, id=option):
                    user = discord.utils.get(server.members, id=option)
                if not user:
                    for servers in self.servers:
                        if discord.utils.get(servers.members, name=option):
                            user = discord.utils.get(servers.members, name=option)
                        elif discord.utils.get(servers.members, id=option):
                            user = discord.utils.get(servers.members, id=option)
            elif not option:
                user = author
            if not user:
                raise CommandError('Could not find user info on "%s"' % option)
            await self.safe_send_message(message.channel, ', '.join([servers.name for servers in self.servers if discord.utils.get(servers.members, id=user.id)]))



    async def cmd_changegame(self, author, option, string_game):
        """
        Usage: {command_prefix}changegame ["new game name"]
        Changes the "Now Playing..." game on Discord!
        """
        if author.id == self.config.master_id:
            if option not in ['+', 'true', '-', 'false']:
                return Response('🖕 bad input you ass', reply=True)
            if option in ['+', 'true']:
                await self.change_status(game=discord.Game(name=string_game,
                                                           url='https://www.twitch.tv/s3xualrhinoceros',
                                                           type=1))
            else:
                await self.change_status(game=discord.Game(name=string_game))
            return Response(':thumbsup:', reply=True)
        return
    async def cmd_promote(self, author, string_game):
        """
        Usage: {command_prefix}changegame ["new game name"]
        Changes the "Now Playing..." game on Discord!
        """
        if author.id == self.config.master_id:
            await self.change_status(game=discord.Game(name='CHECK THIS OUT',
                                                       url=string_game,
                                                       type=1))
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_changename(self, author, string_name):
        """
        Usage: {command_prefix}changegame ["new game name"]
        Changes the "Now Playing..." game on Discord!
        """
        if author.id == self.config.master_id:
            await self.edit_profile(username=string_name)
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_changeavi(self, author, string_avi):
        """
        Usage: {command_prefix}changegame ["new game name"]
        Changes the "Now Playing..." game on Discord!
        """
        if author.id == self.config.master_id:
            async with aiohttp.get(string_avi) as r:
                data = await r.read()
                await self.edit_profile(avatar=data)
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_eval(self, author, server, message, channel, mentions, code):
        """
        Usage: {command_prefix}eval "evaluation string"
        runs a command thru the eval param for testing
        """
        if author.id == self.config.master_id:
            result = None

            try:
                result = eval(code)
            except Exception:
                formatted_lines = traceback.format_exc().splitlines()
                return Response('```py\n{}\n{}\n```'.format(formatted_lines[-1], '/n'.join(formatted_lines[4:-1])), reply=True)

            if asyncio.iscoroutine(result):
                result = await result

            if result:
                return Response('```{}```'.format(result), reply=True)

            return Response(':thumbsup:'.format(result), reply=True)
        return

    async def cmd_exec(self, author, server, message, channel, mentions, code):
        """
        Usage: {command_prefix}eval "evaluation string"
        runs a command thru the eval param for testing
        """
        if author.id == self.config.master_id:
            old_stdout = sys.stdout
            redirected_output = sys.stdout = StringIO()

            try:
                exec(code)
            except Exception:
                formatted_lines = traceback.format_exc().splitlines()
                return Response('```py\n{}\n{}\n```'.format(formatted_lines[-1], '\n'.join(formatted_lines[4:-1])), reply=True)
            finally:
                sys.stdout = old_stdout

            if redirected_output.getvalue():
                return Response(redirected_output.getvalue(), reply=True)
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_lurk(self, author, server, message, channel):
        """
        Usage: {command_prefix}lurk
        Force the bot to lurk in a server rather than send shit to it or leave
        after the time is up
        """
        if author.id in [self.config.master_id, '98295630480314368', '134122930828214273']:
            self.server_index[server.id] = ['LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK',
                                            'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK', 'LURK']
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_blserver(self, author, key):
        """
        Usage: {command_prefix}lurk
        Force the bot to lurk in a server rather than send shit to it or leave
        after the time is up
        """
        if author.id in [self.config.master_id, '98295630480314368', '134122930828214273']:
            try:
                if discord.utils.get(self.servers, name=key):
                    await self.leave_server(discord.utils.get(self.servers, name=key))
                    self.globalbans.add(discord.utils.get(self.servers, name=key).id)
                elif discord.utils.get(self.servers, id=key):
                    await self.leave_server(discord.utils.get(self.servers, id=key))
                    self.globalbans.add(discord.utils.get(self.servers, id=key).id)
                else:
                    print('I did fuck all')
                write_file('config/globalbans.txt', self.globalbans)
                return Response(':thumbsup:', reply=True)
            except:
                return Response(':thumbsdown:', reply=True)
        return

    async def cmd_globalban(self, author, this_id, leftover_args):
        """
        Usage: {command_prefix}lurk
        Force the bot to lurk in a server rather than send shit to it or leave
        after the time is up
        """
        if author.id in [self.config.master_id, '98295630480314368', '134122930828214273']:
            if not leftover_args:
                raise CommandError('ERROR: You didn\'t fucking specify a reason you fuck stick\n'
                                   '[!!globalban <id> <reason>] NO FUCKING QUOTES NEEDED BRUH')
            reason = ' '.join(leftover_args)
            serverlist = list(self.servers)
            for server in serverlist:
                try:
                    await self.http.ban(this_id, server.id, 0)
                    await self.do_server_log(banned_id=this_id, server=server, reason=reason, log_flag='autoban')
                    await asyncio.sleep(1)
                except:
                    print('cannot ban on %s' % server.name)
            write_file('config/banonjoin.txt', self.banonjoin)
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_stats(self, author, channel, server, id=None):
        """
        Usage: {command_prefix}lurk
        Force the bot to lurk in a server rather than send shit to it or leave
        after the time is up
        """
        if await self.has_roles(channel, author, server, command='stats'):
            info_dict = {
                'servers': 0,
                'members': 0,
                'actionstaken': self.action_dict['actions_taken'],
                'starttime': datetime.utcnow() - self.start_time,
                'commandsran': self.action_dict['commands_ran'],
                'messagesdeleted': self.action_dict['messages_deleted'],
                'messagesprocessed': self.action_dict['messages_processed'],
                'ateveryones': self.action_dict['at_everyones'],
                'messagessent': self.action_dict['messages_sent']
            }
            for server in self.servers:
                info_dict['servers'] += 1
                for member in server.members:
                    info_dict['members'] += 1

            return Response(
                    'I have been running continuously for **{}**!\nI\'m currently in **{}** servers and can see '
                    '**{}** members in those servers.\n\nSince starting, I have seen **{}** messages, automatically taken **{}** moderation'
                    ' actions, sent **{}** messages, deleted **{}** messages, have had **{}** commands ran, and seen @\u200beveryone used **{}** times!'
                    '\n\n To get me on your server, PM me an invite link or go to **https://www.carbonitex.net/'
                    'discord/bots?rhino**'
                    ''.format(strfdelta(info_dict['starttime']), info_dict['servers'], info_dict['members'],
                              info_dict['messagesprocessed'], info_dict['actionstaken'],
                              info_dict['messagesdeleted'], info_dict['messagessent'], info_dict['commandsran'],
                              info_dict['ateveryones']),
                    reply=True)
        return

    async def cmd_dropconfigs(self, author):
        """
        Usage: {command_prefix}forcebackup
        Forces a back up of all server configs
        """
        if author.id == self.config.master_id:
            server_id_list = []
            for server in self.servers:
                server_id_list.append(server.id)
            new_index = {}
            for id, config in self.server_index.items():
                if id in server_id_list:
                    new_index[id] = config
            self.server_index = new_index
            await self.backup_config(new_index)
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_restart(self, channel, author, server):
        """
        Usage: {command_prefix}forcebackup
        Forces a back up of all server configs
        """
        if author.id in [self.config.master_id, '98295630480314368', '134122930828214273']:
            await self.safe_send_message(discord.Object(id='155553608400764928'),
                                         '__**<@{}>**__ restarting in *{}* on `{}`'.format(author.id,
                                                                                           channel.name,
                                                                                           server.name
                                                                                           )
                                         )
            await self.safe_send_message(channel, '**Restarting...**')
            await self.backup_config(self.server_index)
            await self.logout()
        return

    async def cmd_remind(self, author, server):
        """
        Usage: {command_prefix}remind
        Sends a reminder to register to all nonregistered servers
        """
        if author.id == self.config.master_id:
            for server in self.servers:
                if server.id not in self.server_index:
                    await self.safe_send_message(server,
                                                 'Hello! Just a reminder from your friendly robo-Moderator that I don\'t have any function'
                                                 ' until someone goes through the registration process with me!\nIf a Moderator with the `{}` permission'
                                                 ' would run the command `{}register`, I can start helping keep things clean!'.format(
                                                         BOT_HANDLER_ROLE, self.config.command_prefix))
            return Response(':thumbsup:', reply=True)
        return

    async def cmd_url(self):
        """
        blahblahblah
        """
        return Response('Here is my OAuth URL!:\n{}'
                        ''.format(discord.utils.oauth_url('170242612425392128', permissions=discord.Permissions.all())),
                        reply=True)

    async def cmd_joinserver(self):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server.
        """
        return Response('I no longer use invites! If you wish to invite me to a server, please use this link:\n{}'
                        ''.format(discord.utils.oauth_url('170242612425392128', permissions=discord.Permissions.all())),
                        reply=True)

    async def on_server_join(self, server):
        if not self.uber_ready: return
        if int(server.id) in self.globalbans or server.id in self.globalbans:
            if server.owner == server.me:
                await self.delete_server(server)
            else:
                await self.leave_server(server)
            print('leaving %s because server blacklisted' % server.name)
            return
        print('joined server "{}" : {}'.format(server.name, server.id))
        try:
            self.ban_dict[server.id] = await self.get_bans(server)
        except:
            print('couldn\'t get ban list')
            self.ban_dict[server.id] = []
        await self.safe_send_message(server.default_channel,
                                     'Hello! I\'m your friendly robo-Moderator and I\'m here to make the lives of everyone easier!'
                                     '\nIf a Moderator with the `{}` permission would run the command `{}register`, I can start helping'
                                     ' keep things clean!'.format( BOT_HANDLER_ROLE, self.config.command_prefix))

    async def on_server_remove(self, server):
        print('Removed from Server: {}'.format(server.name))

    async def on_member_update(self, before, after):
        if not self.uber_ready: return
        await self.user_index_check(before)
        if before.name != after.name:
            await self.do_server_log(before=before, after=after, log_flag='name')
            if after.name not in self.user_dict[before.id]['names']:
                self.user_dict[before.id]['names'].append(after.name)
        if before.avatar != after.avatar:
            # await self.do_server_log(before=before, after=after, log_flag='avatar')
            pass
        if before.nick != after.nick:
            await self.do_server_log(before=before, after=after, log_flag='nickname')
        if before.roles != after.roles:
            for role_ids in list(self.slow_mode_dict.keys()):
                if [role.id for role in before.roles if role.id in role_ids] or [role.id for role in after.roles if role.id in role_ids]:
                    return
            await self.do_server_log(before=before, after=after, log_flag='role')

    async def on_message_edit(self, before, after):
        if not self.uber_ready: return
        await self.user_index_check(before.author)
        if before.channel.is_private:
            return
        if before.content == after.content:
            return
        if before.author.id == self.user.id:
            return
        if before.server.id in self.server_index and 'LURK' in self.server_index[before.server.id]:
            return
        await self.do_server_log(before=before, after=after, log_flag='edit')
        await self.on_message(after, flag=True)

    async def on_message_delete(self, message):
        if not self.uber_ready: return
        if message.channel.is_private:
            return
        if message.server.id in self.server_index and 'LURK' in self.server_index[message.server.id]:
            return
        await self.do_server_log(message=message, log_flag='delete')

    async def on_member_remove(self, member):
        if not self.uber_ready: return
        if member.server.id in self.server_index and 'LURK' in self.server_index[member.server.id]:
            return
        try:
            if member in self.ban_dict[member.server.id]:
                return
            await self.do_server_log(self, member=member, log_flag='remove')
        except:
            pass

    async def on_member_ban(self, member):
        if not self.uber_ready: return
        await self.user_index_check(member)
        self.ban_dict[member.server.id].append(member)
        if member.id in self.user_dict:
            self.user_dict[member.id]['severs_banned_in'] += 1
        if member.server.id in self.server_index and 'LURK' in self.server_index[member.server.id]:
            return
        await self.do_server_log(self, member=member, log_flag='ban')

    async def on_member_unban(self, server, user):
        if not self.uber_ready: return
        if user.id in self.user_dict:
            self.user_dict[user.id]['severs_banned_in'] -= 1
        if server.id in self.server_index and 'LURK' in self.server_index[server.id]:
            return
        await self.do_server_log(self, member=user, log_flag='unban', server=server)

    async def user_index_check(self, member):
        if member.id not in self.user_dict:
            self.user_dict[member.id] = {'names': [member.name],
                                         'avatar_changes': 0,
                                         'actions_taken_against': 0,
                                         'severs_banned_in': 0}
            try:
                for banlist in self.ban_dict:
                    for user in banlist:
                        if member.id == user.id:
                            self.user_dict[member.id]['severs_banned_in'] += 1
            except:
                pass

    async def on_member_join(self, member):
        if not self.uber_ready: return
        await self.user_index_check(member)
        if member.server.id in self.server_index and 'LURK' in self.server_index[member.server.id]:
            return
        await self.do_server_log(self, member=member, log_flag='join')

    async def on_message(self, message, flag=None):
        if message.author.id in [self.user.id, '159985870458322944']:
            return

        if message.channel.id == '209607650768453633':
            print('pong')
            await self.send_message(message.channel, 'pong')

        if not self.uber_ready: return

        if message.channel.type == discord.ChannelType.group:
            return
        if message.channel.type == discord.ChannelType.private:
            if message.author.id in SHITTY_BOT_IDS:  # Holy Shit Fuck Auto Moderator so hard
                return
            print('pm')
            self.action_dict['messages_processed'] += 1
            if message.author.id in self.register_instances:
                register_instance = self.register_instances[message.author.id]

                message_content = message.content.strip()
                args = message_content.rsplit(sep=', ')
                args = list(filter(None, args))

                response = await register_instance.do_next_step(args)
                if response and isinstance(response, Response):
                    if response.pm:
                        await self.safe_send_message(message.author, response.content)

                    if response.trigger:
                        print('Registration Completed by: {}'.format(message.author.name))
                        this_server = register_instance.server
                        self.server_index[register_instance.server.id] = register_instance.return_server_config()
                        del self.register_instances[message.author.id]
                        try:
                            for this_id in self.banonjoin:
                                await self.http.ban(str(this_id), this_server.id, 7)
                        except:
                            print('Cannot ban the ban on joins on "%s"' % this_server.name)
                    return
            elif message.author.id in self.pmlist:
                return
            else:
                await self.safe_send_message(message.author, 'You cannot use this bot in private messages. If you wish '
                                                             'to invite me to a server, please use this link:\n%s'
                                             % discord.utils.oauth_url('170242612425392128', permissions=discord.Permissions.all()))
                self.pmlist.append(message.author.id)
            return

        if message.mention_everyone:
            self.action_dict['at_everyones'] += 1

        if message.server.id in self.server_index and 'LURK' in self.server_index[message.server.id]:
        #     if message.author.id == self.config.master_id and message.content.startswith('{}eval'.format(self.config.command_prefix)):
        #         result = None
        #         try:
        #             result = eval(message.content[len('{}eval'.format(self.config.command_prefix))+1:])
        #         except Exception:
        #             formatted_lines = traceback.format_exc().splitlines()
        #             await self.safe_send_message(message.channel, '```py\n{}\n{}\n```'.format(formatted_lines[-1], '/n'.join(formatted_lines[4:-1])))
        #
        #         if asyncio.iscoroutine(result):
        #             result = await result
        #
        #         if result:
        #             await self.safe_send_message(message.channel, '```{}```'.format(result))
        #         else:
        #             await self.safe_send_message(message.channel, ':thumbsup:'.format(result))
        #
        #     if message.author.id == self.config.master_id and message.content.startswith('{}exec'.format(self.config.command_prefix)):
        #         old_stdout = sys.stdout
        #         redirected_output = sys.stdout = StringIO()
        #
        #         try:
        #             exec(message.content[len('{}exec'.format(self.config.command_prefix))+1:])
        #         except Exception:
        #             formatted_lines = traceback.format_exc().splitlines()
        #             await self.safe_send_message(message.channel, '```py\n{}\n{}\n```'.format(formatted_lines[-1], '\n'.join(formatted_lines[4:-1])))
        #         finally:
        #             sys.stdout = old_stdout
        #
        #         if redirected_output.getvalue():
        #             await self.safe_send_message(message.channel, redirected_output.getvalue())
        #         else:
        #             await self.safe_send_message(message.channel,':thumbsup:')
        #
        #     if message.content.startswith('{}info'.format(self.config.command_prefix)):
        #         await self.safe_send_message(message.channel,
        #                                      'I was coded by SexualRhinoceros and am currently on v{} ! \nFor info on how to get my in your server, check out this link! '
        #                                      '{}'.format(VERSION, DOCUMENTATION_FOR_BOT), expire_in=30)
        #     if message.content.startswith('{}donate'.format(self.config.command_prefix)):
        #         await self.safe_send_message(message.channel,
        #                                      'Thanks for considering donating! Check out the Patreon here\n\t{}'.format(
        #                                              RHINO_PATREON), expire_in=30)
        #     if message.content.startswith('{}url'.format(self.config.command_prefix)):
        #         await self.safe_send_message(message.channel,
        #                                      'Here is my OAuth URL!:\n\n%s'
        #                                      '' % discord.utils.oauth_url('170242612425392128',
        #                                                                   permissions=discord.Permissions.all()),
        #                                      expire_in=30)
        #
        #     if message.content.startswith('{}userinfo'.format(self.config.command_prefix)):
        #         try:
        #             user = None
        #             join_str = None
        #             message_content = message.clean_content[1 + len('{}userinfo'.format(self.config.command_prefix)):]
        #             if message.mentions:
        #                 user = message.mentions[0]
        #                 join_str = user.joined_at.strftime("%c")
        #             elif not message.mentions and message_content:
        #                 if discord.utils.get(message.server.members, name=message_content):
        #                     user = discord.utils.get(message.server.members, name=message_content)
        #                     join_str = user.joined_at.strftime("%c")
        #                 elif discord.utils.get(message.server.members, id=message_content):
        #                     user = discord.utils.get(message.server.members, id=message_content)
        #                     join_str = user.joined_at.strftime("%c")
        #                 if not user:
        #                     join_str = 'NOT IN SERVER'
        #                     for servers in self.servers:
        #                         if discord.utils.get(servers.members, name=message_content):
        #                             user = discord.utils.get(servers.members, name=message_content)
        #                         elif discord.utils.get(servers.members, id=message_content):
        #                             user = discord.utils.get(servers.members, id=message_content)
        #             elif not message_content:
        #                 user = message.author
        #                 join_str = user.joined_at.strftime("%c")
        #             if not user:
        #                 raise CommandError('Could not find user info on "%s"' % message_content)
        #             await self.user_index_check(user)
        #             await self.safe_send_message(message.channel,
        #                     '```​          User: {}\n         Names: {}\n       Discrim: {}\n            ID: {}\n    Created At'
        #             ': {}\n        Joined: {}\n     # of Bans: {}\n   Infractions: {}\nShared Servers: {}\n        Avatar: {} \n```'.format(
        #                     clean_string(user.name), clean_string(', '.join(self.user_dict[user.id]['names'][-20:])),
        #                     user.discriminator, user.id,
        #                     snowflake_time(user.id).strftime("%c"), join_str,
        #                     self.user_dict[user.id]['severs_banned_in'],
        #                     self.user_dict[user.id]['actions_taken_against'],
        #                     len([servers for servers in self.servers if discord.utils.get(servers.members,
        #                                                                                              id=user.id)]),
        #                     clean_string(user.avatar_url)
        #                     )
        #             )
        #         except CommandError as e:
        #             await self.safe_send_message(message.channel, '```\n%s\n```' % e.message)
        #
        #     if message.content.startswith('{}stats'.format(self.config.command_prefix)):
        #         info_dict = {
        #             'servers': 0,
        #             'members': 0,
        #             'actionstaken': self.action_dict['actions_taken'],
        #             'starttime': datetime.utcnow() - self.start_time,
        #             'commandsran': self.action_dict['commands_ran'],
        #             'messagesdeleted': self.action_dict['messages_deleted'],
        #             'messagesprocessed': self.action_dict['messages_processed'],
        #             'messagessent': self.action_dict['messages_sent'],
        #             'ateveryones': self.action_dict['at_everyones']
        #         }
        #         for server in self.servers:
        #             info_dict['servers'] += 1
        #             for member in server.members:
        #                 info_dict['members'] += 1
        #
        #         await self.safe_send_message(message.channel,
        #                                      'I have been running continuously for **{}**!\nI\'m currently in **{}** servers and can see '
        #                                      '**{}** members in those servers.\n\nSince starting, I have seen **{}** messages, automatically taken **{}** moderation'
        #                                      ' actions, sent **{}** messages, deleted **{}** messages, have had **{}** commands ran, and seen @\u200beveryone used **{}** times!'
        #                                      '\n\n To get me on your server, PM me an invite link or go to **https://www.carbonitex.net/'
        #                                      'discord/bots?rhino**'
        #                                      ''.format(strfdelta(info_dict['starttime']), info_dict['servers'],
        #                                                info_dict['members'],
        #                                                info_dict['messagesprocessed'], info_dict['actionstaken'],
        #                                                info_dict['messagesdeleted'], info_dict['messagessent'],
        #                                                info_dict['commandsran'],
        #                                                info_dict['ateveryones']),
        #                                      expire_in=60)
            return
        if self.user in message.mentions:
            print('[{} : {}]{} says \'{}\''.format(message.server.name, message.channel.name, message.author.name,
                                                   message.clean_content))

        perm_check = False
        for role in message.server.me.roles:
            perms = role.permissions
            if perms.administrator:
                perm_check = True

        if not perm_check and message.server.id in self.server_index:
            return

        self.action_dict['messages_processed'] += 1
        message_content = message.content.strip()
        if message_content.startswith(self.config.command_prefix):
            try:
                command, *args = shlex.split(message_content)
            except ValueError:
                await self.safe_send_message(message.channel,
                                             '```\nNo closing quote detected in message : {}\n```'.format(
                                                     message.server.name))
                return

            for arg in list(args):
                if arg.startswith('<@'):
                    args.remove(arg)
                if arg.startswith('<#'):
                    pos = args.index(arg)
                    arg = arg.replace('<#', '').replace('>', '')
                    args[pos] = arg

            command = command[len(self.config.command_prefix):].lower().strip()

            handler = getattr(self, 'cmd_%s' % command, None)
            for register_instance in self.register_instances.values():
                if register_instance.server.id == message.server.id:
                    await self.safe_send_message(message.channel,
                                                 'You cannot use the bot until it has been set up. <@{}> is in the process of'
                                                 ' configuring AutoModerator!'.format(register_instance.user.id))
                    return
            if handler:
                argspec = inspect.signature(handler)
                params = argspec.parameters.copy()

                try:
                    handler_kwargs = {}
                    if params.pop('message', None):
                        handler_kwargs['message'] = message

                    if params.pop('channel', None):
                        handler_kwargs['channel'] = message.channel

                    if params.pop('author', None):
                        handler_kwargs['author'] = message.author

                    if params.pop('server', None):
                        handler_kwargs['server'] = message.server

                    if params.pop('mentions', None):
                        handler_kwargs['mentions'] = message.mentions

                    if params.pop('leftover_args', None):
                        handler_kwargs['leftover_args'] = args


                    args_expected = []
                    for key, param in list(params.items()):
                        doc_key = '[%s=%s]' % (
                            key, param.default) if param.default is not inspect.Parameter.empty else key
                        args_expected.append(doc_key)

                        if not args and param.default is not inspect.Parameter.empty:
                            params.pop(key)
                            continue

                        if args:
                            arg_value = args.pop(0)
                            handler_kwargs[key] = arg_value
                            params.pop(key)

                    if params:
                        return
                    try:
                        response = await handler(**handler_kwargs)
                        self.action_dict['commands_ran'] += 1
                    except discord.DiscordException as e:
                        response = None
                        print(
                                'Exception on {}({}) in channel {}\n\t{}'.format(message.server.name, message.server.id,
                                                                                 message.channel.name,
                                                                                 traceback.format_exc()))
                    if response and isinstance(response, Response):
                        content = response.content
                        if response.ignore_flag:
                            return
                        if response.pm:
                            route = message.author
                        if response.reply:
                            content = '%s, %s' % (message.author.mention, content)
                            route = message.channel
                        try:
                            await self.safe_send_message(route, content)
                        except:
                            pass

                        if response.delete_incoming is True:
                            await self.safe_delete_message(message)


                except CommandError as e:
                    await self.safe_send_message(message.channel, '```\n%s\n```' % e.message)

                except:
                    await self.safe_send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
                    traceback.print_exc()
            if not flag:
                await self.do_server_log(message=message)
        if message.server.id not in self.server_index:
            return
        elif message.channel.id in self.server_index[message.server.id][12]:
            return
        elif not await self.is_checked(message.author, message.server):
            if not flag:
                await self.do_server_log(message=message)
            return
        elif await self.is_long_member(message.author.joined_at, message.server):
            if self.server_index[message.server.id][10][2] is True:
                for emote in self.emote_list:
                    if emote in message.clean_content.lower():
                        await self.safe_delete_message(message)
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    '*twitch emote* ***{}*** *detected*```{}```'.format(emote,
                                                                                                        message.clean_content[
                                                                                                        :150]),
                                                    message.channel)
                        self.action_dict['twitch_memes_killed'] += 1
                        self.action_dict['actions_taken'] += 1
                        return
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                this = config[11][message.author.id]
                now = datetime.utcnow()
                dis = await self.limit_post(message.author, message.server, message.content, limit_post_flag=flag)
                if dis > 0:
                    await self.safe_delete_message(message)
                    this[3] += 1
                    self.action_dict['actions_taken'] += 1
                    if this[3] > 5:
                        action = self.server_index[message.server.id][6]
                        if 'kick' in action:
                            await self._write_to_modlog('kicked', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            try:
                                await self.kick(message.author)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been kicked for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot kick, no permissions : {}'.format(message.server.name))
                        elif 'ban' in action:
                            await self._write_to_modlog('banned', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            try:
                                await self.ban(message.author, 7)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been banned for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot ban, no permissions : {}'.format(message.server.name))
                        elif 'mute' in action:
                            await self._write_to_modlog('muted', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            mutedrole = discord.utils.get(message.server.roles, name='Muted')
                            try:
                                await self.add_roles(message.author, mutedrole)
                                await self.server_voice_state(message.author, mute=True)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been muted for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot mute, no permissions : {}'.format(message.server.name))
                        else:
                            await self._write_to_modlog('flagged', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                        return
                    if dis is 1:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    '*duplicate message detected*```{}```'.format(
                                                            message.clean_content[:150]), message.channel)
                    elif dis is 2:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    '*spam-esque duplicate characters detected*```{}```'.format(
                                                            message.clean_content[:150]), message.channel)
                    else:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    '*rate limiting*```{}```'.format(message.clean_content[:150]),
                                                    message.channel)
                    this[0] = now
                else:
                    if not flag:
                        await self.do_server_log(message=message)
                this[2].append(do_slugify(message.content))
                self.server_index[message.server.id][11][message.author.id] = this
            else:
                if not flag:
                    await self.do_server_log(message=message)
                this = [datetime.utcnow(), config[1] + 2, [message.content], 0]
                self.server_index[message.server.id][11][message.author.id] = this
        else:
            if self.server_index[message.server.id][10][2] is True:
                for emote in self.emote_list:
                    if emote in message.clean_content.lower():
                        await self.safe_delete_message(message)
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    '*twitch emote* **{}** *detected*```{}```'.format(emote,
                                                                                                      message.clean_content[
                                                                                                      :150]),
                                                    message.channel)
                        self.action_dict['twitch_memes_killed'] += 1
                        self.action_dict['actions_taken'] += 1
                        return
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                dis = await self.strict_limit_post(message.author, message.server, message.content, limit_post_flag=flag)
                if dis > 0:
                    await self.safe_delete_message(message)
                    config[11][message.author.id][3] += 1
                    self.action_dict['actions_taken'] += 1
                    if config[11][message.author.id][3] > 3:
                        action = self.server_index[message.server.id][6]
                        if 'kick' in action:
                            await self._write_to_modlog('kicked', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            try:
                                await self.kick(message.author)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been kicked for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot kick, no permissions : {}'.format(message.server.name))
                        elif 'ban' in action:
                            await self._write_to_modlog('banned', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            try:
                                await self.ban(message.author, 7)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been banned for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot ban, no permissions : {}'.format(message.server.name))
                        elif 'mute' in action:
                            await self._write_to_modlog('muted', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                            mutedrole = discord.utils.get(message.server.roles, name='Muted')
                            try:
                                await self.add_roles(message.author, mutedrole)
                                await self.server_voice_state(message.author, mute=True)
                                await self.safe_send_message(message.author,
                                                             'You\'ve been muted for multiple violations of anti spam filters on `{}`!'.format(
                                                                     message.server.name))
                            except:
                                print('Cannot mute, no permissions : {}'.format(message.server.name))
                        else:
                            await self._write_to_modlog('flagged', message.author, message.server,
                                                        'multiple violations of anti spam filters', message.channel)
                        return
                    if dis is 1:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    'duplicate message detected```{}```'.format(
                                                            message.clean_content[:150]), message.channel)
                    elif dis is 2:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    'spam-esque duplicate characters detected```{}```'.format(
                                                            message.clean_content[:150]), message.channel)
                    else:
                        await self._write_to_modlog('deleted the message of ', message.author, message.server,
                                                    'rate limiting```{}```'.format(message.clean_content[:150]),
                                                    message.channel)
                else:
                    if not flag:
                        await self.do_server_log(message=message)
                this = config[11][message.author.id]
                this[0] = datetime.utcnow()
                this[2].append(do_slugify(message.content))
                self.server_index[message.server.id][11][message.author.id] = this
            else:
                if not flag:
                    await self.do_server_log(message=message)
                this = [datetime.utcnow(), config[1], [message.content], 0]
                self.server_index[message.server.id][11][message.author.id] = this

        max_word_length = 0
        for words in self.server_index[message.server.id][5]:
            if len(words) > max_word_length:
                max_word_length = len(words)
        if max_word_length > 4:
            max_word_length = 4
        for words in self.server_index[message.server.id][5]:
            if len(message.content) < max_word_length:
                return
            is_similar = False
            if await self.is_long_member(message.author.joined_at, message.server):
                if compare_strings(words, do_slugify(message.content)) > OLD_MEM_SIMILARITY_PCT:
                    is_similar = True
            else:
                if strict_compare_strings(words, do_slugify(message.content)) > NEW_MEM_SIMILARITY_PCT:
                    is_similar = True

            if is_similar or words in do_slugify(message.content):
                action = self.server_index[message.server.id][6]
                if 'kick' in action:
                    try:
                        await self.delete_message(message)
                        await self.kick(message.author)
                        await self.safe_send_message(message.author,
                                                     'Your message `{}` has been deleted and you\'ve been kicked for breaking the word filter on `{}`!'.format(
                                                             message.clean_content, message.server.name))
                        await self._write_to_modlog('kicked', message.author, message.server,
                                                    'the use of a blacklisted word : `{}`'.format(
                                                            message.clean_content), message.channel)
                    except discord.Forbidden:
                        print('Cannot kick, no permissions : {}'.format(message.server.name))
                    except:
                        pass
                elif 'ban' in action:
                    try:
                        await self.delete_message(message)
                        await self.ban(message.author, 7)
                        await self.safe_send_message(message.author,
                                                     'Your message `{}` has been deleted and you\'ve been banned for breaking the word filter on `{}`!'.format(
                                                             message.clean_content, message.server.name))
                        await self._write_to_modlog('banned', message.author, message.server,
                                                    'the use of a blacklisted word : `{}`'.format(
                                                            message.clean_content), message.channel)
                    except discord.Forbidden:
                        print('Cannot ban, no permissions : {}'.format(message.server.name))
                    except:
                        pass
                    return
                elif 'mute' in action:
                    mutedrole = discord.utils.get(message.server.roles, name='Muted')
                    try:
                        await self.delete_message(message)
                        await self.add_roles(message.author, mutedrole)
                        await self.server_voice_state(message.author, mute=True)
                        # self.server_index[message.server.id][13][message.author.id] = [0, None]
                        await self.safe_send_message(message.author,
                                                     'Your message `{}` has been deleted and you\'ve been muted for breaking the word filter on `{}`!'.format(
                                                             message.clean_content, message.server.name))
                        await self._write_to_modlog('muted', message.author, message.server,
                                                    'the use of a blacklisted word : `{}`'.format(
                                                            message.clean_content), message.channel)
                    except discord.Forbidden:
                        print('Cannot mute, no permissions : {}'.format(message.server.name))
                    except:
                        pass
                elif 'nothing' in action:
                    try:
                        await self.delete_message(message)
                        await self.safe_send_message(message.author,
                                                     'Your message `{}` has been deleted for breaking the word filter on `{}`!'.format(
                                                             message.clean_content, message.server.name))
                        await self._write_to_modlog('deleted', message.author, message.server,
                                                    'the use of a blacklisted word : `{}`'.format(
                                                            message.clean_content), message.channel)
                    except:
                        pass
                else:
                    return
                self.action_dict['actions_taken'] += 1
        if message.channel.id in list(self.slow_mode_dict.keys()):
            time_out = self.slow_mode_dict[message.channel.id]['time_between']
            channel_muted_role = self.slow_mode_dict[message.channel.id]['channel_muted_role']
            await self.add_roles(message.author, *[channel_muted_role])
            self.action_dict['seconds_slowed'] += time_out
            await asyncio.sleep(time_out)
            await self.remove_roles(message.author, *[channel_muted_role])


if __name__ == '__main__':
    bot = AutoMod()
    bot.run()
