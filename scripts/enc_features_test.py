import pathlib
import json
import arcpy

from osgeo import ogr


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


class ENCReaderEngine:
    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup
        self.driver = None
        self.geometries = {
            'Point': [],
            'LineString': [],
            'Polygon': [],
            'other': []
        }
        
    def start(self):
        self.set_driver()
        self.filter_enc_geometries()
        # self.print_geometries()
        self.perform_spatial_filter(self.make_sheets_layer())


    def filter_enc_geometries(self):
        """"""

        enc_file = self.open_file()
        for i in range(enc_file.GetLayerCount()):
            layer = enc_file.GetLayer(i)
            # print(layer.GetExtent())  # always the same extent for every layer
            enc_geom_type = layer.GetGeomType()
            for j in range(layer.GetFeatureCount()):
                feature = layer.GetFeature(j)
                # TODO FME shows 967 features passed, 7659 failed.  Script only gets 42 and 47
                if feature:  # hundreds of features don't show up with GetFeature.  Look at else block.
                    # print(i, 'yes')
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                    if geom_type in ['Point', 'LineString', 'Polygon']:
                        self.geometries[geom_type].append({'type': enc_geom_type, 'geojson': feature_json})
                    else: # TODO do we need the others? geometry: None types
                        print(json.loads(feature.ExportToJson()))
                    #     self.geometries['other'].append({'type': enc_geom_type, 'geojson': feature_json})
                else:
                    # description = layer.GetDescription() # WRECK etc. 
                    print('\nelse:', j, layer.GetNextFeature().ExportToJson())  # TODO what is NextFeature?  hard to check RCID numbers
        
                    # # print(dir(layer.GetLayerDefn()))
                    # print(layer.GetLayerDefn().GetFieldDefn())
                    # print(layer.GetLayerDefn().GetName())

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
        sheet_layer = arcpy.management.MakeFeatureLayer(self.param_lookup['sheets'].valueAsText, field_info=field_info)
        layer = arcpy.management.CopyFeatures(sheet_layer, r'memory\sheets_layer')
        return layer
    
    def open_file(self):
        enc_file_path = self.param_lookup['enc_files'].valueAsText
        enc_file = self.driver.Open(enc_file_path, 0)
        return enc_file

    def perform_spatial_filter(self, sheets_layer):
        sorted_sheets = arcpy.management.Sort(sheets_layer, r'memory\sorted_sheets', [["scale", "ASCENDING"]])

        point_list = []
        for feature in self.geometries['Point']:
            coords = feature['geojson']['geometry']['coordinates']
            point_list.append(arcpy.PointGeometry(arcpy.Point(coords[0], coords[1])))
        if point_list:
            points_layer = arcpy.management.CopyFeatures(point_list, r'memory\points_layer')
            point_intersect = arcpy.analysis.PairwiseIntersect([points_layer, sorted_sheets], r'memory\point_intersect')
            print('Points:', len(point_list), arcpy.management.GetCount(point_intersect))
        
        lines_list = []
        for feature in self.geometries['LineString']:
            points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates']]
            coord_array = arcpy.Array(points)
            lines_list.append(arcpy.Polyline(coord_array))
        if lines_list:
            lines_layer = arcpy.management.CopyFeatures(lines_list, r'memory\lines_layer')
            line_intersect = arcpy.analysis.PairwiseIntersect([lines_layer, sorted_sheets], r'memory\line_intersect')
            print('Lines:', len(line_intersect), arcpy.management.GetCount(line_intersect))

        polygons_list = []
        for feature in self.geometries['Polygon']:
            polygons = feature['geojson']['geometry']['coordinates']
            if len(polygons) > 1:
                print('###################################\nMultipolygon')
                for polygon in polygons:
                    points = [arcpy.Point(coord[0], coord[1]) for coord in polygon]
                    coord_array = arcpy.Array(points)
                    polygons_list.append(arcpy.Polygon(coord_array)) 
            else:
                points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates'][0]]
                coord_array = arcpy.Array(points)
                polygons_list.append(arcpy.Polygon(coord_array))
        if polygons_list:
            polygons_layer = arcpy.management.CopyFeatures(polygons_list, r'memory\polygons_layer')
            polygon_intersect = arcpy.analysis.PairwiseIntersect([polygons_layer, sorted_sheets], r'memory\polygon_intersect')
            print('Polygons:', len(polygon_intersect), arcpy.management.GetCount(polygon_intersect))      


        # for row in arcpy.da.SearchCursor(sorted_sheets, ["SHAPE@"]):
        #     point_filter = [point for point in point_list if point.within(row)]
        #     line_filter = [line for line in lines_list if line.crosses(row)]
        #     polygon_filter = [polygon for polygon in polygons_list if polygon.intersect(row)]


    def print_geometries(self):
        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                print('\n', feature['type'], ':', feature['geojson'])

    def set_driver(self):
        self.driver = ogr.GetDriverByName('S57')


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