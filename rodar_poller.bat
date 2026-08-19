@echo off
REM Alvo do Windows Task Scheduler: sincroniza automaticamente as tarefas
REM "Finalizada" da planilha de versoes para o Confluence.
cd /d "%~dp0"
.venv\Scripts\python.exe poller.py
