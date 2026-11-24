param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Servidor", "Cliente")]
    [string]$Tipo,
    [Parameter(Mandatory = $true)]
    [string]$Directorio
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$pythonVersion = "3.13.18"
$cloudflaredVersion = "2026.11.2"
$logDirectory = Join-Path $env:LOCALAPPDATA "VigiWork\Logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logPath = Join-Path $logDirectory "instalacion-$Tipo.log"
$transcriptStarted = $false
$exitCode = 0

function Find-Python313 {
    $launcher = Get-PythonLauncher
    if ($launcher) {
        & $launcher -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,13) and sys.version_info < (3,14) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $resolved = (& $launcher -3.13 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            if ($resolved -and (Test-Path -LiteralPath $resolved)) { return $resolved }
        }
    }
    $pythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path -LiteralPath $pythonRoot) {
        $installed = Get-ChildItem -LiteralPath $pythonRoot -Directory -Filter "Python313*" -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName "python.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($installed) { return $installed }
    }
    return $null
}

function Get-PythonLauncher {
    $command = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $path = Join-Path $env:LOCALAPPDATA "Programs\Python\Launcher\py.exe"
    if (Test-Path -LiteralPath $path) { return $path }
    return $null
}

function Get-VerifiedDownload {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string]$Sha256 = "",
        [string]$ExpectedPublisher = ""
    )

    $partial = "$Destination.download"
    Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $partial
        if (-not (Test-Path -LiteralPath $partial) -or (Get-Item -LiteralPath $partial).Length -eq 0) {
            throw "La descarga quedó vacía: $Uri"
        }
        if ($Sha256) {
            $actual = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $Sha256.ToLowerInvariant()) {
                throw "La descarga no pasó la verificación SHA-256: $Uri"
            }
        }
        if ($ExpectedPublisher) {
            $signature = Get-AuthenticodeSignature -LiteralPath $partial
            $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { "" }
            if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or
                $subject -notlike "*$ExpectedPublisher*") {
                throw "La firma digital de la descarga no es válida para ${ExpectedPublisher}: $Uri"
            }
        }
        Move-Item -LiteralPath $partial -Destination $Destination -Force
    }
    finally {
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    }
}

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    $transcriptStarted = $true
    Write-Host "Iniciando preparación de $Tipo."
    $pythonExe = Find-Python313
    if (-not $pythonExe) {
        Write-Host "Descargando Python $pythonVersion desde python.org..."
        $pythonInstaller = Join-Path $env:TEMP "vigiwork-python-$pythonVersion-amd64.exe"
        Get-VerifiedDownload `
            -Uri "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe" `
            -Destination $pythonInstaller `
            -ExpectedPublisher "Python Software Foundation"
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $pythonInstaller
        $start.Arguments = "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 InstallLauncherAllUsers=0 Include_pip=1 Include_test=0"
        $start.UseShellExecute = $false
        $process = [Diagnostics.Process]::Start($start)
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        Remove-Item -LiteralPath $pythonInstaller -Force -ErrorAction SilentlyContinue
        if ($exitCode -ne 0) { throw "No se pudo instalar Python (código $exitCode)." }
        $launcherDirectory = Join-Path $env:LOCALAPPDATA "Programs\Python\Launcher"
        if (Test-Path -LiteralPath $launcherDirectory) { $env:PATH = "$launcherDirectory;$env:PATH" }
        $pythonExe = Find-Python313
        if (-not $pythonExe) { throw "Python se instaló, pero no se encontró Python 3.13 en el perfil del usuario." }
    }

    $appFolder = if ($Tipo -eq "Servidor") { "server" } else { "client" }
    $appDirectory = Join-Path $Directorio $appFolder
    $venvPython = Join-Path $appDirectory ".venv\Scripts\python.exe"
    $venvIsValid = $false
    if (Test-Path -LiteralPath $venvPython) {
        & $venvPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)" 2>$null
        $venvIsValid = $LASTEXITCODE -eq 0
    }
    if (-not $venvIsValid) {
        Write-Host "Creando el entorno de la aplicación..."
        & $pythonExe -m venv --clear (Join-Path $appDirectory ".venv")
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de Python." }
    }
    Write-Host "Instalando dependencias de Python..."
    & $venvPython -m pip install -r (Join-Path $appDirectory "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias de la aplicación." }

    Push-Location $appDirectory
    try {
        if ($Tipo -eq "Servidor") {
            Write-Host "Comprobando OpenCV, NumPy y PySide6..."
            & $venvPython -c "import cv2, numpy, PySide6; assert hasattr(cv2.dnn, 'readNetFromONNX')"
            if ($LASTEXITCODE -ne 0) { throw "Las dependencias del servidor no superaron la comprobación." }

            $tools = Join-Path $appDirectory "tools"
            New-Item -ItemType Directory -Path $tools -Force | Out-Null
            $cloudflared = Join-Path $tools "cloudflared.exe"
            $cloudflaredIsValid = $false
            if (Test-Path -LiteralPath $cloudflared) {
                $signature = Get-AuthenticodeSignature -LiteralPath $cloudflared
                $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { "" }
                if ($signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid -and
                    $subject -like "*Cloudflare, Inc.*") {
                    $versionOutput = (& $cloudflared version 2>$null | Out-String)
                    $versionExitCode = $LASTEXITCODE
                    $cloudflaredIsValid = (
                        $versionExitCode -eq 0 -and
                        $versionOutput -match [regex]::Escape("cloudflared version $cloudflaredVersion")
                    )
                }
            }
            if (-not $cloudflaredIsValid) {
                Write-Host "Descargando Cloudflare Tunnel $cloudflaredVersion..."
                Get-VerifiedDownload `
                    -Uri "https://github.com/cloudflare/cloudflared/releases/download/$cloudflaredVersion/cloudflared-windows-amd64.exe" `
                    -Destination $cloudflared `
                    -ExpectedPublisher "Cloudflare, Inc."
                $versionOutput = (& $cloudflared version 2>$null | Out-String)
                if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch [regex]::Escape("cloudflared version $cloudflaredVersion")) {
                    throw "cloudflared no corresponde a la versión esperada $cloudflaredVersion."
                }
            }
            Write-Host "Descargando y validando el detector de cascos..."
            & $venvPython -c "from helmet_detector import load_detector; print('Detector:', load_detector().backend)"
            if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar el detector de cascos." }
        }
        else {
            Write-Host "Comprobando PySide6..."
            & $venvPython -c "import PySide6"
            if ($LASTEXITCODE -ne 0) { throw "Las dependencias del cliente no superaron la comprobación." }
        }
    }
    finally {
        Pop-Location
    }
}
catch {
    $exitCode = 1
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host ($_ | Out-String)
}
finally {
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
}
exit $exitCode
