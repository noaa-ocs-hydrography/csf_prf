import arcpy
import time
import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))

from csf_prf.engines.ENCReaderEngine import ENCReaderEngine
from csf_prf.engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine
from csf_prf.helpers.tools import Param # TODO verify this still works


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__':
    param_lookup = {
        'sheets': Param(str(INPUTS / 'test_shapefiles' / 'G322_Sheets_01302024.shp')),
        # 'enc_files': Param(str(str(INPUTS / 'US2EC02M.000') + ';' + str(INPUTS / 'US3GA10M.000'))),
        'enc_files': Param(str(INPUTS / 'US3GA10M.000')),
        'output_folder': Param(str(OUTPUTS)),
        'download_geographic_cells': Param(False),
        'layerfile_export': Param(False)
    }
    csf_engine = CompositeSourceCreatorEngine(param_lookup)
    csf_engine.convert_sheets()
    engine = ENCReaderEngine(param_lookup, csf_engine.sheets_layer)
    start = time.time()
    engine.start()
    print(f'Run time: {(time.time() - start) / 60}')