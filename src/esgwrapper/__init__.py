from pathlib import Path

REPO_DIR = Path(__file__).parents[2]

CONFIG_FILES_DIR = Path( REPO_DIR / 'config' )
WORK_DIRS_LOCATION = Path( REPO_DIR / 'work' )

ESGCET_CONFIG_FILES_DIR = CONFIG_FILES_DIR / 'esgcet_files'
# ESGCET_CONFIG_FILE = 'esg_east.yaml'

DEFAULT_DATASETS_CONFIG_FILE = 'config-datasets.yaml'
DEFAULT_WORKDIRS_CONFIG_FILE = 'config-workdirs.yaml'

DEFAULT_DATASETS_FILE = 'datasets.json'
DEFAULT_INVENTORY_FILE = 'inventory.json'

SEND_STDOUT_TO_LOGFILE = True
