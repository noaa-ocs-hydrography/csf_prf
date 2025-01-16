import arcpy
from csf_prf.engines.MHWBufferEngine import MHWBufferEngine


class MHWBuffer:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "MHW Buffer"
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
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
                
        param_lookup = self.setup_param_lookup(parameters)
        downloader = MHWBufferEngine(param_lookup)
        downloader.start()
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

    # Custom Python code ##############################
    def get_params(self):
        """Set up the tool parameters"""
        
        sheets_shapefile = arcpy.Parameter(
            displayName="Sheets boundary in shapefile format:",
            name="sheets",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input"
        )

        enc_files = arcpy.Parameter(
            displayName="ENC File(s) (Leave empty to automatically download ENC files):",
            name="enc_files",
            datatype="DEFile",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        enc_files.filter.list = ['000']

        output_folder = arcpy.Parameter(
            displayName="Output Folder:",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        return [
            sheets_shapefile,
            enc_files,
            output_folder
        ]

    def setup_param_lookup(self, params):
        """Build key/value lookup for parameters"""

        param_names = [
            'sheets',
            'enc_files',
            'output_folder'
        ]

        lookup = {}
        for name, param in zip(param_names, params):
            lookup[name] = param
        self.param_lookup = lookup
        return lookup
        
    
    
