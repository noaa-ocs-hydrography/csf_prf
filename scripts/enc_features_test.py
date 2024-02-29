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
            'Point': [],
            'LineString': [],
            'Polygon': [],
        }

    def get_enc_geometries(self):
        """"""
        enc_file = self.open_file()
        for layer in enc_file:
            enc_geom_type = layer.GetGeomType()
            for feature in layer:
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False  

                    if geom_type in ['Point', 'LineString', 'Polygon']:
                        self.geometries[geom_type].append({'type': enc_geom_type, 'geojson': feature_json})
                    elif geom_type == 'MultiPoint':
                        # Create individual points for soundings
                        feature_template = json.loads(feature.ExportToJson())
                        feature_template['geometry']['type'] = 'Point'
                        for point in feature.geometry():
                            feature_template['geometry']['coordinates'] = [point.GetX(), point.GetY()]  # XY
                            self.geometries['Point'].append({'type': enc_geom_type, 'geojson': feature_template})     
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
        for feature in self.geometries['Point']:
            coords = feature['geojson']['geometry']['coordinates']
            point_list.append(arcpy.PointGeometry(arcpy.Point(X=coords[0], Y=coords[1]), arcpy.SpatialReference(4326)))
        if point_list:
            points_layer = arcpy.management.CopyFeatures(point_list, r'memory\points_layer')
            point_intersect = arcpy.management.SelectLayerByLocation(points_layer, 'INTERSECT', sheets_layer)
            print('Points:', len(point_list), arcpy.management.GetCount(point_intersect)) 
        
        # LINES
        lines_list = []
        for feature in self.geometries['LineString']:
            points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates']]
            coord_array = arcpy.Array(points)
            lines_list.append(arcpy.Polyline(coord_array, arcpy.SpatialReference(4326)))
        if lines_list:
            lines_layer = arcpy.management.CopyFeatures(lines_list, r'memory\lines_layer')
            line_intersect = arcpy.management.SelectLayerByLocation(lines_layer, 'INTERSECT', sheets_layer)
            print('Lines:', len(lines_list), arcpy.management.GetCount(line_intersect))

        # POLYGONS
        polygons_list = []
        for feature in self.geometries['Polygon']:
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
            polygon_intersect = arcpy.management.SelectLayerByLocation(polygons_layer, 'INTERSECT', sheets_layer)
            print('Polygons:', len(polygons_list), arcpy.management.GetCount(polygon_intersect))    

    def print_geometries(self):
        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                print('\n', feature['type'], ':', feature['geojson'])

    def set_driver(self):
        self.driver = ogr.GetDriverByName('S57')

    def start(self):
        self.set_driver()
        self.get_enc_geometries()
        # self.print_geometries()
        # self.get_polygon_types()
        self.perform_spatial_filter(self.make_sheets_layer())


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