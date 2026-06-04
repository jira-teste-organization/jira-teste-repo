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

def print_human_report(report):
    print("")
    print("=" * 80)

    if report["isValid"]:
        print("✅ RELEASE CANDIDATE VÁLIDA")
    else:
        print("❌ RELEASE CANDIDATE INVÁLIDA")

    print("=" * 80)
    print("")
    print(f"Release Jira     : {report['release']}")
    print(f"Branch candidate : {report['candidateBranch']}")
    print("")
    print("Resumo:")
    print(f"- Tickets esperados no Jira      : {len(report['expectedJiraTickets'])}")
    print(f"- Tickets encontrados na candidate: {len(report['candidateJiraTickets'])}")
    print(f"- Tickets faltando               : {len(report['missingJiraTickets'])}")
    print(f"- Commits desconhecidos           : {len(report['unknownCommits'])}")
    print(f"- Commits fora da release         : {len(report['extraJiraCommits'])}")
    print("")

    if report["isValid"]:
        print("Nenhum problema crítico encontrado.")
        print("")
        print("=" * 80)
        return

    print("Problemas críticos:")
    print("")

    index = 1

    for ticket in report["missingJiraTickets"]:
        print(f"{index}. Ticket faltando na candidate")
        print(f"   Jira   : {ticket}")
        print(f"   Motivo : o ticket está marcado na Fix Version {report['release']},")
        print("            mas nenhum commit/merge correspondente foi encontrado na candidate.")
        print(f"   Ação   : verificar se o desenvolvimento de {ticket} foi mergeado na branch candidate.")
        print("")
        index += 1

    for commit in report["unknownCommits"]:
        print(f"{index}. Commit sem rastreabilidade")
        print(f"   Commit : {commit['sha']}")
        print(f"   Mensagem: {commit['message']}")
        print("   Motivo : o commit está na candidate, mas não possui referência SCRUM-* ou STM-*.")
        print("   Ação   : corrigir a mensagem do commit, associar a um ticket, ou remover da candidate.")
        print("")
        index += 1

    for commit in report["extraJiraCommits"]:
        print(f"{index}. Commit associado a ticket fora da release")
        print(f"   Jira   : {commit['ticket']}")
        print(f"   Commit : {commit['sha']}")
        print(f"   Mensagem: {commit['message']}")
        print(f"   Motivo : o commit está na candidate, mas o ticket não está na Fix Version {report['release']}.")
        print("   Ação   : validar se o ticket deve entrar na release ou remover o commit da candidate.")
        print("")
        index += 1

    print("Ação recomendada geral:")
    print("- Corrigir os merges da candidate.")
    print("- Executar novamente esta validação antes de gerar a versão.")
    print("")
    print("=" * 80)

def commits_between(branch):
    output = run(f'git log --pretty=format:"%H|%s" origin/develop..origin/{branch}')

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

run("git fetch origin develop --prune")
run(f"git fetch origin {candidate_branch} --prune")

jira_issues = jira_get_issues()
expected_jira_keys = set(jira_issues.keys())

candidate_commits = commits_between(candidate_branch)

candidate_jira_keys = set()
unknown_commits = []
extra_jira_commits = []

for commit in candidate_commits:
    message = commit["message"]

    if message.startswith("Merge pull request") and "/develop" in message:
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

is_valid = not (missing_jira_keys or unknown_commits or extra_jira_commits)

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
report = {
    "release": release_name,
    "candidateBranch": candidate_branch,
    "expectedJiraTickets": sorted(expected_jira_keys),
    "candidateJiraTickets": sorted(candidate_jira_keys),
    "missingJiraTickets": missing_jira_keys,
    "unknownCommits": unknown_commits,
    "extraJiraCommits": extra_jira_commits
}

print(json.dumps(report, indent=2, ensure_ascii=False))

with open("release-validation-report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

if missing_jira_keys or unknown_commits or extra_jira_commits:
    print("❌ Release candidate inválida.")
    sys.exit(1)

print("✅ Release candidate válida.")
