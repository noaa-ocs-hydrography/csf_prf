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
        'enc_files': Param(''),
        # 'enc_files': Param(str(OUTPUTS / 'US5WA3BE.000') + ';' + str(OUTPUTS / 'US5PDXPF.000')),
        'sheets': Param(r"C:\Users\Stephen.Patterson\Data\junk\OPR-N399-KR-25_NewSheets_03192025_New\OPR-N399-KR-25_NewSheets_03192025.shp"),
        'output_folder': Param(str(OUTPUTS)),
    }
    engine = MHWBufferEngine(param_lookup)
    engine.start()