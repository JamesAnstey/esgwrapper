
Workflow:

- copy code to the ESGF server using `server_sync.py send`

- ssh to the ESGF server 

- `source setup.py` in repo dir

- create a working dir

- copy config-datasets.yaml into the working dir and edit it

- run `./publish.py -m` to generate mapfiles (activate correct env first)

- run `./publish.py -p` to publish (activate correct env first)

- good idea to have search_esgf session open in parallel (e.g. on science) to check progress, this is totally independent of running the publisher

Note, the envs for mapfile generation & publishing are different

Calling without args, it will check the available datasets. Useful to check what can be published.

Add check of already-published datasets (using search_esgf).

