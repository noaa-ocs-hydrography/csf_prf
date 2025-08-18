import os
import shutil
import pathlib
import zipfile
import xml.etree.ElementTree as ET

from urllib import request
from osgeo import gdal, ogr, osr
osr.DontUseExceptions()

gdal.SetConfigOption('CHECK_DISK_FREE_SPACE', 'FALSE')


class ENCDownloaderOpenSourceEngine:
    """Class to download all ENC files that intersect a project boundary geojson"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup
        self.xml_path = "https://charts.noaa.gov/ENCs/ENCProdCat.xml"
        self.geojson = None
        self.output_folder = param_lookup['output_folder']

    def build_polygons_dataset(self, polygons):
        """
        Create an in memory polygon GDAL dataset for querying against ENC XML geometry
        :param list[str | list[list[float]] polygons: List ENC file extents and file ID numbers
        :returns gdal.Dataset: Returns a polygon dataset object
        """

        output_srs = osr.SpatialReference()
        output_srs.ImportFromEPSG(4326)
        in_memory_driver = ogr.GetDriverByName('Memory')    
        polygon_ds = in_memory_driver.CreateDataSource('polygons_layer.shp')
        polygons_layer = polygon_ds.CreateLayer(f'polygons', geom_type=ogr.wkbPolygon, srs=output_srs)
        field_definition = ogr.FieldDefn('enc_id', ogr.OFTString)
        polygons_layer.CreateField(field_definition)
        for id, polygon_list in polygons: # unpack list of id, polygon_list
            for polygon in polygon_list:
                ring = ogr.Geometry(ogr.wkbLinearRing)
                for coord in polygon:
                    ring.AddPoint(float(coord[0]), float(coord[1]))
                ring.AddPoint(float(polygon[0][0]), float(polygon[0][1]))
                polygon = ogr.Geometry(ogr.wkbPolygon)
                polygon.AddGeometry(ring)
                feature = ogr.Feature(polygons_layer.GetLayerDefn())
                feature.SetField('enc_id', id)
                feature.SetGeometry(polygon)
                polygons_layer.CreateFeature(feature)

        return polygon_ds
    
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
        for enc_file in output_path.glob('*.zip'):
            print(f'Remove unzipped: {enc_file.name}')
            enc_file.unlink()
        if os.path.exists(str(output_path / 'ENC_ROOT')):
            print(f'Removing ENC_ROOT folder')
            shutil.rmtree(output_path / 'ENC_ROOT')

    def create_geojson_geometry(self):
        """Build GDAL geojson geometry reference"""

        geojson_ds = ogr.Open(self.param_lookup['geojson'])
        layer = geojson_ds.GetLayer()
        feature = layer.GetFeature(0)
        self.geojson = feature.GetGeometryRef().Clone()
        print(f'Loaded geojson: {self.param_lookup["geojson"]}')

    def download_enc_zipfiles(self, enc_intersected) -> None:
        """
        Download all intersected ENC zip files
        :param arcpy.Layer enc_intersected: Layer of intersected polygons
        """

        for polygon in enc_intersected:
            enc_id = polygon.GetField('enc_id')
            print(f'Downloading: {enc_id}')
            output_file = str(pathlib.Path(self.output_folder) / f'{enc_id}.zip')
            request.urlretrieve(f'https://charts.noaa.gov/ENCs/{enc_id}.zip', output_file)

    def find_intersecting_polygons(self, xml):
        """
        Obtain ENC geometry from XML and spatial query against project boundary
        :param str xml: Text result from reading XML file
        :return list[ogr.Feature]: Returns list of GDAL polygon features
        """

        tree = ET.fromstring(xml)
        xml_cells = tree.findall('cell')    
        polygons = []   
        for cell in xml_cells:
            if cell.find('status').text == 'Active':  # Ignore Cancelled status files
                enc_id = cell.find('name').text
                coverage = cell.find('cov')
                panels = coverage.findall('panel')
                panel_polygons = self.get_panel_polygons(panels)
                polygons.append([enc_id, panel_polygons])

        enc_polygons_ds = self.build_polygons_dataset(polygons)
        enc_polygons_layer = enc_polygons_ds.GetLayer()
        # find polygons that intersect geojson
        encs_intersected = []
        for polygon in enc_polygons_layer:
            polygon_geom = polygon.GetGeometryRef()
            if polygon_geom.Intersects(self.geojson):
                encs_intersected.append(polygon)

        print(f'ENC files found: {len(encs_intersected)}')
        return encs_intersected
    
    def get_enc_xml(self, path=False):
        """
        Get XML result from a URL path
        :param str path: URL path to an XML file
        :return str: Text content from XML parsing
        """

        result = request.urlopen(path if path else self.xml_path).read()
        return result
    
    def get_panel_polygons(self, panels):
        """
        Convert the panel vertex values to polygons
        :param bs4.element panels: One to many XML coverage polygons for a single ENC
        :returns list[list[str]]: 
        """

        polygons = []
        for panel in panels:
            vertices = panel.findall('vertex')
            polygon = []
            for vertex in vertices:
                lat = vertex.find('lat').text
                long = vertex.find('long').text
                polygon.append([long, lat])
            polygons.append(polygon)
        return polygons
    
    def move_to_output_folder(self) -> None:
        """Move all *.000 files to the main output folder"""

        output_path = pathlib.Path(self.output_folder)
        enc_folders = []
        for enc_file in output_path.rglob('*.000'):
            enc_path = pathlib.Path(enc_file)
            enc_folders.append(enc_path.stem)
            output_enc = str(output_path / enc_path.name)
            if not os.path.exists(output_enc):
                print(f'Moving: {enc_file.name}')
                enc_path.rename(output_enc)
        for folder in enc_folders:
            unzipped_folder = output_path / folder
            if os.path.exists(unzipped_folder):
                shutil.rmtree(unzipped_folder)

    def start(self) -> None:
        """Main method to begin process"""

        self.create_geojson_geometry()
        xml = self.get_enc_xml()
        enc_intersected = self.find_intersecting_polygons(xml)
        self.download_enc_zipfiles(enc_intersected)
        self.unzip_enc_files(self.output_folder, '000')
        self.move_to_output_folder()
        self.cleanup_output()
        self.geojson = None

    def unzip_enc_files(self, output_folder, file_ending) -> None:
        """Unzip all zip fileis in a folder"""

        for zipped_file in pathlib.Path(output_folder).rglob('*.zip'):
            unzipped_file = str(zipped_file).replace('zip', file_ending)
            if not os.path.exists(unzipped_file):
                download_folder = unzipped_file.replace(file_ending, '')
                with zipfile.ZipFile(zipped_file, 'r') as zipped:
                    zipped.extractall(str(download_folder))

if __name__ == '__main__':   
    param_lookup = {
        'geojson': r"path\to\outline.geojson",
        'output_folder': r"path\to\output\folder"
    }
    engine = ENCDownloaderOpenSourceEngine(param_lookup)
    engine.start()