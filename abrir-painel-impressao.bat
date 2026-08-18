@echo off
setlocal

rem === Ajuste esse endereco quando o site estiver publicado (Netlify) ===
rem Local (Docker rodando neste PC):
set "URL=http://localhost:8081/html/estabelecimento.html"
rem Producao (troque pelo dominio real quando tiver):
rem set "URL=https://SEU-SITE.netlify.app/html/estabelecimento.html"

rem Perfil separado so pra essa janela, pra garantir que a flag de impressao
rem direta sempre funcione, mesmo com outra janela do Chrome ja aberta.
set "PERFIL=%LOCALAPPDATA%\LoversAcai\ChromeImpressao"

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
) else (
    echo Nao encontrei o Google Chrome instalado.
    echo Edite este arquivo e ajuste o caminho na variavel CHROME manualmente.
    pause
    exit /b 1
)

start "" "%CHROME%" --kiosk-printing --user-data-dir="%PERFIL%" --new-window "%URL%"
