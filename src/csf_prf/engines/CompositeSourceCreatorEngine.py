import os
import arcpy
import time
import pathlib
import json

import arcpy.management

from csf_prf.engines.Engine import Engine
from csf_prf.engines.ENCReaderEngine import ENCReaderEngine
arcpy.env.overwriteOutput = True
arcpy.env.qualifiedFieldNames = False # Force use of field name alias


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


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
        self.gdb_name = 'csf_features'
        self.layerfile_name = 'maritime_layerfile'
        self.output_db = False
        self.junctions_layer = False
        self.sheets_layer = False
        self.output_data = None
        self.output_data = {
            'sheets': None,
            'junctions': None
        }

    def convert_enc_files(self) -> None:
        """Process the ENC files input parameter"""

        if not self.param_lookup['enc_files'].valueAsText:
            self.download_enc_files()

        arcpy.AddMessage('Converting ENC files')
        enc_engine = ENCReaderEngine(self.param_lookup, self.sheets_layer)
        enc_engine.start()
        self.output_data = {**self.output_data, **enc_engine.output_data}  # merge output from ENCReaderEngine
        # Could use composition to pass around the base engine instance

    def convert_junctions(self) -> None:
        """Process the Junctions input parameter"""

        junctions_parameter = self.param_lookup['junctions'].valueAsText
        if junctions_parameter:
            junctions = junctions_parameter.replace("'", "").split(';')
            arcpy.AddMessage('Converting junctions')
            layers = [self.make_junctions_layer(junctions_file) for junctions_file in junctions]
            layer = arcpy.management.Merge(layers, r'memory\junctions_layer')
            expression = "'Survey: ' + str(!survey!)"  # TODO is junctions missing registry_n?
            self.add_column_and_constant(layer, 'invreq', expression)
            self.add_column_and_constant(layer, 'asgnmt', "'Assigned'")
            self.junctions_layer = layer

    def convert_sheets(self) -> None:
        """Process the Sheets input parameter"""

        sheet_parameter = self.param_lookup['sheets'].valueAsText
        if sheet_parameter:
            arcpy.AddMessage('Converting sheets')
            sheets = sheet_parameter.replace("'", "").split(';')
            layers = [self.make_sheets_layer(sheets_file) for sheets_file in sheets]
            layer = arcpy.management.Merge(layers, r'memory\sheets_layer')
            expression = "'Survey: ' + str(!registry_n!) + ', Priority: ' + str(!priority!) + ', Name: ' + str(!sub_locali!)"
            self.add_column_and_constant(layer, 'invreq', expression)
            self.add_column_and_constant(layer, 'asgnmt', "'Assigned'")

            # FME used inner polygons, but it is not needed
            # outer_features, inner_features = self.split_inner_polygons(layer)
            # self.write_sheets_to_featureclass('sheets', layer, outer_features + inner_features, 'output_sheets')
            self.sheets_layer = layer

    def copy_layer_to_feature_class(self, output_data_type, layer, feature_class_name) -> None:
        """
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param str feature_class_name: Name for output feature_class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        output_gdb = os.path.join(output_folder, self.gdb_name + '.geodatabase')
        fc_path = os.path.join(output_gdb, feature_class_name)
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        arcpy.conversion.ExportFeatures(layer, fc_path)
        self.output_data[output_data_type] = fc_path

    def create_caris_export(self) -> None:
        """Output datasets to Geopackage by unique OBJL_NAME"""

        caris_folder = pathlib.Path(self.param_lookup['output_folder'].valueAsText) / 'caris_export'
        caris_folder.mkdir(parents=True, exist_ok=True)

        csfprf_output_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
        arcpy.management.CreateSQLiteDatabase(csfprf_output_path, spatial_type='GEOPACKAGE')
        for feature_type, feature_class in self.output_data.items():
            if feature_class:
                  # Don't export sheets or GC files to Caris gpkg
                if ("GC" not in feature_type and feature_type.split('_')[0] in ['Point', 'LineString', 'Polygon']):
                    # Export to csf_prf_geopackage.gpkg as well as CARIS gpkg files
                    self.export_to_geopackage(csfprf_output_path, feature_type, feature_class)
                    output_path = os.path.join( caris_folder, feature_type)
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
                    self.export_to_geopackage(csfprf_output_path, feature_type, feature_class)

    def export_to_feature_class(self, output_data_type, template_layer, feature_class_name) -> None:
        """
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param str feature_class_name: Name for output feature class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        output_name = os.path.join(os.path.join(output_folder, self.gdb_name + '.geodatabase'), feature_class_name)
        # TODO use Project() method to make a file instead of CopyFeatures.  Set to WGS84
        copied_layer = arcpy.management.CopyFeatures(template_layer, output_name)
        arcpy.management.DefineProjection(copied_layer, arcpy.SpatialReference(4326))

        self.output_data[output_data_type] = output_name

    def get_mhw_buffer(self) -> None:
        """Create MHW Buffer of Sheets and COALNE intersection"""

        arcpy.AddMessage('Clipping Sheets to MHW Buffer')
        self.load_toolbox()
        if not self.param_lookup['enc_files'].valueAsText:
            self.download_enc_files()
        
        arcpy.AddMessage(f'Clipping Sheets to MHW Buffer:')
        # Function name is a built-in combo of class and toolbox alias
        # Inputs are strings
        arcpy.MHWBuffer_csf_prf_tools(self.param_lookup['sheets'].valueAsText, 
                                      self.param_lookup['enc_files'].valueAsText, 
                                      self.param_lookup['output_folder'].valueAsText)
        self.set_sheets_input_param(pathlib.Path(self.param_lookup['output_folder'].valueAsText))

    def make_junctions_layer(self, junctions):
        """
        Create in memory layer for processing.
        This copies the input Junctions shapefile to not corrupt it.
        :param str junctions: Path to the input Junctions shapefile
        :return arcpy.FeatureLayer: In memory layer used for processing
        """
    
        required_fields = ['survey']
        field_info = arcpy.FieldInfo()
        input_fields = arcpy.ListFields(junctions)
        for field in input_fields:
            if field.name in required_fields:
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        if arcpy.Describe(junctions).spatialReference.projectionCode != 4326:
            arcpy.AddMessage(f' - Junctions layer was projected to WGS84')
            junctions = arcpy.management.Project(junctions, r'memory\projected_junctions', 4326)
        layer = arcpy.management.MakeFeatureLayer(junctions, field_info=field_info)
        return layer

    def make_sheets_layer(self, sheets):
        """
        Create in memory layer for processing.
        This copies the input Sheets shapefile to not corrupt it.
        :param str sheets: Path to the input Sheets shapefile
        :return arcpy.FeatureLayer: In memory layer used for processing
        """

        required_fields = ['priority', 'project_nu', 'sub_locali', 'registry_n']
        field_info = arcpy.FieldInfo()
        input_fields = arcpy.ListFields(sheets)
        for field in input_fields:
            if field.name in required_fields:
                field_info.addField(field.name, field.name, 'VISIBLE', 'NONE')
            else:
                field_info.addField(field.name, field.name, 'HIDDEN', 'NONE')
        if arcpy.Describe(sheets).spatialReference.projectionCode != 4326:
            arcpy.AddMessage(f' - Sheets layer was projected to WGS84')
            sheets = arcpy.management.Project(sheets, r'memory\projected_sheets', 4326)
        layer = arcpy.management.MakeFeatureLayer(sheets, field_info=field_info)
        return layer

    def merge_shps_to_enc(self) -> None:
        """Append Sheets and Junctions to output assigned polygons"""

        arcpy.AddMessage(f'Merging Sheets and Junctions to assigned polygons')
        sheets_fields = ["SHAPE@", "project_nu", "sub_locali", "registry_n", "invreq"]
        sheets_cursor = [row for row in arcpy.da.SearchCursor(self.sheets_layer, sheets_fields)] if self.sheets_layer else False
        junctions_fields = ["SHAPE@", "survey", "invreq"]  # "survey", "year", "scale", "field_unit"  TODO do we need these fields?
        junctions_cursor = [row for row in arcpy.da.SearchCursor(self.junctions_layer, junctions_fields)] if self.junctions_layer else False
        polygon_assigned = self.output_data[f'Polygon_features_assigned']
        new_fields = [*sheets_fields[1:], *junctions_fields[1:]]
        for field in new_fields:
            self.add_column_and_constant(polygon_assigned, field, nullable=True) 
        existing_fields = ['OBJL_NAME', 'FCSubtype'] if self.param_lookup['layerfile_export'].value else ['OBJL_NAME']
        if sheets_cursor:
            existing_values = ['TESARE', '115'] if self.param_lookup['layerfile_export'].value else ['TESARE']
            with arcpy.da.InsertCursor(polygon_assigned, sheets_fields + existing_fields) as cursor:
                for sheets_row in sheets_cursor:
                    cursor.insertRow([*sheets_row, *existing_values])
        if junctions_cursor:
            existing_values = ['TWRTPT', '70'] if self.param_lookup['layerfile_export'].value else ['TWRTPT']
            with arcpy.da.InsertCursor(polygon_assigned, junctions_fields + existing_fields) as cursor:
                for junctions_row in junctions_cursor:
                    cursor.insertRow([*junctions_row, *existing_values])

        # Set empty values to empty strings to match other data
        with arcpy.da.UpdateCursor(polygon_assigned, ['*']) as cursor:
            for row in cursor:
                new_row = list(row)
                for i, val in enumerate(new_row):
                    if val is None:
                        new_row[i] = ''
                cursor.updateRow(new_row)

    def start(self) -> None:
        """Main method to begin process"""

        start = time.time()
        # self.get_mhw_buffer()  # TODO maybe not call this from CSF tool? Would require two tools be ran if needed
        self.create_output_gdb() # TODO move to the base class
        self.convert_sheets()
        self.convert_junctions()
        self.convert_enc_files()
        self.merge_shps_to_enc()
        self.write_to_geopackage()
        if self.param_lookup['layerfile_export'].value:
            self.write_output_layer_file()
        arcpy.AddMessage('\nDone')
        arcpy.AddMessage(f'Run time: {(time.time() - start) / 60}')

    def write_output_layer_file(self) -> None:
        """Update layer file for output gdb"""

        # TODO layer file missing unassigned layers

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
        for layer in layer_dict['layerDefinitions']:
            if 'featureTable' in layer:
                layer['featureTable']['dataConnection']['workspaceConnectionString'] = f'AUTHENTICATION_MODE=OSA;DATABASE={output_gpkg}'
                fields = arcpy.ListFields(os.path.join(output_folder, self.gdb_name + '.geodatabase', layer['name']))
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
        
        with open(str(output_folder / f'{self.layerfile_name}.lyrx'), 'w') as writer:
            writer.writelines(json.dumps(layer_dict, indent=4))              

    def write_to_geopackage(self) -> None:
        """Copy the output feature classes to Geopackage"""

        arcpy.AddMessage('Writing to geopackage database')
        if self.param_lookup['caris_export'].value:
            self.create_caris_export()
        else:
            if not self.output_db: # TODO double check is self.output_db needs to be used
                output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, self.gdb_name)
                arcpy.AddMessage(f'Creating output GeoPackage in {output_db_path}.gpkg')
                arcpy.management.CreateSQLiteDatabase(output_db_path, spatial_type='GEOPACKAGE')
                self.output_db = True
            else:
                arcpy.AddMessage(f'Output GeoPackage already exists')
            for feature_type, feature_class in self.output_data.items():
                if feature_class:
                    self.export_to_geopackage(output_db_path, feature_type, feature_class)                    

    def write_sheets_to_featureclass(self, output_data_type, template_layer, features, feature_class_name) -> None:
        """
        NOT USED ANYMORE
        Store processed layer as an output feature class
        :param str output_data_type: Name of input parameter type being stored; see param_lookup
        :param arcpy.FeatureLayer template_layer: Layer used as a schema template
        :param (list[dict[]]) features: Combined outer and inner feature lists
        :param str feature_class_name: Name for output feature_class
        """

        output_folder = str(self.param_lookup['output_folder'].valueAsText)
        arcpy.AddMessage(f'Writing output feature class: {feature_class_name}')
        output_name = os.path.join(output_folder, self.gdb_name + '.geodatabase', feature_class_name)
        arcpy.management.CreateFeatureclass(os.path.join(output_folder, self.gdb_name + '.geodatabase'), feature_class_name, 
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
            # This adds the inner sheets polygons that were found to the output dataset
            for feature in features:
                vertices = [(point.X, point.Y) for point in feature['geometry']]
                polygon = list(vertices)
                # TODO make a geometry object and projectAs(wgs84)
                cursor.insertRow([polygon] + list(feature['attributes'][2:]))
        self.output_data[output_data_type] = output_name

