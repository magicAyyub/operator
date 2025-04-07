from pathlib import Path

class Config:
    BASE_ROOT = Path.cwd() 
    UPLOAD_FOLDER = BASE_ROOT / "data/"
    PROCESSED_CSV = "processed_data.csv"
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    # if you are using windows, you can use the executable file
    # if you are using linux, you can use the C source code

    # C_EXECUTABLE_PATH = BASE_ROOT /"utils/data_processor"
    C_EXECUTABLE_PATH = BASE_ROOT / "utils/data_processor.exe"
    DETECTOR_FIRST_INPUT = BASE_ROOT / "app/utils/tmp/sample.csv"
    DETECTOR_SECOND_OUTPUT = BASE_ROOT / "app/utils/tmp/MAJNUM.csv"
    PROCESSED_CSV = 'combined_output.csv'