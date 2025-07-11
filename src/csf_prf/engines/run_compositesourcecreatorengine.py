import   pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine
from csf_prf.helpers.tools import Param


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__':
    param_lookup = {
        'sheets': Param(str(INPUTS / 'test_shapefiles' / 'G322_Sheets_01302024.shp')),
        'junctions': Param(''),
        # 'enc_files': Param(str(str(INPUTS / 'US4GA17M.000') + ';' + str(INPUTS / 'US5SC21M.000'))),
        # 'enc_files': Param(str(str(INPUTS / 'US5SC21M.000'))),
        'enc_files': Param(''),
        'output_folder': Param(str(OUTPUTS)),
        'download_geographic_cells': Param(False),
        'caris_export': Param(False),
        'layerfile_export': Param(False)
    }
    engine = CompositeSourceCreatorEngine(param_lookup)
    engine.start()