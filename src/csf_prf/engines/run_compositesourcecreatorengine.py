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
            return str(self.path)
        
        @property
        def value(self):
            return self.path
        
    param_lookup = {
        'sheets': Param(str(INPUTS / 'test_shapefiles/G322_Sheets_01302024.shp')),
        'junctions': Param(''),
        'maritime_boundary_pts': Param(''),
        'maritime_boundary_features': Param(''),
        'maritime_boundary_baselines': Param(''),
        'enc_files': Param(str(str(INPUTS / 'US2EC02M.000') + ';' + str(INPUTS / 'US3GA10M.000'))),
        'output_folder': Param(str(OUTPUTS)),
        'download_geographic_cells': Param(False),
        'caris_export': Param(False)
    }
    engine = CompositeSourceCreatorEngine(param_lookup)
    engine.start()