import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.engines.ClipEncEngine import ClipEncEngine


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs' / 'test'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'inputs' / 'test' / 'clipped'


if __name__ == '__main__':
    class Param:
        def __init__(self, path):
            self.path = path

        @property
        def valueAsText(self):
            return self.path
        
    param_lookup = {
        'input_folder': Param(str(INPUTS)),
        'output_folder': Param(str(OUTPUTS))
    }
    engine = ClipEncEngine(param_lookup)
    engine.start()