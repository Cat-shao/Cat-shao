#!/usr/bin/env python3
"""Render a clean layered DAG: AttnRes at top, references flowing downward."""
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import matplotlib.patheffects as pe
import time

t0 = time.time()

with open('papers.json') as f:
    papers = json.load(f)

in_degree = {}
for pid, p in papers.items():
    for ref in p.get('references', []):
        in_degree[ref] = in_degree.get(ref, 0) + 1

root = "2603.15031"

# Build layers by BFS depth from root
from collections import deque
depth = {root: 0}
queue = deque([root])
included = {root}
MAX_DEPTH = 3  # Keep it readable

while queue:
    pid = queue.popleft()
    if depth[pid] >= MAX_DEPTH:
        continue
    if pid not in papers:
        continue
    for ref in papers[pid].get('references', []):
        if ref not in depth and ref in papers:
            depth[ref] = depth[pid] + 1
            included.add(ref)
            queue.append(ref)

# Filter aggressively for readability
filtered = set()
filtered.add(root)
# Depth 1: all direct references
for ref in papers[root].get('references', []):
    if ref in papers:
        filtered.add(ref)
# Depth 2: only if cited >= 15 times in the full DAG
for pid in included:
    d = depth.get(pid, 99)
    if d == 2 and in_degree.get(pid, 0) >= 50:
        filtered.add(pid)
# Depth 3: only if cited >= 300 times
for pid in included:
    d = depth.get(pid, 99)
    if d == 3 and in_degree.get(pid, 0) >= 300:
        filtered.add(pid)
filtered = {pid for pid in filtered if pid in papers}

# Organize by layer
layers = {}
for pid in filtered:
    d = depth.get(pid, 3)
    if d not in layers:
        layers[d] = []
    layers[d].append(pid)

# Sort each layer by year
for d in layers:
    layers[d].sort(key=lambda pid: papers[pid].get('year', 2020) or 2020)

print(f"Layers: {', '.join(f'depth {d}: {len(v)} papers' for d, v in sorted(layers.items()))}")
print(f"Total: {len(filtered)} papers")

# Assign positions
pos = {}
layer_y = {0: 0, 1: -4, 2: -9, 3: -15}
for d, pids in layers.items():
    n = len(pids)
    y = layer_y.get(d, -4 * d)
    # Spread horizontally
    width = max(n * 1.2, 10)
    for i, pid in enumerate(pids):
        x = (i - n/2) * (width/n)
        pos[pid] = (x, y)

# Collect edges
edges = []
for pid in filtered:
    if pid in papers:
        for ref in papers[pid].get('references', []):
            if ref in filtered:
                edges.append((pid, ref))

print(f"Edges: {len(edges)}")

# ─── Render ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(36, 24), dpi=100, facecolor='#0c0c18')
ax.set_facecolor('#0c0c18')

era_colors = {
    (2025, 2030): '#ff4433',
    (2023, 2024): '#ff9944',
    (2021, 2022): '#ddcc33',
    (2019, 2020): '#44cc55',
    (2017, 2018): '#4488ee',
    (2015, 2016): '#9966dd',
    (0, 2014): '#888899',
}

def get_color(year):
    if year is None: return '#666677'
    for (lo, hi), c in era_colors.items():
        if lo <= year <= hi: return c
    return '#666677'

# Draw edges
for src, tgt in edges:
    if src in pos and tgt in pos:
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        ax.plot([x0, x1], [y0, y1], color='#2a3555', alpha=0.12, linewidth=0.4, zorder=1)

# Draw nodes
for pid in filtered:
    if pid not in pos:
        continue
    x, y = pos[pid]
    p = papers[pid]
    year = p.get('year')
    deg = in_degree.get(pid, 0)
    color = get_color(year)

    # Size by in-degree
    size = 15 + min(deg, 500) * 0.15
    if pid == root:
        size = 60
        color = '#ff1111'

    ax.scatter(x, y, s=size, c=color, edgecolors='white', linewidths=0.3,
              alpha=0.9, zorder=3)

    # Labels for important nodes
    d = depth.get(pid, 99)
    show_label = (pid == root or
                  d == 1 or
                  (d == 2 and deg >= 20) or
                  (d == 3 and deg >= 80))

    if show_label:
        title = p['title']
        if len(title) > 45:
            title = title[:43] + '...'
        label = f"{title}\n({year or '?'})"
        fontsize = 5.5
        if pid == root:
            fontsize = 9
        elif d <= 1:
            fontsize = 6.5
        elif deg >= 100:
            fontsize = 6

        ax.annotate(label, (x, y), xytext=(0, -8 if d > 0 else 12),
                   textcoords='offset points', fontsize=fontsize,
                   color='#ccccdd', ha='center', va='top' if d > 0 else 'bottom',
                   fontfamily='sans-serif',
                   path_effects=[pe.withStroke(linewidth=2, foreground='#0c0c18')])

# Layer labels
for d in sorted(layers.keys()):
    y = layer_y.get(d, -4*d)
    labels = {0: 'AttnRes (root)', 1: 'Direct References (depth 1)',
              2: 'Depth 2 (cited ≥3x)', 3: 'Depth 3 (cited ≥3x)'}
    ax.text(-max(len(layers[d])*0.6, 5) - 3, y, labels.get(d, f'Depth {d}'),
           fontsize=10, color='#556688', fontfamily='sans-serif', va='center', ha='right',
           style='italic')

# Title
fig.text(0.5, 0.97, 'Citation DAG of Kimi AttnRes (arXiv:2603.15031)',
         ha='center', fontsize=22, color='#e8d0a0', fontweight='bold', fontfamily='sans-serif')
fig.text(0.5, 0.945, f'{len(filtered)} key papers · {len(edges)} edges · Color = publication year',
         ha='center', fontsize=12, color='#667799', fontfamily='sans-serif')

ax.set_xlim(ax.get_xlim()[0]-5, ax.get_xlim()[1]+5)
ax.margins(0.05)
ax.axis('off')
plt.tight_layout(pad=2)
plt.savefig('citation_dag_layered.png', dpi=100, facecolor='#0c0c18', bbox_inches='tight')
plt.close()

print(f"Done! Saved citation_dag_layered.png ({time.time()-t0:.1f}s)")
