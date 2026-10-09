# Campus Space Booking - first-time local setup (Windows PowerShell)
# Creates the Python venv, installs backend + frontend deps, and seeds the DB.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "==> [1/4] Creating backend virtualenv" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".\.venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip

Write-Host "==> [2/4] Installing backend dependencies" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install `
    "fastapi[standard]>=0.141.1,<1.0.0" "python-multipart<1.0.0,>=0.0.27" `
    "email-validator<3.0.0.0,>=2.1.0.post1" "pydantic>=2.13.5" `
    "emails>=1.1.2,<2.0" "jinja2<4.0.0,>=3.1.4" "alembic>=1.19.1,<2.0.0" `
    "httpx<1.0.0,>=0.25.1" "sqlmodel>=0.0.46,<1.0.0" `
    "pydantic-settings<3.0.0,>=2.2.1" "sentry-sdk[fastapi]>=2.70.0,<3.0.0" `
    "pyjwt>=2.15.0,<3.0.0" "pwdlib[argon2,bcrypt]>=0.3.1" `
    "pytest<10.0.0,>=7.4.3"

Write-Host "==> [3/4] Seeding SQLite database + superuser" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m app.initial_data

Write-Host "==> [4/4] Installing frontend dependencies (npm)" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install --no-audit --no-fund

Write-Host ""
Write-Host "Setup complete. Start the app with:  .\run-local.ps1" -ForegroundColor Green
