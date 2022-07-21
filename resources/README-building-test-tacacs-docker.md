## Building and Testing TACACS+ server on docker container

The TACACS+ server described in this document has very basic implementation, which is suited for testing purposes only.
In the production environment it is recommended to use Cisco ISE software.

### Building the TACACS+ docker container

Make sure the docker software is installed on your platform and the docker daemon is running. Then follow this procedure.

1. Pull existing docker image with the TACACS+ installation from [docker hub](https://hub.docker.com/r/llima3000/tacplus):

> $ docker pull llima3000/tacplus

2. Inspect the image for exposed ports. It is expected port 49 to be exposed.
```
$ docker image inspect llima3000/tacplus -f '{{ .Config.ExposedPorts }}'
map[49/tcp:{}]
```

3. In your working directory create TACACS configurations file _tac_plus.conf_. For testing purposes a copy of this file with configuration of multiple users and groups configured for usage with NSO is presented in this repository.

4. Create log directory ./logs/tac_plus, which will be used to see TACACS+ server log messages:
```
mkdir -p ./logs/tac_plus
```

5. Start the container:
```
$ docker run -td --name tacplus \
   -v ${PWD}/tac_plus.conf:/etc/tacacs+/tac_plus.conf \
   -v ${PWD}/logs/tac_plus:/var/log \
   -p 55000:49 \
   -e DEBUGLEVEL=16 \
   llima3000/tacplus
0a6bcee9d800f26be703696a72004785c72f98f30c40784a5664690665837f62
```

This command:
 - creates from docker image _llima3000/tacplus_ a docker container with the name _tacplus_
 - binds your TACACS+ configuration file to location on the server _/etc/tacacs+/tac_plus.conf_
 - binds your TACACS+ server logging file _./logs/tac_plus.log_ to loging file /var/log/tac_plus.log on the server
 - maps port 49 to local platform port 55000
 - sets server logging level
 The response should be a hash code of the running container, example:

6. Check the docker container’s port mapping:
```
$ docker ps
CONTAINER ID   IMAGE               COMMAND                  CREATED          STATUS          PORTS                   NAMES
0a6bcee9d800   llima3000/tacplus   "/bin/sh -c 'service…"   25 minutes ago   Up 25 minutes   0.0.0.0:55000->49/tcp   tacplus
```

7. Check the docker container IP address:
```
$ docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' tacplus
172.17.0.2
```
 
### Testing TACACS+ server with Python client

1. Install Python package _tacacs_plus_:
```
$ pip install tacacs_plus
```

Test installation with command: 
```
$ tacacs_client -h
```

2. Perform simple tests in bash shell:
```
$ tacacs_client -v -H 127.0.0.1 -p 55000 -k tacacs123 -u tacadmin authenticate --password tacadmin
status: PASS
```

3. Write and execute a simple Python script:
```
from tacacs_plus.client import TACACSClient
import socket

cli = TACACSClient('localhost', 55000, 'tacacs123', timeout=10, family=socket.AF_INET)
authen = cli.authenticate(’tacadmin, ‘password’)
print(authen.valid)
```
Expected output is _True_. If so, your TACACS+ server and client are fully functional and ready for your software development and testing.

