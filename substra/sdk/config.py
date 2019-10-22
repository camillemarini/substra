import copy
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_PATH = os.path.expanduser('~/.substra')
DEFAULT_VERSION = '0.0'
DEFAULT_URL = 'http://127.0.0.1:8000'
DEFAULT_PROFILE_NAME = 'default'

DEFAULT_CONFIG = {
    'default': {
        'url': 'http://127.0.0.1:8000',
        'version': '0.0',
        'auth': False,
        'insecure': False,
    }
}


class ConfigException(Exception):
    pass


class ProfileNotFoundError(ConfigException):
    pass


def _read_config(path):
    with open(path) as fh:
        try:
            return json.load(fh)
        except json.decoder.JSONDecodeError:
            raise ConfigException(f"Cannot parse config file '{path}'")


def _write_config(path, config):
    with open(path, 'w') as fh:
        json.dump(config, fh, indent=2, sort_keys=True)


def create_profile(url, version, insecure, username, password):
    """Create profile object."""
    if username and password:
        auth = {
            'username': username,
            'password': password,
        }
    else:
        auth = False

    return {
        'url': url,
        'version': version,
        'insecure': insecure,
        'auth': auth,
    }


def _add_profile(path, name, url, version, insecure, username=None, password=None):
    """Add profile to config file on disk."""
    # read config file
    try:
        config = _read_config(path)
    except FileNotFoundError:
        config = copy.deepcopy(DEFAULT_CONFIG)

    # create profile
    profile = create_profile(url, version, insecure, username, password)

    # update config file
    if name in config:
        config[name].update(profile)
    else:
        config[name] = profile

    _write_config(path, config)
    return config


def _load_profile(path, name):
    """Load profile from config file on disk.

    Raises:
        FileNotFoundError: if config file does not exist.
        ProfileNotFoundError: if profile does not exist.
    """
    logger.debug(f"Loading profile '{name}' from '{path}'")
    config = _read_config(path)
    try:
        return config[name]
    except KeyError:
        raise ProfileNotFoundError(name)


class Manager():
    def __init__(self, path=DEFAULT_PATH):
        self.path = path

    def add_profile(self, name, url=DEFAULT_URL, version=DEFAULT_VERSION,
                    insecure=False, username=None, password=None):
        """Add profile to config file on disk."""
        config = _add_profile(
            self.path,
            name,
            url,
            version=version,
            insecure=insecure,
            username=username,
            password=password,
        )
        return config[name]

    def load_profile(self, name):
        """Load profile from config file on disk.

        Raises:
            FileNotFoundError: if config file does not exist.
            ProfileNotFoundError: if profile does not exist.
        """
        return _load_profile(self.path, name)
