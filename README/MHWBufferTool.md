# MHW Buffer Tool

## Overview
The MHW Buffer Tool is an ArcGIS Pro Python Tool that creates buffer polygons from COALNE and SLCONS linear features and outputs a clipped Sheets shapefile

## Usage
View the main repository README file for guidance on loading the tools into ArcGIS Pro

## Input Parameters
The MHW Buffer Tool only requires three input parameters
    1. Sheets polygon shapefile
    2. ENC files to convert(Leave blank to download files)
    3. Output Folder

## Output Results
The main output from the MHWBufferTool is a shapefile containing Sheets that have been clipped to the processed Mean-High-Water boundary.
The tool also outputs intermediate files for user assistance. 
All of these files are written to the user selected output folder.

### &nbsp;&nbsp;File names:
&nbsp;&nbsp;1. (Input sheets name)_clip.shp<br />
&nbsp;&nbsp;&nbsp;&nbsp; - Portions of Sheets that overlapped the MHW features have been removed<br />
&nbsp;&nbsp;2. mhw_polygons.shp<br />
&nbsp;&nbsp;&nbsp;&nbsp; - Polygons built from any LNDARE area features in the input ENC files<br />
&nbsp;&nbsp;3. mhw_lines.shp<br />
&nbsp;&nbsp;&nbsp;&nbsp; - Lines built from any COALNE, SLCONS features in the input ENC files<br />
&nbsp;&nbsp;4. buffered_mhw_polygons.shp<br />
&nbsp;&nbsp;&nbsp;&nbsp; - Merged LNDARE, COALNE, and SLCONS features that have been buffered to chart scale<br />
&nbsp;&nbsp;5. dissolved_mhw_polygons.shp<br />
&nbsp;&nbsp;&nbsp;&nbsp; - Simplified polygons by dissolving any connected polygons in the bufffered_mhw_polygons.shp file<br />
&nbsp;&nbsp;&nbsp;&nbsp; - This dataset is what was used to clip the input Sheets datasets<br />