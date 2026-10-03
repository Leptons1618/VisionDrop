#!/bin/bash
# Drive the built CLI with good and bad input and assert exit codes and output.
#
# Runs on macOS and Linux. The engine and replay path must behave identically on
# both; camera capture and the menu-bar app are macOS-only and must refuse
# cleanly elsewhere instead of crashing or half-running.
set -uo pipefail

cd "$(dirname "$0")/.."
swift build >/dev/null || exit 1
bin="$(swift build --show-bin-path)"
cli="$bin/visiondrop-cli"
fixture=Tests/Fixtures/pinch-click.jsonl
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
failures=0

# check <name> <want-exit> <want-substring-in-output|""> -- <command...>
check() {
    local name="$1" want_code="$2" want_text="$3"
    shift 4
    local out code
    out="$("$@" 2>&1)"
    code=$?
    if [[ "$code" != "$want_code" ]] || [[ -n "$want_text" && "$out" != *"$want_text"* ]]; then
        echo "FAIL $name: exit $code (want $want_code), output:"
        echo "$out" | head -5 | sed 's/^/       /'
        failures=$((failures + 1))
    else
        echo "ok   $name"
    fi
}

header="$(head -1 "$fixture")"
frame="$(sed -n 2p "$fixture")"
printf '%s\n' "$header" >"$tmp/header-only.jsonl"
printf '' >"$tmp/empty.jsonl"
printf '%s\n{not json\n' "$header" >"$tmp/malformed.jsonl"
printf '%s\n' "${header/\"version\": 2/\"version\": 1}" >"$tmp/v1.jsonl"
printf '%s\n' "$frame" >"$tmp/no-header.jsonl"
printf '%s\n%s\n%s\n' "$header" "${frame/\"t\": /\"t\": 9}" "$frame" >"$tmp/backwards.jsonl"
printf '%s\n' "${header/\"primary\": true/\"primary\": false}" >"$tmp/no-primary.jsonl"
printf '%s\n%s\n' "$header" "${frame/\[0.5, 0.12, 0.87\], /}" >"$tmp/twenty-points.jsonl"
printf '\377\376garbage\n' >"$tmp/binary.jsonl"

echo "── good input"
check "replay fixture" 0 "click: 1" -- "$cli" replay "$fixture"
check "replay --json" 0 '"press",' -- "$cli" replay "$fixture" --json
check "replay flags before path" 0 "press" -- "$cli" replay --verbose "$fixture"
check "info" 0 "recording format version: 2" -- "$cli" info
check "help" 0 "replay <recording.jsonl | ->" -- "$cli" --help
check "replay stdin" 0 "click: 1" -- sh -c '"$1" replay - < "$2"' _ "$cli" "$fixture"
check "replay stdin --json" 0 '"press",' -- sh -c '"$1" replay - --json < "$2"' _ "$cli" "$fixture"
check "stdin with blank lines" 0 "click: 1" -- sh -c 'sed G "$2" | "$1" replay -' _ "$cli" "$fixture"
check "header-only recording" 0 "replayed 0 frames" -- "$cli" replay "$tmp/header-only.jsonl"

echo "── bad arguments"
check "no command" 1 "visiondrop-cli" -- "$cli"
check "unknown command" 1 "unknown command 'fly'" -- "$cli" fly
check "replay without path" 2 "needs a path" -- "$cli" replay
check "replay unknown flag" 2 "does not accept --jsno" -- "$cli" replay "$fixture" --jsno
check "replay two paths" 2 "takes one path" -- "$cli" replay "$fixture" "$fixture"
check "replay missing file" 2 "error:" -- "$cli" replay "$tmp/nope.jsonl"
check "replay a directory" 2 "error:" -- "$cli" replay "$tmp"
check "record without path" 2 "needs a path" -- "$cli" record
check "record --seconds text" 2 "positive number" -- "$cli" record "$tmp/o.jsonl" --seconds abc
check "record --seconds 0" 2 "positive number" -- "$cli" record "$tmp/o.jsonl" --seconds 0
check "record --seconds -5" 2 "positive number" -- "$cli" record "$tmp/o.jsonl" --seconds -5
check "record --seconds nan" 2 "positive number" -- "$cli" record "$tmp/o.jsonl" --seconds nan
check "record --device no value" 2 "--device needs a value" -- "$cli" record "$tmp/o.jsonl" --device
check "record option eats flag" 2 "--seconds needs a value" -- "$cli" record "$tmp/o.jsonl" --seconds --no-mirror
check "record unknown flag" 2 "does not accept --mirror" -- "$cli" record "$tmp/o.jsonl" --mirror

echo "── bad recordings"
check "empty file" 2 "error:" -- "$cli" replay "$tmp/empty.jsonl"
check "malformed line" 2 "line 2" -- "$cli" replay "$tmp/malformed.jsonl"
check "version 1 rejected" 2 "error:" -- "$cli" replay "$tmp/v1.jsonl"
check "frame before header" 2 "error:" -- "$cli" replay "$tmp/no-header.jsonl"
check "timestamps go backwards" 2 "monotonic" -- "$cli" replay "$tmp/backwards.jsonl"
check "no primary display" 2 "primary" -- "$cli" replay "$tmp/no-primary.jsonl"
check "hand with 20 points" 2 "error:" -- "$cli" replay "$tmp/twenty-points.jsonl"
check "binary garbage" 2 "error:" -- "$cli" replay "$tmp/binary.jsonl"

echo "── live stdin"
# The press is on line 6. Hold the rest of the stream back and check the press
# was already reported: events must come out as frames arrive, not at EOF.
{ head -n 8 "$fixture"; sleep 4; tail -n +9 "$fixture"; } \
    | "$cli" replay - --verbose >"$tmp/live.out" 2>&1 &
live=$!
sleep 2
check "event emitted before EOF" 0 "press" -- cat "$tmp/live.out"
check "click not yet emitted" 1 "" -- grep -q click "$tmp/live.out"
wait "$live"
check "stream completes" 0 "click" -- cat "$tmp/live.out"
check "empty stdin" 2 "no lines" -- sh -c '"$1" replay - < /dev/null' _ "$cli"
check "stdin frame first" 2 "header" -- sh -c '"$1" replay - < "$2"' _ "$cli" "$tmp/no-header.jsonl"
check "stdin bad line mid-stream" 2 "line 2" -- sh -c '"$1" replay - < "$2"' _ "$cli" "$tmp/malformed.jsonl"
check "stdin backwards" 2 "monotonic" -- sh -c '"$1" replay - < "$2"' _ "$cli" "$tmp/backwards.jsonl"

echo "── platform ($(uname -s))"
if [[ "$(uname -s)" == "Darwin" ]]; then
    # Recording would open the camera; info's camera lines are the safe probe.
    check "info lists camera permission" 0 "camera:" -- "$cli" info
else
    check "record refuses off macOS" 2 "macOS-only" -- "$cli" record "$tmp/o.jsonl" --seconds 1
    check "record wrote nothing" 1 "" -- test -e "$tmp/o.jsonl"
    check "info says camera unavailable" 0 "unavailable" -- "$cli" info
    check "app refuses off macOS" 1 "requires macOS" -- "$bin/visiondrop-app"
fi

echo
[[ "$failures" == 0 ]] && echo "all CLI checks passed" || echo "$failures CLI check(s) failed"
exit "$failures"
