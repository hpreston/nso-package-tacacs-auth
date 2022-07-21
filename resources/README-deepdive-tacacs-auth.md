# How the External Authentication Works
This document is a deep dive under the hood into the tacacs-auth service and how it works.  This write-up assumes the following: 

* The TACACS server being used has already been setup correctly. (See [Preparing TACACS Server - Cisco ISE](README-setup-tacacs-ise.md))
* The tacacs-auth package service has already been installed to the NSO instance, and the NSO server has had external authentication with the script in the service configured.  For details on installation and setup, see [How to Deploy and Use the tacacs-auth Service](README-tacacs-auth-installation.md)

## Configuring the TACACS Host(s) and Shared Secret
Before NSO can perform external authentication to the TACACS server, it needs to know the address of the host as well as the shared-secret to use when communicating.  Rather than baking these into the script, or requiring they be set on the underlying Linux host running NSO, these values are stored in the NSO CDB and read from it.  

They are configured in NSO like this

```
tacacs-auth host 10.224.0.16
tacacs-auth host 10.224.0.17
tacacs-auth secret MyTACACSSecret
commit
```

Note that more than one TACACS host can be configured.  The external authentication script will attempt to authenticate with the hosts in the order they are stored in the CDB.  If a successfull authentication is achieved on a host, that host will be used for authorizing the user.  If an attempt to authenticate to a host fails for any reason, the next host in the list will be tried.  If all hosts fail authentication, authorization is skipped, and the overall external authentication will fail.

## Testing the `nso_extauth_tacacs.py` script
The external authentication script can be run directly, and not as part of an authentication request.  

Log into the NSO host server, and navigate to the NSO packages directory.  In this example, packages for NSO are located in `/var/opt/ncs/packages`

```bash
cd /var/opt/ncs/packages

# Look and verify the tacacs-auth package is listed 
ls -l
total 0
drwxr-xr-x 8 1001 1001 160 Aug  4 13:02 tacacs-auth
```

Within the `tacacs-auth` package directory you'll see all the code for the package.  You'll see two directories related to running the script.

* `python` - this directory holds all the Python code for the package, including the external authentication script 
* `pyvenv` - this is the Python virtual environment that has the requirements for the external authentication script installed 

```
# Within the package directory you'll find the python
ls -l tacacs-auth/
total 12
-rw-r--r-- 1 1001 1001 750 Aug  4 13:02 README
-rw-r--r-- 1 root root 562 Aug  5 20:10 build-meta-data.xml
drwxr-xr-x 2 root root  29 Aug  4 15:13 load-dir
-rw-r--r-- 1 1001 1001 390 Aug  4 13:02 package-meta-data.xml
drwxr-xr-x 3 1001 1001  25 Aug  4 15:18 python  <--- Python code for the package
drwxr-xr-x 6 root root  87 Aug  4 15:13 pyvenv  <--- Python virtual environment 
drwxr-xr-x 4 1001 1001  70 Aug  4 13:59 src
drwxr-xr-x 2 1001 1001  38 Aug  4 13:02 templates
drwxr-xr-x 3 1001 1001  38 Dec 21  2020 test
ls -l tacacs-auth/python/
total 0
drwxr-xr-x 2 1001 1001 114 Aug  4 17:51 tacacs_auth
```

> Note: See the package [installation and setup document]((README-tacacs-auth-installation.md)) for details on the Python requirements and virtual environment.

The external authentication script is located in the Python module directory `tacacs_auth` under the `python` directory.  The script is called `tacacs_ext_auth.py`

> Note: Python modules can't have `-`'s in the name. So the NSO service of `tacacs-auth` has a Python module/folder name of `tacacs_auth`

```bash
ls -l tacacs-auth/python/tacacs_auth/

total 20
-rw-r--r-- 1 1001 1001    0 Dec 21  2020 __init__.py
-rw-rw-r-- 1 1001 1001  537 Aug  5 20:35 logger.conf
-rw-r--r-- 1 1001 1001 2755 Aug  4 13:02 main.py
-rwxrwxr-x 1 1001 1001 7345 Aug  5 20:34 tacacs_ext_auth.py  <--- Python external authentication script
```

Test the script by running it from the command line.  When you run it, the script waits for the credentials to be provided for testing.  The format for the credentials is dictated by NSO and discussed in the NSO Admininstration Guide (`The AAA Infrastructure > Authentication > External authentication`)

> ... and pass the username and the clear text password on stdin using the string notation: `"[user;password;]\n"`.
>
> For example if user "bob" attempts to login over SSH using the password "secret", and external authentication is enabled, NSO will invoke the configured executable and write `"[bob;secret;]\n"` on the stdin stream for the executable.
> 
> ***NOTE: The string entered by NSO is `[bob;secret;]` followed by **ENTER**.  The double quotes in the guide are NOT entered, and the `\n` indicates the **ENTER**.***

Here is an example of a successful authentication test for a user who is authorized for both `ncsadmin` and `ncsoper` groups.

```bash
./tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py   <-- Run the script
[jdoe;CORRECTPASSWORD;]                               <-- The credentials are typed
accept ncsadmin ncsoper 1004 1004 /tmp                <-- The results are returned
```

What if a wrong password is provided.

```bash
./tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py   <-- Run the script 
[jdoe;WRONGPASSWORD;]                                 <-- The wrong password
reject Authentication Failed                          <-- The results are returned
```

What is an invalid username is provided? 

```bash
./tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py   <-- Run the script 
[notauser;NOTAPASSWORD;]                              <-- A user who does not exist
reject Authentication Failed                          <-- The results are returned
```

What about a user and password that are correct, but who aren't authorized for NSO?

```bash
./tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py   <-- Run the script 
[bsmith;BSMITHSPASSWORD;]                             <-- A user lacks NSO authorization
reject Authentication Failed                          <-- The results are returned
```

As you can see, the external authentication script works when run independently. 

> Note: The format of the successful external authentication is described in the NSO admin guide as well.  
> 
> `accept $groups $uid $gid $supplementary_gids $HOME\n`
> 
> So in our example of `accept ncsadmin ncsoper 1004 1004 /tmp` the user is a member of 2 groups, and will have their home directory set to `/tmp`.  
>
> The `uid` and `gid` of `1004` are set statically to this value at this time.


## Code Walkthrough
You can view the full code for [`tacacs_ext_auth.py`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py) within the repository.  This walkthrough isn't intended to be a full review of the script, but does highlight key or interesting parts.  The script itself has comments to describe what is going on. 

### The code entry point
Executing the script will run the [`if __name__ == "__main__":`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py#L169) condition.  This is where the logic flow for the script happens. 

First, the TACACS details are looked up from the NSO CDB.  If this fails, the script will not continue.

```python
if __name__ == "__main__":
    # Retrieve TACACS host and secret from NSO CDB
    hosts, secret = lookup_tacacs_auth_details()
```

Next, the script waits for the incoming user credentials to be entered as stdin. Either from NSO or the user directly during a test.  The credential string is then parsed into username and password.

```python
    # Read incoming credentials from NSO
    logger.info("Reading credentials from NSO")
    credentialstring = sys.stdin.readline()
    username, password = parse_credentialstring(credentialstring)
    logger.info(f"username={username} password=***********")

```

With the credentials and TACACS host(s), the script then attempts to find a host that will successfully authenticate the user.  

```python
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

```

After completing authentication, or exhausting all options, an authorization request is made. 

> The result of authentication is part of the authorization process, so if authentication did fail for all conifgured TACACS hosts, authorization will be skipped.

```python
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
```

With both authentication and authorization run, the result string is created.  Even a failed authentication or authorization will result in a result string being created.  

```python
    # Create final result string for NSO
    result = build_result(authen_result, authz_result, groups)

    # Log results of authentication attemp
    logger.info(f"Authentication result: '{result}'")
```

The result string is finally printed to stdout for NSO to retrieve and process.

```python
    # Print results to screen for NSO to process
    print(result)
```

### Retrieving the TACACS host details from the CDB 
Before any authentication can be done, the TACACS host and secret must be retrieve from NSO.  The function [`lookup_tacacs_auth_details`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py#L169) does this. 

```python
def lookup_tacacs_auth_details():
    """Retrieve the tacacs host and secret stored within NSO"""

    # Create NCS connection to read tacacs host details
    logger.info("Connecting to NSO to retrieve tacacs-auth details")
```

In order to lookup details from NSO, a `root` object is needed.  To do so: 

1. A Maapi connection is made to NSO
1. A user session is opened
1. A read-only transaction is started 
1. A root object is created

```python
    m = ncs.maapi.Maapi()
    m.start_user_session("tacacsadmin", "system", [])
    trans = m.start_read_trans()
    root = ncs.maagic.get_root(trans)
```

With the root object created, it is a simple action to lookupo the secret and host values from the CDB. 

```python
    # TACACS Server Details
    secret = root.tacacs_auth.secret
    hosts = root.tacacs_auth.host
    logger.info(f"tacacs hosts = {[host for host in hosts]}")
    logger.debug(f"tacacs secret: {root.tacacs_auth.secret}")
```

If no hosts have been configured or a secret wasn't set, the script will immediately error and exit.

```python
    if not hosts or not secret:
        error_message = "❌🛑 Error: Configuration for 'tacacs-auth host' and/or 'tacacs-auth secret' not found in NSO."
        logger.error(error_message)
        print(error_message)
        exit(1)
```

The function returns the tacacs hosts (as a list) and secret values as a tuple.

```python
    return (hosts, secret)
```

### Authenticating Users with TACACS
The Python library [`tacacs_plus`](https://gitlab.systems.cll.cloud/python-libraries/python_tacacs_plus) is used perform TACACS operations.  This source for this library is from [https://github.com/ansible/tacacs_plus](https://github.com/ansible/tacacs_plus) and uses the [TACACS RFC 8907](https://datatracker.ietf.org/doc/html/rfc8907) to build an open source Python library for TACACS communications.  

The function [`authenticate_user`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py#L84) handles the processing of the authentication request/response.

```python
def authenticate_user(host, secret, username, password, port=49):
    """Send a TACACS Authentication request for a user. Return result and message"""

```

A `TACACSClient` object is created for communicating with the host.

```python
    client = TACACSClient(host=host, port=port, secret=secret, timeout=10)
```

Initial values for the `result`, and `message` return values are set. The "default" result is a failed authentication.

```python
    result, message = False, ""
```

The authentication attempt can raise a series of errors depending on if the host is reachable, the secret is correct, or if the user authenticated successfully.  So the step is wrapped in a `try..expect` block.

```python
    logger.info(f"Sending Authentication request to {host} for username {username}")
    try:
        authen = client.authenticate(username, password)
```

A successful authentiction will set a message and change the result.  A failed authentication will set an appropriate message.

```python
        if authen.valid:
            message = "✅ Authentication Successful!"
            result = True
        else:
            message = "❌🛑 Error: Authentication Failed!"
```

Another function [`process_tacacs_error`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py#L67) was written to identify and provide useful messages for different errors.

```python
    except Exception as error:
        message = process_tacacs_error(error)
```

Finally the authentication result and message are returned.

```python
    return (result, message)
```

### Authorizing a User for NSO groups/access
The function [`authroize_user`](packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py#L103) follows a similar structure to the `authenticate_user` function.  Comments in line should explain any details needed. 

