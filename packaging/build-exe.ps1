param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent $PSScriptRoot
$projectPath = Split-Path -Parent $repoPath
$buildPath = Join-Path $projectPath 'dist\build'
$releasePath = Join-Path $projectPath 'dist\release'
$tools = Join-Path $buildPath 'tools'
$mathTools = Join-Path $buildPath 'math-tools'
if (Test-Path -LiteralPath $mathTools) {
    $env:PYTHONPATH = $mathTools + [IO.Path]::PathSeparator + $env:PYTHONPATH
}
if (Test-Path -LiteralPath $tools) {
    $env:PYTHONPATH = $tools + [IO.Path]::PathSeparator + $env:PYTHONPATH
}
$env:PYINSTALLER_CONFIG_DIR = Join-Path $buildPath 'cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $buildPath 'pycache'
# Install build dependencies beforehand: python -m pip install -e './repo[build]'
& $Python -m PyInstaller --noconfirm --distpath $releasePath --workpath (Join-Path $buildPath 'work') (Join-Path $PSScriptRoot 'PDFBilingual.spec')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host ('Executable: ' + (Join-Path $releasePath 'PDFBilingual.exe'))
