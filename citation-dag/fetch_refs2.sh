#!/bin/bash
set -e

INPUT="/home/user/Cat-shao/citation-dag/todo_batch_1.txt"
TMPDIR="/home/user/Cat-shao/citation-dag/tmp_fetches"
mkdir -p "$TMPDIR"

# Read IDs into array
mapfile -t IDS < <(sed 's/^[[:space:]]*//' "$INPUT" | grep -v '^$')

# Figure out which ones we already fetched successfully
TODO=()
for ID in "${IDS[@]}"; do
  FPATH="$TMPDIR/$ID.json"
  if [ -f "$FPATH" ]; then
    CONTENT=$(cat "$FPATH")
    if [ "$CONTENT" = "not_found" ]; then
      # Already marked not_found, skip
      continue
    fi
    # Check if valid JSON with title
    if python3 -c "import json; d=json.loads(open('$FPATH').read()); assert 'title' in d" 2>/dev/null; then
      continue
    fi
  fi
  TODO+=("$ID")
done

echo "Already fetched: $((${#IDS[@]} - ${#TODO[@]}))"
echo "Remaining to fetch: ${#TODO[@]}"

if [ ${#TODO[@]} -eq 0 ]; then
  echo "Nothing to do!"
  exit 0
fi

echo "Waiting 10 seconds before starting..."
sleep 10

for i in "${!TODO[@]}"; do
  ID="${TODO[$i]}"
  IDX=$((i+1))
  echo "[$IDX/${#TODO[@]}] Fetching ARXIV:$ID ..."
  
  RETRY=0
  MAX_RETRY=3
  SUCCESS=0
  
  while [ $RETRY -lt $MAX_RETRY ]; do
    HTTP_CODE=$(curl -s -o "$TMPDIR/$ID.json" -w "%{http_code}" \
      "https://api.semanticscholar.org/graph/v1/paper/ARXIV:${ID}?fields=title,references.title,references.externalIds,references.year")
    
    if [ "$HTTP_CODE" = "200" ]; then
      echo "  -> OK"
      SUCCESS=1
      break
    elif [ "$HTTP_CODE" = "404" ]; then
      echo "  -> 404 Not Found"
      echo "not_found" > "$TMPDIR/$ID.json"
      SUCCESS=2
      break
    elif [ "$HTTP_CODE" = "429" ]; then
      RETRY=$((RETRY+1))
      echo "  -> 429 Rate limited. Retry $RETRY/$MAX_RETRY. Waiting 60s..."
      sleep 60
    else
      echo "  -> HTTP $HTTP_CODE. Retry $((RETRY+1))/$MAX_RETRY. Waiting 60s..."
      RETRY=$((RETRY+1))
      sleep 60
    fi
  done
  
  if [ $SUCCESS -eq 0 ]; then
    echo "  -> FAILED after $MAX_RETRY retries, marking as not_found"
    echo "not_found" > "$TMPDIR/$ID.json"
  fi
  
  # Wait between requests - longer delay to avoid rate limits
  if [ $IDX -lt ${#TODO[@]} ]; then
    sleep 5
  fi
done

echo "All fetches complete."
