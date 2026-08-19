"""
Poller: gera as notas de versão automaticamente a partir da planilha "Versões 2026".

Fluxo:
  1. Descobre sozinho as abas de versão da planilha (abas cujo nome tem 4 dígitos: 1031, 1032, ...).
  2. Para cada aba, baixa o conteúdo como CSV e seleciona as tarefas com Status == "Finalizada".
  3. Monta o título da página do Confluence: VERSION_PREFIX + nome da aba (ex.: "4.0.2501.1031").
  4. Chama sync_multiple_issues(), que lê o campo Documentation de cada issue no Jira e publica
     a linha na página do Confluence (criando a página se ainda não existir).

Não é preciso manter nenhuma lista de versões: a cada execução o poller varre as abas de versão
existentes. A guarda de deduplicação em jira_confluence_sync.py garante que rodar repetidamente
(via Agendador de Tarefas do Windows) não duplica linhas já publicadas nem refaz trabalho.

IMPORTANTE: a planilha precisa estar compartilhada como "qualquer pessoa com o link" na internet,
senão a leitura retorna a página de login do Google (erro tratado abaixo).
"""

import os
import io
import re
import sys
import csv
import contextlib
import logging

import requests
from dotenv import load_dotenv

from jira_confluence_sync import (
    sync_multiple_issues,
    find_page_id_by_title,
    get_confluence_page,
    issue_already_on_page,
    SPACE_KEY,
)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ----------------------------- Configuração -----------------------------
SHEET_ID = os.environ.get("SHEET_ID", "1ESvAnD9PpDXRqRWoVDATG_GVXKqZslEgQvs0tFXocNc")
VERSION_PREFIX = os.environ.get("VERSION_PREFIX", "4.0.2501.")
DONE_STATUS = os.environ.get("DONE_STATUS", "Finalizada")

# Piso de versão: na auto-descoberta, ignora abas com número MENOR que este (versões antigas já
# encerradas). O piso e todas as versões futuras (maiores) são processados automaticamente, sem
# precisar editar nada quando uma versão nova surgir. Deixe vazio para não aplicar piso.
MIN_VERSION_TAB = os.environ.get("MIN_VERSION_TAB", "1032").strip()

# Opcional: fixar abas específicas (ex.: SHEET_TABS=1032,1033). Se vazio, descobre automaticamente
# as abas de versão da planilha (respeitando o piso acima).
_ENV_TABS = [t.strip() for t in os.environ.get("SHEET_TABS", "").split(",") if t.strip()]

# Modo dry-run: mostra o que SERIA publicado, sem escrever nada no Confluence.
# Ativa via "python poller.py --dry-run" ou DRY_RUN=1 no .env.
DRY_RUN = ("--dry-run" in sys.argv) or (
    os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "sim", "yes")
)

ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")   # ex.: CWM-3170
VERSION_TAB_RE = re.compile(r"^\d{4}$")               # nome de aba de versão: 4 dígitos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "sync.log")

# Garante acentuação correta no console do Windows (o arquivo de log já é UTF-8).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("poller")


def discover_version_tabs() -> list:
    """Lê a planilha pública e retorna os nomes das abas de versão (4 dígitos), mais novas primeiro."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200 or "accounts.google.com" in resp.url:
        raise RuntimeError(
            f"Não consegui listar as abas (HTTP {resp.status_code}). "
            "A planilha precisa estar compartilhada como 'qualquer pessoa com o link'."
        )
    # bootstrap do htmlview: items.push({name: "1031", ... gid: "957837833"})
    pairs = re.findall(r'name:\s*"([^"]+)"[^}]*?gid:\s*"(\d+)"', resp.text)
    tabs = sorted({name for name, _gid in pairs if VERSION_TAB_RE.match(name)}, reverse=True)

    if MIN_VERSION_TAB:
        try:
            piso = int(MIN_VERSION_TAB)
            ignoradas = [t for t in tabs if int(t) < piso]
            tabs = [t for t in tabs if int(t) >= piso]
            if ignoradas:
                log.info("Ignorando %d aba(s) antiga(s) abaixo do piso %s: %s",
                         len(ignoradas), MIN_VERSION_TAB, ignoradas)
        except ValueError:
            log.warning("MIN_VERSION_TAB='%s' inválido; ignorando o piso.", MIN_VERSION_TAB)
    return tabs


def fetch_tab_csv(tab_name: str) -> str:
    """Baixa uma aba da planilha como CSV (endpoint gviz, leitura por nome da aba)."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
    params = {"tqx": "out:csv", "sheet": tab_name}
    resp = requests.get(url, params=params, allow_redirects=True, timeout=30)
    resp.encoding = "utf-8"
    text = resp.text
    login_redirect = "accounts.google.com" in resp.url
    looks_like_html = text.lstrip()[:15].lower().startswith("<!doctype html")
    if resp.status_code != 200 or login_redirect or looks_like_html:
        raise RuntimeError(
            f"Não consegui ler a aba '{tab_name}' (HTTP {resp.status_code}). "
            "Verifique se a planilha está compartilhada como 'qualquer pessoa com o link'."
        )
    return text


def parse_finished_issues(csv_text: str) -> list:
    """Retorna as chaves de issue cujo Status é DONE_STATUS.

    O layout da aba de versão tem um painel de contadores no topo e só depois o cabeçalho com a
    coluna 'Status'; por isso a coluna é localizada em qualquer linha, não apenas na primeira.
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        return []

    # Localiza o índice da coluna "Status" procurando em qualquer linha de cabeçalho.
    status_col = None
    for row in rows:
        for i, cell in enumerate(row):
            if cell.strip().lower() == "status":
                status_col = i
                break
        if status_col is not None:
            break

    finished, seen = [], set()
    for row in rows:
        # Chave: primeira célula que casa o padrão de issue (ex.: CWM-3170).
        key = next((c.strip() for c in row if ISSUE_KEY_RE.match(c.strip())), None)
        if not key or key in seen:
            continue

        if status_col is not None and status_col < len(row):
            is_done = row[status_col].strip() == DONE_STATUS
        else:
            # Fallback: sem coluna Status identificada, considera concluída quando
            # alguma célula da linha for exatamente igual ao status configurado.
            is_done = any(c.strip() == DONE_STATUS for c in row)

        if is_done:
            finished.append(key)
            seen.add(key)
    return finished


def preview_version(tab_name: str) -> int:
    """DRY-RUN: mostra o que seria publicado nesta versão, sem escrever no Confluence.

    Retorna quantas tarefas NOVAS (ainda não publicadas) seriam adicionadas.
    """
    version_title = f"{VERSION_PREFIX}{tab_name}"
    keys = parse_finished_issues(fetch_tab_csv(tab_name))

    if not keys:
        log.info("[dry-run] Aba '%s' (versão %s): nenhuma tarefa '%s'.",
                 tab_name, version_title, DONE_STATUS)
        return 0

    page_id = find_page_id_by_title(SPACE_KEY, version_title)
    if not page_id:
        log.info("[dry-run] Versão %s: página NÃO existe — seria CRIADA e %d tarefa(s) publicada(s): %s",
                 version_title, len(keys), keys)
        return len(keys)

    body = get_confluence_page(page_id)["body"]["storage"]["value"]
    novas = [k for k in keys if not issue_already_on_page(body, k)]
    ja_publicadas = [k for k in keys if issue_already_on_page(body, k)]

    if novas:
        log.info("[dry-run] Versão %s: %d NOVA(S) a publicar: %s  (%d já na página)",
                 version_title, len(novas), novas, len(ja_publicadas))
    else:
        log.info("[dry-run] Versão %s: nada novo — %d tarefa(s) já publicada(s).",
                 version_title, len(ja_publicadas))
    return len(novas)


def sync_version(tab_name: str) -> int:
    """Sincroniza uma aba de versão. Retorna quantas issues foram enviadas ao sync."""
    version_title = f"{VERSION_PREFIX}{tab_name}"
    csv_text = fetch_tab_csv(tab_name)
    keys = parse_finished_issues(csv_text)

    if not keys:
        log.info("Aba '%s' (versão %s): nenhuma tarefa '%s'.", tab_name, version_title, DONE_STATUS)
        return 0

    log.info("Aba '%s' (versão %s): %d tarefa(s) '%s' -> %s",
             tab_name, version_title, len(keys), DONE_STATUS, keys)

    # Captura o stdout do sync (mensagens [ok]/[skip]/[erro]) para registrar no log.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            sync_multiple_issues(keys, fix_version=version_title)
    finally:
        for line in buf.getvalue().splitlines():
            if line.strip():
                log.info("[sync] %s", line)
    return len(keys)


def main():
    modo = "DRY-RUN (nada será escrito no Confluence)" if DRY_RUN else "execução real"
    if _ENV_TABS:
        tabs = _ENV_TABS
        log.info("=== Poller iniciado [%s]. Abas fixadas via .env: %s ===", modo, tabs)
    else:
        try:
            tabs = discover_version_tabs()
        except Exception as e:
            log.error("Falha ao descobrir as abas de versão: %s", e)
            return
        log.info("=== Poller iniciado [%s]. Abas de versão descobertas: %s ===", modo, tabs)

    processar = preview_version if DRY_RUN else sync_version
    total = 0
    for tab in tabs:
        try:
            total += processar(tab)
        except Exception as e:
            log.error("Aba '%s': %s", tab, e)

    if DRY_RUN:
        log.info("=== Poller finalizado [DRY-RUN]. %d tarefa(s) NOVA(S) seriam publicadas. ===", total)
    else:
        log.info("=== Poller finalizado. %d tarefa(s) enviada(s) ao sync. ===", total)


if __name__ == "__main__":
    main()
