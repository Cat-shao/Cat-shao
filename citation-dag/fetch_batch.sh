#!/bin/bash

INPUT="/home/user/Cat-shao/citation-dag/todo_batch_1.txt"
TMPDIR="/home/user/Cat-shao/citation-dag/tmp_fetches"
mkdir -p "$TMPDIR"

mapfile -t IDS < <(sed 's/^[[:space:]]*//' "$INPUT" | grep -v '^$')

# Figure out which ones we need
TODO=()
for ID in "${IDS[@]}"; do
  FPATH="$TMPDIR/$ID.json"
  if [ -f "$FPATH" ]; then
    CONTENT=$(head -c 10 "$FPATH")
    if [ "$CONTENT" = "not_found" ]; then
      continue
    fi
    if echo "$CONTENT" | grep -q '"paperId"'; then
      continue
    fi
    # Invalid cached file, remove
    rm "$FPATH"
  fi
  TODO+=("$ID")
done

echo "Remaining: ${#TODO[@]}"
if [ ${#TODO[@]} -eq 0 ]; then
  echo "Done!"
  exit 0
fi

# Process in this run
COUNT=0
for ID in "${TODO[@]}"; do
  COUNT=$((COUNT+1))
  echo "[$COUNT/${#TODO[@]}] ARXIV:$ID"
  
  RETRY=0
  while [ $RETRY -lt 3 ]; do
    HTTP_CODE=$(curl -s -o "$TMPDIR/$ID.json" -w "%{http_code}" \
      "https://api.semanticscholar.org/graph/v1/paper/ARXIV:${ID}?fields=title,references.title,references.externalIds,references.year")
    
    if [ "$HTTP_CODE" = "200" ]; then
      echo "  OK"
      break
    elif [ "$HTTP_CODE" = "404" ]; then
      echo "  404"
      echo "not_found" > "$TMPDIR/$ID.json"
      break
    else
      RETRY=$((RETRY+1))
      echo "  HTTP $HTTP_CODE, retry $RETRY/3, wait 65s"
      sleep 65
    fi
  done
  
  if [ $RETRY -eq 3 ]; then
    echo "  FAILED"
    echo "not_found" > "$TMPDIR/$ID.json"
  fi
  
  sleep 4
done
echo "Batch complete."
