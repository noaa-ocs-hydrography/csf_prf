import os
import sqlite3
import datetime
import pathlib
import time
CSFPRF_MODULE = pathlib.Path(__file__).parents[2]

import sys
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.helpers.tools import Param
from csf_prf.engines.S57ConversionEngine import S57ConversionEngine


INPUTS = pathlib.Path(__file__).parents[3] / "inputs"
OUTPUTS = pathlib.Path(__file__).parents[3] / "outputs"


def create_table(cursor):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS old_surveys
             (date text, filename text, path text, success integer)"""
    )


def get_logging_db():
    log_folder = INPUTS / 'log'
    log_folder.mkdir(parents=True, exist_ok=True)
    db_connection = sqlite3.connect(log_folder / 'fff_conversion.db')
    create_table(db_connection.cursor())
    return db_connection


def log_status(db_conn, filename, path, success):
    cursor = db_conn.cursor()
    now = datetime.datetime.now()
    date = f'{now.year}-{now.month}-{now.day}'
    cursor.execute(f"INSERT INTO old_surveys VALUES ('{date}', '{filename}', '{path}', {success})")
    db_conn.commit()


def processed_survey(db_conn, filename):
    cursor = db_conn.cursor()
    # TODO this only returns the first result if more than 1 row for filename
    results = cursor.execute(f"SELECT * FROM old_surveys WHERE filename = '{filename}';")
    db_conn.commit()
    processed = results.fetchone()
    if processed and len(processed) > 0:
        if processed[-1] == 1:
            return True
        else:
            return False
    return False


def previous_failure(db_conn, filename):
    cursor = db_conn.cursor()
    results = cursor.execute(f"SELECT * FROM old_surveys WHERE filename = '{filename}';")
    db_conn.commit()
    processed = results.fetchone()
    if processed and len(processed) > 0:
        if processed[-1] == 0:
            return True
        else:
            return False


def update_status(db_conn, filename, path, success):
    cursor = db_conn.cursor()
    now = datetime.datetime.now()
    date = f'{now.year}-{now.month}-{now.day}'
    cursor.execute(f"UPDATE old_surveys SET date = '{date}', path = '{path}', success = 1 WHERE filename = '{filename}'")
    db_conn.commit()


def process():
    # new path: N:\HSD\Projects\SurveyDatabase\Churn\Surveys
    search_path = pathlib.Path(r'N:\HSD\Projects\SurveyDatabase\Churn\Surveys')
    old_surveys = list(search_path.rglob('*FFF.000'))
    print('len:', len(old_surveys))
    db_conn = get_logging_db()
    run_times = []
    for i, survey in enumerate(old_surveys):
        start = time.time()
        filename = survey.name
        output = survey.parents[0]
        if not processed_survey(db_conn, filename):
            try:
                param_lookup = {
                    "enc_file": Param(str(survey)),
                    "output_folder": Param(str(output)),        
                    "layerfile_export": Param(False),
                    "toggle_crs": Param(False)
                }
                engine = S57ConversionEngine(param_lookup)
                engine.start()
                print(f'{i} completed - {survey}')
                # TODO update record if previously 0
                # if record was found but success was 0, call update_status()
                if previous_failure(db_conn, filename):
                    update_status(db_conn, filename, survey, 1)
                else:
                    log_status(db_conn, filename, survey, 1)
            except Exception as e:
                print(f'{i} failed - {survey}\n{e}')
                # all seem to fail for: Cannot find field '$SCALE'
                output_gpkg = str(output / survey.stem) + 'gpkg'
                if os.path.isfile(output_gpkg):
                    os.remove(output_gpkg)
                if not previous_failure(db_conn, filename):
                    log_status(db_conn, filename, survey, 0)
                pass
        else:
            print(f'{i} skipping - {survey}')
        end = time.time()
        run_times.append(end - start)
        
    db_conn.close()
    print('Average runtime:', sum(run_times) / len(run_times))  # first 100 - 38 seconds


if __name__ == "__main__":
    process()
