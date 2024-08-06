import os
import arcpy
import time
import pathlib
from csf_prf.engines.Engine import Engine

class S57ConversionEngine(Engine):
    """Class for converting S57 files to geopackage"""

    def __init__(self, param_lookup: dict):
        self.param_lookup = param_lookup