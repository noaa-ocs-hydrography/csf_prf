import pyodbc
import pathlib
import yaml
import glob


INPUTS = pathlib.Path(__file__).parents[3] / 'inputs'


class ENCReaderException(Exception):
    """Custom exception for tool"""

    pass 


def get_config_item(parent: str, child: str=False) -> tuple[str, int]:
    """Load config and return speciific key"""

    with open(str(INPUTS / 'lookups' / 'config.yaml'), 'r') as lookup:
        config = yaml.safe_load(lookup)
        parent_item = config[parent]
        if child:
            return parent_item[child]
        else:
            return parent_item
        
        
def test_table_access() -> None:
    print('Checking for Geographic Cells')
    pwd = get_config_item('GC', 'SQL_PW')
    connection = pyodbc.connect('Driver={SQL Server};'
                            'Server=OCS-VS-SQLT2PRD;'
                            'Database=mcd;'
                            'UID=DREGreader;'
                            f'PWD={pwd};')
    cursor = connection.cursor()
    print(type(cursor))
    

    info_code = 20  # Geographic Cells

    # cursor.execute(f"select TOP (5) * from sourcedocument")
    # cursor.execute(f"select * from sourcedocument where InformationCode = '20' AND Status = 'AVAILABLE' AND DocumentNumber IN ('11113', '11117')")
    
    # execute ENC query
    # path = INPUTS / 'sql' / 'GetRelatedENC.sql'
    # with open(path, 'r') as sql:
    #     query = sql.read()  
    # cursor.execute(query)

    cells = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    print(columns, '\n')
    

    # TODO check with Erik or Mark from MCD about DB schema
    cols = {}
    for i, name in enumerate(columns):
        cols[name] = i

    for row in cells:
        # row[cols['chartformat']] converted to a USX number? Coastal, Harbor, Small, etc. 
        # print([f"{col}: {row[cols[col]]}" for col in columns])
        print('\n')
        for val in [f"{col}: {row[cols[col]]}" for col in columns]:
            print(val)


def get_columns(cursor):
    return [column[0] for column in cursor.description]


def get_cursor():
    """
    Connected to MCD SQL Server and obtain an OBDC cursor
    :returns pyodbc.Cursor: MCD database cursor
    """

    pwd = get_config_item('GC', 'SQL_PW')
    connection = pyodbc.connect('Driver={SQL Server};'
                                'Server=OCS-VS-SQLT2PRD;'
                                'Database=mcd;'
                                'UID=DREGreader;'
                                f'PWD={pwd};')
    return connection.cursor()

    
def get_gc_files() -> None:
    cursor = get_cursor()
    sql = get_sql('GetRelatedENC')
    results = run_query(cursor, sql)
    columns = get_columns(cursor)
    for row in results:
        print(row)
    print(columns)
    # TODO GC files found: N:\MCD\NDB\DREG\2024\GC


def get_sql(file_name: str) -> str:
    """
    Retrieve SQL query in string format
    :returns str: Query string
    """

    sql_files = glob.glob(str(INPUTS / 'sql' / '*'))
    for file in sql_files:
        path = pathlib.Path(file)
        if path.stem == file_name:
            with open(path, 'r') as sql:
                return sql.read()   
    raise ENCReaderException(f'SQL file not found: {file_name}.sql')


def run_query(cursor, sql):
    cursor.execute(sql)
    return cursor.fetchall()


if __name__ == '__main__' :
    # get_gc_files()
    test_table_access()