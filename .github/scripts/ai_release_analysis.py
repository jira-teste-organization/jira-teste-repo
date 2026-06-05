import json
import os
import urllib.request
import urllib.error
import traceback

REPORT_FILE = "release-validation-report.json"
OUTPUT_FILE = "ai-release-analysis.md"

MODEL_ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL_NAME = "openai/gpt-4o-mini"


def safe_json_dumps(value):
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


def load_report():
    try:
        if not os.path.exists(REPORT_FILE):
            return {
                "isValid": False,
                "error": f"Arquivo {REPORT_FILE} não encontrado."
            }

        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        return {
            "isValid": False,
            "error": f"Erro ao ler {REPORT_FILE}: {type(e).__name__}: {str(e)}"
        }


def build_prompt(report):
    return f"""
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
- Se o JSON indicar erro técnico, explique que a análise de IA usou o relatório bruto disponível.

Relatório JSON:

{safe_json_dumps(report)}
"""


def call_github_models(prompt):
    try:
        github_token = os.environ.get("GITHUB_TOKEN")

        if not github_token:
            raise RuntimeError("Variável GITHUB_TOKEN não encontrada.")

        payload = {
            "model": MODEL_NAME,
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
            MODEL_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {github_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data["choices"][0]["message"]["content"]

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = "Não foi possível ler o corpo do erro HTTP."

        raise RuntimeError(
            f"Erro HTTP ao chamar GitHub Models: {e.code}\n{error_body}"
        )

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Erro de conexão ao chamar GitHub Models: {str(e)}"
        )

    except Exception as e:
        raise RuntimeError(
            f"Erro inesperado ao chamar GitHub Models: {type(e).__name__}: {str(e)}"
        )


def build_fallback_analysis(report, error):
    return f"""# AI Release Analysis

Não foi possível gerar a análise com IA usando GitHub Models.

## Motivo técnico

"""
{error}
