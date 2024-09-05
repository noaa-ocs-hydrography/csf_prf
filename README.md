# CSF/PRF Toolbox

This application contains Python code for the workflows related to 
the Composite Source File/Project Reference File(CSF/PRF).

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