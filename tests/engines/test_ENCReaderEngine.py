import pytest
import pathlib
import os
import arcpy
import yaml
import json

from osgeo import ogr
from csf_prf.engines.ENCReaderEngine import ENCReaderEngine

"""
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
OUTPUTS = REPO / 'outputs'

ENC_FILE = str(INPUTS / 'US4GA17M.000')
SHEETS_LAYER = str(INPUTS / 'test_shapefiles' / 'G322_Sheets_01302024.shp') 
SHP_POINT_FILE_1 = str(INPUTS / 'test_shapefiles' / 'test_point_shapefile_1.shp')
SHP_POINT_FILE_2 = str(INPUTS / 'test_shapefiles' / 'test_point_shapefile_2.shp')
SHP_LINE_FILE = str(INPUTS / 'test_shapefiles' / 'test_line_shapefile.shp')
SHP_POLYGON_FILE = str(INPUTS / 'test_shapefiles' / 'test_polygon_shapefile.shp')
S57_FILE = str(INPUTS / 'test_S57_files' / 'US5GA20M_S57_testfile.000') # 1 line, 2 points, 2 polygons
ENC_FILE = str(INPUTS / 'US4GA17M.000')
MULTIPLE_ENC = ENC_FILE + ';' + str(INPUTS / 'US5SC21M.000')

class Param:
    def __init__(self, path):
        self.path = path

    @property
    def valueAsText(self):
        return self.path

@pytest.fixture
def victim():

    victim = ENCReaderEngine(
        param_lookup={"enc_files": Param(S57_FILE), "output_folder": Param(OUTPUTS)}, 
        sheets_layer=SHEETS_LAYER)
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
    layer = arcpy.management.CopyFeatures(SHP_POINT_FILE_1, r'memory\test_layer')
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' not in fields
    victim.add_column_and_constant(layer, 'test_column_name', nullable=True)
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'test_column_name' in fields    


@pytest.mark.skip(reason="This function runs 2 other functions.")
def test_add_invreq_column():
    ...


@pytest.mark.skip(reason="This function runs 1 other function.")
def test_asgnmt_column():
    ...    


@pytest.mark.skip(reason="This function will be tested later with a mock object.")
def test_download_gc(): 
    ...


@pytest.mark.skip(reason="This function will be tested later with a mock object.")
def test_download_gcs():
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


def test_filter_gc_features(victim):
    victim.gc_points = SHP_POINT_FILE_1
    victim.gc_lines = SHP_LINE_FILE
    victim.filter_gc_features()
    assert victim.geometries['Point']['GC_layers']['assigned'] != None
    assert victim.geometries['Point']['GC_layers']['unassigned'] != None
    assert victim.geometries['LineString']['GC_layers']['assigned'] != None
    assert victim.geometries['LineString']['GC_layers']['unassigned'] != None
    assert int(arcpy.management.GetCount(victim.geometries['Point']['GC_layers']['assigned'])[0]) == 11
    assert int(arcpy.management.GetCount(victim.geometries['LineString']['GC_layers']['assigned'])[0]) == 2


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


@pytest.mark.skip(reason="Requires the database password.")
def test_get_cursor():
    ...    


def test_get_enc_bounds(victim):
    class MultiParam:
        @property
        def valueAsText(self):
            return MULTIPLE_ENC
    victim.param_lookup['enc_files'] = MultiParam()
    victim.get_enc_bounds()
    assert hasattr(victim, 'scale_bounds')
    assert 4 in victim.scale_bounds
    assert -81.3995801 in victim.scale_bounds[4][0]


def test_get_feature_records(victim):
    victim.split_multipoint_env()
    victim.get_feature_records()
    assert len(victim.geometries['Point']['features']) == 2
    assert len(victim.geometries['LineString']['features']) == 1
    assert len(victim.geometries['Polygon']['features']) == 2


@pytest.mark.skip(reason="This function runs 3 other functions.")
def test_get_gc_data():
    ...    


def test_get_sql(victim): 
    results = victim.get_sql('GetRelatedENC')
    first_line = 'SELECT doc.BaseFileName, k.iecode, lk.status, doc.Path'
    assert results[55:109] == first_line


def test_get_vector_records(victim):
    victim.return_primitives_env()
    victim.get_vector_records()
    assert 'QUAPOS' in victim.geometries['Point'].keys()
    assert victim.geometries['Point']['QUAPOS'][0]['geojson']['properties']['QUAPOS'] == 4


def test_merge_gc_features(victim):
    victim.gc_files = ['US3GA10M']
    victim.merge_gc_features() 
    assert int(arcpy.management.GetCount(victim.gc_points)[0]) == 40
    assert int(arcpy.management.GetCount(victim.gc_lines)[0]) == 20


def test_open_file(victim):
    victim.open_file(ENC_FILE)
    results = victim.driver.GetName()
    assert results == 'S57'


def test_perform_spatial_filter(victim):
    geometry_types = {'Point': SHP_POINT_FILE_1, 'LineString': SHP_LINE_FILE, 'Polygon': SHP_POLYGON_FILE}
    for geometry in geometry_types:
        geojson_outputs = []
        for row in arcpy.da.SearchCursor(geometry_types[geometry], ['FID','OBJL_NAME', 'SHAPE@', 'SHAPE@XY']):
            id_val = row[0]
            properties_val = row[1]
            coordinates_val = []
            if geometry == 'Point':
                coordinates_val = list(row[3])
            elif geometry == 'LineString' or geometry == 'Polygon':
                for part in row[2]:
                    for pnt in part:
                        coordinates_val.append([pnt.X, pnt.Y])
                    if geometry == 'Polygon':    
                        coordinates_val = [coordinates_val]
            geojson = {
                "geojson": {
                    "id": id_val,
                    "properties": {
                        "OBJL_NAME" : properties_val},
                    "geometry": {
                        "type": geometry,
                        "coordinates": coordinates_val
                    }                
                }
            }
            geojson_outputs.append(geojson)
        victim.geometries[geometry]['features'] = geojson_outputs        

    victim.perform_spatial_filter()
    assert victim.geometries['Point']['features_layers']['assigned'] is not None
    assert victim.geometries['Point']['features_layers']['unassigned'] is not None
    assert victim.geometries['LineString']['features_layers']['assigned'] is not None
    assert victim.geometries['LineString']['features_layers']['unassigned'] is not None
    assert victim.geometries['Polygon']['features_layers']['assigned'] is not None
    assert victim.geometries['Polygon']['features_layers']['unassigned'] is not None
    assert int(arcpy.management.GetCount(victim.geometries['Point']['features_layers']['assigned'])[0]) == 11
    assert int(arcpy.management.GetCount(victim.geometries['LineString']['features_layers']['assigned'])[0]) == 2
    assert int(arcpy.management.GetCount(victim.geometries['Polygon']['features_layers']['assigned'])[0]) == 12


@pytest.mark.skip(reason="This function runs 2 other functions.")
def test_print_feature_total(): 
    ...


pytest.mark.skip(reason="This function runs the arcpy.AddMessage function.")
def test_print_geometries():
    ...


def test_join_quapos_to_features(victim): 
    # spatialjoin won't add column to an in memory layer
    SHP_POINT_FILE_3 = str(INPUTS / 'test_shapefiles' / 'test_point_shapefile_3.shp')
    arcpy.management.CopyFeatures(SHP_POINT_FILE_1, SHP_POINT_FILE_3)
    victim.geometries['Point']['features_layers']['assigned'] =  SHP_POINT_FILE_3
    victim.geometries['Point']['QUAPOS_layers']['assigned'] = SHP_POINT_FILE_2
    fields = [field.name for field in arcpy.ListFields(SHP_POINT_FILE_3)]
    assert 'QUAPOS' not in fields
    victim.join_quapos_to_features()
    fields = [field.aliasName for field in arcpy.ListFields(SHP_POINT_FILE_3)]
    assert 'QUAPOS' in fields
    arcpy.management.Delete(SHP_POINT_FILE_3)
    

def test_return_primitives_env(victim):
    victim.return_primitives_env()
    assert os.environ["OGR_S57_OPTIONS"] == "RETURN_PRIMITIVES=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"


@pytest.mark.skip(reason="This function will be tested later with a mock object.")
def test_run_query():
    ...   


def test_set_assigned_invreq(victim): 
    layer = arcpy.management.CopyFeatures(SHP_POLYGON_FILE, r'memory\test_layer')
    victim.geometries['Polygon']['features_layers']['assigned'] = layer
    with open(str(INPUTS / 'lookups' / 'invreq_lookup.yaml'), 'r') as lookup:
        objl_lookup = yaml.safe_load(lookup)
    victim.set_assigned_invreq('Polygon', objl_lookup, objl_lookup['OPTIONS'])

    with arcpy.da.SearchCursor(layer, ['invreq']) as cursor:
        test_data = list(cursor)

    # LNDARE check
    assert 'update LNDELV' in test_data[0][0]

    # MORFAC check 
    assert 'contact PM/COR' in test_data[1][0]

    # # OBSTRN check
    assert 'wellhead investigation' in test_data[2][0]
    assert 'minimum depth' in test_data[3][0]
    assert 'appropriate attribution' in test_data[4][0]

    # # SBDARE check 
    assert 'FFF with descrp=retain' in test_data[5][0]

    # # SLCONS check
    assert 'contact PM/COR' in test_data[6][0]
    assert 'appropriate attribution' in test_data[7][0]

    # # UWTROC check
    assert 'appropriate attribution' in test_data[8][0]
    assert 'submerged rock' in test_data[9][0]

    # # Other OBJL name check
    assert 'serving intended purpose' in test_data[10][0]


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


def test_set_unassigned_invreq(victim): 
    layer = arcpy.management.CopyFeatures(SHP_POINT_FILE_1, r'memory\test_layer')
    victim.geometries['Point']['features_layers']['unassigned'] = layer
    with open(str(INPUTS / 'lookups' / 'invreq_lookup.yaml'), 'r') as lookup:
        objl_lookup = yaml.safe_load(lookup)
    victim.set_unassigned_invreq('Point', objl_lookup, objl_lookup['OPTIONS'])
    with arcpy.da.SearchCursor(layer, ['invreq']) as cursor:
        test_data = list(cursor)
    option_14 = 'See HSSD Section 7.3.1, Unassigned Features'
    assert test_data[13][0] == ' ' # SBDARE check
    assert test_data[14][0] == option_14 
    assert test_data[0][0] == ' ' # OBJL name not in invreq_lookup.yaml check


def test_split_multipoint_env(victim):
    victim.split_multipoint_env()
    assert os.environ["OGR_S57_OPTIONS"] == "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON,ADD_SOUNDG_DEPTH=ON"


def test_store_gc_names(victim): 
    gc_rows =  [('GC_test_filename.zip', 'US5GA20M_S57_testfile', 'Review Complete', '2014\\GC'),
              ('GC11099.zip', 'US4AK55M', 'Review Complete', '2014\\GC')]
    victim.store_gc_names(gc_rows) 
    results = victim.gc_files
    assert 'GC_test_filename' in results
    assert len(results) == 1 # testing to verify the second row is ignored


def test_unapproved(victim):
    victim.set_feature_lookup()
    class_codes = {
        'LIGHTS': 75,
        'MORFAC': 84
    }
    unapproved_feature_subcategory = {'OBJL': class_codes['MORFAC'], 'CATMOR': 2}
    catmor_not_one = victim.unapproved('Point', unapproved_feature_subcategory)
    assert catmor_not_one
    unapproved_feature = {'OBJL': class_codes['LIGHTS']}
    unapproved_point_feature = victim.unapproved('Point', unapproved_feature)
    assert unapproved_point_feature


def test_unapproved_subcategory(victim):
    unapproved_feature_subcategory = {'OBJL_NAME': 'SLCONS', 'CONDTN': 2}
    slcons_condtn_is_two = victim.unapproved_subcategory('Point', 'SLCONS', unapproved_feature_subcategory)
    assert slcons_condtn_is_two