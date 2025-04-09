## **ClimRes 2.0**
Logan Macdonald - 2023 June 21

Technical infomation for the new ESGF server migrated to EDC Montreal.

### ESGF
```
Hostname:               eccc-esgf.collab.science.gc.ca
IP Address:             142.98.230.25

Domain Name (EN/FR):    crd-esgf-drc.ec.gc.ca   
```

### ESGF Structure
ESGF data is distributed among ten 100T partitions.
```
/dev/mapper/esgfa--LV-esgfa--LVM  100T   50T   46T  53% /esgA
/dev/mapper/esgfb--LV-esgfb--LVM  100T   50T   46T  53% /esgB
/dev/mapper/esgfc--LV-esgfc--LVM  100T   50T   46T  52% /esgC
/dev/mapper/esgfd--LV-esgfd--LVM  100T   50T   46T  53% /esgD
/dev/mapper/esgfe--LV-esgfe--LVM  100T   49T   46T  52% /esgE
/dev/mapper/esgff--LV-esgff--LVM  100T   50T   46T  53% /esgF
/dev/mapper/esgfg--LV-esgfg--LVM  100T   50T   45T  53% /esgG
/dev/mapper/esgfh--LV-esgfh--LVM  100T   50T   46T  53% /esgH
/dev/mapper/esgfi--LV-esgfi--LVM  100T   17T   79T  18% /esgI
/dev/mapper/esgfj--LV-esgfj--LVM  100T   54T   42T  57% /esg
```

The ESGF software is run inside several docker containers that each handle different tasks.
```
CONTAINER ID   IMAGE                         COMMAND                  CREATED       STATUS       PORTS                   NAMES
e4284594af9b   esgfdeploy/nginx:33ea7b06     "/usr/local/bin/tini…"   5 weeks ago   Up 2 weeks   0.0.0.0:443->8080/tcp   proxy
a8d127ab8d3f   esgfdeploy/nginx:33ea7b06     "/usr/local/bin/tini…"   5 weeks ago   Up 2 weeks   8080/tcp                fileserver
d0daeafa7776   esgfdeploy/thredds:33ea7b06   "/usr/local/bin/tini…"   5 weeks ago   Up 2 weeks   8080/tcp                thredds
```
The `proxy` container listens for incoming requests passing them to either the `filerserver` or `thredds` container based on the request URL.

The `filerserver` container maps all the data partitions `esg[A-I]` to be accessed by the software. This mapping must be an exact match to our existing published data.

The `thredds` generates a thredds catalog from available data that can be accessed through the web interface. 