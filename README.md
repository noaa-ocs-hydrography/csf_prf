# CSF-PRF Repository

This repository contains Python code for the workflows related to 
the Composite Source File/Project Reference File(CSF/PRF).

## Location of Tools
The repository currently contains an ArcGIS Python Toolbox and associated Tools.

**The Toolbox file:** *csf_prf/src/csf_prf/CSF_PRF_Toolbox.pyt*

**Tools:**
1. *csf_prf/src/csf_prf/CompositeSourceCreatorTool.py*
2. *csf_prf/src/csf_prf/ENCDownloaderTool.py*
3. *csf_prf/src/csf_prf/S57ConversionTool.py*

## Accessing the tools
Once the files are downloaded, you will need to open ArcGIS Pro and add a Folder Connection.
1. Open ArcGIS Pro
2. Open an existing project or create a new project
3. Access the Catalog Pane: **Click View, then click Catalog Pane**
4. Right click on **Folders**, then click on **Add Folder Connection**
5. Choose a folder that lets you access the tools; **ex: c:\Users\xxxxx\Downloads**
6. In the Catalog Pane, expand Folders and expand the new folder you just added
7. Navigate to the CSF/PRF toolbox; **ex: c:\Users\xxxxx\Downloads\csf_prf\src\csf_prf\CSF_PRF_Toolbox.pyt**

## Use of Tools
1. Double click on the CSF_PRF_Toolbox.pyt file to open it
2. Double click one of the tools to open the user interface
3. Add the required parameters for the tool or any optional parameters
4. Add the output folder for the tool to export files
5. Click run to start the tool
6. Click *View Details* to see log messages that show the status of the tool
7. View the output folder you selected to see the output data
8. If running the Composite Source Creator Tool, an optional *maritime_layerfile.lyrx* file <br>is added to the output folder to view the data like an ENC chart
9. Drag the *maritime_layerfile.lyrx* file into a map