import datetime

from slugify import slugify

from automod.constants import MUTED_IMGUR_SETUP_LINK, DOCUMENTATION_FOR_BOT
from automod.response import Response
from automod.version import VERSION


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
        self.server_config_build.append(VERSION)                # STRING; Version Number
        self.server_config_build.append(5)                      # INT; * Number of Tokens given to a user
        self.server_config_build.append(5)                      # INT; * Time till tokens are reset back to max amount
        self.server_config_build.append([])                     # LIST; * All Roles which are whitelisted ie: not subject to filtering / rate limiting
        self.server_config_build.append(['77511942717046784'])  # LIST; All Users which are whitelisted ie: not subject to filtering / rate limiting
        self.server_config_build.append(['bigbuttstest'])       # LIST; * All strings in a sluggified format which are blacklisted and result in deletion / more action
        self.server_config_build.append('nothing')              # STRING; * Action to be taken upon black listed word if defined. Only accepts 'kick', 'ban', 'mute', 'nothing' or errors will arise
        self.server_config_build.append(12)                     # INT; * The amount of hours until a user is considered a "long time member" of the server
        self.server_config_build.append(0)                      # INT; The channel ID for the specific server's Mod Log
        self.server_config_build.append(0)                      # INT; The channel ID for the specific server's Server Log
        self.server_config_build.append(False)                  # BOOLEAN; * Whether the Mod Log will be actually used or not
        self.server_config_build.append({})                     # DICT; Keeps track of rate limiting. Key = user ID, Value = List [time of last post, # of tokens left, List = [#  of last messages based on # of tokens given]]
        self.server_config_build.append([])                     # LIST; * Channels to be ignored entirely by the bot
        self.server_config_build.append({})                     # DICT; EMPTY ; Used to be for Muted Users but I found no performance improvement using this vs a regular asynchronous timer
        self.server_config_build.append([])                     # LIST; * Roles which are given the ability to command the bot
        self.server_config_build.append(['77511942717046784'])  # LIST; Users who are given the ability to command the bot

    async def do_next_step(self, args=None):
        method_name = 'step_' + str(self.step)
        method_call = getattr(self, method_name, lambda: None)
        return await method_call(args)

    async def step_0(self, args):
        self.step = 1
        self.build_empty_config()
        return Response('Hello {}! Let\'s get your server `{}` set up and ready to roll! A few prerequisites before we continue, '
                        'you\'ll need to make sure the bot has all of the permissions of a regular Moderator *ie: Manage Server, Channels, Roles,'
                        'Messages, ect.* Also be sure the check out {} for information on setting up the **Muted** role! Finally, for full syntax '
                        'info or if you don\'t understand a step, be sure to check out {}!\n\nNow, for the configuration, make sure you respond with'
                        ' **ONLY** the information needed.\n For the first step, I\'ll need to know which roles which you\'d like me omit from my'
                        'filtering\n\t`example input: \"Moderators, Admin, Trusted\"`'.format(
                            self.user.name, self.server.name, MUTED_IMGUR_SETUP_LINK, DOCUMENTATION_FOR_BOT
                        ),
                        pm=True
                        )

    async def step_1(self, args):
        self.step = 2
        if args and '!skip' not in args:
            self.server_config_build[14] = args
        else:
             args = '.....? Incorrect input or nothing received so setting it to the default. Added nothing'
        return Response('Okay, got it. Added {} to the list of white listed roles! Next up is the user groups you\'d like me to take orders from!'
                        '\n\t`example input: \"Moderators, Admin, Developers\"`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_2(self, args):
        self.step = 3
        if args and '!skip' not in args:
            self.server_config_build[3] = args
        else:
            args = '.....? Incorrect input or nothing received so setting it to the default. Added nothing'
        return Response('Okay, got it. Added {} to the list of privileged roles! Next up is token reset time in seconds'
                        '\n\t`example input: \"5\"`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_3(self, args):
        self.step = 4
        try:
            this = int(args[0])
            self.server_config_build[2] = this
        except:
            args[0] = '.....? Incorrect input received so setting it to the default. Added 5'
        return Response('Okay, got it. Added `{}` as the Token Reset Time! Next up is the number of tokens given to a user'
                        '\n\t`example input: \"5\"`'.format(
                            this
                        ),
                        pm=True
                        )

    async def step_4(self, args):
        self.step = 5
        try:
            this = int(args[0])
        except:
            pass
        if isinstance(this, int):
            self.server_config_build[1] = this
        else:
            args[0] = '.....? Incorrect input received so setting it to the default. Added 5'
        return Response('Okay, got it. Added {} as the number of user given tokens per reset period! Next up is the word blacklist'
                        '\n\t`example input: \"twitch.tv, discord.gg, faggots\"`'.format(
                            this
                        ),
                        pm=True
                        )
    async def step_5(self, args):
        self.step = 6
        if args and '!skip' not in args:
            newargs = []
            for thing in args:
                newargs.append(slugify(thing, stopwords=['https', 'http', 'www'], separator='_'))

            self.server_config_build[5] = newargs
        else:
            args = '.....? Incorrect input or nothing received so setting it to the default. Added nothing'
        return Response('Okay, got it. Added {} to the list of black listed strings! Next up is the action to be taken upon finding a '
                        'blacklisted word! \nI\'ll take `kick / ban / mute / nothing` as input for this option!'
                        ' \n\t`example input: \"mute\"`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_6(self, args):
        self.step = 7
        if 'kick' or 'ban' or 'mute' or 'nothing' in args:
                self.server_config_build[6] = str(args[0])
        else:
            args = '....? You didn\'t specify anything I could use for a required option so instead I decided to add `nothing`'
        return Response('Okay, got it. Added {} as the bad word action! Next up is the number of hours till a user is considered a long time member'
                        '\n\t`example input: \"36\"`'.format(
                            args[0]
                        ),
                        pm=True
                        )

    async def step_7(self, args):
        self.step = 8
        if args:
            self.server_config_build[7] = int(args[0])
        else:
            args = '.....? Incorrect input or nothing received so setting it to the default. Added the default of 12'
        return Response('Okay, got it. Added {} as the number of hours till a user is considered a long time member! Next up is whether you want'
                        'moderator action reasons to be reported! I accept `True` or `False` as inputs'
                        '\n\t`example input: \"True\"`'.format(
                            args[0]
                        ),
                        pm=True
                        )

    async def step_8(self, args):
        self.step = 9
        if 'True' in args:
            self.server_config_build[10] = True
            args = 'will'
        elif 'False' in args:
            self.server_config_build[10] = False
            args = 'wont'
        else:
            self.server_config_build[10] = False
            args = 'didn\'t get a good input so I default to False. I won\'t'
        return Response('Okay, got it. I {} report action reasons! Finally, I\'ll need to know which channels you\'d like me to ignore all together.'
                        '\nMake sure its sent as the Channel ID which can be found by putting a `\\`` before the channel tag `ie \#channel_name`'
                        '\n\t`example input: \"130787272781070337, 77514836912644096\"`'.format(
                            args
                        ),
                        pm=True
                        )

    async def step_9(self, args):
        if args and '!skip' not in args:
            self.server_config_build[12] = args
        else:
            args = '.....? Incorrect input or nothing received so setting it to the default. Added nothing'
        return Response('Okay, got it. Added {} to the list of ignored channels! \n\nThats it! Its over! Make sure you check out the syntax page'
                        ' so that you can use me properly and I hope you have a nice day :D'.format(
                            args
                        ),
                        pm=True,
                        trigger=True
                        )
