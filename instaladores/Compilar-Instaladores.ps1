$ErrorActionPreference = "Stop"
$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$compiler = if ($isccCommand) { $isccCommand.Source } else { $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1 }
if (-not $compiler) { throw "No se encontró Inno Setup 6 o 7. Instalalo y volvé a ejecutar este archivo." }

$output = Join-Path $PSScriptRoot "salida"
New-Item -ItemType Directory -Path $output -Force | Out-Null
Push-Location $PSScriptRoot
try {
    foreach ($name in @("VigiWork-Servidor", "VigiWork-Cliente")) {
        Write-Host "Compilando $name..."
        & $compiler "/O$output" (Join-Path $PSScriptRoot "$name.iss")
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup no pudo compilar $name.iss (código $LASTEXITCODE)." }
    }
}
finally {
    Pop-Location
}
Write-Host "Instaladores creados en $output" -ForegroundColor Green
