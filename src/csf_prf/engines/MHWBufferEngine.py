import json
import arcpy
import pathlib
import yaml

from csf_prf.engines.Engine import Engine

arcpy.env.overwriteOutput = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class MHWBufferEngine(Engine):
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.features = {'COALNE': [], 'SLCONS': []}
        self.layers = {'buffered': None, 'dissolved': None, 'merged': None, 
                       'COALNE': None, 'SLCONS': None}
        self.chartscale_layer = None
        
    def buffer_lines(self) -> None:
        """Buffer the MHW lines by meters for each Chart scale"""

        self.layers['buffered'] = arcpy.management.CreateFeatureclass(
            'memory', 
            f'buffered_layer', 
            'POLYGON', 
            spatial_reference=arcpy.SpatialReference(4326)  # web mercator
        )
        arcpy.management.AddField(self.layers['buffered'], 'display_scale', 'LONG')

        with arcpy.da.InsertCursor(self.layers['buffered'], ['SHAPE@', 'display_scale']) as cursor: 
            with arcpy.da.SearchCursor(self.layers['merged'], ['SHAPE@', 'display_scale']) as merged_cursor:
                for row in merged_cursor:
                    projected_geom = row[0].projectAs(arcpy.SpatialReference(5070), 'WGS_1984_(ITRF00)_To_NAD_1983')  # Albers Equal Equal 2011 NAD83
                    chart_scale = self.get_chart_scale(row[1])
                    buffered = projected_geom.buffer(chart_scale).projectAs(arcpy.SpatialReference(4326), 'WGS_1984_(ITRF00)_To_NAD_1983')  # buffer and back to WGS84
                    cursor.insertRow([buffered, row[1]])

        del self.layers['merged']
        arcpy.management.CopyFeatures(self.layers['buffered'], str(OUTPUTS / 'cursor_buffered.shp'))

    def build_feature_layers(self) -> None:
        """Create layers for all coastal features"""

        for feature_type in self.features:
            line_fields = self.get_all_fields(self.features[feature_type])
            self.layers[feature_type] = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_lines', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
            sorted_line_fields = sorted(line_fields)
            for field in sorted_line_fields:
                arcpy.management.AddField(self.layers[feature_type], field, 'TEXT', field_length=100, field_is_nullable='NULLABLE')
            arcpy.management.AddField(self.layers[feature_type], 'layer_type', 'TEXT', field_length=10, field_is_nullable='NULLABLE')

            arcpy.AddMessage(f' - Building {feature_type} features')
            cursor_fields = ['SHAPE@JSON'] + sorted_line_fields + ['layer_type']
            with arcpy.da.InsertCursor(self.layers[feature_type], cursor_fields, explicit=True) as line_cursor: 
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

    def clip_sheets(self) -> None:
        """Clip input sheets boundary with dissolved MHW layer"""

        sheet_parameter = self.param_lookup['sheets'].valueAsText
        # Create output sheets to manipulate
        sheet_layer = arcpy.management.CopyFeatures(sheet_parameter, str(OUTPUTS / 'sheet_clipped.shp'))
        dissolved_selection = arcpy.management.SelectLayerByLocation(self.layers['dissolved'], 'INTERSECT', sheet_layer)
        with arcpy.da.SearchCursor(dissolved_selection, ['SHAPE@']) as dissolved_cursor:
            dissolved_polygons = [row[0] for row in dissolved_cursor]
        with arcpy.da.UpdateCursor(sheet_layer, ['SHAPE@']) as sheet_cursor:
            for row in sheet_cursor:
                sheet_geom = row[0]
                for polygon in dissolved_polygons:
                    if not sheet_geom.disjoint(polygon):
                        sheet_geom = sheet_geom.difference(polygon)
                sheet_cursor.updateRow([sheet_geom])
        
    def dissolve_polygons(self) -> None:
        """Dissolve overlappingi polygons to create a single polygon"""
        self.layers['dissolved'] = arcpy.management.Dissolve(self.layers['buffered'], str(pathlib.Path('memory') / 'dissolved_layer'), multi_part='SINGLE_PART')
        # arcpy.management.CopyFeatures(self.layers['dissolved'], str(OUTPUTS / 'cursor_dissolved.shp'))

    def get_chart_scale(self, current_scale) -> int:
        """Get the upper chart scale or max chart scale for the current input chart scale"""

        with open(str(INPUTS / 'lookups' / 'chartscale.yaml'), 'r') as lookup:
            chartscale_lookup = yaml.safe_load(lookup)
        scale_numbers = [int(scale) for scale in chartscale_lookup]
        for lower_resolution, higher_resolution in zip(scale_numbers, list(scale_numbers)[1:]):
            if lower_resolution < int(current_scale) <= higher_resolution:
                return chartscale_lookup[higher_resolution]
            elif int(current_scale) > higher_resolution:
                continue
        return chartscale_lookup[max(scale_numbers)]

    def get_enc_display_scale(self, enc_file) -> str:
        """Obtain ENC resolution scale for setting buffer value"""

        metadata_layer = enc_file.GetLayerByName('DSID')
        metadata = metadata_layer.GetFeature(0)
        metadata_json = json.loads(metadata.ExportToJson())
        display_scale = metadata_json['properties']['DSPM_CSCL']
        return display_scale

    def get_high_water_features(self):
        """Read ENC features and build HW dataset"""

        arcpy.AddMessage('Reading Feature records')   
        enc_files = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            enc_scale = pathlib.Path(enc_path).stem[2]
            display_scale = self.get_enc_display_scale(enc_file)
            for layer in enc_file:
                layer.ResetReading()
                name = layer.GetDescription()
                # TODO can we just use geometry and disregard attributes?
                if name == 'COALNE':
                    self.store_coalne_features(layer, enc_scale, display_scale)
                elif name == 'SLCONS':
                    self.store_slcons_features(layer, enc_scale, display_scale)
                elif name == 'LNDARE':
                    # TODO what is LNDARE for?
                    continue
                elif name == 'PONTON':
                    # TODO is PONTON needed?
                    continue

    def merge_feature_layers(self) -> None:
        """Merge together the COALNE and SLCONS features"""

        self.layers['merged'] = arcpy.management.CreateFeatureclass(
            'memory', 
            f'merged_layer', 
            'POLYLINE', 
            spatial_reference=arcpy.SpatialReference(4326)
        )
        arcpy.management.AddField(self.layers['merged'], 'display_scale', 'LONG')

        with arcpy.da.InsertCursor(self.layers['merged'], ['SHAPE@', 'display_scale']) as cursor: 
            for feature_type in ['COALNE', 'SLCONS']:
                if self.layers[feature_type]:
                    with arcpy.da.SearchCursor(self.layers[feature_type], ['SHAPE@', 'DISPLAY_SCALE']) as feature_cursor:
                        for row in feature_cursor:
                            cursor.insertRow(row)

        # arcpy.management.CopyFeatures(self.features['merged'], str(OUTPUTS / 'cursor_merged.shp'))

    def print_properties(self, feature: dict) -> None:
        """Helper function to view feature details"""

        for key, val in feature['properties'].items():
            print(key, val)
        print(feature['geometry'])

    def remove_inner_polygons(self) -> None:
        """"Only keep the first geometry for each polygon feature"""

        with arcpy.da.UpdateCursor(self.layers['dissolved'], ['SHAPE@']) as cursor:
            for row in cursor:
                row_json = json.loads(row[0].JSON)
                outer_polygon = row_json['rings'][0]
                points = [arcpy.Point(x, y) for x, y in outer_polygon]
                point_array = arcpy.Array(points)
                cursor.updateRow([arcpy.Polygon(point_array, arcpy.SpatialReference(4326))])

    # def remove_unassigned_buffer(self) -> None:
    #     """Remove features that are outside of 1km from Sheets boundary"""
        
    #     output_folder = self.param_lookup['output_folder'].valueAsText
    #     buffer_1km = arcpy.analysis.Buffer(self.sheets_layer, str(pathlib.Path('memory') / 'sheets_buffer'), '1 kilometers')

    #     # Create list from buffer cursor iterator to use it over and over
    #     # Iterator by default would only work once
    #     buffer_cursor = [row for row in arcpy.da.UpdateCursor(unassigned_buffer, ["SHAPE@"])]

    #     for geom_type in self.geometries:
    #         unassigned_deleted = 0
    #         arcpy.AddMessage(f'Removing {geom_type} unassigned outside of 1km')
    #         feature_records = self.geometries[geom_type]['features_layers']['unassigned']
    #         feature_count = arcpy.management.GetCount(feature_records)
    #         # arcpy.management.CopyFeatures(feature_records, os.path.join(output_folder, f'{geom_type}_unassigned_copy.shp')) # Output full unassigned dataset
    #         with arcpy.da.UpdateCursor(feature_records, ["SHAPE@"]) as feature_cursor:
    #             for row in feature_cursor:
    #                 inside = False
    #                 for buffer_row in buffer_cursor:
    #                     disjointed = row[0].disjoint(buffer_row[0])
    #                     if not disjointed:
    #                         inside = True
    #                         break
    #                 if not inside:
    #                     unassigned_deleted += 1
    #                     feature_cursor.deleteRow()
    #         arcpy.AddMessage(f' - Deleted {unassigned_deleted} of {feature_count} unassigned {geom_type} features')
    #     del buffer_cursor

    def start(self) -> None:
        """Main method to begin process"""

        if not self.param_lookup['enc_files'].valueAsText:
            self.download_enc_files()
        self.set_driver()
        self.return_primitives_env()
        # TODO do we need to allow GC features input or download?
        self.get_high_water_features()
        self.build_feature_layers()
        # TODO implement 1km feature removal?
        # self.remove_unassigned_buffer()
        self.merge_feature_layers()
        self.buffer_lines()
        self.dissolve_polygons()
        self.remove_inner_polygons()
        self.clip_sheets()

        arcpy.management.CopyFeatures(self.layers['dissolved'], str(OUTPUTS / 'cursor_dissolved.shp'))

        arcpy.AddMessage('Done')

    def store_coalne_features(self, layer: list[dict], enc_scale: str, display_scale: str) -> None:
        """Collect all COALNE features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                # TODO do we only use lines?
                if geom_type == 'LineString':
                    feature_json['properties']['DISPLAY_SCALE'] = display_scale
                    self.features['COALNE'].append(feature_json)

    def store_slcons_features(self, layer: list[dict], enc_scale: str, display_scale: str) -> None:
        """Collect all SLCONS features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                if geom_type == 'LineString':
                    feature_json['properties']['DISPLAY_SCALE'] = display_scale
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
                    