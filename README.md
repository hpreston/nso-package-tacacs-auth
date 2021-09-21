# NSO TACACS Authentication
This project focuses on enabling TACACS based external authentication for Cisco NSO.  

## Background 
External Authentication for is accomplished by creating some script that NSO will call whenever someeone tries to login.  NSO simply passes the credentials provided to the script as a standard input in the forom of `"[user;password;]\n"` and expects an output such as `accept ncsadmin ncsoper 1004 1004 /tmp`.  In this example the user will be placed into the groups `ncsadmin` and `ncsoper`.  

What is done in the external authentication script is irrelevant to NSO, all that matters is the output.  For example, this script would work fine, but result in any provided credentials passing authentication and being authorized for both admin and operator roles. 

```python
#! /usr/bin/env python3 

accept = "accept ncsadmin ncsoper 1004 1004 /tmp"
print(accept)
```

> For more details on how external authentication works, see the documentation at `doc/html/nso_admin_guide/ug.aaa.External_authentication.html` (docs included with NSO installation).  Also, a presentation on access control with NSO is included in the repo [NSODevDays2020-NSO-Access-Control-Role-based-and-Resource-based-Access.pdf](resources/NSODevDays2020-NSO-Access-Control-Role-based-and-Resource-based-Access.pdf)

The goals for this project is to leverage the same AAA infrastructure used for network device administrator for NSO, namely TACACS (Cisco ISE).  The Python library [`tacacs_plus`](https://github.com/ansible/tacacs_plus) is used to communicate with the TACACS server. 

## Guides
The following detailed guides have been written on how to use this service. 

* [Preparing TACACS Server - Cisco ISE](README-setup-tacacs-ise.md): How to setup Cisco ISE to receive and responde to NSO authentication requests from this service.
* [How the External Authentication Works](README-deepdive-tacacs-auth.md): A technical deep dive into this service works.
* [How to Deploy and Use the tacacs-auth Service](README-tacacs-auth-installation.md): A walkthrough on how to install the tacacs-auth service to NSO
* [Troubleshooting External Authentication with Logs](README-troubleshooting-logs.md): A review of how to troubleshoot the external authentication with logs

## Basic External Authentication with TACAS Usage
### Configuring the TACACS Host(s) and Shared Secret
Before NSO can perform external authentication to the TACACS server, it needs to know the address of the host as well as the shared-secret to use when communicating.  Rather than baking these into the script, or requiring they be set on the underlying Linux host running NSO, these values are stored in the NSO CDB and read from it.  

They are configured in NSO like this

```
tacacs-auth host 10.224.0.16
tacacs-auth host 10.224.0.17
tacacs-auth secret MyTACACSSecret
commit
```

Note that more than one TACACS host can be configured.  The external authentication script will attempt to authenticate with the hosts in the order they are stored in the CDB.  If a successfull authentication is achieved on a host, that host will be used for authorizing the user.  If an attempt to authenticate to a host fails for any reason, the next host in the list will be tried.  If all hosts fail authentication, authorization is skipped, and the overall external authentication will fail.

### Enabling External Authentication in `ncs.conf`
NSO needs to be enabled to use/try external authentication within the `ncs.conf` file. This is done within the `<aaa></aaa>` configuration block, and requires two settings. 

1. `<enabled>true</enabled>` 
1. `<executable>scriptpath.py</executable>`
    * The path used here must be the exact path to the `tacacs_ext_auth.py` script located within the packages directory.

Here is an example of the relevant parts of the `ncs.conf` file. 

```xml
<?xml version="1.0"?>
<ncs-config xmlns="http://tail-f.com/yang/tailf-ncs-config">
  <aaa>
    <external-authentication>
      <enabled>true</enabled>
      <executable>/var/opt/ncs/packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py</executable>
    </external-authentication>
    <local-authentication>
      <enabled>true</enabled>
    </local-authentication>
  </aaa>
</ncs-config>  
```

> Note: in the example `local-authentication` is also enabled.  This could be disabled once the external-authentication is configured, tested, and trusted.  Or you can leave `local-authentication` enabled as a secondary access method.

### Logging into NSO with External Authentication
With the `tacacs-auth` configured, and `ncs.conf` configured to enable external authentication, we can now try to log into NSO with the external credentials. 

First, we'll try logging in with a user who has both `ncsadmin` and `ncsoper` writes. 

```
ssh jdoe@nso
jdoe@nso's password: 

# Try a basic "show" command
jdoe@ncs# show packages package oper-status 
packages package tacacs-auth
 oper-status up

# Let's see what configuration options exist
jdoe@ncs# config terminal 
Entering configuration mode terminal
jdoe@ncs(config)# ?
Possible completions:
  aaa                           AAA management
  alarms                        Alarm management
  alias                         Create command alias.
  cluster                       Cluster configuration
  compliance                    Compliance reporting
  customers                     Customers using services
  devices                       The managed devices and device
                                communication settings
  high-availability             Configuration, status and actions
                                concerning NSO Built-in HA
  java-vm                       Control of the NCS Java VM
  nacm                          Access control
  ncs-state                     NCS status information
  packages                      Installed packages
```

So `jdoe` looks to have full access for read and config actions.  

What about a user with only `ncsoper` (read-only) rights.  

```
ssh bsmith@nso
bsmith@nso's password: 

# Try a basic "show" command
bsmith@ncs# show packages package oper-status 
packages package tacacs-auth
 oper-status up

# Let's see what configuration options exist
bsmith@ncs# config terminal 
Entering configuration mode terminal
bsmith@ncs(config)# ?
Possible completions:
  user              User specific command aliases and default CLI
                    session parameters
  webui             Web UI specific configuration
  ---               
  abort             Abort configuration session
  activate          Activate a statement
  annotate          Add a comment to a statement
  clear             Remove all configuration changes
  commit            Commit current set of changes
```

User `bsmith` only has `user` and `webui` listed.  These show up in the list due to how their models are setup, but attemps to actually configure something under them result in `access-denied`.

```
bsmith@ncs(config)# user test
Error: access denied
```