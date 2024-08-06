import pytest
import pathlib
import os
import arcpy

from osgeo import ogr
from csf_prf.engines.ENCReaderEngine import ENCReaderEngine

"""
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
ENC_FILE = str(INPUTS / 'US4GA17M.000')
SHP_FILE = str(INPUTS / 'test_shapefile.shp')
MULTIPLE_ENC = ENC_FILE + ';' + str(INPUTS / 'US5SC21M.000')


@pytest.fixture
def victim():
    class Param:
        @property
        def valueAsText(self):
            return ENC_FILE

    victim = ENCReaderEngine(param_lookup={"enc_files": Param()}, sheets_layer=None)
    victim.set_driver()
    return victim


def test___init__(victim):
    assert hasattr(victim, 'geometries')
    assert hasattr(victim, 'gdb_name')
    assert victim.gdb_name == 'csf_features'
    assert 'Point' in victim.geometries.keys()

@pytest.mark.skip(reason="This function runs 3 other functions.")
def add_columns():
    ...

def test_add_column_and_constant(victim):    
    layer = arcpy.management.CopyFeatures(SHP_FILE, r'memory\test_layer')
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' not in fields
    victim.add_column_and_constant(layer, 'test_column_name', nullable=True)
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' in fields    

def test_add_invreq_column(victim): # TODO Build S57 test file
    victim.split_multipoint_env()
    victim.get_feature_records() 
    victim.add_invreq_column() 
    assert 'invreq' in victim.geometries['Point']['GC_layers']['assigned'].keys()

# def test_add_objl_string(victim):



@pytest.mark.skip(reason="This function runs 1 other function twice.")
def test_asgnmt_column():
    ...    

def test_feature_covered_by_upper_scale(victim):
    class MultiParam:
        @property
        def valueAsText(self):
            return MULTIPLE_ENC
    victim.param_lookup['enc_files'] = MultiParam()
    victim.get_enc_bounds()
    feature_json = {
        "geometry": {
            "type": "Point",
            "coordinates": [-80.6, 32.3]
        }
    }
    result = victim.feature_covered_by_upper_scale(feature_json, 4)
    assert result

def test_get_all_fields(victim):
    features = [
        {'geojson': {
            'properties': {
                'one': 1,
                'two': 2
            }
        }},
        {'geojson': {
            'properties': {
                'three': 3,
                'four': 4
            }
        }}
    ]
    results = victim.get_all_fields(features)
    assert 'one' in results
    assert 'two' in results
    assert 'three' in results
    assert 'four' in results


def test_get_aton_lookup(victim):
    results = victim.get_aton_lookup()
    assert type(results) == type([])
    assert results[0] == 'BCNCAR'

@pytest.mark.skip(reason="Requires the password.")
def test_get_cursor():
    ...    


def test_get_enc_bounds(victim):
    victim.get_enc_bounds()
    assert hasattr(victim, 'scale_bounds')
    assert 4 in victim.scale_bounds
    assert -81.3995801 in victim.scale_bounds[4]


def test_get_feature_records(victim):
    victim.split_multipoint_env()
    victim.get_feature_records()
    assert len(victim.geometries['Point']['features']) == 4490
    assert len(victim.geometries['LineString']['features']) == 3219
    assert len(victim.geometries['Polygon']['features']) == 2241


def test_get_vector_records(victim):
    victim.return_primitives_env()
    victim.get_vector_records()
    assert 'QUAPOS' in victim.geometries['Point'].keys()
    assert victim.geometries['Point']['QUAPOS'][0]['geojson']['properties']['QUAPOS'] == 4


def test_return_primitives_env(victim):
    victim.return_primitives_env()
    assert os.environ["OGR_S57_OPTIONS"] == "RETURN_PRIMITIVES=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"

def test_set_driver(victim): 
    victim.set_driver()
    results = victim.driver.GetName()
    assert results == 'S57'

def test_set_none_to_null(victim):
    feature_json = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [125.6, 10.1]
        },
        'properties': {
            'name': 'None',
            'type': None
        }
        }
    results = victim.set_none_to_null(feature_json)
    assert results['properties']['name'] == ''
    assert results['properties']['type'] == ''

def test_split_multipoint_env(victim):
    victim.split_multipoint_env()
    assert os.environ["OGR_S57_OPTIONS"] == "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"
