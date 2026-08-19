@echo off
REM Modo de simulacao: mostra o que SERIA publicado, sem escrever nada no Confluence.
cd /d "%~dp0"
.venv\Scripts\python.exe poller.py --dry-run
pause
