import pandas as pd
import io


def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(file_bytes))


def parse_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes))


def parse_file(filename: str, file_bytes: bytes) -> pd.DataFrame:
    if filename.endswith(".csv"):
        return parse_csv(file_bytes)
    elif filename.endswith((".xls", ".xlsx")):
        return parse_excel(file_bytes)
    raise ValueError(f"Unsupported file type: {filename}")
