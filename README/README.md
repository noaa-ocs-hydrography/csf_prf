# CSF/PRF Toolbox

This application contains Python code for the workflows related to 
the Composite Source File/Project Reference File(CSF/PRF).

## Code Version
- {VERSION}

## Location of Tools
The CSF/PRF Toolbox application currently contains an ArcGIS Python Toolbox and associated Python code.

**The Toolbox file:** csf_prf/src/csf_prf/CSF_PRF_Toolbox.pyt

## Tools
1. csf_prf/src/csf_prf/CompositeSourceCreatorTool.py
2. csf_prf/src/csf_prf/ENCDownloaderTool.py
3. csf_prf/src/csf_prf/S57ConversionTool.py

## Accessing the tools
Once Pydro pulls the latest changes, you will need to open ArcGIS Pro and add a Folder Connection.<br>
~**You can click the *Run* button to open a dialog box to copy the folder path to add to ArcGIS Pro**

### Add Folder Connection example
1. Open ArcGIS Pro
2. Open an existing project or create a new project
3. Access the Catalog Pane: **Click View, then click Catalog Pane**
4. Right click on **Folders**, then click on **Add Folder Connection**
5. Choose a folder that lets you access the tools; **ex: c:\path\to\pydro...**
6. In the Catalog Pane, expand Folders and expand the new folder you just added
7. Navigate to the CSF/PRF toolbox; **ex: c:\path\to\pydro...\csf_prf\src\csf_prf\CSF_PRF_Toolbox.pyt**

## Use of Tools
1. Double click on the CSF_PRF_Toolbox.pyt file to open it
2. Double click one of the tools to open the user interface
3. Add the required parameters for the tool or any optional parameters <br>**Sheets** and **Output Folder** are the only required parameters.
4. Add the output folder for the tool to export files <br>~You may want to add a new Folder Connection to ArcGIS Pro for your chosen output folder as well.
5. Click run to start the tool <br>~approx. runtime takes 7-10 minutes
6. Click **View Details** to see log messages that show the status of the tool
7. View the output folder you selected to see the output data
8. If running the Composite Source Creator Tool, an optional *maritime_layerfile.lyrx* file <br>is added to the output folder to view the data like an ENC chart
9. Drag the *maritime_layerfile.lyrx* file into a map

## Geotransformation
The S-57 to Geopackage conversion tools performs a geotransformation for objects where the field 
'descrp' = 'New'. The transformation used is NAD 83 (2011) to WGS 84 (ITRF08). These objects will have the transformation noted in the 'transformed' field.
Additional documentation on NAD83 to WGS84 can be found here: [Choosing An Appropriate Transformation](https://desktop.arcgis.com/en/arcmap/latest/map/projections/choosing-an-appropriate-transformation.htm)


## Support 
The CSF/PRF Tools are used by field units and general support is provided by your branch's streamlining team lead:
- [Tyanne Faulkes-PHB](mailto:tyanne.faulkes@noaa.gov?subject=Pydro-csf_prf_toolbox%20issue&body=Tyanne,)
- [Matt Wilson-AHB](mailto:matthew.wilson@noaa.gov?subject=Pydro-csf_prf_toolbox%20issue&body=Matt,)

If there are technical issues with the tools or documentation, feel free to contact the maintainer of the library:
- [Stephen Patterson-HSTB](mailto:stephen.patterson@noaa.gov?subject=Pydro-csf_prf_toolbox%20issue&body=Stephen,)