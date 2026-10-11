# Campus Space Booking - stop the local dev servers started by run-local.ps1
# Kills the listening processes on 8000/5173 AND their whole process tree
# (uvicorn --reload / vite spawn child workers that would otherwise linger).

function Stop-Tree([int]$procId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue
    foreach ($ch in $children) { Stop-Tree $ch.ProcessId }
    try { Stop-Process -Id $procId -Force -ErrorAction Stop } catch {}
}

$roots = @()
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "port $port : nothing listening"; continue }
    foreach ($c in $conns) { $roots += $c.OwningProcess }
}

foreach ($rootId in ($roots | Sort-Object -Unique)) {
    Write-Host "stopping process tree rooted at PID $rootId" -ForegroundColor Yellow
    Stop-Tree $rootId
}

Start-Sleep -Milliseconds 800

# Sweep any orphaned uvicorn / vite workers left from this repo.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main*" -or $_.CommandLine -like "*multiprocessing-fork*app.main*" } |
    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }

Start-Sleep -Milliseconds 500
$left = Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue
if ($left) { $left | Select-Object LocalPort, OwningProcess | Format-Table | Out-String | Write-Host } else { Write-Host "ports 8000/5173 are now free" -ForegroundColor Green }
Write-Host "Done." -ForegroundColor Green
