@echo off
title Yordamchi Buxgalter AI - Backend Server
echo ========================================================
echo   Yordamchi Buxgalter AI - Backend Ishga Tushirilmoqda
echo   Manzil: http://127.0.0.1:8000
echo   Swagger Docs: http://127.0.0.1:8000/docs
echo ========================================================
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
