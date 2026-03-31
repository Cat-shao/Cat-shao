#!/usr/bin/env python3
"""Fetch references using Semantic Scholar BATCH API - much more efficient."""

import json
import time
import urllib.request
import urllib.error
import sys
import os
import random

DAG_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_FILE = os.path.join(DAG_DIR, "papers.json")
BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,references.title,references.externalIds,references.year"

HEADERS_LIST = [
    {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15'},
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0'},
]

def load_papers():
    with open(PAPERS_FILE) as f:
        return json.load(f)

def save_papers(papers):
    # Atomic write: write to temp file, then rename
    tmp_file = PAPERS_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(papers, f, ensure_ascii=False)
    os.replace(tmp_file, PAPERS_FILE)

def fetch_batch(arxiv_ids, max_retries=4):
    """Fetch up to 500 papers in one batch request."""
    ids = [f"ARXIV:{aid}" for aid in arxiv_ids]
    data = json.dumps({"ids": ids}).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(BATCH_URL, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            h = random.choice(HEADERS_LIST)
            for k, v in h.items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (2 ** attempt) * 10
                print(f"  Rate limited, waiting {wait}s (attempt {attempt+1})", flush=True)
                time.sleep(wait)
            else:
                print(f"  HTTP error {e.code}, waiting 5s", flush=True)
                time.sleep(5)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            time.sleep(5)
    return None

def process_batch_result(papers, arxiv_ids, results):
    """Process batch API results and update papers dict."""
    if results is None:
        return 0

    processed_count = 0
    for i, result in enumerate(results):
        if i >= len(arxiv_ids):
            break
        arxiv_id = arxiv_ids[i]

        if result is None:
            papers[arxiv_id]["processed"] = True
            continue

        ref_ids = []
        for ref in result.get("references", []) or []:
            ext_ids = ref.get("externalIds", {}) or {}
            ref_arxiv = ext_ids.get("ArXiv")
            ref_title = ref.get("title", "Unknown")
            ref_year = ref.get("year")

            if ref_arxiv:
                rid = ref_arxiv
            else:
                rid = "nonarxiv_" + ref_title[:60].replace(" ", "_").replace("/", "_").replace('"', '').replace("'", "")

            if rid not in papers:
                papers[rid] = {
                    "title": ref_title,
                    "year": ref_year,
                    "arxiv": ref_arxiv,
                    "processed": ref_arxiv is None,
                    "references": []
                }
            ref_ids.append(rid)

        papers[arxiv_id]["references"] = ref_ids
        papers[arxiv_id]["processed"] = True
        processed_count += 1

    return processed_count

def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 50  # papers per API call (max 500)
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    max_total = int(sys.argv[3]) if len(sys.argv) > 3 else 99999

    papers = load_papers()
    unprocessed = [pid for pid, p in papers.items() if not p["processed"] and p.get("arxiv")]
    print(f"Total unprocessed arxiv papers: {len(unprocessed)}", flush=True)

    to_process = unprocessed[:max_total]
    total_batches = (len(to_process) + batch_size - 1) // batch_size
    print(f"Processing {len(to_process)} papers in {total_batches} batches of {batch_size}", flush=True)

    total_processed = 0
    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(to_process))
        batch_ids = to_process[start:end]

        print(f"\n[Batch {batch_idx+1}/{total_batches}] Fetching {len(batch_ids)} papers...", flush=True)
        results = fetch_batch(batch_ids)

        if results:
            count = process_batch_result(papers, batch_ids, results)
            total_processed += count
            print(f"  Processed {count} papers (total: {total_processed})", flush=True)
        else:
            print(f"  FAILED batch {batch_idx+1}", flush=True)

        # Save checkpoint
        save_papers(papers)
        total = len(papers)
        processed = sum(1 for p in papers.values() if p["processed"])
        print(f"  Checkpoint: {total} papers, {processed} processed, {total-processed} unprocessed", flush=True)

        if batch_idx < total_batches - 1:
            time.sleep(delay)

    total = len(papers)
    processed = sum(1 for p in papers.values() if p["processed"])
    edges = sum(len(p["references"]) for p in papers.values())
    print(f"\nFinal: {total} papers, {processed} processed, {total-processed} unprocessed, {edges} edges", flush=True)

if __name__ == "__main__":
    main()
