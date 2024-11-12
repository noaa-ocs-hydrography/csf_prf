import arcpy
import os
from csf_prf.engines.S57ConversionEngine import S57ConversionEngine


class S57Conversion:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "S-57 to Geopackage"
        self.description = ""

    def getParameterInfo(self):
        """Define the tool parameters."""
        enc_file = arcpy.Parameter(
            displayName="ENC File (.000):",
            name="enc_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=False
        )
        enc_file.filter.list = ['000']

        output_folder = arcpy.Parameter(
            displayName="Output Folder:",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )
        layerfile_export = arcpy.Parameter(
            displayName="Create layerfile to view output data like an ENC chart?",
            name="layerfile_export",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )

        return [enc_file, output_folder, layerfile_export]

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
        conversion = S57ConversionEngine(param_lookup)
        conversion.start()
        self.delete_geodatabase()
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
    
    def setup_param_lookup(self, params):
        """Build key/value lookup for parameters"""

        param_names = [
            'enc_file',
            'output_folder',
            'layerfile_export'
        ]

        lookup = {}
        for name, param in zip(param_names, params):
            lookup[name] = param
        self.param_lookup = lookup
        return lookup
    
    def delete_geodatabase(self) -> None:
        """Delete the intermediate geodatabase dataset"""

        arcpy.AddMessage('Deleting Geodatabase')
        gdb_name = self.param_lookup['enc_file'].valueAsText.split('\\')[-1].replace('.000', '')
        arcpy.AddMessage(gdb_name)
        output_db_path = os.path.join(self.param_lookup['output_folder'].valueAsText, gdb_name + '.gdb')
        print('output gdb:', output_db_path)
        arcpy.management.Compact(output_db_path)
        arcpy.management.Delete(output_db_path)