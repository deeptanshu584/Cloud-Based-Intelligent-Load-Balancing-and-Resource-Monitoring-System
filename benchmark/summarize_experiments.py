"""Print grouped descriptive statistics from completed benchmark summaries."""
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

for folder in map(Path, sys.argv[1:]):
    groups=defaultdict(list)
    with (folder/'summary.csv').open(newline='') as file:
        for row in csv.DictReader(file):
            groups[row['run'].rsplit('_',1)[0]].append(row)
    print(folder)
    for policy, rows in groups.items():
        print(policy, 'runs=',len(rows),
              'mean_p95_s=',round(statistics.mean(float(r['p95_seconds']) for r in rows),6),
              'mean_throughput_rps=',round(statistics.mean(float(r['throughput_rps']) for r in rows),3),
              'mean_error_rate=',round(statistics.mean(float(r['error_rate']) for r in rows),4))
