# Sincronização Jira → Confluence (Documentação)

Este projeto automatiza o envio do conteúdo do campo **Documentation** das issues do Jira para as páginas de release do Confluence (ex: `4.0.2501.1027`), formatando tudo automaticamente: cabeçalho, legenda, cores por tipo de issue e alinhamento das colunas.

Pode ser usado de duas formas:
- **Direto pelo script** (`jira_confluence_sync.py`), editando a lista de issues no código
- **Pela interface web local** (`app.py`), colando as issues num formulário no navegador

---

## 1. O que o sistema faz

Para cada issue que você informar, ele:

1. Busca no Jira: o **resumo** (summary), o **tipo** (Melhoria/Bug) e o conteúdo do campo **Documentation**
2. Converte esse conteúdo do formato interno do Jira (ADF) para o formato que o Confluence entende (Storage Format)
3. Encontra a página do Confluence correspondente à versão (pelo nome, ex: "4.0.2501.1027")
   - **Se a página já existe:** apenas adiciona uma linha nova na tabela
   - **Se a página não existe:** cria a página do zero, **dentro da pasta correta** (ex: "CRM - Notas de versão 2026"), já com o cabeçalho padrão (banner verde + legenda + tabela vazia), e então adiciona as linhas
4. Colore cada linha da tabela: **verde claro** para issues do tipo Melhoria, **vermelho claro** para Bug
5. Centraliza as colunas **Chave** e **Resumo** (a coluna Documentação permanece alinhada à esquerda, por ter texto formatado)
6. Salva a página no Confluence **uma única vez**, mesmo processando várias issues ao mesmo tempo

---

## 2. Estrutura de arquivos do projeto

```
versoes-tarefas/
├── .venv/                     # ambiente virtual do Python (não versionar, não copiar entre máquinas)
├── .env                       # credenciais (NUNCA compartilhar ou subir pro Git)
├── .gitignore                 # garante que .env e .venv não vão pro Git
├── requirements.txt           # lista de bibliotecas necessárias
├── setup.bat                  # instalação automática (Windows) — rodar 1x
├── setup.sh                   # instalação automática (Git Bash/macOS/Linux) — rodar 1x
├── rodar_interface.bat        # abre a interface web (duplo clique, Windows)
├── rodar_script.bat           # roda o script direto (duplo clique, Windows)
├── rodar_poller.bat           # roda o modo automático (alvo do Agendador de Tarefas)
├── rodar_poller_dryrun.bat    # simula o modo automático (dry-run: não escreve no Confluence)
├── jira_confluence_sync.py    # o script principal (lógica de sincronização)
├── poller.py                  # modo automático: lê a planilha e publica as tarefas "Finalizada"
├── app.py                     # interface web local (opcional, usa as funções do script principal)
└── sync.log                   # log das execuções automáticas (gerado em runtime, não versionar)
```

> O código de `jira_confluence_sync.py` está sem comentários por preferência do time — esta documentação é a referência para entender o que cada parte faz.

---

## 3. Configuração (fazer uma vez por máquina)

### 3.0. Opção rápida: setup automático

Em vez de rodar os comandos manualmente (seções 3.1 a 3.3), você pode usar o script de instalação incluído no projeto, que faz tudo de uma vez: cria o `.venv`, instala as dependências e cria um `.env` de exemplo.

**Windows (CMD ou clique duplo no arquivo):**
```cmd
setup.bat
```

**Git Bash / macOS / Linux:**
```bash
./setup.sh
```

Depois de rodar, só falta **editar o `.env`** com as credenciais reais (ele é criado com valores de exemplo, que precisam ser substituídos) — o script avisa isso no final.

> Se preferir entender/rodar cada passo manualmente (ou algo no `setup` der problema), siga as seções 3.1 a 3.3 abaixo normalmente.

### 3.1. Criar e ativar o ambiente virtual

Toda máquina nova (ou todo clone/download do projeto) **não vem com o `.venv`** — ele é local e nunca deve ser copiado ou versionado. É preciso criar do zero:

**CMD (Prompt de Comando do Windows):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Git Bash:**
```bash
python -m venv .venv
source .venv/Scripts/activate
```

Quando ativo, o prompt mostra `(.venv)` no início da linha.

> Se aparecer o erro `O sistema não pode encontrar o caminho especificado` ao tentar ativar, significa que o `.venv` ainda não foi criado nessa máquina — rode o `python -m venv .venv` primeiro.

### 3.2. Instalar as dependências

```bash
pip install -r requirements.txt
```

Ou, uma por uma:
```bash
pip install requests
pip install python-dotenv
pip install flask
```

Conferir se instalou certo:
```bash
pip list
```

### 3.3. Criar o arquivo `.env`

O `.env` também **não vem versionado** (por segurança) — precisa ser criado manualmente em cada máquina. Crie um arquivo chamado `.env` na raiz do projeto com:

```
JIRA_EMAIL=seu-email@empresa.com
JIRA_API_TOKEN=seu-token-aqui
CONFLUENCE_CUSTOM_FIELD_DOC=customfield_XXXXX
```

| Variável | O que é | Onde conseguir |
|---|---|---|
| `JIRA_EMAIL` | E-mail da conta usada para autenticar | O e-mail de login no Atlassian |
| `JIRA_API_TOKEN` | Token de acesso à API | https://id.atlassian.com/manage-profile/security/api-tokens |
| `CONFLUENCE_CUSTOM_FIELD_DOC` | ID do campo "Documentation" no Jira | `GET https://nimitz.atlassian.net/rest/api/3/field` → procure `"name": "Documentation"` e copie o `"id"` |

### 3.4. Constantes fixas no topo do script

```python
JIRA_URL = "https://nimitz.atlassian.net"
CONFLUENCE_URL = "https://nimitz.atlassian.net/wiki"
SPACE_KEY = "DPU"                      # espaço único do Confluence usado por todas as verticais
DEFAULT_ANCESTOR_ID = "4911792138"     # ID da pasta "CRM - Notas de versão 2026"
```

### 3.5. Mapeamento de cores por tipo de issue

```python
ISSUE_TYPE_COLORS = {
    "Melhoria": "#E3FCEF",   # verde claro
    "Improve": "#E3FCEF",
    "Bug": "#FFEBE6",        # vermelho claro
    "Erro": "#FFEBE6",
}
```

Se algum tipo de issue do seu Jira não estiver na lista, o sistema avisa no terminal (`[aviso] ... tipo não mapeado`) e insere a linha sem cor — não trava o processo. Basta adicionar o nome exato do tipo aqui se quiser que ele seja colorido também.

---

## 4. Como executar — Opção A: pelo script direto

### 4.1. Editar a lista de tarefas a sincronizar

Abra `jira_confluence_sync.py`, vá até o final do arquivo (`if __name__ == "__main__":`) e edite:

```python
lista_de_tarefas = [
    "CWM-2867", "CWM-2904", "CWM-2865", "CWM-3041",
    # ... cole aqui as chaves das issues que você quer sincronizar
]
sync_multiple_issues(lista_de_tarefas, fix_version="4.0.2501.1031")
```

- **`lista_de_tarefas`**: as chaves das issues do Jira (uma lista, entre colchetes, separadas por vírgula)
- **`fix_version`**: o nome exato da versão/página de destino no Confluence (ex: `"4.0.2501.1031"`)

> ⚠️ **Importante:** o valor de `fix_version` precisa ser **idêntico** ao título da página no Confluence (ou ao valor que a página vai receber, se ainda não existir). Diferenças de espaço ou caracteres impedem o sistema de encontrar/criar a página certa.

### 4.2. Rodar

**Windows — atalho rápido:** dê duplo clique em `rodar_script.bat`.

**Ou manualmente:**
```bash
python jira_confluence_sync.py
```

---

## 5. Como executar — Opção B: pela interface web local

Mais prático no dia a dia: não precisa editar código, só colar a lista de issues num formulário.

### 5.1. Rodar o servidor local

**Windows — atalho rápido:** dê duplo clique em `rodar_interface.bat` (ele já usa o Python de dentro do `.venv`, não precisa ativar nada manualmente).

**Ou manualmente**, com o `.venv` ativado e `app.py` na mesma pasta de `jira_confluence_sync.py`:

```bash
python app.py
```

### 5.2. Abrir no navegador

```
http://127.0.0.1:5000
```

### 5.3. Usar o formulário

- **Versão de destino:** o `fix_version` (ex: `4.0.2501.1031`)
- **Chaves das issues:** cole a lista de tarefas — aceita separadas por vírgula, espaço, ou uma por linha (pode colar direto do Jira sem formatar)
- Clique em **Sincronizar** — o resultado (os mesmos logs `[ok]`, `[skip]`, `[aviso]` do terminal) aparece na própria página

Para parar o servidor, volte ao terminal onde ele está rodando e aperte `Ctrl+C`.

---

## 6. Sobre as funções principais (referência rápida)

| Função | O que faz |
|---|---|
| `sync_multiple_issues(issue_keys, fix_version, ...)` | Função principal. Processa uma lista de issues de uma vez, lendo e salvando a página do Confluence só uma vez. |
| `sync_issue_to_confluence(issue_key, fix_version, ...)` | Atalho para sincronizar **uma única issue**. Por baixo dos panos, chama `sync_multiple_issues` com uma lista de 1 item — não precisa de manutenção separada, herda todas as melhorias automaticamente. |
| `get_issue_documentation(issue_key)` | Busca no Jira o resumo, tipo e conteúdo do campo Documentation de uma issue. |
| `convert_adf_to_storage(adf_content)` | Converte o conteúdo do campo Documentation (formato ADF do Jira) para o formato que o Confluence entende (Storage Format). |
| `find_page_id_by_title(space_key, title)` | Procura se já existe uma página com aquele título de versão no Confluence. |
| `get_space_id(space_key)` | Descobre o ID numérico do espaço do Confluence (necessário para criar páginas usando a API v2). |
| `create_confluence_page(space_key, title, ancestor_id)` | Cria uma página nova já dentro da pasta certa, com o cabeçalho padrão (banner + legenda + tabela vazia). Usa a API v2 do Confluence, porque a API v1 não é confiável para definir a pasta pai na hora da criação. |
| `append_row_to_table(...)` | Monta e insere a linha nova (com cor e alinhamento) na tabela existente. |
| `update_confluence_page(...)` | Salva o conteúdo atualizado da página no Confluence. |
| `build_header_block(version_title)` | Monta o HTML do cabeçalho padrão (banner, legenda, título das colunas) usado em páginas novas. |

---

## 7. O que esperar no terminal

**Página já existe — sucesso:**
```
[ok] 21 issue(s) sincronizada(s) na página '4.0.2501.1031' (ID 123456789): [...]
```

**Página não existe — criação automática (já dentro da pasta certa):**
```
[info] Página '4.0.2501.1031' não existe ainda no espaço 'DPU'. Criando com o cabeçalho padrão...
[ok] Página vazia '4.0.2501.1031' criada (ID 123456789, parent=4911792138). Aplicando cabeçalho...
[ok] Cabeçalho aplicado com sucesso na página '4.0.2501.1031' (ID 123456789).
[ok] 21 issue(s) sincronizada(s) na página '4.0.2501.1031' (ID 123456789): [...]
```

**Alguma issue sem conteúdo no campo Documentation (não trava, só avisa):**
```
[skip] CWM-3050 não possui conteúdo no campo Documentation.
...
[skip] 1 issue(s) ignorada(s) por falta de conteúdo: ['CWM-3050']
```

**Tipo de issue não mapeado em ISSUE_TYPE_COLORS (linha inserida sem cor):**
```
[aviso] CWM-2999: tipo 'Tarefa' não mapeado em ISSUE_TYPE_COLORS, linha será inserida sem cor.
```

---

## 8. Erros comuns e como resolver

| Erro | Causa | Solução |
|---|---|---|
| `O sistema não pode encontrar o caminho especificado` (ao ativar o venv) | O `.venv` não existe nessa máquina ainda | Rode `python -m venv .venv` antes de ativar |
| `KeyError: 'JIRA_EMAIL'` | Variável faltando ou nome errado no `.env` | Confira se o `.env` tem exatamente `JIRA_EMAIL`, `JIRA_API_TOKEN`, `CONFLUENCE_CUSTOM_FIELD_DOC` |
| `401 Unauthorized` | E-mail ou token errado/expirado | Gere um novo token em id.atlassian.com e atualize o `.env` |
| `404 Not Found` (na issue) | Chave da issue não existe ou está digitada errada | Confira a chave (ex: `CWM-2874`) direto no Jira |
| `Nenhuma <table> encontrada na página de destino` | A página existe mas está vazia/sem tabela (ex: criada manualmente sem o cabeçalho padrão) | Adicione manualmente uma tabela na página, ou apague e deixe o sistema recriar do zero |
| `[skip] ... não possui conteúdo no campo Documentation` | Campo customizado errado, ou a issue realmente está vazia nesse campo | Confira o `CONFLUENCE_CUSTOM_FIELD_DOC` no `.env` |
| `bash: pip: command not found` | Ambiente virtual não está ativado nessa aba do terminal | Rode novamente o comando de ativação (seção 3.1) |
| `ERROR: Could not open requirements file` | O arquivo `requirements.txt` não existe na pasta | Confira se ele veio junto no download/clone do projeto |
| Página criada fora da pasta certa | `ancestor_id` não foi aplicado (bug já corrigido, ver seção 6) | Confirme que está usando a versão atual do script, com `create_confluence_page` usando a API v2 |

---

## 9. Perguntas frequentes

**Preciso rodar isso toda vez que fechar uma issue?**
Não é obrigatório. Além das duas formas manuais (script e interface), existe o **modo automático** (seção 10): o `poller.py` lê a planilha de versões e publica sozinho as tarefas marcadas como `Finalizada`, e pode ser agendado no Windows para rodar de tempos em tempos.

**Posso sincronizar issues de versões diferentes na mesma execução?**
Não diretamente — cada chamada de `sync_multiple_issues()` grava numa única página/versão. Se precisar sincronizar duas versões diferentes, rode duas vezes (ou adicione duas chamadas no final do script, ou use a interface duas vezes, uma para cada `fix_version`).

**O que acontece se eu rodar duas vezes com a mesma lista?**
Nada de errado: antes de inserir cada linha, o sistema verifica se a issue **já está** na página (pelo link `/browse/CHAVE`) e, se estiver, ignora com `[skip] ... já está na página`. Ou seja, é seguro reprocessar — é justamente isso que permite o modo automático rodar de tempos em tempos sem duplicar linhas.

**Onde acompanho o histórico de alterações da página?**
No próprio Confluence — cada vez que o sistema salva a página, isso gera uma nova versão no histórico (visível em "..." → "Page History").

**Preciso reinstalar tudo se copiar o projeto pra outra máquina?**
Sim: crie o `.venv` do zero (`python -m venv .venv`), instale as dependências (`pip install -r requirements.txt`) e recrie o `.env` manualmente — nenhum desses três vai junto quando você clona ou baixa o projeto.

---

## 10. Geração automática ao finalizar tarefas (modo automático)

Em vez de colar listas manualmente, o `poller.py` usa a **planilha de versões** como fonte de
verdade e publica sozinho as tarefas que já estão prontas.

### 10.1. Como funciona

```
[Jira] --(add-on Sheet Director, já existe)--> [Planilha "Versões 2026"]
                                                        |
                              (Agendador de Tarefas do Windows, a cada N min)
                                                        v
                          poller.py descobre sozinho as abas de versão (1031, 1032, ...)
                          e, em cada uma, filtra as linhas com Status = "Finalizada"
                                                        |
                        para cada tarefa: lê o campo Documentation no Jira
                                                        v
                        publica a linha na página "4.0.2501.<aba>" do Confluence
                                    (com deduplicação: não repete linha)
```

- **Não é preciso manter lista de versões:** o poller lê a planilha e descobre automaticamente as
  abas de versão (nomes com 4 dígitos, ex.: `1031`, `1032`). Novas versões são pegas sozinhas.
- A **aba** define a versão: aba `1031` → página `4.0.2501.1031` (prefixo `4.0.2501.`).
- O gatilho é a coluna **Status** igual a **`Finalizada`** (as tarefas da seção "Previstas para a
  versão", ainda não finalizadas, são ignoradas).
- O **conteúdo** de cada nota continua vindo do campo **Documentation** do Jira (não da planilha).
- Rodar repetidamente é seguro e barato: a deduplicação ignora o que já está publicado, então as
  versões antigas (já 100% publicadas) só são lidas e puladas, sem reescrever nada.

### 10.2. Pré-requisito: deixar a planilha legível pelo script

O script lê a planilha por uma URL de export CSV, que **exige que a planilha esteja pública**:

1. Abra a planilha → **Compartilhar** → em "Acesso geral", escolha **"Qualquer pessoa com o link"**
   com permissão **Leitor**.

> ⚠️ **Atenção de segurança:** isso deixa os dados da planilha (tarefas, desenvolvedores, clientes)
> acessíveis a qualquer pessoa **na internet** que tenha o link. Confirme que isso é aceitável pela
> política da empresa. Alternativa mais fechada (não implementada aqui): usar a **API do Google
> Sheets com uma conta de serviço**, que funciona mesmo com a planilha privada.

### 10.3. Configuração do `.env` (opcional)

**Não é obrigatório mexer no `.env`** — o poller já vem com os valores certos embutidos e descobre
as abas de versão sozinho. Só acrescente algo se quiser sobrescrever o padrão:

```
SHEET_ID=1ESvAnD9PpDXRqRWoVDATG_GVXKqZslEgQvs0tFXocNc   # planilha de versões
VERSION_PREFIX=4.0.2501.                                 # prefixo do título das páginas
DONE_STATUS=Finalizada                                   # valor da coluna Status que dispara a nota
SHEET_TABS=                                              # (opcional) fixe abas: 1032,1033 — vazio = auto
```

- `SHEET_TABS` **vazio ou ausente** = descobre e varre todas as abas de versão automaticamente
  (recomendado — você nunca precisa editar isso). Preencha (ex.: `SHEET_TABS=1032,1033`) só se
  quiser limitar a processamento a versões específicas.

### 10.4. Testar manualmente antes de agendar

**Passo 1 — simular (dry-run), sem escrever nada:** mostra o que *seria* publicado.

```bash
.venv\Scripts\python.exe poller.py --dry-run
```

(No Windows, dá pra dar duplo clique em `rodar_poller_dryrun.bat`.) A saída indica, por versão,
quantas tarefas **novas** entrariam, quais chaves, e se a página seria criada — por exemplo:

```
[dry-run] Versão 4.0.2501.1031: nada novo — 17 tarefa(s) já publicada(s).
[dry-run] Versão 4.0.2501.1032: 2 NOVA(S) a publicar: ['CWM-3200', 'CWM-3201']  (5 já na página)
=== Poller finalizado [DRY-RUN]. 2 tarefa(s) NOVA(S) seriam publicadas. ===
```

**Passo 2 — execução real:**

```bash
.venv\Scripts\python.exe poller.py
```

Confira o resultado no terminal e no arquivo `sync.log`. Rode **de novo** e confirme que as linhas
**não** duplicam (deve aparecer `[skip] ... já está na página`).

### 10.5. Agendamento no Windows (já configurado: 12h e 17h)

Existe uma tarefa agendada chamada **"Notas de versao - poller"** que roda o poller **duas vezes por
dia, às 12:00 e às 17:00**, usando `pythonw.exe` (sem abrir janela). Ela roda enquanto o usuário
estiver conectado ao Windows.

Comandos úteis (PowerShell) para gerenciar:

```powershell
# Ver estado e próximo disparo
Get-ScheduledTaskInfo -TaskName "Notas de versao - poller"

# Rodar agora, sob demanda (sem esperar o horário)
Start-ScheduledTask -TaskName "Notas de versao - poller"

# Desativar temporariamente / reativar
Disable-ScheduledTask -TaskName "Notas de versao - poller"
Enable-ScheduledTask  -TaskName "Notas de versao - poller"

# Remover de vez
Unregister-ScheduledTask -TaskName "Notas de versao - poller" -Confirm:$false
```

Para **recriar** a tarefa (ou mudar os horários), rode em PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\versoes-tarefas\.venv\Scripts\pythonw.exe" -Argument '"C:\versoes-tarefas\poller.py"' -WorkingDirectory "C:\versoes-tarefas"
$t1 = New-ScheduledTaskTrigger -Daily -At 12:00
$t2 = New-ScheduledTaskTrigger -Daily -At 17:00
Register-ScheduledTask -TaskName "Notas de versao - poller" -Action $action -Trigger $t1,$t2 -Description "Publica notas de versao no Confluence. Roda 12h e 17h." -Force
```

> Para rodar **mesmo com o usuário deslogado**, edite a tarefa no Agendador de Tarefas (GUI),
> aba Geral → "Executar estando o usuário conectado ou não" — isso exige informar a senha do Windows.

Pronto: a partir daí, toda tarefa marcada como `Finalizada` na planilha (versão 1032 em diante) vira
nota de versão sozinha, no disparo das 12h ou 17h.

### 10.6. Recomendação de segurança (token exposto)

O `.env` atual contém um token de API real. Como boa prática — e porque ele já circulou —
**gere um novo token e revogue o antigo** em
https://id.atlassian.com/manage-profile/security/api-tokens, atualizando o `.env` em seguida.