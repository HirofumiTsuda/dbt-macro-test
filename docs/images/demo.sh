#!/usr/bin/env bash
# A recording of a real session: each command is typed on the screen and then really run, in a
# copy of dev/sample_project (called shop, as its dbt_project.yml is).
export PATH="$(dirname "$0")/bin:$PATH"
cd "$(dirname "$0")/shop"
say() { printf '$ '; for ((i = 0; i < ${#1}; i++)); do printf '%s' "${1:i:1}"; sleep 0.03; done; echo; sleep 0.3; }
say "dbt-macro-test run --list"
dbt-macro-test run --list
sleep 2.5
say "dbt-macro-test run 2>&1 | tail -n 4"
dbt-macro-test run 2>&1 | tail -n 4
sleep 2.5
clear
say "sed -i 's/{result: 2.5}/{result: 2.0}/' macro_test/expressions.yml"
sed -i 's/{result: 2.5}/{result: 2.0}/' macro_test/expressions.yml
sleep 0.6
say "dbt-macro-test run --select safe_divide::divides"
dbt-macro-test run --select safe_divide::divides
echo "exit code: $?"
sleep 2.5
