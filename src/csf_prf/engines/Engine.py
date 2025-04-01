import json
import yaml
import pathlib
import os
import zipfile
import arcpy

from osgeo import ogr

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
CSF_PRF = pathlib.Path(__file__).parents[1]


class EngineException(Exception):
    """Custom exception for tool"""

    pass 


class Engine:
    def add_column_and_constant(self, layer, column, expression='""', field_alias='', field_type='TEXT', field_length=300, code_block='', nullable=False) -> None:
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

    # def add_subtypes_to_data(self) -> None:
    #     """Add subtype objects to all output featureclasses"""

    #     arcpy.AddMessage('Adding subtype values to output layers')
    #     output_folder = self.param_lookup['output_folder'].valueAsText
    #     output_gdb = os.path.join(output_folder, f'{self.gdb_name}.geodatabase')

    #     with open(str(INPUTS / 'lookups' / 'all_subtypes.yaml'), 'r') as lookup:
    #         subtype_lookup = yaml.safe_load(lookup)

    #     # Make unique code values
    #     unique_subtype_lookup = self.get_unique_subtype_codes(subtype_lookup)
    #     arcpy.env.workspace = output_gdb
    #     feature_classes = arcpy.ListFeatureClasses()

    #     for featureclass in feature_classes: 
    #         for geometry_type in unique_subtype_lookup.keys():
    #             # Skip GC fc's
    #             if geometry_type in featureclass and 'GC' not in featureclass:
    #                 arcpy.AddMessage(f' - {featureclass}')
    #                 field = [field.name for field in arcpy.ListFields(featureclass) if 'FCSubtype' in field.name][0]
    #                 arcpy.management.SetSubtypeField(featureclass, field)
    #                 for data in unique_subtype_lookup[geometry_type].values():
    #                     arcpy.management.AddSubtype(featureclass, data['code'], data['objl_string'])  

    def create_output_gdb(self, gdb_name='csf_features') -> None:
        """
        Build the output geodatabase for data storage
        :param str gdb_name: Name of the geodatabase
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        if arcpy.Exists(os.path.join(output_folder, gdb_name + '.geodatabase')):
            arcpy.AddMessage('Output GDB already exists')
        else:
            arcpy.AddMessage(f'Creating output geodatabase in {output_folder}')
            # Use of Mobile GDB allows Python to delete the sqlite based file without locks
            # Mobile GDB has a 2TB size limit
            arcpy.management.CreateMobileGDB(output_folder, gdb_name)

    def download_enc_files(self) -> None:
        """Factory function to download project ENC files"""

        self.load_toolbox()
        sheet_parameter = self.param_lookup['sheets'].valueAsText
        sheets = sheet_parameter.replace("'", "").split(';')
        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)
        for sheet in sheets:
            arcpy.AddMessage(f'Downloading ENC files for SHP: {sheet}')
            # Function name is a built-in combo of class and toolbox alias
            arcpy.ENCDownloader_csf_prf_tools(sheet, str(output_folder))
        self.set_enc_files_param(output_folder)

    def export_to_geopackage(self, output_path, param_name, feature_class) -> None:
        """
        Export a feature class in GDB to a Geopackage
        :param str output_path: Path to the output Geopackage
        :param str param_name: Current output_data key for feature class
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
        except EngineException as e:
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
        feature_geometry = arcpy.AsShape(json.dumps(feature_json['geometry']))
        inside = False

        supersession_polygon = self.scale_bounds[enc_scale]
        if supersession_polygon and not supersession_polygon.disjoint(feature_geometry):  # not disjoint means intersected
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
            json_fields = feature['geojson']['properties'].keys() if 'geojson' in feature else feature['properties'].keys()
            for field in json_fields:
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
            
    def get_multiple_values_from_field(self, field_name, current_value, s57_lookup):
        """
        Isolating logic for handling multiple values being found in one S57 field

        :param str field_name: Field name from attribute value
        :param str current_value: Current value from field in row
        :param dict[dict[str]] s57_lookup: YAML lookup dictionary for S57 fields
        :returns str: Concatenated string of multiple values
        """

        multiple_values = current_value.split(',')
        # TODO Seems like an issue with assigned/unassigned dictionary value by reference issue.  
        # unassigned was already having intger values converted to strings and causing the bypass here
        # Need to heavily debug if conversion to strings is required. 
        new_values = []
        for val in multiple_values:
            if val and val.isnumeric():
                # TODO sometimes NOAA attrs are strings: pier ( jetty)
                new_values.append(s57_lookup[field_name][int(val)]) # TODO missing s57_lookup values
            else:
                print('--Bypass:', current_value, multiple_values, val)
                arcpy.AddMessage(f' - Bypassing: Multiple Value Error: {val}')

        multiple_value_result = ','.join(new_values)
        return multiple_value_result  

    def get_scale_bounds(self) -> None:
        """Create lookup for ENC extents by scale"""

        scale_polygons = {}
        enc_files = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            enc_scale = int(pathlib.Path(enc_path).stem[2])  # TODO do we need to look up scale and accept any file name?
            metadata_layer = enc_file.GetLayerByName('DSID')
            metadata = metadata_layer.GetFeature(0)
            metadata_json = json.loads(metadata.ExportToJson())
            # resolution = metadata_json['properties']['DSPM_CSCL']
            scale_level = metadata_json['properties']['DSID_INTU']

            # get CATCOV 1 polygon
            m_covr_layer = enc_file.GetLayerByName('M_COVR')
            catcov = None
            for feature in m_covr_layer:
                feature_json = json.loads(feature.ExportToJson())
                if feature_json['properties']['CATCOV'] == 1:
                    catcov = feature_json
                    break

            if catcov is not None:
                points = [arcpy.Point(*coords) for polygon in catcov['geometry']['coordinates'] for coords in polygon]
                esri_extent_polygon = arcpy.Polygon(arcpy.Array(points))
            else: 
                xMin, xMax, yMin, yMax = m_covr_layer.GetExtent()
                extent_array = arcpy.Array()
                extent_array.add(arcpy.Point(xMin, yMin))
                extent_array.add(arcpy.Point(xMin, yMax))
                extent_array.add(arcpy.Point(xMax, yMax))
                extent_array.add(arcpy.Point(xMax, yMin))
                extent_array.add(arcpy.Point(xMin, yMin))
                esri_extent_polygon = arcpy.Polygon(extent_array)

            if scale_level not in scale_polygons:
                scale_polygons[enc_scale] = []
            scale_polygons[enc_scale].append(esri_extent_polygon)

        # Make a single multi-part extent polygon for each scale
        union_polygons = {}
        for scale, polygons in scale_polygons.items():
            polygon = polygons[0]
            if len(polygons) > 1:
                for add_polygon in polygons[1:]:
                    # creates a multipart arpy.Polygon
                    polygon = polygon.union(add_polygon)
            union_polygons[scale] = polygon
        
        # Merge upper level extent polygons
        scales = sorted(union_polygons) 
        # [2, 3, 4, 5]
        for i, scale in enumerate(scales):
            # 0, 2
            if scale + 1 in scales:
                # if 2 covered by 3
                supersession_polygon = union_polygons[scale + 1]
                if scale + 2 in scales: # if there are 2 upper level scales, merge them
                    upper_scales = scales[i + 2:]
                    for upper_scale in upper_scales:
                        supersession_polygon = supersession_polygon.union(union_polygons[upper_scale])
                self.scale_bounds[scale] = supersession_polygon
            else:
                self.scale_bounds[scale] = False

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

    def load_toolbox(self) -> None:
        """Shared method to load the main toolbox"""

        csf_prf_toolbox = str(CSF_PRF / 'CSF_PRF_Toolbox.pyt')
        arcpy.ImportToolbox(csf_prf_toolbox)

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

    def set_enc_files_param(self, output_folder: pathlib.Path) -> None:
        """Set the ENC files parameter after downloading files"""
        
        enc_files = []
        arcpy.AddMessage('ENC files found:')
        for enc in output_folder.glob('*.000'):
            enc_file = str(enc)
            arcpy.AddMessage(f' - {enc_file}')
            enc_files.append(enc_file)
        self.param_lookup['enc_files'].value = ';'.join(enc_files)

    def set_none_to_null(self, feature_json):
        """
        Convert undesirable text to empty string
        :param dict[dict[]] feature_json: JSON object of ENC Vector features
        :returns dict[dict[]]: Updated JSON object
        """

        for key, value in feature_json['properties'].items():
            # retain all onotes strings
            if key == 'onotes': 
                if value in [2147483641.0] or value is None:
                    print(key, value)
                    feature_json['properties'][key] = ''
            elif value in ['None', 2147483641.0] or value is None:
                feature_json['properties'][key] = ''
        return feature_json

    def set_sheets_input_param(self, output_folder: pathlib.Path) -> None:
        """Set the Sheets parameter after clipping Sheets to MHW buffer"""

        input_sheets = pathlib.Path(self.param_lookup['sheets'].valueAsText).stem
        clipped_sheets = list(output_folder.glob(f'{input_sheets}_clip.shp'))[0]
        if clipped_sheets:
            self.param_lookup['sheets'].value = str(clipped_sheets)

    def split_inner_polygons(self, layer):
        """
        NOT USED ANYMORE
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

    def split_multipoint_env(self) -> None:
        """Reset S57 ENV for split multipoint only"""

        os.environ["S57_CSV"] = str(INPUTS / 'lookups')
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
        """Copy the output feature classes to Geopackage.  Override with child class"""

        raise NotImplementedError               
