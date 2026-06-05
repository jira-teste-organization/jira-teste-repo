import os
import re
import json
import base64
import urllib.parse
import urllib.request
import subprocess
import sys

jira_key_regex = re.compile(r"SCRUM-\d+", re.IGNORECASE)
stm_key_regex = re.compile(r"STM-\d+", re.IGNORECASE)

jira_base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
jira_email = os.environ["JIRA_EMAIL"]
jira_api_token = os.environ["JIRA_API_TOKEN"]
jira_project_key = os.environ["JIRA_PROJECT_KEY"]
release_name = os.environ["RELEASE_NAME"]
candidate_branch = os.environ["CANDIDATE_BRANCH"]


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()


def jira_get_issues():
    jql = (
        f'project = {jira_project_key} '
        f'AND fixVersion = "{release_name}" '
        f'ORDER BY key ASC'
    )

    url = (
        f"{jira_base_url}/rest/api/3/search/jql"
        f"?jql={urllib.parse.quote(jql)}"
        f"&fields=summary,status&maxResults=100"
    )

    token = base64.b64encode(f"{jira_email}:{jira_api_token}".encode()).decode()

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    return {issue["key"].upper(): issue for issue in data.get("issues", [])}


def extract_refs(message):
    jira_keys = sorted(set(x.upper() for x in jira_key_regex.findall(message)))
    stm_keys = sorted(set(x.upper() for x in stm_key_regex.findall(message)))
    return jira_keys, stm_keys


def get_candidate_commits():
    run(f"git fetch origin {candidate_branch} --prune")

    output = run(
        f'git log --pretty=format:"%H|%s" origin/{candidate_branch}'
    )

    commits = []

    for line in output.splitlines():
        if "|" not in line:
            continue

        sha, message = line.split("|", 1)
        jira_keys, stm_keys = extract_refs(message)

        commits.append({
            "sha": sha[:7],
            "message": message,
            "jiraKeys": jira_keys,
            "stmKeys": stm_keys
        })

    return commits


def should_ignore_commit(message):
    normalized = message.lower().strip()

    if "unknown" in normalized or "unknow" in normalized:
        return False

    if normalized.startswith("merge pull request") and "/develop" in normalized:
        return True

    if normalized == "initial commit":
        return True

    if normalized.startswith("add initial content"):
        return True

    return False


def print_human_report(report):
    print("")
    print("## Release Validation Report")
    print("")

    status = "✅ VÁLIDA" if report["isValid"] else "❌ INVÁLIDA"

    print(f"**Status:** {status}")
    print(f"**Release Jira:** `{report['release']}`")
    print(f"**Branch candidate:** `{report['candidateBranch']}`")
    print("")
    print("### Resumo")
    print("")
    print("| Métrica | Valor |")
    print("|---|---:|")
    print(f"| Tickets esperados no Jira | {len(report['expectedJiraTickets'])} |")
    print(f"| Tickets encontrados na candidate | {len(report['candidateJiraTickets'])} |")
    print(f"| Tickets faltando | {len(report['missingJiraTickets'])} |")
    print(f"| Commits sem rastreabilidade | {len(report['unknownCommits'])} |")
    print(f"| Commits fora da release | {len(report['extraJiraCommits'])} |")
    print("")

    if report["isValid"]:
        print("### Resultado")
        print("")
        print("Nenhum problema crítico encontrado.")
        return

    if report["missingJiraTickets"]:
        print("### ❌ Tickets faltando na candidate")
        print("")
        print("| Ticket | Motivo | Ação recomendada |")
        print("|---|---|---|")

        for ticket in report["missingJiraTickets"]:
            print(
                f"| `{ticket}` | Está na Fix Version `{report['release']}`, "
                "mas não foi encontrado na candidate | "
                "Verificar merge/cherry-pick ou remover da Fix Version |"
            )

        print("")

    if report["unknownCommits"]:
        print("### ⚠️ Commits sem rastreabilidade")
        print("")
        print("| Commit | Mensagem | Ação recomendada |")
        print("|---|---|---|")

        for commit in report["unknownCommits"]:
            message = commit["message"].replace("|", "\\|")
            print(
                f"| `{commit['sha']}` | {message} | "
                "Associar a um ticket SCRUM-* / STM-* ou remover da candidate |"
            )

        print("")

    if report["extraJiraCommits"]:
        print("### ⚠️ Commits com ticket fora da Fix Version")
        print("")
        print("| Ticket | Commit | Mensagem | Ação recomendada |")
        print("|---|---|---|---|")

        for commit in report["extraJiraCommits"]:
            message = commit["message"].replace("|", "\\|")
            print(
                f"| `{commit['ticket']}` | `{commit['sha']}` | {message} | "
                "Adicionar ticket à Fix Version ou remover commit da candidate |"
            )

        print("")

    print("### Ação recomendada geral")
    print("")
    print("- Corrigir os merges da candidate.")
    print("- Remover commits sem rastreabilidade.")
    print("- Executar novamente a validação antes de gerar a versão.")


jira_issues = jira_get_issues()
expected_jira_keys = set(jira_issues.keys())

candidate_commits = get_candidate_commits()

candidate_jira_keys = set()
unknown_commits = []
extra_jira_commits = []

for commit in candidate_commits:
    message = commit["message"]

    if should_ignore_commit(message):
        continue

    if not commit["jiraKeys"] and not commit["stmKeys"]:
        unknown_commits.append(commit)
        continue

    for jira_key in commit["jiraKeys"]:
        candidate_jira_keys.add(jira_key)

        if jira_key not in expected_jira_keys:
            extra_jira_commits.append({
                "ticket": jira_key,
                "sha": commit["sha"],
                "message": commit["message"]
            })

missing_jira_keys = sorted(expected_jira_keys - candidate_jira_keys)

is_valid = not (
    missing_jira_keys
    or unknown_commits
    or extra_jira_commits
)

report = {
    "release": release_name,
    "candidateBranch": candidate_branch,
    "expectedJiraTickets": sorted(expected_jira_keys),
    "candidateJiraTickets": sorted(candidate_jira_keys),
    "missingJiraTickets": missing_jira_keys,
    "unknownCommits": unknown_commits,
    "extraJiraCommits": extra_jira_commits,
    "isValid": is_valid
}

print_human_report(report)

with open("release-validation-report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

if not is_valid:
    sys.exit(1)

print("✅ Release candidate válida.")
