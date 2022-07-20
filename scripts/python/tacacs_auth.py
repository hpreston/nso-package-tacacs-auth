#!/usr/bin/env python
"""
Cisco NSO External Authentication with TACACS+ Script:

    * Requires configuration within ncs.conf, such as

        <external-authentication>
            <enabled>true</enabled>
            <executable>./scripts/python/tacacs_auth.py</executable>
        </external-authentication>
        <auth-order>external-authentication local-authentication pam</auth-order>

    * Reads TACACS+ servers configuration - host, port, and secret, - from CDB

    * Expects username and password to be sent to stdin in format
        * [username;password;]

    * The script explicitly uses the Python interpreter from env
      created for the service, because this script is called outside a normal
      service context.  As an alternative, the requirements for this service could 
      be installed in the default Python instance on the NSO server.
"""

import ncs
import _ncs

import logging
import sys
import os
from tacacs_plus.client import TACACSClient
import socket

# Setup logger
logdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../logs")
logname = os.path.join(logdir, "ncs-python-tacacs-auth.log")
if not os.path.isdir(logdir):
    os.mkdir(logdir)

logging.basicConfig(filename=logname,
                    filemode='a+',
                    format='%(asctime)s.%(msecs)02d %(filename)s:%(lineno)s %(levelname)s: %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


class TacacsConfig(object):
    def __init__(self, server_, port_, secret_):
        self.host = server_
        self.port = port_
        self.secret = secret_


def lookup_tacacs_server_config():
    """Retrieve the tacacs host and secret stored within NSO"""

    # Create NCS connection to read tacacs host details
    logger.debug("Connecting to NSO to retrieve tacacs servers configuration")
    with ncs.maapi.single_read_trans('admin', 'system') as trans:
        m = ncs.maapi.Maapi()
        m.install_crypto_keys()
        root = ncs.maagic.get_root(trans)

        # TACACS Servers Details
        tacacs_servers = []
        for config in root.tacacs_config__tacacs:
            pswd = _ncs.decrypt(config.secret)
            tc = TacacsConfig(config.host, config.port, pswd)
            tacacs_servers.append(tc)
            logger.debug(f"TACACS server: host={tc.host}, port={tc.port}, secret={tc.secret}")

    return tacacs_servers


def process_tacacs_error(error_):
    """Provide useful errors to the common exceptions raised by the TACACSClient"""

    if isinstance(error_, ValueError):
        msg = "Error performing authentication. Provided user credentials or TACACS secret incorrect."
    elif isinstance(error_, socket.gaierror):
        msg = "Unable to find TACACS server"
    elif isinstance(error_, ConnectionRefusedError):
        msg = "Connection refused to TACACS server"
    elif isinstance(error_, ConnectionResetError):
        msg = "Connection reset by TACACS server"
    else:
        msg = f"Error: {error_}"

    return msg


def authenticate_user(servers_, username_, password_):
    # Attempt authenticating to all tacacs servers
    for tac_server in servers:
        client = TACACSClient(host=tac_server.host, port=tac_server.port,
                              secret=tac_server.secret, timeout=10)
        logger.info(f"Sending Authentication request to {tac_server.host}:{tac_server.port}")
        try:
            authen = client.authenticate(username, password)
            authenticated = authen.valid
            if authenticated:
                message = "Authentication Successful!"
            else:
                message = "Authentication Failed!"
            logger.debug(message)
            return authenticated, tac_server

        except Exception as error:
            message = process_tacacs_error(error)
            logger.error(f"Exception error: {message}")
            # Connection failed, try another server
    return False, None


def authorize_user(tac_server, username_):
    """Send TACACS Authorization request for a user. Return result, message, and groups list"""

    response, msg, member_of = False, "", []
    client = TACACSClient(host=tac_server.host, port=tac_server.port, secret=tac_server.secret, timeout=10)
    logger.info(f"Sending Authorization request to {tac_server.host}")
    try:
        author = client.authorize(username_, arguments=[b"service=nso", b"cmd="])
        if author.valid:
            member_of = retrieve_authz_groups(author.arguments)
            if member_of:
                response = True
                msg = "Authorization Successful!"
            else:
                msg = "Authorization successful, but no NSO authentication group assigned to the user"
        else:
            msg = "Error: Authorization Failed!"

    except Exception as error:
        msg = process_tacacs_error(error)

    return response, msg, member_of


def retrieve_authz_groups(arguments):
    """Parse and return the nso:group list from Authorization arguments."""

    nso_groups = []
    for argument in arguments:
        # Convert bytes to stgring
        argument = argument.decode("utf-8")
        # Only process the arguments with a key of "nso:group"
        if "groups" in argument:
            # Add the group name from argument to the list
            nso_groups.extend(argument.split("=")[1].split())

    return nso_groups


def build_result(authenticated, authorized, nso_groups):
    """Create appropriate result string for NSO to complete external auth"""

    if not authenticated:
        response = "reject Authentication Failed"
    elif not authorized:
        response = "reject Authorization Failed"
    else:
        response = f"accept {' '.join(nso_groups)} 1004 1004 /tmp"

    return response


def parse_credential_string(credentials):
    """Parse username and password input from NSO as part of external auth"""

    credentials_list = credentials.split(";")
    user = credentials_list[0][1:]
    pswd = credentials_list[1]
    return user, pswd


if __name__ == "__main__":
    # Retrieve TACACS host and secret from NSO CDB
    servers = lookup_tacacs_server_config()

    # Read incoming credentials from NSO
    logger.debug("Reading credentials from NSO")
    user_credentials = sys.stdin.readline()
    # user_credentials = "[tester;tester;]"
    username, password = parse_credential_string(user_credentials)
    logger.info(f"External user attempts to login: username={username}, password=***********")

    authen_result, server = authenticate_user(servers, username, password)
    if authen_result:
        # Attempt authorization on the host with succeeded authentication
        author_result, authz_message, groups = authorize_user(server, username)
        if author_result and groups:
            logger.info(f"User {username} authorized for groups: {', '.join(groups)}")
        else:
            logger.info(authz_message)
            logger.info(f"User {username} failed authorization.")
    else:
        author_result = False
        groups = []
        logger.info(f"User {username} failed authentication.")

    # Create final result string for NSO
    result = build_result(authen_result, author_result, groups)

    # Log results of authentication attemp
    logger.info(f"Authentication result: '{result}'")

    # Print results to screen for NSO to process
    print(result)
