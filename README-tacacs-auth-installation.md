# How to Deploy and Use the tacacs-auth Service 
This guide discusses the unique aspects of installing and using this service for NSO.  A basic knowledge of how to install any NSO service or NED is assumed.  

# Installation using NSO in Docker 
The following instructions relate to installing and using the nso-tacacs-auth package with an NSO in Docker based solution. 

> These steps assume that the Docker image for the nso-tacacs-auth service/package has been created and already available within the container registry used for NSO in Docker.

## Including the `nso-tacacs-auth` package
Like any package to be included with NSO in Docker setups, simply add a file to the `includes/` directory where you want to include it. 

```
cat includes/nso-tacacs-auth 

# Contents of file
${PKG_PATH}nso-tacacs-auth/package:5.5-490
```

Just specify the version (ie tag) of the package image you want to include.

## Configuring tacacs-auth in the `testenv` 
If you'd like to enable TACACS authentication in your `testenv` for development, you can add the Environment Variables in the `NSO_EXTRA_ARGS` optional variable in the `Makefile`.  Here is an example: 

```
export NSO_EXTRA_ARGS ?= -e EXTERNAL_AUTH=true -e EXTERNAL_AUTH_EXECUTABLE=/var/opt/ncs/packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py
```

> Note: Be sure you have setup the development host you are working from in your TACACS server as a network device and applied proper policies or Authentication/Authorization requests will be rejected.

## Starting a Production Instance
To start a "production instance" of NSO with external authentication enabled simply provide the proper values for the `EXTERNAL_AUTH` and `EXTERNAL_AUTH_EXECUTABLE` envrionment variables when starting the container.  Something like this: 

```
docker run -itd --name nso \
  -v /data/nso:/nso \
  -v /data/nso-logs:/log \
  --net=host \
  -e SSH_PORT=2024 \
  -e EXTERNAL_AUTH=true \
  -e EXTERNAL_AUTH_EXECUTABLE=/var/opt/ncs/packages/tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py \
  my-prod-image:12345
```

> Note: Be sure you have setup the production host in your TACACS server as a network device and applied proper policies or Authentication/Authorization requests will be rejected.

# Manual Package/Service Installation 
The following instructions directions are for manual installation of the package in a typical local or system install of NSO. 

## Install the Service Package and Verify Operational Status
There is nothing direclty unique about installing the `tacacs-auth` package into NSO.  Simply placing the service directory within the configured NSO packages directory, and then restarting ncs, or a `packages reload` will have it loaded up. 

In this example, packages are located in the directory `/var/opt/ncs/packages` 

```
ls -l /var/opt/ncs/packages

drwxr-xr-x 8 1001 1001 160 Aug  4 13:02 tacacs-auth
```

And here we reload packages and checks status from within NSO. 

```
admin@ncs# packages reload 

reload-result {
    package tacacs-auth
    result true
}

admin@ncs# show packages package oper-status 

packages package tacacs-auth
 oper-status up
 ```

## Installing Python Requirement for External Authentication Script 
The `tacacs_ext_auth.py` script relies on the Python library `tacacs_plus`.  This library must be installed into the Python environment where the script runs in order to function.  The execution of this Python script is a little different from normal Python services, in that the execution of the script isn't done as part of an NSO commit or action call. Rather it is executed by NSO in response to authentication process.  There are a few different ways you could configure the Python environments for NSO to function for this use case.  These instructions will approach it this way: 

1. A Python virtual environment is created for the service and external authentication script
1. The requirements for the authentication are installed into this virtual environment 
1. The external authentication script (`tacacs_ext_auth.py`) is explicity configured to leverage this virtual environment within the sh-bang line

### Creating the Virtual Environment 
There is nothing specific to NSO for creating the virtual environment.  Simply use normal Python practices to create the venv.  You could place it anywhere on the NSO host, but in this example it is created within the packages directory. 

```
cd /var/opt/ncs/packages/tacacs-auth 

python3 -m venv pyvenv 
```

### Installing requirements into the Virtual Environment 
A `requirements.txt` file is included in the `tacacs-auth/src` directory.  This can be used to install the library. 

```
source pyvenv/bin/activate
pip install -f src/requirements.txt
```

### Setting the sh-bang line 
Change the path in the sh-bang line in the script file `tacacs-auth/python/tacacs_auth/tacacs_ext_auth.py` to use `python` from within the virtual environment directory.

```
cat python/tacacs_auth/tacacs_ext_auth.py | grep '#!'

#! /var/opt/ncs/packages/tacacs-auth/pyvenv/bin/python
```

> Note: If you want to test and verify that the virtual environment and requirements are working, see the **Testing the `nso_extauth_tacacs.py` script** section in [How the External Authentication Works](README-deepdive-tacacs-auth.md) guide.

## Enabling External Authentication in `ncs.conf` 
The final step to setting up external authentication is to enable the feature in `ncs.conf`.  This is done within the `<aaa></aaa>` configuration block, and requires two settings. 

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
