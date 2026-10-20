@echo off
rem Double-click to run. Extra options can be added after main.py (e.g. --port none)
cd /d "%~dp0"
python main.py %*
if errorlevel 1 pause
