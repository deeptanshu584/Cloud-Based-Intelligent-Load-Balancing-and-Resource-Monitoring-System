# Experiment guide

1. **Smoke test:** one short run checks that routing, CSV output, and charts work. It is not statistically meaningful.
2. **Calibration:** measure each replica with the same workload and validate whether the 0.5:1:1.5 configured CPU allocation approximates real capacity. Keep the allocations fixed for the comparison.
3. **Final evaluation:** fix the SLO, request mix, offered rate, duration, and warm-up first. Use at least five repetitions per condition with the same seeds across policies. Compare reactive and predictive at equal capacity and workload; include all three native baselines. Report negative or inconclusive results too.

Client p99 is computed from all successful client requests, never from averaged backend p99 values. Include failed and dropped requests in error rates. Keep raw CSV, JSON config, per-run summary, and charts together. When forecast validation data are insufficient, mark accuracy unavailable.
