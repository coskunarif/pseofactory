#!/usr/bin/env bash
# ==============================================================================
# Consolidated Multi-Cloud Infrastructure & Host Hygiene Audit Script
# Path: pseofactory/bin/audit-infra.sh
# Consolidates:
#   1) satellites/cloudflare/bin/cloud audit
#   2) satellites/cloudflare/bin/gcp billing summary
#   3) HostHygieneAuditor on profithelm-platform
#   4) Live edge curl checks on active tenant endpoints:
#      profithelm.com, prexvo.com, arifcoskun.com, gainhelm.com
# Emits structured JSON anomaly logs to .agy/telemetry_events.jsonl on failure.
# Exits code 0 on all passes.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PSEOFACTORY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$PSEOFACTORY_DIR:${PYTHONPATH:-}"
exec python3 -m pseofactory.infra_audit "$@"
