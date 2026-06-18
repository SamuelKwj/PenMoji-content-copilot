@echo off
setlocal
cd /d "%~dp0"
python main.py --host 127.0.0.1 --port 7870
