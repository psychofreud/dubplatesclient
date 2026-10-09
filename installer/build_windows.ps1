# Builds the Windows installer: build\DubplatesClient-Setup-<version>.exe
# Needs: Python 3.11 (the .venv from run.bat), Node.js, Inno Setup 6 (winget install JRSoftware.InnoSetup).
# Layout inside the install folder:  python\ (embeddable Python + pip + pywebview)   app\ (dubplates_client + ui\dist)
# (native tools write warnings to stderr: PowerShell 5.1 must not stop on that; we check $LASTEXITCODE)
$ErrorActionPreference = 'Continue'
$PyVer = '3.11.9'
$Root = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $Root 'build'
$Out = Join-Path $Build 'win'
$Cache = Join-Path $Build 'cache'
$HostPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $HostPy)) { throw "Run run.bat once first (it makes .venv)" }

$Version = (& $HostPy -c "import sys; sys.path.insert(0, r'$Root'); import dubplates_client as d; print(d.VERSION)").Trim()
Write-Host "Dubplates.net Client $Version"

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force $Out, $Cache | Out-Null

# 1. embeddable Python
$Zip = Join-Path $Cache "python-$PyVer-embed-amd64.zip"
if (-not (Test-Path $Zip)) { Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $Zip -UseBasicParsing -ErrorAction Stop }
Expand-Archive $Zip (Join-Path $Out 'python') -ErrorAction Stop
# search path: the stdlib zip, Lib\site-packages (pip installs there), ..\app (our code); "import site" turns on site-packages
$Pth = "python311.zip`r`n.`r`nLib\site-packages`r`n..\app`r`nimport site`r`n"
[IO.File]::WriteAllText((Join-Path $Out 'python\python311._pth'), $Pth, (New-Object Text.UTF8Encoding $false))

# 2. pip + the window part (the stem engine comes on first start: dubplates_client\bootstrap.py)
& $HostPy -m pip install --disable-pip-version-check --no-warn-script-location -q --target (Join-Path $Out 'python\Lib\site-packages') pip "pywebview>=6.2" requests pyyaml
if ($LASTEXITCODE) { throw "pip failed" }

# 3. the app: code + built UI
Push-Location (Join-Path $Root 'ui'); npm install --silent; npx vite build; if ($LASTEXITCODE) { throw "UI build failed" }; Pop-Location
$App = Join-Path $Out 'app'
New-Item -ItemType Directory -Force (Join-Path $App 'ui') | Out-Null
Copy-Item -Recurse (Join-Path $Root 'dubplates_client') $App
Copy-Item -Recurse (Join-Path $Root 'ui\dist') (Join-Path $App 'ui\dist')
Get-ChildItem $App -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

# 4. quick check: the embedded Python finds our code and pywebview
& (Join-Path $Out 'python\python.exe') -c "import dubplates_client, webview, yaml, requests; print('embedded python ok')"
if ($LASTEXITCODE) { throw "embedded Python check failed" }

# 5. the installer
$Iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
& $Iscc /Q "/DAppVersion=$Version" "/DSrc=$Out" (Join-Path $PSScriptRoot 'dubplates-client.iss')
if ($LASTEXITCODE) { throw "Inno Setup failed" }
$Exe = Join-Path $Build "DubplatesClient-Setup-$Version.exe"
Write-Host ("Done: {0} ({1:N1} MB)" -f $Exe, ((Get-Item $Exe).Length / 1MB))
