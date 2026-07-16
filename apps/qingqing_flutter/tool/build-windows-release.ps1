param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ApiBaseUrl
)

$ErrorActionPreference = 'Stop'

$vsRoot = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio'
$atl = Get-ChildItem $vsRoot -Filter atlstr.h -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $atl) {
    throw @'
Visual C++ ATL is not installed. Add component
Microsoft.VisualStudio.Component.VC.ATL in Visual Studio Installer.
'@
}

# Some Windows security products can stall MSBuild's file tracker while the
# compiler itself remains healthy. Flutter does not require that tracker.
$env:TrackFileAccess = 'false'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    puro -e stable flutter build windows --release `
        "--dart-define=API_BASE_URL=$ApiBaseUrl"
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter Windows Release build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$exe = Join-Path $PSScriptRoot '..\build\windows\x64\runner\Release\qingqing.exe'
if (-not (Test-Path $exe)) {
    throw "Windows Release executable was not produced: $exe"
}

Get-Item $exe | Select-Object FullName, Length, LastWriteTime
