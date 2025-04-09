## **ESGF Configuration Guide**
Logan Macdonald - 2023 Dec

This guide will walk through CCCma's configuration for ESGF-docker. 

### Configuration

All configuration is done through files placed in the `/datalocal/config` directory. The following instructions will highlight each config file and its purpose: 

`inventory.ini` 

Defines the hosts to deploy to. `ansible_connection-local` deploys the stack to the host you are working on.
```
[data]
crd-esgf-drc.ec.gc.ca   ansible_connection=local
```
`playbook.yml` 

Initiates the deployment, we have added a variable to ensure paython3 is used.
```
---

#####
## This playbook deploys the configured hosts as ESGF nodes using Docker containers
#####

- hosts: all
  become: true
  roles:
    - docker
    - { name: data, tags: [data] }
    - { name: index, tags: [index] }
    - proxy
  vars:
    ansible_python_interpreter: /usr/bin/python3
```
`/host_vars/crd-esgf-drc.ec.gc.ca`

This sets variable for the desired host, in this case enabling SSL
```
## OPTIONAL: Enabling SSL for the server

nginx_config_template: ssl.proxy.conf.j2

published_port_http: 80
published_port_https: 443

### See: https://github.com/ESGF/esgf-docker/blob/master/docs/deploy-ansible.md#enabling-ssl
```

`/group_vars/all.yml`

Defines various variables for deployment. The esgf-docker image to be used is an imutable version of esgf-docker, the image tag is the commit hash used at the time of deployment (the list of commits can be found [here](https://hub.docker.com/r/esgfdeploy/thredds/tags)). Included is the variables to enable log forwarding to CMCC:
```
# Use the images that were built for a particular commit
image_tag: c313c166
# If using an immutable tag, don't do unnecessary pulls
image_pull: false

logstash_enabled: true
logstash_stats_server: ophidialab.cmcc.it
logstash_stats_port: 5045
```

`/group_vars/data.yml` 

Defines the mapping between data locations on the host machine and locations in the container. The container filesystem is what is presented to index nodes. 

`/docker/main.yml`

This installs dependencies for docker and deploys the containers calling the appropriate playbooks for each. Because we are deploying on linux and have installed much of the dependencies ourselves this has to be modified.

### SSL Certs
The certificates for enabling SSL are placed under `/esg/config/proxy/ssl`. They must be owned by the ESGF user (1000:1000). They include:

`proxy.crt` the SSL certificate for the server and the ChainBundle

`proxy.key` the SSL private key for the server

### Deploying the Containers

As several changes have been made to the default esgf-docker configuration, the above config files need to be added to the esgf-docker source. `datalocal/config` has the script `bin/load_conf` to move each to their needed location:
```
./datalocal/config/bin/load_conf
```

The playbook can then be deployed using `sudo ansible-playbook -i /datalocal/config/inventory.ini ./deploy/ansible/playbook.yml` or the deploy scrip foun in `bin`:
```
./datalocal/config/bin/deploy_esgf
```

### Docker Commands
Once deployed you can view the list of deployed containers using:
`sudo docker container ls`

You can interact with the containers by opening a bash shell inside them:
`sudo docker container exec -it "container name" /bin/bash`

docker container inspect proxy --format "{{ .LogPath }}"


For testing we can stop and remove all containers with:
```
sudo docker container stop "NAME"
sudo docker system prune -a
```