@echo off
echo Starting MathMinds AI System...
start "MathMinds API" cmd /k "run_api.bat"
start "MathMinds Worker" cmd /k "run_worker.bat"
start "MathMinds UI" cmd /k "run_ui.bat"
echo System started in separate windows.
