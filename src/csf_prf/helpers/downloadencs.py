import os
import requests
import zipfile
import shutil
import arcpy
import pathlib

from bs4 import BeautifulSoup

arcpy.env.overwriteOutput = True


class DownloadENCs:
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.xml_path = "https://charts.noaa.gov/ENCs/ENCProdCat_19115.xml" # TODO will this URL ever change?
        self.sheets_layer = param_lookup['sheets'].valueAsText
        self.output_folder = param_lookup['output_folder'].valueAsText

    def build_polygons_layer(self, polygons):
        """
        :param list[list[list[string|float]] polygons: List ENC file extents and file ID numbers
        :returns arcpy.Layer: Returns an arcpy feature layer
        """

        polygons_layer = arcpy.management.CreateFeatureclass(
            'memory', 
            'polygons_layer', 'POLYGON', spatial_reference=arcpy.SpatialReference(4326))
        arcpy.management.AddField(polygons_layer, 'enc_id', 'TEXT')
        with arcpy.da.InsertCursor(polygons_layer, ['enc_id', 'SHAPE@'], explicit=True) as polygons_cursor: 
            for id, geometry in polygons: # unpack list of id, geometry
                points = [arcpy.Point(coord[1], coord[0]) for coord in geometry]
                coord_array = arcpy.Array(points)
                geometry = arcpy.Polygon(coord_array, arcpy.SpatialReference(4326))
                polygons_cursor.insertRow([id, geometry])
        return polygons_layer
    
    def clean_geometry(self, polygon):
        """
        Clean up XML geometry text and convert to number
        :param str polygon: Text version of XML polygon extent
        :return list[list[float]]: List of polygon geometry converted to number
        """

        strip_polygon = polygon.strip()
        polygon_text = strip_polygon.split('\n')
        return [[float(c) for c in coord.split(' ')] for coord in polygon_text if coord]
    
    def cleanup_output(self) -> None:
        """Delete any zip files after use"""

        output_path = pathlib.Path(self.output_folder)
        for enc_file in output_path.rglob('*.zip'):
            arcpy.AddMessage(f'Remove unzipped: {enc_file.name}')
            enc_file.unlink()
        if os.path.exists(str(output_path / 'ENC_ROOT')):
            arcpy.AddMessage(f'Removing ENC_ROOT folder')
            shutil.rmtree(output_path / 'ENC_ROOT')

    def download_enc_zipfiles(self, enc_intersected) -> None:
        """
        Download all intersected ENC zip files
        :param arcpy.Layer enc_intersected: Layer of intersected polygons
        """
        with arcpy.da.SearchCursor(enc_intersected, ['enc_id']) as cursor:
            for row in cursor:
                downloaded = str(pathlib.Path(self.output_folder) / str(row[0] + '.000'))
                if not os.path.exists(downloaded):
                    arcpy.AddMessage(f'Downloading: {row[0]}')
                    # TODO check if file in output folder
                    enc_zip = requests.get(f'https://charts.noaa.gov/ENCs/{row[0]}.zip')
                    output_file = str(pathlib.Path(self.output_folder) / f'{row[0]}.zip')
                    with open(output_file, 'wb') as file:
                        for chunk in enc_zip.iter_content(chunk_size=128):
                            file.write(chunk)
                else:
                    arcpy.AddMessage(f'File already downloaded: {row[0]}')

    def find_intersecting_polygons(self, xml):
        """
        Obtain ENC geometry from XML and spatial query against project boundary
        :param str xml: Text result from reading XML file
        :return arpy.Layer: Returns an arcpy feature layer
        """

        soup = BeautifulSoup(xml, 'xml')
        xml_polygons = soup.find_all('polygon')
        polygons = []
        for polygon in xml_polygons:
            # id, geometry
            polygons.append([polygon.find('gml:Polygon').attrs['gml:id'].split('_')[0], self.clean_geometry(polygon.text)])
        enc_polygons_layer = self.build_polygons_layer(polygons)
        enc_intersected = arcpy.management.SelectLayerByLocation(enc_polygons_layer, 'INTERSECT', self.sheets_layer)
        arcpy.management.CopyFeatures(enc_intersected, str(pathlib.Path(self.output_folder) / 'enc_intersected.shp'))
        arcpy.AddMessage(f'ENC files found: {arcpy.management.GetCount(enc_intersected)}')
        return enc_intersected
    
    def get_enc_xml(self, path=False):
        """
        Get XML result from a URL path
        :param str path: URL path to an XML file
        :return str: Text content from XML parsing
        """

        result = requests.get(path if path else self.xml_path)
        return result.content 
    
    def move_to_output_folder(self) -> None:
        """Move all *.000 files to the main output folder"""

        output_path = pathlib.Path(self.output_folder)
        for enc_file in output_path.rglob('*.000'):
            enc_path = pathlib.Path(enc_file)
            output_enc = str(output_path / enc_path.name)
            if not os.path.exists(output_enc):
                arcpy.AddMessage(f'Moving: {enc_file.name}')
                enc_path.rename(output_enc)

    def start(self) -> None:
        """Main method to begin process"""

        self.verify_sheets_layer()
        xml = self.get_enc_xml()
        enc_intersected = self.find_intersecting_polygons(xml)
        self.download_enc_zipfiles(enc_intersected)
        self.unzip_enc_files()
        self.move_to_output_folder()
        self.cleanup_output()
        # TODO Clipping process for ENCs
        # 1. Smaller scale ENCs (clipee) should be clipped by larger scale ENCs (clipper).  
        # 2. Older ENCs (clipee) should be clipped by newer ENCs (clipper).  
        # 3. ENCs that do not include all the same features as the corresponding raster chart (clipee) should be clipped by ENCs that do contain all the features (clipper). 

        arcpy.AddMessage('Done')

    def unzip_enc_files(self) -> None:
        """Unzip all zip fileis in a folder"""
        
        for enc_path in pathlib.Path(self.output_folder).rglob('*.zip'):
            # TODO check if existing unzipped file
            unzipped_file = str(enc_path).replace('zip', '000')
            if not os.path.exists(unzipped_file):
                arcpy.AddMessage(f'Unzipping: {enc_path.name}')
                with zipfile.ZipFile(enc_path, 'r') as zipped:
                    zipped.extractall(str(pathlib.Path(self.output_folder)))

    def verify_sheets_layer(self):
        """Convert geojson for tool to work same as shapefile"""
        
        if 'geojson' in self.sheets_layer:
            arcpy.AddMessage('Converting geojson input to feature layer')
            self.sheets_layer = arcpy.conversion.JSONToFeatures(self.sheets_layer, os.path.join('memory', 'sheets_layer'))
  