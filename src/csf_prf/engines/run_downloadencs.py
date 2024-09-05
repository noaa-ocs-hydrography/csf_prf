import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.engines.DownloadEncEngine import DownloadEncEngine


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__':
    class Param:
        def __init__(self, path):
            self.path = path

        @property
        def valueAsText(self):
            return self.path
        
    param_lookup = {
        'sheets': Param(str(INPUTS / 'test_shapefiles' / 'enc_downloader_boundary.shp')),
        'output_folder': Param(str(OUTPUTS)),
    }
    engine = DownloadEncEngine(param_lookup)
    engine.start()