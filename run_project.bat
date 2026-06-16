@echo off
echo Starting Thaqib Project...

:: Start Backend
start cmd /k ".\venv\Scripts\python.exe -m uvicorn src.thaqib.main:app --host 127.0.0.1 --port 8001 --reload"

:: Start Frontend
cd frontend
start cmd /k "npm run dev"

echo Services started! 
echo Backend: http://127.0.0.1:8001
echo Frontend: http://localhost:5173
pause
