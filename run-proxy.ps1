# Starts the Token IQ proxy on http://localhost:4001
#
# Run it from your own terminal:  .\run-proxy.ps1
# Ctrl+C stops it. Nothing else will, unlike a process started from a chat session.
#
# Credentials are read from the running Postgres container, so no password is
# stored in this file or typed on the command line.

$ErrorActionPreference = "Stop"

$container = "tokeniq_db"
$port = 4001
$repo = $PSScriptRoot
$python = "$repo\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtualenv at $python" -ForegroundColor Red
    exit 1
}

if (-not (docker ps --filter "name=$container" --format "{{.Names}}")) {
    Write-Host "Database container '$container' is not running." -ForegroundColor Red
    Write-Host "Start it with:  docker start $container" -ForegroundColor Yellow
    exit 1
}

$envLines = docker inspect $container --format '{{range .Config.Env}}{{println .}}{{end}}'
function Get-ContainerEnv($name) {
    $match = $envLines | Select-String "^$name="
    if (-not $match) { throw "$name not found on container $container" }
    return ($match.ToString() -split '=', 2)[1]
}

$user = Get-ContainerEnv "POSTGRES_USER"
$pass = Get-ContainerEnv "POSTGRES_PASSWORD"
$db = Get-ContainerEnv "POSTGRES_DB"

# 127.0.0.1 rather than localhost: on Windows localhost resolves to ::1 first and
# goes through a different Docker relay. Naming the address avoids the question.
$env:DATABASE_URL = "postgresql://${user}:${pass}@127.0.0.1:5432/${db}"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $repo
$env:PATH = "$repo\.venv\Scripts;$env:PATH"

# Prisma runs its query engine as a child process. Kill the proxy without a clean
# shutdown, by closing the terminal or from a tool that stops the parent, and the engine
# survives as an orphan. Enough of those accumulate and new engines fail to start, which
# surfaces as httpx.ConnectError inside prisma/engine/http.py or as a P1001 claiming the
# database is unreachable. Both messages point at the database; neither is about it.
$orphans = Get-Process -Name "query-engine-windows" -ErrorAction SilentlyContinue
if ($orphans) {
    Write-Host "Clearing $($orphans.Count) orphaned Prisma engine process(es)..." -ForegroundColor DarkGray
    $orphans | Stop-Process -Force -Confirm:$false
    Start-Sleep -Seconds 1
}

# Prisma picks the engine's port by binding to port 0, reading the number, then closing
# the socket before the engine binds it. On this machine ~1,300 ports are reserved by
# Hyper-V/Docker/WSL (netsh interface ipv4 show excludedportrange protocol=tcp) and Docker
# churns ports constantly, so that gap is sometimes lost. The engine then fails to bind and
# exits, and the client reports "All connection attempts failed" as though the database were
# down. The port is random each attempt, so retrying clears it.
$maxAttempts = 4
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    if ($attempt -gt 1) {
        Write-Host "Engine failed to start. Retrying ($attempt of $maxAttempts)..." -ForegroundColor Yellow
        Get-Process -Name "query-engine-windows" -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
        Start-Sleep -Seconds 2
    }

    Write-Host "Starting Token IQ on http://localhost:$port  (Ctrl+C to stop)" -ForegroundColor Cyan
    $startedAt = Get-Date
    & $python "$repo\litellm\proxy\proxy_cli.py" --config "$repo\litellm\proxy\dev_config.yaml" --port $port
    $ranFor = (Get-Date) - $startedAt

    # A clean run lasts as long as you leave it open. Exiting within a minute means it never
    # got off the ground, which is the engine race rather than anything you did.
    if ($ranFor.TotalSeconds -ge 60) { break }
}

Get-Process -Name "query-engine-windows" -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
