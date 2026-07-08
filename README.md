# Sincronização Jira → Confluence (Documentação)

Este script automatiza o envio do conteúdo do campo **Documentation** das issues do Jira para as páginas de release do Confluence (ex: `4.0.2501.1027`), formatando tudo automaticamente: cabeçalho, legenda, cores por tipo de issue e alinhamento das colunas.

---

## 1. O que o script faz

Para cada issue que você informar, o script:

1. Busca no Jira: o **resumo** (summary), o **tipo** (Melhoria/Bug) e o conteúdo do campo **Documentation**
2. Converte esse conteúdo do formato interno do Jira (ADF) para o formato que o Confluence entende (Storage Format)
3. Encontra a página do Confluence correspondente à versão (pelo nome, ex: "4.0.2501.1027")
   - **Se a página já existe:** apenas adiciona uma linha nova na tabela
   - **Se a página não existe:** cria a página do zero, dentro da pasta correta, já com o cabeçalho padrão (banner verde + legenda + tabela vazia), e então adiciona as linhas
4. Colore cada linha da tabela: **verde claro** para issues do tipo Melhoria, **vermelho claro** para Bug
5. Centraliza as colunas **Chave** e **Resumo** (a coluna Documentação permanece alinhada à esquerda, por ter texto formatado)
6. Salva a página no Confluence **uma única vez**, mesmo processando várias issues ao mesmo tempo

---

## 2. Estrutura de arquivos do projeto

```
versoes-tarefas/
├── .venv/                     # ambiente virtual do Python (não mexer)
├── .env                       # credenciais (NUNCA compartilhar ou subir pro Git)
├── .gitignore                 # garante que .env e .venv não vão pro Git
├── requirements.txt           # lista de bibliotecas necessárias
└── jira_confluence_sync.py    # o script principal
```

---

## 3. Configuração (fazer uma vez só)

### 3.1. Arquivo `.env`

Crie um arquivo chamado `.env` na raiz do projeto com:

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

### 3.2. Constantes fixas no topo do script

Essas já vêm configuradas, mas é bom saber o que cada uma significa:

```python
JIRA_URL = "https://nimitz.atlassian.net"
CONFLUENCE_URL = "https://nimitz.atlassian.net/wiki"
SPACE_KEY = "DPU"                      # espaço único do Confluence usado por todas as verticais
DEFAULT_ANCESTOR_ID = "4911792138"     # ID da pasta "CRM - Notas de versão 2026"
```

### 3.3. Mapeamento de cores por tipo de issue

```python
ISSUE_TYPE_COLORS = {
    "Melhoria": "#E3FCEF",   # verde claro
    "Improve": "#E3FCEF",
    "Bug": "#FFEBE6",        # vermelho claro
    "Erro": "#FFEBE6",
}
```

Se algum tipo de issue do seu Jira não estiver na lista, o script avisa no terminal (`[aviso] ... tipo não mapeado`) e insere a linha sem cor — não trava o processo. Basta adicionar o nome exato do tipo aqui se quiser que ele seja colorido também.

---

## 4. Como executar

### 4.1. Ativar o ambiente virtual

No terminal, dentro da pasta do projeto:

**CMD (Prompt de Comando do Windows):**
```cmd
.venv\Scripts\activate.bat
```

**Git Bash:**
```bash
source .venv/Scripts/activate
```

Quando ativo, o prompt mostra `(.venv)` no início da linha.

### 4.2. Instalar as dependências (só na primeira vez, ou se `requirements.txt` mudar)

```bash
pip install -r requirements.txt
```

### 4.3. Editar a lista de tarefas a sincronizar

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

> ⚠️ **Importante:** o valor de `fix_version` precisa ser **idêntico** ao título da página no Confluence (ou ao valor que a página vai receber, se ainda não existir). Diferenças de espaço ou caracteres impedem o script de encontrar/criar a página certa.

### 4.4. Rodar o script

```bash
python jira_confluence_sync.py
```

---

## 5. O que esperar no terminal

**Página já existe — sucesso:**
```
[ok] 21 issue(s) sincronizada(s) na página '4.0.2501.1031' (ID 123456789): [...]
```

**Página não existe — criação automática:**
```
[info] Página '4.0.2501.1031' não existe ainda no espaço 'DPU'. Criando com o cabeçalho padrão...
[ok] Página vazia '4.0.2501.1031' criada (ID 123456789). Aplicando cabeçalho...
[ok] Cabeçalho aplicado com sucesso na página '4.0.2501.1031' (ID 123456789).
[ok] 21 issue(s) sincronizada(s) na página '4.0.2501.1031' (ID 123456789): [...]
```

**Alguma issue sem conteúdo no campo Documentation (não trava, só avisa):**
```
[skip] CWM-3050 não possui conteúdo no campo Documentation.
...
[skip] 1 issue(s) ignorada(s) por falta de conteúdo: ['CWM-3050']
```

---

## 6. Erros comuns e como resolver

| Erro no terminal | Causa | Solução |
|---|---|---|
| `KeyError: 'JIRA_EMAIL'` | Variável faltando ou nome errado no `.env` | Confira se o `.env` tem exatamente `JIRA_EMAIL`, `JIRA_API_TOKEN`, `CONFLUENCE_CUSTOM_FIELD_DOC` |
| `401 Unauthorized` | E-mail ou token errado/expirado | Gere um novo token em id.atlassian.com e atualize o `.env` |
| `404 Not Found` (na issue) | Chave da issue não existe ou está digitada errada | Confira a chave (ex: `CWM-2874`) direto no Jira |
| `Nenhuma página encontrada no espaço 'DPU'...` (com `page_id` fixo) | Título da versão não bate com o título da página | Confira se não há espaços extras ou caracteres diferentes |
| `[skip] ... não possui conteúdo no campo Documentation` | Campo customizado errado, ou a issue realmente está vazia nesse campo | Confira o `CONFLUENCE_CUSTOM_FIELD_DOC` no `.env` |
| `bash: pip: command not found` | Ambiente virtual não está ativado nessa aba do terminal | Rode novamente o comando de ativação (seção 4.1) |
| `ERROR: Could not open requirements file` | O arquivo `requirements.txt` não existe na pasta | Crie o arquivo com `requests` e `python-dotenv`, uma biblioteca por linha |

---

## 7. Perguntas frequentes

**Preciso rodar isso toda vez que fechar uma issue?**
Por enquanto, sim — o script roda manualmente. Ele foi desenhado para também poder ser chamado automaticamente por um webhook do Jira Automation no futuro, mas essa parte ainda não foi configurada.

**Posso sincronizar issues de versões diferentes na mesma execução?**
Não diretamente — cada chamada de `sync_multiple_issues()` grava numa única página/versão. Se precisar sincronizar duas versões diferentes, rode duas vezes (ou adicione duas chamadas no final do script), uma para cada `fix_version`.

**O que acontece se eu rodar o script duas vezes com a mesma lista?**
As issues serão adicionadas novamente como linhas duplicadas na tabela — o script não verifica se uma issue já foi sincronizada antes. Tenha cuidado para não rodar duas vezes com a mesma lista sem necessidade.

**Onde acompanho o histórico de alterações da página?**
No próprio Confluence — cada vez que o script salva a página, isso gera uma nova versão no histórico da página (visível em "..." → "Page History").
