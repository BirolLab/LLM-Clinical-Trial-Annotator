#!/bin/bash
# Full regression suite for the agent-annotate package.
#
# Discovers and runs every scripts/test_*.py (millisec, no network). Use
# before any merge to main, or as a sanity check after refactors. Exits 0
# only if every discovered test file passes.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=python3

print_section() {
    printf '\n========================================\n%s\n========================================\n' "$1"
}

source_failures=0
total_files=0
total_tests=0
passed_tests=0

print_section "Source-level tests"
for f in scripts/test_*.py; do
    [ -f "$f" ] || continue
    total_files=$((total_files + 1))
    last=$($PY "$f" 2>&1 | tail -1)
    case "$last" in
        OK:*)
            count=$(echo "$last" | sed -nE 's/.*OK: ([0-9]+)\/([0-9]+).*/\1 \2/p')
            read -r p t <<<"$count"
            passed_tests=$((passed_tests + p))
            total_tests=$((total_tests + t))
            printf '  %s :: %s\n' "$last" "$(basename "$f")"
            ;;
        *)
            source_failures=$((source_failures + 1))
            printf '  %s :: %s  ← FAILED\n' "$last" "$(basename "$f")"
            ;;
    esac
done

print_section "Summary"
printf '  Source files: %d (%d tests passed)\n' "$total_files" "$passed_tests"
printf '  Source failures: %d  (must be 0 to merge)\n' "$source_failures"

if [ "$source_failures" -eq 0 ]; then
    echo
    echo "✓ Regression PASS — safe to merge."
    exit 0
else
    echo
    echo "✗ Regression FAIL — fix source failures before merging."
    exit 1
fi
