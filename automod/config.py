import configparser


class Config(object):
    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        self.username = config.get('Credentials', 'Username', fallback=None)
        self.password = config.get('Credentials', 'Password', fallback=None)

        self.master_id = config.get('Permissions', 'OwnerID', fallback=None)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback='!')

        # TODO: make this work right and not have a file hanging out in root directory
        self.globalbans_file = config.get('Files', 'GlobalBansFile', fallback='globalbans.txt')

        # Validation logic for bot settings.
        if not self.username or not self.password:
            raise ValueError('A username or password was not specified in the configuration file.')

        if not self.master_id:
            raise ValueError("An owner is not specified in the configuration file")