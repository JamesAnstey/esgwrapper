from pathlib import Path

repo_dir = Path(__file__).parents[2]

CONFIG_FILES_DIR = Path( repo_dir / 'config' )
WORK_DIRS_LOCATION = Path( repo_dir / 'work' )

DEFAULT_DATASETS_CONFIG_FILE = 'config-datasets.yaml'
DEFAULT_WORKDIRS_CONFIG_FILE = 'config-workdirs.yaml'

DEFAULT_DATASETS_FILE = 'datasets.json'
DEFAULT_INVENTORY_FILE = 'inventory.json'
