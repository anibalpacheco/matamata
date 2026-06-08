#!/usr/bin/env bash

set -e # Fail when a command fails!

if [ "$1" == "fix" ]; then
    isort . || true
    black . || true
    git add -u
else
    isort --check-only .
    black --check .
fi

# Always run checkers.
mypy .
pylint --rcfile=.pylintrc $(git ls-files '*.py')
