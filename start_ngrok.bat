@echo off
REM ==============================================
REM 🦈 SharkIA - Iniciar API com ngrok (Batch)
REM ==============================================
REM Uso alternativo ao PowerShell: start_ngrok.bat
REM ==============================================

echo.
echo   🦈 SharkIA - Iniciando...
echo.

REM Verificar ngrok
where ngrok >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ ngrok nao encontrado!
    echo.
    echo   Instale: https://ngrok.com/download
    echo   Ou: winget install ngrok.ngrok
    echo.
    pause
    exit /b 1
)

REM Iniciar API
echo 🚀 Iniciando API...
start /B python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

echo ⏳ Aguardando API iniciar (pode levar 1-2 min)...
timeout /t 60 /nobreak >nul

REM Iniciar ngrok
echo 🌍 Criando tunel ngrok...
start ngrok http 8000

echo.
echo ✅ Verifique a URL publica no painel do ngrok: http://localhost:4040
echo    Ou na janela do ngrok que abriu.
echo.
echo 📖 Documentacao local: http://localhost:8000/docs
echo.
pause
