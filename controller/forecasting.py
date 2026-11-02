import math
from statistics import mean

def persistence(history):
    values = [v for v in history if math.isfinite(v) and v >= 0]
    return values[-1] if values else None

def ewma(history, alpha=.4):
    if not 0 < alpha <= 1:
        raise ValueError('alpha must be in (0,1]')
    values = [v for v in history if math.isfinite(v) and v >= 0]
    if not values:
        return None
    estimate = values[0]
    for value in values[1:]:
        estimate = alpha * value + (1-alpha) * estimate
    return estimate

def evaluate(series, minimum=3, horizon=1):
    """Walk forward; each forecast uses only observations before its target."""
    out = {}
    for name, fn in [('persistence', persistence), ('ewma', ewma)]:
        errors = [fn(series[:i])-series[i+horizon-1] for i in range(minimum, len(series)-horizon+1)]
        out[name] = {'mae': mean(abs(e) for e in errors), 'rmse': math.sqrt(mean(e*e for e in errors)), 'samples': len(errors)} if errors else None
    return out
