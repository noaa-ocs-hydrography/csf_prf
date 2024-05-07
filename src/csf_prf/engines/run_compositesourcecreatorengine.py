import pathlib
from csf_prf.engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine


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
        'sheets': Param(str(INPUTS / 'G322_Sheets_01302024.shp')),
        'junctions': Param(''),
        'maritime_boundary_pts': Param(''),
        'maritime_boundary_features': Param(''),
        'maritime_boundary_baselinespython': Param(''),
        'enc_files': Param(str(INPUTS / 'savannah_enc.000')),
        'output_folder': Param(str(OUTPUTS)),
    }
    engine = CompositeSourceCreatorEngine(param_lookup)
    engine.start()