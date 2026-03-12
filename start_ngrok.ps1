# ==============================================
# SharkIA - Iniciar API com ngrok
# ==============================================
# Uso: .\start_ngrok.ps1
# Pre-requisitos: Python 3.11+, ngrok instalado e autenticado
# ==============================================

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

function Write-Banner {
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "  [SHARK] SharkIA - Classificador NCM         " -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# Banner
Write-Banner

# ---- Verificacoes ----
Write-Host "[*] Verificando pre-requisitos..." -ForegroundColor Yellow

# Python
if (-not (Test-Command "python")) {
    Write-Host "[X] Python nao encontrado! Instale Python 3.11+" -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  [OK] $pyVersion" -ForegroundColor Green

# ngrok
if (-not (Test-Command "ngrok")) {
    Write-Host "[X] ngrok nao encontrado!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Para instalar:" -ForegroundColor Yellow
    Write-Host "    1. Baixe em: https://ngrok.com/download" -ForegroundColor White
    Write-Host "    2. Ou via winget:  winget install ngrok.ngrok" -ForegroundColor White
    Write-Host "    3. Ou via choco:   choco install ngrok" -ForegroundColor White
    Write-Host ""
    Write-Host "  Depois autentique:" -ForegroundColor Yellow
    Write-Host "    ngrok config add-authtoken SEU_TOKEN" -ForegroundColor White
    Write-Host "    (Pegue o token em: https://dashboard.ngrok.com/get-started/your-authtoken)" -ForegroundColor DarkGray
    exit 1
}
Write-Host "  [OK] ngrok instalado" -ForegroundColor Green

# ---- Instalar dependencias ----
Write-Host ""
Write-Host "[*] Verificando dependencias Python..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
python -m pip install -r requirements.txt --quiet 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
Write-Host "  [OK] Dependencias OK" -ForegroundColor Green

# ---- Iniciar API ----
Write-Host ""
Write-Host "[>] Iniciando SharkIA API na porta $Port..." -ForegroundColor Yellow

# Matar processos anteriores na mesma porta (se houver)
$existingProcess = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($existingProcess) {
    Write-Host "  [!] Porta $Port em uso. Liberando..." -ForegroundColor DarkYellow
    $existingProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# Iniciar uvicorn em background
$apiJob = Start-Job -ScriptBlock {
    param($port, $dir)
    Set-Location $dir
    $env:PYTHONIOENCODING = "utf-8"
    & python -m uvicorn src.api.main:app --host 0.0.0.0 --port $port 2>&1
} -ArgumentList $Port, $PWD

Write-Host "  [...] Aguardando API iniciar..." -ForegroundColor DarkGray

# Aguardar API ficar pronta (max 3 min)
$maxAttempts = 36
$attempt = 0
$apiReady = $false

while ($attempt -lt $maxAttempts) {
    Start-Sleep -Seconds 5
    $attempt++
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method Get -TimeoutSec 3 -ErrorAction Stop
        $apiReady = $true
        break
    } catch {
        Write-Host "  [...] Tentativa $attempt/$maxAttempts..." -ForegroundColor DarkGray
    }
}

if (-not $apiReady) {
    Write-Host "[X] API nao iniciou! Verifique os logs:" -ForegroundColor Red
    Receive-Job $apiJob
    exit 1
}

Write-Host "  [OK] API respondendo em http://localhost:$Port" -ForegroundColor Green

# ---- Iniciar ngrok ----
Write-Host ""
Write-Host "[>] Criando tunel ngrok..." -ForegroundColor Yellow

# Matar ngrok anterior (se houver)
Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Iniciar ngrok em background
$ngrokProcess = Start-Process ngrok -ArgumentList "http $Port" -PassThru -WindowStyle Hidden

# Aguardar ngrok criar o tunel
Start-Sleep -Seconds 5

# Obter URL publica via API local do ngrok
$maxNgrokAttempts = 10
$ngrokUrl = $null
$ngrokAttempt = 0

while ($ngrokAttempt -lt $maxNgrokAttempts) {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -TimeoutSec 3 -ErrorAction Stop
        $ngrokUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
        if (-not $ngrokUrl) {
            $ngrokUrl = ($tunnels.tunnels | Select-Object -First 1).public_url
        }
        if ($ngrokUrl) { break }
    } catch {}
    $ngrokAttempt++
    Start-Sleep -Seconds 2
}

if (-not $ngrokUrl) {
    Write-Host "[X] Nao foi possivel obter a URL do ngrok!" -ForegroundColor Red
    Write-Host "  Verifique se o ngrok esta autenticado:" -ForegroundColor Yellow
    Write-Host "    ngrok config add-authtoken SEU_TOKEN" -ForegroundColor White
    exit 1
}

# ---- Sucesso! ----
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host "  [SHARK] SharkIA API esta ONLINE!           " -ForegroundColor Green
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL PUBLICA: " -NoNewline -ForegroundColor White
Write-Host "$ngrokUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Endpoints:" -ForegroundColor White
Write-Host "     GET  $ngrokUrl/health" -ForegroundColor DarkGray
Write-Host "     GET  $ngrokUrl/docs" -ForegroundColor DarkGray
Write-Host "     POST $ngrokUrl/classificar" -ForegroundColor DarkGray
Write-Host "     POST $ngrokUrl/confirmar" -ForegroundColor DarkGray
Write-Host "     POST $ngrokUrl/buscar" -ForegroundColor DarkGray
Write-Host "     GET  $ngrokUrl/pendentes" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Swagger UI:" -ForegroundColor White
Write-Host "     $ngrokUrl/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ngrok Dashboard:" -ForegroundColor White
Write-Host "     http://localhost:4040" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host "  Pressione Ctrl+C para encerrar tudo" -ForegroundColor Yellow
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host ""

# Copiar URL para clipboard
try {
    $ngrokUrl | Set-Clipboard
    Write-Host "  [i] URL copiada para a area de transferencia!" -ForegroundColor DarkGreen
    Write-Host ""
} catch {}

# ---- Manter rodando e monitorar ----
try {
    while ($true) {
        Start-Sleep -Seconds 60

        # Verificar se API ainda esta viva
        try {
            $null = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 5 -ErrorAction Stop
            $timestamp = Get-Date -Format "HH:mm:ss"
            Write-Host "  [OK] [$timestamp] API ativa - $ngrokUrl" -ForegroundColor DarkGreen
        } catch {
            $timestamp = Get-Date -Format "HH:mm:ss"
            Write-Host "  [!] [$timestamp] API nao respondeu! Verificando..." -ForegroundColor Yellow
        }
    }
} finally {
    # Cleanup ao sair (Ctrl+C)
    Write-Host ""
    Write-Host "[!] Encerrando SharkIA..." -ForegroundColor Yellow

    # Parar ngrok
    Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    # Parar job da API
    if ($apiJob) {
        Stop-Job $apiJob -ErrorAction SilentlyContinue
        Remove-Job $apiJob -Force -ErrorAction SilentlyContinue
    }

    # Matar uvicorn na porta
    $procs = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    $procs | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

    Write-Host "SharkIA encerrado!" -ForegroundColor Green
}
