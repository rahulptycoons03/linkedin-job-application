@echo off
echo ============================================================
echo   LinkedIn Easy Apply Bot - Run Multiple Profiles
echo ============================================================
echo.
echo This will run ALL .json profiles found in the "profiles" folder
echo in separate windows (in parallel).
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run "install.bat" first.
    pause
    exit /b 1
)

set COUNT=0
for %%f in (profiles\*.json) do (
    echo Starting: %%f
    start "Bot - %%~nf" cmd /k "call venv\Scripts\activate.bat && python linkedin_easy_apply_bot.py --profile %%f"
    set /a COUNT+=1
    timeout /t 5 >nul
)

echo.
echo Started %COUNT% bot(s) in separate windows.
echo Close the windows or press Ctrl+C in each to stop.
echo.
pause
