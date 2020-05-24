from collections import namedtuple
import yaml


def load_config(path) -> dict:
    with open(path, 'r') as conf_fd:
        return yaml.safe_load(conf_fd.read())


Socket = namedtuple('Socket', ('reader', 'writer'))
