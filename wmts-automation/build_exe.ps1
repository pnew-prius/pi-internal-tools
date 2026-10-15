# Build the Windows package:  pwsh -File build_exe.ps1
# Result: dist\wmts-builder-<commit>.zip  (unzip anywhere on another Windows machine and run wmts-builder.exe; see INSTALL.txt)
# Uses a throwaway virtual environment (.build-venv) so nothing is installed system-wide.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$commit = (git rev-parse --short HEAD 2>$null)
if (-not $commit) { $commit = "local" }
if (git status --porcelain -- . 2>$null) { $commit += "-dirty" }

if (-not (Test-Path .build-venv)) { python -m venv .build-venv }
$py = Join-Path $PSScriptRoot ".build-venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt pyinstaller

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --clean --onedir --name wmts-builder `
    --add-data "templates;templates" `
    --collect-data pyproj `
    --collect-submodules azure.identity --collect-submodules azure.keyvault.secrets `
    exe_main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item INSTALL.txt dist\wmts-builder\INSTALL.txt
Set-Content dist\wmts-builder\VERSION.txt "wmts-automation $commit, built $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$zip = "dist\wmts-builder-$commit.zip"
Compress-Archive -Path dist\wmts-builder -DestinationPath $zip -Force
"Built $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
