@echo off
set PYTHONPATH=src
python -m pytest src/tests/test_tasks.py -v > test_output.txt 2>&1