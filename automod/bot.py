import asyncio
import discord
import traceback
import inspect
import os
import re
import shlex

from functools import wraps

from fuzzywuzzy import fuzz
from datetime import datetime, timedelta

from automod.config import Config
from automod.register import Register
from automod.response import Response
from automod.version import VERSION
from automod.utils import load_json, extract_user_id, write_json, load_file, write_file, compare_strings, do_slugify

from .exceptions import CommandError
from .constants import BOT_HANDLER_ROLE, RHINO_SERVER, RHINO_SERVER_CHANNEL, DOCUMENTATION_FOR_BOT, CARBON_BOT_ID


def backup_config(server_config_list):
    for key, current_config in server_config_list.items():
        current_config[11] = {}
        savedir = 'configs\\'+str(key)
        if not os.path.exists(savedir):
            os.makedirs(savedir)
        savedir += '\\config.json'
        write_json(savedir, current_config)

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

    def has_roles(self, channel, user, check_server, register=False):
        if register is False:
            if check_server.id not in self.server_index:
                return
        if len(check_server.roles) != 1:
            try:
                for role in user.roles:
                    try:
                        perms = user.permissions_in(channel)
                        if perms.manage_roles:
                            return True
                        elif role.name in self.server_index[check_server.id][14] or user.id in self.server_index[check_server.id][15]:
                            return True
                    except:
                        pass
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
            margin = timedelta(hours=config[7])
            return today - margin > date_joined
        except:
            return False

    def strict_limit_post(self, author, server, content, limit_post_flag=None):
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
            return 2

        if now - last_post_time < timedelta(minutes=10) and not limit_post_flag:
            for last_content in last_timeframe_content:
                if compare_strings(last_content, content) > 75:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 1

        if now - last_post_time < timedelta(seconds=config[2]):
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            if author_index[1] <= 0:
                return 3
        else:
            author_index[1] = config[1]
            author_index[2] = []
        self.server_index[server.id][11][author.id] = author_index
        return 0

    def limit_post(self, author, server, content, limit_post_flag=None):
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
            return 2

        content = do_slugify(content)

        match2 = re.split("[\n]{4,}", content)
        match = re.split(r"(.)\1{9,}", content)

        if len(match) > 1 or len(match2) > 1:
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            return 2

        if now - last_post_time < timedelta(minutes=1) and not limit_post_flag:
            for last_content in last_timeframe_content:
                if compare_strings(last_content, content) > 85:
                    author_index[1] -= 1
                    self.server_index[server.id][11][author.id] = author_index
                    return 1

        this = config[2] + 1
        if now - last_post_time < timedelta(seconds=this):
            author_index[1] -= 1
            self.server_index[server.id][11][author.id] = author_index
            if author_index[1] <= 0:
                return 3
        else:
            author_index[1] = config[1] + 2
            author_index[2] = []
        self.server_index[server.id][11][author.id] = author_index
        return 0

    async def on_ready(self):
        print('Connected!\n')
        print('Username: ' + self.user.name)
        print('ID: ' + self.user.id)
        print('--Servers Currently not Registered--')
        for server in self.servers:
            if server.id not in self.server_index:
                print("{} : {}".format(server.name, server.id))
        print()
        await self.backup_list()

    async def server_timer(self, server):
        await asyncio.sleep(86400)
        print('Server Timer has run out, leaving')
        if server.id not in self.server_index:
            await self.leave_server(server)
            print('{} timed out after 24 hours')

    async def backup_list(self):
        await asyncio.sleep(900)
        print('-----------BACKING UP JSON-----------')
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
        content = re.sub(r'".+".*?(".+")', '', message.content)
        try:
            await self.send_message(discord.Object(id=config[8]), 'At *{}*, **{}** has used the command ```{}```Reason: `{}`'
                                                                  ''.format(datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"), author, content, reason))
        except discord.NotFound:
            print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))

    async def _write_to_modlog(self, autoaction, offender, server, reason):
        if server.id in self.server_index:
            config = self.server_index[server.id]
        else:
            return
        if not config[8] or not config[10]:
            return
        if not reason:
            reason = "***No Reason Specified***"
        try:
            await self.send_message(discord.Object(id=config[8]), 'At *{}*, I automatically {} **{}** for {}'
                                                                  ''.format(datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"), autoaction, offender, reason))
        except discord.NotFound:
            print('ERROR FOUND ON : {} : {}'.format(server.name, server.id))

    # TODO: Make this good code that is mine, not stuff taken from old pre async branch code written by @Sharpwaves
    async def do_server_log(self, message=None, log_flag=None, member=None, before=None, after=None):
        if message and not log_flag:
            if message.server.id in self.server_index:
                config = self.server_index[message.server.id]
            else:
                return
            if message.channel.id in config[12]:
                return
            if not config[9]:
                return
            channel_trimmed = message.channel.name.upper()[:10]
            if len(message.clean_content) > 1800:
                msg = '**__{}|__ {}:** {}'.format(channel_trimmed, message.author.name, message.clean_content)
                split = [msg[i:i+1800] for i in range(0, len(msg), 1800)]
                for x in split:
                    try:
                        await self.send_message(discord.Object(config[9]), x)
                    except discord.NotFound:
                        print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                    except discord.Forbidden:
                        print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
            else:
                try:
                    msg = '**__{}|__ {} uploaded an attachment:** {}'.format(channel_trimmed, message.author.name, message.attachments[0]['url'])
                    await self.send_message(discord.Object(config[9]), msg)
                except:
                    pass
                if message.clean_content != '':
                    msg = '**__{}|__ {}:** {}'.format(channel_trimmed, message.author.name, message.clean_content)
                    try:
                        await self.send_message(discord.Object(config[9]), msg)
                    except discord.NotFound:
                        print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                    except discord.Forbidden:
                        print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
        elif log_flag:
            if log_flag == 'join':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not config[9]:
                    return
                try:
                    await self.send_message(discord.Object(config[9]), '**++++++++++++++++++++++++**\n**{} '
                                                                      'JOINED THE SERVER**\n**++++++++++++++++++++++++'
                                                                      '**'.format(member.name.upper()))
                except discord.NotFound:
                        print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                except discord.Forbidden:
                    print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
            elif log_flag == 'remove':
                if member.server.id in self.server_index:
                    config = self.server_index[member.server.id]
                else:
                    return
                if not config[9]:
                    return
                try:
                    await self.send_message(discord.Object(config[9]), '**--------------------------------------**'
                                                                      '\n**{} LEFT THE SERVER**\n**'
                                                                      '--------------------------------------**'
                                                                      ''.format(member.name.upper()))
                except discord.NotFound:
                    print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                except discord.Forbidden:
                    print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
            elif log_flag == 'edit':
                if before.server.id in self.server_index:
                    config = self.server_index[before.server.id]
                else:
                    return
                if before.channel.id in config[12]:
                    return
                if not config[9]:
                    return
                channel_trimmed = after.channel.name.upper()[:10]
                if (len(before.clean_content) + len(after.clean_content)) > 1800:
                    msg = '**__{}|__ {} edited their message**\n**Before:** {}\n**+After:** {}'.format(channel_trimmed, after.author.name, before.clean_content, after.clean_content)
                    split = [msg[i:i+1800] for i in range(0, len(msg), 1800)]
                    for x in split:
                        try:
                            await self.send_message(discord.Object(config[9]), x)
                        except discord.NotFound:
                            print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                        except discord.Forbidden:
                            print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
                else:
                    msg = '**__{}|__ {} edited their message**\n**Before:** {}\n**+After:** {}'.format(channel_trimmed, after.author.name, before.clean_content, after.clean_content)
                    try:
                        await self.send_message(discord.Object(config[9]), msg)
                    except discord.NotFound:
                        print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                    except discord.Forbidden:
                        print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
            elif log_flag == 'delete':
                if message.server.id in self.server_index:
                    config = self.server_index[message.server.id]
                else:
                    return
                if message.channel.id in config[12] or message.content == '':
                    return
                if not config[9]:
                    return
                channel_trimmed = message.channel.name.upper()[:10]
                if len(message.clean_content) > 1800:
                    msg = '**__{}|__ {} deleted their message:** {}'.format(channel_trimmed, message.author.name, message.clean_content)
                    split = [msg[i:i + 1800] for i in range(0, len(msg), 1800)]
                    for x in split:
                        try:
                            await self.send_message(discord.Object(config[9]), x)
                        except discord.NotFound:
                            print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                        except discord.Forbidden:
                            print('Cannot send message to server log, no permissions : {}'.format(message.server.name))
                else:
                    if message.clean_content != '':
                        msg = '**__{}|__ {} deleted their message:** {}'.format(channel_trimmed, message.author.name, message.clean_content)
                        try:
                            await self.send_message(discord.Object(config[9]), msg)
                        except discord.NotFound:
                            print('ERROR FOUND ON : {} : {} : {}'.format(message.server.name, message.server.id, message.channel.name))
                        except discord.Forbidden:
                            print('Cannot send message to server log, no permissions : {}'.format(message.server.name))

    async def handle_register(self, message, author, server):
        """
        Usage: {command_prefix}register
        If the user who starts the registration has the `AutoManager` role, start the registration process.
        """
        if self.has_roles(message.channel, author, server, register=True):
            print('Registration Started for "{}" by: {}'.format(server.name, author.name))
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
        Usage: {command_prefix}mute @UserName <time> "<reason>"
        Mute the user indefinitley unless given a time, then only mute till the time is up
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}unmute @UserName "<reason>"
        Unmutes the user defined.
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}addroles @UserName "<role name>" "<reason>"
        Assigns the user the roles defined
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}removerole @UserName "<role name>" "<reason>"
        Removes the role defined from the user
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}purge <# to purge> @UserName "<reason>"
        Removes all messages from chat unless a user is specified;
        then remove all messages by the user.
        """
        if self.has_roles(message.channel, author, server):
            if username and not reason and not username.startswith('<@'):
                reason = username
                username = None
            await self.write_to_modlog(message, author, server, reason)
            if not username:
                # logs = await self.logs_from(channel, int(count))
                # for msg in logs:
                async for msg in self.logs_from(channel, int(count)):
                    await self.delete_message(msg)
            else:
                user_id = extract_user_id(username)
                if not user_id:
                    raise CommandError('Invalid user specified')
                culprit = discord.utils.get(server.members, id=str(user_id))
                # logs = await self.logs_from(channel)
                # for msg in logs:
                async for msg in self.logs_from(channel):
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
        Usage: {command_prefix}ban @UserName "<reason>"
        Bans the user from the server and removes 7 days worth of their messages
        """
        if self.has_roles(message.channel, author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            member = discord.utils.get(server.members, id=str(user_id))
            self.ban(member, 7)

    async def handle_kick(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}kick @Username "<reason>"
        Kicks the user from the server.
        """
        if self.has_roles(message.channel, author, server):
            user_id = extract_user_id(username)
            if not user_id:
                raise CommandError('Invalid user specified')
            await self.write_to_modlog(message, author, server, reason)
            member = discord.utils.get(server.members, id=str(user_id))
            self.kick(member)

    async def handle_whitelist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}whitelist @UserName *OR* "<role name>" "<reason>"
        Adds the user or role to the whitelist so they're ignored by the filters.
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                role = discord.utils.get(server.members, id=str(user_id))
                if not role:
                    config[4].append(role.id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    if not role:
                        int('this')
                    config[3].append(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_modlist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}modlist @UserName *OR* "<role name>" "<reason>"
        Adds the user or role to the list of people I allow to use my commands!
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                role = discord.utils.get(server.members, id=str(user_id))
                if not role:
                    config[15].append(role.id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    if not role:
                        config[14].append(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_blacklist(self, message, author, server, string_arg, reason=None):
        """
        Usage: {command_prefix}blacklist "<string>" "<reason>"
        Adds the specified word / words (string) to the blacklist!
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            config[5].append(do_slugify(string_arg))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remblacklist(self, message, author, server, string_arg, reason=None):
        """
        Usage: {command_prefix}remblacklist "<string>" "<reason>"
        Removes the specified word / words (string) from the blacklist!
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            try:
                config[5].remove(do_slugify(string_arg))
            except ValueError:
                raise CommandError('No such item in blacklist : {}'.format(string_arg))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remwhitelist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}whitelist @UserName *OR* "<role name>" "<reason>"
        Removes the user or role from the whitelist so they're no longer ignored by the filters.
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                role = discord.utils.get(server.members, id=str(user_id))
                if not role:
                    int('this')
                config[4].remove(role.id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    if not role:
                        int('this')
                    config[3].remove(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remmodlist(self, message, author, server, agent, reason=None):
        """
        Usage: {command_prefix}remmodlist @UserName *OR* "<role name>" "<reason>"
        Removes the user or role from the list of people I take commands from.
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            try:
                user_id = extract_user_id(agent)
                role = discord.utils.get(server.members, id=str(user_id))
                if not role:
                    int('this')
                config[15].remove(role.id)
            except:
                try:
                    role = discord.utils.get(server.roles, name=agent)
                    if not role:
                        int('this')
                    config[14].remove(role.name)
                except:
                    raise CommandError('Invalid user / role specified : {}'.format(agent))
            self.server_index[server.id] = config
            await self.write_to_modlog(message, author, server, reason)

    async def handle_unban(self, message, author, server, username, reason=None):
        """
        Usage: {command_prefix}unban @UserName "<reason>"
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
        Usage: {command_prefix}settokens <number> "<reason>"
        Sets the number of tokens a user has to spend in a reset period
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}settokenreset <time in seconds> "<reason>"
        Sets the time frame in which a user can spend their tokens until they're rate limited
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}setpunishment <new punishment> "<reason>"
        Sets the punishment to be used when a blacklisted word is detected
        Only accepts : 'kick', 'ban', 'mute', or 'nothing'
        """
        if self.has_roles(message.channel, author, server):
            if 'kick' or 'ban' or 'mute' or 'nothing' not in new_punishment:
                raise CommandError('Improper option inputted: {}'.format(new_punishment))
            config = self.server_index[server.id]
            if new_punishment == config[6]:
                return
            config[6] = new_punishment
            await self.write_to_modlog(message, author, server, reason)

    async def handle_setlongtimemember(self, message, author, server, time, reason=None):
        """
        Usage: {command_prefix}setlongtimemember <time> "<reason>"
        Sets what the time in hours will be until a user is considered a 'long time memeber' of the server
        and be subjected to less strict filtering.
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}setmodlogid <new channel ID> "<reason>"
        Sets the channel ID of the mod log!
        """
        if self.has_roles(message.channel, author, server):
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
        Usage: {command_prefix}setserverlogid <new channel ID> "<reason>"
        Sets the channel ID of the server log!
        """
        if self.has_roles(message.channel, author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(str(new_id)) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[9] = new_id
            await self.write_to_modlog(message, author, server, reason)

    async def handle_togglemodlog(self, message, author, server, reason=None):
        """
        Usage: {command_prefix}togglemodlog "<reason>"
        Changes whether the mod log is to be used or not!
        """
        if self.has_roles(message.channel, author, server):
            current = self.server_index[server.id][10]
            if current is True:
                self.server_index[server.id][10] = False
            else:
                self.server_index[server.id][10] = True
                await self.write_to_modlog(message, author, server, reason)

    async def handle_serverinfo(self, message, author, server):
        """
        Usage: {command_prefix}serverinfo
        Gets all the info for the server the command was called from and PM it to
        the person who used the command
        """
        if self.has_roles(message.channel, author, server):
            config = self.server_index[server.id]
            await self.send_message(author, '*{}\'s Server Config*\n**Created in bot version number: {}**\n----------------------------------\n'
                                            'Number of Tokens: `{}`\n\nToken Reset Time: `{} second(s)`\n\nWhitelisted roles: `{}`\n\nWhitelisted Users: `{}`'
                                            '\n\nBlacklisted words: `{}`\n\nAutomatic action to take: `{}`\n\nTime till user considered an old user: `{} hours`'
                                            '\n\nChannel ID for Mod Log: `{}`\n\nChannel ID for Server Log: `{}`\n\nShould I use the Mod Log?: `{}`'
                                            '\n\nIgnored Channel IDs: `{}`\n\nRoles which can use all my commands: `{}`\n\nUsers who can use all my commands: `{}`'
                                            '\n\n**END OF SERVER CONFIG**'.format(server.name, config[0], config[1], config[2], config[3], config[4], config[5], config[6],
                                                                                  config[7], config[8], config[9], config[10], config[12], config[14], config[15]))

    async def handle_alertrhino(self, message, author, server, string_arg):
        """
        Usage: {command_prefix}alertrhino "<message>"
        Used to send a message to SexualRhinoceros if the bot isn't working for one reason or another!
        """
        if self.has_roles(message.channel, author, server):
            inv = await self.create_invite(server, max_uses=3, xkcd=True)
            print('Alert Command on Server: {}'.format(server.name))
            for servers in self.servers:
                if servers.id == RHINO_SERVER:
                    for channel in servers.channels:
                        if channel.id == RHINO_SERVER_CHANNEL:
                            await self.send_message(channel, 'Help requested by **{}** at *{}* for reason `{}`\n\t{}'
                                                             ''.format(author.name, server.name, string_arg, inv))
                            return Response('Rhino has been alerted!', reply=True)
            pass

    async def handle_ping(self, message, author, server):
        """
        Usage: {command_prefix}ping
        Replies with "PONG!"; Use to test bot's responsiveness
        """
        if self.has_roles(message.channel, author, server):
            return Response('PONG!', reply=True)

    async def handle_help(self, message, author, server):
        """
        Usage: {command_prefix}help
        Replies with the link to the commands page!
        """
        if self.has_roles(message.channel, author, server):
            return Response('https://github.com/SexualRhinoceros/ModTools/wiki/Main#commands', reply=True)

    async def handle_info(self, message, author, server):
        """
        Usage: {command_prefix}info
        Sends a whole buncha info pertaining to the bot to the chat!
        """
        return Response('I was coded by SexualRhinoceros and am currently on v{} ! \nFor documentation on my commands or info on how to get my in your'
                        ' server, check out this link! {}'.format(VERSION, DOCUMENTATION_FOR_BOT), reply=True)

    async def handle_ignore(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}ignore <channel ID> "<reason>"
        Adds the channel ID to the list of ignored channels when outputting to the server log
        """
        if self.has_roles(message.channel, author, server):
            try:
                new_id = str(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(new_id) != 18 or len(new_id) != 17:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            config[12].append(new_id)
            await self.write_to_modlog(message, author, server, reason)

    async def handle_remignore(self, message, author, server, new_id, reason=None):
        """
        Usage: {command_prefix}remignore <channel ID> "<reason>"
        Removes the channel ID from the list of ignored channels when outputting to the server log
        """
        if self.has_roles(message.channel, author, server):
            try:
                new_id = int(new_id)
            except:
                raise CommandError('Non number detected: {}'.format(new_id))
            if len(str(new_id)) != 18:
                raise CommandError('Invalid Channel ID: {}'.format(new_id))
            config = self.server_index[server.id]
            try:
                config[12].remove(str(new_id))
            except ValueError:
                raise CommandError('No such channel in ignore list : {}'.format(new_id))
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

    async def handle_dropdeadbeats(self, message, author, server):
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

            if server_leave_array:
                for dbserver in server_leave_array:
                    print('Leaving Deadbeat Server : {}'.format(dbserver.name))
                    await self.leave_server(dbserver)
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
            self.globalbans.add(str(user_id))
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
        Usage: {command_prefix}forcebackup
        Forces a back up of all server configs
        """
        if author.id == self.config.master_id:
            backup_config(self.server_index)
            return Response('its been done', reply=True)
        return

    async def handle_remind(self, author, server):
        """
        Usage: {command_prefix}remind
        Sends a reminder to register to all nonregistered servers
        """
        if author.id == self.config.master_id:
            for server in self.servers:
                if server.id not in self.server_index:
                    try:
                        await self.send_message(server, 'Hello! Just a reminder from your friendly robo-Moderator that I don\'t have any function'
                                                        ' until someone goes through the registration process with me!\nIf a Moderator with a role named '
                                                        '`{}` would run the command `{}register`, I can start helping keep things clean!'.format(
                                                            BOT_HANDLER_ROLE, self.config.command_prefix))
                    except discord.Forbidden:
                        print('Cannot remind, server\'s default channel is locked : {}'.format(server.name))
            return Response('its been done', reply=True)
        return

    async def handle_joinserver(self, author, server_link, join_flag=None):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server.
        """
        try:
            inv = await self.get_invite(server_link)
            self.user_invite_dict[inv.server.id] = author.id
            await self.accept_invite(server_link)
            print('Joined Server: {}'.format(inv.server.name))
            if join_flag:
                return True
            return False
        except:
            if not join_flag:
                raise CommandError('Invalid URL provided:\n\t{}\n'.format(server_link))

    async def on_server_join(self, server):
        try:
            await self.send_message(server.default_channel, 'Hello! I\'m your friendly robo-Moderator and was invited by <@{}> to make the lives of everyone easier!'
                                                            '\nIf a Moderator with a role named `{}` would run the command `{}register`, I can start helping'
                                                            ' keep things clean!'.format(
                                                                self.user_invite_dict[server.id], BOT_HANDLER_ROLE, self.config.command_prefix))
        except discord.Forbidden:
            print('Cannot greet, server\'s default channel is locked')
        await self.server_timer(server)

    async def on_server_remove(self, server):
        print('Removed from Server: {}'.format(server.name))

    async def on_message_edit(self, before, after):

        if before.content == after.content:
            return
        if before.author.id == self.user.id:
            return
        await self.do_server_log(before=before, after=after, log_flag='edit')
        await self.on_message(after, flag=True)

    async def on_message_delete(self, message):
        await self.do_server_log(message=message, log_flag='delete')

    async def on_member_remove(self, member):
        await self.do_server_log(self, member=member, log_flag='remove')

    async def on_member_join(self, member):
        await self.do_server_log(self, member=member, log_flag='join')

    async def on_message(self, message, flag=None):

        if message.author == self.user:
            return

        if message.author.id in self.globalbans:
            return
        if message.channel.is_private:
            try:
                this = await self.handle_joinserver(message.author, message.content, join_flag=True)
                if this and this is not False:
                    await self.send_message(message.author, 'I joined the requested server. <333')
                    return
            except:
                pass
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
                        print('Registration Completed by: {}'.format(message.author.name))
                        self.server_index[register_instance.server.id] = register_instance.return_server_config()
                        del self.register_instances[message.author.id]
                    return
            else:
                await self.send_message(message.channel, 'You cannot use this bot in private messages.')
            return

        message_content = message.content.strip()
        if message_content.startswith(self.config.command_prefix):
            try:
                command, *args = shlex.split(message_content)
            except ValueError:
                await self.send_message(message.channel, '```\nNo closing quote detected in message : {}\n```'.format(message.server.name))

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
                try:
                    response = await handler(**handler_kwargs)
                except discord.DiscordException as e:
                    response = None
                    print('Exception on {}({}) in channel {}\n\t{}'.format(message.server.name, message.server.id, message.channel.name, e))
                if response and isinstance(response, Response):
                    content = response.content
                    if response.pm:
                        route = message.author
                    if response.reply:
                        content = '%s, %s' % (message.author.mention, content)
                        route = message.channel
                    try:
                        await self.send_message(route, content)
                    except:
                        pass

                    if response.delete_incoming is True:
                        try:
                            self.delete_message(message)
                        except discord.NotFound:
                            pass

            except CommandError as e:
                await self.send_message(message.channel, '```\n%s\n```' % e.message)

            except:
                await self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
                traceback.print_exc()
            if not flag:
                await self.do_server_log(message=message)
        elif message.server.id not in self.server_index:
            return
        elif message.author.id in self.server_index[message.server.id][12]:
            return
        elif not self.is_checked(message.author, message.server):
            if not flag:
                await self.do_server_log(message=message)
            return
        elif self.is_long_member(message.author.joined_at, message.server):
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                this = config[11][message.author.id]
                now = datetime.utcnow()
                dis = self.limit_post(message.author, message.server, message.content, limit_post_flag=flag)
                if dis > 0:
                    try:
                        await self.delete_message(message)
                        if dis is 1:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, '*duplicate message detected*```{}```'.format(message.content[:10]))
                        elif dis is 2:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, '*spam-esque duplicate characters detected*```{}```'.format(message.content[:10]))
                        else:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, '*rate limiting*```{}```'.format(message.content[:10]))
                        this[0] = now
                    except:
                        print('Cannot delete, no permissions : {}'.format(message.server.name))
                else:
                    if not flag:
                        await self.do_server_log(message=message)
                this[2].append(do_slugify(message.content))
                self.server_index[message.server.id][11][message.author.id] = this
            else:
                if not flag:
                    await self.do_server_log(message=message)
                this = [datetime.utcnow(), config[1] + 2, [message.content]]
                self.server_index[message.server.id][11][message.author.id] = this
        else:
            config = self.server_index[message.server.id]
            if message.author.id in config[11]:
                dis = self.strict_limit_post(message.author, message.server, message.content, limit_post_flag=flag)
                if dis > 0:
                    try:
                        await self.delete_message(message)
                        if dis is 1:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, 'duplicate message detected```{}```'.format(message.content[:10]))
                        elif dis is 2:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, 'spam-esque duplicate characters detected```{}```'.format(message.content[:10]))
                        else:
                            await self._write_to_modlog('deleted the message of ', message.author, message.server, 'rate limiting```{}```'.format(message.content[:10]))
                    except:
                        print('Cannot delete, no permissions : {}'.format(message.server.name))
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
                this = [datetime.utcnow(), config[1], [message.content]]
                self.server_index[message.server.id][11][message.author.id] = this
        if not self.is_checked(message.author, message.server):
            return
        if message.server.id not in self.server_index:
            return
        else:
            for words in self.server_index[message.server.id][5]:
                check_pct = 79
                if self.is_long_member(message.author.joined_at, message.server):
                    check_pct = 90
                if compare_strings(words, do_slugify(message.content)) > check_pct or words in do_slugify(message.content):
                    action = self.server_index[message.server.id][6]
                    if 'kick' in action:
                        await self._write_to_modlog('kicked', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                        try:
                            self.kick(message.author)
                        except:
                            print('Cannot kick, no permissions : {}'.format(message.server.name))
                    elif 'ban' in action:
                        await self._write_to_modlog('banned', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                        try:
                            self.ban(message.author, 7)
                        except:
                            print('Cannot ban, no permissions : {}'.format(message.server.name))
                        return
                    elif 'mute' in action:
                        await self._write_to_modlog('muted', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                        mutedrole = discord.utils.get(message.server.roles, name='Muted')
                        try:
                            await self.add_roles(message.author, mutedrole)
                        except:
                            print('Cannot mute, no permissions : {}'.format(message.server.name))
                    elif 'nothing' in action:
                        await self._write_to_modlog('flagged', message.author, message.server, 'the use of a blacklisted word : `{}`'.format(message.content))
                    else:
                        return
                    try:
                        await self.delete_message(message)
                    except discord.Forbidden:
                        print('Cannot delete, no permissions : {}'.format(message.server.name))
                    except discord.NotFound:
                        pass

if __name__ == '__main__':
    bot = AutoMod()
    bot.run()
