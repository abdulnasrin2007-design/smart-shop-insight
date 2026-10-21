@echo off
REM First-time setup + start both servers. Run from the project folder.
cd backend
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -r requirements.txt
start "Backend" cmd /k "uvicorn app.main:app --port 8000"
cd ..\frontend
call npm install
start "Frontend" cmd /k "npm run dev"
echo Open http://localhost:5173  (API docs: http://127.0.0.1:8000/docs)
