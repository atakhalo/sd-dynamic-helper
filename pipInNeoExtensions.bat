@echo off
cd /d "%~dp0..\.."
call venv\Scripts\activate
uv pip install PySide6 webuiapi dynamicprompts
pause
