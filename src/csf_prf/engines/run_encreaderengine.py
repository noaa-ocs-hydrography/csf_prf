import arcpy
import time
import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))

from csf_prf.engines.ENCReaderEngine import ENCReaderEngine
from csf_prf.helpers.tools import Param # TODO verify this still works


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


if __name__ == '__main__':
    def add_column_and_constant(layer, column, expression=None, field_type='TEXT', field_length=255, nullable=False) -> None:
        """
        Add the asgnment column and 
        :param arcpy.FeatureLayerlayer layer: In memory layer used for processing
        """

        if nullable:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length, field_is_nullable='NULLABLE')
        else:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length)
            arcpy.management.CalculateField(
                layer, column, expression, expression_type="PYTHON3", field_type=field_type
            )
    
    def convert_sheets(sheet_parameter) -> None:
        """Process the Sheets input parameter"""

        arcpy.AddMessage('converting sheets')
        sheets = sheet_parameter.replace("'", "").split(';')
        layers = [make_sheets_layer(sheets_file) for sheets_file in sheets]
        layer = arcpy.management.Merge(layers, r'memory\sheets_layer')
        expression = "'Survey: ' + str(!registry_n!) + ', Priority: ' + str(!priority!) + ', Name: ' + str(!sub_locali!)"
        add_column_and_constant(layer, 'invreq', expression)
        return layer

    def make_sheets_layer(sheets):
        """
        Create in memory layer for processing.
        This copies the input Sheets shapefile to not corrupt it.
        :param str sheets: Path to the input Sheets shapefile
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        fields = { # Use for information.  FME used these 6 fields. Might be different sometimes.
             9: 'snm',
            16: 'priority',
            17: 'scale',
            19: 'sub_locali',
            20: 'registry_n',
            23: 'invreq'
        }
        field_info = arcpy.FieldInfo()
        input_fields = arcpy.ListFields(sheets)
        for field in input_fields:
            if field.name in fields.values():
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        layer = arcpy.management.MakeFeatureLayer(sheets, field_info=field_info)
        return layer
    
    param_lookup = {
        'sheets': Param(str(INPUTS / 'test_shapefiles' / 'G322_Sheets_01302024.shp')),
        'enc_files': Param(str(str(INPUTS / 'US2EC02M.000') + ';' + str(INPUTS / 'US3GA10M.000'))),
        # 'enc_files': Param(str(INPUTS / 'US3GA10M.000')),
        'output_folder': Param(str(OUTPUTS)),
        'download_geographic_cells': Param(True)
    }
    sheets_layer = convert_sheets(param_lookup['sheets'].valueAsText)
    engine = ENCReaderEngine(param_lookup, sheets_layer)
    start = time.time()
    engine.start()
    print(f'Run time: {(time.time() - start) / 60}')