import argparse
import csv
import math
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def percentile(values, q):
    if len(values) < 20: return None
    values = sorted(values)
    pos = (len(values)-1)*q
    low = int(pos); high = min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(pos-low)

def summarize(rows, duration, slo=.5):
    status = [str(row['status']) for row in rows]
    success = [row for row in rows if str(row['status']).startswith('2')]
    latencies = [float(row['latency_seconds']) for row in success if row['latency_seconds'] != '']
    failures = [row for row in rows if row['failure']]
    counts = Counter(row['replica'] for row in success if row['replica'])
    n = len(rows)
    return {'offered_rps': n/duration, 'throughput_rps': len(success)/duration,
            'error_rate': (n-len(success))/n if n else 0,
            'timeout_rate': sum('Timeout' in row['failure'] for row in failures)/n if n else 0,
            'p50_seconds': percentile(latencies,.5), 'p95_seconds': percentile(latencies,.95),
            'p99_seconds': percentile(latencies,.99), 'slo_violation_rate': sum(v>slo for v in latencies)/len(latencies) if latencies else None,
            'replica_distribution': dict(counts), 'requests': n, 'successful': len(success),
            'percentiles_reliable': len(latencies)>=20}

def analyze(paths, duration, output, slo=.5):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for path in paths:
        with open(path,newline='') as file: rows=list(csv.DictReader(file))
        summary=summarize(rows,duration,slo); summary['run']=Path(path).stem
        summaries.append(summary)
    fields=[k for k in summaries[0] if k!='replica_distribution'] if summaries else []
    if summaries:
        for filename in ('summary.csv','policy_comparison.csv'):
            with (output/filename).open('w',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=fields); writer.writeheader(); writer.writerows({k:v for k,v in s.items() if k in fields} for s in summaries)
        names=[s['run'] for s in summaries]
        for key,label,filename in [('p95_seconds','p95 latency (seconds)','latency.png'),('throughput_rps','successful requests / second','throughput.png'),('error_rate','error rate','errors.png')]:
            fig,ax=plt.subplots(); ax.bar(names,[s[key] or 0 for s in summaries]); ax.set_ylabel(label); ax.tick_params(axis='x',rotation=30)
            fig.tight_layout(); fig.savefig(output/filename); plt.close(fig)
        replicas=sorted({r for s in summaries for r in s['replica_distribution']})
        fig,ax=plt.subplots(); bottom=[0]*len(names)
        for replica in replicas:
            values=[s['replica_distribution'].get(replica,0) for s in summaries]
            ax.bar(names,values,bottom=bottom,label=replica); bottom=[a+b for a,b in zip(bottom,values)]
        ax.set_ylabel('successful requests'); ax.legend(); fig.tight_layout(); fig.savefig(output/'distribution.png'); plt.close(fig)
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv',nargs='+'); p.add_argument('--duration',type=float,required=True)
    p.add_argument('--output',default='results/analysis'); p.add_argument('--slo',type=float,default=.5)
    a=p.parse_args(); analyze(a.csv,a.duration,a.output,a.slo)
