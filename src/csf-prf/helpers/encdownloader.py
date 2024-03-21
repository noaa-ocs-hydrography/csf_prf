import requests
import xml.etree.ElementTree as ET


class ENCDownloader:
    def __init__(self):
        self.xml_path = "https://charts.noaa.gov/ENCs/ENCProdCat_19115.xml"

    def start(self):
        xml = self.get_enc_xml()
        intersected_elements = self.find_intersecting_polygons(xml)

    def find_intersecting_polygons(self, xml):
        # use XTREE to parse XML for intersecting polygons
        # loop through each chart and check if intersects?  seems horribly slow
        root = ET.fromstring(xml)
        for child in root:
            linear_ring = child[0][0][0][5][0][7][0][1][0][0][0][0][0]
            coords = [item.text for item in linear_ring]
            print(coords)
            break
        # if intersects, get CI_OnlineResource URL for ENC zip file
        # store URL in a list
        return

    
    def get_enc_xml(self, path=False):
        result = requests.get(path if path else self.xml_path)
        return result.content 


    # make requests for each ENC zip file URL
    # store them in an output ENC folder

    # unzip each file that was downloaded

    # run the ENCReaderEngine on the files
  
   
if __name__ == "__main__":
    downloader = ENCDownloader()
    downloader.start()