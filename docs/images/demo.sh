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
say "sed -i '27s/shipped/open/' macro_test/relations.yml"
sed -i '27s/shipped/open/' macro_test/relations.yml
sleep 0.6
say "dbt-macro-test run --select upsert_orders 2>&1 | tail -n 18 | grep -v 'compiled code'"
dbt-macro-test run --select upsert_orders 2>&1 | tail -n 18 | grep -v 'compiled code'
echo "exit code: ${PIPESTATUS[0]}"
sleep 2.5
