import pytest
import pathlib
import arcpy

from csf_prf.engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine

"""
Unit tests need to havea .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
OUTPUTS = REPO / 'outputs'
SHEETS = str(INPUTS / 'G322_Sheets_01302024.shp')
JUNCTIONS = str(INPUTS / 'G322_Junctions_01302024.shp')


class Param:
    def __init__(self, path):
        self.path = path

    @property
    def valueAsText(self):
        return self.path
    

@pytest.fixture
def victim():
    victim = CompositeSourceCreatorEngine(
        param_lookup={
            'sheets': Param(SHEETS), 
            'junctions': Param(JUNCTIONS),
            'output_folder': Param(str(OUTPUTS))})
    return victim


def test_add_column_and_constant(victim):
    
    layer = arcpy.management.CopyFeatures(SHEETS, r'memory\test_layer')
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'invreq' not in fields
    expression = "'Survey: ' + str(!registry_n!) + ', Priority: ' + str(!priority!) + ', Name: ' + str(!sub_locali!)"
    victim.add_column_and_constant(layer, 'invreq', expression)
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'invreq' in fields


def test_convert_sheets(victim):
    victim.convert_sheets()
    assert int(arcpy.management.GetCount(victim.sheets_layer)[0]) == 13


def test_copy_layer_to_feature_class(victim):
    sheets_feature_class = str(OUTPUTS / 'csf_features.gdb' / 'output_sheets')
    arcpy.management.Delete(sheets_feature_class)
    layer = arcpy.management.CopyFeatures(SHEETS, r'memory\test_layer')
    victim.copy_layer_to_feature_class('sheets', layer, 'output_sheets')
    files = [file for _, __, files in arcpy.da.Walk(str(OUTPUTS / 'csf_features.gdb'), datatype="FeatureClass") for file in files]
    assert 'output_sheets' in files


def test_get_unique_values(victim):
    result = victim.get_unique_values(SHEETS, 'priority')
    assert len(result) == 13
    assert max(result) == 13


def test_convert_junctions(victim):
    victim.convert_junctions()
    output_junctions = str(OUTPUTS / 'csf_features.gdb' / 'output_junctions')
    assert int(arcpy.management.GetCount(output_junctions)[0]) == 6


def test_create_output_gdb(victim):
    output_gdb = str(OUTPUTS / 'csf_features.gdb')
    arcpy.management.Delete(output_gdb)
    assert not arcpy.Exists(output_gdb)
    victim.create_output_gdb()
    assert arcpy.Exists(output_gdb)


def test_make_junctions_layer(victim):
    result = victim.make_junctions_layer(victim.param_lookup['junctions'].valueAsText)
    assert int(arcpy.management.GetCount(result)[0]) == 6


def test_make_sheets_layer(victim):
    result = victim.make_sheets_layer(victim.param_lookup['sheets'].valueAsText)
    assert int(arcpy.management.GetCount(result)[0]) == 13


def test_split_inner_polygons(victim):
    result = victim.make_sheets_layer(victim.param_lookup['sheets'].valueAsText)
    outter, inner = victim.split_inner_polygons(result)
    assert len(outter) == 13
    assert len(inner) == 0