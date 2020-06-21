#!/bin/sh

# Run from top level project directory:
# $ test/pep8.sh

# When changing this script, be sure to sync changes with the GitHub action
# script: .github/workflows/pythonapp.yml

echo "Running critical tests"
python3 -m flake8 . --isolated --show-source --statistics --extend-ignore=E501,F821,F722 || exit 1
echo "PASS"

echo ""
echo "Running informational tests"
# exit-zero treats all errors as warnings. Blender defines line length of 120.
python3 -m flake8 . --isolated --max-complexity=10 --max-line-length=120 --statistics --extend-ignore=F821,F722 && echo "PASS"
exit 0
