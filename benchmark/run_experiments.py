import argparse
import csv
import os
import subprocess
import time
from pathlib import Path
import requests
from benchmark.load_generator import run
from benchmark.analyze_results import analyze

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--policies',nargs='+',default=['round_robin','static_weighted','least_connections','reactive','predictive'])
    p.add_argument('--repetitions',type=int,default=1); p.add_argument('--duration',type=float,default=15)
    p.add_argument('--warmup',type=float,default=10); p.add_argument('--rate',type=float,default=10)
    p.add_argument('--pattern',default='constant'); p.add_argument('--mix',default='mixed'); p.add_argument('--seed',type=int,default=42)
    p.add_argument('--output',default='results/experiment')
    a=p.parse_args(); output=Path(a.output); output.mkdir(parents=True,exist_ok=True); paths=[]
    for policy in a.policies:
        for repeat in range(a.repetitions):
            env={**os.environ,'POLICY':policy}
            subprocess.run(['docker','compose','up','-d','--force-recreate','haproxy','controller'],env=env,check=True)
            if a.warmup > 0:
                run('http://localhost:8080',a.warmup,a.rate,'constant',a.mix,a.seed+repeat,output/f'{policy}_{repeat}_warmup.csv')
            path=output/f'{policy}_{repeat}.csv'
            run('http://localhost:8080',a.duration,a.rate,a.pattern,a.mix,a.seed+repeat,path)
            paths.append(path)
            if policy == 'predictive':
                try:
                    status=requests.get('http://localhost:8081/status',timeout=2).json()
                    validation=status.get('forecast_validation')
                    if validation:
                        accuracy=output/'forecast_validation.csv'
                        with accuracy.open('a',newline='') as file:
                            writer=csv.DictWriter(file,fieldnames=['run','method','mae','rmse','samples'])
                            if file.tell()==0: writer.writeheader()
                            writer.writerow({'run':path.stem,'method':status.get('forecast_method','unknown'),**validation})
                except requests.RequestException:
                    pass
    analyze(paths,a.duration,output)

if __name__=='__main__': main()
