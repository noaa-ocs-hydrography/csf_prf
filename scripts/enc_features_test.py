import pathlib
import json
import arcpy
import os
arcpy.env.overwriteOutput = True

from osgeo import ogr


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'

class ENCReaderEngine:
    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup
        self.driver = None
        self.geometries = {
            'Point': {'features': [], 'layers': {'passed': None, 'failed': None}},
            'LineString': {'features': [], 'layers': {'passed': None, 'failed': None}},
            'Polygon': {'features': [], 'layers': {'passed': None, 'failed': None}}
        }

    def get_enc_geometries(self):
        """"""
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

    def make_sheets_layer(self):
        """
        Create in memory layer for processing.
        This copies the input Sheets shapefile to not corrupt it.
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
        input_fields = arcpy.ListFields(self.param_lookup['sheets'].valueAsText)
        for field in input_fields:
            if field.name in fields.values():
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        sheets_layer = arcpy.management.MakeFeatureLayer(self.param_lookup['sheets'].valueAsText, field_info=field_info)
        return sheets_layer
    
    def open_file(self):
        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON"
        enc_file_path = self.param_lookup['enc_files'].valueAsText
        enc_file = self.driver.Open(enc_file_path, 0)
        return enc_file

    def perform_spatial_filter(self, sheets_layer):
        # sorted_sheets = arcpy.management.Sort(sheets_layer, r'memory\sorted_sheets', [["scale", "ASCENDING"]])
        # POINTS
        point_list = []
        for feature in self.geometries['Point']['features']:
            coords = feature['geojson']['geometry']['coordinates']
            point_list.append(arcpy.PointGeometry(arcpy.Point(X=coords[0], Y=coords[1]), arcpy.SpatialReference(4326)))
        if point_list:
            points_layer = arcpy.management.CopyFeatures(point_list, r'memory\points_layer')
            points_passed = arcpy.management.SelectLayerByLocation(points_layer, 'INTERSECT', sheets_layer)
            points_passed_layer = arcpy.arcpy.management.MakeFeatureLayer(points_passed)
            point_failed = arcpy.management.SelectLayerByLocation(points_passed_layer, selection_type='SWITCH_SELECTION')
            self.geometries['Point']['layers']['passed'] = points_passed
            self.geometries['Point']['layers']['failed'] = point_failed

        # LINES
        lines_list = []
        for feature in self.geometries['LineString']['features']:
            points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates']]
            coord_array = arcpy.Array(points)
            lines_list.append(arcpy.Polyline(coord_array, arcpy.SpatialReference(4326)))
        if lines_list:
            lines_layer = arcpy.management.CopyFeatures(lines_list, r'memory\lines_layer')
            lines_passed = arcpy.management.SelectLayerByLocation(lines_layer, 'INTERSECT', sheets_layer)
            lines_passed_layer = arcpy.arcpy.management.MakeFeatureLayer(lines_passed)
            line_failed = arcpy.management.SelectLayerByLocation(lines_passed_layer, selection_type='SWITCH_SELECTION')
            self.geometries['LineString']['layers']['passed'] = lines_passed
            self.geometries['LineString']['layers']['failed'] = line_failed

        # POLYGONS
        polygons_list = []
        for feature in self.geometries['Polygon']['features']:
            polygons = feature['geojson']['geometry']['coordinates']
            if len(polygons) > 1:
                points = [arcpy.Point(coord[0], coord[1]) for coord in polygons[0]]
                coord_array = arcpy.Array(points)
                polygons_list.append(arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))) 
            else:
                points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates'][0]]
                coord_array = arcpy.Array(points)
                polygons_list.append(arcpy.Polygon(coord_array, arcpy.SpatialReference(4326)))
        if polygons_list:
            polygons_layer = arcpy.management.CopyFeatures(polygons_list, r'memory\polygons_layer')
            polygons_passed = arcpy.management.SelectLayerByLocation(polygons_layer, 'INTERSECT', sheets_layer)
            polygons_passed_layer = arcpy.arcpy.management.MakeFeatureLayer(polygons_passed)
            polygon_failed = arcpy.management.SelectLayerByLocation(polygons_passed_layer, selection_type='SWITCH_SELECTION')
            self.geometries['Polygon']['layers']['passed'] = polygons_passed
            self.geometries['Polygon']['layers']['failed'] = polygon_failed

    def print_geometries(self):
        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                print('\n', feature['type'], ':', feature['geojson'])
    
    def print_feature_total(self):
        points = arcpy.management.GetCount(self.geometries['Point']['layers']['passed'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['passed'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['passed'])
        print('Total passed:', int(points[0]) + int(lines[0]) + int(polygons[0]))
        points = arcpy.management.GetCount(self.geometries['Point']['layers']['failed'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['failed'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['failed'])
        print('Total failed:', int(points[0]) + int(lines[0]) + int(polygons[0]))

    def set_driver(self):
        self.driver = ogr.GetDriverByName('S57')

    def start(self):
        self.set_driver()
        self.get_enc_geometries()
        # self.print_geometries()
        # self.get_polygon_types()
        self.perform_spatial_filter(self.make_sheets_layer())
        self.print_feature_total()


if __name__ == "__main__":
    class ENCParam:
        valueAsText = str(INPUTS / 'US4MA04M.000')
    class SheetsParam:
        valueAsText = str(INPUTS / 'OPR_A325_KR_24_Sheets_09262023_FULL_AREA_NO_LIDAR.shp')
    param_lookup = {
        'enc_files': ENCParam(),
        'sheets': SheetsParam()
    }
    engine = ENCReaderEngine(param_lookup)
    engine.start()