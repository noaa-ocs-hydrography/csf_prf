import requests
import zipfile
import glob
import arcpy
import pathlib

from bs4 import BeautifulSoup

arcpy.env.overwriteOutput = True


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[3] / 'outputs'


class ENCDownloader:
    def __init__(self, sheets_layer=str(INPUTS / 'G322_Sheets_01302024.shp')):
        self.xml_path = "https://charts.noaa.gov/ENCs/ENCProdCat_19115.xml"
        self.sheets_layer = sheets_layer

    def build_polygons_layer(self, polygons):
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
        strip_polygon = polygon.strip()
        polygon_text = strip_polygon.split('\n')
        return [[float(c) for c in coord.split(' ')] for coord in polygon_text]

    def download_enc_zipfiles(self, enc_intersected):
        with arcpy.da.SearchCursor(enc_intersected, ['enc_id']) as cursor:
            for row in cursor:
                print(f'Downloading: {row[0]}')
                enc_zip = requests.get(f'https://charts.noaa.gov/ENCs/{row[0]}.zip')
                with open(str(OUTPUTS / 'charts' / f'{row[0]}.zip'), 'wb') as file:
                    for chunk in enc_zip.iter_content(chunk_size=128):
                        file.write(chunk)

    def start(self):
        xml = self.get_enc_xml()
        enc_intersected = self.find_intersecting_polygons(xml)
        self.download_enc_zipfiles(enc_intersected)
        self.unzip_enc_files()

    def find_intersecting_polygons(self, xml):
        soup = BeautifulSoup(xml, 'xml')
        xml_polygons = soup.find_all('polygon')
        polygons = []
        for polygon in xml_polygons:
            # id, geometry
            polygons.append([polygon.find('gml:Polygon').attrs['gml:id'].split('_')[0], self.clean_geometry(polygon.text)])
        enc_polygons_layer = self.build_polygons_layer(polygons)
        enc_intersected = arcpy.management.SelectLayerByLocation(enc_polygons_layer, 'INTERSECT', self.sheets_layer)
        arcpy.management.CopyFeatures(enc_intersected, str(OUTPUTS / 'enc_intersected.shp'))
        print(f'ENC files found: {arcpy.management.GetCount(enc_intersected)}')
        return enc_intersected
    
    def get_enc_xml(self, path=False):
        result = requests.get(path if path else self.xml_path)
        return result.content 

    def unzip_enc_files(self):
        for enc_path in glob.glob(str(OUTPUTS / 'charts' / '*.zip')):
            print(f'Unzipping: {enc_path}')
            with zipfile.ZipFile(enc_path, 'r') as zipped:
                zipped.extractall(str(OUTPUTS / 'charts'))
  
   
if __name__ == "__main__":
    downloader = ENCDownloader()
    downloader.start()