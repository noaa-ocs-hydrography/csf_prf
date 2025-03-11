import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.engines.MHWBufferEngine import MHWBufferEngine
from csf_prf.helpers.tools import Param

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__': 
    param_lookup = {
        # 'sheets': Param(str(INPUTS / 'test_shapefiles' / 'G322_Sheets_01302024.shp')),
        'sheets': Param(r"C:\Users\Stephen.Patterson\Data\junk\Revillagigedo\Revillagigedo_sheets.shp"),
        # 'enc_files': Param(str(OUTPUTS / 'US4AK5FP.000') + ';' + str(OUTPUTS / 'US4AK5GO.000')),
        'enc_files': Param(''),
        'output_folder': Param(str(OUTPUTS)),
    }
    engine = MHWBufferEngine(param_lookup)
    engine.start()