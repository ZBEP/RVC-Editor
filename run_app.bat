@echo off
cd /d "%~dp0"
cd ..
set RVC_ROOT=%cd%
cd app

"%RVC_ROOT%\runtime\python.exe" main.py
pause