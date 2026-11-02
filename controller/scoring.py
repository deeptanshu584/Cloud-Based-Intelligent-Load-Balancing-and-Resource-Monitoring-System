import math

SIGNAL_COEFFICIENTS = {'cpu': .30, 'memory': .15, 'inflight': .25, 'latency': .30}

def clip(value):
    if value is None or not math.isfinite(value):
        return None
    return max(0.0, min(1.0, value))

def pressure(sample, cpu_limit=1, memory_limit=268435456, inflight_limit=20, latency_slo=.5):
    limits = {'cpu': cpu_limit, 'memory': memory_limit, 'inflight': inflight_limit, 'latency': latency_slo}
    normalized = {key: clip(sample.get(key) / limit) if sample.get(key) is not None and limit > 0 else None for key, limit in limits.items()}
    available = {k: v for k,v in normalized.items() if v is not None}
    if not available:
        return None
    total = sum(SIGNAL_COEFFICIENTS[k] for k in available)
    return sum(SIGNAL_COEFFICIENTS[k] * v for k,v in available.items()) / total

def preferences(samples, capacities, forecast=None, recent_rate=None, latency_slo=.5):
    result = {}
    for name, capacity in capacities.items():
        sample = samples.get(name)
        if not sample or not sample.get('healthy', False):
            result[name] = 0.0
            continue
        p = pressure(sample, cpu_limit=capacity, latency_slo=latency_slo)
        if p is None:
            result[name] = None
            continue
        if forecast is not None and recent_rate and recent_rate > 0:
            # Forecast demand amplifies existing pressure; it cannot invent spare capacity.
            p = clip(p * min(2.0, max(.5, forecast / recent_rate)))
        result[name] = max(0.01, capacity * (1-p))
    return result

def shares(preferences, capacities):
    if any(v is None for v in preferences.values()):
        preferences = {k: capacities[k] if v != 0 else 0 for k,v in preferences.items()}
    total = sum(v for v in preferences.values() if v > 0)
    return {k: max(0,v)/total if total else 0 for k,v in preferences.items()}

def bounded_weights(target, previous, step=.05, scale=256):
    # Clip share movement, then renormalize; native HAProxy health still gates routing.
    moved = {k: (0 if v == 0 else min(previous.get(k, 0)+step, max(previous.get(k, 0)-step, v))) for k,v in target.items()}
    total = sum(moved.values())
    if not total:
        return {k: 0 for k in moved}, moved
    actual = {k: v/total for k,v in moved.items()}
    return {k: max(1, round(scale*v)) if target[k] > 0 else 0 for k,v in actual.items()}, actual
