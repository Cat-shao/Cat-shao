#!/usr/bin/env python3
"""Radial DAG: AttnRes at center, refs in concentric rings, all labeled."""
import json, math, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from collections import deque

with open('papers.json') as f:
    papers = json.load(f)

in_degree = {}
for pid, p in papers.items():
    for ref in p.get('references', []):
        in_degree[ref] = in_degree.get(ref, 0) + 1

root = "2603.15031"

# BFS from root, keeping only manageable count per depth
depth = {root: 0}
queue = deque([root])
layers = {0: [root]}

while queue:
    pid = queue.popleft()
    d = depth[pid]
    if d >= 3: continue
    if pid not in papers: continue
    for ref in papers[pid].get('references', []):
        if ref not in depth and ref in papers:
            depth[ref] = d + 1
            if d + 1 not in layers: layers[d+1] = []
            layers[d+1].append(ref)
            queue.append(ref)

# Filter each layer for readability
final = {0: layers[0]}  # root
final[1] = layers.get(1, [])  # all 68 direct refs
# Depth 2: top 80 by in-degree
d2 = sorted(layers.get(2, []), key=lambda p: -in_degree.get(p, 0))[:80]
final[2] = d2
# Depth 3: top 40 by in-degree
d3 = sorted(layers.get(3, []), key=lambda p: -in_degree.get(p, 0))[:40]
final[3] = d3

all_pids = set()
for d, pids in final.items():
    all_pids.update(pids)

print(f"Nodes: {len(all_pids)} (d0={len(final[0])}, d1={len(final[1])}, d2={len(final[2])}, d3={len(final[3])})")

# Edges between included nodes
edges = []
for pid in all_pids:
    if pid in papers:
        for ref in papers[pid].get('references', []):
            if ref in all_pids:
                edges.append((pid, ref))
print(f"Edges: {len(edges)}")

# Radial positions
pos = {}
radii = {0: 0, 1: 8, 2: 18, 3: 27}

for d, pids in final.items():
    r = radii[d]
    n = len(pids)
    if d == 0:
        pos[pids[0]] = (0, 0)
    else:
        for i, pid in enumerate(pids):
            angle = 2 * math.pi * i / n - math.pi/2
            pos[pid] = (r * math.cos(angle), r * math.sin(angle))

# ─── Render ──────────────────────────────────────
fig, ax = plt.subplots(figsize=(40, 40), dpi=80, facecolor='#0b0b16')
ax.set_facecolor('#0b0b16')

# Concentric ring guides
for d, r in radii.items():
    if r > 0:
        circle = plt.Circle((0, 0), r, fill=False, color='#1a1a2e', linewidth=0.5, linestyle='--')
        ax.add_patch(circle)

# Draw edges
for src, tgt in edges:
    if src in pos and tgt in pos:
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        # Curved edges using quadratic bezier
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-", color='#2a3555', alpha=0.08,
                                    connectionstyle="arc3,rad=0.1", lw=0.4))

# Color scheme
def get_color(year):
    if year is None: return '#666677'
    if year >= 2025: return '#ff3322'
    if year >= 2023: return '#ff8844'
    if year >= 2021: return '#ddcc33'
    if year >= 2019: return '#44cc55'
    if year >= 2017: return '#4488ee'
    if year >= 2015: return '#9966dd'
    return '#888899'

# Draw nodes and labels
for pid in all_pids:
    if pid not in pos: continue
    x, y = pos[pid]
    p = papers[pid]
    year = p.get('year')
    deg = in_degree.get(pid, 0)
    d = depth[pid]
    color = get_color(year)

    # Node size
    if pid == root:
        size = 200
        color = '#ff1111'
    elif d == 1:
        size = 40 + min(deg, 200) * 0.3
    else:
        size = 20 + min(deg, 500) * 0.08

    ax.scatter(x, y, s=size, c=color, edgecolors='white', linewidths=0.4,
              alpha=0.9, zorder=5)

    # Labels
    title = p['title']
    if len(title) > 38:
        title = title[:36] + '..'

    if pid == root:
        fontsize = 10
        label = f"AttnRes\n(2026)"
    elif d == 1:
        fontsize = 5.5
        label = f"{title}\n({year or '?'})"
    elif d == 2 and deg >= 80:
        fontsize = 5
        label = f"{title}\n({year or '?'}) [{deg}]"
    elif d == 2:
        fontsize = 4.2
        label = f"{title[:30]}\n({year or '?'})"
    else:
        fontsize = 3.8
        label = f"{title[:25]} ({year or '?'})"

    # Label position: radially outward
    r = math.sqrt(x*x + y*y)
    if r > 0.1:
        angle = math.atan2(y, x)
        offset = 0.8 + fontsize * 0.15
        lx = x + offset * math.cos(angle)
        ly = y + offset * math.sin(angle)
        ha = 'left' if math.cos(angle) > 0.1 else ('right' if math.cos(angle) < -0.1 else 'center')
        rotation = math.degrees(angle)
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
    else:
        lx, ly = x, y + 1.5
        ha = 'center'
        rotation = 0

    ax.text(lx, ly, label, fontsize=fontsize, color='#bbc0cc', ha=ha, va='center',
           rotation=rotation, rotation_mode='anchor', fontfamily='sans-serif',
           path_effects=[pe.withStroke(linewidth=1.5, foreground='#0b0b16')])

# Ring labels
for d, r in radii.items():
    if r > 0:
        labels = {1: 'Direct References', 2: 'Depth 2 (top 80 by citation)',
                  3: 'Depth 3 (top 40 by citation)'}
        ax.text(0, r + 1.2, labels.get(d, ''), fontsize=8, color='#445566',
               ha='center', va='bottom', style='italic', fontfamily='sans-serif')

# Title
fig.text(0.5, 0.96, 'Citation DAG of Kimi AttnRes (arXiv:2603.15031)',
         ha='center', fontsize=24, color='#e8d0a0', fontweight='bold', fontfamily='sans-serif')
fig.text(0.5, 0.94, f'{len(all_pids)} key papers · {len(edges)} edges · Radial layout by citation depth',
         ha='center', fontsize=13, color='#667799', fontfamily='sans-serif')

ax.set_xlim(-32, 32)
ax.set_ylim(-32, 32)
ax.set_aspect('equal')
ax.axis('off')
plt.tight_layout(pad=1)
plt.savefig('citation_dag_radial.png', dpi=80, facecolor='#0b0b16', bbox_inches='tight')
plt.close()
print("Done! Saved citation_dag_radial.png")
