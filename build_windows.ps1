[CmdletBinding(PositionalBinding=$false)]
param(
    [switch]$Clean,
    [switch]$SomentePrincipal,
    [string]$SplashPath = ".\\Splash.png",
    [string]$IconPath = ".\\app.ico",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptRoot ".venv\\Scripts\\python.exe"
$RequirementsDev = Join-Path $ScriptRoot "requirements-dev.txt"

Set-Location $ScriptRoot

if (-not (Test-Path -Path $PythonExe)) {
    Write-Host "Ambiente virtual não encontrado em .venv." -ForegroundColor Red
    Write-Host "Execute setup.bat antes de compilar." -ForegroundColor Yellow
    exit 1
}

if (-not [System.IO.Path]::IsPathRooted($SplashPath)) {
    $SplashPath = Join-Path $ScriptRoot $SplashPath
}

if (-not [System.IO.Path]::IsPathRooted($IconPath)) {
    $IconPath = Join-Path $ScriptRoot $IconPath
}

if ($Clean) {
    Write-Host "Limpando builds anteriores..."
    Remove-Item -Recurse -Force (Join-Path $ScriptRoot "build"), (Join-Path $ScriptRoot "dist") -ErrorAction SilentlyContinue
    Remove-Item -Force (Join-Path $ScriptRoot "Fluxar Emissoes.spec"), (Join-Path $ScriptRoot "Fluxar Emissoes Console.spec") -ErrorAction SilentlyContinue
}

& $PythonExe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller não encontrado na .venv. Instalando dependências de desenvolvimento..."
    & $PythonExe -m pip install -r $RequirementsDev

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar as dependências de desenvolvimento."
    }
}

$commonArgs = @(
    "app.py",
    "--noconfirm",
    "--onefile",
    "--add-data", "templates;templates",
    "--add-data", "static;static"
)

if (Test-Path -Path $SplashPath) {
    Write-Host "Splash detectada: $SplashPath"
    $commonArgs += @("--splash", $SplashPath)
}
else {
    Write-Host "Splash não encontrada: $SplashPath" -ForegroundColor Yellow
    Write-Host "O executável será gerado sem splash."
}

if (Test-Path -Path $IconPath) {
    Write-Host "Ícone detectado: $IconPath"
    $commonArgs += @("--icon", $IconPath)
}
else {
    Write-Host "Ícone não encontrado: $IconPath" -ForegroundColor Yellow
    Write-Host "O executável será gerado com o ícone padrão."
}

Write-Host ""
Write-Host "Fluxar Emissões - compilação Windows"
Write-Host "Projeto : $ScriptRoot"
Write-Host "Saída   : $(Join-Path $ScriptRoot 'dist')"
Write-Host ""

if ($DryRun) {
    Write-Host "DryRun habilitado. Nenhum executável será gerado."
    Write-Host "Principal: $PythonExe -m PyInstaller $($commonArgs -join ' ') --clean --windowed --name 'Fluxar Emissoes'"
    if (-not $SomentePrincipal) {
        Write-Host "Console  : $PythonExe -m PyInstaller $($commonArgs -join ' ') --clean --console --name 'Fluxar Emissoes Console'"
    }
    exit 0
}

Write-Host "Gerando Fluxar Emissões (sem console)..."
& $PythonExe -m PyInstaller @commonArgs --clean --windowed --name "Fluxar Emissoes"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o executável principal."
}

if (-not $SomentePrincipal) {
    Write-Host ""
    Write-Host "Gerando versão de diagnóstico (com console)..."
    & $PythonExe -m PyInstaller @commonArgs --clean --console --name "Fluxar Emissoes Console"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao gerar o executável de diagnóstico."
    }
}

Write-Host ""
Write-Host "Compilação concluída." -ForegroundColor Green
Write-Host "Executáveis gerados em: $(Join-Path $ScriptRoot 'dist')"
Write-Host ""
Write-Host "Ao executar o programa pela primeira vez, a pasta instance será criada ao lado do .exe."
