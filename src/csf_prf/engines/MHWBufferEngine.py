import json
import arcpy
import pathlib

from csf_prf.engines.Engine import Engine

arcpy.env.overwriteOutput = True

OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class MHWBufferEngine(Engine):
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.features = {'COALNE': [], 'SLCONS': []}
        self.chartscale_layer = None

    def build_feature_layers(self) -> None:
        """Create layers for all coastal features"""

        for feature_type in self.features:
            line_fields = self.get_all_fields(self.features[feature_type])
            lines_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_lines', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
            sorted_line_fields = sorted(line_fields)
            for field in sorted_line_fields:
                arcpy.management.AddField(lines_layer, field, 'TEXT', field_length=100, field_is_nullable='NULLABLE')
            arcpy.management.AddField(lines_layer, 'layer_type', 'TEXT', field_length=10, field_is_nullable='NULLABLE')

            arcpy.AddMessage(f' - Building {feature_type} features')
            cursor_fields = ['SHAPE@JSON'] + sorted_line_fields + ['layer_type']
            with arcpy.da.InsertCursor(lines_layer, cursor_fields, explicit=True) as line_cursor: 
                for feature in self.features[feature_type]:
                    attribute_values = ['' for i in range(len(cursor_fields))]
                    geometry = feature['geometry']
                    attribute_values[0] = arcpy.AsShape(geometry).JSON
                    for fieldname, attr in list(feature['properties'].items()):
                        field_index = line_cursor.fields.index(fieldname)
                        attribute_values[field_index] = str(attr)
                    layer_type_index = line_cursor.fields.index('layer_type')
                    attribute_values[layer_type_index] = feature_type
                    line_cursor.insertRow(attribute_values)
        
            self.features[feature_type] = lines_layer  # overwrite memory with layer

    def get_chartscale_layer(self) -> None:
        """Create layer for ChartScale features"""

        self.chartscale_layer = arcpy.management.CreateFeatureclass(
            'memory', 
            f'chartscale_layer', 
            'POLYGON', 
            spatial_reference=arcpy.SpatialReference(4326))

    def get_high_water_features(self):
        """Read ENC features and build HW dataset"""

        arcpy.AddMessage('Reading Feature records')
        if not self.param_lookup['enc_files'].valueAsText:
            self.download_enc_files()
            
        enc_files = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        for enc_path in enc_files:
            # TODO should features be merged or unique across ENC files?
            enc_file = self.open_file(enc_path)
            for layer in enc_file:
                layer.ResetReading()
                name = layer.GetDescription()
                if name == 'COALNE':
                    self.store_coalne_features(layer)
                elif name == 'SLCONS':
                    self.store_slcons_features(layer)
                elif name == 'LNDARE':
                    # TODO what is LNDARE for?
                    continue
                # elif name == 'DSID':
                #     metadata = layer.GetFeature(0)
                #     metadata_json = json.loads(metadata.ExportToJson())
                #     resolution = metadata_json['properties']['DSPM_CSCL']
                #     scale_level = metadata_json['properties']['DSID_INTU']
                #     print(resolution, scale_level)

    def merge_feature_layers(self) -> None:
        """Merge together the COALNE and SLCONS features"""

        self.features['merged'] = arcpy.management.Merge(
            [self.features[feature_type] for feature_type in self.features if self.features[feature_type]],
            f'{OUTPUTS / "merged_layers.shp"}')
        
    def perform_spatial_filter(self) -> None:
        """Select features that intersect the chart scalelayer"""

        pass

    def print_properties(self, feature: dict) -> None:
        """Helper function to view feature details"""

        for key, val in feature['properties'].items():
            print(key, val)
        print(feature['geometry'])

    def start(self) -> None:
        """Main method to begin process"""

        self.set_driver()
        self.return_primitives_env()
        # TODO do we need to allow GC features input or download?

        self.get_high_water_features()
        self.build_feature_layers()
        self.get_chartscale_layer()
        self.merge_feature_layers()

        # TODO Intersect chart scale with all features
        self.perform_spatial_filter()

        # TODO add attribute values

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
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                # TODO do we only use lines?
                if geom_type == 'LineString':
                    self.features['COALNE'].append(feature_json)

    def store_slcons_features(self, layer: list[dict]) -> None:
        """Collect all SLCONS features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                if geom_type == 'LineString':
                    props = feature_json['properties']
                    if 'CATSLC' in props and props['CATSLC'] == 4:
                        if props['WATLEV'] == 2:
                            self.features['SLCONS'].append(feature_json)
                        else:
                            if props['CONDTN'] != 2:
                                self.features['SLCONS'].append(feature_json)
                    else: # != 4
                        if props['WATLEV'] is None or props['WATLEV'] in ['', 2]:
                            self.features['SLCONS'].append(feature_json)
                    