#!/bin/zsh
set -euo pipefail

output_dir="submission/voice-samples"
mkdir -p "$output_dir"

sample="Signal Desk turns live market data into evidence-grounded research, with governed tools, attributable sources, and confirmed actions."
rate="190"

voices=(
  "Samantha"
  "Alex"
  "Daniel"
  "Karen"
  "Moira"
  "Rishi"
)

for voice in "${voices[@]}"; do
  slug=$(echo "$voice" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
  say -v "$voice" -r "$rate" -o "$output_dir/$slug.aiff" "$sample"
done

echo "$output_dir"
