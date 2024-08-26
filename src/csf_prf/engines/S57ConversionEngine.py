import os
import arcpy
import pathlib
import json
import yaml

from csf_prf.engines.Engine import Engine
from csf_prf.engines.class_code_lookup import class_codes as CLASS_CODES
arcpy.env.overwriteOutput = True

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class MultipleValueException(ValueError):
    """Custom error for multiple values found in one S57 field"""

    pass


class InvalidValueException(KeyError):
    """Custom error for invalid values in S57 fields"""
    pass


class S57ConversionEngine(Engine):
    """Class for converting S57 files to geopackage"""

    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup
        self.s57_name = pathlib.Path(param_lookup['enc_file'].valueAsText).stem
        self.gdb_name = f'fff_{self.s57_name}' # TODO add as a parameter 
        self.output_data = {}
        self.geometries = {
            "Point": {
                "features": [],
                "output": None
            },
            "LineString": {
                "features": [],
                "output": None
            },
            "Polygon": {
                "features": [],
                "output": None
            }
        }

    def add_objl_string_to_S57(self) -> None:
        """Convert OBJL number to string name"""
        
        aton_values = self.get_aton_lookup()
        aton_count = 0
        aton_found = set()
        for feature_type in self.geometries.keys():
            self.add_column_and_constant(self.geometries[feature_type]['output'], 'OBJL_NAME', nullable=True)
            with arcpy.da.UpdateCursor(self.geometries[feature_type]['output'], ['OBJL', 'OBJL_NAME']) as updateCursor:
                for row in updateCursor:
                    row[1] = CLASS_CODES.get(int(row[0]), CLASS_CODES['OTHER'])[0]
                    if feature_type == 'Point' and row[1] in aton_values:
                        aton_found.add(row[1])
                        aton_count += 1
                        updateCursor.deleteRow() 
                    else:
                        updateCursor.updateRow(row)

    def convert_noaa_attributes(self) -> None:
        """Obtain string values for all numerical S57 fields"""

        with open(str(INPUTS / 'lookups' / 's57_lookup.yaml'), 'r') as lookup:
            s57_lookup = yaml.safe_load(lookup)

        for feature_type in self.geometries.keys():
            arcpy.AddMessage(f'Update field values for: {feature_type}')
            with arcpy.da.UpdateCursor(self.geometries[feature_type]['output'], ['*']) as updateCursor:
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
                                except MultipleValueException as e:
                                    multiple_value_result = self.get_multiple_values_from_field(field_name, current_value, s57_lookup, new_row)
                                    new_row.append(multiple_value_result)
                                    pass
                                except InvalidValueException as e:
                                    arcpy.AddMessage(f'  -field {field_name} has weird value: {current_value}')
                                    new_row.append(current_value)
                                    pass
                            else:
                                new_row.append(current_value)
                        else:
                            new_row.append(current_value)
                    updateCursor.updateRow(new_row)

    def build_output_layers(self) -> None:
        """Spatial query all of the ENC features against Sheets boundary"""

        for feature_type in ['features']:

            # POINTS
            point_fields = self.get_all_fields(self.geometries['Point'][feature_type])
            points_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_points_layer', 'POINT', spatial_reference=arcpy.SpatialReference(4326))
            sorted_point_fields = sorted(point_fields)
            for field in sorted_point_fields:
                arcpy.management.AddField(points_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building point features')     
            # 1. add geometry to fields
            cursor_fields = ['SHAPE@XY'] + sorted_point_fields
            with arcpy.da.InsertCursor(points_layer, cursor_fields, explicit=True) as point_cursor: 
                for feature in self.geometries['Point'][feature_type]:
                    # Make new list all set to None
                    attribute_values = [None for i in range(len(cursor_fields))]
                    # Set geometry on first index
                    coords = feature['geojson']['geometry']['coordinates']
                    attribute_values[0] = (coords[0], coords[1])
                    # Set attributes based on index
                    for fieldname, attr in list(feature['geojson']['properties'].items()):
                        field_index = point_cursor.fields.index(fieldname)
                        attribute_values[field_index] = str(attr)
                    # add to cursor
                    point_cursor.insertRow(attribute_values)

            self.geometries['Point']['output'] = points_layer
                    
            # LINES
            line_fields = self.get_all_fields(self.geometries['LineString'][feature_type])
            lines_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_lines_layer', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
            sorted_line_fields = sorted(line_fields)
            for field in sorted_line_fields:
                arcpy.management.AddField(lines_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building line features')
            cursor_fields = ['SHAPE@JSON'] + sorted_line_fields
            with arcpy.da.InsertCursor(lines_layer, cursor_fields, explicit=True) as line_cursor: 
                for feature in self.geometries['LineString'][feature_type]:
                    attribute_values = [None for i in range(len(cursor_fields))]
                    geometry = feature['geojson']['geometry']
                    attribute_values[0] = arcpy.AsShape(geometry).JSON
                    for fieldname, attr in list(feature['geojson']['properties'].items()):
                        field_index = line_cursor.fields.index(fieldname)
                        attribute_values[field_index] = str(attr)
                    line_cursor.insertRow(attribute_values)

            self.geometries['LineString']['output'] = lines_layer        

            # POLYGONS
            polygons_fields = self.get_all_fields(self.geometries['Polygon'][feature_type])
            polygons_layer = arcpy.management.CreateFeatureclass(
                'memory', 
                f'{feature_type}_polygons_layer', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
            sorted_polygon_fields = sorted(polygons_fields)
            for field in sorted_polygon_fields:
                arcpy.management.AddField(polygons_layer, field, 'TEXT', field_length=300, field_is_nullable='NULLABLE')

            arcpy.AddMessage(' - Building Polygon features')
            cursor_fields = ['SHAPE@'] + sorted_polygon_fields
            with arcpy.da.InsertCursor(polygons_layer, cursor_fields, explicit=True) as polygons_cursor: 
                for feature in self.geometries['Polygon'][feature_type]:
                    attribute_values = [None for i in range(len(cursor_fields))]
                    polygons = feature['geojson']['geometry']['coordinates']
                    if polygons:
                        points = [arcpy.Point(coord[0], coord[1]) for coord in polygons[0]]
                        coord_array = arcpy.Array(points)
                        attribute_values[0] = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                        for fieldname, attr in list(feature['geojson']['properties'].items()):
                            field_index = polygons_cursor.fields.index(fieldname)
                            attribute_values[field_index] = str(attr)
                        polygons_cursor.insertRow(attribute_values)   

            self.geometries['Polygon']['output'] = polygons_layer        

    def export_enc_layers(self) -> None:
        """ Write output layers to output folder """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        for geom_type in self.geometries.keys():
            if self.geometries[geom_type]['output']:
                assigned_name = f'{geom_type}_features'
                arcpy.AddMessage(f' - Writing output feature class: {assigned_name}')
                output_name = os.path.join(output_folder, self.gdb_name + '.gdb', assigned_name)
                arcpy.management.CopyFeatures(self.geometries[geom_type]['output'], output_name)
                self.output_data[geom_type] = output_name

    def export_to_geopackage(self, output_path, param_name, feature_class) -> None:
        """
        Export a feature class in GDB to a Geopackage
        :param str output_path: Path to the output Geopackage
        :param str param_name: Current OBJL_NAME to export
        :param str feature_class: Current path to the .GDB feature class being exported
        """

        arcpy.AddMessage(f" - Exporting: {param_name}")
        gpkg_data = os.path.join(output_path + ".gpkg", param_name)
        arcpy.conversion.ExportFeatures(
            feature_class,
            gpkg_data,
            use_field_alias_as_name="USE_ALIAS",
        )

    def get_feature_records(self) -> None:
        """Read and store all features from ENC file"""

        arcpy.AddMessage(' - Reading Feature records')
        enc_path = self.param_lookup['enc_file'].valueAsText
        enc_file = self.open_file(enc_path) # TODO move to the base class
        for layer in enc_file:
            layer.ResetReading()
            for feature in layer:
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                    if geom_type in ['Point', 'LineString', 'Polygon'] and feature_json['geometry']['coordinates']:
                        feature_json = self.set_none_to_null(feature_json) # TODO move to the base class
                        self.geometries[geom_type]['features'].append({'geojson': feature_json})  

    def get_vector_records(self) -> None:
        # TODO does MCD need the QUAPOS feature?
        """Read and store all vector records with QUAPOS from ENC file"""

        arcpy.AddMessage(' - Reading QUAPOS records')
        enc_path = self.param_lookup['enc_files'].valueAsText
        enc_file = self.open_file(enc_path)
        for layer in enc_file:
            layer.ResetReading()
            for feature in layer:
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    if 'QUAPOS' in feature_json['properties'] and feature_json['properties']['QUAPOS'] is not None:
                        geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False  
                        if geom_type in ['Point', 'LineString', 'Polygon'] and feature_json['geometry']['coordinates']:
                            self.geometries[geom_type]['QUAPOS'].append({'geojson': feature_json})     
    
    def get_multiple_values_from_field(self, field_name, current_value, s57_lookup):
        """
        Isolating logic for handling multiple values being found in one S57 field

        :param str field_name: Field name from attribute value
        :param str current_value: Current value from field in row
        :param dict[dict[str]] s57_lookup: YAML lookup dictionary for S57 fields
        :returns str: Concatenated string of multiple values
        """

        arcpy.AddMessage(f'  -field {field_name} had multiple values: {current_value}')
        multiple_values = current_value.split(',')
        new_values = []
        for val in multiple_values:
            new_values.append(s57_lookup[field_name][int(val)])

        multiple_value_result = ','.join(new_values)
        return multiple_value_result
        
    def open_file(self, enc_path):
        """
        Open a single input ENC file
        :param str enc_path: Path to an ENC file on disk
        :returns GDAL.File: GDAL File object you can loop through
        """

        enc_file = self.driver.Open(enc_path, 0)
        return enc_file     

    def split_multipoint_env(self) -> None:
        """Reset S57 ENV for split multipoint only"""

        os.environ["S57_CSV"] = str(INPUTS / 'lookups')
        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON,ADD_SOUNDG_DEPTH=ON"                                                                     

    def start(self) -> None:
        self.create_output_gdb(gdb_name=self.gdb_name)   
        self.set_driver()
        self.split_multipoint_env() 
        self.get_feature_records()
        # self.return_primitives_env() 
        # self.get_vector_records()
         
        self.build_output_layers()
        self.add_objl_string_to_S57() 
        self.convert_noaa_attributes()
        self.export_enc_layers()
        self.write_to_geopackage()  

    def write_to_geopackage(self) -> None:
        """Copy the output feature classes to Geopackage"""

        arcpy.AddMessage('Writing to geopackage database')
        output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
        arcpy.AddMessage(f'Creating output GeoPackage in {output_db_path}')
        arcpy.management.CreateSQLiteDatabase(output_db_path, spatial_type='GEOPACKAGE')

        for geom_type, feature_class in self.output_data.items():
            if feature_class:
                self.export_to_geopackage(output_db_path, geom_type, feature_class)


        