import yaml
import pandas as pd
import pathlib


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'



def convert_to_yaml(df):
    with open(str(INPUTS / 'lookups' / 's57_lookup.yaml'), 'w') as writer:
        unique_acronyms_df = df.groupby('Acronym')
        for name, group in unique_acronyms_df:
            print(name)
            writer.write(f'{name}:\n')
            for i, row in group.iterrows():
                meaning = row['Meaning'].replace('"', '') if type(row['Meaning']) == str else str(row['Meaning']).replace('"', '')
                output_value = f'  {row["ID"]}: "{meaning}"\n'
                writer.write(output_value)
    with open(str(INPUTS / 'lookups' / 's57_lookup.yaml'), 'r+') as writer:
        print('Removing backslasshes')
        data = writer.read()
        writer.seek(0)
        output_data = data.replace('\\', '/')
        writer.write(output_data)
        writer.truncate()

def process():
    lookup_csv = str(INPUTS / 'lookups' / 's57_lookup.csv')
    lookup_df = pd.read_csv(lookup_csv)

    convert_to_yaml(lookup_df)


if __name__ == "__main__":
    process()