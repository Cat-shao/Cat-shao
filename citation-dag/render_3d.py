#!/usr/bin/env python3
"""
Render the citation DAG in 3D space using matplotlib with proper lighting.
Nodes = spheres, edges = lines, all with uniform optical properties.
"""
import json
import math
import random
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import time

t0 = time.time()

# ─── Load DAG ───────────────────────────────────────────────────────────
print("Loading DAG...", flush=True)
with open('papers.json') as f:
    papers = json.load(f)

in_degree = {}
for pid, p in papers.items():
    for ref in p.get('references', []):
        in_degree[ref] = in_degree.get(ref, 0) + 1

# Select: AttnRes 2-hop + high in-degree papers
root = "2603.15031"
included = {root}
for ref in papers[root].get('references', []):
    included.add(ref)
for ref in list(papers[root].get('references', [])):
    if ref in papers:
        for ref2 in papers[ref].get('references', []):
            if in_degree.get(ref2, 0) >= 8:
                included.add(ref2)
for pid in list(included):
    if pid in papers:
        for ref in papers[pid].get('references', []):
            if in_degree.get(ref, 0) >= 20:
                included.add(ref)

included = {pid for pid in included if pid in papers}

pid_list = list(included)
pid_index = {pid: i for i, pid in enumerate(pid_list)}
edges = []
for pid in included:
    for ref in papers[pid].get('references', []):
        if ref in included:
            edges.append((pid_index[pid], pid_index[ref]))

N = len(pid_list)
E = len(edges)
print(f"Selected {N} nodes, {E} edges", flush=True)

# ─── 3D Layout ──────────────────────────────────────────────────────────
print("Computing 3D force-directed layout...", flush=True)
np.random.seed(42)
pos = np.random.randn(N, 3).astype(np.float64) * 8.0

# Year-based Z initialization
for i, pid in enumerate(pid_list):
    year = papers[pid].get('year')
    if year:
        pos[i, 2] = (year - 2015) * 1.5
    pos[i, 2] += np.random.randn() * 0.2

# Force-directed with Barnes-Hut approximation
k = (200.0 / max(N, 1)) ** 0.33
temp = 8.0

for iteration in range(200):
    disp = np.zeros_like(pos)

    # Repulsive (sampled pairwise)
    sample = min(300, N)
    for i in range(N):
        idx = np.random.choice(N, size=sample, replace=False)
        delta = pos[i] - pos[idx]
        dist = np.linalg.norm(delta, axis=1, keepdims=True)
        dist = np.maximum(dist, 0.05)
        force = delta * (k * k / (dist * dist))
        disp[i] += np.sum(force, axis=0) / sample * N * 0.0008

    # Attractive (edges)
    for a, b in edges:
        delta = pos[a] - pos[b]
        dist = max(np.linalg.norm(delta), 0.05)
        f = delta * dist / k * 0.08
        disp[a] -= f
        disp[b] += f

    disp_norm = np.linalg.norm(disp, axis=1, keepdims=True)
    disp_norm = np.maximum(disp_norm, 0.001)
    pos += disp * np.minimum(temp / disp_norm, 1.0)
    temp *= 0.975

    if (iteration + 1) % 50 == 0:
        print(f"  Iteration {iteration+1}/200, temp={temp:.3f}", flush=True)

# Center & scale
pos -= pos.mean(axis=0)
maxr = np.max(np.linalg.norm(pos, axis=1))
pos = pos / maxr * 15.0
print(f"Layout done. {time.time()-t0:.1f}s", flush=True)

# ─── Render with matplotlib 3D ─────────────────────────────────────────
print("Rendering...", flush=True)

fig = plt.figure(figsize=(24, 13.5), dpi=120, facecolor='#08080F')
ax = fig.add_subplot(111, projection='3d', facecolor='#08080F')

# Draw edges
if E > 8000:
    edge_idx = random.sample(range(E), 8000)
    sampled_edges = [edges[i] for i in edge_idx]
else:
    sampled_edges = edges

lines = []
for a, b in sampled_edges:
    lines.append([pos[a], pos[b]])

lc = Line3DCollection(lines, colors=(0.25, 0.35, 0.55, 0.08), linewidths=0.3)
ax.add_collection(lc)

# Draw nodes
years = np.array([papers[pid].get('year', 2018) or 2018 for pid in pid_list], dtype=float)
degrees = np.array([in_degree.get(pid, 0) for pid in pid_list], dtype=float)

# Size by in-degree (log scale)
sizes = np.log1p(degrees) * 3 + 2

# Color by year
norm_years = (years - years.min()) / max(years.max() - years.min(), 1)

# Custom colormap: deep blue (old) -> teal -> gold -> red (new)
colors = np.zeros((N, 4))
for i in range(N):
    t = norm_years[i]
    if t < 0.33:
        s = t / 0.33
        colors[i] = [0.15*(1-s) + 0.1*s, 0.2*(1-s) + 0.6*s, 0.6*(1-s) + 0.7*s, 0.85]
    elif t < 0.66:
        s = (t - 0.33) / 0.33
        colors[i] = [0.1*(1-s) + 0.85*s, 0.6*(1-s) + 0.7*s, 0.7*(1-s) + 0.2*s, 0.85]
    else:
        s = (t - 0.66) / 0.34
        colors[i] = [0.85*(1-s) + 1.0*s, 0.7*(1-s) + 0.25*s, 0.2*(1-s) + 0.15*s, 0.85]

# Highlight root
root_idx = pid_index.get(root, 0)
colors[root_idx] = [1.0, 0.1, 0.1, 1.0]
sizes[root_idx] = 80

# Simulate lighting: brighter on one side
light_dir = np.array([0.5, -0.8, 0.5])
light_dir = light_dir / np.linalg.norm(light_dir)
# Use position relative to center as proxy for normal
normals = pos / (np.linalg.norm(pos, axis=1, keepdims=True) + 0.01)
lighting = np.dot(normals, light_dir)
lighting = 0.4 + 0.6 * np.clip(lighting, 0, 1)  # ambient + diffuse

# Apply lighting to colors
for i in range(N):
    colors[i, :3] *= lighting[i]
    colors[i, :3] = np.clip(colors[i, :3], 0, 1)

ax.scatter(pos[:, 0], pos[:, 1], pos[:, 2],
           s=sizes, c=colors, edgecolors='none', depthshade=True, alpha=0.9)

# Camera angle
ax.view_init(elev=20, azim=-60)
ax.set_xlim(-16, 16)
ax.set_ylim(-16, 16)
ax.set_zlim(-16, 16)

# Clean up axes
ax.set_axis_off()
ax.grid(False)
ax.xaxis.pane.fill = False
ax.yaxis.pane.fill = False
ax.zaxis.pane.fill = False

# Title
fig.text(0.5, 0.95, 'Citation DAG of Kimi AttnRes (arXiv:2603.15031)',
         ha='center', va='top', fontsize=16, color='white', fontweight='bold',
         fontfamily='sans-serif')
fig.text(0.5, 0.92, f'{N:,} papers · {E:,} edges · Recursive depth 4+',
         ha='center', va='top', fontsize=10, color='#88AACC',
         fontfamily='sans-serif')

# Legend
legend_items = [
    ('●', '#1A33AA', 'pre-2017'),
    ('●', '#1A99BB', '2017-2019'),
    ('●', '#DDBB33', '2020-2022'),
    ('●', '#FF4422', '2023-2026'),
    ('●', '#FF1111', 'AttnRes (root)'),
]
for i, (marker, color, label) in enumerate(legend_items):
    fig.text(0.02, 0.88 - i * 0.035, f'{marker} {label}', fontsize=9, color=color,
             fontfamily='sans-serif')

plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
plt.savefig('citation_dag_3d.png', dpi=120, facecolor='#08080F',
            bbox_inches='tight', pad_inches=0.1)
plt.close()

print(f"\nDone! Saved citation_dag_3d.png")
print(f"Total time: {time.time()-t0:.0f}s")
