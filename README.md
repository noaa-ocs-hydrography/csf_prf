# CSF-PRF Repository

This repository contains Python code for the workflows related to 
the Composite Source File/Project Reference File(CSF/PRF).

## Location of Tools
The repository currently contains an ArcGIS Python Toolbox and associated Tools.

**The Toolbox file:** *root/src/csf-prf/CSF_PRF_Toolbox.pyt*

**Tools:**
1. *root/src/csf-prf/ags_tools/CompositeSourceCreator.py*
2. *root/src/csf-prf/ags_tools/ENCDownloader.py*

## Setup .pth file
The respository needs a .pth file in your ArcGIS Pro Conda environment in order to access the code.
1. Open the *Python Command Prompt* to see your Conda environment
2. Type *conda env list* to find the path to your Conda environment
3. In Windows Explorer, navigate to *your/conda/environment/Lib/site-packages/
4. Create a file in that location called *noaa.pth*
5. Open that file in a text editor and paste in the path to the CSF-PRF repository like the following: *C:\path\to\your\respository\csf_prf\src*

## Use of Tools
1. Request copy of files from HSTB or clone repository
2. Set up the .pth file as documented above
3. Open ArcGIS Pro and add a folder connection to the repository files
4. Expand the CSF_PRF_Toolbox file to view the inner tools
5. Double click one of the tools to open the user interface
6. Add the required parameters for the tool or any optional parameters
7. Add the output folder for the tool to export files
8. Click run and view the log messages for tool status
9. View the output folder you selected to see the output data