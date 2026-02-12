# LinkedIn Easy Apply – Robot Framework (Australia Data Engineer)
# Run from project root. Uses robot/ suite, vars from rahul-au-data-engineer profile.
# For MCP browser, use robot/LINKEDIN_EASY_APPLY_MCP.md (run via AI + MCP tools).

Set-Location $PSScriptRoot

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    .\venv\Scripts\Activate.ps1
}

pip install -q -r requirements-robot.txt 2>$null
robot --pythonpath robot --loglevel DEBUG --outputdir output_au robot/linkedin_easy_apply_au.robot
