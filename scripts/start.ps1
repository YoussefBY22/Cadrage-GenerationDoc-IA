# Lance Cadrage en local : Ollama (si -Demo absent), l'API FastAPI et l'interface Next.js.
# Usage, depuis la racine du dépôt :
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1          # vrai modèle (Ollama, qwen3:4b + bge-m3)
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Demo    # modèle de démonstration, sans Ollama
param([switch]$Demo)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$py = Join-Path $backend ".venv\Scripts\python.exe"

# 1. Environnement Python (une seule fois)
if (-not (Test-Path $py)) {
    Write-Host "Création du venv backend..."
    & py -3.12 -m venv (Join-Path $backend ".venv")
    & $py -m pip install -q -e $backend reportlab
}

# 2. Dépendances de l'interface (une seule fois)
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installation des dépendances de l'interface..."
    Push-Location $frontend; npm install --no-audit --no-fund; Pop-Location
}

# 3. Modèle
$env:AUTH_MODE = "dev"
if ($Demo) {
    $env:LLM_PROVIDER = "demo"
} else {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw "Ollama introuvable : installe-le (winget install Ollama.Ollama) ou relance avec -Demo."
    }
    try { Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null }
    catch {
        Write-Host "Démarrage d'Ollama..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }
    $models = (& ollama list) -join "`n"
    foreach ($m in @("qwen3:4b", "bge-m3")) {
        if ($models -notmatch [regex]::Escape($m)) { & ollama pull $m }
    }
    $env:LLM_PROVIDER = "ollama"
    $env:OLLAMA_BASE_URL = "http://localhost:11434"
    $env:OLLAMA_GENERATION_MODEL = "qwen3:4b"
    $env:OLLAMA_EMBEDDING_MODEL = "bge-m3"
    $env:OLLAMA_THINK = "false"
    $env:OLLAMA_NUM_GPU = "99"
    $env:EMBEDDING_DIM = "1024"
}

# 4. API (port 8000) et interface (port 3000), chacune dans sa fenêtre
$env:NEXT_TELEMETRY_DISABLED = "1"
Start-Process powershell -WorkingDirectory $backend -ArgumentList "-NoExit", "-Command", "& '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -WorkingDirectory $frontend -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "API : http://localhost:8000/docs   Interface : http://localhost:3000"
Start-Sleep -Seconds 8
Start-Process "http://localhost:3000"
