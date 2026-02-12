@echo off
echo ============================================================
echo   LinkedIn Easy Apply Bot
echo ============================================================
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run "install.bat" first.
    pause
    exit /b 1
)

:: Activate venv
call venv\Scripts\activate.bat

:: Check for profile argument
if "%~1"=="" (
    echo.
    echo Available profiles in the "profiles" folder:
    echo.
    dir /b profiles\*.json 2>nul
    echo.
    set /p PROFILE="Enter profile filename (e.g. my_profile.json): "
    set PROFILE_PATH=profiles\%PROFILE%
) else (
    set PROFILE_PATH=%~1
)

echo.
echo Starting bot with profile: %PROFILE_PATH%
echo.
echo TIP: The bot will open Chrome and start applying.
echo      If LinkedIn asks for verification, complete it in the browser.
echo      Press Ctrl+C to stop the bot at any time.
echo.

python linkedin_easy_apply_bot.py --profile "%PROFILE_PATH%"

echo.
pause
