#!/usr/bin/env python3
"""Merge batch result files into papers.json and generate Graphviz DOT."""

import json
import glob
import os
import sys

DAG_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_FILE = os.path.join(DAG_DIR, "papers.json")

def load_papers():
    with open(PAPERS_FILE) as f:
        return json.load(f)

def save_papers(papers):
    with open(PAPERS_FILE, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

def merge_batch(papers, batch_file):
    """Merge a batch result file into the papers dict."""
    with open(batch_file) as f:
        batch = json.load(f)

    for arxiv_id, data in batch.items():
        if data == "not_found":
            if arxiv_id in papers:
                papers[arxiv_id]["processed"] = True
            continue

        ref_ids = []
        for ref in data.get("references", []):
            ref_arxiv = ref.get("arxiv")
            ref_title = ref.get("title", "Unknown")
            ref_year = ref.get("year")

            if ref_arxiv:
                rid = ref_arxiv
            else:
                # Use a sanitized title as ID for non-arxiv papers
                rid = "nonarxiv_" + ref_title[:60].replace(" ", "_").replace("/", "_").replace('"', '')

            # Add to papers dict if not present
            if rid not in papers:
                papers[rid] = {
                    "title": ref_title,
                    "year": ref_year,
                    "arxiv": ref_arxiv,
                    "processed": False,
                    "references": []
                }
            ref_ids.append(rid)

        if arxiv_id in papers:
            papers[arxiv_id]["references"] = ref_ids
            papers[arxiv_id]["processed"] = True
        else:
            papers[arxiv_id] = {
                "title": data.get("title", "Unknown"),
                "year": None,
                "arxiv": arxiv_id,
                "processed": True,
                "references": ref_ids
            }

    return papers

def stats(papers):
    total = len(papers)
    processed = sum(1 for p in papers.values() if p["processed"])
    unprocessed = total - processed
    edges = sum(len(p["references"]) for p in papers.values())
    print(f"Total papers: {total}")
    print(f"Processed: {processed}")
    print(f"Unprocessed: {unprocessed}")
    print(f"Total edges: {edges}")
    return unprocessed

def get_unprocessed(papers, limit=None):
    """Get list of unprocessed arxiv paper IDs."""
    result = []
    for pid, p in papers.items():
        if not p["processed"] and p.get("arxiv"):
            result.append(pid)
    if limit:
        result = result[:limit]
    return result

def generate_dot(papers, output_file=None):
    """Generate Graphviz DOT file."""
    if output_file is None:
        output_file = os.path.join(DAG_DIR, "citation_dag.dot")

    lines = []
    lines.append("digraph CitationDAG {")
    lines.append('  rankdir=BT;')  # Bottom to top (older papers at bottom)
    lines.append('  node [shape=box, style=filled, fillcolor=lightyellow, fontsize=8, width=0, height=0, margin="0.05,0.02"];')
    lines.append('  edge [arrowsize=0.5, color=gray60];')
    lines.append("")

    # Color coding by era
    era_colors = {
        (2025, 2030): "lightcoral",
        (2023, 2024): "lightsalmon",
        (2021, 2022): "khaki",
        (2019, 2020): "palegreen",
        (2017, 2018): "lightblue",
        (2015, 2016): "plum",
        (0, 2014): "lightgray",
    }

    def get_color(year):
        if year is None:
            return "white"
        for (lo, hi), color in era_colors.items():
            if lo <= year <= hi:
                return color
        return "white"

    def sanitize_id(pid):
        return pid.replace(".", "_").replace("-", "_").replace(":", "_")

    # Nodes
    for pid, p in papers.items():
        sid = sanitize_id(pid)
        title = p["title"][:50].replace('"', '\\"')
        year = p.get("year", "?")
        color = get_color(p.get("year"))
        label = f"{title}\\n({year})"
        lines.append(f'  {sid} [label="{label}", fillcolor={color}];')

    lines.append("")

    # Edges: paper -> reference (paper cites reference)
    for pid, p in papers.items():
        sid = sanitize_id(pid)
        for ref_id in p.get("references", []):
            if ref_id in papers:
                rid = sanitize_id(ref_id)
                lines.append(f'  {sid} -> {rid};')

    lines.append("}")

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    print(f"DOT file written to {output_file}")
    print(f"Nodes: {len(papers)}, Edges: {sum(len(p.get('references', [])) for p in papers.values())}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "merge":
        papers = load_papers()
        for batch_file in sys.argv[2:]:
            print(f"Merging {batch_file}...")
            papers = merge_batch(papers, batch_file)
        save_papers(papers)
        stats(papers)

    elif cmd == "stats":
        papers = load_papers()
        stats(papers)

    elif cmd == "unprocessed":
        papers = load_papers()
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        for pid in get_unprocessed(papers, limit):
            print(f"{pid}: {papers[pid]['title']}")

    elif cmd == "dot":
        papers = load_papers()
        generate_dot(papers)

    elif cmd == "mark_leaf":
        # Mark papers older than a given year as processed (leaf nodes)
        papers = load_papers()
        cutoff_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2014
        count = 0
        for pid, p in papers.items():
            if not p["processed"] and p.get("year") and p["year"] <= cutoff_year:
                p["processed"] = True
                count += 1
        save_papers(papers)
        print(f"Marked {count} papers as leaf nodes (year <= {cutoff_year})")
        stats(papers)

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python merge_and_generate.py [stats|merge <files...>|unprocessed [limit]|dot|mark_leaf [year]]")
