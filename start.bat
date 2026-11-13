@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Trace: 检查环境 ===
where python >nul 2>nul || (echo [缺少] 没找到 python，请先安装 Python 3.11+ & pause & exit /b 1)
where npm >nul 2>nul || (echo [缺少] 没找到 Node.js，请先安装 Node.js 20+ & pause & exit /b 1)

if not exist .env (
  copy .env.example .env >nul
  powershell -NoProfile -Command "(Get-Content .env) -replace '^DATA_DIR=.*','DATA_DIR=E:/Download/junction-dataset-preview' | Set-Content -Encoding utf8 .env"
  echo 已创建 .env，请在里面填 GEMINI_API_KEY 等，然后重新运行本脚本
  notepad .env
  pause
  exit /b 0
)

if not exist .venv (
  echo === 创建 Python 虚拟环境 ===
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo === 安装后端依赖 ===
python -m pip install -q -r agent\requirements.txt || (pause & exit /b 1)

echo === 安装前端依赖 ===
pushd web
call npm install --no-audit --no-fund || (popd & pause & exit /b 1)
popd

echo === 启动后端 (端口 8000) 和前端 (端口 5173) ===
start "Trace backend" cmd /k ".venv\Scripts\activate.bat && uvicorn agent.app:app --reload --port 8000"
start "Trace web" cmd /k "cd web && npm run dev"
timeout /t 6 >nul
start http://localhost:5173
echo 已启动。关掉两个黑色窗口即可停止。
pause
