from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import time
import random

app = FastAPI()

# 1. JSON Processing Endpoint
@app.get("/")
def json_processing():
    # Simulate some CPU work to process data
    x = [i**2 for i in range(1000)]
    return JSONResponse(content={"status": "success", "message": "JSON Data Processed", "data_length": len(x)})

# 2. Async DB Endpoint
@app.get("/db")
async def async_db():
    # Simulate typical async database query latency (20ms - 80ms)
    delay = random.uniform(0.02, 0.08)
    await asyncio.sleep(delay)
    return {"status": "success", "message": f"DB operation complete after {delay:.3f}s"}

# To test static files, FastAPI handles it natively via StaticFiles middleware.
# (But to keep dependencies low, we can just return a large text payload mimicking a file if we want, or mount a static directory).
from fastapi.staticfiles import StaticFiles
import os

# Create dummy text file if it does not exist
if not os.path.exists("static/dummy.txt"):
    os.makedirs("static", exist_ok=True)
    with open("static/dummy.txt", "w") as f:
        f.write("A" * 50000) # 50 KB dummy file

app.mount("/static", StaticFiles(directory="static"), name="static")
