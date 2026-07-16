param(
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $RepoRoot 'backend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
$DockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Backend virtual environment is missing: $Python"
}

& $Python (Join-Path $Backend 'scripts\bootstrap_dev_env.py')

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path -LiteralPath $DockerDesktop)) {
        throw 'Docker Desktop is not installed.'
    }
    Start-Process -FilePath $DockerDesktop -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Seconds 3
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    } while ((Get-Date) -lt $deadline)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop did not become ready within 60 seconds.'
    }
}

Push-Location $RepoRoot
try {
    docker compose up -d --wait
    if (-not $SkipInstall) {
        & $Python -m pip install -r (Join-Path $Backend 'requirements-integration.txt')
    }
    if (-not $SkipTests) {
        $env:QINGQING_RUN_INTEGRATION = '1'
        $env:QINGQING_ALLOW_LOCAL_USER = 'true'
        & $Python -m pytest `
            (Join-Path $Backend 'tests\test_smtp_login.py') `
            (Join-Path $Backend 'tests\test_optional_integration.py') `
            -q --tb=short
        if ($LASTEXITCODE -ne 0) {
            throw 'QingQing integration checks failed.'
        }
    }
    docker compose ps
} finally {
    Pop-Location
}
