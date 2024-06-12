import requests
from bs4 import BeautifulSoup

result = requests.get('https://charts.noaa.gov/ENCs/ENCProdCat.xml')

xml = result.content

soup = BeautifulSoup(xml, 'xml')
xml_cells = soup.find_all('cell')

status = set()
cell_types = set()
for cell in xml_cells:
    status.add(cell.find('status').text)
    coverage = cell.find('cov')
    if coverage:
        panels = coverage.find_all('panel')
        for panel in panels:
            cell_types.add(panel.find('type').text)

print('status:', status)
print('types:', cell_types)
# status: {'Active', 'Cancelled'}
# types: {'I', 'E'}


# Example cell

# <cell>
#    <name>US2HA06M</name>
#    <lname>Ni‘ihau to French Frigate Shoals;Necker Island;Nihoa</lname>
#    <cscale>663392</cscale>
#    <status>Active</status>
#    <coast_guard_districts>
#        <coast_guard_district>14</coast_guard_district>
#    </coast_guard_districts>
#    <states>
#        <state>HI</state>
#        <state>PO</state>
#    </states>
#    <regions>
#        <region>40</region>
#    </regions>
#    <zipfile_location>https://www.charts.noaa.gov/ENCs/US2HA06M.zip</zipfile_location>
#    <zipfile_datetime>20240611_015304</zipfile_datetime>
#    <zipfile_datetime_iso8601>2024-06-11T05:53:04Z</zipfile_datetime_iso8601>
#    <zipfile_size>347924</zipfile_size>
#    <edtn>5</edtn>
#    <updn>1</updn>
#    <uadt>2018-05-14</uadt>
#    <isdt>2018-11-21</isdt>
#    <cov>
#        <panel>
#            <panel_no>1</panel_no>
#            <type>E</type>
#            <vertex>
#                <lat>24.6067759</lat>
#                <long>-163.1666667</long>
#            </vertex>
#            <vertex>
#                <lat>24.5166666</lat>
#                <long>-163.1666667</long>
#            </vertex>
#            <vertex>
#                <lat>24.6067759</lat>
#                <long>-163.1666667</long>
#            </vertex>
#        </panel>
#    </cov>
# </cell>