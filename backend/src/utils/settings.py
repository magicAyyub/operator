class Config:
    BASE_ROOT = "src/"
    UPLOAD_FOLDER = BASE_ROOT + "data/"
    PROCESSED_CSV = 'input.csv'

    # Dynamically determine the executable path based on platform
    EXECUTABLE_DIR = BASE_ROOT + "executables/"
    
    EXECUTABLE_NAME = "data_processor"
    # For Mac
    # EXECUTABLE_NAME = "data_processor_linux_arm"
    
    # Full path to the executable
    C_EXECUTABLE_PATH = EXECUTABLE_DIR + EXECUTABLE_NAME
    

# Allow requests from the frontend
ORIGINS = [
    'http://localhost:3000',
    "http://localhost:3000",
    "http://localhost:3000/api",
    "localhost:3000/api",
    "localhost:3000/",
    "http://localhost:8000",
    "http://localhost:8000/api",
]