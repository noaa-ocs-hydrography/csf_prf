import pathlib
import arcpy

from csf_prf.helpers.tools import Param
from csf_prf.engines.S57ConversionEngine import S57ConversionEngine


INPUTS = pathlib.Path(__file__).parents[3] / "inputs"
OUTPUTS = pathlib.Path(__file__).parents[3] / "outputs"


if __name__ == "__main__":
    param_lookup = {
        "enc_file": Param(str(INPUTS / "US3GA10M.000")),
        "output_folder": Param(str(OUTPUTS)),
    }
    engine = S57ConversionEngine(param_lookup)
    engine.start()
