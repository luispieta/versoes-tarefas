"""
Sincroniza o campo "Documentation" de uma issue do Jira para uma tabela
existente em uma página do Confluence.

Pré-requisitos:
    pip install requests python-dotenv

Configuração:
    1. Crie um arquivo ".env" na mesma pasta deste script com o conteúdo:
         JIRA_EMAIL=seu-email@empresa.com
         JIRA_API_TOKEN=seu-token-aqui
         CONFLUENCE_CUSTOM_FIELD_DOC=customfield_XXXXX
    2. Descubra o ID do campo customizado "Documentation":
       GET {JIRA_URL}/rest/api/3/field
       Procure na lista o campo com name == "Documentation" e copie o "id"
       (algo como "customfield_10087") para usar no CONFLUENCE_CUSTOM_FIELD_DOC.
    3. Descubra o ID (pageId) da página do Confluence de destino, se for usar
       page_id diretamente:
       - Abra a página no navegador
       - O ID aparece na URL, ex: .../pages/123456789/4.0.2501.1026
    4. Rode: python jira_confluence_sync.py

Este script foi pensado para ser chamado a partir de um serviço externo
(Lambda, Cloud Function, servidor simples) que recebe o webhook disparado
pelo "Send web request" do Jira Automation.
"""

import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()  # lê o arquivo .env na mesma pasta e carrega as variáveis

# ----------------------- CONFIGURAÇÃO -----------------------
JIRA_URL = "https://nimitz.atlassian.net"
CONFLUENCE_URL = "https://nimitz.atlassian.net/wiki"

EMAIL = os.environ["JIRA_EMAIL"]
API_TOKEN = os.environ["JIRA_API_TOKEN"]
CUSTOM_FIELD_DOC = os.environ["CONFLUENCE_CUSTOM_FIELD_DOC"]

# Um único space do Confluence para todas as verticais. As diferentes
# verticais/projetos são organizadas por páginas (ex: pastas "CRM",
# "Fiscal", etc.) dentro deste mesmo espaço, não por spaces separados.
SPACE_KEY = "DPU"

# Cores de destaque por tipo de issue, iguais à legenda usada nas páginas de
# release (verde claro = melhoria, vermelho claro = bug/correção).
# Ajuste os nomes das chaves para bater EXATAMENTE com o "Issue Type" usado
# no seu Jira (confira em Project Settings > Issue types, ou olhando o ícone
# de tipo na própria issue).
ISSUE_TYPE_COLORS = {
    "Melhoria": "#E3FCEF",   # verde claro
    "Improve": "#E3FCEF",    # verde claro (caso o tipo se chame "Improve")
    "Bug": "#FFEBE6",        # vermelho claro
    "Erro": "#FFEBE6",       # vermelho claro (caso o tipo se chame "Erro")
}
DEFAULT_ROW_COLOR = None  # cor usada quando o tipo não estiver no mapeamento acima

# ---- Configuração do cabeçalho padrão criado em páginas novas ----
BANNER_PREFIX = "CRM"          # texto antes da versão no banner (ex: "CRM 4.0.2501.1027")
BANNER_COLOR = "#57D9A3"       # verde do banner de título
LEGEND_IMPROVEMENT_COLOR = "#E3FCEF"  # verde claro (mesmo de ISSUE_TYPE_COLORS)
LEGEND_IMPROVEMENT_TEXT = "Melhorias e implementações de novas funcionalidade."
LEGEND_BUG_COLOR = "#FFEBE6"          # vermelho claro (mesmo de ISSUE_TYPE_COLORS)
LEGEND_BUG_TEXT = "Correções e ajustes de validações incorretas."

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Content-Type": "application/json"}
# --------------------------------------------------------------


def get_issue_documentation(issue_key: str):
    """Busca resumo, tipo da issue e conteúdo (ADF) do campo Documentation."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    resp = requests.get(url, auth=auth, headers=headers)
    resp.raise_for_status()
    fields = resp.json()["fields"]
    summary = fields.get("summary")
    adf_content = fields.get(CUSTOM_FIELD_DOC)
    issue_type = fields.get("issuetype", {}).get("name")
    return summary, adf_content, issue_type


def convert_adf_to_storage(adf_content: dict) -> str:
    """Converte o conteúdo ADF do Jira para o Storage Format do Confluence.

    A API do Confluence espera o campo "value" como STRING, mesmo quando a
    representação é atlas_doc_format — por isso serializamos o dict com
    json.dumps antes de enviar.
    """
    url = f"{CONFLUENCE_URL}/rest/api/contentbody/convert/storage"
    body = {
        "value": json.dumps(adf_content),
        "representation": "atlas_doc_format",
    }
    resp = requests.post(url, auth=auth, headers=headers, json=body)
    if not resp.ok:
        # Mostra o corpo do erro retornado pela API para facilitar o diagnóstico
        print(f"[erro convert_adf_to_storage] status={resp.status_code} body={resp.text}")
    resp.raise_for_status()
    return resp.json()["value"]


def get_confluence_page(page_id: str):
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=body.storage,version"
    resp = requests.get(url, auth=auth, headers=headers)
    resp.raise_for_status()
    return resp.json()


def find_page_id_by_title(space_key: str, title: str):
    """Alternativa a passar o page_id manualmente: busca pelo título exato
    (útil se você quiser mapear automaticamente Fix Version -> página)."""
    url = f"{CONFLUENCE_URL}/rest/api/content"
    params = {"spaceKey": space_key, "title": title, "expand": "version"}
    resp = requests.get(url, auth=auth, headers=headers, params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def build_header_block(version_title: str) -> str:
    """Monta o cabeçalho padrão: banner com o título da versão, bloco de
    Legenda (melhoria/bug) e a tabela vazia com o cabeçalho de colunas
    Chave / Resumo / Documentação — igual ao padrão já usado nas páginas
    de release existentes.
    """
    banner_text = f"{BANNER_PREFIX} {version_title}".strip()
    return f"""
<table style="width: 100%;">
  <tbody>
    <tr>
      <td data-highlight-colour="{BANNER_COLOR}" style="text-align: center;">
        <strong>{banner_text}</strong>
      </td>
    </tr>
  </tbody>
</table>
<p style="text-align: center;"><strong>Legenda:</strong></p>
<table style="width: 100%;">
  <tbody>
    <tr>
      <td data-highlight-colour="{LEGEND_IMPROVEMENT_COLOR}">
        <strong>{LEGEND_IMPROVEMENT_TEXT}</strong>
      </td>
    </tr>
    <tr>
      <td data-highlight-colour="{LEGEND_BUG_COLOR}">
        <strong>{LEGEND_BUG_TEXT}</strong>
      </td>
    </tr>
  </tbody>
</table>
<table style="width: 100%;">
  <tbody>
    <tr>
      <th>Chave</th>
      <th>Resumo</th>
      <th>Documentação</th>
    </tr>
  </tbody>
</table>
"""


def create_confluence_page(space_key: str, title: str) -> dict:
    """Cria uma página nova no Confluence já com o cabeçalho padrão
    (banner + legenda + tabela com cabeçalho de colunas)."""
    url = f"{CONFLUENCE_URL}/rest/api/content"
    body = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": build_header_block(title),
                "representation": "storage",
            }
        },
    }
    resp = requests.post(url, auth=auth, headers=headers, json=body)
    if not resp.ok:
        print(f"[erro create_confluence_page] status={resp.status_code} body={resp.text}")
    resp.raise_for_status()
    print(f"[ok] Página '{title}' criada no espaço '{space_key}' com o cabeçalho padrão.")
    return resp.json()


def append_row_to_table(page_storage_html: str, issue_key: str, summary: str,
                         doc_storage_html: str, row_color: str = None) -> str:
    """Insere uma nova linha antes do fechamento da última </table> da página.

    Se row_color for informado (ex: "#E3FCEF"), aplica esse destaque de fundo
    nas células da linha, usando o mesmo atributo nativo que o editor do
    Confluence usa para colorir células de tabela (data-highlight-colour).

    Ajuste esta função se a página tiver mais de uma tabela ou se você quiser
    inserir em um ponto específico (ex: sempre no topo, logo após o <thead>).
    """
    color_attr = f' data-highlight-colour="{row_color}"' if row_color else ""
    new_row = f"""
    <tr>
      <td{color_attr} style="text-align: center;"><a href="{JIRA_URL}/browse/{issue_key}">{issue_key}</a></td>
      <td{color_attr} style="text-align: center;">{summary}</td>
      <td{color_attr}>{doc_storage_html}</td>
    </tr>
    """
    idx = page_storage_html.rfind("</table>")
    if idx == -1:
        raise ValueError("Nenhuma <table> encontrada na página de destino.")
    return page_storage_html[:idx] + new_row + page_storage_html[idx:]


def update_confluence_page(page_id: str, title: str, new_body: str,
                            current_version: int):
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
    body = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": current_version + 1},
        "body": {"storage": {"value": new_body, "representation": "storage"}},
    }
    resp = requests.put(url, auth=auth, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


def sync_multiple_issues(issue_keys: list, fix_version: str = None,
                          page_id: str = None):
    """
    Sincroniza VÁRIAS issues de uma vez na mesma página do Confluence,
    fazendo apenas 1 leitura e 1 gravação da página no final (mais rápido
    e evita criar várias versões desnecessárias no histórico da página).

    Uso:
        sync_multiple_issues(
            issue_keys=["CWM-2867", "CWM-2904", "CWM-2865", "CWM-3041"],
            fix_version="4.0.2501.1027"
        )
    """
    created_now = False
    if not page_id:
        if not fix_version:
            raise ValueError("Informe page_id ou fix_version.")
        page_id = find_page_id_by_title(SPACE_KEY, fix_version)
        if not page_id:
            print(f"[info] Página '{fix_version}' não existe ainda no espaço "
                  f"'{SPACE_KEY}'. Criando com o cabeçalho padrão...")
            new_page = create_confluence_page(SPACE_KEY, fix_version)
            page_id = new_page["id"]
            created_now = True

    # Busca a página UMA vez (mesmo se acabou de ser criada, para pegar a
    # versão/estrutura mais atual retornada pela API)
    page = get_confluence_page(page_id)
    current_body = page["body"]["storage"]["value"]
    current_version = page["version"]["number"]
    title = page["title"]

    updated_body = current_body
    synced = []
    skipped = []

    for issue_key in issue_keys:
        summary, adf_content, issue_type = get_issue_documentation(issue_key)
        if not adf_content:
            print(f"[skip] {issue_key} não possui conteúdo no campo Documentation.")
            skipped.append(issue_key)
            continue

        row_color = ISSUE_TYPE_COLORS.get(issue_type, DEFAULT_ROW_COLOR)
        if issue_type not in ISSUE_TYPE_COLORS:
            print(f"[aviso] {issue_key}: tipo '{issue_type}' não mapeado em "
                  f"ISSUE_TYPE_COLORS, linha será inserida sem cor.")

        doc_storage_html = convert_adf_to_storage(adf_content)
        updated_body = append_row_to_table(updated_body, issue_key, summary,
                                            doc_storage_html, row_color=row_color)
        synced.append(issue_key)

    if not synced:
        print("[info] Nenhuma issue tinha conteúdo para sincronizar. Nada foi salvo.")
        return

    # Salva a página UMA vez, já com todas as linhas novas
    update_confluence_page(page_id, title, updated_body, current_version)

    print(f"[ok] {len(synced)} issue(s) sincronizada(s) na página '{title}' (ID {page_id}): {synced}")
    if skipped:
        print(f"[skip] {len(skipped)} issue(s) ignorada(s) por falta de conteúdo: {skipped}")


def sync_issue_to_confluence(issue_key: str, fix_version: str = None,
                              page_id: str = None):
    """
    Sincroniza UMA ÚNICA issue com a página do Confluence correspondente.
    Para várias issues de uma vez, use sync_multiple_issues() em vez desta.

    Você pode informar:
      - page_id diretamente (se já souber o ID da página), OU
      - fix_version (ex: "4.0.2501.1027") para o script descobrir o page_id
        automaticamente, buscando a página com esse título dentro do
        espaço único definido em SPACE_KEY.
    """
    sync_multiple_issues([issue_key], fix_version=fix_version, page_id=page_id)


if __name__ == "__main__":
    # Exemplo 1: uma única issue
    # sync_issue_to_confluence(issue_key="CWM-2874", fix_version="4.0.2501.1027")

    # Exemplo 2: lista inteira de issues, tudo na mesma página, de uma vez
    lista_de_tarefas = [
        "CWM-2867", "CWM-2904", "CWM-2865", "CWM-3041", "CWM-2871",
        "CWM-2997", "CWM-2922", "CWM-2998", "CWM-2547", "CWM-2368",
        "CWM-2994", "CWM-2680", "CWM-2690", "CWM-2737", "CWM-2890",
        "CWM-2414", "CWM-2837", "CWM-2794", "CWM-2555", "CWM-3062",
        "CWM-3050",
    ]
    sync_multiple_issues(lista_de_tarefas, fix_version="4.0.2501.1027")