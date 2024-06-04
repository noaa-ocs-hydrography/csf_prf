import os
import requests
import zipfile
import shutil
import pathlib
import json


from osgeo import ogr
from csf_prf.engines.Engine import Engine

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class ClipEncEngine(Engine):
    """Class to perform supersession on ENC files"""

    def __init__(self, param_lookup: dict) -> None:
        self.input_folder = param_lookup['input_folder'].valueAsText
        self.output_folder = param_lookup['output_folder'].valueAsText
        self.driver = None

    def intersect_enc_files(self, enc_sorter):
        output_path = str(pathlib.Path(self.output_folder) / 'US5_Joined_ENC.000')
        output_enc = self.driver.CreateDataSource(output_path)
        
        scales = list(sorted(enc_sorter.keys()))  # 1, 2, 3, 4, 5
        print('All scales:', scales)
        for i, scale in enumerate(scales):  # treat lowest scale differently
            upper_scale = scale + 1
            if upper_scale in scales:
                print(f'Lower: {scale}, Upper: {upper_scale}')
                for lower_path in enc_sorter[scale]: 
                    for upper_path in enc_sorter[upper_scale]:
                        self.erase_lower(i, lower_path, upper_path, output_enc)
        output_enc = None

    def get_extent_polygon(self, extent):
        xMin, xMax, yMin, yMax = extent
        extent_geom = ogr.Geometry(ogr.wkbLinearRing)
        extent_geom.AddPoint(xMin, yMin)
        extent_geom.AddPoint(xMin, yMax)
        extent_geom.AddPoint(xMax, yMax)
        extent_geom.AddPoint(xMax, yMin)
        extent_geom.AddPoint(xMin, yMin)
        extent_polygon = ogr.Geometry(ogr.wkbPolygon)
        extent_polygon.AddGeometry(extent_geom)
        return extent_polygon

    def erase_lower(self, scale_number, lower_path, upper_path, output_enc):
        lower_enc = self.driver.Open(str(lower_path))
        upper_enc = self.driver.Open(str(upper_path))
        for lower_layer in lower_enc:
            lower_layer.ResetReading()
            lower_name = lower_layer.GetName()
            print(lower_name)
            upper_layer = upper_enc.GetLayerByName(lower_name)
            if upper_layer:
                upper_extent_polygon = self.get_extent_polygon(upper_layer.GetExtent())  # Used to ignore intersect features in upper layer
                # TODO
                # Forward - add all lower to new layer, run erase with new layer against upper, add upper layer
                output_layer = output_enc.GetLayerByName(lower_name)
                feature_definition = output_layer.GetLayerDefn()

                # TODO fine tune this logic for more layers or missing data
                if output_layer is None or lower_name == 'DSID':
                    print(f'Skipping layer: {lower_name}')
                else:
                    if upper_layer is not None:
                        print(f'Layer Supersession: {lower_name}')
                        if scale_number == 0:
                            # ex: remove 1 features overlapped by 2 and store in output_layer
                            lower_layer.Erase(upper_layer, output_layer)
                        else:
                            # ex: 2 features are already in output_layer.  Need manually remove feature from output_layer
                            for feature in output_layer:
                                self.manually_remove_lower_feature(feature, output_layer, upper_extent_polygon)

                        # Always add upper scale layer features to output
                        for feature in upper_layer:
                            self.store_feature(feature, output_layer, feature_definition)

        output_enc = None
        lower_enc = None
        upper_enc = None
        
    def get_enc_files(self):
        enc_files = []
        for file in os.listdir(self.input_folder):
            if file.endswith('.000'):
                enc_files.append(pathlib.Path(self.input_folder) / file)
        return enc_files
        
    def get_enc_list(self):
        enc_files = self.get_enc_files()
        enc_sorter = {}
        for enc_file in enc_files:
            scale = int(enc_file.stem[2])
            if scale not in enc_sorter.keys():
                enc_sorter[scale] = []
            enc_sorter[scale].append(enc_file)
        return enc_sorter
    
    def manually_remove_lower_feature(self, feature, output_layer, upper_extent_polygon):
        feature_json = json.loads(feature.ExportToJson())
        if feature_json['geometry'] is None:
            return
        
        feature_geometry = ogr.CreateGeometryFromJson(json.dumps(feature_json['geometry']))

        xMin, xMax, yMin, yMax = upper_extent_polygon
        extent_geom = ogr.Geometry(ogr.wkbLinearRing)
        extent_geom.AddPoint(xMin, yMin)
        extent_geom.AddPoint(xMin, yMax)
        extent_geom.AddPoint(xMax, yMax)
        extent_geom.AddPoint(xMax, yMin)
        extent_geom.AddPoint(xMin, yMin)
        extent_polygon = ogr.Geometry(ogr.wkbPolygon)
        extent_polygon.AddGeometry(extent_geom)

        if feature_geometry.Intersects(extent_polygon):
            output_layer.DeleteFeature(feature.GetFID())

    def start(self) -> None:
        self.driver = ogr.GetDriverByName('S57')
        self.set_config_options()
        enc_sorter = self.get_enc_list()
        # TODO create new ENC file and add to it?
        self.intersect_enc_files(enc_sorter)
        # clip by top to bottom of stacked ENCs
            # if no clip, only take features from stacked ENC order
        # output clipped ENC files to output folder

    def store_feature(self, feature, output_layer, feature_definition):        
        # better_feature = feature.Clone()
        out_feat = ogr.Feature(feature_definition)
        geometry = feature.GetGeometryRef()
        out_feat.SetGeometry(geometry)
        output_layer.CreateFeature(out_feat)
        output_layer.SyncToDisk()
        out_feat = None

    def set_config_options(self):
        os.environ["OGR_S57_OPTIONS"] = "GDAL_VALIDATE_CREATION_OPTIONS=ON,UPDATES=APPLY,RETURN_PRIMITIVES=ON,RETURN_LINKAGES=ON,LNAM_REFS=ON"
 