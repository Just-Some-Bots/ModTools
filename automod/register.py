import datetime

from slugify import slugify

from automod.constants import MUTED_IMGUR_SETUP_LINK, DOCUMENTATION_FOR_BOT
from automod.response import Response
from automod.version import VERSION
from automod.constants import REGISTER_WORD


class Register(object):
    def __init__(self, user, server):
        self.user = user
        self.step = 0
        self.server = server
        self.server_config_build = []
        self.last_time = datetime.datetime.now()

    def return_server_config(self):
        return self.server_config_build

                                                                # List below directly corrolates with adjacent appended config element. *'s indicate items changed in set up
    def build_empty_config(self):                               # ----------------------------------------------------------------------------------------------------------------------------------------------------------
        self.server_config_build.append(VERSION)                # 0    STRING; Version Number
        self.server_config_build.append(5)                      # 1    INT; * Number of Tokens given to a user
        self.server_config_build.append(5)                      # 2    INT; * Time till tokens are reset back to max amount
        self.server_config_build.append([])                     # 3    LIST; * All Roles which are whitelisted ie: not subject to filtering / rate limiting
        self.server_config_build.append([])                     # 4    LIST; All Users which are whitelisted ie: not subject to filtering / rate limiting
        self.server_config_build.append([])                     # 5    LIST; * All strings in a sluggified format which are blacklisted and result in deletion / more action
        self.server_config_build.append('nothing')              # 6    STRING; * Action to be taken upon black listed word if defined. Only accepts 'kick', 'ban', 'mute', 'nothing' or errors will arise
        self.server_config_build.append(12)                     # 7    INT; * The amount of hours until a user is considered a long time member of the server
        self.server_config_build.append(0)                      # 8    INT; The channel ID for the specific server's Mod Log
        self.server_config_build.append(0)                      # 9    INT; The channel ID for the specific server's Server Log
        self.server_config_build.append([False,                 # 10.0 BOOLEAN;   Whether the Mod Log will be actually used or not
                                         False,                 # 10.1 BOOLEAN; * Whether the Server Log will be actually used or not
                                         False,                 # 10.2 BOOLEAN; * Whether Anti Twitch mode will be used which removes twitch emote names
                                         True,                  # 10.3 BOOLEAN; * Whether the bot will rate limit
                                         True,                  # 10.4 BOOLEAN; * Whether the bot will check for duplicate characters
                                         True])                 # 10.5 BOOLEAN; * Whether the bot will check for duplicate messages
        self.server_config_build.append({})                     # *11   DICT; Keeps track of rate limiting. Key = user ID, Value = List [time of last post, # of tokens left, List = [#  of last messages based on # of tokens given]]
        self.server_config_build.append([])                     # 12    LIST; * Channels to be ignored entirely by the bot
        self.server_config_build.append({})                     # *13   DICT; A dict that holds the IDs of muted users as keys and the datetime of the mute as values
        self.server_config_build.append([])                     # 14    LIST; * Roles which are given the ability to command the bot
        self.server_config_build.append(['77511942717046784'])  # 15    LIST; Users who are given the ability to command the bot
        self.server_config_build.append([{}, {}])               # 16    LIST; Used for dynamic permissions, first dict holds allowed permissions, while the second holds denied permissions.
        self.server_config_build.append(None)                   # 17    NONE OBJECT; Reserved for future use

    async def do_next_step(self, args=None):
        method_name = 'step_' + str(self.step)
        method_call = getattr(self, method_name, lambda: None)
        return await method_call(args)
    
    async def restart(self):
        self.step = 2
        self.build_empty_config()
        return Response('Please make sure you respond with **ONLY** the information needed. Also, use `!skip` if you don\'t wish to complete a step or '
                        '`!restart`if you want to start over!\nFor the first step, I\'ll need to know which roles which you\'d like me omit from my '
                        'filtering\n\t`example input: Moderators, Admin, Trusted`',
                        pm=True
                        )

    async def step_0(self, args):
        self.step = 1
        self.build_empty_config()
        return Response('Hello {}! Let\'s get your server `{}` set up and ready to roll! \nA few prerequisites before we continue, '
                        'you\'ll need to make sure the bot has all of the permissions of a regular Moderator *ie: Manage Server, Channels, Roles,'
                        'Messages, ect.* Also be sure the check out {} for information on setting up the **Muted** role! \n\nNow, to start the Registration'
                        ' process, you need to go to {} and read through it. Follow the directions there and you\'ll be able to continue!'.format(
                            self.user.name, self.server.name, MUTED_IMGUR_SETUP_LINK, DOCUMENTATION_FOR_BOT
                        ),
                        pm=True
                        )

    async def step_1(self, args):
        if REGISTER_WORD not in args:
            return Response('To continue the Registration process, you need to go to {} and read through everything. '
                            'Follow the directions there and you\'ll be able to continue!'.format(DOCUMENTATION_FOR_BOT),
                            pm=True
                            )
        else:
            self.step = 2
            return Response('Great! Now that you\'ve read everything, time for the configuration! \n\nPlease make sure you respond with **ONLY** the information needed. '
                            'Also, use `!skip` if you don\'t wish to complete a step or `!restart`if you want to start over!\nFor the first step, I\'ll need to know which '
                            'roles which you\'d like me omit from my filtering. This step can be skipped!\n\t`example input: Moderators, Admin, Trusted`',
                            pm=True
                            )

    async def step_2(self, args):
        if '!restart' in args:
            return await self.restart()

        if args and '!skip' not in args:
            self.server_config_build[3] = args
        elif '!skip' in args:
            args = 'nothing since you decided to skip'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 3
        return Response('Okay, got it. Added {} to the list of white listed roles!\n\nNext up, I need to know which user groups you\'d like me to '
                        'take orders from! They\'ll have full access to all of my commands. This step can be skipped!'
                        '\n\t`example input: Moderators, Admin, Developers`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_3(self, args):
        if '!restart' in args:
            return await self.restart()

        if args and '!skip' not in args:
            self.server_config_build[14] = args
        elif '!skip' in args:
            args = 'nothing since you decided to skip'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 4
        return Response('Okay, got it. Added {} to the list of privileged roles!\n\nNext up is token reset time in seconds'
                        '\n\t`example input: 5`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_4(self, args):
        if '!restart' in args:
            return await self.restart()
        try:
            this = int(args[0])
            self.server_config_build[2] = this
        except:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 5
        return Response('Okay, got it. Added `{}` as the Token Reset Time!\n\nNext up is the number of tokens given to a user'
                        '\n\t`example input: 5`'.format(
                            this
                        ),
                        pm=True
                        )

    async def step_5(self, args):
        if '!restart' in args:
            return await self.restart()
        try:
            this = int(args[0])
            self.server_config_build[1] = this
        except:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 6
        return Response('Okay, got it. Added {} as the number of user given tokens per reset period!\n\nNext up is the word filter. This step can be skipped!'
                        '\n\t`example input: twitch.tv, discord.gg, faggots`'.format(
                            this
                        ),
                        pm=True
                        )
    async def step_6(self, args):
        if '!restart' in args:
            return await self.restart()
        if args and '!skip' not in args:
            newargs = []
            for thing in args:
                newargs.append(slugify(thing, stopwords=['https', 'http', 'www'], separator='_'))

            self.server_config_build[5] = newargs
        elif '!skip' in args:
            args = 'nothing since you decided to skip'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 7
        return Response('Okay, got it. Added {} to the list of black listed strings!\n\nNext up is the action to be taken upon finding a '
                        'blacklisted word or if a person is rate limited over 4 times! \nI\'ll take `kick / ban / mute / nothing` as input for this option!'
                        ' \n\t`example input: mute`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_7(self, args):
        if '!restart' in args:
            return await self.restart()
        if 'kick' in args or 'ban' in args or 'mute' in args or 'nothing' in args:
                self.server_config_build[6] = str(args[0])
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 8
        return Response('Okay, got it. Added {} as the bad word action!\n\nNext up is the number of hours till a user is considered a long time member'
                        '\n\t`example input: 36`'.format(
                            args[0]
                        ),
                        pm=True
                        )

    async def step_8(self, args):
        if '!restart' in args:
            return await self.restart()
        try:
            if int(args[0]) > 10000000:
                return Response('The number you entered is too large! Please enter something more reasonable!\nPlease try again!',
                            pm=True)
            self.server_config_build[7] = int(args[0])
        except:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 9
        return Response('Okay, got it. Added {} as the number of hours till a user is considered a long time member!\n\nNext up is the channel you\'d'
                        'like all my announcements of changes to go to!\nThese will be sent when Rhino needs to communicate with the moderation teams '
                        'who use the bot about new commands, new features, ect.\nMake sure its sent as the Channel ID which can be found by putting a `\` before the channel tag `ie \#channel_name`'
                        '\nThis step can be skipped!\n\t`example input: 135866654117724160`'.format(
                            args[0]
                        ),
                        pm=True
                        )

    async def step_9(self, args):
        if '!restart' in args:
            return await self.restart()
        if args and '!skip' not in args:
            self.server_config_build[17] = args[0]
        elif '!skip' in args:
            args = 'the default server channel since you decided to skip'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 10
        return Response('Okay, got it. Added {} as the channel to send all my broadcasts to!\n\nNext up is whether you want '
                        'moderator action reasons to be reported! I accept `True` or `False` as inputs'
                        '\n\t`example input: True`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_10(self, args):
        if '!restart' in args:
            return await self.restart()
        if 'True' in args:
            self.server_config_build[10][0] = True
            args = 'will'
        elif 'False' in args:
            self.server_config_build[10][0] = False
            args = 'wont'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        self.step = 11
        return Response('Okay, got it. I {} report action reasons!\n\nFinally, I\'ll need to know which channels you\'d like me to ignore all together.'
                        '\nMake sure its sent as the Channel ID which can be found by putting a `\` before the channel tag `ie \#channel_name` This step can be skipped!'
                        '\n\t`example input: 130787272781070337, 77514836912644096`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_11(self, args):
        if '!restart' in args:
            return await self.restart()
        if args and '!skip' not in args:
            self.server_config_build[12] = args
        elif '!skip' in args:
            args = 'nothing since you decided to skip'
        else:
            return Response('I didn\'t quite catch that! The input I picked up doesn\'t seem to be correct!\nPlease try again!',
                            pm=True)
        return Response('Okay, got it. Added {} to the list of ignored channels! \n\nThats it! Its over! Make sure you check out the syntax page'
                        ' so that you can use me properly and I hope you have a nice day :D'.format(
                            args
                        ),
                        pm=True,
                        trigger=True
                        )
