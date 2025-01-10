import os
import requests
import shutil
import arcpy
import pathlib

from csf_prf.engines.Engine import Engine

arcpy.env.overwriteOutput = True


class MHWBufferEngine(Engine):
    """Class to download all ENC files that intersect a project boundary shapefile"""

    def __init__(self, param_lookup: dict) -> None:
        self.param_lookup = param_lookup

    def start(self) -> None:
        """Main method to begin process"""

        # TODO do we need to allow GC features input or download?

        # TODO use input ENC files or download ENC files?

        # TODO get COALNE features with WATLEV blank or always dry
        # TODO get SLCONS features
            # TODO SLCONS 4, check if CONDTN not = piers/ruins
        
        # TODO get chart scale from MapInfo table

        # TODO Intersect chart scale with all features

        # TODO add attribute values

        # TODO project to WGS84?

        # TODO buffer selected features 

        # TODO remove donut polygons

        # TODO project again to NAD83?

        # TODO write out shapefile
        arcpy.AddMessage('Done')