#!/bin/bash
# Prints the useful part of an xcodebuild log: errors, a few warnings, test results and the verdict.
LOG="$1"
[ -f "$LOG" ] || { echo "no log at $LOG"; exit 0; }

echo "=== errors ==="
grep -E "(error:|fatal error|Undefined symbol|ld: |Command .* failed|Testing failed|The following build commands failed)" "$LOG" | sort -u | head -80
echo "=== warnings (first 40 of $(grep -cE '\.swift:[0-9]+:[0-9]+: warning:' "$LOG")) ==="
grep -E "\.swift:[0-9]+:[0-9]+: warning:" "$LOG" | sed -E 's#^.*/Sufler/##' | sort -u | head -40
echo "=== tests ==="
grep -E "(Test Case .* (failed|passed)|XCTAssert|Executed [0-9]+ tests|SUFLER_RENDER_MS_PER_FRAME|error: -\[)" "$LOG" | sed -E 's#^.*/Sufler/##' | tail -90
echo "=== result ==="
grep -E "^\*\* .* \*\*" "$LOG" | tail -3
exit 0
