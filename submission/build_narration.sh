#!/bin/zsh
set -euo pipefail

output_dir="submission/narration-daniel"
mkdir -p "$output_dir"

voice="Daniel"
rate="175"

lines=(
  "Signal Desk turns market data into grounded research, governed actions, and measurable operations."
  "Two Render services provide the research interface and its authenticated M. C. P. tool plane."
  "The workspace unifies performance, evidence, watchlists, saved research, and analytics."
  "Every market result states its as-of date, source coverage, and limitations alongside the key metrics."
  "Peer comparisons use the same time window, making differences in return, range, and volatility directly meaningful."
  "Users search the investment thesis, constrain the company and source type, and receive ranked, attributable evidence with direct links."
  "Persistent changes begin as intent. Signal Desk shows the proposed watchlist update, requires confirmation, and then displays the verified result."
  "Privacy-safe Gold tables make adoption, errors, saved research, and per-tool latency visible to operators."
  "The Supervisor composes the same governed tools into a grounded answer with metrics, sources, dates, and limitations."
  "Tool parameters remain inspectable, while retrieved filing evidence supports the thesis and surfaces material counterpoints."
  "After explicit approval, the Supervisor performs the write and reads the state back to confirm success."
  "Drafting and saving remain separate, so research memory is only persisted when the user asks."
  "Confirmed multi-company reports become durable, reusable research with idempotent writes."
  "Nine discovery, retrieval, read, and write tools publish through a single Unity Catalog M. C. P. service."
  "Native metrics expose request volume, errors, and latency across the tool plane."
  "Sensitive-data guardrails inspect both the incoming request and the final response around every tool call."
  "Lake Flow keeps ingestion, search publishing, and analytics refreshes observable and auditable."
  "The Delta Sync index is online, serving filing and article chunks for grounded retrieval."
  "Lake Base Change Data Feed moves operational state into Unity Catalog for governed downstream analytics."
  "Together, Data Bricks Lake Flow, Lake Base, A. I. Search, Unity Catalog M. C. P., Agent Bricks, and Render form one governed Lake House research data plane."
  "Signal Desk. Research the claim, inspect the evidence, and confirm every action."
)

for index in {1..21}; do
  filename=$(printf "%02d.aiff" "$index")
  say -v "$voice" -r "$rate" -o "$output_dir/$filename" "${lines[$index]}"
done

echo "$output_dir"
