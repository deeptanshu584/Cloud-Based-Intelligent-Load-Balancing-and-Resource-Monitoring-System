"""Run a local backend and real client benchmark without Docker or HAProxy."""
import subprocess
import sys
import time
from pathlib import Path
import requests
from benchmark.load_generator import run
from benchmark.analyze_results import analyze

def main():
    process = subprocess.Popen([sys.executable, '-m', 'app.app'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                if requests.get('http://127.0.0.1:8000/health', timeout=1).ok: break
            except requests.RequestException: pass
            time.sleep(.2)
        else: raise RuntimeError('backend did not start')
        path=Path('results/local_smoke.csv')
        rows=run('http://127.0.0.1:8000',3,10,'constant','mixed',42,path)
        summary=analyze([path],3,'results/local_smoke_analysis')[0]
        if not rows or summary['successful']==0: raise RuntimeError('no successful requests')
        print(summary)
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill()

if __name__=='__main__': main()
