## Troubleshooting External Authentication with Logs

You will troubleshoot failed authentication or authorization from NSO the same way you would troubleshoot a failed TACACS authentication from a network device. For this project all the log messages related to TACACS+ authentication and authorization are logged to the same directory where NSO is storing its logs. If your installation uses different logging directory, the logging configuration in the script.

When troubleshooting, or exploring how the authentication process is working, there are three main places to look at (here we assume that TACACS+ docker container is used):

1. The TACACS server log - logs/tac_plus/tac_plus.log
2. The NSO user audit log - logs/audit.log 
3. The log for the authentication script logs/ncs-python-tacacs-auth.log

For the purpose of this project all the log files are placed to the NSO logs directory. Here is its content and comments:
```bash
(nso-venv) YGORELIK-M-C3GG:logs ygorelik$ ll
total 680
drwxr-xr-x  17 ygorelik  staff   544B Jul 20 14:15 .
drwxr-xr-x  19 ygorelik  staff   608B Jul 20 16:27 ..
-rw-r--r--   1 ygorelik  staff    14K Jul 21 10:53 audit.log     <-- The audit log
-rw-r--r--   1 ygorelik  staff   138K Jul 21 10:53 devel.log
-rw-r--r--   1 ygorelik  staff     0B Jul 19 16:53 localhost:8080.access
-rw-r--r--   1 ygorelik  staff   2.2K Jul 19 16:56 ncs-java-vm.log
-rw-r--r--   1 ygorelik  staff    37K Jul 21 10:53 ncs-python-tacacs-auth.log     <-- The script log
-rw-r--r--   1 ygorelik  staff     0B Jul 19 16:53 ncs-python-vm.log
-rw-r--r--   1 ygorelik  staff    40K Jul 21 10:53 ncs.log
-rw-r--r--   1 ygorelik  staff     8B Jul 19 16:53 ncserr.log.1
-rw-r--r--   1 ygorelik  staff    18B Jul 19 16:53 ncserr.log.idx
-rw-r--r--   1 ygorelik  staff    13B Jul 19 16:53 ncserr.log.siz
-rw-r--r--   1 ygorelik  staff     0B Jul 19 16:53 netconf.log
-rw-r--r--   1 ygorelik  staff   833B Jul 19 16:53 rollback10001
-rw-r--r--   1 ygorelik  staff   196B Jul 19 16:58 rollback10002
-rw-r--r--   1 ygorelik  staff     0B Jul 19 16:53 snmp.log
drwxr-xr-x   4 ygorelik  staff   128B Jul 21 12:19 tac_plus     <-- The server log directory
-rw-r--r--   1 ygorelik  staff    17K Jul 19 16:56 xpath.trace
```

And TACACS+ server log directory contains:
```bash
(nso-venv) YGORELIK-M-C3GG:logs ygorelik$ ll tac_plus/
total 8
drwxr-xr-x   4 ygorelik  staff   128B Jul 21 12:19 .
drwxr-xr-x  18 ygorelik  staff   576B Jul 21 12:18 ..
-rw-r--r--   1 ygorelik  staff   625B Jul 21 12:21 tac_plus.log  <-- The server connection and user authentication log
-rw-------   1 ygorelik  staff     0B Jul 21 12:19 tacwho.log
```

> Note the path of the NSO log directory could be different and depends on the NSO installation. In this case the script must be adjusted accordingly.

### Checking TACACS+ server log

The file tac_plus.log is bound to corresponding file on the running docker container. In case of successful authentication it will have these records:
```bash
Thu Jul 21 19:21:49 2022 [10]: connect from 172.17.0.1 [172.17.0.1]
Thu Jul 21 19:21:49 2022 [10]: login query for 'tacadmin' port python_tty0 from 172.17.0.1 accepted
```
In case of failure to authenticate:
```bash
Thu Jul 21 19:56:38 2022 [11]: connect from 172.17.0.1 [172.17.0.1]
Thu Jul 21 19:56:38 2022 [11]: login query for 'tacadmin' port python_tty0 from 172.17.0.1 rejected
Thu Jul 21 19:56:38 2022 [11]: login failure: tacadmin 172.17.0.1 (172.17.0.1) python_tty0
```
The keywords to look for are _accepted_ and _rejected_.

### Checking NSO `audit.log`
Cisco NSO generates a lot of logs by default. One of the log files is called `audit.log`. This file shows the results of successful and unsuccessful logins to the system. It also indicates whether a login attempt was processed through local or external authentication. If we start a _tail_ command on `audit.log` and then attempt to login we can see what details are shown.
```bash
tail -f /log/audit.log
```

First, a login attempt with the local `admin` account (no external authentication required):

```
<INFO> 19-Jul-2022::16:56:18.084 YGORELIK-M-C3GG ncs[71858]: audit user: admin/45 assigned to groups: admin,staff,everyone,localaccounts,_appserverusr,_appserveradm,_lpadmin,com.apple.access_screensharing,access_bpf,com.apple.sharepoint.group.1,_appstore,_lpoperator,_developer,_analyticsusers,com.apple.access_ftp,com.apple.access_ssh
<INFO> 19-Jul-2022::16:56:18.084 YGORELIK-M-C3GG ncs[71858]: audit user: admin/45 created new session via cli from 127.0.0.1:0 with console
```

Next, a login attempt with an externally authenticated user:
```
<INFO> 21-Jul-2022::10:50:10.665 YGORELIK-M-C3GG ncs[71858]: audit user: tester/0 external authentication succeeded via cli from 127.0.0.1:59012 with ssh, member of groups: admin,private
<INFO> 21-Jul-2022::10:50:10.666 YGORELIK-M-C3GG ncs[71858]: audit user: tester/0 logged in via cli from 127.0.0.1:59012 with ssh using external authentication
<INFO> 21-Jul-2022::10:50:10.675 YGORELIK-M-C3GG ncs[71858]: audit user: tester/101 assigned to groups: admin,private
<INFO> 21-Jul-2022::10:50:10.675 YGORELIK-M-C3GG ncs[71858]: audit user: tester/101 created new session via cli from 127.0.0.1:59012 with ssh
```

And lastly, a failed authentication.  Notice how the username is NOT included in the log.  This is done by NSO for security reasons.  

```
<INFO> 21-Jul-2022::10:53:35.654 YGORELIK-M-C3GG ncs[71858]: audit user: [withheld]/0 external authentication failed via cli from 127.0.0.1:59196 with ssh:  Authentication Failed
<INFO> 21-Jul-2022::10:53:35.654 YGORELIK-M-C3GG ncs[71858]: audit user: [withheld]/0 local authentication failed via cli from 127.0.0.1:59196 with ssh: no such local user
<INFO> 21-Jul-2022::10:53:35.654 YGORELIK-M-C3GG ncs[71858]: audit user: [withheld]/0 login failed via cli from 127.0.0.1:59196 with ssh: No such local user
```

### Checking the script log
The script _tacacs_auth.py_ produces many log messages that can be used for troubleshooting external authentication and authorization failures. The default loging level is INFO, which produces minimal number of lines, but user might want to change it to DEBUG (more messages) or ERROR (errors and exceptions only) to get comfortable level of information. 

All the script log messages are logged to a file `./logs/ncs-python-tacacs-auth.log`. 
If we tail this file, we can see what information is logged there.  

```
tail -f ./logs/ncs-python-tacacs-auth.log 
```

> NOTE. Local authentication attempts are NOT running the external authentication script, and therefore will have no log messages in this file.

A successful external authentication with logging.INFO level enabled will look like this:
```
21/07/2022 10:50:10.570 tacacs_auth.py:185 INFO: External user attempts to login: username=tester, password=***********
21/07/2022 10:50:10.571 tacacs_auth.py:97 INFO: Sending Authentication request to 127.0.0.1:55000
21/07/2022 10:50:10.658 tacacs_auth.py:120 INFO: Sending Authorization request to 127.0.0.1
21/07/2022 10:50:10.663 tacacs_auth.py:192 INFO: User tester authorized for groups: admin, private
21/07/2022 10:50:10.663 tacacs_auth.py:205 INFO: Authentication result: 'accept admin private 1004 1004 /tmp'
```

Here is how failed authentication looks like: 

```
20/07/2022 14:59:49.753 tacacs_auth.py:185 INFO: External user attempts to login: username=tacadmin, password=***********
20/07/2022 14:59:49.753 tacacs_auth.py:97 INFO: Sending Authentication request to 127.0.0.1:55000
20/07/2022 14:59:49.757 tacacs_auth.py:199 INFO: User tacadmin failed authentication.
20/07/2022 14:59:49.757 tacacs_auth.py:205 INFO: Authentication result: 'reject Authentication Failed'
```

The log messages here show that Authentication failed, and Authorization was skipped because of that failure.  The final result is a reject.

If the TACACS server is down:
```
21/07/2022 10:53:35.653 tacacs_auth.py:97 INFO: Sending Authentication request to 127.0.0.1:55000
21/07/2022 10:53:35.653 tacacs_auth.py:110 ERROR: Exception error: Connection refused to TACACS server
21/07/2022 10:53:35.654 tacacs_auth.py:199 INFO: User tester failed authentication.
21/07/2022 10:53:35.654 tacacs_auth.py:205 INFO: Authentication result: 'reject Authentication Failed'
```
The log shows ERROR message "Connection refused to TACACS server".