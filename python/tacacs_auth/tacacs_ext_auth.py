#! /var/opt/ncs/packages/tacacs-auth/pyvenv/bin/python
"""
Cisco NSO External Authentication with TACACS Script: 

    * Configured within ncs.conf to run such as

        <external-authentication>
            <enabled>true</enabled> 
            <executable>${PACKAGES_DIRECTORY}/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py</executable>
        </external-authentication>

    * Reads TACACS host and secret from NCS

        tacacs-auth host [ 10.224.0.16 ]
        tacacs-auth secret secret

    * Expects username/password to be sent as stdin in format
        * [username;password;]

    * The sh-bang line at the top of this script explicitly uses the Python venv
      created for the service because this script is called outside of a normal 
      service context.  As an alternative, the requirements for this service could 
      be installed in the default Python instance on the NSO server.
"""

import ncs
import logging.config
import logging
import os
from tacacs_plus.client import TACACSClient
import socket
import sys


# Setup logger
logging.config.fileConfig(
    os.path.realpath(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
)
logger = logging.getLogger(__name__)


def lookup_tacacs_auth_details():
    """Retrieve the tacacs host and secret stored within NSO"""

    # Create NCS connection to read tacacs host details
    logger.info("Connecting to NSO to retrieve tacacs-auth details")
    m = ncs.maapi.Maapi()
    m.start_user_session("tacacsadmin", "system", [])
    trans = m.start_read_trans()
    root = ncs.maagic.get_root(trans)

    # TACACS Server Details
    secret = root.tacacs_auth.secret
    hosts = root.tacacs_auth.host
    logger.info(f"tacacs hosts = {[host for host in hosts]}")
    logger.debug(f"tacacs secret: {root.tacacs_auth.secret}")

    if not hosts or not secret:
        error_message = "❌🛑 Error: Configuration for 'tacacs-auth host' and/or 'tacacs-auth secret' not found in NSO."
        logger.error(error_message)
        print(error_message)
        exit(1)

    return (hosts, secret)


def process_tacacs_error(error):
    """Provide useful errors to the common exceptions raised by the TACACSClient"""

    if isinstance(error, ValueError):
        message = "❌🛑 Error performing authentication. Provided user credentials or TACACS secret incorrect."
    elif isinstance(error, socket.gaierror):
        message = "❌🛑 Unable to find TACACS host at address"
    elif isinstance(error, ConnectionRefusedError):
        message = "❌🛑 Unable to connect to TACACS host at address"
    elif isinstance(error, ConnectionResetError):
        message = "❌🛑 Connection refused by TACACS host. Is the requesting host configured as a network device on server?"
    else:
        message = f"❌🛑 Some other error: {error}"

    return message


def authenticate_user(host, secret, username, password, port=49):
    """Send a TACACS Authentication request for a user. Return result and message"""

    client = TACACSClient(host=host, port=port, secret=secret, timeout=10)
    result, message = False, ""
    logger.info(f"Sending Authentication request to {host} for username {username}")
    try:
        authen = client.authenticate(username, password)
        if authen.valid:
            message = "✅ Authentication Successful!"
            result = True
        else:
            message = "❌🛑 Error: Authentication Failed!"
    except Exception as error:
        message = process_tacacs_error(error)

    return (result, message)


def authorize_user(authen_result, host, secret, username, port=49):
    """Send a TACACS Authorization request for a user. Return result, message, and groups list"""

    result, message, groups = False, "", []

    # Check authentication result, only perform authorization if True
    if authen_result:
        client = TACACSClient(host=host, port=port, secret=secret, timeout=10)
        logger.info(f"Sending Authorization request to {host} for username {username}")

        try:
            author = client.authorize(username, arguments=[b"service=shell", b"cmd="])
            if author.valid:
                result = True
                message = "✅ Authorization Successful!"
                groups = retrieve_authz_groups(author.arguments)
            else:
                message = "❌🛑 Error: Authorization Failed!"

        except Exception as error:
            message = process_tacacs_error(error)

    else:
        message = "❌🛑 Authentication failed, Authorization not performed."

    return (result, message, groups)


def retrieve_authz_groups(arguments):
    """Parse and return the nso:group list from Authorization arguments."""

    groups = []
    for argument in arguments:
        # Convert bytes to stgring
        argument = argument.decode("utf-8")
        # Only process the arguments with a key of "nso:group"
        if "nso:group" in argument:
            # Add the group name from argument to the list
            groups.append(argument.split("=")[1])

    return groups


def build_result(authen_result, authz_result, groups):
    """Create appropriate result string for NSO to complete external auth"""

    if not authen_result:
        result = "reject Authentication Failed"
    elif not authz_result:
        result = "reject Authorization Failed"
    elif authen_result and authz_result:
        result = f"accept {' '.join(groups)} 1004 1004 /tmp"

    return result


def parse_credentialstring(credentialstring):
    """Parse username and password input from NSO as part of external auth"""

    credentialstring = credentialstring[:-2][1:]
    credentials = credentialstring.split(";")
    user = credentials[0]
    password = credentials[1]
    return (user, password)


if __name__ == "__main__":
    # Retrieve TACACS host and secret from NSO CDB
    hosts, secret = lookup_tacacs_auth_details()

    # Read incoming credentials from NSO
    logger.info("Reading credentials from NSO")
    credentialstring = sys.stdin.readline()
    username, password = parse_credentialstring(credentialstring)
    logger.info(f"username={username} password=***********")

    # Attempt authenticating to all tacacs hosts
    for host in hosts:
        authen_result, authen_message = authenticate_user(
            host, secret, username, password
        )
        # Check result - if success don't check other servers
        if authen_result:
            logger.info(authen_message)
            break
        else:
            logger.warning(authen_message)

    # Attempt authorization
    # The host that resulted in a successful authentication is the only one tested
    authz_result, authz_message, groups = authorize_user(
        authen_result, host, secret, username
    )

    # Log results of authorization
    if authz_result:
        logger.info(authz_message)
        logger.info(f"User {username} authorized for groups {', '.join(groups)}")
    else:
        logger.warning(authz_message)
        logger.warning(f"User {username} was failed authorization.")

    # Create final result string for NSO
    result = build_result(authen_result, authz_result, groups)

    # Log results of authentication attemp
    logger.info(f"Authentication result: '{result}'")

    # Print results to screen for NSO to process
    print(result)
