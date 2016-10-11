import configparser


class Config(object):
    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        self.token = config.get('Credentials', 'Token', fallback=None)

        self.master_id = config.get('Permissions', 'OwnerID', fallback=None)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback='!')

        # TODO: make this work right and not have a file hanging out in root directory
        self.globalbans_file = config.get('Files', 'GlobalBansFile', fallback='config/globalbans.txt')
        self.banonjoin_file = config.get('Files', 'BanOnJoinFile', fallback='config/banonjoin.txt')
        self.user_changes_file = config.get('Files', 'UserChangesFile', fallback='config/userchanges.json')

        # Validation logic for bot settings.

        if not self.master_id:
            raise ValueError("An owner is not specified in the configuration file")