# -*- coding: utf-8 -*-


from csf_prf.ags_tools.CompositeSourceCreator import CompositeSourceCreator
from csf_prf.ags_tools.ENCDownloader import ENCDownloader

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "CSF/PRF Toolbox"
        self.alias = "csf_prf_tools"

        self.tools = [ENCDownloader, CompositeSourceCreator]
