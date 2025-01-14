import json
import arcpy
import pathlib

from csf_prf.engines.Engine import Engine

arcpy.env.overwriteOutput = True


class MHWBufferEngine(Engine):
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.features = {'COALNE': [], 'SLCONS': []}

    def get_high_water_features(self):
        """Read ENC features and build HW dataset"""

        arcpy.AddMessage('Reading Feature records')
        enc_files = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        for enc_path in enc_files:
            # TODO should features be merged or unique across ENC files?
            enc_file = self.open_file(enc_path)
            enc_scale = pathlib.Path(enc_path).stem[2]
            for layer in enc_file:
                layer.ResetReading()
                name = layer.GetDescription()
                print(name)
                if name == 'COALNE':
                    print(name)
                    self.store_coalne_features(layer)
                elif name == 'SLCONS':
                    print(name)
                    self.store_slcons_features(layer)
                elif name == 'LNDARE':
                    print(name, layer)
                    # TODO what is LNDARE for?
                elif name == 'DSID':
                    metadata = layer.GetFeature(0)
                    metadata_json = json.loads(metadata.ExportToJson())
                    resolution = metadata_json['properties']['DSPM_CSCL']
                    scale_level = metadata_json['properties']['DSID_INTU']

    def print_properties(self, feature) -> None:
        for key, val in feature['properties'].items():
            print(key, val)
        print(feature['geometry'])

    def start(self) -> None:
        """Main method to begin process"""

        self.set_driver()
        # TODO do we need to allow GC features input or download?

        # TODO use input ENC files or download ENC files?

        self.get_high_water_features()
        # self.print_properties(self.features['SLCONS'][-1])
        # self.print_properties(self.features['COALNE'][-1])
        # open ENC files and read JSON features
        # if table == MapInfo
            # TODO get chart scale from MapInfo table
        # TODO get SLCONS features
            # TODO SLCONS 4, check if CONDTN not = piers/ruins
        
        # TODO Intersect chart scale with all features

        # TODO add attribute values

        # TODO project to WGS84?

        # TODO buffer selected features 

        # TODO remove donut polygons

        # TODO project again to NAD83?

        # TODO write out shapefile
        arcpy.AddMessage('Done')

    def store_coalne_features(self, layer: list[dict]) -> None:
        """Collect all COALNE features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                props = feature_json['properties']
                # TODO what is <Unfiltered> in FME?
                if props['WATLEV'] in ['', '2']:  # TODO is empty string == FME <Blank>
                    self.features['COALNE'].append(feature)

    def store_slcons_features(self, layer: list[dict]) -> None:
        """Collect all SLCONS features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                props = feature_json['properties']
                if props['CATSLC'] == '4':
                    if props['WATLEV'] == '2':
                        self.features['SLCONS'].append(feature)
                    else:
                        if props['CONDTN'] != '2':
                            self.features['SLCONS'].append(feature)
                else: # != 4
                    # TODO what is <Unfiltered> in FME?
                    if props['WATLEV'] in ['', '2']:  # TODO is empty string == FME <Blank>
                        self.features['SLCONS'].append(feature)
                    