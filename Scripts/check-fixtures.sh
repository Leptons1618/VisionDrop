#!/bin/bash
# Assert each fixture still replays to its expected event sequence.
#
# This is the behavioural half of the regression gate (SRS §7.2): the coverage
# and lint checks say the code is well formed, this says it still does the same
# thing. A commit that deliberately changes gesture behaviour updates the
# expectation here in the same commit, so the diff shows the change explicitly
# (ARCHITECTURE §6.3).
set -euo pipefail

cd "$(dirname "$0")/.."
failures=0

expect() {
    local fixture="$1" want="$2"
    local got
    got=$(swift run -c release visiondrop-cli replay "$fixture" --json \
          | python3 -c "import json,sys; print(' '.join(json.load(sys.stdin)['eventSequence']))")
    if [[ "$got" != "$want" ]]; then
        echo "FAIL $(basename "$fixture"): expected sequence [$want], got [$got]"
        failures=$((failures + 1))
    else
        echo "ok   $(basename "$fixture"): [$got]"
    fi
}

expect Tests/Fixtures/pinch-click.jsonl "press click"


exit "$failures"
