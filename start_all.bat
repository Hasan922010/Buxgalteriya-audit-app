@echo off
title Yordamchi Buxgalter AI - Launch All
echo ========================================================
echo   Yordamchi Buxgalter AI - Tizim Ishga Tushirilmoqda...
echo   1. Backend (FastAPI): http://127.0.0.1:8000/docs
echo   2. Frontend (Next.js): http://localhost:3000
echo ========================================================
start "Yordamchi Buxgalter Backend" cmd /k "call \"%~dp0start_backend.bat\""
timeout /t 3 /nobreak >nul
start "Yordamchi Buxgalter Frontend" cmd /k "call \"%~dp0start_frontend.bat\""
timeout /t 2 /nobreak >nul
start http://localhost:3000
echo Tizim muvaffaqiyatli ishga tushirildi! Brauzer ochilmoqda.
