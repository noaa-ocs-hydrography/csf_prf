import arcpy
from csf_prf.engines.ClipEncEngine import ClipEncEngine


class ENCClipper:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "ENC Clipper"
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
        downloader = ClipEncEngine(param_lookup)
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
            displayName="Input folder containing ENC files:",
            name="input_folder",
            datatype="DEFolder",
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

        return [
            sheets_shapefile,
            output_folder
        ]

    def setup_param_lookup(self, params):
        """Build key/value lookup for parameters"""

        param_names = [
            'sheets',
            'output_folder'
        ]

        lookup = {}
        for name, param in zip(param_names, params):
            lookup[name] = param
        self.param_lookup = lookup
        return lookup
        
    