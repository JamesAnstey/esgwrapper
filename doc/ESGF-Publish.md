## **ESGF Publishing Guide**
Logan Macdonald - 2023 Aug

This guide will walk through how to publish data to the ESGF Network. Publishing has been configured to be run by `acrnpub`.

### Conda Environments
There are two conda environments used to publish:

- esgf-prep: the tools for generating the mapfiles for datasets.

- esgf-pub: the publisher that pushes records to the ESGF network

You can switch between environments using:
```
conda activate esgf-___
```

#### esgf-prep
The [esgprep](http://www.esgf.io/esgf-prepare/) toolbox contains several utilities to prepare data for publishing. Of note to us is generating [map files](http://www.esgf.io/esgf-prepare/mapfiles.html).

```
esgmapfile make --project PROJECT_ID /PATH/TO/SCAN/ --outdir /PATH/TO/MY_MAPFILES/
```

#### esgf-pub
The publisher is fairly straight forward, it accepts a mapfile and runs through the entire publishing process. The configurations for publishing are found under `~/.esg/esg.ini` .

```
esgpublish --project cmip6 --map /datalocal/mapfiles/files.to.publish.map --no-auth
```