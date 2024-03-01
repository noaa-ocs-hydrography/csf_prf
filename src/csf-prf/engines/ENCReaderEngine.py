import pathlib
import json
import arcpy
import os
arcpy.env.overwriteOutput = True

from osgeo import ogr
from engines.Engine import Engine


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'


class ENCReaderEngine(Engine):
    def __init__(self, param_lookup: dict, sheets_layer) -> None:
        self.param_lookup = param_lookup
        self.sheets_layer = sheets_layer
        self.driver = None
        self.geometries = {
            'Point': {'features': [], 'layers': {'passed': None, 'failed': None}},
            'LineString': {'features': [], 'layers': {'passed': None, 'failed': None}},
            'Polygon': {'features': [], 'layers': {'passed': None, 'failed': None}}
        }

    def add_asgnmt_column(self):
        for feature_type in self.geometries.keys():
            # Passed layers
            self.add_column_and_constant(self.geometries[feature_type]['layers']['passed'], 'asgnmt', 2)
            
            # Failed layers
            self.add_column_and_constant(self.geometries[feature_type]['layers']['failed'], 'asgnmt', 1)

            # TODO For Info Only layers?
        with arcpy.da.SearchCursor(self.geometries['Point']['layers']['passed'], ["*"]) as searchCursor:
            for row in searchCursor:
                arcpy.AddMessage(row)

    
    def add_columns(self):
        self.add_asgnmt_column()
        self.add_invreq_column()

    def add_invreq_column(self):
        #  for feature_type in self.geometries.keys():
        pass

    def get_all_fields(self, features):
        fields = set()
        for feature in features:
            for field in feature['geojson']['properties'].keys():
                fields.add(field)
        return fields

    def get_polygon_types(self):
        foids = {}
        rcids = {}
        for feature in self.geometries['Polygon']:
            foid = (feature['geojson']['properties']['FIDN'], feature['geojson']['properties']['FIDS'])
            rcid = feature['geojson']['properties']['RCID']
            foids.setdefault(foid, 0)
            foids[foid] += 1
            rcids[rcid] = None
        print(foids.values())
        print(len(foids.keys()), '\n', len(rcids.keys()))
        print(len(self.geometries['Polygon']))

    def join_attributes(self):
        with arcpy.da.SearchCursor(self.geometries['Point']['layers']['passed'], ["*"]) as searchCursor:
            for row in searchCursor:
                arcpy.AddMessage(row)
    
    def open_file(self):
        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON"
        enc_file_path = self.param_lookup['enc_files'].valueAsText
        enc_file = self.driver.Open(enc_file_path, 0)
        return enc_file

    def perform_spatial_filter(self):

        arcpy.AddMessage(' - filtering features against sheets')
        # sorted_sheets = arcpy.management.Sort(sheets_layer, r'memory\sorted_sheets', [["scale", "ASCENDING"]])
        # POINTS
        point_fields = self.get_all_fields(self.geometries['Point']['features'])
        points_layer = arcpy.management.CreateFeatureclass('memory', 'points_layer', 'POINT', spatial_reference=arcpy.SpatialReference(4326))
        for field in point_fields:
            arcpy.management.AddField(points_layer, field, 'TEXT')

        arcpy.AddMessage('Building point features')
        for feature in self.geometries['Point']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            # TODO this is slow to open new every time, but field names change
            # Another option might be to have lookup by index and fill missing values to None
            with arcpy.da.InsertCursor(points_layer, current_fields, explicit=True) as point_cursor: 
                coords = feature['geojson']['geometry']['coordinates']
                geometry = arcpy.PointGeometry(arcpy.Point(X=coords[0], Y=coords[1]), arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                point_cursor.insertRow([geometry] + attribute_values)
        points_passed = arcpy.management.SelectLayerByLocation(points_layer, 'INTERSECT', self.sheets_layer)
        points_passed_layer = arcpy.management.MakeFeatureLayer(points_passed)
        point_failed = arcpy.management.SelectLayerByLocation(points_passed_layer, selection_type='SWITCH_SELECTION')
        self.geometries['Point']['layers']['passed'] = points_passed
        self.geometries['Point']['layers']['failed'] = point_failed
        arcpy.AddMessage(f'Points: {arcpy.management.GetCount(points_passed)}')

        # LINES
        line_fields = self.get_all_fields(self.geometries['LineString']['features'])
        lines_layer = arcpy.management.CreateFeatureclass('memory', 'lines_layer', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
        for field in line_fields:
            arcpy.management.AddField(lines_layer, field, 'TEXT')

        arcpy.AddMessage('Building line features')
        for feature in self.geometries['LineString']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            with arcpy.da.InsertCursor(lines_layer, current_fields, explicit=True) as line_cursor: 
                points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates']]
                coord_array = arcpy.Array(points)
                geometry = arcpy.Polyline(coord_array, arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                line_cursor.insertRow([geometry] + attribute_values)
        lines_passed = arcpy.management.SelectLayerByLocation(lines_layer, 'INTERSECT', self.sheets_layer)
        lines_passed_layer = arcpy.arcpy.management.MakeFeatureLayer(lines_passed)
        line_failed = arcpy.management.SelectLayerByLocation(lines_passed_layer, selection_type='SWITCH_SELECTION')
        self.geometries['LineString']['layers']['passed'] = lines_passed
        self.geometries['LineString']['layers']['failed'] = line_failed
        arcpy.AddMessage(f'Lines: {arcpy.management.GetCount(lines_passed)}')

        # POLYGONS
        polygons_fields = self.get_all_fields(self.geometries['Polygon']['features'])
        polygons_layer = arcpy.management.CreateFeatureclass('memory', 'polygons_layer', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
        for field in polygons_fields:
            arcpy.management.AddField(polygons_layer, field, 'TEXT')

        arcpy.AddMessage('Building Polygon features')
        for feature in self.geometries['Polygon']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            with arcpy.da.InsertCursor(polygons_layer, current_fields, explicit=True) as polygons_cursor: 
                polygons = feature['geojson']['geometry']['coordinates']
                if len(polygons) > 1:
                    points = [arcpy.Point(coord[0], coord[1]) for coord in polygons[0]]
                else:
                    points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates'][0]]
                coord_array = arcpy.Array(points)
                geometry = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                polygons_cursor.insertRow([geometry] + attribute_values)
        polygons_passed = arcpy.management.SelectLayerByLocation(polygons_layer, 'INTERSECT', self.sheets_layer)
        polygons_passed_layer = arcpy.arcpy.management.MakeFeatureLayer(polygons_passed)
        polygon_failed = arcpy.management.SelectLayerByLocation(polygons_passed_layer, selection_type='SWITCH_SELECTION')
        self.geometries['Polygon']['layers']['passed'] = polygons_passed
        self.geometries['Polygon']['layers']['failed'] = polygon_failed
        arcpy.AddMessage(f'Polygons: {arcpy.management.GetCount(polygons_passed)}')

        # Points: 5109, 373
        # Lines: 1857, 282
        # Polygons: 1660, 309
        # Points: 372
        # Lines: 286
        # Polygons: 309

    def print_geometries(self):
        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                print('\n', feature['type'], ':', feature['geojson'])
    
    def print_feature_total(self):
        points = arcpy.management.GetCount(self.geometries['Point']['layers']['passed'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['passed'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['passed'])
        arcpy.AddMessage(f'Total passed: {int(points[0]) + int(lines[0]) + int(polygons[0])}')
        points = arcpy.management.GetCount(self.geometries['Point']['layers']['failed'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['failed'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['failed'])
        arcpy.AddMessage(f'Total failed: {int(points[0]) + int(lines[0]) + int(polygons[0])}')

    def read_enc_features(self):
        """"""

        arcpy.AddMessage(' - reading ENC features')
        enc_file = self.open_file()
        for layer in enc_file:
            for feature in layer:
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False  

                    if geom_type in ['Point', 'LineString', 'Polygon']:
                        self.geometries[geom_type]['features'].append({'geojson': feature_json})
                    elif geom_type == 'MultiPoint':
                        # Create individual points for soundings
                        feature_template = json.loads(feature.ExportToJson())
                        feature_template['geometry']['type'] = 'Point'
                        for point in feature.geometry():
                            feature_template['geometry']['coordinates'] = [point.GetX(), point.GetY()]  # XY
                            self.geometries['Point']['features'].append({'geojson': feature_template})     
                    else:
                        if geom_type:
                            print(f'Unknown feature type: {geom_type}')

    def set_driver(self):
        arcpy.AddMessage(' - setting S57 driver')
        self.driver = ogr.GetDriverByName('S57')

    def start(self):
        self.set_driver()
        self.read_enc_features()
        # self.join_attributes()
        self.perform_spatial_filter()
        self.print_feature_total()
        self.add_columns()
