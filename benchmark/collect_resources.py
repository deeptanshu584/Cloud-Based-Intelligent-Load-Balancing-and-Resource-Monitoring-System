"""Join observed Prometheus process resource samples to benchmark runs."""
import argparse
import csv
import statistics
from pathlib import Path
import requests

ALLOCATIONS={'app1:8000':.5,'app2:8000':1.0,'app3:8000':1.5}

def collect(folder, duration, base='http://localhost:9090'):
    folder=Path(folder)
    output=[]
    for path in sorted(folder.glob('*.csv')):
        if path.stem.endswith('_warmup') or path.stem in ('summary','policy_comparison','forecast_validation','resource_summary'): continue
        with path.open(newline='') as file: rows=list(csv.DictReader(file))
        if not rows: continue
        start=min(float(r['scheduled_time']) for r in rows)
        end=start+duration
        for metric,expr in [('cpu','rate(process_cpu_seconds_total{job="backends"}[30s])'),('memory','process_resident_memory_bytes{job="backends"}')]:
            response=requests.get(base+'/api/v1/query_range',params={'query':expr,'start':start,'end':end,'step':5},timeout=10)
            response.raise_for_status()
            for series in response.json()['data']['result']:
                instance=series['metric'].get('instance')
                if instance not in ALLOCATIONS: continue
                values=[float(value) for _,value in series['values'] if value not in ('NaN','+Inf','-Inf')]
                if values:
                    divisor=ALLOCATIONS[instance] if metric=='cpu' else 268435456
                    output.append({'run':path.stem,'instance':instance,'metric':metric+'_fraction_of_allocation','mean':statistics.mean(values)/divisor,'max':max(values)/divisor,'samples':len(values)})
    if output:
        with (folder/'resource_summary.csv').open('w',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=output[0]); writer.writeheader(); writer.writerows(output)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('folder'); p.add_argument('--duration',type=float,required=True)
    a=p.parse_args(); print('resource series:',len(collect(a.folder,a.duration)))
