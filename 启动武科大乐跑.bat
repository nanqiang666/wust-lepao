@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" wust_panel.py
) else (
    python wust_panel.py
)
pause
