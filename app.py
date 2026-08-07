import io
import contextlib
import traceback

from flask import Flask, render_template_string, request


from jira_confluence_sync import (
    sync_multiple_issues,
    SPACE_KEY,
    DEFAULT_ANCESTOR_ID,
    ISSUE_TYPE_COLORS,
)

app = Flask(__name__)

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Sincronizar Jira &rarr; Confluence</title>
  <style>
    body {
      font-family: -apple-system, Segoe UI, Roboto, sans-serif;
      max-width: 720px;
      margin: 40px auto;
      padding: 0 20px;
      color: #172B4D;
      background: #F4F5F7;
    }
    h1 { font-size: 22px; }
    .card {
      background: white;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 1px 3px rgba(9,30,66,0.15);
      margin-bottom: 20px;
    }
    label { display: block; font-weight: 600; margin-bottom: 6px; margin-top: 16px; }
    textarea, input[type=text] {
      width: 100%;
      box-sizing: border-box;
      padding: 10px;
      border: 1px solid #DFE1E6;
      border-radius: 4px;
      font-family: monospace;
      font-size: 14px;
    }
    textarea { height: 140px; resize: vertical; }
    small { color: #6B778C; }
    button {
      margin-top: 20px;
      background: #0052CC;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 4px;
      font-size: 15px;
      cursor: pointer;
    }
    button:hover { background: #0747A6; }
    pre {
      background: #172B4D;
      color: #E3FCEF;
      padding: 16px;
      border-radius: 6px;
      overflow-x: auto;
      white-space: pre-wrap;
      font-size: 13px;
    }
    .error { color: #DE350B; font-weight: 600; }
    .info-box {
      background: #DEEBFF;
      border-radius: 4px;
      padding: 12px 16px;
      font-size: 13px;
      margin-bottom: 16px;
    }
  </style>
</head>
<body>
  <h1>Sincronizar Jira &rarr; Confluence</h1>

  <div class="info-box">
    Space: <strong>{{ space_key }}</strong> &middot;
    Pasta padrão (ancestor): <strong>{{ ancestor_id }}</strong> &middot;
    Tipos mapeados: <strong>{{ tipos }}</strong>
  </div>

  <div class="card">
    <form method="POST">
      <label for="fix_version">Vers&atilde;o de destino (fix_version)</label>
      <input type="text" id="fix_version" name="fix_version"
             placeholder="ex: 4.0.2501.1031" value="{{ fix_version or '' }}" required>
      <small>Precisa ser id&ecirc;ntico ao t&iacute;tulo da p&aacute;gina no Confluence.
      Se n&atilde;o existir, o script cria a p&aacute;gina automaticamente.</small>

      <label for="issue_keys">Chaves das issues</label>
      <textarea id="issue_keys" name="issue_keys"
                placeholder="CWM-2867, CWM-2904, CWM-2865&#10;(uma por linha ou separadas por v&iacute;rgula)">{{ issue_keys or '' }}</textarea>
      <small>Cole a lista de tarefas, uma por linha ou separadas por v&iacute;rgula.</small>

      <button type="submit">Sincronizar</button>
    </form>
  </div>

  {% if log %}
  <div class="card">
    <h3>Resultado</h3>
    {% if error %}<p class="error">Ocorreu um erro durante a execu&ccedil;&atilde;o:</p>{% endif %}
    <pre>{{ log }}</pre>
  </div>
  {% endif %}
</body>
</html>
"""


def parse_issue_keys(raw_text: str) -> list:
    """Aceita chaves separadas por vírgula, quebra de linha, ou espaço."""
    raw_text = raw_text.replace(",", "\n").replace(" ", "\n")
    keys = [line.strip() for line in raw_text.splitlines() if line.strip()]
    seen = set()
    unique_keys = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique_keys.append(k)
    return unique_keys


@app.route("/", methods=["GET", "POST"])
def home():
    log = None
    error = False
    fix_version = None
    issue_keys_raw = None

    if request.method == "POST":
        fix_version = request.form.get("fix_version", "").strip()
        issue_keys_raw = request.form.get("issue_keys", "")
        issue_keys = parse_issue_keys(issue_keys_raw)

        buffer = io.StringIO()
        try:
            if not issue_keys:
                raise ValueError("Nenhuma chave de issue foi informada.")

            with contextlib.redirect_stdout(buffer):
                print(f"Sincronizando {len(issue_keys)} issue(s) para a versão "
                      f"'{fix_version}'...\n")
                sync_multiple_issues(issue_keys, fix_version=fix_version)
        except Exception:
            error = True
            buffer.write("\n" + traceback.format_exc())

        log = buffer.getvalue()

    return render_template_string(
        PAGE_TEMPLATE,
        log=log,
        error=error,
        fix_version=fix_version,
        issue_keys=issue_keys_raw,
        space_key=SPACE_KEY,
        ancestor_id=DEFAULT_ANCESTOR_ID,
        tipos=", ".join(ISSUE_TYPE_COLORS.keys()),
    )


if __name__ == "__main__":
    print("Abra no navegador: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)