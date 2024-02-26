import os

from .ENCReaderEngine import ENCReaderEngine


class CompositeSourceCreatorException(Exception):
    """Custom exception for tool"""

    pass


class CompositeSourceCreatorEngine:
    """
    Class to hold the logic for transforming the 
    Composite Source Creator process into an ArcGIS Python Tool
    """
    def __init__(self, param_lookup: dict, tool_type: str = 'esri') -> None:
        self.param_lookup = param_lookup
        self.tool_type = tool_type
        self.output_name = 'csf_prf_geopackage'
        self.loaded_arcpy = False
        self.output_db = False
        self.split_features = []
        self.output_data = {key: None for key in list(self.param_lookup.keys())[:-1]} # skip output_folder

    @property
    def is_esri(self) -> bool:
        """Property to check if process is an Esri tool or other type"""

        is_esri = self.tool_type == 'esri'
        if is_esri:
            self.load_arcpy()
            return True
        return False
    
    def add_column_and_constant(self, layer, column, expression=None, field_type='TEXT') -> None:
        """
        Add the asgnment column and 
        :param arcpy.FeatureLayerlayer layer: In memory layer used for processing
        """

        self.arcpy.management.CalculateField(
            layer, column, expression, expression_type="PYTHON3", field_type=field_type
        )

    def add_message(self, message: str) -> None:
        """Wrap the Esri message option for open-source use"""

        if self.is_esri:
            self.arcpy.AddMessage(message)
        else:
            print(message)

    def convert_sheets(self):
        """Process the Sheets input parameter"""

        if self.param_lookup['sheets'].valueAsText:
            self.add_message('converting sheets')
            layer = self.make_sheets_layer()
            expression = "'Survey: ' + str(!registry_n!) + ', Priority: ' + str(!priority!) + ', Name: ' + str(!sub_locali!)"
            self.add_column_and_constant(layer, 'invreq', expression)
            outer_features, inner_features = self.split_inner_polygons(layer)
            self.write_features_to_shapefile('sheets', layer, outer_features + inner_features, 'output_sheets.shp')

    def convert_junctions(self):
        """Process the Junctions input parameter"""

        self.add_message('converting junctions')
        # layer = self.arcpy.management.MakeFeatureLayer(self.param_lookup['junctions'].valueAsText)

    def convert_bottom_samples(self):
        """Process the Bottom Samples input parameter"""

        return

    def convert_maritime_datasets(self):
        """Process the 3 Maritime input parameters"""

        self.add_message('converting maritime boundary files')
        self.convert_maritime_boundary_baselines()
        self.convert_maritime_boundary_points_and_features()

    def convert_maritime_boundary_points_and_features(self):
        layer = self.merge_maritime_baselines_and_features()
        self.add_column_and_constant(layer, 'invreq', "'Verify the existence of the furthest offshore feature that is dry at MLLW. \
                                     See Baseline Priorities.doc and section 8.1.4 Descriptive Report of the HSSD for further \
                                     information. NOAA units, see FPM section 3.5.6 Maritime Boundary Delineation.'")
        self.add_column_and_constant(layer, 'asgnment', 2, 'SHORT')
        self.add_column_and_constant(layer, 'sftype', 4, 'SHORT')
        self.copy_layer_to_shapefile('maritime_boundary_features', layer, 'output_maritime_features.shp')

    def convert_maritime_boundary_baselines(self):
        """Process the maritime boundary baselines input parameter"""

        layer = self.make_maritime_boundary_pts_layer()
        self.add_column_and_constant(layer, 'invreq', "'Current baseline point. See Baseline Priorities.doc for further \
                                     information. NOAA units, see FPM section 3.5.6 Maritime Boundary Delineation.'")
        self.add_column_and_constant(layer, 'asgnment', 3, 'SHORT')
        self.add_column_and_constant(layer, 'sftype', 4, 'SHORT')
        self.copy_layer_to_shapefile('maritime_boundary_baselines', layer, 'output_maritime_baselines.shp')

    def convert_tides(self):
        """Process the Tides input parameter"""

        return

    def convert_enc_files(self):
        """Process the ENC files input parameter"""

        enc_engine = ENCReaderEngine(self.param_lookup)
        enc_engine.start()
        enc_engine.perform_spatial_filter(self.make_sheets_layer())

        # TODO load ENC files
        # make sure they are CCW right hand rule
        
        # if selected
            # merge all selected layers into 1
            # (FME sets CCW right hand rule again.  Probably not needed)
            # Add asgnment field = 2
            # query by attribute for ENC type
                # some results are multiple integers that need to be filtered again
            # set invreq column for specific ENC types
            # filter and write out to speciific S57 type
        # else not selected
            # TODO merge all not selected layers into 1
            # TODO (FME sets CCW right hand rule again.  Probably not needed)
            # Add asgnment field = 1
            # query by attribute
                # if SBDARE, select all different geometry types
            # set invreq column for specific ENC types
            # filter features
                # if SBDARE, select all different geometry types
            # set invreq column for asgnment = 3 
            # filter and write out to speciific S57 type

        return
    
    def copy_layer_to_shapefile(self, output_data_type, layer, shapefile_name):
        """
        Store processed layer as an output shapefile
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param str shapefile_name: Name for output shapefile
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        self.add_message(f'Writing output shapefile: {shapefile_name}')
        self.arcpy.conversion.FeatureClassToFeatureClass(layer, output_folder, shapefile_name)
        self.output_data[output_data_type] = os.path.join(output_folder, shapefile_name)

    def create_output_db(self) -> None:
        """Build the output SQLite Geopackage database"""

        if not self.output_db:
            self.add_message('Creating output GeoPackage')
            self.output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.output_name)
            self.arcpy.management.CreateSQLiteDatabase(self.output_db_path, spatial_type='GEOPACKAGE')
            self.output_db = True
        else:
            self.add_message(f'Output GeoPackage already exists')

    def load_arcpy(self) -> None:
        """Load arcpy only if needed"""

        if not self.loaded_arcpy:
            import arcpy
            arcpy.env.overwriteOutput = True
            self.arcpy = arcpy
            self.loaded_arcpy = True

    def make_maritime_boundary_pts_layer(self):
        """
        Create in memory layer for processing.
        This copies the input maritime boundary points shapefile to not corrupt it.
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        maritime_pts_path = self.param_lookup['maritime_boundary_pts'].valueAsText
        field_info = self.arcpy.FieldInfo()
        input_fields = self.arcpy.ListFields(maritime_pts_path)
        for field in input_fields:
            field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
        maritime_boundary_pts_layer = self.arcpy.management.MakeFeatureLayer(maritime_pts_path, field_info=field_info)
        layer = self.arcpy.management.CopyFeatures(maritime_boundary_pts_layer, r'memory\maritime_pts_layer')
        return layer

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
        field_info = self.arcpy.FieldInfo()
        input_fields = self.arcpy.ListFields(self.param_lookup['sheets'].valueAsText)
        for field in input_fields:
            if field.name in fields.values():
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        sheet_layer = self.arcpy.management.MakeFeatureLayer(self.param_lookup['sheets'].valueAsText, field_info=field_info)
        layer = self.arcpy.management.CopyFeatures(sheet_layer, r'memory\sheets_layer')
        return layer
    
    def merge_maritime_baselines_and_features(self):
        """
        Merge the point maritime boundary datasets and create a layer
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        maritime_baselines = self.param_lookup['maritime_boundary_pts'].valueAsText
        maritime_features = self.param_lookup['maritime_boundary_features'].valueAsText
        layer = self.arcpy.management.Merge([maritime_baselines, maritime_features], r'memory\maritime_features_layer')
        return layer

    def reverse(self, geom_list):
        """
        Reverse all the inner polygon geometries
        - Esri inner polygons are supposed to be counterclockwise
        - Shapely.is_ccw() could be used to properly test
        :return list[arcpy.Geometry]: List of reversed inner polygon geometry
        """

        return list(reversed(geom_list))

    def split_inner_polygons(self, layer):
        """
        Get all inner and outer polygon feature geometries
        :param arcpy.FeatureLayer layer: In memory layer used for processing
        :return (list[dict[]], list[dict[]]): Feature lists with attributes and geometry keys
        """

        inner_features = []
        outer_features = []
        total_nones = 0
        with self.arcpy.da.SearchCursor(layer, ['SHAPE@'] + ["*"]) as searchCursor:
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

        # self.add_message(f'outer: {len(outer_features)}')
        # self.add_message(f'inner: {len(inner_features)}')

        return outer_features, inner_features

    def start(self) -> None:
        """Main method to begin process"""

        self.convert_sheets()
        self.convert_junctions()
        self.convert_bottom_samples()
        self.convert_maritime_datasets()
        self.convert_tides()
        self.convert_enc_files()
        self.create_output_db()
        self.write_to_geopackage()
        self.add_message('Done')

    def write_features_to_shapefile(self, output_data_type, template_layer, features, shapefile_name) -> None:
        """
        Store processed layer as an output shapefile
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param (list[dict[]]) features: Combined outer and inner feature lists
        :param str shapefile_name: Name for output shapefile
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        self.add_message(f'Writing output shapefile: {shapefile_name}')
        output_name = os.path.join(output_folder, shapefile_name)
        self.arcpy.management.CreateFeatureclass(output_folder, shapefile_name, 
                                                geometry_type='POLYGON', 
                                                template=template_layer,
                                                spatial_reference=self.arcpy.SpatialReference(4326))

        # ['SHAPE@', 'snm', 'priority', 'scale', 'sub_locali', 'registry_n', 'invreq']
        fields = []
        for field in self.arcpy.ListFields(template_layer):
            if field.name != 'OBJECTID':
                if field.name == 'Shape':
                    fields.append('SHAPE@')
                else:
                    fields.append(field.name)

        with self.arcpy.da.InsertCursor(output_name, fields) as cursor:
            for feature in features:
                vertices = [(point.X, point.Y) for point in feature['geometry']]
                polygon = list(vertices)
                cursor.insertRow([polygon] + list(feature['attributes'][2:]))
        self.output_data[output_data_type] = output_name

    def write_to_geopackage(self) -> None:
        """Copy the output shapefiles to Geopackage"""

        self.add_message('Writing to geopackage database')
        for output_name, data in self.output_data.items():
            if data:
                self.add_message(f'{output_name}')
                try:
                    self.arcpy.conversion.ExportFeatures(data, os.path.join(self.output_db_path + '.gpkg', output_name))
                except CompositeSourceCreatorException as e:
                    self.add_message(f'Error writing {output_name} to {self.output_db_path} : \n{e}')
