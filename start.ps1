# openlab 一键启动脚本
#
# 用法（在仓库根目录执行）:
#   .\start.ps1                    # 后端默认端口 8001
#   .\start.ps1 -Port 9000         # 指定后端端口
#   $env:OPENLAB_PORT=9000; .\start.ps1   # 通过环境变量指定端口（-Port 参数优先级更高）
#
# 作用: 自动检测并安装缺失依赖（Python + 后端 venv 与依赖；Node/npm + 前端依赖），
#       然后通过 concurrently 将后端(uvicorn)与前端(vite)合并到一个终端输出启动。
#       后端端口可配置（-Port 参数 > OPENLAB_PORT 环境变量 > 默认 8001），前端代理端口与之一致。
#
# 若 PowerShell 执行策略限制导致无法运行，先执行:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

# 端口解析：-Port 参数优先于 OPENLAB_PORT 环境变量，均未提供时使用默认 8001。
if (-not $PSBoundParameters.ContainsKey('Port') -and $env:OPENLAB_PORT) {
    $Port = [int]$env:OPENLAB_PORT
}
$env:OPENLAB_PORT = "$Port"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Err {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- 1. 检测 Python ---
Write-Step "检测 Python ..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Err "未检测到 Python。请安装 Python 3.10+ 并勾选 'Add to PATH'：https://www.python.org/downloads/"
    exit 1
}
python --version

# --- 2. 创建后端虚拟环境（若不存在） ---
Write-Step "检查后端虚拟环境 backend\.venv ..."
$venvDir = Join-Path $Root "backend\.venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Step "创建虚拟环境 backend\.venv ..."
    python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "创建虚拟环境失败。"
        exit 1
    }
}

# --- 3. 检测/安装后端依赖 ---
Write-Step "检查后端依赖 ..."
& $venvPython -c "import fastapi, uvicorn, langchain_openai"
if ($LASTEXITCODE -ne 0) {
    Write-Step "安装后端依赖 (backend\requirements.txt) ..."
    & $venvPython -m pip install -r (Join-Path $Root "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Err "后端依赖安装失败。"
        exit 1
    }
}

# --- 4. 检测 Node / npm ---
Write-Step "检测 Node / npm ..."
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Err "未检测到 Node.js。请安装 Node.js 18+ (LTS)：https://nodejs.org/"
    exit 1
}
if (-not $npmCmd) {
    Write-Err "未检测到 npm。请安装 Node.js（自带 npm）：https://nodejs.org/"
    exit 1
}
node --version
npm --version

# --- 5. 安装前端依赖（若不存在） ---
Write-Step "检查前端依赖 frontend\node_modules ..."
if (-not (Test-Path -LiteralPath (Join-Path $Root "frontend\node_modules"))) {
    Write-Step "安装前端依赖 ..."
    Push-Location (Join-Path $Root "frontend")
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err "前端依赖安装失败。"
            exit 1
        }
    }
    finally {
        Pop-Location
    }
}

Write-Step "检查根目录依赖 (concurrently / electron) ..."
if (-not (Test-Path -LiteralPath (Join-Path $Root "node_modules")) -or -not (Test-Path -LiteralPath (Join-Path $Root "node_modules\electron"))) {
    Write-Step "安装根目录依赖 ..."
    Push-Location $Root
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err "根目录依赖安装失败。"
            exit 1
        }
    }
    finally {
        Pop-Location
    }
}

# --- 7. 启动 Electron 桌面客户端 ---
Write-Step "启动 Electron 桌面客户端（按 Ctrl+C 停止）..."
Write-Host "  后端: http://localhost:$Port  (health: /api/health)" -ForegroundColor DarkGray
Write-Host "  前端: 由 Electron 窗口内嵌加载" -ForegroundColor DarkGray
Push-Location $Root
try {
    npm run electron:dev
}
finally {
    Pop-Location
}

