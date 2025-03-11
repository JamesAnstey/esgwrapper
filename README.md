
Workflow:

- clone repo and copy it to the ESGF server

- ssh to the ESGF server 

- create a working dir

- copy config-datasets.yaml into the working dir and edit it

- run `./publish.py -m` to generate mapfiles (activate correct env first)

- run `./publish.py -p` to publish (activate correct env first)

Note, the envs for mapfile generation & publishing are different

Calling without args, it will check the available datasets. Useful to check what can be published.

Add check of already-published datasets (using search_esgf).

