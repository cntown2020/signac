# Copyright (c) 2016 The Regents of the University of Michigan
# All rights reserved.
# This software is licensed under the MIT License.
import logging
import warnings
import getpass
import json

from .config import load_config
from .errors import ConfigError, AuthenticationError
from .connection import DBClientConnector
from .crypt import get_crypt_context, SimpleKeyring, get_keyring
from . import six

logger = logging.getLogger(__name__)


SESSION_PASSWORD_HASH_CACHE = SimpleKeyring()


def get_default_host(config=None):
    if config is None:
        config = load_config()
    try:
        return config['General']['default_host']
    except KeyError:
        try:
            return config['hosts'].keys()[0]
        except (KeyError, IndexError):
            raise ConfigError("No hosts specified.")


def get_host_config(hostname=None, config=None):
    if config is None:
        config = load_config()
    if hostname is None:
        hostname = get_default_host(config)
    try:
        return config['hosts'][hostname]
    except KeyError:
        raise ConfigError("Host '{}' not configured.".format(hostname))


def uri(hostcfg):
    return '{}@{}'.format(hostcfg['username'], hostcfg['url'])


def _request_credentials(hostcfg):
    pwcfg = hostcfg.get('password_config')
    pw = getpass.getpass("Enter password for {}@{}: ".format(
        hostcfg['username'], hostcfg['url']))
    if pwcfg and 'salt' in pwcfg and 'rounds' in pwcfg:
        logger.debug("Using password configuration for hashing.")
        return get_crypt_context().encrypt(pw, **pwcfg)
    else:
        return pw


def _get_config_credentials(hostcfg):
    return hostcfg.get('password')


def _get_keyring_credentials(hostcfg):
    pwcfg = hostcfg.get('password_config')
    kr = get_keyring()
    if kr is None:
        if pwcfg and 'keyring' in pwcfg:
            warnings.warn(
                "Password stored in keyring, but keyring is not available!")
    elif pwcfg and 'keyring' in pwcfg:
        return kr.get_password('signac', pwcfg['keyring'])
    else:
        return kr.get_password('signac', uri(hostcfg))


def _get_cached_credentials(hostcfg, default):
    hostcfg_id = json.dumps(hostcfg, sort_keys=True)
    if hostcfg_id in SESSION_PASSWORD_HASH_CACHE:
        logger.debug("Loading credentials from cache.")
        return SESSION_PASSWORD_HASH_CACHE[hostcfg_id]
    else:
        return SESSION_PASSWORD_HASH_CACHE.setdefault(hostcfg_id, default())


def _get_stored_credentials(hostcfg):
    def default():
        pw = _get_keyring_credentials(hostcfg)
        if pw is None:
            pw = _get_config_credentials(hostcfg)
        return pw
    return _get_cached_credentials(hostcfg, default)


def _get_credentials(hostcfg):
    def default():
        pw = _get_config_credentials(hostcfg)
        if pw is None:
            pw = _get_keyring_credentials(hostcfg)
            if pw is None:
                pw = _request_credentials(hostcfg)
        return pw
    return _get_cached_credentials(hostcfg, default)


def get_credentials(hostcfg, ask=True):
    if ask:
        return _get_credentials(hostcfg)
    else:
        return _get_stored_credentials(hostcfg)


def check_credentials(hostcfg):
    input_ = raw_input if six.PY2 else input  # noqa
    auth_m = hostcfg.get('auth_mechanism', 'none')
    if auth_m == 'SCRAM-SHA-1':
        if 'username' not in hostcfg:
            username = input("Username ({}): ".format(getpass.getuser()))
            if not username:
                username = getpass.getuser()
            hostcfg['username'] = username
        if 'password' not in hostcfg:
            hostcfg['password'] = get_credentials(hostcfg)
    return hostcfg


def get_connector(hostcfg, **kwargs):
    return DBClientConnector(hostcfg, **kwargs)


def get_client(hostcfg, **kwargs):
    connector = get_connector(hostcfg, **kwargs)
    connector.connect()
    connector.authenticate()
    return connector.client


def get_database(name, hostname=None, config=None, **kwargs):
    if hostname is None:
        hostname = get_default_host()
    if config is None:
        config = load_config()
    hostcfg = check_credentials(get_host_config(hostname, config))
    logger.debug("Connecting with host config: {}".format(
        {k: '***' if 'password' in k else v for k, v in hostcfg.items()}))
    try:
        client = get_client(hostcfg, **kwargs)
    except Exception as error:
        if "Authentication failed" in str(error):
            raise AuthenticationError(hostname)
        raise
    return client[name]
