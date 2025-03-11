
Workflow:

- clone repo and copy it to the ESGF server

- ssh to the ESGF server 

- create a working dir

- copy config-datasets.yaml into the working dir and edit it

- run `./publish.py -m` to generate mapfiles (activate correct env first)

- run `./publish.py -p` to publish (activate correct env first)

Note, the envs for mapfile generation & publishing are different

