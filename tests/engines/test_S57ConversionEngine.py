import pytest
import pathlib
import json
import os
import arcpy
import sys
import arcpy

CSFPRF_MODULE = pathlib.Path(__file__).parents[1]
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.helpers.tools import Param
from csf_prf.engines.S57ConversionEngine import S57ConversionEngine


'''
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
'''

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
OUTPUTS = REPO / 'outputs'

S57_FILE = str(INPUTS / 'H13384_FFF.000')
TRANSFORM_SHP = str(INPUTS / 'test_shapefiles' / 'test_s57_transform.shp')


@pytest.fixture
def victim():

    victim = S57ConversionEngine(
        param_lookup={'enc_file': Param(str(S57_FILE)), 
                      'output_folder': Param(str(OUTPUTS)),
                      'caris_export': Param(False),
                      'layerfile_export': Param(False)})
    return victim


def test___init__(victim):
    assert hasattr(victim, 'geometries')
    assert hasattr(victim, 'gdb_name')
    assert victim.gdb_name == 'H13384_FFF'
    assert 'Point' in victim.geometries.keys()


def test_project_rows_to_wgs84(victim):
    victim.gdb_name = 'unit_tests'
    victim.create_output_gdb(gdb_name=victim.gdb_name)
    gdb_path = os.path.join(victim.param_lookup['output_folder'].valueAsText, f"{victim.gdb_name}.gdb")
    fc_name = 'test_s57_transform'
    original_locations = os.path.join(gdb_path, fc_name)
    arcpy.management.CopyFeatures(TRANSFORM_SHP, original_locations)
    # shapefile shortened column name
    victim.add_column_and_constant(original_locations, 'transformed', expression='!transforme!', nullable=False)

    victim.feature_classes = [fc_name]
    victim.project_rows_to_wgs84()

    with arcpy.da.SearchCursor(TRANSFORM_SHP, ['SHAPE@']) as original_cursor:
        original_locations = list(original_cursor)
    with arcpy.da.SearchCursor(os.path.join(gdb_path, fc_name), ['SHAPE@', 'transformed']) as cursor:
        for i, row in enumerate(cursor):
            assert row[1] == 'NAD_1983_To_WGS_1984_5'
            current = json.loads(row[0].JSON)
            original = json.loads(original_locations[i][0].JSON)
            assert current['x'] != original['x']
            assert current['y'] != original['y']
            assert row[0].distanceTo(original_locations[i][0]) > .000001
