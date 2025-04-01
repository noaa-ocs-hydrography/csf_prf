import os
import arcpy
import pathlib
import json
import yaml
import time
import copy

from osgeo import osr, ogr
from csf_prf.engines.Engine import Engine
from csf_prf.engines.class_code_lookup import class_codes as CLASS_CODES
arcpy.env.overwriteOutput = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class S57ConversionEngineException(Exception):
    """Custom exception for tool"""

    pass 


class S57ConversionEngine(Engine):
    """Class for converting S57 files to geopackage"""

    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup
        self.gdb_name = pathlib.Path(param_lookup['enc_file'].valueAsText).stem
        self.output_data = {}
        self.letter_lookup = {'Point': 'P', 'LineString': 'L', 'Polygon': 'A'}
        self.layerfile_name = 'MCD_maritime_layerfile'
        self.geometries = {
            "Point": {
                "features": [],
                "output": None,
                'objl_names': None
            },
            "LineString": {
                "features": [],
                "output": None,
                'objl_names': None
            },
            "Polygon": {
                "features": [],
                "output": None,
                'objl_names': None
            }
        }

    def get_geom_letter(self, value: str) -> str:
        """Get geometry letter designation"""

        return self.letter_lookup[value]

    def get_geom_type(self, value: str) -> str:
        """Get geometry type from letter designation"""

        lookup = dict((value, key) for key, value in self.letter_lookup.items())
        return lookup[value]

    def add_projected_columns(self) -> None:
        """Add field for CSR verification"""

        gdb_path = os.path.join(self.param_lookup['output_folder'].valueAsText, f"{self.gdb_name}.geodatabase")
        for geom_type in self.geometries.keys():
            fc_name = f'{geom_type}_features'
            fc = os.path.join(gdb_path, fc_name)
            arcpy.management.AddField(fc, 'transformed', field_type='TEXT', field_length=50, field_is_nullable='NULLABLE')

    def add_objl_string_to_S57(self) -> None:
        """Convert OBJL number to string name"""

        aton_values = self.get_aton_lookup()
        aton_count = 0
        aton_found = set()
        for feature_type in self.geometries.keys():
            arcpy.AddMessage(f" - Adding 'OBJL_NAME' column: {feature_type}")
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

    def build_output_layers(self) -> None:
        """Spatial query all of the ENC features against Sheets boundary"""

        for feature_type in ['features']:

            # POINTS
            if 'Point' in self.geometries:
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

                self.geometries['Point']['output'] = points_layer

            # LINES
            if 'LineString' in self.geometries:
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
                        attribute_values = ['' for i in range(len(cursor_fields))]
                        geometry = feature['geojson']['geometry']
                        attribute_values[0] = arcpy.AsShape(geometry).JSON
                        for fieldname, attr in list(feature['geojson']['properties'].items()):
                            field_index = line_cursor.fields.index(fieldname)
                            attribute_values[field_index] = str(attr)
                        line_cursor.insertRow(attribute_values)

                self.geometries['LineString']['output'] = lines_layer        

            # POLYGONS
            if 'Polygon' in self.geometries:
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

                            for fieldname, attr in list(feature['geojson']['properties'].items()):
                                field_index = polygons_cursor.fields.index(fieldname)
                                attribute_values[field_index] = str(attr)
                            polygons_cursor.insertRow(attribute_values)   

                self.geometries['Polygon']['output'] = polygons_layer    

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

    def create_gpkg_export(self, output_gpkg_path: str) -> None:
        """Output datasets to a single Geopackage by unique OBJL_NAME"""

        for feature_type, feature_class in self.output_data.items():
            if feature_class:
                geom_type = feature_type.split('_')[0]
                if geom_type in ['Point', 'LineString', 'Polygon']:
                    feature_type_letter = self.get_geom_letter(geom_type)
                    objl_name_check = [field.name for field in arcpy.ListFields(feature_class) if 'OBJL_NAME' in field.name]
                    if objl_name_check:
                        objl_name_field = objl_name_check[0]
                        objl_names = self.get_unique_values(feature_class, objl_name_field)
                        self.store_objl_names(geom_type, objl_names)
                        for objl_name in objl_names:
                            query = f'{objl_name_field} = ' + f"'{objl_name}'"
                            rows = arcpy.management.SelectLayerByAttribute(feature_class,'NEW_SELECTION', query)
                            gpkg_data = os.path.join(output_gpkg_path + ".gpkg", f'{objl_name}_{feature_type_letter}')
                            try:
                                arcpy.AddMessage(f"   - {objl_name}")
                                arcpy.conversion.ExportFeatures(rows, gpkg_data, use_field_alias_as_name="USE_ALIAS")
                            except S57ConversionEngineException as e:
                                arcpy.AddMessage(f'Error writing {objl_name} to {output_gpkg_path} : \n{e}')

    def delete_geodatabase(self) -> None:
        """Remove the GDB after GPKG and layefile are built"""
        
        arcpy.AddMessage('Deleting Geodatabase')
        output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name + '.geodatabase')
        arcpy.management.Delete(output_db_path)

    def export_enc_layers(self) -> None:
        """ Write output layers to output folder """

        arcpy.AddMessage('Exporting ENC layers to geodatabase')
        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        for geom_type in self.geometries.keys():
            if self.geometries[geom_type]['output']:
                assigned_name = f'{geom_type}_features'
                arcpy.AddMessage(f' - Writing output feature class: {assigned_name}')
                output_name = os.path.join(output_folder, self.gdb_name + '.geodatabase', assigned_name)
                arcpy.management.CopyFeatures(self.geometries[geom_type]['output'], output_name)
                self.output_data[f'{assigned_name}'] = output_name

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

        for geom_type in ['Point', 'LineString', 'Polygon']:
            if len(self.geometries[geom_type]['features']) == 0:
                arcpy.AddMessage(f"   - No features found for {geom_type}")
                del self.geometries[geom_type]

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

    def project_rows_to_wgs84(self) -> None: 
        """Redefine the GCS to NAD83 then reproject from NAD83 to WGS84"""   

        nad83_2011_spatial_ref = arcpy.SpatialReference(6318)
        wgs84_spatial_ref = arcpy.SpatialReference(4326)

        nad83_gdal = osr.SpatialReference()
        nad83_gdal.ImportFromEPSG(6318)
        wgs84_gdal = osr.SpatialReference()
        wgs84_gdal.ImportFromEPSG(4326)

        coordinate_options = osr.CoordinateTransformationOptions()
        coordinate_options.SetOperation("NAD_1983_To_WGS_1984_5")
        gdal_transformation = osr.CoordinateTransformation(nad83_gdal, wgs84_gdal, coordinate_options)

        gdb_path = os.path.join(self.param_lookup['output_folder'].valueAsText, f"{self.gdb_name}.geodatabase")

        arcpy.AddMessage("Reprojecting New or Updated objects from NAD 83 (2011) to WGS 84 (ITRF08)")
        for geom_type in self.geometries.keys():
            fc_name = f'{geom_type}_features'
            updated_rows = 0
            # Change CRS to NAD83.  It is mislabled as WGS84.
            fc = os.path.join(gdb_path, fc_name)
            arcpy.management.DefineProjection(fc, nad83_2011_spatial_ref)

            fields = [field.name for field in arcpy.ListFields(fc)]
            if 'descrp' in fields:
                with arcpy.da.UpdateCursor(fc, ['SHAPE@', 'descrp', 'transformed']) as cursor:
                    for row in cursor:
                        geometry = row[0]
                        descrp_value = row[1]

                        # Only specific rows need to be projected to WGS84
                        if descrp_value in ['1']:  # '1' == 'New'
                            output_geometry = ogr.CreateGeometryFromWkb(geometry.WKB)
                            output_geometry.Transform(gdal_transformation)
                            projected_geometry = arcpy.FromWKB(output_geometry.ExportToWkb())
                            row[0] = projected_geometry
                            row[2] = 'NAD_1983_To_WGS_1984_5'
                            cursor.updateRow(row)
                            updated_rows += 1
                arcpy.management.DefineProjection(fc, wgs84_spatial_ref)   
                arcpy.AddMessage(f'  - {fc_name}: {updated_rows} features projected to WGS84 locations')
            else:
                arcpy.AddMessage(f'  -{fc_name} did not need a transformation.')                                                                     

    def start(self) -> None:
        start = time.time()
        self.create_output_gdb(gdb_name=self.gdb_name)
        self.set_driver()
        self.split_multipoint_env() 
        self.get_feature_records()
        self.build_output_layers()
        self.add_objl_string_to_S57() 
        if self.param_lookup['layerfile_export'].value:
            self.add_subtype_column()
        # self.convert_noaa_attributes()  # Nathan Leveling requested to keep integer attribute values
        self.export_enc_layers()
        self.add_projected_columns()
        if self.param_lookup['toggle_crs'].value:
            self.project_rows_to_wgs84()
        self.write_to_geopackage()
        if self.param_lookup['layerfile_export'].value:
            self.write_output_layer_file()
        self.delete_geodatabase()
        arcpy.AddMessage('\nDone')
        arcpy.AddMessage(f'Run time: {(time.time() - start) / 60}')

    def store_objl_names(self, geom_type, objl_names) -> None:
        """Storeore the objl names for use in layerfile"""

        self.geometries[geom_type]['objl_names'] = objl_names

    def write_to_geopackage(self) -> None:
        """Copy the output feature classes to Geopackage"""

        arcpy.AddMessage('Writing to geopackage database')
        output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
        arcpy.AddMessage(f'Creating output GeoPackage in {output_db_path}.gpkg')
        arcpy.management.CreateSQLiteDatabase(output_db_path, spatial_type='GEOPACKAGE')
        self.create_gpkg_export(output_db_path)

    def write_output_layer_file(self) -> None:
        """Update layer file for output gdb"""

        arcpy.AddMessage('Writing output layerfile')
        with open(str(INPUTS / f'{self.layerfile_name}.lyrx'), 'r') as reader:
            layer_file = reader.read()
        layer_dict = json.loads(layer_file)
        output_gpkg = f'{self.gdb_name}.gpkg'
        output_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText)
        dbmsType_lookup = {
            'Integer': 2,
            'String': 5,
            'Geometry': 8,
            'OID': 11,
            'Double': 3
        }
        geom_fields = ['Shape_Length', 'Shape_Area']

        # Remove unused OBJL layers
        final_layers = copy.deepcopy(layer_dict['layerDefinitions'])
        drop_list = []
        for i, layer in enumerate(layer_dict['layerDefinitions']):
            if layer['name'] != 'Maritime':
                layer_name, geom_letter = layer['name'][:-2], layer['name'][-1]
                if (self.get_geom_type(geom_letter) in self.geometries) and (layer_name not in self.geometries[self.get_geom_type(geom_letter)]['objl_names']):
                    drop_list.append(i)

        for index in sorted(drop_list, reverse=True):
            final_layers.pop(index)

        # Remove unused Maritime layer pointers
        for i, layer in enumerate(layer_dict['layerDefinitions']):
            if layer['name'] == 'Maritime':
                maritime_layers = copy.deepcopy(layer['layers'])
                for index in sorted(drop_list, reverse=True):
                    maritime_layers.pop(index)

        # Reset layers in layerfile
        layer_dict['layerDefinitions'] = final_layers
        drop_list = []
        for i, layer in enumerate(layer_dict['layerDefinitions']):
            if layer['name'] != 'Maritime':
                layer_name = layer['name'][:-2]
                geom_letter = layer['name'][-1]
                if self.get_geom_type(geom_letter) in self.geometries:
                    if 'featureTable' in layer:
                        layer['featureTable']['dataConnection']['workspaceConnectionString'] = f'AUTHENTICATION_MODE=OSA;DATABASE={output_gpkg}'
                        fields = arcpy.ListFields(os.path.join(output_folder, self.gdb_name + '.gpkg', layer['name']))
                        field_names = [field.name for field in fields if field.name not in geom_fields]
                        field_jsons = [{
                                        "name": field.name,
                                        "type": f"{'esriFieldTypeBigInteger' if field.type == 'OID' else 'esriFieldType' + field.type}",
                                        "isNullable": field.isNullable,
                                        "length": field.length,
                                        "precision": field.precision,
                                        "scale": field.scale,
                                        "required": field.required,
                                        "editable": field.editable,
                                        "dbmsType": dbmsType_lookup[field.type]
                                    } for field in fields if field.name not in geom_fields]
                        layer['featureTable']['dataConnection']['sqlQuery'] = f'select {",".join(field_names)} from main.{layer["name"]}'
                        layer['featureTable']['dataConnection']['queryFields'] = field_jsons
                else:
                    drop_list.append(i)
            else:
                layer['layers'] = maritime_layers
                # set name of group layer
                layer['name'] = self.gdb_name

        # Remove empty layers for missing geom_types
        for index in sorted(drop_list, reverse=True):
            layer_dict['layerDefinitions'].pop(index)

        with open(str(output_folder / f'{self.gdb_name}.lyrx'), 'w') as writer:
            writer.writelines(json.dumps(layer_dict, indent=4))     
