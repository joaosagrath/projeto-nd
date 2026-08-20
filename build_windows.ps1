[CmdletBinding(PositionalBinding=$false)]
param(
    [switch]$Clean,
    [switch]$SomentePrincipal,
    [string]$SplashPath = ".\Splash.png",
    [string]$IconPath = ".\app.ico",
    [ValidateRange(1, 3650)]
    [int]$DiasTeste,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptRoot ".venv\Scripts\python.exe"
$RequirementsDev = Join-Path $ScriptRoot "requirements-dev.txt"
$AppPath = Join-Path $ScriptRoot "app.py"
$BuildConfigPath = Join-Path $ScriptRoot "build_config.py"
$DataBuild = (Get-Date).Date
$TemPeriodoTeste = $PSBoundParameters.ContainsKey("DiasTeste")
$DataExpiracao = $null

if ($TemPeriodoTeste) {
    $DataExpiracao = $DataBuild.AddDays($DiasTeste)
}

Set-Location $ScriptRoot

if (-not (Test-Path -Path $PythonExe)) {
    Write-Host "Ambiente virtual não encontrado em .venv." -ForegroundColor Red
    Write-Host "Execute setup.bat antes de compilar." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -Path $BuildConfigPath)) {
    throw "Arquivo build_config.py não encontrado na raiz do projeto."
}

$AppContent = [System.IO.File]::ReadAllText($AppPath)
if ($AppContent -match "from\s+_build_config\s+import") {
    throw "app.py ainda importa _build_config. Substitua pelo import de build_config antes de compilar."
}
if ($AppContent -notmatch "from\s+build_config\s+import\s+DATA_BUILD_EXECUTAVEL") {
    throw "app.py não está importando build_config.py no formato esperado."
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
    "--add-data", "static;static",
    "--hidden-import", "build_config"
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
if ($TemPeriodoTeste) {
    Write-Host "Teste   : $DiasTeste dia(s)"
    Write-Host "Início  : $($DataBuild.ToString('dd/MM/yyyy'))"
    Write-Host "Bloqueio: $($DataExpiracao.ToString('dd/MM/yyyy'))"
}
else {
    Write-Host "Teste   : sem limite de validade"
}
Write-Host ""

if ($DryRun) {
    Write-Host "DryRun habilitado. Nenhum executável será gerado."
    Write-Host "Principal: $PythonExe -m PyInstaller $($commonArgs -join ' ') --clean --windowed --name 'Fluxar Emissoes'"
    if (-not $SomentePrincipal) {
        Write-Host "Console  : $PythonExe -m PyInstaller $($commonArgs -join ' ') --clean --console --name 'Fluxar Emissoes Console'"
    }
    exit 0
}

function Criar-ConfiguracaoBuild {
    if ($TemPeriodoTeste) {
        $DataBuildPython = '"' + $DataBuild.ToString('yyyy-MM-dd') + '"'
        $DiasTestePython = [string]$DiasTeste
    }
    else {
        $DataBuildPython = "None"
        $DiasTestePython = "None"
    }

    $Conteudo = @"
DATA_BUILD_EXECUTAVEL = $DataBuildPython
DIAS_TESTE_EXECUTAVEL = $DiasTestePython
"@

    [System.IO.File]::WriteAllText(
        $BuildConfigPath,
        $Conteudo,
        (New-Object System.Text.UTF8Encoding($false))
    )

    $PyCache = Join-Path $ScriptRoot "__pycache__"
    if (Test-Path -Path $PyCache) {
        Get-ChildItem -Path $PyCache -Filter "build_config*.pyc" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

$BuildConfigOriginal = $null
$BuildConfigExistia = Test-Path -Path $BuildConfigPath
if ($BuildConfigExistia) {
    $BuildConfigOriginal = [System.IO.File]::ReadAllText($BuildConfigPath)
}

try {
    Criar-ConfiguracaoBuild

    Write-Host "Configuração efetivamente lida pelo Python:"
    & $PythonExe -c "import build_config; print(f'  DATA_BUILD_EXECUTAVEL = {build_config.DATA_BUILD_EXECUTAVEL!r}'); print(f'  DIAS_TESTE_EXECUTAVEL = {build_config.DIAS_TESTE_EXECUTAVEL!r}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao validar build_config.py antes da compilação."
    }
    Write-Host ""

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
}
finally {
    if ($BuildConfigExistia) {
        [System.IO.File]::WriteAllText(
            $BuildConfigPath,
            $BuildConfigOriginal,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    else {
        Remove-Item -Force $BuildConfigPath -ErrorAction SilentlyContinue
    }

    $PyCache = Join-Path $ScriptRoot "__pycache__"
    if (Test-Path -Path $PyCache) {
        Get-ChildItem -Path $PyCache -Filter "build_config*.pyc" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Compilação concluída." -ForegroundColor Green
Write-Host "Executáveis gerados em: $(Join-Path $ScriptRoot 'dist')"
if ($TemPeriodoTeste) {
    Write-Host "Validade: $DiasTeste dia(s), com bloqueio em $($DataExpiracao.ToString('dd/MM/yyyy'))."
}
else {
    Write-Host "Validade: ilimitada."
}
Write-Host ""
Write-Host "Ao executar o programa pela primeira vez, a pasta instance será criada ao lado do .exe."
