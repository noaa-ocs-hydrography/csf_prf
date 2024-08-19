import pytest
import pathlib
import os
import arcpy
import yaml

from osgeo import ogr
from csf_prf.engines.ENCReaderEngine import ENCReaderEngine

"""
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
# LOOKUP = 
INPUTS = REPO / 'inputs'
ENC_FILE = str(INPUTS / 'US4GA17M.000')
SHP_FILE_1 = str(INPUTS / 'test_shapefile_1.shp')
SHP_FILE_2 = str(INPUTS / 'test_shapefile_2.shp')
SHP_POLYGON_FILE_1 = str(INPUTS / 'test_shapefile_polygons_1.shp')
S57_FILE = str(INPUTS / 'test_S57_files/US5GA20M_S57_testfile.000') # 1 line, 2 points, 2 polygons
MULTIPLE_ENC = S57_FILE # + ';' + str(INPUTS / 'US5SC21M.000')

class Param:
    def __init__(self, path):
        self.path = path

    @property
    def valueAsText(self):
        return self.path

@pytest.fixture
def victim():
    # class Param:
    #     @property
    #     def valueAsText(self):
    #         return ENC_FILE

    victim = ENCReaderEngine(
        param_lookup={"enc_files": Param(S57_FILE)}, 
        sheets_layer=None)
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
    layer = arcpy.management.CopyFeatures(SHP_FILE_1, r'memory\test_layer')
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' not in fields
    victim.add_column_and_constant(layer, 'test_column_name', nullable=True)
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' in fields    


@pytest.mark.skip(reason="This function runs 2 other functions.")
def test_add_invreq_column():
    ...


def test_add_objl_string(victim):
    victim.geometries['Point']['features_layers']['assigned'] = SHP_FILE_1
    victim.geometries['Point']['features_layers']['unassigned'] = SHP_FILE_2
    arcpy.management.DeleteField(victim.geometries['Point']['features_layers']['assigned'], 'OBJL_NAME')
    arcpy.management.DeleteField(victim.geometries['Point']['features_layers']['unassigned'], 'OBJL_NAME')
    victim.add_objl_string()
    
    # TODO add more for the loop, this is a bit confusing for the ATON values, they might be missing


@pytest.mark.skip(reason="This function runs 1 other function.")
def test_asgnmt_column():
    ...    


def test_download_gc(victim): # TODO 
    ...


def test_download_gcs(victim): # TODO 
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


def test_filter_gc_features(victim): # TODO, need gc layer


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
    assert -81.3995801 in victim.scale_bounds[4][0]


def test_get_feature_records(victim):
    victim.split_multipoint_env()
    victim.get_feature_records()
    assert len(victim.geometries['Point']['features']) == 4490
    assert len(victim.geometries['LineString']['features']) == 3219
    assert len(victim.geometries['Polygon']['features']) == 2241


@pytest.mark.skip(reason="This function runs 3 other functions.")
def test_get_gc_data():
    ...    


def test_get_sql(): # TODO what to do with sql.read()
    victim.get_sql('GetRelatedENC.sql')


def test_get_vector_records(victim):
    victim.return_primitives_env()
    victim.get_vector_records()
    assert 'QUAPOS' in victim.geometries['Point'].keys()
    assert victim.geometries['Point']['QUAPOS'][0]['geojson']['properties']['QUAPOS'] == 4


def test_merge_gc_features(victim):    


def test_open_file(victim):
    victim.open_file(ENC_FILE)
    results = victim.driver.GetName()
    assert results == 'S57'


def test_perform_spatial_filter(victim): # TODO



def test_print_feature_total(victim):
    victim.geometries['Point']['features_layers']['assigned'] = SHP_FILE_1
    victim.geometries['Point']['features_layers']['unassigned'] = SHP_FILE_2
    # TODO should I do this for lines and polygons too? then make test shapefiles
    # victim.print_feature_total()
    # assert victim.points == 6
    # assert int(arcpy.management.GetCount(victim.geometries['Point']['features_layers']['assigned']).getOutput(0)) == 6
    # assert int(arcpy.management.GetCount(victim.geometries['Point']['features_layers']['unassigned']).getOutput(0)) == 6


pytest.mark.skip(reason="This function runs the arcpy.AddMessage function.")
def test_print_geometries(): # TODO double check this should be skipped
    ...


def test_join_quapos_to_features(victim): # TODO need to make quapos layers, they will get joined, then check quapos is there
    victim.geometries['Point']['features_layers']['assigned'] = SHP_FILE_1
    victim.geometries['Point']['features_layers']['unassigned'] = SHP_FILE_2
    victim.geometries['Point']['QUAPOS_layers']['assigned'] = QUAPOS_FILE_1
    victim.geometries['Point']['QUAPOS_layers']['assigned'] = QUAPOS_FILE_2


def test_return_primitives_env(victim):
    victim.return_primitives_env()
    assert os.environ["OGR_S57_OPTIONS"] == "RETURN_PRIMITIVES=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"


pytest.mark.skip(reason="")
def test_run_query(): # TODO double check this should be skipped
    ...   


# TODO verify through engine results
def test_set_assigned_invreq(victim): # TODO delete all 'invreq' first
    victim.geometries['Polygon']['features_layers']['assigned'] = SHP_POLYGON_FILE_1
    with open(str(INPUTS / 'lookups' / 'invreq_lookup.yaml'), 'r') as lookup:
        objl_lookup = yaml.safe_load(lookup)
    victim.set_assigned_invreq('Polygon', objl_lookup, objl_lookup['OPTIONS'])

    with arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']) as cursor:
        test_data = list(cursor)
    # LNDARE check TODO may have to do something different here for the area
    # assert '' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[0][0]

    
    # MORFAC check
    # assert 'sumberged dolphins' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[1][0]
    assert 'sumberged dolphins' in test_data[1][0] # TODO doube check this works

    # assert 'contact PM/COR' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[2][0]

    # # OBSTRN check, did part of this
    # assert 'wellhead investigation' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[3][0]
    # assert 'minimum depth' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[4][0]
    # assert 'appropriate attribution' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[5][0]

    # # SBDARE check 
    # assert 'FFF with descrp=retain' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[6][0]

    # # SLCONS check
    # assert 'contact PM/COR' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[7][0]
    # assert 'appropriate attribution' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[8][0]

    # # UWTROC check
    # assert 'appropriate attribution' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[9][0]
    # assert 'submerged rock' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[10][0]

    # # Missing check
    # # assert '' in list(arcpy.da.SearchCursor(SHP_POLYGON_FILE_1, ['invreq']))[10][0]


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


def test_set_unassigned_invreq(victim): # TODO more to add 
    victim.geometries['Point']['features_layers']['unassigned'] = SHP_FILE_2


def test_split_multipoint_env(victim):
    victim.split_multipoint_env()
    assert os.environ["OGR_S57_OPTIONS"] == "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"


def test_store_gc_names(victim): # TODO

