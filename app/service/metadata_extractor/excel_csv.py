import pandas as pd
from .common import get_basic_metadata


# Function to extract metadata from Excel and CSV files
# This function reads the file, extracts basic metadata, and includes information specific to the file type like columns, rows, and sheet names for Excel files.

def extract_excel_or_csv_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        ext = file_path.split('.')[-1].lower()
        df = pd.read_excel(file_path) if ext in ['xlsx', 'xls'] else pd.read_csv(file_path)
        metadata.update({
            "type": "spreadsheet",
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata