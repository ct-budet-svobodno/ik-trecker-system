@echo off
REM Запускает бэкенд и фронтенд в двух отдельных окнах и открывает сайт в браузере.
cd /d "%~dp0"
start "" start-backend.bat
start "" start-frontend.bat
echo Подождите ~10 секунд, пока поднимутся серверы...
timeout /t 10 /nobreak >nul
start "" http://localhost:5173
echo.
echo Сайт: http://localhost:5173   (логин admin / admin123)
echo Чтобы остановить — закройте оба чёрных окна.
