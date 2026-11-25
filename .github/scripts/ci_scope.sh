#!/usr/bin/env bash
# Decides whether the checks that run the test suite are needed for this change, and writes
# `code=true` or `code=false` to $GITHUB_OUTPUT. The one place that says what counts as
# documentation (#65); tests/test_ci_scope.py runs it.
#
# Only a pull request can be only documentation. Anything that is not clearly documentation, and
# any doubt (not a pull request, no diff), means `code=true`: run everything.
#
# Documentation is: a Markdown file at the root, anything under docs/, LICENSE, and the template
# of pull requests. Not .github/workflows/ or .github/scripts/: they change what CI does.
# When a test reads the docs (#69), docs/ stops being only documentation.
set -euo pipefail

out="${GITHUB_OUTPUT:-/dev/stdout}"
documentation='^(docs/|LICENSE$|[^/]+\.md$|\.github/PULL_REQUEST_TEMPLATE\.md$)'

if [ "${GITHUB_EVENT_NAME:-}" != pull_request ]; then
  echo "not a pull request: everything runs"
  echo "code=true" >> "$out"
  exit 0
fi

# A pull request is checked out as a merge commit, whose first parent is the tip of the base.
changed=$(git diff --name-only HEAD^1 HEAD 2>/dev/null || true)
if [ -z "$changed" ]; then
  echo "no changed files could be read: everything runs"
  echo "code=true" >> "$out"
  exit 0
fi

echo "changed files:"
printf '%s\n' "$changed" | sed 's/^/  /'

if printf '%s\n' "$changed" | grep -qvE "$documentation"; then
  echo "something is not documentation: everything runs"
  echo "code=true" >> "$out"
else
  echo "only documentation: the test suite is skipped"
  echo "code=false" >> "$out"
fi
