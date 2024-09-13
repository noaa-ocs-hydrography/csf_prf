import os
import arcpy
import pathlib
import json
import yaml
import time

from csf_prf.engines.Engine import Engine
from csf_prf.engines.class_code_lookup import class_codes as CLASS_CODES
arcpy.env.overwriteOutput = True

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class S57ConversionEngine(Engine):
    """Class for converting S57 files to geopackage"""

    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup
        self.gdb_name = pathlib.Path(param_lookup['enc_file'].valueAsText).stem
        self.feature_classes = ['Point_features', 'LineString_features', 'Polygon_features']
        self.output_data = {}
        self.layerfile_name = 'MCD_maritime_layerfile'
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

    def add_projected_columns(self):
        gdb_path = os.path.join(self.param_lookup['output_folder'].valueAsText, f"{self.gdb_name}.gdb")

        for fc_name in self.feature_classes:
            fc = os.path.join(gdb_path, fc_name)
            arcpy.management.AddField(fc, 'transformed', field_type='TEXT', field_length=10, field_is_nullable='NULLABLE')

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
            invalid_field_names = set()
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
            arcpy.AddMessage(f' - fields with invalid values: {invalid_field_names}')

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

            arcpy.AddMessage(' - Building Point features')     
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

            arcpy.AddMessage(' - Building Line features')
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
                self.output_data[f'enc_{assigned_name}'] = output_name

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
        enc_file = self.open_file(enc_path) 
        for layer in enc_file:
            layer.ResetReading()
            for feature in layer:
                if feature:
                    feature_json = json.loads(feature.ExportToJson())
                    geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False
                    if geom_type in ['Point', 'LineString', 'Polygon'] and feature_json['geometry']['coordinates']:
                        feature_json = self.set_none_to_null(feature_json) 
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

        multiple_values = current_value.split(',')
        new_values = []
        for val in multiple_values:
            if val:
                new_values.append(s57_lookup[field_name][int(val)]) # TODO missing s57_lookup values

        multiple_value_result = ','.join(new_values)
        return multiple_value_result  

    def set_gcs_to_wgs84(self) -> None: 
        """Redefine the GCS to NAD83 then reproject from NAD83 to WGS84"""   

        nad83_2011_spatial_ref = arcpy.SpatialReference(6318)
        wgs84_spatial_ref = arcpy.SpatialReference(4326)
        gdb_path = os.path.join(self.param_lookup['output_folder'].valueAsText, f"{self.gdb_name}.gdb")
        output_folder = str(self.param_lookup['output_folder'].valueAsText)

        with open(str(INPUTS / 'lookups' / 's57_lookup.yaml'), 'r') as lookup:
            objl_lookup = yaml.safe_load(lookup)
        tescou_options = [val for key, val in objl_lookup['TECSOU'].items() if key in [1, 2, 3, 7]]

        arcpy.AddMessage("Reprojecting New or Updated objects from NAD 83 (2011) to WGS 84")
        for fc_name in self.feature_classes:
            fc = os.path.join(gdb_path, fc_name)
            geom_type = fc.split('_')[0]
            arcpy.management.DefineProjection(fc, nad83_2011_spatial_ref)

            fields = [field.name for field in arcpy.ListFields(fc)]

            if 'descrp' and 'TECSOU' in fields:
                with arcpy.da.UpdateCursor(fc, ['SHAPE@', 'descrp', 'TECSOU', 'transformed']) as cursor:
                    for row in cursor:
                        geometry = row[0]
                        descrp_value = row[1]
                        tecsou_value = row[2]

                        if descrp_value in ['New', 'Update'] and tecsou_value in tescou_options:
                            # point_original = geometry.firstPoint
                            # print(f"Sample point original: X = {point_original.X}, Y = {point_original.Y}")
                            projected_geometry = geometry.projectAs(wgs84_spatial_ref, 'NAD_1983_(2011)_to_WGS_1984_1')
                            # point = projected_geometry.firstPoint
                            # print(f"Sample point original: X = {point.X}, Y = {point.Y}")
                            # print(f"Sample point: X = {point_original.X == point.X}, Y = {point_original.Y == point.Y}")
                            row[0] = projected_geometry
                            row[3] = 'True'
                            cursor.updateRow(row)
                arcpy.management.DefineProjection(fc, wgs84_spatial_ref)   

            else:
                arcpy.AddMessage(f'  -{fc_name} did not need a transformation.')

        # for geom_type in self.geometries.keys():
        #     assigned_name = f'{geom_type}_features'
        #     self.output_data[geom_type] = os.path.join(output_folder, self.gdb_name + '.gdb', assigned_name)

    def split_multipoint_env(self) -> None:
        """Reset S57 ENV for split multipoint only"""

        os.environ["S57_CSV"] = str(INPUTS / 'lookups')
        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,LIST_AS_STRING=ON,PRESERVE_EMPTY_NUMBERS=ON,ADD_SOUNDG_DEPTH=ON"                                                                     

    def start(self) -> None:
        start = time.time()
        self.create_output_gdb(gdb_name=self.gdb_name)
        self.set_driver()
        self.split_multipoint_env() 
        self.get_feature_records()
        # self.return_primitives_env() 
        # self.get_vector_records()
        self.build_output_layers()
        self.add_objl_string_to_S57() 
        self.add_subtype_column()
        self.convert_noaa_attributes()
        self.export_enc_layers()
        self.add_projected_columns()
        self.set_gcs_to_wgs84()
        if self.param_lookup['layerfile_export'].value:
            self.add_subtypes_to_data()
            self.write_output_layer_file()
        self.write_to_geopackage()  
        arcpy.AddMessage('Done')
        arcpy.AddMessage(f'Run time: {(time.time() - start) / 60}')
