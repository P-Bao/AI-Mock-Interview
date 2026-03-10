import subprocess
import time
import sys

def run_pipeline():
    print("Khởi động Pipeline: Phỏng vấn & Đánh giá...")
    # Port 8000: Audio Proxy
    p1 = subprocess.Popen([sys.executable, "-m", "uvicorn", "voice:app", "--port", "8000"])
    # Port 8001: Evaluation API
    p2 = subprocess.Popen([sys.executable, "-m", "uvicorn", "evaluation:app", "--port", "8001"])
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        p1.terminate()
        p2.terminate()
        print("\nPipeline stopped.")

if __name__ == "__main__":
    run_pipeline()