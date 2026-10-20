@echo off
rem Double-click once to install the libraries (needs internet)
cd /d "%~dp0"
python -m pip install -r requirements.txt
pause
