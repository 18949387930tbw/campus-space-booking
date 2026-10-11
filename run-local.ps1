# Campus Space Booking - start backend + frontend locally (no Docker needed)
#
#   .\run-local.ps1              # start both (default)
#   .\run-local.ps1 -Backend     # backend only
#   .\run-local.ps1 -Frontend    # frontend only
param(
    [switch]$Backend,
    [switch]$Frontend
)

$root = $PSScriptRoot
$startBoth = -not ($Backend -or $Frontend)

if ($Backend -or $startBoth) {
    $p = Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload" `
        -WorkingDirectory "$root\backend" -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$root\backend\uvicorn.out.log" -RedirectStandardError "$root\backend\uvicorn.err.log"
    Write-Host ("Backend  PID {0}  ->  http://localhost:8000/docs" -f $p.Id) -ForegroundColor Cyan
}

if ($Frontend -or $startBoth) {
    $p = Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run","dev","--","--host","localhost","--port","5173" `
        -WorkingDirectory "$root\frontend" -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$root\frontend\vite.out.log" -RedirectStandardError "$root\frontend\vite.err.log"
    Write-Host ("Frontend PID {0}  ->  http://localhost:5173" -f $p.Id) -ForegroundColor Cyan
}

Write-Host ""
Write-Host "App:      http://localhost:5173" -ForegroundColor Green
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Login:    admin@example.com / admin12345" -ForegroundColor Green

Write-Host "To stop:  .\stop-local.ps1" -ForegroundColor Yellow