import time
import pathlib
import json
import arcpy
import arcpy.management
import requests
import yaml
import glob
import os
import pyodbc

from csf_prf.engines.Engine import Engine
from csf_prf.engines.class_code_lookup import class_codes as CLASS_CODES
arcpy.env.overwriteOutput = True
arcpy.env.qualifiedFieldNames = False # Force use of field name alias
arcpy.env.transferGDBAttributeProperties = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class ENCReaderException(Exception):
    """Custom exception for tool"""

    pass 


# def get_config_item(parent: str, child: str=False) -> tuple[str, int]:
#     """
#     Load config and return speciific key
#     - Standalone function because class methods can't be pickled
#     """

#     with open(str(INPUTS / 'lookups' / 'config.yaml'), 'r') as lookup:
#         config = yaml.safe_load(lookup)
#         parent_item = config[parent]
#         if child:
#             return parent_item[child]
#         else:
#             return parent_item
            

# def download_gc(download_inputs) -> None:
#     """
#     Download a specific geograhic cell associated with an ENC
#     - Standalone function because class methods can't be pickled
#     :param list[list] download_inputs:  Prepared array of output_folder, enc, path, basefilename 
#     """

#     output_folder, enc, path, basefilename = download_inputs
#     enc_folder = output_folder / 'geographic_cells' / enc
#     enc_folder.mkdir(parents=True, exist_ok=True)
#     dreg_api = get_config_item('GC', 'DREG_API').replace('{Path}', path).replace('{BaseFileName}', basefilename)
#     gc_folder = enc_folder / basefilename.replace('.zip', '')
#     if not os.path.exists(gc_folder):
#         arcpy.AddMessage(f'Downloading GC: {basefilename}')
#         enc_zip = requests.get(dreg_api)
#         output_file = enc_folder / basefilename
#         with open(output_file, 'wb') as file:
#             for chunk in enc_zip.iter_content(chunk_size=128):
#                 file.write(chunk)
#     else:
#         arcpy.AddMessage(f'Already downloaded GC: {basefilename}')

class ENCReaderEngine(Engine):
    """
    Class for handling all reading and processing
    of features from ENC files
    """

    def __init__(self, param_lookup: dict, sheets_layer):
        self.param_lookup = param_lookup
        self.sheets_layer = sheets_layer
        self.gdb_name = 'csf_features'
        self.driver = None
        self.scale_bounds = {}
        self.feature_lookup = None
        self.gc_files = set()
        self.gc_points = None
        self.gc_lines = None
        self.geometries = {
            "Point": {
                "features": [],
                "QUAPOS": [],
                "features_layers": {"assigned": None, "unassigned": None},
                "QUAPOS_layers": {"assigned": None, "unassigned": None},
                "GC_layers": {"assigned": None, "unassigned": None}
            },
            "LineString": {
                "features": [],
                "QUAPOS": [],
                "features_layers": {"assigned": None, "unassigned": None},
                "QUAPOS_layers": {"assigned": None, "unassigned": None},
                "GC_layers": {"assigned": None, "unassigned": None}
            },
            "Polygon": {
                "features": [],
                "QUAPOS": [],
                "features_layers": {"assigned": None, "unassigned": None},
                "QUAPOS_layers": {"assigned": None, "unassigned": None},
                "GC_layers": {"assigned": None, "unassigned": None}
            }
        }
        self.output_data = {}

    def add_asgnmt_column(self) -> None:
        """Populate the 'asgnmt' column for all feature layers"""

        arcpy.AddMessage(" - Adding 'asgnmt' column")
        for feature_type in self.geometries.keys():
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['assigned'], 'asgnmt', 2)
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['unassigned'], 'asgnmt', 1)

    def add_columns(self) -> None:
        """Main caller for adding all columns"""

        self.add_objl_string()
        self.add_asgnmt_column()
        self.add_invreq_column()
        if self.param_lookup['layerfile_export'].value:
            self.add_subtype_column()

    def add_invreq_column(self) -> None:
        """Add and populate the investigation required column for allowed features"""

        # with open(str(INPUTS / 'lookups' / 'invreq_lookup.yaml'), 'r') as lookup:
        #     objl_lookup = yaml.safe_load(lookup)
        # invreq_options = objl_lookup['OPTIONS']

        for feature_type in self.geometries.keys():
            arcpy.AddMessage(f" - Adding 'invreq' column: {feature_type}")
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['assigned'], 'invreq', nullable=True)
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['unassigned'], 'invreq', nullable=True)
            # self.set_assigned_invreq(feature_type, objl_lookup, invreq_options)
            # self.set_unassigned_invreq(feature_type, objl_lookup, invreq_options)

    def add_objl_string(self) -> None:
        """Convert OBJL number to string name"""
        
        # TODO review if unapproved_features.yaml handles this same logic
        arcpy.AddMessage(" - Adding 'OBJL_NAME' column")
        aton_values = self.get_aton_lookup()
        aton_count = 0
        aton_found = set()
        for feature_type in self.geometries.keys():
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['assigned'], 'OBJL_NAME', nullable=True)
            self.add_column_and_constant(self.geometries[feature_type]['features_layers']['unassigned'], 'OBJL_NAME', nullable=True)

            for value in ['assigned', 'unassigned']:
                with arcpy.da.UpdateCursor(self.geometries[feature_type]['features_layers'][value], ['*']) as updateCursor:
                    fields = updateCursor.fields
                    if 'OBJL' in fields:
                        for row in updateCursor:
                            objl = fields.index('OBJL')
                            objl_name = fields.index('OBJL_NAME')
                            row[objl_name] = CLASS_CODES.get(int(row[objl]), CLASS_CODES['OTHER'])[0]
                            if feature_type == 'Point' and row[objl_name] in aton_values:
                                aton_found.add(row[1])
                                aton_count += 1
                                updateCursor.deleteRow()
                            else:
                                updateCursor.updateRow(row)
                    else:
                        # TODO determine why OBJL is missing sometimes
                        print(f'  - {feature_type} missing OBJL in row: {fields}')

        if len(aton_found) > 0:
            arcpy.AddMessage(f'  - Removed {aton_count} ATON features containing {str(aton_found)}')

    def convert_noaa_attributes(self) -> None:
        """Obtain string values for all numerical S57 fields"""

        with open(str(INPUTS / 'lookups' / 's57_lookup.yaml'), 'r') as lookup:
            s57_lookup = yaml.safe_load(lookup)

        for feature_type in self.geometries.keys():
            for value in ['assigned', 'unassigned']:
                arcpy.AddMessage(f'Update field values for: {feature_type} - {value}')
                invalid_field_names = set()
                with arcpy.da.UpdateCursor(self.geometries[feature_type]['features_layers'][value], ['*']) as updateCursor:
                    fields = updateCursor.fields
                    for row in updateCursor:
                        new_row = []
                        for field_name in fields:
                            field_index = fields.index(field_name)
                            current_value = row[field_index]
                            if field_name in s57_lookup:
                                if current_value:
                                    try:
                                        new_value = s57_lookup[field_name][int(current_value)]
                                        new_row.append(new_value)
                                    except ValueError as e: # current_value has multiple values
                                        multiple_value_result = self.get_multiple_values_from_field(field_name, current_value, s57_lookup)
                                        new_row.append(multiple_value_result)
                                        pass
                                    except KeyError as e: # current_value is invalid ie. 2147483641
                                        new_row.append(current_value)
                                        invalid_field_names.add((field_name, current_value))
                                        pass
                                else:
                                    new_row.append(current_value)
                            else:
                                new_row.append(current_value)
                        updateCursor.updateRow(new_row)
                if len(invalid_field_names) > 0:
                    arcpy.AddMessage(f' - fields with invalid values: {invalid_field_names}')

    def download_gc(self, number, download_inputs) -> None:
        """
        Download a specific geograhic cell associated with an ENC
        :param int number: Current GC file count
        :param list[list] download_inputs:  Prepared array of output_folder, enc, path, basefilename 
        """

        output_folder, enc, path, basefilename = download_inputs

        geographic_cells = output_folder / 'geographic_cells'
        enc_folder = geographic_cells / enc
        enc_folder.mkdir(parents=True, exist_ok=True)
        dreg_api = self.get_config_item('GC', 'DREG_API').replace('{Path}', path).replace('{BaseFileName}', basefilename)
        output_file = enc_folder / basefilename

        already_downloaded = [file for file in geographic_cells.rglob(basefilename)]
        if not already_downloaded:
            arcpy.AddMessage(f' - Downloading GC {number+1}: {basefilename}')
            enc_zip = requests.get(dreg_api)
            with open(output_file, 'wb') as file:
                for chunk in enc_zip.iter_content(chunk_size=128):
                    file.write(chunk)
        else:
            arcpy.AddMessage(f' - Already downloaded GC: {basefilename}')

    def download_gcs(self, gc_rows) -> None:
        """
        Download any GCs for current ENC files
        :param list[()] gc_rows: Query results of GCs and which ENC
        """

        enc_paths = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        gc_lookup = {}
        for enc in enc_paths:
            gc_lookup[pathlib.Path(enc).stem] = []
        for gc in gc_rows:
            # ['BaseFileName', 'iecode', 'status', 'Path]
            enc_name = gc[1]
            if enc_name in gc_lookup.keys():
                gc_lookup[enc_name].append(gc)
        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)

        # processors = int(multiprocessing.cpu_count() * .75)
        for enc in gc_lookup.keys():
            if len(gc_lookup[enc]) > 0:
                arcpy.AddMessage(f'ENC {enc} has {len(gc_lookup[enc])} GCs')
            for number, gc in enumerate(gc_lookup[enc]):
                download_inputs = [output_folder, enc, gc[3], gc[0]]
                self.download_gc(number, download_inputs)
            # TODO make DownloadGCS class and make Pool in __main__ section
            # multiprocessing.set_executable(os.path.join(sys.exec_prefix, 'pythonw.exe'))
            # deep_water = multiprocessing.Pool(processes=processors)
            # download_inputs = [[output_folder, enc, gc[3], gc[0]] for gc in gc_lookup[enc]]
            # deep_water.map(download_gc, download_inputs)
            # deep_water.close()
            # deep_water.join()

        self.unzip_enc_files(str(output_folder / 'geographic_cells'), '.shp')

        gc_folder = output_folder / 'geographic_cells'
        for gc_file in gc_folder.rglob('*.zip'):
            arcpy.AddMessage(f' - Remove unzipped: {gc_file.name}')
            gc_file.unlink()

    def export_enc_layers(self) -> None:
        """
        Write out assigned and unassigned layers to output folder
        - SpatialJoin adds file name to attributes if performed on an "memory" layer
        - Copying features out to disk to force use of alias names for attributes to work with layerfile
        - # Could also just create static layers initially instead of "memory" in perform_spatial_filter()
        """

        arcpy.AddMessage(f'Writing output feature classes')
        arcpy.env.qualifiedFieldNames = False
        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        for geom_type in self.geometries.keys():
            for feature_type in ['features', 'GC', 'QUAPOS']:
                assigned_name = f'{geom_type}_{feature_type}_assigned'
                if self.geometries[geom_type][f'{feature_type}_layers']['assigned']:
                    arcpy.AddMessage(f' - {assigned_name}')
                    output_name = os.path.join(output_folder, self.gdb_name + '.geodatabase', assigned_name)
                    arcpy.management.CopyFeatures(self.geometries[geom_type][f'{feature_type}_layers']['assigned'], output_name)
                    self.output_data[f'{assigned_name}'] = output_name

                unassigned_name = f'{geom_type}_{feature_type}_unassigned'
                if self.geometries[geom_type][f'{feature_type}_layers']['unassigned']:
                    arcpy.AddMessage(f' - {unassigned_name}')
                    output_name = os.path.join(output_folder, self.gdb_name + '.geodatabase', unassigned_name)
                    arcpy.management.CopyFeatures(self.geometries[geom_type][f'{feature_type}_layers']['unassigned'], output_name)
                    self.output_data[f'{unassigned_name}'] = output_name
    
    def filter_gc_features(self) -> None:
        """Spatial query GC features within Sheets layer"""

        # TODO Run tool and see if GC_layers are identical to features from ENC files
        # TODO is supersession an issue with GC features?
        if self.gc_points:
            points_assigned = arcpy.management.SelectLayerByLocation(self.gc_points, 'INTERSECT', self.sheets_layer)
            points_assigned_layer = arcpy.management.MakeFeatureLayer(points_assigned)
            points_unassigned = arcpy.management.SelectLayerByLocation(points_assigned_layer, selection_type='SWITCH_SELECTION')
            self.geometries['Point']['GC_layers']['assigned'] = points_assigned
            self.geometries['Point']['GC_layers']['unassigned'] = points_unassigned 
        
        if self.gc_lines:
            lines_assigned = arcpy.management.SelectLayerByLocation(self.gc_lines, 'INTERSECT', self.sheets_layer)
            lines_assigned_layer = arcpy.management.MakeFeatureLayer(lines_assigned)
            lines_unassigned = arcpy.management.SelectLayerByLocation(lines_assigned_layer, selection_type='SWITCH_SELECTION')
            self.geometries['LineString']['GC_layers']['assigned'] = lines_assigned
            self.geometries['LineString']['GC_layers']['unassigned'] = lines_unassigned
        
    def get_cursor(self):
        """
        Connected to MCD SQL Server and obtain an OBDC cursor
        :returns pyodbc.Cursor: MCD database cursor
        """

        key = self.get_config_item('GC', 'MCD_KEY')
        auth = self.get_config_item('GC', 'MCD_AUTH')
        translate_auth = self.get_translated_mcd_auth(key, auth)
        connection = pyodbc.connect('Driver={SQL Server};'
                                    'Server=OCS-VS-SQLT2PRD;'
                                    'Database=mcd;'
                                    'UID=DREGreader;'
                                    f'PWD={translate_auth};')
        return connection.cursor()
    
    def get_feature_records(self) -> None:
        """Read and store all features from ENC file"""

        arcpy.AddMessage(' - Reading Feature records')
        enc_files = self.get_approved_enc_files()
        intersected = 0
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            enc_scale = pathlib.Path(enc_path).stem[2]
            for layer in enc_file:
                layer.ResetReading()
                # features_missing_coords = 0
                for feature in layer:
                    if feature:
                        feature_json = json.loads(feature.ExportToJson())
                        if self.feature_covered_by_upper_scale(feature_json, int(enc_scale)):
                            intersected += 1
                            continue
                        
                        feature_json['properties']['SCALE_LVL'] = enc_scale
                        geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                        if geom_type in ['Point', 'LineString', 'Polygon'] and feature_json['geometry']['coordinates']:
                            if self.unapproved(geom_type, feature_json['properties']):
                                continue

                            feature_json = self.set_none_to_null(feature_json)
                            self.geometries[geom_type]['features'].append({'geojson': feature_json, 'scale': enc_scale})
                        # elif geom_type == 'MultiPoint':
                        #     # MultiPoints are broken up now to single features with an ENV variable
                        #     feature_template = json.loads(feature.ExportToJson())
                        #     feature_template['geometry']['type'] = 'Point'
                        #     for point in feature.geometry():
                        #         feature_template['geometry']['coordinates'] = [point.GetX(), point.GetY()]  # XY
                        #         self.geometries['Point']['features'].append({'geojson': feature_template})     
                        # else:
                        #     if geom_type:
                        #         features_missing_coords += 1
                # if features_missing_coords > 0:
                #     arcpy.AddMessage(f"Found ({features_missing_coords}) features but missing coordinates")
        arcpy.AddMessage(f'  - Removed {intersected} supersession features')

    def get_translated_mcd_auth(self, key, auth):
        """Obtain MCD information"""

        from cryptography.fernet import Fernet
        setup = Fernet(key)
        return setup.decrypt(auth).decode()
    
    def get_unapproved_names(self) -> list[str]:
        """Obtain list of OBJL names to exclude that require subcategories"""

        return ['MORFAC', 'SLCONS', 'UWTROC', 'WRECKS']
    
    def merge_gc_features(self) -> None:
        """Read and store all features from GC shapefiles"""

        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)
        gc_folder = output_folder / 'geographic_cells'

        point_files = []
        line_files = []
        for shapefile in gc_folder.rglob('*.shp'):
            gc_name = pathlib.Path(shapefile).parents[0].stem
            shp_pth = str(shapefile)
            if gc_name in self.gc_files:
                if shp_pth.endswith('p1.shp'):
                    point_files.append(shp_pth)
                elif shp_pth.endswith('l1.shp'):
                    line_files.append(shp_pth)
                else:
                    arcpy.AddMessage(f'Found other GC: {shp_pth}')
                    
        if point_files:
            self.gc_points = arcpy.management.Merge(point_files, 'memory/gc_points')
        if line_files:
            self.gc_lines = arcpy.management.Merge(line_files, 'memory/gc_lines')

    def get_gc_data(self) -> None:
        """Start the process to download any GCs associated with input ENCs"""
        
        arcpy.AddMessage('Checking for Geographic Cells')
        cursor = self.get_cursor()
        sql = self.get_sql('GetRelatedENC')
        # TODO create new method for string replacement if needed, ie: list of ENC #'s for where clause
        return self.run_query(cursor, sql)

    def get_sql(self, file_name: str) -> str:
        """
        Retrieve SQL query in string format
        :returns str: Query string
        """

        sql_files = glob.glob(str(INPUTS / 'sql' / '*'))
        for file in sql_files:
            path = pathlib.Path(file)
            if path.stem == file_name:
                with open(path, 'r') as sql:
                    return sql.read()   
        raise ENCReaderException(f'SQL file not found: {file_name}.sql')

    def get_vector_records(self) -> None:
        """Read and store all vector records with QUAPOS from ENC file"""

        arcpy.AddMessage(' - Reading QUAPOS records')
        enc_files = self.get_approved_enc_files()
        intersected = 0
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            enc_scale = pathlib.Path(enc_path).stem[2]
            for layer in enc_file:
                layer.ResetReading()
                # features_missing_coords = 0
                for feature in layer:
                    if feature:
                        feature_json = json.loads(feature.ExportToJson())
                        if self.feature_covered_by_upper_scale(feature_json, int(enc_scale)):
                            intersected += 1
                            continue

                        feature_json['properties']['SCALE_LVL'] = enc_scale
                        if 'QUAPOS' in feature_json['properties'] and feature_json['properties']['QUAPOS'] is not None:
                            geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False  
                            if geom_type in ['Point', 'LineString', 'Polygon'] and feature_json['geometry']['coordinates']:
                                self.geometries[geom_type]['QUAPOS'].append({'geojson': feature_json, 'scale': enc_scale})
                            # elif geom_type == 'MultiPoint':  # TODO do we need MultiPoint 'QUAPOS' features?
                            #     feature_template = json.loads(feature.ExportToJson())
                            #     feature_template['geometry']['type'] = 'Point'
                            #     for point in feature.geometry():
                            #         feature_template['geometry']['coordinates'] = [point.GetX(), point.GetY()]  # XY
                            #         self.geometries['Point']['QUAPOS'].append({'geojson': feature_template})
                #             else:
                #                 if geom_type:
                #                     features_missing_coords += 1
                # if features_missing_coords > 0:
                    # arcpy.AddMessage(f"Found ({features_missing_coords}) QUAPOS features but missing coordinates")
        arcpy.AddMessage(f'  - Removed {intersected} supersession QUAPOS features')

    def join_quapos_to_features(self) -> None:
        """Spatial join the QUAPOS tables to features tables"""

        arcpy.AddMessage(' - Joining QUAPOS to feature records')
        overlap_types = {
            'Point': 'ARE_IDENTICAL_TO',
            'LineString': 'SHARE_A_LINE_SEGMENT_WITH',
            'Polygon': 'ARE_IDENTICAL_TO'
        }
        for feature_type in self.geometries:
            output_types = ['assigned', 'unassigned']
            for output_type in output_types:
                feature_records = self.output_data[f'{feature_type}_features_{output_type}']
                vector_records = self.output_data[f'{feature_type}_QUAPOS_{output_type}']
                if feature_records is not None and vector_records is not None:
                    quapos_count = int(arcpy.management.GetCount(vector_records)[0])
                    if quapos_count > 0: # Joining an empty vector_records layer caused duplicate fields
                        output_name = vector_records + '_joined'
                        arcpy.analysis.SpatialJoin(
                            feature_records,
                            vector_records,
                            output_name,
                            match_option=overlap_types[feature_type]
                        )
                        arcpy.management.Delete(feature_records)
                        arcpy.management.Rename(output_name, feature_records)
                        self.geometries[feature_type]["features_layers"][output_type] = feature_records

        # Delete left over QUAPOS layers
        arcpy.env.workspace = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name + '.geodatabase')
        quapos_layers = arcpy.ListFeatureClasses('*QUAPOS*')
        for layer in quapos_layers:
            arcpy.management.Delete(layer)
        # Remove QUAPOS from output_data
        self.output_data = {output_name: data_path for output_name, data_path in self.output_data.items() if 'QUAPOS' not in output_name}

    def perform_spatial_filter(self) -> None:
        """Spatial query all of the ENC features against Sheets boundary"""

        for feature_type in ['features', 'QUAPOS']:
            arcpy.AddMessage(f' - Filtering {feature_type} records')

            # POINTS
            point_fields = self.get_all_fields(self.geometries['Point'][feature_type])
            points_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_points_assigned', 'POINT', spatial_reference=arcpy.SpatialReference(4326))
            sorted_point_fields = sorted(point_fields)
            for field in sorted_point_fields:
                arcpy.management.AddField(points_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building Point features')     
            # 1. add geometry to fields
            cursor_fields = ['SHAPE@XY'] + sorted_point_fields
            with arcpy.da.InsertCursor(points_layer, cursor_fields, explicit=True) as point_cursor: 
                for feature in self.geometries['Point'][feature_type]:
                    # Make new list all set to empty string.  Using None would leave some different
                    attribute_values = ['' for i in range(len(cursor_fields))]
                    # Set geometry on first index
                    coords = feature['geojson']['geometry']['coordinates']
                    attribute_values[0] = (coords[0], coords[1])
                    # Set attributes based on index
                    for fieldname, attr in list(feature['geojson']['properties'].items()):
                        field_index = point_cursor.fields.index(fieldname)
                        attribute_values[field_index] = str(attr)
                    # add to cursor
                    point_cursor.insertRow(attribute_values)
            
            # Must create separate layer name for unassigned.  Using same layer name will cause cursor to open the same layer.
            points_unassigned_rename = arcpy.management.CopyFeatures(points_layer, fr'memory\{feature_type}_points_unassigned')

            points_assigned = arcpy.management.SelectLayerByLocation(points_layer, 'INTERSECT', self.sheets_layer)
            points_unassigned = arcpy.management.SelectLayerByLocation(points_unassigned_rename, 'INTERSECT', self.sheets_layer, invert_spatial_relationship='INVERT')
            self.geometries['Point'][f'{feature_type}_layers']['assigned'] = points_assigned
            self.geometries['Point'][f'{feature_type}_layers']['unassigned'] = points_unassigned
            
            # LINES
            line_fields = self.get_all_fields(self.geometries['LineString'][feature_type])
            lines_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_lines_assigned', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
            sorted_line_fields = sorted(line_fields)
            for field in sorted_line_fields:
                arcpy.management.AddField(lines_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building Line features')
            cursor_fields = ['SHAPE@JSON'] + sorted_line_fields
            with arcpy.da.InsertCursor(lines_layer, cursor_fields, explicit=True) as line_cursor: 
                for feature in self.geometries['LineString'][feature_type]:
                    attribute_values = ['' for i in range(len(cursor_fields))]
                    geometry = feature['geojson']['geometry']
                    attribute_values[0] = arcpy.AsShape(geometry).JSON
                    for fieldname, attr in list(feature['geojson']['properties'].items()):
                        field_index = line_cursor.fields.index(fieldname)
                        attribute_values[field_index] = str(attr)
                    line_cursor.insertRow(attribute_values)
            lines_unassigned_rename = arcpy.management.CopyFeatures(lines_layer, fr'memory\{feature_type}_lines_unassigned')

            lines_assigned = arcpy.management.SelectLayerByLocation(lines_layer, 'INTERSECT', self.sheets_layer)
            lines_unassigned = arcpy.management.SelectLayerByLocation(lines_unassigned_rename, 'INTERSECT', self.sheets_layer, invert_spatial_relationship='INVERT')
            self.geometries['LineString'][f'{feature_type}_layers']['assigned'] = lines_assigned
            self.geometries['LineString'][f'{feature_type}_layers']['unassigned'] = lines_unassigned

            # POLYGONS
            polygons_fields = self.get_all_fields(self.geometries['Polygon'][feature_type])
            polygons_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_polygons_assigned', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
            sorted_polygon_fields = sorted(polygons_fields)
            for field in sorted_polygon_fields:
                arcpy.management.AddField(polygons_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building Polygon features')
            cursor_fields = ['SHAPE@'] + sorted_polygon_fields
            with arcpy.da.InsertCursor(polygons_layer, cursor_fields, explicit=True) as polygons_cursor: 
                large_lndare = 0
                for feature in self.geometries['Polygon'][feature_type]:
                    attribute_values = ['' for i in range(len(cursor_fields))]
                    polygons = feature['geojson']['geometry']['coordinates']
                    if polygons:
                        # 1 polygon is single, > 1 is outer and inners
                        point_arrays = arcpy.Array()
                        for polygon in polygons:
                            points = []
                            for point in polygon:
                                points.append(arcpy.Point(*point))
                            points.append(arcpy.Point(*polygon[0]))  # close the polygon
                            point_arrays.add(arcpy.Array(points))
                        attribute_values[0] = arcpy.Polygon(point_arrays, arcpy.SpatialReference(4326))
                        
                        # skip LNDARE > 3775
                        objl_string = CLASS_CODES.get(int(feature['geojson']['properties']['OBJL']))[0]
                        if objl_string == 'LNDARE':
                            polygon_area = attribute_values[0].projectAs(arcpy.SpatialReference(102008)).area
                            if polygon_area > 3775:
                                # arcpy.AddMessage(f'- Skipping LNDARE: {polygon_area}')
                                large_lndare += 1
                                continue

                        for fieldname, attr in list(feature['geojson']['properties'].items()):
                            field_index = polygons_cursor.fields.index(fieldname)
                            attribute_values[field_index] = str(attr)
                        polygons_cursor.insertRow(attribute_values)

                        # TODO this loads all polygons in a multipolygon
                        # FME 2018_CompositeSource_Creator.fmw comes up with 958(130), 22(1066), 108(980)
                        # This code blocked comes up with 960, 22, 126 - 2 extra points and the multipolygons extracted
                        # first polygon is extent boundary
                        # if len(polygons) > 1:
                        #     for polygon in polygons:
                        #         points = [arcpy.Point(coord[0], coord[1]) for coord in polygon]
                        #         coord_array = arcpy.Array(points)
                        #         geometry = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                        #         attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                        #         polygons_cursor.insertRow([geometry] + attribute_values)
                        # else:
                        #     # add single polygon
                        #     points = [arcpy.Point(coord[0], coord[1]) for coord in polygons[0]]
                        #     coord_array = arcpy.Array(points)
                        #     geometry = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                        #     attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                        #     polygons_cursor.insertRow([geometry] + attribute_values)
            arcpy.AddMessage( f' - Removed {large_lndare} LNDARE features with area > 3775m')
            polygons_unassigned_rename = arcpy.management.CopyFeatures(polygons_layer, fr'memory\{feature_type}_polygons_unassigned')

            polygons_assigned = arcpy.management.SelectLayerByLocation(polygons_layer, 'INTERSECT', self.sheets_layer)
            polygons_unassigned = arcpy.management.SelectLayerByLocation(polygons_unassigned_rename, 'INTERSECT', self.sheets_layer, invert_spatial_relationship='INVERT')
            self.geometries['Polygon'][f'{feature_type}_layers']['assigned'] = polygons_assigned
            self.geometries['Polygon'][f'{feature_type}_layers']['unassigned'] = polygons_unassigned

    def print_feature_total(self) -> None:
        """Print total number of assigned/unassigned features from ENC file"""

        points = arcpy.management.GetCount(self.geometries['Point']['features_layers']['assigned'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['features_layers']['assigned'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['features_layers']['assigned'])
        arcpy.AddMessage(f' - Found Points: {points}')
        arcpy.AddMessage(f' - Found Lines: {lines}')
        arcpy.AddMessage(f' - Found Polygons: {polygons}')
        arcpy.AddMessage(f' - Total assigned: {int(points[0]) + int(lines[0]) + int(polygons[0])}')
        points = arcpy.management.GetCount(self.geometries['Point']['features_layers']['unassigned'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['features_layers']['unassigned'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['features_layers']['unassigned'])
        arcpy.AddMessage(f' - Total unassigned: {int(points[0]) + int(lines[0]) + int(polygons[0])}')

    def print_geometries(self) -> None:
        """Print GeoJSON of all features for review"""

        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                arcpy.AddMessage(f"\n - {feature['type']}:{feature['geojson']}")

    def remove_unassigned_buffer(self) -> None:
        """Remove unassigned features that are outside of 1km from Sheets boundary"""
        
        output_folder = self.param_lookup['output_folder'].valueAsText
        unassigned_buffer = arcpy.analysis.Buffer(self.sheets_layer, os.path.join(output_folder, self.gdb_name + '.geodatabase', 'sheets_buffer'), '1 kilometers')

        # Create list from buffer cursor iterator to use it over and over
        # Iterator by default would only work once
        buffer_cursor = [row for row in arcpy.da.UpdateCursor(unassigned_buffer, ["SHAPE@"])]

        for geom_type in self.geometries:
            unassigned_deleted = 0
            arcpy.AddMessage(f'Removing {geom_type} unassigned outside of 1km')
            feature_records = self.geometries[geom_type]['features_layers']['unassigned']
            feature_count = arcpy.management.GetCount(feature_records)
            # arcpy.management.CopyFeatures(feature_records, os.path.join(output_folder, f'{geom_type}_unassigned_copy.shp')) # Output full unassigned dataset
            with arcpy.da.UpdateCursor(feature_records, ["SHAPE@"]) as feature_cursor:
                for row in feature_cursor:
                    inside = False
                    for buffer_row in buffer_cursor:
                        disjointed = row[0].disjoint(buffer_row[0])
                        if not disjointed:
                            inside = True
                            break
                    if not inside:
                        unassigned_deleted += 1
                        feature_cursor.deleteRow()
            arcpy.AddMessage(f' - Deleted {unassigned_deleted} of {feature_count} unassigned {geom_type} features')
        del buffer_cursor

    def run_query(self, cursor, sql):
        """
        Execute a SQL query
        :param pyodbc.Cursor cursor: Current database and table cursor
        :param str sql: Formatted SQL expression to run
        :returns list[()]: All the query results
        """

        cursor.execute(sql)
        return cursor.fetchall()

    def set_assigned_invreq(self, feature_type, objl_lookup, invreq_options) -> None:
        """
        Isolate logic for setting assigned layer 'invreq' column
        :param str feature_type: Point, LineString, or Polygon
        :param dict[str[str|int]] objl_lookup: YAML values from invreq_look.yaml
        :param dict[int|str] invreq_options: YAML invreq string values to fill column
        """

        with arcpy.da.UpdateCursor(self.geometries[feature_type]['features_layers']['assigned'], ["SHAPE@", "*"]) as updateCursor:
            # Have to use * because some columns(CATOBS, etc) may be missing in point, line, or polygon feature layers
            indx = {
                'OBJL_NAME': updateCursor.fields.index('OBJL_NAME'),
                'CATOBS': updateCursor.fields.index('CATOBS') if 'CATOBS' in updateCursor.fields else False,
                'CATMOR': updateCursor.fields.index('CATMOR') if 'CATMOR' in updateCursor.fields else False,
                'CONDTN': updateCursor.fields.index('CONDTN') if 'CONDTN' in updateCursor.fields else False,
                'WATLEV': updateCursor.fields.index('WATLEV') if 'WATLEV' in updateCursor.fields else False,
                'invreq': updateCursor.fields.index('invreq'),
                'SHAPE@': updateCursor.fields.index('SHAPE@')
            }
            for row in updateCursor:
                if row[indx['OBJL_NAME']] == 'LNDARE':
                    if feature_type == 'Polygon':
                        area = row[indx['SHAPE@']].projectAs(arcpy.SpatialReference(102008)).area  # project to NA Albers Equal Area
                        if area < 3775:  # FME polygon size check 
                            invreq = objl_lookup.get(row[indx['OBJL_NAME']], objl_lookup['OTHER'])['invreq']
                            row[indx['invreq']] = invreq_options.get(invreq, '')
                # CATMOR column needed for MORFAC
                elif row[indx['OBJL_NAME']] == 'MORFAC':
                    if indx['CATMOR']:
                        catmor = row[indx["CATMOR"]]
                        if catmor == '1':
                            row[indx['invreq']] = invreq_options.get(10, '')
                        elif catmor in ['2', '3', '4', '5', '6', '7']:
                            row[indx['invreq']] = invreq_options.get(1, '')
                # CATOBS column needed for OBSTRN
                elif row[indx['OBJL_NAME']] == 'OBSTRN':
                    if indx['CATOBS']:
                        catobs = row[indx["CATOBS"]]
                        if catobs == '2':
                            row[indx['invreq']] = invreq_options.get(12, '')
                        elif catobs == '5':
                            row[indx['invreq']] = invreq_options.get(8, '')
                        elif catobs in [None, '1', '3', '4', '6', '7', '8', '9', '10']:
                            row[indx['invreq']] = invreq_options.get(5, '')
                elif row[indx['OBJL_NAME']] == 'SBDARE':
                    row[indx['invreq']] = invreq_options.get(13, '')
                # CONDTN column needed for SLCONS
                elif row[indx['OBJL_NAME']] == 'SLCONS':
                    if indx['CONDTN']:
                        condtn = row[indx["CONDTN"]]
                        if condtn in ['1', '3', '4', '5']:
                            row[indx['invreq']] = invreq_options.get(1, '')
                        elif condtn == '2':
                            row[indx['invreq']] = invreq_options.get(5, '')
                # WATLEV column needed for UWTROC
                elif row[indx['OBJL_NAME']] == 'UWTROC':
                    if indx['WATLEV']:
                        condtn = row[indx["WATLEV"]]
                        if condtn in ['1', '2', '4', '5', '6', '7']:
                            row[indx['invreq']] = invreq_options.get(5, '')
                        elif condtn == '3':
                            row[indx['invreq']] = invreq_options.get(7, '')
                else:
                    # Set to OTHER value if missing
                    invreq = objl_lookup.get(row[indx['OBJL_NAME']], objl_lookup['OTHER'])['invreq']
                    row[indx['invreq']] = invreq_options.get(invreq, '')
                updateCursor.updateRow(row)

    def set_feature_lookup(self):
        with open(str(INPUTS / 'lookups' / 'unapproved_features.yaml'), 'r') as lookup:
            self.feature_lookup = yaml.safe_load(lookup)

    def set_unassigned_invreq(self, feature_type, objl_lookup, invreq_options) -> None:
        """
        Isolate logic for setting unassigned layer 'invreq' column
        :param str feature_type: Point, LineString, or Polygon
        :param dict[str[str|int]] objl_lookup: YAML values from invreq_look.yaml
        :param dict[int|str] invreq_options: YAML invreq string values to fill column
        """

        with arcpy.da.UpdateCursor(self.geometries[feature_type]['features_layers']['unassigned'], ['OBJL_NAME', 'invreq']) as updateCursor:
            for row in updateCursor:
                objl_found = row[0] in objl_lookup.keys()
                if objl_found:
                    if row[0] == 'SBDARE':
                        if feature_type != 'Point':
                            row[1] = invreq_options.get(14)
                    else:
                        row[1] = invreq_options.get(14)
                    updateCursor.updateRow(row)

    def store_gc_names(self, gc_rows) -> None:
        """Create property of all current GC names"""

        enc_paths = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        enc_names = [pathlib.Path(enc).stem for enc in enc_paths]
        for gc in gc_rows:
            # ['BaseFileName', 'iecode', 'status', 'Path]
            # GC_name.zip, ENC name, review status, Year\GC
            gc_name = gc[0].replace('.zip', '')
            enc_name = gc[1]
            if enc_name in enc_names:
                self.gc_files.add(gc_name)
    
    def start(self) -> None:
        if self.param_lookup['download_geographic_cells'].value:
            try:
                rows = self.get_gc_data()
                self.store_gc_names(rows)
                self.download_gcs(rows)
                self.merge_gc_features()
                self.filter_gc_features()
            except pyodbc.OperationalError as e:
                arcpy.AddMessage(f' - Unable to download GC files.  Check VPN connection. \n - Error: {e}')
                pass
        self.set_driver()
        self.split_multipoint_env()
        self.get_scale_bounds('ENCReaderEngine')
        self.set_feature_lookup()
        self.get_feature_records()
        self.return_primitives_env()
        self.get_vector_records()
        self.perform_spatial_filter()
        self.print_feature_total()
        self.add_columns()
        self.convert_noaa_attributes()
        self.remove_unassigned_buffer()
        self.export_enc_layers()
        self.join_quapos_to_features()
        

        # Run times in seconds
        # download_gcs - 75.
        # merge_gc_features - 12.
        # get_feature_records - 115.
        # get_vector_records - 159.
        # perform_spatial_filter - 668. 656 651 176
        # add_columns - 8.
        # join_quapos_to_features - 12.

    def unapproved(self, geom_type: str, properties: dict[str]) -> bool:
        """Check to ignore unapproved feature types"""

        objl_name = CLASS_CODES.get(int(properties['OBJL']), CLASS_CODES['OTHER'])[0]

        if objl_name in self.get_unapproved_names():
            return self.unapproved_subcategory(geom_type, objl_name, properties)

        unapproved_features = self.feature_lookup[geom_type]
        unapproved = False
        if objl_name in unapproved_features:
            unapproved = True
        return unapproved
    
    def unapproved_subcategory(self, geom_type: str, objl_name: str, properties: dict[str]) -> bool:
        """Check to ignore unapproved feature types that require a subcategory"""

        if objl_name == 'MORFAC':
            if properties['CATMOR'] != 1:
                return True
        elif objl_name == 'SLCONS':
            if properties['CONDTN'] != 2 or properties['WATLEV'] != 3:
                return True
        elif objl_name == 'UWTROC':  
            if geom_type != 'Point':
                # only allow point UWTROC
                return True
        elif objl_name == 'WRECKS': 
            # only allow point and area WRECKS
            if geom_type == 'LineString':
                return True
        return False
