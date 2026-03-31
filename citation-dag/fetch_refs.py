#!/usr/bin/env python3
"""Fetch references for unprocessed papers from Semantic Scholar API."""

import json
import time
import urllib.request
import urllib.error
import sys
import os

DAG_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_FILE = os.path.join(DAG_DIR, "papers.json")
BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/ARXIV:{}?fields=title,references.title,references.externalIds,references.year"

def load_papers():
    with open(PAPERS_FILE) as f:
        return json.load(f)

def save_papers(papers):
    with open(PAPERS_FILE, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

def fetch_paper_refs(arxiv_id, max_retries=4):
    url = BASE_URL.format(arxiv_id)
    import random
    headers_list = [
        {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
         'Accept': 'application/json, text/plain, */*',
         'Accept-Language': 'en-US,en;q=0.9',
         'Referer': 'https://www.semanticscholar.org/',
         'Origin': 'https://www.semanticscholar.org',
         'Connection': 'keep-alive'},
        {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
         'Accept': 'application/json',
         'Accept-Language': 'en-US,en;q=0.8',
         'Referer': 'https://www.semanticscholar.org/'},
        {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
         'Accept': 'application/json, text/plain, */*',
         'Accept-Language': 'en-US,en;q=0.5',
         'Referer': 'https://www.semanticscholar.org/'},
    ]
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            h = random.choice(headers_list)
            for k, v in h.items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                refs = []
                for ref in data.get("references", []):
                    ext_ids = ref.get("externalIds", {}) or {}
                    refs.append({
                        "arxiv": ext_ids.get("ArXiv"),
                        "title": ref.get("title", "Unknown"),
                        "year": ref.get("year")
                    })
                return {"title": data.get("title", "Unknown"), "references": refs}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (2 ** attempt) * 5
                print(f"  Rate limited on {arxiv_id}, waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
            elif e.code == 404:
                print(f"  Not found: {arxiv_id}")
                return None
            else:
                print(f"  HTTP error {e.code} for {arxiv_id}")
                time.sleep(2)
        except Exception as e:
            print(f"  Error fetching {arxiv_id}: {e}")
            time.sleep(2)
    return None

def add_refs_to_papers(papers, arxiv_id, data):
    if data is None:
        papers[arxiv_id]["processed"] = True
        return

    ref_ids = []
    for ref in data.get("references", []):
        ref_arxiv = ref.get("arxiv")
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
                "processed": ref_arxiv is None,  # non-arxiv are leaf nodes
                "references": []
            }
        ref_ids.append(rid)

    papers[arxiv_id]["references"] = ref_ids
    papers[arxiv_id]["processed"] = True

def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5

    papers = load_papers()

    unprocessed = [pid for pid, p in papers.items() if not p["processed"] and p.get("arxiv")]
    print(f"Total unprocessed arxiv papers: {len(unprocessed)}")

    to_process = unprocessed[:batch_size]
    print(f"Processing {len(to_process)} papers with {delay}s delay")

    for i, arxiv_id in enumerate(to_process):
        print(f"[{i+1}/{len(to_process)}] Fetching {arxiv_id}: {papers[arxiv_id]['title'][:60]}")
        data = fetch_paper_refs(arxiv_id)
        add_refs_to_papers(papers, arxiv_id, data)

        # Save periodically
        if (i + 1) % 20 == 0:
            save_papers(papers)
            total = len(papers)
            processed = sum(1 for p in papers.values() if p["processed"])
            print(f"  === Checkpoint: {total} papers, {processed} processed, {total-processed} remaining ===")

        time.sleep(delay)

    save_papers(papers)
    total = len(papers)
    processed = sum(1 for p in papers.values() if p["processed"])
    edges = sum(len(p["references"]) for p in papers.values())
    print(f"\nFinal: {total} papers, {processed} processed, {total-processed} unprocessed, {edges} edges")

if __name__ == "__main__":
    main()
