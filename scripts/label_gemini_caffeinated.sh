#!/usr/bin/env bash
# Keep the Mac awake for the whole Gemini labelling run, including crash retries.
set -u
cd /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation
while true; do
  if caffeinate -is env PYTHONUNBUFFERED=1 .venv/bin/python src/production_labelling.py label gemini; then
    echo GEMINI_FINISHED
    exit 0
  fi
  echo "GEMINI_CRASHED exit=$? retry in 30s"
  sleep 30
done
