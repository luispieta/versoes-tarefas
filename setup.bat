@echo off
echo ============================================
echo   Configurando o projeto (primeira vez)...
echo ============================================

if not exist ".venv" (
    echo Criando ambiente virtual...
    python -m venv .venv
) else (
    echo Ambiente virtual ja existe, pulando criacao.
)

echo Instalando dependencias...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

if not exist ".env" (
    echo Criando arquivo .env de exemplo...
    (
        echo JIRA_EMAIL=seu-email@empresa.com
        echo JIRA_API_TOKEN=seu-token-aqui
        echo CONFLUENCE_CUSTOM_FIELD_DOC=customfield_XXXXX
    ) > .env
    echo.
    echo ATENCAO: edite o arquivo .env com suas credenciais reais antes de rodar o sistema.
) else (
    echo Arquivo .env ja existe, pulando criacao.
)

echo.
echo ============================================
echo   Setup concluido!
echo   Para rodar o script:   .venv\Scripts\python.exe jira_confluence_sync.py
echo   Para rodar a interface: .venv\Scripts\python.exe app.py
echo ============================================
pause
