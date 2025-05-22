import pathlib
import wx

CSF_PRF_TOOLBOX = pathlib.Path(__file__).parents[0] / 'csf_prf' / 'src' / 'csf_prf'


class CSFPRFFrame(wx.Frame):
    def __init__(self, parent):
        """Copy path for adding a folder connection"""

        wx.Frame.__init__(self, parent)
        self.Title = "Copy path for ArcGIS Pro Folder Connection"
        self.SetSize(500, 500, 900, 160)
        self.csf_prf_folder = str(CSF_PRF_TOOLBOX)
        self.panel = wx.Panel(self, wx.ID_ANY)
        self.text = wx.TextCtrl(self.panel, wx.ID_ANY, size = (900,50), value=self.csf_prf_folder, style = wx.TE_READONLY | wx.TE_CENTER)
        self.button = wx.Button(self.panel, wx.ID_ANY, 'Copy to Clipboard', (400, 50))
        self.button.Bind(wx.EVT_BUTTON, self.button_click)
        
    def button_click(self, event):
        """Add folder path to clipboard"""
        
        copy_data = wx.TextDataObject()
        copy_data.SetText(self.text.GetValue())
        if not wx.TheClipboard.IsOpened():
            wx.TheClipboard.Open()
            wx.TheClipboard.SetData(copy_data)
            wx.TheClipboard.Close()


if __name__ == "__main__":
    app = wx.App(False)
    frame = CSFPRFFrame(None)
    frame.Show()
    app.MainLoop()