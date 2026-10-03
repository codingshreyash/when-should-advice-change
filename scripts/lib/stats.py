"""Small statistics shared by the analysis scripts: d' z-scores, total-variation
distance between option distributions, and AUROC."""
import statistics

def z(p, n):
    # 0.5 correction so 0/n and n/n stay finite
    p = (p * n + 0.5) / (n + 1)
    return statistics.NormalDist().inv_cdf(p)

def tv(p, q):
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in keys)

def auroc(pos, neg):
    if not pos or not neg: return float("nan")
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))
