import json
import os
import urllib.request
import urllib.error

REPORT_FILE = "release-validation-report.json"
OUTPUT_FILE = "ai-release-analysis.md"

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

with open(REPORT_FILE, "r", encoding="utf-8") as f:
    report = json.load(f)

prompt = f"""
Você é um Release Governance Agent.

Analise o relatório abaixo e gere um parecer objetivo em português para o time de desenvolvimento.

Regras:
- Explique se a candidate pode ou não seguir para release.
- Destaque tickets faltando.
- Destaque commits sem rastreabilidade.
- Destaque commits com tickets fora da Fix Version.
- Informe o risco.
- Sugira próximas ações.
- Não invente tickets, commits ou dados não presentes no JSON.

Relatório JSON:

{json.dumps(report, indent=2, ensure_ascii=False)}
"""

payload = {
    "model": "openai/gpt-4o-mini",
    "messages": [
        {
            "role": "system",
            "content": "Você é um agente especialista em governança de releases, GitHub, Jira e controle de versões."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    "temperature": 0.2,
    "max_tokens": 1200
}

request = urllib.request.Request(
    "https://models.github.ai/inference/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"]

except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")

    content = f"""
# AI Release Analysis

Não foi possível gerar a análise com IA.

Erro HTTP: {e.code}

Detalhes:

```text
{error_body}
