## **ESGF Installation Guide**
Logan Macdonald - 2023 Dec

This guide will walk through how to install the ESGF software stack and the publisher.

### ESGF:

[esgf-docker](https://github.com/ESGF/esgf-docker/blob/master/docs/deploy-ansible.md) uses Ansible playbooks to deploy Docker Containers. Both of these will need to be installed on the host machine:

- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#installing-and-upgrading-ansible)
```
sudo apt install ansible
```
- [Docker](https://docs.docker.com/engine/install/ubuntu/)
```
sudo apt-get remove docker docker-engine docker.io containerd runc

sudo apt-get update
sudo apt-get install \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

The source code for ESGF Docker can be cloned with the following command:
```
git clone https://github.com/ESGF/esgf-docker.git
```

esgf-docker should be cloned inside `/datalocal`. Configuration for esgf-docker is placed in a directory `/config` which must be outside of esgf-docker, so this will be placed in `/datalocal` as well.

Refer to ESGF-config.md for how to setup the `/datalocal/config` directory.

Once configured the playbook can then be deployed using `sudo ansible-playbook -i /datalocal/config/inventory.ini /datalocal/esgf-docker/deploy/ansible/playbook.yml`

### Docker Containers
Once deployed you can view the list of deployed containers using:
`sudo docker container ls`

There should be the following:

```
CONTAINER ID   IMAGE                         COMMAND                  CREATED          STATUS          PORTS                  NAMES
ecd967c228c3   esgfdeploy/nginx:7dbc92a2     "/usr/local/bin/tini…"   32 minutes ago   Up 32 minutes   0.0.0.0:80->8080/tcp   proxy
19d5b36c75ea   esgfdeploy/nginx:7dbc92a2     "/usr/local/bin/tini…"   32 minutes ago   Up 32 minutes   8080/tcp               fileserver
c3ff565cd8b7   esgfdeploy/thredds:7dbc92a2   "/usr/local/bin/tini…"   32 minutes ago   Up 32 minutes   8080/tcp               thredds
```

You can interact with the containers by opening a bash shell inside them:
`sudo docker container exec -u root -it "container name" /bin/bash`

If any configuration changes need to be made, or the ESGF stack needs to be updated, the changes can be made and then the playbook is run again. 

### Publisher
The Publisher can be installed on the data node host outside of the ESGF containers. The publisher itself will be installed using conda environments. The official documentation can be found here: [esg-publish Read The Docs](https://esg-publisher.readthedocs.io/en/latest/).

---

(v5.1 OUT OF DATE BUT KEEPING FOR REFERENCE)

To install v5.1 of the publisher:

```
conda create -n esgf-pub -c conda-forge -c esgf-forge pip libnetcdf cmor autocurator esgconfigparser
conda activate esgf-pub

pip install esgfpid

conda install -c esgf-forge -c conda-forge esgcet
```

The publisher config is `~/.esg/esg.ini`

---
#### esg-publish v5.2
To install v5.2 of the publisher:
```
conda create -n esgf-pub520 -c conda-forge pip cmor
conda activate esgf-pub520
pip install esgcet
```

The config file is `~/.esg/esg.yaml`

Finally a certificate file is needed under `~/.globus`:
```
mkdir $HOME/.globus   # if not already present
myproxy-logon -s esgf-node.llnl.gov -l acrnpub -p 7512 -t 72 -o $HOME/.globus/certificate-file
```

#### esg-prep
Another conda environment is needed for `esgprep` which has conflicting dependencies with `esg-publish`. This is used for fetching CMOR tables and generation of mapfiles if needed.
```
conda create -n esgf-prep python=2.7
```

 Several dependencies should already be part of the basic python libraries but you can check with `python -c "import lib-name"` and `echo $?`. If any of them are missing install them with `pip install`.

```
python -c "import argparse"
python -c "import collections"
python -c "import datetime"
python -c "import ESGConfigParser'
python -c "import fnmatch'
python -c "import getpass"
python -c "import hashlib"
python -c "import importlib"
python -c "import logging"
python -c "import multiprocessing"
python -c "import os"
python -c "import pickle"
python -c "import re"
python -c "import shutil"
python -c "import sys"
python -c "import textwrap"
python -c "import unittest"
python -c "import gettext"
```
The following dependencies will need to be installed and then finally install esgprep:
```
pip install fuzzywuzzy
pip install hurry.filesize
conda install netCDF4
pip install requests
pip install tqdm
pip install treelib

pip install esgprep
```

**Fetch CMOR Tables**
You can fetch all CMOR tables with:
```
esgfetchtables
```
Or specify projects and output locations with:
```
esgfetchtables --project CMIP6 --table-dir <path>
```

**Generate Mapfile**
To generate mapfiles you can use the following command. It is possible mapfiles will instead be generated as part of data generation before being moves to the ESGF data node.
```
esgmapfile --project cmip6 --max-processes 4 --no-cleanup --outdir ./mapfiles /path/to/nc*
```