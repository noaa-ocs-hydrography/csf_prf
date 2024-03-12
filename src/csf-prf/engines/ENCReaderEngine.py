import pathlib
import json
import arcpy
import os
import yaml

from osgeo import ogr
from engines.Engine import Engine
from engines.class_code_lookup import class_codes as CLASS_CODES
arcpy.env.overwriteOutput = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class ENCReaderEngine(Engine):
    def __init__(self, param_lookup: dict, sheets_layer):
        self.param_lookup = param_lookup
        self.sheets_layer = sheets_layer
        self.driver = None
        self.geometries = {
            'Point': {'features': [], 'layers': {'assigned': None, 'unassigned': None}},
            'LineString': {'features': [], 'layers': {'assigned': None, 'unassigned': None}},
            'Polygon': {'features': [], 'layers': {'assigned': None, 'unassigned': None}}
        }

    def add_columns(self):
        """Main caller for adding all columns"""

        self.add_objl_string()
        self.add_asgnmt_column()
        self.add_invreq_column()

    def add_asgnmt_column(self):
        """Populate the 'asgnmt' column for all feature layers"""

        arcpy.AddMessage(" - Adding 'asgnmt' column")
        for feature_type in self.geometries.keys():
            # Assigned layers
            self.add_column_and_constant(self.geometries[feature_type]['layers']['assigned'], 'asgnmt', 2)
            
            # Unassigned layers
            self.add_column_and_constant(self.geometries[feature_type]['layers']['unassigned'], 'asgnmt', 1)
            
    def add_invreq_column(self):
        """Add and populate the investigation required column for allowed features"""

        with open(str(INPUTS / 'invreq_lookup.yaml'), 'r') as lookup:
            objl_lookup = yaml.safe_load(lookup)
        invreq_options = objl_lookup['OPTIONS']

        for feature_type in self.geometries.keys():
            arcpy.AddMessage(f" - Adding 'invreq' column: {feature_type}")
            self.add_column_and_constant(self.geometries[feature_type]['layers']['assigned'], 'invreq', nullable=True)
            self.add_column_and_constant(self.geometries[feature_type]['layers']['unassigned'], 'invreq', nullable=True)
            self.set_assigned_invreq(feature_type, objl_lookup, invreq_options)
            self.set_unassigned_invreq(feature_type, objl_lookup, invreq_options)

    def add_objl_string(self):
        """Convert OBJL number to string name"""

        for feature_type in self.geometries.keys():
            self.add_column_and_constant(self.geometries[feature_type]['layers']['assigned'], 'OBJL_NAME', nullable=True)
            self.add_column_and_constant(self.geometries[feature_type]['layers']['unassigned'], 'OBJL_NAME', nullable=True)
            
            for value in ['assigned', 'unassigned']:
                with arcpy.da.UpdateCursor(self.geometries[feature_type]['layers'][value], ["OBJL", "OBJL_NAME"]) as updateCursor:
                    for row in updateCursor:
                        row[1] = CLASS_CODES.get(int(row[0]), CLASS_CODES['OTHER'])[0]
                        updateCursor.updateRow(row)

    def get_all_fields(self, features):
        """
        Build a unique list of all field names
        :param dict[dict[str]]: GeoJSON of string values for all features
        :returns set[str]: Unique list of all fields
        """
        
        fields = set()
        for feature in features:
            for field in feature['geojson']['properties'].keys():
                fields.add(field)
        return fields

    def get_enc_geometries(self) -> None:
        """Read and store all features from ENC file"""

        enc_files = self.param_lookup['enc_files'].valueAsText.replace("'", "").split(';')
        for enc_path in enc_files:
            enc_file = self.open_file(enc_path)
            for layer in enc_file:
                for feature in layer:
                    if feature:
                        feature_json = json.loads(feature.ExportToJson())
                        geom_type = feature_json['geometry']['type'] if feature_json['geometry'] else False  

                        if geom_type in ['Point', 'LineString', 'Polygon']:
                            self.geometries[geom_type]['features'].append({'geojson': feature_json})
                        elif geom_type == 'MultiPoint':
                            # MultiPoints are broken up now to single features with an ENV variable
                            feature_template = json.loads(feature.ExportToJson())
                            feature_template['geometry']['type'] = 'Point'
                            for point in feature.geometry():
                                feature_template['geometry']['coordinates'] = [point.GetX(), point.GetY()]  # XY
                                self.geometries['Point']['features'].append({'geojson': feature_template})     
                        else:
                            if geom_type:
                                arcpy.AddMessage(f'Unknown feature type: {geom_type}')
        
    def open_file(self, enc_path):
        """
        Open a single input ENC file
        :param str enc_path: Path to an ENC file on disk
        :returns GDAL.File: GDAL File object you can loop through
        """

        enc_file = self.driver.Open(enc_path, 0)
        return enc_file

    def perform_spatial_filter(self) -> None:
        """Spatial query all of the ENC features against Sheets boundary"""

        # sorted_sheets = arcpy.management.Sort(self.sheets_layer, r'memory\sorted_sheets', [["scale", "ASCENDING"]])
        # POINTS
        point_fields = self.get_all_fields(self.geometries['Point']['features'])
        points_layer = arcpy.management.CreateFeatureclass('memory', 'points_layer', 'POINT', spatial_reference=arcpy.SpatialReference(4326))
        for field in point_fields:
            arcpy.management.AddField(points_layer, field, 'TEXT')

        arcpy.AddMessage(' - Building point features')
        for feature in self.geometries['Point']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            # TODO this is slow to open new every time, but field names change
            # Another option might be to have lookup by index and fill missing values to None
            with arcpy.da.InsertCursor(points_layer, current_fields, explicit=True) as point_cursor: 
                coords = feature['geojson']['geometry']['coordinates']
                geometry = arcpy.PointGeometry(arcpy.Point(X=coords[0], Y=coords[1]), arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                point_cursor.insertRow([geometry] + attribute_values)
        points_assigned = arcpy.management.SelectLayerByLocation(points_layer, 'INTERSECT', self.sheets_layer)
        points_assigned_layer = arcpy.management.MakeFeatureLayer(points_assigned)
        point_unassigned = arcpy.management.SelectLayerByLocation(points_assigned_layer, selection_type='SWITCH_SELECTION')
        self.geometries['Point']['layers']['assigned'] = points_assigned
        self.geometries['Point']['layers']['unassigned'] = point_unassigned

        # LINES
        line_fields = self.get_all_fields(self.geometries['LineString']['features'])
        lines_layer = arcpy.management.CreateFeatureclass('memory', 'lines_layer', 'POLYLINE', spatial_reference=arcpy.SpatialReference(4326))
        for field in line_fields:
            arcpy.management.AddField(lines_layer, field, 'TEXT')

        arcpy.AddMessage(' - Building line features')
        for feature in self.geometries['LineString']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            with arcpy.da.InsertCursor(lines_layer, current_fields, explicit=True) as line_cursor: 
                points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates']]
                coord_array = arcpy.Array(points)
                geometry = arcpy.Polyline(coord_array, arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                line_cursor.insertRow([geometry] + attribute_values)
        lines_assigned = arcpy.management.SelectLayerByLocation(lines_layer, 'INTERSECT', self.sheets_layer)
        lines_assigned_layer = arcpy.arcpy.management.MakeFeatureLayer(lines_assigned)
        line_unassigned = arcpy.management.SelectLayerByLocation(lines_assigned_layer, selection_type='SWITCH_SELECTION')
        self.geometries['LineString']['layers']['assigned'] = lines_assigned
        self.geometries['LineString']['layers']['unassigned'] = line_unassigned

        # POLYGONS
        polygons_fields = self.get_all_fields(self.geometries['Polygon']['features'])
        polygons_layer = arcpy.management.CreateFeatureclass('memory', 'polygons_layer', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
        for field in polygons_fields:
            arcpy.management.AddField(polygons_layer, field, 'TEXT')

        arcpy.AddMessage(' - Building Polygon features')
        for feature in self.geometries['Polygon']['features']:
            current_fields = ['SHAPE@'] + list(feature['geojson']['properties'].keys())
            with arcpy.da.InsertCursor(polygons_layer, current_fields, explicit=True) as polygons_cursor: 
                polygons = feature['geojson']['geometry']['coordinates']
                if len(polygons) > 1:
                    points = [arcpy.Point(coord[0], coord[1]) for coord in polygons[0]]
                else:
                    points = [arcpy.Point(coord[0], coord[1]) for coord in feature['geojson']['geometry']['coordinates'][0]]
                coord_array = arcpy.Array(points)
                geometry = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                attribute_values = [str(attr) for attr in list(feature['geojson']['properties'].values())]
                polygons_cursor.insertRow([geometry] + attribute_values)
        polygons_assigned = arcpy.management.SelectLayerByLocation(polygons_layer, 'INTERSECT', self.sheets_layer)
        polygons_assigned_layer = arcpy.arcpy.management.MakeFeatureLayer(polygons_assigned)
        polygon_unassigned = arcpy.management.SelectLayerByLocation(polygons_assigned_layer, selection_type='SWITCH_SELECTION')
        self.geometries['Polygon']['layers']['assigned'] = polygons_assigned
        self.geometries['Polygon']['layers']['unassigned'] = polygon_unassigned

    def print_geometries(self) -> None:
        """Print GeoJSON of all features for review"""

        for feature_type in self.geometries.keys():
            for feature in self.geometries[feature_type]:
                arcpy.AddMessage(f"\n - {feature['type']}:{feature['geojson']}")
    
    def print_feature_total(self) -> None:
        """Print total number of assigned/unassigned features from ENC file"""

        points = arcpy.management.GetCount(self.geometries['Point']['layers']['assigned'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['assigned'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['assigned'])
        arcpy.AddMessage(f' - Found Points: {points}')
        arcpy.AddMessage(f' - Found Lines: {lines}')
        arcpy.AddMessage(f' - Found Polygons: {polygons}')
        arcpy.AddMessage(f' - Total assigned: {int(points[0]) + int(lines[0]) + int(polygons[0])}')
        points = arcpy.management.GetCount(self.geometries['Point']['layers']['unassigned'])
        lines = arcpy.management.GetCount(self.geometries['LineString']['layers']['unassigned'])
        polygons = arcpy.management.GetCount(self.geometries['Polygon']['layers']['unassigned'])
        arcpy.AddMessage(f' - Total unassigned: {int(points[0]) + int(lines[0]) + int(polygons[0])}')

    def save_feature_layers(self) -> None:
        """Write out assigned and unassigned layers to output folder"""

        for feature_type in self.geometries.keys():
            arcpy.AddMessage(f' - Saving {feature_type} layers to {str(OUTPUTS)}')
            arcpy.management.CopyFeatures(self.geometries[feature_type]['layers']['assigned'], str(OUTPUTS / f'{feature_type}-assigned.shp'))
            arcpy.management.CopyFeatures(self.geometries[feature_type]['layers']['unassigned'], str(OUTPUTS / f'{feature_type}-unassigned.shp'))

    def set_driver(self) -> None:
        """Set the S57 driver for GDAL"""

        self.driver = ogr.GetDriverByName('S57')

    def set_env_variables(self) -> None:
        """Set multipoint on ENV variable"""

        os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON"

    def set_unassigned_invreq(self, feature_type, objl_lookup, invreq_options) -> None:
        """
        Isolate logic for setting unassigned layer 'invreq' column
        :param str feature_type: Point, LineString, or Polygon
        :param dict[str[str|int]]: YAML values from invreq_look.yaml
        :param dict[int|str] invreq_options: YAML invreq string values to fill column
        """

        with arcpy.da.UpdateCursor(self.geometries[feature_type]['layers']['unassigned'], ['OBJL_NAME', 'invreq']) as updateCursor:
            for row in updateCursor:
                objl_found = row[0] in objl_lookup.keys()
                if objl_found:
                    if row[0] == 'SBDARE':
                        if feature_type != 'Point':
                            row[1] = invreq_options.get(14)
                    else:
                        row[1] = invreq_options.get(14)
                    updateCursor.updateRow(row)

    def set_assigned_invreq(self, feature_type, objl_lookup, invreq_options):
        """
        Isolate logic for setting assigned layer 'invreq' column
        :param str feature_type: Point, LineString, or Polygon
        :param dict[str[str|int]]: YAML values from invreq_look.yaml
        :param dict[int|str] invreq_options: YAML invreq string values to fill column
        """

        with arcpy.da.UpdateCursor(self.geometries[feature_type]['layers']['assigned'], ["SHAPE@", "*"]) as updateCursor:
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
                        if catmor == 1:
                            row[indx['invreq']] = invreq_options.get(10, '')
                        elif catmor in [2, 3, 4, 5, 6, 7]:
                            row[indx['invreq']] = invreq_options.get(1, '')
                # CATOBS column needed for OBSTRN
                elif row[indx['OBJL_NAME']] == 'OBSTRN':
                    if indx['CATOBS']:
                        catobs = row[indx["CATOBS"]]
                        if catobs == 2:
                            row[indx['invreq']] = invreq_options.get(12, '')
                        elif catobs == 5:
                            row[indx['invreq']] = invreq_options.get(8, '')
                        elif catobs in [None, 1, 3, 4, 6, 7, 8, 9, 10]:
                            row[indx['invreq']] = invreq_options.get(5, '')
                elif row[indx['OBJL_NAME']] == 'SBDARE':
                    row[indx['invreq']] = invreq_options.get(13, '')
                # CONDTN column needed for SLCONS
                elif row[indx['OBJL_NAME']] == 'SLCONS':
                    if indx['CONDTN']:
                        condtn = row[indx["CONDTN"]]
                        if condtn in [1, 3, 4, 5]:
                            row[indx['invreq']] = invreq_options.get(1, '')
                        elif condtn == 2:
                            row[indx['invreq']] = invreq_options.get(5, '')
                # WATLEV column needed for UWTROC
                elif row[indx['OBJL_NAME']] == 'UWTROC':
                    if indx['WATLEV']:
                        condtn = row[indx["WATLEV"]]
                        if condtn in [1, 2, 4, 5, 6, 7]:
                            row[indx['invreq']] = invreq_options.get(5, '')
                        elif condtn == 3:
                            row[indx['invreq']] = invreq_options.get(7, '')
                else:
                    # Set to OTHER value if missing
                    invreq = objl_lookup.get(row[indx['OBJL_NAME']], objl_lookup['OTHER'])['invreq']
                    row[indx['invreq']] = invreq_options.get(invreq, '')
                updateCursor.updateRow(row)

    def start(self):
        self.set_driver()
        self.set_env_variables()
        self.get_enc_geometries()
        self.perform_spatial_filter()
        self.print_feature_total()
        self.add_columns()
        # self.save_feature_layers()
