import asyncio
import discord
import traceback
import inspect
import os
import re

from functools import wraps

from fuzzywuzzy import fuzz
from datetime import datetime, timedelta

from automod.config import Config
from automod.register import Register
from automod.response import Response
from automod.version import VERSION
from automod.utils import load_json, extract_user_id, write_json, load_file, write_file, compare_strings, do_slugify

from .exceptions import CommandError
from .constants import BOT_HANDLER_ROLE, RHINO_SERVER, RHINO_SERVER_CHANNEL

def backup_config(server_config_list):
    for key, current_config in server_config_list.items():
        current_config[11] = {}
        savedir = 'configs\\'+str(key)
        if not os.path.exists(savedir):
            os.makedirs(savedir)
        savedir += '\\config.json'
        write_json(savedir, current_config)

def sleep_decorator(timer):
    def func_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            yield from asyncio.sleep(timer)
            print('BACKING UP JSON')
            return func(*args, **kwargs)
        return wrapper
    return func_wrapper

class AutoMod(discord.Client):
    def __init__(self, config_file='config/options.txt'):
        super().__init__()
        self.config = Config(config_file)

        self.register_instances = {}
        self.user_invite_dict = {}
        self.globalbans = set(map(int, load_file(self.config.globalbans_file)))

        self.server_index = self.load_configs()

    # noinspection PyMethodOverriding
    def run(self):
        return super().run(self.config.username, self.config.password)

    def load_configs(self):
        server_index = {}
        for root, dirs, files in os.walk('configs', topdown=False):
            for name in dirs:
                fullname = os.path.join(name, 'config.json')
                fileroute = os.path.join(root, fullname)
                server_index[name] = load_json(fileroute)
        return server_index

    def has_roles(self, user, check_server, register=False):
        if register is False:
            if check_server.id not in self.server_index:
                return
        if len(check_server.roles) != 1:
            try:
                for role in user.roles:
                    if role.id in self.server_index[check_server.id][14] or user.id in self.server_index[check_server.id][15] or role.name.lower() == BOT_HANDLER_ROLE.lower():
                        return True
            except:
                return False
        else:
            raise CommandError('No roles detected on server {}'.format(check_server.name))

    def is_checked(self, user, server):
        for role in user.roles:
            if server.id in self.server_index:
                if role.name in self.server_index[server.id][3] or user.id in self.server_index[server.id][4]:
                    return False
        return True

    def is_long_member(self, date_joined, server):
        if server.id not in self.server_index:
            return
        config = self.server_index[server.id]
        try:
            today = datetime.utcnow()
            margin = datetime.timedelta(hours=config[7])
            return today - margin > date_joined
        except:
            return False

    def strict_limit_post(self, author, server, content, flg=None):
        config = self.server_index[server.id]
        author_index = config[11][author.id]
        last_post_time = author_index[0]
        last_timeframe_content = author_index[2]
        now = datetime.utcnow()

        match2 = re.split("[\n]{4,}", content)
        match = re.split(r"(.)\1{9,}", content)

        if len(match) > 1 or len(match2) > 1:
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            return True

        content = do_slugify(content)

        match2 = re.split("[\n]{4,}", content)
        match = re.split(r"(.)\1{9,}", content)

        if len(match) > 1 or len(match2) > 1:
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            return True

        if now - last_post_time < timedelta(minutes=10 and not flg):
            for last_content in last_timeframe_content:
                if compare_strings(last_content, content) > 70:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return True

        if now - last_post_time < timedelta(seconds=config[2]):
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            if author_index[1] <= 0:
                return True
        else:
            author_index[1] = config[1]
            author_index[2] = []
        self.server_index[server.id][11][author.id] = author_index
        return False

    def limit_post(self, author, server, content, flg=None):
        config = self.server_index[server.id]
        author_index = config[11][author.id]
        last_post_time = author_index[0]
        last_timeframe_content = author_index[2]
        now = datetime.utcnow()

        match2 = re.split("[\n]{4,}", content)
        match = re.split(r"(.)\1{9,}", content)

        if match or match2:
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            return True

        content = do_slugify(content)
        if now - last_post_time < timedelta(minutes=10 and not flg):
            for last_content in last_timeframe_content:
                if compare_strings(last_content, content) > 80:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return True

        if now - last_post_time < timedelta(seconds=config[2]-1):
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            if author_index[1] <= 0:

                return True
        else:
            author_index[0] = now
            author_index[1] = config[1]+2
            author_index[2] = []
        self.server_index[server.id][11][author.id] = author_index
        return False

    async def on_ready(self):
        print('Connected!\n')
        print('Username: ' + self.user.name)
        print('ID: ' + self.user.id)
        print('--Server List--')
        for server in self.servers:
            print(server.name+' : '+server.id)
            # if server.id in self.server_index:
            #     self.server_index[server.id][0] = self.get_bans(server)
        print()
        self.backup_list()

    @sleep_decorator(86400)
    async def server_timer(self, server):
        if server.id not in self.server_index:
            await self.leave_server(server)
            print('{} timed out after 24 hours')

    @sleep_decorator(1800)
    async def backup_list(self):
        backup_config(self.server_index)
        await self.backup_list()

    async def write_to_modlog(self, message, author, server, reason):
        if server.id in self.server_index:
            config = self.server_index[server.id]
        else:
            return
        if not config[8] or not config[10]:
            return
        if not reason:
            reason = "***No Reason Specified***"
        await self.send_message(discord.Object(id=config[8]), 'At *{}*, **{}** has used the command ```{}```Reason: `{}`'
                                                              ''.format(datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"), author, message.content, reason))

    async def _write_to_modlog(self, autoaction, offender, server, reason):
        if server.id in self.server_index:
            config = self.server_index[server.id]
        else:
            return
        if not config[8] or not config[10]:
            return
        if not reason:
            reason = "***No Reason Specified***"
        await self.send_message(discord.Object(id=config[8]), 'At *{}*, I automatically {} **{}** for {}'
                                                              ''.format(datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"), autoaction, offender, reason))

    # TODO: Make this good code that is mine, not stuff taken from old pre async branch code written by @Sharpwaves
    async def do_server_log(self, message=None, flag=None, member=None, before=None, after=None):
        if message and not flag:
            if message.server.id in self.server_index:
                config = self.server_index[message.server.id]
            else:
                return
            if message.channel.id in config[12]:
                return
            if not config[9]:
                return
            channel_trimmed = message.channel.name.upper()[:10]
            if len(message.content) > 1800:
                msg = '**__{0}|__ {1}:** {2}'.format(channel_trimmed, message.author.name, message.content)
                split = [msg[i:i+1800] for i in range(0, len(msg), 1800)]
                for x in split:
                    await self.send_message(discord.Object(id=config[9]), x)
            else:
                try:
                    msg = '**__{0}|__ {1} uploaded an attachment:** {2}'.format(channel_trimmed, message.author.name, message.attachments[0]['url'])
                    await self.send_message(discord.Object(id=config[9]), msg)
                except:
                    pass
                if message.content != '':
                    msg = '**__{0}|__ {1}:** {2}'.format(channel_trimmed, message.author.name, message.content)
                    await self.send_message(discord.Object(id=config[9]), msg)
        elif flag:
            if flag == 'join':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not config[9]:
                    return
                await self.send_message(discord.Object(id=config[9]), '**++++++++++++++++++++++++**\n**{} '
                                                                      'JOINED THE SERVER**\n**++++++++++++++++++++++++'
                                                                      '**'.format(member.name.upper()))
            elif flag == 'remove':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not config[9]:
                    return
                await self.send_message(discord.Object(id=config[9]), '**--------------------------------------**'
                                                                      '\n**{} LEFT THE SERVER**\n**'
                                                                      '--------------------------------------**'
                                                                      ''.format(member.name.upper()))
            elif flag == 'edit':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if before.channel.id in config[12]:
                    return
                if not config[9]:
                    return
                if before.content != after.content:
                    channel_trimmed = after.channel.name.upper()[:10]
                    if (len(before.content) + len(after.content)) > 1800:
                        msg = '**__{0}|__ {1} edited their message**\n**Before:** {2}\n**+After:** {3}'.format(channel_trimmed, after.author.name, before.content, after.content)
                        split = [msg[i:i+1800] for i in range(0, len(msg), 1800)]
                        for x in split:
                            await self.send_message(discord.Object(id=config[9]), x)
                    else:
                        msg = '**__{0}|__ {1} edited their message**\n**Before:** {2}\n**+After:** {3}'.format(channel_trimmed, after.author.name, before.content, after.content)
                        await self.send_message(discord.Object(id=config[9]), msg)
            elif flag == 'delete':
                if message.server.id in self.server_index:
                    config = self.server_index[message.server.id]
                else:
                    return
                if message.channel.id in config[12] or message.content == '':
                    return
                if not config[9]:
                    return
                channel_trimmed = message.channel.name.upper()[:10]
                if len(message.content) > 1800:
                    msg = '**__{0}|__ {1} deleted their message:** {2}'.format(channel_trimmed, message.author.name, message.content)
                    split = [msg[i:i+1800] for i in range(0, len(msg), 1800)]
                    for x in split:
                        await self.send_message(discord.Object(id=config[9]), x)
                else:
                    if message.content != '':
                        msg = '**__{0}|__ {1} deleted their message:** {2}'.format(channel_trimmed, message.author.name, message.content)
                        await self.send_message(discord.Object(id=config[9]), msg)

    async def handle_register(self, message, author, server):
        """
        Usage: {command_prefix}register
        If the user who starts the registration has the `AutoManager` role, start the registration process.
        """
        if self.has_roles(author, server, register=True):
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
                return await register.do_next_step()
            else:
                return Response('there is an existing registration instance for your server started by {}'.format(
                        error_response
                ),
                        reply=True
                )

    async def handle_mute(self, message, server, author, username, time=None, reason=None):
        """
        Usage: {command_prefix}mute @UserName <time> <reason>
        Mute the user indefinitley unless given a time, then only mute till the time is up
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            if time and not reason and not time.isdigit():
                reason = time
                time = None
            await self.write_to_modlog(message, author, server, reason)
            asshole = discord.utils.get(server.members, id=str(user_id))
            mutedrole = discord.utils.get(server.roles, name='Muted')
            if not mutedrole:
                raise CommandError('No Muted role created')
            try:
                await self.add_roles(asshole, mutedrole)
            except:
                raise CommandError('Unable to mute user defined:\n{}\n'.format(username))
            if time:
                await asyncio.sleep(float(time))
                muteeroles = asshole.roles
                if mutedrole in muteeroles:
                    muteeroles.remove(mutedrole)
                await self.replace_roles(asshole, *muteeroles)

    async def handle_unmute(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}unmute @UserName <reason>
        Unmutes the user defined.
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            reformedDick = discord.utils.get(server.members, id=str(user_id))
            mutedrole = discord.utils.get(server.roles, name='Muted')
            muteeroles = reformedDick.roles
            if mutedrole in muteeroles:
                muteeroles.remove(mutedrole)
            try:
                await self.replace_roles(reformedDick, *muteeroles)
            except:
                raise CommandError('Unable to unmute user defined:\n{}\n'.format(username))

    async def handle_addrole(self, message, author, server, username, rolename, reason=None):
        """
        Usage: {command_prefix}addroles @UserName <role name> <reason>
        Assigns the user the roles defined
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            user = discord.utils.get(server.members, id=str(user_id))
            role = discord.utils.get(server.roles, name=rolename)
            if not role:
                raise CommandError('No role named `{}` exists!'.format(rolename))
            try:
                await self.add_roles(user, role)
            except:
                raise CommandError('Unable to assign {} the role `{}`'.format(username, rolename))

    async def handle_removerole(self, message, author, server, username, rolename, reason=None):
        """
        Usage: {command_prefix}removerole @UserName <role name> <reason>
        Removes the role defined from the user
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            user = discord.utils.get(server.members, id=str(user_id))
            role = discord.utils.get(server.roles, name=rolename)
            stopdroprole = user.roles
            if role in stopdroprole:
                stopdroprole.remove(role)
            try:
                await self.replace_roles(user, *stopdroprole)
            except:
                raise CommandError('Unable remove the role `{}` from user {}'.format(rolename, username))

    async def handle_purge(self, message, author, server, channel, count, username=None, reason=None):
        """
        Usage: {command_prefix}purge <# to purge> @UserName <reason>
        Removes all messages from chat unless a user is specified;
        then remove all messages by the user.
        """
        if self.has_roles(author, server):
            if username and not reason and not username.startswith('<@'):
                reason = username
                username = None
            await self.write_to_modlog(message, author, server, reason)
            if not username:
                logs = await self.logs_from(channel, int(count))
                for msg in logs:
                    await self.delete_message(msg)
            else:
                user_id = extract_user_id(username)
                if not user_id:
                    raise CommandError('Invalid user specified')
                culprit = discord.utils.get(server.members, id=str(user_id))
                logs = await self.logs_from(channel)
                for msg in logs:
                    if msg.author.id == culprit.id:
                        await self.delete_message(msg)
        # ALLOWS USERS TO REMOVE THEIR MESSAGES EVEN IF THEY AREN'T A MOD
        # elif not username:
        #     logs = await self.logs_from(channel, int(count))
        #     for msg in logs:
        #         if msg.author == author:
        #             await self.delete_message(msg)

    async def handle_ban(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}ban @UserName <reason>
        Bans the user from the server and removes 7 days worth of their messages
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            member = discord.utils.get(server.members, id=str(user_id))
            self.ban(member, 7)

    async def handle_kick(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}kick @Username <reason>
        Kicks the user from the server.
        """
        if self.has_roles(author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            member = discord.utils.get(server.members, id=str(user_id))
            self.kick(member)

    async def handle_whitelist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}whitelist <@UserName / role> <reason>
        Adds the user or role to the whitelist so they're ignored by the filters.
        """
        if self.has_roles(author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                config[4].append(user_id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    config[3].append(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_blacklist(self, message, author, server, string_arg, reason=None):
        """
        Usage: {command_prefix}blacklist <string> <reason>
        Adds the specified word / words (string) to the blacklist!
        """
        if self.has_roles(author, server):
            config = self.server_index[server.id]
            config[5].append(do_slugify(string_arg))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remblacklist(self, message, author, server, string_arg, reason=None):
        """
        Usage: {command_prefix}remblacklist <string> <reason>
        Removes the specified word / words (string) from the blacklist!
        """
        if self.has_roles(author, server):
            config = self.server_index[server.id]
            config[5].remove(do_slugify(string_arg))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remwhitelist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}whitelist <@UserName / role> <reason>
        Removes the user or role from the whitelist so they're no longer ignored by the filters.
        """
        if self.has_roles(author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                config[4].remove(user_id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    config[3].remove(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_unban(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}unban @UserName <reason>
        Unbans a user!
        """
        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')
        await self.write_to_modlog(message, author, server, reason)
        member = discord.utils.get(server.members, id=str(user_id))
        self.unban(server, member)

    async def handle_settokens(self, message, author, server, tokens, reason=None):
        """
        Usage: {command_prefix}settokens <number> <reason>
        Sets the number of tokens a user has to spend in a reset period
        """
        if self.has_roles(author, server):
            try:
                tokens = int(tokens)
            except:
                raise CommandError('Non number detected: {}'.format(tokens))
            if tokens < 1:
                raise CommandError('Cannot use a number less than 1, received : {}'.format(tokens))
            self.server_index[server.id][1]=tokens
            await self.write_to_modlog(message, author, server, reason)

    async def handle_settokenreset(self, message, author, server, time, reason=None):
        """
        Usage: {command_prefix}settokenreset <time in seconds> <reason>
        Sets the time frame in which a user can spend their tokens until they're rate limited
        """
        if self.has_roles(author, server):
            try:
                time = int(time)
            except:
                raise CommandError('Non number detected: {}'.format(time))
            if time < 1:
                raise CommandError('Cannot use a number less than 1, received : {}'.format(time))
            config = self.server_index[server.id]
            config[2] = time
            await self.write_to_modlog(message, author, server, reason)

    async def handle_setpunishment(self, message, author, server, new_punishment, reason=None):
        """
        Usage: {command_prefix}setpunishment <new punishment> <reason>
        Sets the punishment to be used when a blacklisted word is detected
        Only accepts : 'kick', 'ban', 'mute', or 'nothing'
        """
        if self.has_roles(author, server):
            if 'kick' or 'ban' or 'mute' or 'nothing' not in new_punishment:
                raise CommandError('Improper option inputted: {}'.format(config = self.server_index[server.id]))
            config = self.server_index[server.id]
            if new_punishment == config[6]:
                return
            config[6] = new_punishment
            await self.write_to_modlog(message, author, server, reason)

    async def handle_setlongtimemember(self, message, author, server, time, reason=None):
        """
        Usage: {command_prefix}setlongtimemember <time> <reason>
        Sets what the time in hours will be until a user is considered a 'long time memeber' of the server
        and be subjected to less strict filtering.
        """
        if self.has_roles(author, server):
            try:
                time = int(time)
            except:
                raise CommandError('Non number detected: {}'.format(time))
            if time < 0:
                raise CommandError('Cannot use a number less than 0, received : {}'.format(time))
            config = self.server_index[server.id]
            config[7] = time
            await self.write_to_modlog(message, author, server, reason)

    async def handle_setmodlogid(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}setmodlogid <new channel ID> <reason>
        Sets the channel ID of the mod log!
        """
        if self.has_roles(author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(str(new_id)) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[8] = new_id
            await self.write_to_modlog(message, author, server, reason)

    async def handle_setserverlogid(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}setserverlogid <new channel ID> <reason>
        Sets the channel ID of the server log!
        """
        if self.has_roles(author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(str(new_id)) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[9] = new_id
            await self.write_to_modlog(message, author, server, reason)

    async def handle_alertrhino(self, message, author, server, string_arg):
        """
        Usage: {command_prefix}alertrhino "<message>"
        Used to send a message to SexualRhinoceros if the bot isn't working for one reason or another!
        """
        if self.has_roles(author, server):
            inv = await self.create_invite(server, max_uses=3, xkcd=True)
            for servers in self.servers:
                if servers.id == RHINO_SERVER:
                    for channel in servers.channels:
                        if channel.id == RHINO_SERVER_CHANNEL:
                            await self.send_message(channel, 'Help requested by **{}** at *{}* for reason `{}`\n\t{}'
                                                             ''.format(author.name, server.name, string_arg, inv))
                            return Response('Rhino has been alerted!', reply=True)
            pass

    async def handle_help(self, message, author, server, reason=None):
        """
        Usage: {command_prefix}whitelist @UserName
        Adds the user to the whitelist, permitting them to add songs.
        """
        return Response('I\'ve fallen and I can\'t get up!', reply=True)

    async def handle_ignore(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}ignore <channel ID> "<reason>"
        Adds the channel ID to the list of ignored channels when outputting to the server log
        """
        if self.has_roles(author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(new_id) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[12].append(new_id)
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remignore(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}remignore <channel ID> "<reason>"
        Removes the channel ID from the list of ignored channels when outputting to the server log
        """
        if self.has_roles(author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(new_id) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[12].remove(new_id)
            await self.write_to_modlog(message, author, server, reason)

    async def handle_broadcast(self, message, author, server, string_arg):
        """
        Usage: {command_prefix}broadcast "<message>"
        Sends a message to the default channel of all servers the bot is in
        """
        if author.id == self.config.master_id:
            for servers in self.servers:
                await self.send_message(servers, string_arg)
            return Response('its been done', reply=True)
        return

    async def handle_gban(self, message, author, server, username):
        """
        Usage: {command_prefix}gban @Username
        Globally bans a user from using the bot's commands
        """
        if author.id == self.config.master_id:
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            self.globalbans.add(user_id)
            write_file('globalbans.txt', self.globalbans)
            return Response('its been done', reply=True)
        return

    async def handle_id(self, author, server):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        return Response('your id is `%s`' % author.id, reply=True)

    async def handle_forcebackup(self, author):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        if author.id == self.config.master_id:
            backup_config(self.server_index)
            return Response('its been done', reply=True)
        return

    async def handle_changename(self, author, newname):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        if author.id == self.config.master_id:
            try:
                self.edit_profile(password=self.config.password, username=newname)
                return Response('its been done', reply=True)
            except:
                raise CommandError('Could not change name to:\t{}\n'.format(newname))
        return

    async def handle_joinserver(self, message, author, server_link):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """
        try:
            inv = await self.get_invite(server_link)
            self.user_invite_dict[inv.server.id]=  author.id
            await self.accept_invite(server_link)

        except:
            raise CommandError('Invalid URL provided:\n\t{}\n'.format(server_link))

    async def on_server_join(self, server):
        await self.send_message(server.default_channel, 'Hello! I\'m your friendly robo-Moderator and was invited by <@{}> to make the lives of everyone easier!'
                                                        '\nIf a Moderator with a role named `{}` would run the command `{}register`, I can start helping'
                                                        ' keep things clean!'.format(
                                                         self.user_invite_dict[server.id], BOT_HANDLER_ROLE, self.config.command_prefix))
        self.server_timer(server)

    async def on_message_edit(self, before, after):
        if before.author.id == self.user.id:
            return
        await self.on_message(after, flag=True)
        await self.do_server_log(before=before, after=after, flag='edit')

    async def on_message_delete(self, message):
        await self.do_server_log(message=message, flag='delete')

    async def on_member_remove(self, member):
        await self.do_server_log(self, member=member, flag='remove')

    async def on_member_join(self, member):
        await self.do_server_log(self, member=member, flag='join')

    async def on_message(self, message, flag=None):

        if message.author == self.user:
            return

        if message.channel.is_private:
            if message.author.id in self.register_instances:
                register_instance = self.register_instances[message.author.id]

                message_content = message.content.strip()
                args = message_content.rsplit(sep=', ')
                args = list(filter(None, args))

                response = await register_instance.do_next_step(args)
                if response and isinstance(response, Response):
                    if response.pm:
                        await self.send_message(message.author, response.content)

                    if response.trigger:
                        self.server_index[register_instance.server.id] = register_instance.return_server_config()
                        del self.register_instances[message.author.id]
                    return
            else:
                await self.send_message(message.channel, 'You cannot use this bot in private messages.')
            return

        message_content = message.content.strip()
        if message_content.startswith(self.config.command_prefix):
            m = re.search('".+"', message_content)
            str_content = None
            if m:
                str_content = m.group(0)
                message_content = message_content.replace(str_content, '')
                str_content = str_content.replace('"', '')
            command, *args = message_content.split()

            command = command[len(self.config.command_prefix):].lower().strip()

            handler = getattr(self, 'handle_%s' % command, None)
            for register_instance in self.register_instances.values():
                if register_instance.server.id == message.server.id:
                    await self.send_message(message.channel, 'You cannot use the bot until it has been set up. <@{}> is in the process of'
                                                             'configuring AutoModerator!'.format(register_instance.user.id))
                    return
            if not handler:
                return

            argspec = inspect.signature(handler)
            params = argspec.parameters.copy()

            # noinspection PyBroadException
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

                if params.pop('player', None):
                    handler_kwargs['player'] = await self.get_player(message.channel)

                if params.pop('string_arg', None) and str_content:
                    handler_kwargs['string_arg'] = str_content

                args_expected = []
                for key, param in list(params.items()):
                    doc_key = '[%s=%s]' % (key, param.default) if param.default is not inspect.Parameter.empty else key
                    args_expected.append(doc_key)

                    if not args and param.default is not inspect.Parameter.empty:
                        params.pop(key)
                        continue

                    if args:
                        arg_value = args.pop(0)
                        handler_kwargs[key] = arg_value
                        params.pop(key)

                if params:
                    docs = getattr(handler, '__doc__', None)
                    if not docs:
                        docs = 'Usage: {}{} {}'.format(
                                self.config.command_prefix,
                                command,
                                ' '.join(args_expected)
                        )

                    docs = '\n'.join(l.strip() for l in docs.split('\n'))
                    await self.send_message(
                            message.channel,
                            '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix)
                    )
                    return

                response = await handler(**handler_kwargs)
                if response and isinstance(response, Response):
                    content = response.content
                    if response.pm:
                        route = message.author
                    if response.reply:
                        content = '%s, %s' % (message.author.mention, content)
                        route = message.channel

                    await self.send_message(route, content)

                    if response.delete_incoming is True:
                        self.delete_message(message)

            except CommandError as e:
                await self.send_message(message.channel, '```\n%s\n```' % e.message)

            except:
                await self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
                traceback.print_exc()
            await self.do_server_log(message=message)
        elif message.server.id not in self.server_index:
            return
        elif not self.is_checked(message.author, message.server):
            return
        elif self.is_long_member(message.author.joined_at, message.server):
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                this = config[11][message.author.id]
                now = datetime.utcnow()
                if self.limit_post(message.author, message.server, message.content, flg=flag) is True:
                    try:
                        await self.delete_message(message)
                        await self._write_to_modlog('deleted the message of ', message.author, message.server, 'rate limiting')
                        this[0] = now
                    except:
                        raise CommandError('Cannot delete message: \n{}'.format(message.content))
                else:
                    await self.do_server_log(message=message)
                this[2].append(do_slugify(message.content))
                self.server_index[message.server.id][11][message.author.id] = this
            else:
                this = [datetime.utcnow(), config[1] - 1, [message.content]]
                self.server_index[message.server.id][11][message.author.id] = this
        else:
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                if self.strict_limit_post(message.author, message.server, message.content, flg=flag) is True:
                    try:
                        await self.delete_message(message)
                        await self._write_to_modlog('deleted the message of ', message.author, message.server, 'rate limiting')
                    except:
                        raise CommandError('Cannot delete message: \n{}'.format(message.content))
                else:
                    await self.do_server_log(message=message)
                this = config[11][message.author.id]
                this[0] = datetime.utcnow()
                this[2].append(do_slugify(message.content))
                self.server_index[message.server.id][11][message.author.id] = this
            else:
                this = [datetime.utcnow(), config[1] - 1, [message.content]]
                self.server_index[message.server.id][11][message.author.id] = this
        if not self.is_checked(message.author, message.server):
            return
        for words in self.server_index[message.server.id][5]:
            if compare_strings(words, do_slugify(message.content)) > 79 or words in do_slugify(message.content):
                action = self.server_index[message.server.id][6]
                if 'kick' in action:
                    await self._write_to_modlog('kicked', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                    self.kick(message.author)
                elif 'ban' in action:
                    await self._write_to_modlog('banned', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                    self.ban(message.author, 7)
                    return
                elif 'mute' in action:
                    await self._write_to_modlog('muted', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                    mutedrole = discord.utils.get(message.server.roles, name='Muted')
                    await self.add_roles(message.author, mutedrole)
                elif 'nothing' in action:
                    await self._write_to_modlog('flagged', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                else:
                    return
                await self.delete_message(message)

if __name__ == '__main__':
    bot = AutoMod()
    bot.run()
