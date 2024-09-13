import json
import  yaml
import pathlib
import os
import zipfile
import arcpy

from osgeo import ogr

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class CompositeSourceCreatorException(Exception):
    """Custom exception for tool"""

    pass 


class Engine:
    def add_column_and_constant(self, layer, column, expression='', field_alias='', field_type='TEXT', field_length=300, code_block='', nullable=False) -> None:
        """
        Add the asgnment column and optionally set a value

        :param arcpy.FeatureLayerlayer layer: In memory layer used for processing
        :param str column: Attribute column name
        :param str expression: Simple field calculation expression for a constant
        :param str field_type: Data type for the field
        :param int field_length: Length of the field
        :param str code_block: Advanced string of a Python function as code block 
        :param boolean nullable: Check if the field can be left blank
        """

        if nullable:
            arcpy.management.AddField(layer, column, field_type, field_alias=field_alias, field_length=field_length, field_is_nullable='NULLABLE')
        else:
            arcpy.management.AddField(layer, column, field_type, field_alias=field_alias, field_length=field_length)
            arcpy.management.CalculateField(
                layer, column, expression, expression_type="PYTHON3", field_type=field_type, code_block=code_block
            )

    def add_subtype_column(self) -> None:
        """Add and popuplate FCSubtype field"""

        with open(str(INPUTS / 'lookups' / 'all_subtypes.yaml'), 'r') as lookup:
            subtype_lookup = yaml.safe_load(lookup)

        # Make unique code values
        unique_subtype_lookup = self.get_unique_subtype_codes(subtype_lookup)
        for feature_type in self.geometries.keys():   
            subtypes = unique_subtype_lookup[feature_type]
            code_block = f"""def get_stcode(objl_name):
                '''Code block to use OBJL_NAME field with lookup'''
                return {subtypes}[objl_name]['code']"""
            expression = "get_stcode(!OBJL_NAME!)"
            arcpy.AddMessage(f" - Adding 'FCSubtype' column: {feature_type}")
            if self.__class__.__name__ == "S57ConversionEngine":
                self.add_column_and_constant(
                    self.geometries[feature_type]["output"],
                    "FCSubtype",
                    expression,
                    field_alias="FCSubtype",
                    field_type="LONG",
                    code_block=code_block,
                )
            else:
                data = ["assigned", "unassigned"]
                for data_type in data:
                    self.add_column_and_constant(
                        self.geometries[feature_type]["features_layers"][data_type],
                        "FCSubtype",
                        expression,
                        field_alias="FCSubtype",
                        field_type="LONG",
                        code_block=code_block,
                    )

    def add_subtypes_to_data(self) -> None:
        """Add subtype objects to all output featureclasses"""

        arcpy.AddMessage('Adding subtype values to output layers')
        output_folder = self.param_lookup['output_folder'].valueAsText
        output_gdb = os.path.join(output_folder, f'{self.gdb_name}.gdb')

        with open(str(INPUTS / 'lookups' / 'all_subtypes.yaml'), 'r') as lookup:
            subtype_lookup = yaml.safe_load(lookup)

        # Make unique code values
        unique_subtype_lookup = self.get_unique_subtype_codes(subtype_lookup)
        arcpy.env.workspace = output_gdb
        feature_classes = arcpy.ListFeatureClasses()

        for featureclass in feature_classes: 
            for geometry_type in unique_subtype_lookup.keys():
                # Skip GC fc's
                if geometry_type in featureclass and 'GC' not in featureclass:
                    arcpy.AddMessage(f' - {featureclass}')
                    field = [field.name for field in arcpy.ListFields(featureclass) if 'FCSubtype' in field.name][0]
                    arcpy.management.SetSubtypeField(featureclass, field)
                    for data in unique_subtype_lookup[geometry_type].values():
                        arcpy.management.AddSubtype(featureclass, data['code'], data['objl_string'])  

    def create_caris_export(self) -> None:
        """Output datasets to Geopackage by unique OBJL_NAME"""

        csfprf_output_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
        arcpy.management.CreateSQLiteDatabase(csfprf_output_path, spatial_type='GEOPACKAGE')
        for enc_feature_type, feature_class in self.output_data.items():
            if feature_class:
                arcpy.AddMessage(f" - Exporting: {enc_feature_type}")
                if (
                    "enc" in enc_feature_type
                    and "GC" not in enc_feature_type
                    and enc_feature_type != "enc_files"
                ):  # TODO is 'enc_files' even an option anymore?
                    output_path = os.path.join(
                        self.param_lookup["output_folder"].valueAsText, enc_feature_type
                    )
                    arcpy.management.CreateSQLiteDatabase(output_path, spatial_type='GEOPACKAGE')
                    objl_name_check = [field.name for field in arcpy.ListFields(feature_class) if 'OBJL_NAME' in field.name]
                    if objl_name_check:
                        objl_name_field = objl_name_check[0]
                        objl_names = self.get_unique_values(feature_class, objl_name_field)
                        for objl_name in objl_names:
                            query = f'{objl_name_field} = ' + f"'{objl_name}'"
                            rows = arcpy.management.SelectLayerByAttribute(feature_class,'NEW_SELECTION', query)
                            gpkg_data = os.path.join(output_path + ".gpkg", objl_name)
                            try:
                                arcpy.AddMessage(f"   - {objl_name}")
                                arcpy.conversion.ExportFeatures(rows, gpkg_data, use_field_alias_as_name="USE_ALIAS")
                            except CompositeSourceCreatorException as e:
                                arcpy.AddMessage(f'Error writing {objl_name} to {output_path} : \n{e}')
                else:
                    self.export_to_geopackage(csfprf_output_path, enc_feature_type, feature_class)

    def create_output_gdb(self, gdb_name='csf_features') -> None:
        """
        Build the output geodatabase for data storage
        :param str gdb_name: Name of the geodatabase
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        if arcpy.Exists(os.path.join(output_folder, gdb_name + '.gdb')):
            arcpy.AddMessage('Output GDB already exists')
        else:
            arcpy.AddMessage(f'Creating output geodatabase in {output_folder}')
            arcpy.management.CreateFileGDB(output_folder, gdb_name)

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

    def feature_covered_by_upper_scale(self, feature_json, enc_scale):
        """
        Determine if a current Point, LineString, or Polygon intersects an upper scale level ENC extent
        :param dict[str] feature_json: Loaded JSON of current feature
        :param int enc_scale: Current ENC file scale level
        :returns boolean: True or False
        """

        if feature_json['geometry'] is None:
            return False
        feature_geometry = ogr.CreateGeometryFromJson(json.dumps(feature_json['geometry']))
        upper_scale = int(enc_scale) + 1
        inside = False
        if upper_scale in self.scale_bounds:
            for xMin, xMax, yMin, yMax in self.scale_bounds[upper_scale]:
                extent_geom = ogr.Geometry(ogr.wkbLinearRing)
                extent_geom.AddPoint(xMin, yMin)
                extent_geom.AddPoint(xMin, yMax)
                extent_geom.AddPoint(xMax, yMax)
                extent_geom.AddPoint(xMax, yMin)
                extent_geom.AddPoint(xMin, yMin)
                extent_polygon = ogr.Geometry(ogr.wkbPolygon)
                extent_polygon.AddGeometry(extent_geom)
            # TODO will there be polygons extending over edge of ENC?
            # Might need to use Contains
            if feature_geometry.Intersects(extent_polygon): 
                inside = True
        return inside

    def get_all_fields(self, features) -> None:
        """
        Build a unique list of all field names
        :param dict[dict[str]] features: GeoJSON of string values for all features
        :returns set[str]: Unique list of all fields
        """

        fields = set()
        for feature in features:
            for field in feature['geojson']['properties'].keys():
                fields.add(field)
        return fields 

    def get_aton_lookup(self):
        """
        Return ATON values that are not allowed in CSF
        :return list[str]: ATON attributes
        """

        with open(str(INPUTS / 'lookups' / 'aton_lookup.yaml'), 'r') as lookup:
            return yaml.safe_load(lookup)       

    def get_config_item(self, parent: str, child: str=False) -> tuple[str, int]:
        """Load config and return speciific key"""

        with open(str(INPUTS / 'lookups' / 'config.yaml'), 'r') as lookup:
            config = yaml.safe_load(lookup)
            parent_item = config[parent]
            if child:
                return parent_item[child]
            else:
                return parent_item

    def get_unique_subtype_codes(self, subtype_lookup):
        """
        Create unique codes for all subtypes

        :param dict[str] subtype_lookup: all_subtypes.yaml as dictionary
        :returns dict[str]: Updated dictionary with unique codes
        """

        for geom_type in subtype_lookup.keys():
            codes = []
            for subtype in subtype_lookup[geom_type].values():
                code = subtype['code']
                if code in codes:
                    new_code = code + 1000
                    while new_code in codes:
                        new_code += 1
                    subtype['code'] = new_code
                    codes.append(new_code)
                else:
                    codes.append(code)
        return subtype_lookup
    
    def get_unique_values(self, feature_class, attribute) -> list:
        """
        Get a list of unique values from a feature class
        :param str feature_class: Current path to the .GDB feature class being exported
        :param str attribute: Current OBJL_NAME to export
        :return list[str]: List of unique OBJL_NAMES
        """

        with arcpy.da.SearchCursor(feature_class, [[attribute]]) as cursor:
            return sorted({row[0] for row in cursor})    

    def open_file(self, enc_path):
        """
        Open a single input ENC file
        :param str enc_path: Path to an ENC file on disk
        :returns GDAL.File: GDAL File object you can loop through
        """

        enc_file = self.driver.Open(enc_path, 0)
        return enc_file 

    def return_primitives_env(self) -> None:
        """Reset S57 ENV for primitives only"""

        os.environ["OGR_S57_OPTIONS"] = "RETURN_PRIMITIVES=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON"            

    def reverse(self, geom_list):
        """
        Reverse all the inner polygon geometries
        - Esri inner polygons are supposed to be counterclockwise
        - Shapely.is_ccw() could be used to properly test
        :param list[float] geom_list: 
        :return list[arcpy.Geometry]: List of reversed inner polygon geometry
        """

        return list(reversed(geom_list))

    def set_driver(self) -> None:
        """Set the S57 driver for GDAL"""

        self.driver = ogr.GetDriverByName('S57')

    def set_none_to_null(self, feature_json):
        """
        Convert undesirable text to empty string
        :param dict[dict[]] feature_json: JSON object of ENC Vector features
        :returns dict[dict[]]: Updated JSON object
        """

        for key, value in feature_json['properties'].items():
            if value == 'None' or value is None:
                feature_json['properties'][key] = ''
        return feature_json        

    def split_multipoint_env(self) -> None:
        """Reset S57 ENV for split multipoint only"""

        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON,ADD_SOUNDG_DEPTH=ON"    

    def unzip_enc_files(self, output_folder, file_ending) -> None:
        """Unzip all zip fileis in a folder"""

        for zipped_file in pathlib.Path(output_folder).rglob('*.zip'):
            unzipped_file = str(zipped_file).replace('zip', file_ending)
            if not os.path.exists(unzipped_file):
                download_folder = unzipped_file.replace(file_ending, '')
                with zipfile.ZipFile(zipped_file, 'r') as zipped:
                    zipped.extractall(str(download_folder))

    def write_to_geopackage(self) -> None:
        """Copy the output feature classes to Geopackage"""

        arcpy.AddMessage('Writing to geopackage database')
        if self.param_lookup['caris_export'].value:
            self.create_caris_export()
        else:
            if not self.output_db: # TODO double check is self.output_db needs to be used
                output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
                arcpy.AddMessage(f'Creating output GeoPackage in {output_db_path}')
                arcpy.management.CreateSQLiteDatabase(output_db_path, spatial_type='GEOPACKAGE')
                self.output_db = True
            else:
                arcpy.AddMessage(f'Output GeoPackage already exists')
            for param_name, feature_class in self.output_data.items():
                if feature_class:
                    self.export_to_geopackage(output_db_path, param_name, feature_class)                    

    def write_output_layer_file(self) -> None:
        """Update layer file for output gdb"""

        with open(str(INPUTS / f'{self.layerfile_name}.lyrx'), 'r') as reader:
            layer_file = reader.read()
        layer_dict = json.loads(layer_file)
        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)
        output_gdb = output_folder / f'{self.gdb_name}.gdb'
        for layer in layer_dict['layerDefinitions']:
            if 'featureTable' in layer:
                layer['featureTable']['dataConnection']['workspaceConnectionString'] = f"DATABASE={output_gdb}"
        
        with open(str(output_folder / f'{self.layerfile_name}.lyrx'), 'w') as writer:
            writer.writelines(json.dumps(layer_dict, indent=4))                  
