# -*- coding: utf-8 -*-

import pathlib
CSFPRF_MODULE = pathlib.Path(__file__).parents[1]
if CSFPRF_MODULE.name != 'src':
    raise ImportError('CSF_PRF_Toolbox.pyt must reside in "src/csf_prf" folder location!')

import sys
sys.path.append(str(CSFPRF_MODULE))

from csf_prf.CompositeSourceCreatorTool import CompositeSourceCreator
from csf_prf.ENCDownloaderTool import ENCDownloader
from csf_prf.S57ConversionTool import S57Conversion


class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "CSF/PRF Toolbox"
        self.alias = "csf_prf_tools"

        self.tools = [ENCDownloader, CompositeSourceCreator, S57Conversion]
