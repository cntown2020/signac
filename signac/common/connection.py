import subprocess
import logging
from os.path import expanduser
import ssl

try:
    import pymongo
    PYMONGO_AVAILABLE = True
    PYMONGO_3 = pymongo.version_tuple[0] == 3
except ImportError:
    PYMONGO_AVAILABLE = False
else:
    PYMONGO_AVAILABLE = True
    PYMONGO_3 = pymongo.version_tuple[0] == 3


logger = logging.getLogger(__name__)

AUTH_NONE = 'none'
AUTH_SCRAM_SHA_1 = 'SCRAM-SHA-1'
AUTH_SSL = 'SSL'
AUTH_SSL_x509 = 'SSL-x509'
SSL_CERT_REQS = {
    'none': ssl.CERT_NONE,
    'optional': ssl.CERT_OPTIONAL,
    'required': ssl.CERT_REQUIRED
}


def get_subject_from_certificate(fn_certificate):  # pragma no cover
    try:
        cert_txt = subprocess.check_output(
            ['openssl', 'x509', '-in', fn_certificate,
             '-inform', 'PEM', '-subject', '-nameopt', 'RFC2253']).decode()
    except subprocess.CalledProcessError:
        msg = "Unable to retrieve subject from certificate '{}'."
        raise RuntimeError(msg.format(fn_certificate))
    else:
        lines = cert_txt.split('\n')
        assert lines[0].startswith('subject=')
        return lines[0][len('subject='):].strip()


def raise_unsupported_auth_mechanism(mechanism):
    msg = "Auth mechanism '{}' not supported."
    raise ValueError(msg.format(mechanism))


class DBClientConnector(object):

    def __init__(self, host_config):
        self._config = host_config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("Client not connected.")
        else:
            return self._client

    @property
    def host(self):
        return self._config['url']

    @property
    def config(self):
        return dict(self._config)

    def _config_get(self, key, default=None):
        return self._config.get(key, default)

    def _config_get_required(self, key):
        return self._config[key]

    def _connect_pymongo3(self, host):
        import pymongo
        parameters = {
            'connectTimeoutMS': self._config_get('connect_timeout_ms'),
        }

        auth_mechanism = self._config_get('auth_mechanism')
        if auth_mechanism in (AUTH_NONE, AUTH_SCRAM_SHA_1):
            client = pymongo.MongoClient(
                host,
                ** parameters)
        elif auth_mechanism in (AUTH_SSL, AUTH_SSL_x509):  # pragma  no cover
            # currently not officially supported
            client = pymongo.MongoClient(
                host,
                ssl=True,
                ssl_keyfile=expanduser(
                    self._config_get_required('ssl_keyfile')),
                ssl_certfile=expanduser(
                    self._config_get_required('ssl_certfile')),
                ssl_cert_reqs=SSL_CERT_REQS[
                    self._config_get('ssl_cert_reqs', 'required')],
                ssl_ca_certs=expanduser(
                    self._config_get_required('ssl_ca_certs')),
                ssl_match_hostname=self._config_get(
                    'ssl_match_hostname', True),
                ** parameters)
        else:
            raise_unsupported_auth_mechanism(auth_mechanism)
        self._client = client

    # not officially supported anymore
    def _connect_pymongo2(self, host):  # pragma no cover
        import pymongo
        parameters = {
            'connectTimeoutMS': self._config_get('connect_timeout_ms'),
        }

        auth_mechanism = self._config_get('auth_mechanism')
        if auth_mechanism in (AUTH_NONE, AUTH_SCRAM_SHA_1):
            client = pymongo.MongoClient(
                host,
                ** parameters)
        elif auth_mechanism in (AUTH_SSL, AUTH_SSL_x509):
            logger.critical("SSL authentication not supported for "
                            "pymongo versions <= 3.x .")
            raise_unsupported_auth_mechanism(auth_mechanism)
        else:
            raise_unsupported_auth_mechanism(auth_mechanism)
        self._client = client

    def connect(self, host=None):
        if host is None:
            host = self._config_get_required('url')
        logger.debug("Connecting to host '{host}'.".format(
            host=self._config_get_required('url')))

        if PYMONGO_AVAILABLE:
            if PYMONGO_3:
                self._connect_pymongo3(host)
            else:  # pragma no cover
                self._connect_pymongo2(host)
        else:
            raise RuntimeError("pymongo library required for this.")

    def authenticate(self):
        auth_mechanism = self._config_get('auth_mechanism')
        logger.debug("Authenticating: mechanism={}".format(auth_mechanism))
        if auth_mechanism == AUTH_SCRAM_SHA_1:
            db_auth = self.client[self._config.get('db_auth', 'admin')]
            username = self._config_get_required('username')
            msg = "Authenticating user '{user}' with database '{db}'."
            logger.debug(msg.format(user=username, db=db_auth))
            db_auth.authenticate(
                username,
                self._config_get_required('password'),
                mechanism=AUTH_SCRAM_SHA_1)
        elif auth_mechanism in (AUTH_SSL, AUTH_SSL_x509):  # pragma no cover
            certificate_subject = get_subject_from_certificate(
                expanduser(self._config_get_required('ssl_certfile')))
            logger.debug("Authenticating: user={}".format(certificate_subject))
            db_external = self.client['$external']
            db_external.authenticate(
                certificate_subject, mechanism='MONGODB-X509')

    def logout(self):
        auth_mechanism = self._config_get_required('auth_mechanism')
        if auth_mechanism == AUTH_SCRAM_SHA_1:
            db_auth = self.client['admin']
            db_auth.logout()
        elif auth_mechanism in (AUTH_SSL, AUTH_SSL_x509):  # pragma no cover
            db_external = self.client['$external']
            db_external.logout()
        elif auth_mechanism == AUTH_NONE:
            pass
        else:
            raise_unsupported_auth_mechanism(auth_mechanism)