import pathlib
import yaml


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class Param:
        def __init__(self, path):
            self.value = path

        @property
        def valueAsText(self):
            return self.value


def get_ags_tools():
    parent = pathlib.Path(__file__).parents[1]
    ags_tools = parent / "ags_tools"

    tools = []
    for tool in ags_tools.glob('**/*.py'):
        tools.append(tool)
    return tools


def get_config_item(parent: str, child: str=False) -> tuple[str, int]:
    """Load config and return speciific key"""

    with open(str(INPUTS / 'lookups' / 'config.yaml'), 'r') as lookup:
        config = yaml.safe_load(lookup)
        parent_item = config[parent]
        if child:
            return parent_item[child]
        else:
            return parent_item