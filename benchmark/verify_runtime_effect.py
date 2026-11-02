"""Show that Runtime API weights alter client-visible distribution."""
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
import requests

def compose(*args):
    subprocess.run(['docker','compose',*args],check=True,stdout=subprocess.DEVNULL)

def sample():
    return dict(Counter(requests.get('http://localhost:8080/health',timeout=3).json()['replica'] for _ in range(60)))

def main():
    before=sample()
    compose('stop','controller')
    try:
        code="from controller.controller import runtime; [runtime(f'set server servers/{name} weight {weight}') for name,weight in [('app1',256),('app2',1),('app3',1)]]"
        compose('run','--rm','--no-deps','controller','python','-c',code)
        time.sleep(2)
        forced=sample()
    finally:
        compose('start','controller')
    time.sleep(5)
    restored=sample()
    result={'before':before,'forced':forced,'after_controller_restart':restored}
    assert forced.get('app1',0)>=55 and len(restored)>1
    Path('results/runtime_effect.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
