@echo off
title IK Tracker - Frontend
cd /d "%~dp0frontend"
echo Frontend: http://localhost:5173
"C:\Program Files\nodejs\node.exe" node_modules\vite\bin\vite.js
pause
