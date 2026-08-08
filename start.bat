@echo off
echo =======================================
echo   SwingEdge Pro — Starting...
echo =======================================
cd /d %~dp0
if not exist .env (
    copy .env.example .env
    echo .env created from .env.example
    echo Please add your API keys to .env for better accuracy.
)
pip install -r requirements.txt --quiet
cd backend
echo.
echo Starting server at http://localhost:8000
echo Open your browser to: http://localhost:8000
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
