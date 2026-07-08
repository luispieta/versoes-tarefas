import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = "https://nimitz.atlassian.net"
CONFLUENCE_URL = "https://nimitz.atlassian.net/wiki"

EMAIL = os.environ["JIRA_EMAIL"]
API_TOKEN = os.environ["JIRA_API_TOKEN"]
CUSTOM_FIELD_DOC = os.environ["CONFLUENCE_CUSTOM_FIELD_DOC"]

SPACE_KEY = "DPU"
DEFAULT_ANCESTOR_ID = "4911792138"

ISSUE_TYPE_COLORS = {
    "Melhoria": "#E3FCEF",
    "Improve": "#E3FCEF",
    "Bug": "#FFEBE6",
    "Erro": "#FFEBE6",
}
DEFAULT_ROW_COLOR = None

BANNER_PREFIX = "CRM"
BANNER_COLOR = "#57D9A3"
LEGEND_IMPROVEMENT_COLOR = "#E3FCEF"
LEGEND_IMPROVEMENT_TEXT = "Melhorias e implementações de novas funcionalidade."
LEGEND_BUG_COLOR = "#FFEBE6"
LEGEND_BUG_TEXT = "Correções e ajustes de validações incorretas."

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Content-Type": "application/json"}


def get_issue_documentation(issue_key: str):
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    resp = requests.get(url, auth=auth, headers=headers)
    resp.raise_for_status()
    fields = resp.json()["fields"]
    summary = fields.get("summary")
    adf_content = fields.get(CUSTOM_FIELD_DOC)
    issue_type = fields.get("issuetype", {}).get("name")
    return summary, adf_content, issue_type


def convert_adf_to_storage(adf_content: dict) -> str:
    url = f"{CONFLUENCE_URL}/rest/api/contentbody/convert/storage"
    body = {
        "value": json.dumps(adf_content),
        "representation": "atlas_doc_format",
    }
    resp = requests.post(url, auth=auth, headers=headers, json=body)
    if not resp.ok:
        print(f"[erro convert_adf_to_storage] status={resp.status_code} body={resp.text}")
    resp.raise_for_status()
    return resp.json()["value"]


def get_confluence_page(page_id: str):
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=body.storage,version"
    resp = requests.get(url, auth=auth, headers=headers)
    resp.raise_for_status()
    return resp.json()


def find_page_id_by_title(space_key: str, title: str):
    url = f"{CONFLUENCE_URL}/rest/api/content"
    params = {"spaceKey": space_key, "title": title, "expand": "version"}
    resp = requests.get(url, auth=auth, headers=headers, params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def build_header_block(version_title: str) -> str:
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


def get_space_id(space_key: str) -> str:
    url = f"{CONFLUENCE_URL}/rest/api/space/{space_key}"
    resp = requests.get(url, auth=auth, headers=headers)
    resp.raise_for_status()
    return resp.json()["id"]


def create_confluence_page(space_key: str, title: str, ancestor_id: str = None) -> dict:
    space_id = get_space_id(space_key)

    url = f"{CONFLUENCE_URL}/api/v2/pages"
    body = {
        "spaceId": space_id,
        "status": "current",
        "title": title,
        "body": {
            "representation": "storage",
            "value": "<p>Página criada automaticamente. Aguardando conteúdo...</p>",
        },
    }
    if ancestor_id:
        body["parentId"] = ancestor_id

    resp = requests.post(url, auth=auth, headers=headers, json=body)
    if not resp.ok:
        print(f"[erro create_confluence_page] status={resp.status_code} body={resp.text}")
    resp.raise_for_status()
    created = resp.json()
    page_id = created["id"]
    print(f"[ok] Página vazia '{title}' criada (ID {page_id}, parent={ancestor_id}). Aplicando cabeçalho...")

    header_html = build_header_block(title)
    update_confluence_page(page_id, title, header_html, current_version=1)

    print(f"[ok] Cabeçalho aplicado com sucesso na página '{title}' (ID {page_id}).")
    return created


def append_row_to_table(page_storage_html: str, issue_key: str, summary: str,
                         doc_storage_html: str, row_color: str = None) -> str:
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


def update_confluence_page(page_id: str, title: str, new_body: str, current_version: int):
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
                          page_id: str = None, ancestor_id: str = None):
    if not ancestor_id:
        ancestor_id = DEFAULT_ANCESTOR_ID

    if not page_id:
        if not fix_version:
            raise ValueError("Informe page_id ou fix_version.")
        page_id = find_page_id_by_title(SPACE_KEY, fix_version)
        if not page_id:
            print(f"[info] Página '{fix_version}' não existe ainda no espaço '{SPACE_KEY}'. Criando com o cabeçalho padrão...")
            new_page = create_confluence_page(SPACE_KEY, fix_version, ancestor_id=ancestor_id)
            page_id = new_page["id"]

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
            print(f"[aviso] {issue_key}: tipo '{issue_type}' não mapeado em ISSUE_TYPE_COLORS, linha será inserida sem cor.")

        doc_storage_html = convert_adf_to_storage(adf_content)
        updated_body = append_row_to_table(updated_body, issue_key, summary, doc_storage_html, row_color=row_color)
        synced.append(issue_key)

    if not synced:
        print("[info] Nenhuma issue tinha conteúdo para sincronizar. Nada foi salvo.")
        return

    update_confluence_page(page_id, title, updated_body, current_version)

    print(f"[ok] {len(synced)} issue(s) sincronizada(s) na página '{title}' (ID {page_id}): {synced}")
    if skipped:
        print(f"[skip] {len(skipped)} issue(s) ignorada(s) por falta de conteúdo: {skipped}")


def sync_issue_to_confluence(issue_key: str, fix_version: str = None, page_id: str = None):
    sync_multiple_issues([issue_key], fix_version=fix_version, page_id=page_id)


if __name__ == "__main__":
    lista_de_tarefas = [
        "CWM-2867",
    ]
    sync_multiple_issues(lista_de_tarefas, fix_version="4.0.2501.1030")