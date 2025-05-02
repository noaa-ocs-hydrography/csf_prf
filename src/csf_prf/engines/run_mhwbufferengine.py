import pathlib
import time
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.engines.MHWBufferEngine import MHWBufferEngine
from csf_prf.helpers.tools import Param

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__': 
    param_lookup = {
        'sheets': Param(r"C:\Users\Stephen.Patterson\Downloads\drive-download-20250501T182809Z-001\ChesBaySurveyExtents_040121_4.shp"),
        'enc_files': Param(''),
        'output_folder': Param(str(OUTPUTS)),
    }
    start = time.time()
    engine = MHWBufferEngine(param_lookup)
    engine.start()
    print(f'Run time: {(time.time() - start) / 60}')