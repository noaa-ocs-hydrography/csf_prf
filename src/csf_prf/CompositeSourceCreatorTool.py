import arcpy
from csf_prf.engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine


class CompositeSourceCreator:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Composite Source Creator"
        self.description = ""
        self.param_lookup = {}

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
        engine = CompositeSourceCreatorEngine(param_lookup)
        engine.start()
        return
        

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

    # Custom Python code ##############################
    def get_params(self):
        """Set up the tool parameters"""
        
        sheets_shapefile = arcpy.Parameter(
            displayName="Sheets in shp format (use template file in Project Planning Template for invreq to map):",
            name="sheets",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        junctions_shapefile = arcpy.Parameter(
            displayName="Junctions in shp format (expected input as an export from SURDEX for invreq to map):",
            name="junctions",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        bottom_sample_shapefile = arcpy.Parameter(
            displayName="Bottom Sample Esri Shape File(s):",
            name="bottom_samples",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        boundary_pts_shapefile = arcpy.Parameter(
            displayName="Maritime Boundary Points Rocks Esri Shape File(s):",
            name="maritime_boundary_pts",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        boundary_features_shapefile = arcpy.Parameter(
            displayName="Maritime Boundary Additional Features Esri Shape File(s):",
            name="maritime_boundary_features",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        boundary_baseline_shapefile = arcpy.Parameter(
            displayName="Maritime Boundary Baseline Esri Shape File(s):",
            name="maritime_boundary_baselines",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        # tides_mapinfo_tab = arcpy.Parameter(
        #     displayName="Tides CORP Source MapInfo TAB File:",
        #     name="tides",
        #     datatype="GPFeatureLayer",
        #     parameterType="Optional",
        #     direction="Input"
        # )
        enc_file = arcpy.Parameter(
            displayName="ENC File(s) (Leave empty to automatically download ENC files):",
            name="enc_files",
            datatype="DEFile",
            parameterType="Optional",
            direction="Input",
            multiValue=True
        )
        enc_file.filter.list = ['000']
        
        output_folder = arcpy.Parameter(
            displayName="CSF, PRF & Tide .000 Output File Folder:",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )
        download_geographic_cells = arcpy.Parameter(
            displayName="Get additional features from Geographic Cells?",
            name="download_geographic_cells",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        caris_export = arcpy.Parameter(
            displayName="Create CARIS ready Geopackage?",
            name="caris_export",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        layerfile_export = arcpy.Parameter(
            displayName="Create layerfile to view output data like an ENC chart?",
            name="layerfile_export",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )

        return [
            sheets_shapefile,
            junctions_shapefile,
            bottom_sample_shapefile,
            boundary_pts_shapefile,
            boundary_features_shapefile,
            boundary_baseline_shapefile,
            # tides_mapinfo_tab,
            enc_file,
            output_folder,
            download_geographic_cells,
            caris_export,
            layerfile_export
        ]
    
    @property
    def parameters(self):
        """Get a list of all parameter names"""

        return list(self.parameter_lookup.keys())
    
    def get_parameter(self, param):
        """Return a single parameter by key"""

        parameter = self.parameter_lookup.get(param)
        return parameter
    
    def setup_param_lookup(self, params):
        """Build key/value lookup for parameters"""

        param_names = [
            'sheets',
            'junctions',
            'bottom_samples',
            'maritime_boundary_pts',
            'maritime_boundary_features',
            'maritime_boundary_baselines',
            # 'tides',
            'enc_files',
            'output_folder',
            'download_geographic_cells',
            'caris_export',
            'layerfile_export'
        ]

        lookup = {}
        for name, param in zip(param_names, params):
            lookup[name] = param
        self.param_lookup = lookup
        return lookup
        

    
    
