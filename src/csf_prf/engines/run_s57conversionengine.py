import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.helpers.tools import Param
from csf_prf.engines.S57ConversionEngine import S57ConversionEngine


INPUTS = pathlib.Path(__file__).parents[3] / "inputs"
OUTPUTS = pathlib.Path(__file__).parents[3] / "outputs"


if __name__ == "__main__":
    param_lookup = {
        "enc_file": Param(str(INPUTS / "H13384_FFF.000")),
        "output_folder": Param(str(OUTPUTS)),
        "caris_export": Param(True),
        "layerfile_export": Param(False)
    }
    engine = S57ConversionEngine(param_lookup)
    engine.start()
