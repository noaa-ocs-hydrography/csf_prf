import json
import arcpy
import pathlib
import yaml
import shutil
import gc

from csf_prf.engines.Engine import Engine

arcpy.env.overwriteOutput = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class EncExtentsFolderNotFound(Exception):
    """Exception for missing ENC Extents folder"""
    pass


class MHWBufferEngine(Engine):
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.features = {'COALNE': [], 'SLCONS': [], 'LNDARE': []}
        self.layers = {'buffered': None, 'dissolved': None, 'merged': None, 
                       'COALNE': None, 'SLCONS': None, 'LNDARE': None}
        self.chartscale_layer = None
        self.scale_bounds = {}
        self.intersected = 0
        self.scale_conversion = 0.0008

    def buffer_features(self) -> None:
        """Buffer the MHW features by meters for each Chart scale"""

        arcpy.AddMessage('Buffering features by Chart Scale')

        # 'buffered' layer is written to file
        # supersession is too much for in_memory layers
        output_folder = self.param_lookup['output_folder'].valueAsText
        self.layers['buffered'] = arcpy.management.CreateFeatureclass(
            output_folder,
            f'buffered_mhw_polygons.shp', 
            'POLYGON', 
            spatial_reference=arcpy.SpatialReference(4326)  # web mercator
        )
        arcpy.management.AddField(self.layers['buffered'], 'disp_scale', 'LONG')
        arcpy.management.AddField(self.layers['buffered'], 'enc_scale', 'SHORT')

        with arcpy.da.InsertCursor(self.layers['buffered'], ['SHAPE@', 'disp_scale', 'enc_scale']) as cursor: 
            with arcpy.da.SearchCursor(self.layers['merged'], ['SHAPE@', 'display_scale', 'enc_scale']) as merged_cursor:
                for row in merged_cursor:
                    projected_geom = row[0].projectAs(arcpy.SpatialReference(5070), 'WGS_1984_(ITRF00)_To_NAD_1983')  # Albers Equal Equal 2011 NAD83
                    chart_scale = int(row[1]) * self.scale_conversion
                    buffered = projected_geom.buffer(chart_scale).projectAs(arcpy.SpatialReference(4326), 'WGS_1984_(ITRF00)_To_NAD_1983')  # buffer and back to WGS84
                    cursor.insertRow([buffered, row[1], row[2]])
                arcpy.AddMessage(f' - buffered lines')

            with arcpy.da.SearchCursor(self.layers['LNDARE'], ['SHAPE@', 'display_scale', 'enc_scale']) as land_cursor:
                for row in land_cursor:
                    projected_geom = row[0].projectAs(arcpy.SpatialReference(5070), 'WGS_1984_(ITRF00)_To_NAD_1983')  # Albers Equal Equal 2011 NAD83
                    chart_scale = int(row[1]) * self.scale_conversion
                    buffered = projected_geom.buffer(chart_scale).projectAs(arcpy.SpatialReference(4326), 'WGS_1984_(ITRF00)_To_NAD_1983')  # buffer and back to WGS84
                    cursor.insertRow([buffered, row[1], row[2]])
                arcpy.AddMessage(f' - buffered polygons')

    def build_area_features(self) -> None:
        """Create layers for all linear coastal features"""

        for feature_type in self.features:
            if feature_type == 'LNDARE':
                self.layers[feature_type] = arcpy.management.CreateFeatureclass(
                    'memory', 
                    f'{feature_type}_polygons', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
                self.build_layer(feature_type)

    def build_layer(self, feature_type: str) -> None:
        """Logic for loading data into in-memory layers"""
        
        all_fields = self.get_all_fields(self.features[feature_type])
        sorted_fields = sorted(all_fields)
        for field in sorted_fields:
            arcpy.management.AddField(self.layers[feature_type], field, 'TEXT', field_length=100, field_is_nullable='NULLABLE')
        arcpy.management.AddField(self.layers[feature_type], 'layer_type', 'TEXT', field_length=10, field_is_nullable='NULLABLE')

        arcpy.AddMessage(f'Building {feature_type} layer')
        cursor_fields = ['SHAPE@JSON'] + sorted_fields + ['layer_type']
        with arcpy.da.InsertCursor(self.layers[feature_type], cursor_fields, explicit=True) as feature_cursor: 
            for feature in self.features[feature_type]:
                attribute_values = ['' for i in range(len(cursor_fields))]
                geometry = feature['geometry']
                attribute_values[0] = arcpy.AsShape(geometry).JSON
                for fieldname, attr in list(feature['properties'].items()):
                    field_index = feature_cursor.fields.index(fieldname)
                    attribute_values[field_index] = str(attr)
                layer_type_index = feature_cursor.fields.index('layer_type')
                attribute_values[layer_type_index] = feature_type
                feature_cursor.insertRow(attribute_values)

    def build_line_features(self) -> None:
        """Create layers for all linear coastal features"""

        for feature_type in self.features:
            if feature_type in ['COALNE', 'SLCONS']:
                self.layers[feature_type] = arcpy.management.CreateFeatureclass(
                    'memory', 
                    f'{feature_type}_lines', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
                self.build_layer(feature_type)

    def clip_sheets(self) -> None:
        """Clip input sheets boundary with dissolved MHW layer"""

        arcpy.AddMessage('Clipping Sheets with MHW polygons')
        sheet_parameter = self.param_lookup['sheets'].valueAsText
        # Create output sheets to manipulate
        self.layers['clipped_sheets'] = arcpy.management.CopyFeatures(sheet_parameter, str(pathlib.Path('memory') / 'clipped_sheets'))
        dissolved_selection = arcpy.management.SelectLayerByLocation(self.layers['dissolved'], 'INTERSECT', self.layers['clipped_sheets'])
        with arcpy.da.SearchCursor(dissolved_selection, ['SHAPE@']) as dissolved_cursor:
            dissolved_polygons = [row[0] for row in dissolved_cursor]
        with arcpy.da.UpdateCursor(self.layers['clipped_sheets'], ['SHAPE@']) as sheet_cursor:
            for row in sheet_cursor:
                sheet_geom = row[0]
                for polygon in dissolved_polygons:
                    if not sheet_geom.disjoint(polygon):
                        sheet_geom = sheet_geom.difference(polygon)
                sheet_cursor.updateRow([sheet_geom])

    def delete_enc_extents(self) -> None:
        """Remove the 'enc_extents' folder and shapefiles are tool runs"""

        enc_extents_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText) / 'enc_extents'
        if enc_extents_folder.exists():
            shutil.rmtree(enc_extents_folder)

    def dissolve_polygons(self) -> None:
        """Dissolve overlapping polygons to create a single polygon"""

        arcpy.AddMessage('Dissolving overlapping polygons')
        self.layers["dissolved"] = arcpy.management.Dissolve(
            self.layers["buffered"],
            str(pathlib.Path("memory") / "dissolved_layer"),
            multi_part="SINGLE_PART",
        )

    def erase_covered_features(self) -> None:
        """Use buffered upper level extent polygons to erase covered lower level buffered features"""

        arcpy.AddMessage(f'Removing lower scale features covered by upper scale charts')
        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)
        enc_extents_folder = output_folder / 'enc_extents'
        if not enc_extents_folder.exists():
            raise EncExtentsFolderNotFound(f'Error - Missing {enc_extents_folder} folder')
        extent_shapefiles = enc_extents_folder.rglob('extent_*.shp')
        scale_extent_lookup = {}
        for scale in range(2, 7):
            scale_extent_lookup[str(scale)] = []
        for shp in extent_shapefiles:
            scale = str(shp.stem)[9]
            if scale == '1':  # TODO should be also skip 2?ddd
                continue
            scale_extent_lookup[scale].append(str(shp))

        lndare_start = arcpy.management.GetCount(self.layers['buffered'])

        # Check if any upper level scale extent polygons are available
        if scale_extent_lookup[str(3)] or scale_extent_lookup[str(4)] or scale_extent_lookup[str(5)] or scale_extent_lookup[str(6)]:
            # Select lowest scale features from buffered
            scale_level_2_features = arcpy.management.SelectLayerByAttribute(self.layers['buffered'], "NEW_SELECTION", 'enc_scale = ' + "2")
            # Create an in memory layer of all upper level extent polygons
            # TODO does each extent polygon need to be buffered as well to properly overlap buffered LNDARE, COALNE, SLCONS features?
            merged_upper_extents = 'memory/scale_2_extents'
            arcpy.management.Merge(scale_extent_lookup[str(3)] + scale_extent_lookup[str(4)] + scale_extent_lookup[str(5)] + scale_extent_lookup[str(6)], 
                                                            merged_upper_extents)
            # Erase lowest level buffered features covered by all upper level extent polygons merged together
            erased = arcpy.analysis.Erase(scale_level_2_features, merged_upper_extents, 'memory/scale_2_erase')
            # Delete the original Band 2 buffered features
            arcpy.management.DeleteFeatures(scale_level_2_features)
            # # Append Erase results of original Band 2 buffered features with covered parts removed
            arcpy.management.Append(erased, self.layers['buffered'])

        if scale_extent_lookup[str(4)] or scale_extent_lookup[str(5)] or scale_extent_lookup[str(6)]:
            # Repeat same process for each level 2-4
            scale_level_3_features = arcpy.management.SelectLayerByAttribute(self.layers['buffered'], "NEW_SELECTION", 'enc_scale = ' + "3")
            merged_upper_extents = arcpy.management.Merge(scale_extent_lookup[str(4)] + scale_extent_lookup[str(5)] + scale_extent_lookup[str(6)], 
                                                            'memory/scale_3_extents')
            erased = arcpy.analysis.Erase(scale_level_3_features, merged_upper_extents, 'memory/scale_3_erase')
            arcpy.management.DeleteFeatures(scale_level_3_features)
            arcpy.management.Append(erased, self.layers['buffered'])

        if scale_extent_lookup[str(5)] or scale_extent_lookup[str(6)]:
            scale_level_4_features = arcpy.management.SelectLayerByAttribute(self.layers['buffered'], "NEW_SELECTION", 'enc_scale = ' + "4")
            merged_upper_extents = arcpy.management.Merge(scale_extent_lookup[str(5)] + scale_extent_lookup[str(6)], 'memory/scale_4_extents')
            erased = arcpy.analysis.Erase(scale_level_4_features, merged_upper_extents, 'memory/scale_4_erase')
            arcpy.management.DeleteFeatures(scale_level_4_features)
            arcpy.management.Append(erased, self.layers['buffered'])

        if scale_extent_lookup[str(6)]:
            scale_level_5_features = arcpy.management.SelectLayerByAttribute(self.layers['buffered'], "NEW_SELECTION", 'enc_scale = ' + "5")
            merged_upper_extents = arcpy.management.Merge(scale_extent_lookup[str(6)], 'memory/scale_5_extents')
            erased = arcpy.analysis.Erase(scale_level_5_features, merged_upper_extents, 'memory/scale_5_erase')
            arcpy.management.DeleteFeatures(scale_level_5_features)
            arcpy.management.Append(erased, self.layers['buffered'])

        lndare_end = arcpy.management.GetCount(self.layers['buffered'])
        arcpy.AddMessage(f' - Removed {int(lndare_start[0]) - int(lndare_end[0])} features')

    def get_chart_scale(self, current_scale) -> int:
        """NOT USED ANYMORE
        Code uses self.scale_conversion as a constant now
        Get the upper chart scale or max chart scale for the current input chart scale
        :param str current_scale: Current scale value from an ENC chart
        """

        with open(str(INPUTS / 'lookups' / 'chartscale.yaml'), 'r') as lookup:
            chartscale_lookup = yaml.safe_load(lookup)
        scale_numbers = [int(scale) for scale in chartscale_lookup]
        for lower_resolution, higher_resolution in zip(scale_numbers, list(scale_numbers)[1:]):
            if lower_resolution < int(current_scale) <= higher_resolution:
                return chartscale_lookup[higher_resolution]
            elif int(current_scale) > higher_resolution:
                continue
        return chartscale_lookup[max(scale_numbers)]

    def get_high_water_features(self):
        """Read ENC features and build HW dataset"""

        arcpy.AddMessage('Reading COALNE & SLCONS Feature records')   
        enc_files = self.get_approved_enc_files()
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            enc_scale = pathlib.Path(enc_path).stem[2]
            display_scale = self.get_enc_display_scale(enc_file)
            for layer in enc_file:
                layer.ResetReading()
                name = layer.GetDescription()
                if name == 'COALNE':
                    self.store_coalne_features(layer, enc_scale, display_scale)
                elif name == 'SLCONS':
                    self.store_slcons_features(layer, enc_scale, display_scale)
                elif name == 'LNDARE':
                    self.store_lndare_features(layer, enc_scale, display_scale)
        arcpy.AddMessage(f' - Removed {self.intersected} supersession features')

    def merge_feature_layers(self) -> None:
        """Merge together the COALNE and SLCONS features"""

        arcpy.AddMessage('Merging Water Feature Layers')
        self.layers['merged'] = arcpy.management.CreateFeatureclass(
            'memory', 
            f'merged_layer', 
            'POLYLINE', 
            spatial_reference=arcpy.SpatialReference(4326)
        )
        arcpy.management.AddField(self.layers['merged'], 'display_scale', 'LONG')
        arcpy.management.AddField(self.layers['merged'], 'enc_scale', 'SHORT')

        with arcpy.da.InsertCursor(self.layers['merged'], ['SHAPE@', 'display_scale', 'enc_scale']) as cursor: 
            for feature_type in ['COALNE', 'SLCONS']:
                if self.layers[feature_type]:
                    with arcpy.da.SearchCursor(self.layers[feature_type], ['SHAPE@', 'DISPLAY_SCALE', 'ENC_SCALE']) as feature_cursor:
                        for row in feature_cursor:
                            cursor.insertRow(row)

    def print_properties(self, feature: dict) -> None:
        """Helper function to view feature details"""

        for key, val in feature['properties'].items():
            print(key, val)
        print(feature['geometry'])

    def remove_inner_polygons(self) -> None:
        """"Only keep the first geometry for each polygon feature"""

        arcpy.AddMessage('Removing inner polygons')
        with arcpy.da.UpdateCursor(self.layers['dissolved'], ['SHAPE@']) as cursor:
            for row in cursor:
                row_json = json.loads(row[0].JSON)
                if 'rings' in row_json:
                    outer_polygon = row_json['rings'][0]
                    points = [arcpy.Point(x, y) for x, y in outer_polygon]
                    point_array = arcpy.Array(points)
                    cursor.updateRow([arcpy.Polygon(point_array, arcpy.SpatialReference(4326))])

    def save_layers(self) -> None:
        """Write out memory layers to output folder"""

        output_folder = self.param_lookup['output_folder'].valueAsText
        arcpy.AddMessage(f'Saving layer: {str(pathlib.Path(output_folder) / "mhw_polygons.shp")}')
        arcpy.management.CopyFeatures(self.layers['LNDARE'], str(pathlib.Path(output_folder) / 'mhw_polygons.shp'))
        arcpy.AddMessage(f'Saving layer: {str(pathlib.Path(output_folder) / "mhw_lines.shp")}')
        arcpy.management.CopyFeatures(self.layers['merged'], str(pathlib.Path(output_folder) / 'mhw_lines.shp'))
        arcpy.AddMessage(f'Saving layer: {str(pathlib.Path(output_folder) / "buffered_mhw_polygons.shp")}')
        # arcpy.management.CopyFeatures(self.layers['buffered'], str(pathlib.Path(output_folder) / 'buffered_mhw_polygons.shp'))
        arcpy.AddMessage(f'Saving layer: {str(pathlib.Path(output_folder) / "dissolved_mhw_polygons.shp")}')
        arcpy.management.CopyFeatures(self.layers['dissolved'], str(pathlib.Path(output_folder) / "dissolved_mhw_polygons.shp"))
        arcpy.AddMessage(f'Saving layer: {str(pathlib.Path(output_folder) / pathlib.Path(self.param_lookup["sheets"].valueAsText).stem)}_clip.shp')
        arcpy.management.CopyFeatures(self.layers['clipped_sheets'], 
                                      str(pathlib.Path(output_folder) / f'{pathlib.Path(self.param_lookup["sheets"].valueAsText).stem}_clip.shp'))

    def start(self) -> None:
        """Main method to begin process"""

        if not self.param_lookup['enc_files'].valueAsText:
            self.download_enc_files()
        self.set_driver()
        self.return_primitives_env()
        self.get_scale_bounds('MHWBufferEngine')
        self.get_high_water_features()
        self.build_area_features()
        self.build_line_features()
        self.merge_feature_layers()
        self.buffer_features()
        self.erase_covered_features()
        self.dissolve_polygons()
        self.remove_inner_polygons()
        self.clip_sheets()
        self.save_layers()
        self.delete_enc_extents()

        arcpy.AddMessage('Done')

    def store_coalne_features(self, layer: list[dict], enc_scale: str, display_scale: str) -> None:
        """Collect all COALNE features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                if self.feature_covered_by_upper_scale(feature_json, int(enc_scale)):
                    self.intersected += 1
                    continue
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                if geom_type == 'LineString':
                    feature_json['properties']['DISPLAY_SCALE'] = display_scale
                    feature_json['properties']['ENC_SCALE'] = enc_scale
                    self.features['COALNE'].append(feature_json)
    
    def store_lndare_features(self, layer: list[dict], enc_scale: str, display_scale: str) -> None:
        """Collect all LNDARE features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                if geom_type == 'Polygon':
                    feature_json['properties']['DISPLAY_SCALE'] = display_scale
                    feature_json['properties']['ENC_SCALE'] = enc_scale
                    self.features['LNDARE'].append(feature_json)

    def store_slcons_features(self, layer: list[dict], enc_scale: str, display_scale: str) -> None:
        """Collect all SLCONS features"""

        for feature in layer:
            if feature:
                feature_json = json.loads(feature.ExportToJson())
                if self.feature_covered_by_upper_scale(feature_json, int(enc_scale)):
                    self.intersected += 1
                    continue
                geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                if geom_type == 'LineString':
                    feature_json['properties']['DISPLAY_SCALE'] = display_scale
                    feature_json['properties']['ENC_SCALE'] = enc_scale
                    props = feature_json['properties']
                    if 'CATSLC' in props:
                        if props['CATSLC'] == 4:
                            if props['WATLEV'] == 2:
                                self.features['SLCONS'].append(feature_json)
                            elif props['WATLEV'] in ['', None, 'None']:  # Blank only
                                if props['CONDTN'] in ['', None, 'None', 1, 3, 4, 5]:  # skip 2
                                    self.features['SLCONS'].append(feature_json)
                        else: # != 4
                            self.features['SLCONS'].append(feature_json)

