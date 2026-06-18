@echo off
setlocal
cd /d "%~dp0"
python cloud_mock.py --host 127.0.0.1 --port 8787
