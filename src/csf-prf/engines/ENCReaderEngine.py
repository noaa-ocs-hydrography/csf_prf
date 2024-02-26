import json

from osgeo import ogr


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

    def filter_enc_geometries(self):
        """"""

        enc_file = self.open_file()
        for i, row in enumerate(range(0, enc_file.GetLayerCount())):
            layer = enc_file.GetLayer(row)
            enc_geom_type = layer.GetGeomType()
            for i in range(layer.GetFeatureCount()):
                feature = layer.GetFeature(i)
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                    if geom_type in ['Point', 'LineString', 'Polygon']:
                        self.geometries[geom_type].append({'type': enc_geom_type, 'geojson': feature_json})
                    # else: # TODO do we need the others? geometry: None types
                    #     self.geometries['other'].append({'type': enc_geom_type, 'geojson': feature_json})

    def open_file(self):
        enc_file_path = self.param_lookup['enc_files'].valueAsText
        enc_file = self.driver.Open(enc_file_path, 0)
        return enc_file
    
    def perform_spatial_filter(self, sheets_layer):
        # sort sheets layer by scale ascending
        # Use projected Sheets layer to spatial query all ENC files (Intersects, Crosses, Overlaps, Contains, Within)
        # 1. copy features management of geometry to in memory layer
        # 2. arcpy intersects, etc. 
        pass
    
    def print_geometries(self):
        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                print('\n', feature['type'], ':', feature['geojson'])

    def set_driver(self):
        self.driver = ogr.GetDriverByName('S57')