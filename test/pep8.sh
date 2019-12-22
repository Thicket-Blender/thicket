#!/bin/sh

# Run from top level project directory:
# $ test/pep8.sh

flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || exit 1
# exit-zero treats all errors as warnings. Blender defines line length of 120.
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics
