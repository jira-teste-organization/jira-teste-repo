# jira-teste-repo

Repositório teste para jira

## Scripts Python

Esta seção descreve os scripts Python utilizados para automação de releases e validação de integração com Jira.

### Localização

Os scripts estão localizados em `.github/scripts/` e são executados como parte do workflow de automação de releases.

---

### 1. `validate_release.py`

**Propósito:** Valida se a branch candidata está alinhada com a Fix Version do Jira antes de uma release.

**Funcionalidades:**
- Busca todos os tickets da Fix Version especificada no Jira
- Extrai commits da branch candidata usando `git log`
- Identifica referências aos tickets (SCRUM-*, STM-*) nas mensagens de commit
- Detecta discrepâncias entre os commits na branch e os tickets do Jira
- Gera relatório em JSON e resumo legível para humanos

**Validações realizadas:**
- ✅ Todos os tickets da Fix Version foram mergeados?
- ✅ Existe algum commit sem rastreabilidade (sem referência a ticket)?
- ✅ Existe algum commit com ticket fora da Fix Version?

**Saída:**
- `release-validation-report.json` - Relatório estruturado com todos os detalhes
- Resumo em formato Markdown para visualização

**Variáveis de ambiente necessárias:**
```
JIRA_BASE_URL         # URL base do Jira
JIRA_EMAIL            # Email de autenticação
JIRA_API_TOKEN        # Token de API do Jira
JIRA_PROJECT_KEY      # Chave do projeto (ex: SCRUM)
RELEASE_NAME          # Nome da release/versão
CANDIDATE_BRANCH      # Branch candidata para release
```

**Exemplo de uso:**
```bash
export JIRA_BASE_URL="https://jira.example.com"
export JIRA_EMAIL="user@example.com"
export JIRA_API_TOKEN="seu_token_aqui"
export JIRA_PROJECT_KEY="SCRUM"
export RELEASE_NAME="1.0.0"
export CANDIDATE_BRANCH="release/1.0.0"
python .github/scripts/validate_release.py
```

---

### 2. `compare_candidate_with_jira.py`

**Propósito:** Compara os commits da branch candidata com os tickets da Fix Version no Jira, gerando um relatório detalhado.

**Funcionalidades:**
- Busca tickets do Jira para a Fix Version especificada
- Extrai commits da branch candidata com referências SCRUM-* e STM-*
- Identifica tickets que faltam na candidate
- Identifica commits sem ticket associado
- Identifica commits com tickets fora da Fix Version
- Gera relatório JSON completo com todas as informações

**Validações realizadas:**
- ✅ Todos os tickets foram incluídos na candidate?
- ✅ Todos os commits têm rastreabilidade?
- ✅ Todos os tickets referenciados estão na Fix Version?

**Saída:**
- `candidate-jira-comparison-report.json` - Relatório estruturado com:
  - `expectedJiraTickets` - Tickets esperados na Fix Version
  - `candidateJiraTickets` - Tickets encontrados na candidate
  - `missingJiraTickets` - Tickets que faltam
  - `commitsWithoutTicket` - Commits sem rastreabilidade
  - `ticketsNotInRelease` - Commits com tickets fora da Fix Version
  - `candidateCommits` - Lista de todos os commits processados
  - `isValid` - Indicador se a candidate é válida

**Variáveis de ambiente necessárias:**
```
JIRA_BASE_URL         # URL base do Jira
JIRA_EMAIL            # Email de autenticação
JIRA_API_TOKEN        # Token de API do Jira
JIRA_PROJECT_KEY      # Chave do projeto
RELEASE_NAME          # Nome da release
CANDIDATE_BRANCH      # Branch candidata
```

---

### 3. `ai_release_analysis.py`

**Propósito:** Gera uma análise de IA sobre o relatório de validação da release usando GitHub Models.

**Funcionalidades:**
- Lê o relatório de validação gerado pelo `validate_release.py`
- Usa GitHub Models (GPT-4o-mini) para análise inteligente
- Gera parecer em português sobre:
  - Se a candidate pode seguir para release
  - Tickets faltando
  - Commits sem rastreabilidade
  - Commits com tickets fora da Fix Version
  - Nível de risco
  - Próximas ações recomendadas
- Implementa fallback em caso de erro na chamada da IA

**Entradas:**
- `release-validation-report.json` - Relatório gerado pelo `validate_release.py`

**Saída:**
- `ai-release-analysis.md` - Análise em Markdown com parecer da IA

**Variáveis de ambiente necessárias:**
```
GITHUB_TOKEN          # Token GitHub com acesso a GitHub Models
```

**Características de segurança:**
- Utiliza autenticação Bearer com token GitHub
- Implementa timeout de 60 segundos para chamadas de IA
- Tratamento robusto de erros HTTP e conexão
- Geração de fallback automático se IA falhar

**Exemplo de uso:**
```bash
export GITHUB_TOKEN="seu_token_github"
python .github/scripts/ai_release_analysis.py
```

---

## Fluxo Integrado

O fluxo típico de uso desses scripts é:

1. **`validate_release.py`** - Primeira validação dos commits contra Jira
   - Gera `release-validation-report.json`

2. **`compare_candidate_with_jira.py`** - Comparação detalhada (opcional)
   - Gera `candidate-jira-comparison-report.json`

3. **`ai_release_analysis.py`** - Análise de IA do relatório
   - Gera `ai-release-analysis.md`
   - Utili

za o relatório do `validate_release.py`

---

## Configuração de Padrões de Referência

Os scripts detectam automaticamente referências nos formatos:
- `SCRUM-123` - Tickets do projeto Scrum
- `STM-123` - Tickets de sistema

Commits ignorados automaticamente:
- "Merge pull request ... /develop"
- "initial commit"
- "add initial content"

