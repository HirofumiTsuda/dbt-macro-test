#!/usr/bin/env bash
# A recording of a real session: each command is typed on the screen and then really run.
export PATH="$(dirname "$0")/bin:$PATH"
cd "$(dirname "$0")/shop"
say() { printf '$ '; for ((i = 0; i < ${#1}; i++)); do printf '%s' "${1:i:1}"; sleep 0.03; done; echo; sleep 0.3; }
say "dbt-macro-test run"
dbt-macro-test run
sleep 2
clear
say "sed -i 's/{result: 2.5}/{result: 2.0}/' macro_test/safe_divide.yml"
sed -i 's/{result: 2.5}/{result: 2.0}/' macro_test/safe_divide.yml
sleep 0.6
say "dbt-macro-test run"
dbt-macro-test run
echo "exit code: $?"
sleep 2.5
