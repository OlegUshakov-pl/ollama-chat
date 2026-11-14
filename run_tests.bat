@echo off
set PYTHONPATH=src
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m pytest src/tests -v > test_output.txt 2>&1
) else (
    python -m pytest src/tests -v > test_output.txt 2>&1
)
