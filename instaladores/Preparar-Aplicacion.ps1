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

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    $transcriptStarted = $true
    Write-Host "Iniciando preparación de $Tipo."
    $pythonExe = Find-Python313
    if (-not $pythonExe) {
        Write-Host "Descargando Python 3.13.17 desde python.org..."
        $pythonInstaller = Join-Path $env:TEMP "vigiwork-python-3.13.17-amd64.exe"
        Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.13.17/python-3.13.17-amd64.exe" -OutFile $pythonInstaller
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
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creando el entorno de la aplicación..."
        & $pythonExe -m venv --clear (Join-Path $appDirectory ".venv")
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de Python." }
    }
    Write-Host "Instalando dependencias de Python..."
    & $venvPython -m pip install -r (Join-Path $appDirectory "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias de la aplicación." }

    if ($Tipo -eq "Servidor") {
        $tools = Join-Path $appDirectory "tools"
        New-Item -ItemType Directory -Path $tools -Force | Out-Null
        $cloudflared = Join-Path $tools "cloudflared.exe"
        if (-not (Test-Path -LiteralPath $cloudflared)) {
            Write-Host "Descargando Cloudflare Tunnel..."
            Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $cloudflared
        }
        Write-Host "Descargando y validando el detector de cascos..."
        & $venvPython -c "from helmet_detector import load_detector; print('Detector:', load_detector().backend)"
        if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar el detector de cascos." }
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
