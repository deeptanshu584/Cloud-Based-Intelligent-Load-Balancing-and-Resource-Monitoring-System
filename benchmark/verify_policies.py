"""Exercise each policy against a running Docker Compose installation."""
import csv
import io
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
import requests

POLICIES = ('round_robin', 'static_weighted', 'least_connections', 'reactive', 'predictive')

def actual_proxy():
    command = ['docker','compose','exec','-T','controller','python','-c',
               "from controller.controller import runtime; print(runtime('show stat'))"]
    output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    reader = csv.DictReader(io.StringIO(output.lstrip('# ')))
    rows = list(reader)
    servers = {r['svname']: {'weight': int(r['weight']), 'status':r['status']} for r in rows if r.get('pxname')=='servers' and r.get('svname') in ('app1','app2','app3')}
    backend = next(r for r in rows if r.get('pxname')=='servers' and r.get('svname')=='BACKEND')
    return {'servers':servers, 'algorithm':backend['algo']}

def main():
    results=[]
    for policy in POLICIES:
        env={**os.environ,'POLICY':policy}
        subprocess.run(['docker','compose','up','--build','-d','--force-recreate','haproxy','controller'],env=env,check=True,stdout=subprocess.DEVNULL)
        time.sleep(8)
        if policy=='predictive':
            from benchmark.load_generator import run
            run('http://localhost:8080',20,12,'constant','mixed',42,Path('results/predictive_warmup.csv'))
        counts=Counter()
        for _ in range(60):
            response=requests.get('http://localhost:8080/health',timeout=5)
            response.raise_for_status()
            counts[response.json()['replica']]+=1
        status=requests.get('http://localhost:8081/status',timeout=5).json()
        proxy=actual_proxy()
        result={'policy':policy,'counts':dict(counts),'controller':status,'proxy':proxy}
        print(json.dumps(result),flush=True)
        assert len(counts)==3 and all(s['status']=='UP' for s in proxy['servers'].values())
        assert status['policy']==policy
        assert proxy['algorithm']==('leastconn' if policy=='least_connections' else 'roundrobin')
        results.append(result)
    Path('results/policy_verification.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__': main()
