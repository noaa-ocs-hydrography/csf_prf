import os
import arcpy
import time

from csf_prf.engines.Engine import Engine
from csf_prf.engines.ENCReaderEngine import ENCReaderEngine
arcpy.env.overwriteOutput = True


class CompositeSourceCreatorException(Exception):
    """Custom exception for tool"""

    pass 


class CompositeSourceCreatorEngine(Engine):
    """
    Class to hold the logic for transforming the 
    Composite Source Creator process into an ArcGIS Python Tool
    """

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.output_name = 'csf_prf_geopackage'
        self.gdb_name = 'csf_features'
        self.output_db = False
        self.split_features = []
        self.sheets_layer = None
        self.output_data = {key: None for key in list(self.param_lookup.keys())[:-1]} # skip output_folder

    def convert_bottom_samples(self) -> None:
        """Process the Bottom Samples input parameter"""

        return

    def convert_junctions(self) -> None:
        """Process the Junctions input parameter"""

        junctions_parameter = self.param_lookup['junctions'].valueAsText
        if junctions_parameter:
            junctions = junctions_parameter.replace("'", "").split(';')
            arcpy.AddMessage('converting junctions')
            layers = [self.make_junctions_layer(junctions_file) for junctions_file in junctions]
            layer = arcpy.management.Merge(layers, r'memory\junctions_layer')
            expression = "'Survey: ' + str(!survey!) + ', Platform: ' + str(!field_unit!) + ', Year: ' + str(!year!) + ', Scale: ' + str(!scale!)"
            self.add_column_and_constant(layer, 'invreq', expression)
            self.add_column_and_constant(layer, 'TRAFIC', 2)
            self.add_column_and_constant(layer, 'ORIENT', 45)
            self.export_to_feature_class('junctions', layer, 'output_junctions')

    def convert_maritime_datasets(self) -> None:
        """Process the 3 Maritime input parameters"""

        # TODO can we process with only certain maritime files?
        points_parameter = self.param_lookup['maritime_boundary_pts'].valueAsText
        features_parameter = self.param_lookup['maritime_boundary_features'].valueAsText
        baselines_parameter = self.param_lookup['maritime_boundary_baselines'].valueAsText
        if points_parameter and features_parameter and baselines_parameter:
            arcpy.AddMessage('converting maritime boundary files')
            self.convert_maritime_boundary_baselines()
            self.convert_maritime_boundary_points_and_features()

    def convert_maritime_boundary_points_and_features(self) -> None:
        """Merge and process maritime files"""

        layer = self.merge_maritime_pts_and_features()
        self.add_column_and_constant(layer, 'invreq', "'Verify the existence of the furthest offshore feature that is dry at MLLW. \
                                     See Baseline Priorities.doc and section 8.1.4 Descriptive Report of the HSSD for further \
                                     information. NOAA units, see FPM section 3.5.6 Maritime Boundary Delineation.'")
        self.add_column_and_constant(layer, 'asgnment', 2, 'SHORT')
        self.add_column_and_constant(layer, 'sftype', 4, 'SHORT')
        self.copy_layer_to_feature_class('maritime_boundary_features', layer, 'output_maritime_features')

    def convert_maritime_boundary_baselines(self) -> None:
        """Process the maritime boundary baselines input parameter"""

        points = self.param_lookup['maritime_boundary_pts'].valueAsText.replace("'", "").split(';')
        layers = [self.make_maritime_boundary_pts_layer(points_file) for points_file in points]
        layer = arcpy.management.Merge(layers, r'memory\maritime_pts_layer')
        self.add_column_and_constant(layer, 'invreq', "'Current baseline point. See Baseline Priorities.doc for further \
                                    information. NOAA units, see FPM section 3.5.6 Maritime Boundary Delineation.'")
        self.add_column_and_constant(layer, 'asgnment', 3, 'SHORT')
        self.add_column_and_constant(layer, 'sftype', 4, 'SHORT')
        self.copy_layer_to_feature_class('maritime_boundary_baselines', layer, 'output_maritime_baselines')

    def convert_sheets(self) -> None:
        """Process the Sheets input parameter"""

        sheet_parameter = self.param_lookup['sheets'].valueAsText
        if sheet_parameter:
            arcpy.AddMessage('converting sheets')
            sheets = sheet_parameter.replace("'", "").split(';')
            layers = [self.make_sheets_layer(sheets_file) for sheets_file in sheets]
            layer = arcpy.management.Merge(layers, r'memory\sheets_layer')
            expression = "'Survey: ' + str(!registry_n!) + ', Priority: ' + str(!priority!) + ', Name: ' + str(!sub_locali!)"
            self.add_column_and_constant(layer, 'invreq', expression)
            outer_features, inner_features = self.split_inner_polygons(layer)
            self.write_features_to_featureclass('sheets', layer, outer_features + inner_features, 'output_sheets')
            self.sheets_layer = layer  # Set sheets layer for later use

    def convert_tides(self) -> None:
        """Process the Tides input parameter"""

        return

    def convert_enc_files(self) -> None:
        """Process the ENC files input parameter"""

        arcpy.AddMessage('converting ENC files')
        # sheets = self.param_lookup['sheets'].valueAsText.replace("'", "").split(';')
        # layers = [self.make_sheets_layer(sheets_file) for sheets_file in sheets]
        # layer = arcpy.management.Merge(layers, r'memory\sheets_layer')
        enc_engine = ENCReaderEngine(self.param_lookup, self.sheets_layer)
        enc_engine.start()
        self.export_enc_layers(enc_engine)

    def copy_layer_to_feature_class(self, output_data_type, layer, feature_class_name) -> None:
        """
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param str feature_class_name: Name for output feature_class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        output_gdb = os.path.join(output_folder, self.gdb_name + '.gdb')
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        arcpy.conversion.FeatureClassToFeatureClass(layer, output_gdb, feature_class_name)
        self.output_data[output_data_type] = os.path.join(output_gdb, feature_class_name)

    def create_caris_export(self) -> None:
        """Output datasets to Geopackage by unique OBJL_NAME"""

        csfprf_output_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.output_name)
        arcpy.management.CreateSQLiteDatabase(csfprf_output_path, spatial_type='GEOPACKAGE')
        for enc_feature_type, feature_class in self.output_data.items():
            if feature_class:
                if 'enc' in enc_feature_type and enc_feature_type != 'enc_files':
                    output_path = os.path.join(self.param_lookup['output_folder'].valueAsText, enc_feature_type)
                    arcpy.management.CreateSQLiteDatabase(output_path, spatial_type='GEOPACKAGE')
                    objl_name_field = [field.name for field in arcpy.ListFields(feature_class) if 'OBJL_NAME' in field.name][0]
                    objl_names = self.get_unique_values(feature_class, objl_name_field)
                    for objl_name in objl_names:
                        query = f'{objl_name_field} = ' + f"'{objl_name}'"
                        rows = arcpy.management.SelectLayerByAttribute(feature_class,'NEW_SELECTION', query)
                        gpkg_data = os.path.join(output_path + ".gpkg", objl_name)
                        try:
                            arcpy.AddMessage(f" - Exporting: {enc_feature_type}")
                            arcpy.conversion.ExportFeatures(rows, gpkg_data, use_field_alias_as_name="USE_ALIAS")
                        except CompositeSourceCreatorException as e:
                            arcpy.AddMessage(f'Error writing {objl_name} to {output_path} : \n{e}')
                else:
                    self.export_to_geopackage(csfprf_output_path, enc_feature_type, feature_class)

    def create_output_gdb(self) -> None:
        """Build the output geodatabase for data storage"""

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        if arcpy.Exists(os.path.join(output_folder, self.gdb_name + '.gdb')):
            arcpy.AddMessage('Output GDB already exists')
        else:
            arcpy.AddMessage(f'Creating output geodatabase in {output_folder}')
            arcpy.management.CreateFileGDB(output_folder, self.gdb_name)

    def export_enc_layers(self, enc_engine) -> None:
        """
        Write out assigned and unassigned layers to output folder
        :param ENCReaderEngine enc_engine: ENCReaderEngine object
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        for geom_type in enc_engine.geometries.keys():
            # for feature_type in ['features', 'QUAPOS']:  # QUAPOS is joined later and not needing output
            feature_type = 'features'
            assigned_name = f'{geom_type}_{feature_type}_assigned'
            arcpy.AddMessage(f' - Writing output feature class: {assigned_name}')
            output_name = os.path.join(output_folder, self.gdb_name + '.gdb', assigned_name)
            arcpy.management.CopyFeatures(enc_engine.geometries[geom_type][f'{feature_type}_layers']['assigned'], output_name)
            self.output_data[f'enc_{assigned_name}'] = output_name

            unassigned_name = f'{geom_type}_{feature_type}_unassigned'
            arcpy.AddMessage(f' - Writing output feature class: {unassigned_name}')
            output_name = os.path.join(output_folder, self.gdb_name + '.gdb', unassigned_name)
            arcpy.management.CopyFeatures(enc_engine.geometries[geom_type][f'{feature_type}_layers']['unassigned'], output_name)
            self.output_data[f'enc_{unassigned_name}'] = output_name

    def export_to_feature_class(self, output_data_type, template_layer, feature_class_name) -> None:
        """
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param str feature_class_name: Name for output feature class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        output_name = os.path.join(os.path.join(output_folder, self.gdb_name + '.gdb'), feature_class_name)
        copied_layer = arcpy.management.CopyFeatures(template_layer, output_name)
        arcpy.management.DefineProjection(copied_layer, arcpy.SpatialReference(4326))

        self.output_data[output_data_type] = output_name

    def export_to_geopackage(self, output_path, param_name, feature_class) -> None:
        """
        Export a feature class in GDB to a Geopackage
        :param str output_path: Path to the output Geopackage
        :param str param_name: Current OBJL_NAME to export
        :param str feature_class: Current path to the .GDB feature class being exported
        """

        arcpy.AddMessage(f" - Exporting: {param_name}")
        gpkg_data = os.path.join(output_path + ".gpkg", param_name)
        try:
            arcpy.conversion.ExportFeatures(
                feature_class,
                gpkg_data,
                use_field_alias_as_name="USE_ALIAS",
            )
        except CompositeSourceCreatorException as e:
            arcpy.AddMessage(f'Error writing {param_name} to {output_path} : \n{e}')

    def get_unique_values(self, feature_class, attribute) -> list:
        """
        Get a list of unique values from a feature class
        :param str feature_class: Current path to the .GDB feature class being exported
        :param str attribute: Current OBJL_NAME to export
        :return list[str]: List of unique OBJL_NAMES
        """

        with arcpy.da.SearchCursor(feature_class, [[attribute]]) as cursor:
            return sorted({row[0] for row in cursor})

    def make_junctions_layer(self, junctions):
        """
        Create in memory layer for processing.
        This copies the input Junctions shapefile to not corrupt it.
        :param str junctions: Path to the input Junctions shapefile
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        field_info = arcpy.FieldInfo()
        input_fields = arcpy.ListFields(junctions)
        for field in input_fields:
            field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
        layer = arcpy.management.MakeFeatureLayer(junctions, field_info=field_info)
        return layer
    
    def make_maritime_boundary_pts_layer(self):
        """
        Create in memory layer for processing.
        This copies the input maritime boundary points shapefile to not corrupt it.
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        maritime_pts_path = self.param_lookup['maritime_boundary_pts'].valueAsText
        field_info = arcpy.FieldInfo()
        input_fields = arcpy.ListFields(maritime_pts_path)
        for field in input_fields:
            field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
        layer = arcpy.management.MakeFeatureLayer(maritime_pts_path, field_info=field_info)
        return layer

    def make_sheets_layer(self, sheets):
        """
        Create in memory layer for processing.
        This copies the input Sheets shapefile to not corrupt it.
        :param str sheets: Path to the input Sheets shapefile
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
        input_fields = arcpy.ListFields(sheets)
        for field in input_fields:
            if field.name in fields.values():
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        layer = arcpy.management.MakeFeatureLayer(sheets, field_info=field_info)
        return layer

    def merge_maritime_pts_and_features(self):
        """
        Merge the point maritime boundary datasets and create a layer
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        maritime_pts = self.param_lookup['maritime_boundary_pts'].valueAsText.replace("'", "").split(';')
        maritime_features = self.param_lookup['maritime_boundary_features'].valueAsText.replace("'", "").split(';')

        layer = arcpy.management.Merge(maritime_pts + maritime_features, r'memory\maritime_features_layer')
        return layer
    
    def split_inner_polygons(self, layer):
        """
        Get all inner and outer polygon feature geometries
        :param arcpy.FeatureLayer layer: In memory layer used for processing
        :return (list[dict[]], list[dict[]]): Feature lists with attributes and geometry keys
        """

        inner_features = []
        outer_features = []
        total_nones = 0
        with arcpy.da.SearchCursor(layer, ['SHAPE@'] + ["*"]) as searchCursor:
            for row in searchCursor:
                geom_num = 0
                row_geom = row[0]
                attributes = row[1:]
                for geometry in row_geom:
                    if None in geometry:
                        # find indexes of all Nones
                        none_indexes = [i for i, point in enumerate(geometry) if point is None]
                        total_nones += len(none_indexes)
                        if len(none_indexes) == 1: # only 1 inner polygon
                            outer_features.append({'attributes': attributes, 
                                                'geometry': geometry[0:none_indexes[0]]}) # First polygon is outer
                            inner_features.append({'attributes': attributes, 
                                                'geometry': self.reverse(geometry[none_indexes[0]+1:len(geometry)])}) # capture last inner
                        else: # > 1 inner polygon
                            # split array on none indexes
                            for i, (current, next) in enumerate(zip(none_indexes[:-1], none_indexes[1:])):
                                if i == 0: # first one
                                    outer_features.append({'attributes': attributes, 
                                                        'geometry': geometry[0:current]}) # First polygon is outer
                                    inner_features.append({'attributes': attributes, 
                                                        'geometry': self.reverse(geometry[current+1:next])}) # capture first inner
                                elif i == len(none_indexes) - 2: # last one
                                    inner_features.append({'attributes': attributes, 
                                                        'geometry': self.reverse(geometry[current+1:next])}) # capture current inner
                                    inner_features.append({'attributes': attributes, 
                                                        'geometry': self.reverse(geometry[next+1:len(geometry)])}) # capture last inner
                                else: # in between
                                    inner_features.append({'attributes': attributes, 
                                                        'geometry': self.reverse(geometry[current+1:next])}) # capture current inner
                    else:
                        outer_features.append({'attributes': attributes, 'geometry': geometry})

                    geom_num += 1

        return outer_features, inner_features

    def start(self) -> None:
        """Main method to begin process"""

        start = time.time()
        self.create_output_gdb()
        self.convert_sheets()
        self.convert_junctions()
        self.convert_bottom_samples()
        self.convert_maritime_datasets()
        # self.convert_tides()
        self.convert_enc_files()
        self.write_to_geopackage()
        arcpy.AddMessage('Done')
        arcpy.AddMessage(f'Run time: {(time.time() - start) / 60}')

    def write_features_to_featureclass(self, output_data_type, template_layer, features, feature_class_name) -> None:
        """
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param (list[dict[]]) features: Combined outer and inner feature lists
        :param str feature_class_name: Name for output feature_class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        output_name = os.path.join(output_folder, self.gdb_name + '.gdb', feature_class_name)
        arcpy.management.CreateFeatureclass(os.path.join(output_folder, self.gdb_name + '.gdb'), feature_class_name, 
                                                geometry_type='POLYGON', 
                                                template=template_layer,
                                                spatial_reference=arcpy.SpatialReference(4326))

        fields = []
        for field in arcpy.ListFields(template_layer):
            if field.name != 'OBJECTID':
                if field.name == 'Shape':
                    fields.append('SHAPE@')
                else:
                    fields.append(field.name)

        with arcpy.da.InsertCursor(output_name, fields) as cursor:
            # TODO update for points, lines, and polygons
            for feature in features:
                vertices = [(point.X, point.Y) for point in feature['geometry']]
                polygon = list(vertices)
                cursor.insertRow([polygon] + list(feature['attributes'][2:]))
        self.output_data[output_data_type] = output_name

    def write_to_geopackage(self) -> None:
        """Copy the output feature classes to Geopackage"""

        arcpy.AddMessage('Writing to geopackage database')
        if self.param_lookup['caris_export'].value:
            self.create_caris_export()
        else:
            if not self.output_db:
                output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.output_name)
                arcpy.AddMessage(f'Creating output GeoPackage in {output_db_path}')
                arcpy.management.CreateSQLiteDatabase(output_db_path, spatial_type='GEOPACKAGE')
                self.output_db = True
            else:
                arcpy.AddMessage(f'Output GeoPackage already exists')
            for param_name, feature_class in self.output_data.items():
                if feature_class:
                    self.export_to_geopackage(output_db_path, param_name, feature_class)
        
