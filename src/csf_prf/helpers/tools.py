import pathlib


class Param:
        def __init__(self, path):
            self.path = path

        @property
        def valueAsText(self):
            return self.path
        
        @property
        def value(self):
            return self.path


def get_ags_tools():
    parent = pathlib.Path(__file__).parents[1]
    ags_tools = parent / "ags_tools"

    tools = []
    for tool in ags_tools.glob('**/*.py'):
        tools.append(tool)
    return tools


def get_enc_files(bounding_box):
    """"""
    pass