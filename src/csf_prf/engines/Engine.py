import json
import  yaml
import pathlib
import os
import zipfile
import arcpy

from osgeo import ogr

INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class Engine:

    def add_column_and_constant(self, layer, column, expression='', field_type='TEXT', field_length=255, nullable=False) -> None:
        """
        Add the asgnment column and 
        :param arcpy.FeatureLayerlayer layer: In memory layer used for processing
        """

        if nullable:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length, field_is_nullable='NULLABLE')
        else:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length)
            arcpy.management.CalculateField(
                layer, column, expression, expression_type="PYTHON3", field_type=field_type
            )

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
