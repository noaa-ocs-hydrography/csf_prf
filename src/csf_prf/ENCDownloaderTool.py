import arcpy
from csf_prf.engines.ENCDownloaderEngine import ENCDownloaderEngine


class ENCDownloader:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "ENC Downloader"
        self.description = ""

    def getParameterInfo(self):
        """Define the tool parameters."""
        params = self.get_params()
        return params

    def isLicensed(self):
        """Set whether the tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""

        self.check_input_crs(parameters)

        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
                
        param_lookup = self.setup_param_lookup(parameters)
        downloader = ENCDownloaderEngine(param_lookup)
        downloader.start()
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

    # Custom Python code ##############################
    def check_input_crs(self, parameters) -> None:
        """Set error message if input dataset not in WGS84"""

        if parameters[0].value:
            sheets = parameters[0].valueAsText.replace("'", "").split(';')
            crs_values = [arcpy.Describe(sheet).spatialReference.factoryCode for sheet in sheets]
            bad_crs = [crs for crs in crs_values if crs != 4326]
            if bad_crs:
                parameters[0].setErrorMessage(f'Invalid CRS for input dataset.\n{str(bad_crs)}\nProject dataset to WGS84, EPSG 4326.')

    def get_params(self):
        """Set up the tool parameters"""
        
        sheets_shapefile = arcpy.Parameter(
            displayName="Sheets boundary in shapefile format:",
            name="sheets",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input"
        )

        output_folder = arcpy.Parameter(
            displayName="Output Folder:",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        overwrite_files = arcpy.Parameter(
            displayName="Overwrite any previously downloaded ENC files?",
            name="overwrite_files",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        overwrite_files.value = False

        return [
            sheets_shapefile,
            output_folder,
            overwrite_files
        ]

    def setup_param_lookup(self, params):
        """Build key/value lookup for parameters"""

        param_names = [
            'sheets',
            'output_folder',
            'overwrite_files'
        ]

        lookup = {}
        for name, param in zip(param_names, params):
            lookup[name] = param
        self.param_lookup = lookup
        return lookup
        
    
    
