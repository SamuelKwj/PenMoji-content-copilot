@echo off
setlocal
cd /d "%~dp0"
start "Content Workbench Cloud Mock" /min python cloud_mock.py --host 127.0.0.1 --port 8787
timeout /t 1 /nobreak >nul
start "Content Workbench Desktop" /min python main.py --host 127.0.0.1 --port 7870
timeout /t 2 /nobreak >nul
start http://127.0.0.1:7870
