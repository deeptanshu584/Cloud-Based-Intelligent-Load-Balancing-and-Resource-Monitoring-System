"""Inject recoverable faults into a running Compose stack and record observations."""
import json
import subprocess
import time
from pathlib import Path
import requests

def compose(*args):
    subprocess.run(['docker','compose',*args],check=True,stdout=subprocess.DEVNULL)

def status():
    return requests.get('http://localhost:8081/status',timeout=3).json()

def route():
    response=requests.get('http://localhost:8080/health',timeout=3)
    response.raise_for_status()
    return response.json()['replica']

def until(predicate, timeout=30):
    start=time.monotonic()
    while time.monotonic()-start < timeout:
        try:
            if predicate(): return round(time.monotonic()-start,2)
        except requests.RequestException: pass
        time.sleep(.5)
    raise TimeoutError('condition not observed within '+str(timeout)+' seconds')

def main():
    observations={}
    try:
        compose('stop','app2')
        observations['backend_detection_seconds']=until(lambda: status()['weights']['app2']==0)
        observations['remaining_replicas']=sorted({route() for _ in range(30)})
        assert observations['remaining_replicas']==['app1','app3']
    finally:
        compose('start','app2')
    observations['backend_recovery_seconds']=until(lambda: status()['weights']['app2']>0)
    try:
        compose('stop','prometheus')
        observations['telemetry_fallback_seconds']=until(lambda: status()['mode']=='static_fallback',timeout=35)
        observations['fallback_weights']=status()['weights']
        observations['replica_during_telemetry_outage']=route()
    finally:
        compose('start','prometheus')
    observations['telemetry_recovery_seconds']=until(lambda: status()['mode'] in ('reactive','predictive'),timeout=35)
    try:
        compose('stop','controller')
        observations['replica_during_controller_outage']=route()
    finally:
        compose('start','controller')
    observations['controller_recovery_seconds']=until(lambda: status()['mode'] in ('reactive','predictive'),timeout=35)
    Path('results/fault_verification.json').write_text(json.dumps(observations,indent=2))
    print(json.dumps(observations,indent=2))

if __name__=='__main__': main()
