import uvicorn

def main():
    uvicorn.run("src.app.api:app", host="0.0.0.0", port=8000, reload=True, limit_max_requests=1000, timeout_keep_alive=60)