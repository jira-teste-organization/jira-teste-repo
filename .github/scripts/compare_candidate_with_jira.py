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
base_branch = os.environ.get("BASE_BRANCH", "develop")


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
        f"&fields=summary,status,fixVersions&maxResults=100"
    )

    token = base64.b64encode(f"{jira_email}:{jira_api_token}".encode()).decode()

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    issues = {}

    for issue in data.get("issues", []):
        key = issue["key"].upper()
        fields = issue.get("fields", {})
        issues[key] = {
            "key": key,
            "summary": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", "")
        }

    return issues


def extract_refs(message):
    jira_keys = sorted(set(x.upper() for x in jira_key_regex.findall(message)))
    stm_keys = sorted(set(x.upper() for x in stm_key_regex.findall(message)))
    return jira_keys, stm_keys


def get_candidate_commits():
    run(f"git fetch origin {base_branch} --prune")
    run(f"git fetch origin {candidate_branch} --prune")

    output = run(
        f'git log --pretty=format:"%H|%s" origin/{base_branch}..origin/{candidate_branch}'
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


def print_report(report):
    print("")
    print("=" * 90)

    if report["isValid"]:
        print("✅ CANDIDATE COMPATÍVEL COM A FIX VERSION DO JIRA")
    else:
        print("❌ CANDIDATE DIVERGENTE DA FIX VERSION DO JIRA")

    print("=" * 90)
    print("")
    print(f"Release Jira     : {report['release']}")
    print(f"Branch candidate : {report['candidateBranch']}")
    print(f"Branch base      : {report['baseBranch']}")
    print("")
    print("Resumo:")
    print(f"- Tickets esperados no Jira       : {len(report['expectedJiraTickets'])}")
    print(f"- Tickets encontrados na candidate: {len(report['candidateJiraTickets'])}")
    print(f"- Tickets faltando na candidate   : {len(report['missingJiraTickets'])}")
    print(f"- Commits sem ticket              : {len(report['commitsWithoutTicket'])}")
    print(f"- Tickets fora da release         : {len(report['ticketsNotInRelease'])}")
    print("")

    if report["missingJiraTickets"]:
        print("Tickets do Jira ausentes na candidate:")
        for item in report["missingJiraTickets"]:
            print(f"- {item['key']} | {item['status']} | {item['summary']}")
        print("")

    if report["commitsWithoutTicket"]:
        print("Commits na candidate sem referência Jira/Sistema:")
        for item in report["commitsWithoutTicket"]:
            print(f"- {item['sha']} | {item['message']}")
        print("")

    if report["ticketsNotInRelease"]:
        print("Commits na candidate com ticket fora da Fix Version:")
        for item in report["ticketsNotInRelease"]:
            print(f"- {item['ticket']} | {item['sha']} | {item['message']}")
        print("")

    if not report["isValid"]:
        print("Ação recomendada:")
        print("- Validar se todos os tickets da Fix Version foram mergeados na candidate.")
        print("- Remover commits não autorizados da candidate.")
        print("- Ajustar mensagens de commit/PR sem rastreabilidade.")
        print("- Executar novamente este workflow antes de gerar a versão.")
        print("")

    print("=" * 90)


jira_issues = jira_get_issues()
candidate_commits = get_candidate_commits()

expected_jira_keys = set(jira_issues.keys())

candidate_jira_keys = set()
commits_without_ticket = []
tickets_not_in_release = []

for commit in candidate_commits:
    message = commit["message"]

    if not commit["jiraKeys"] and not commit["stmKeys"]:
        commits_without_ticket.append({
            "sha": commit["sha"],
            "message": message
        })
        continue

    for jira_key in commit["jiraKeys"]:
        candidate_jira_keys.add(jira_key)

        if jira_key not in expected_jira_keys:
            tickets_not_in_release.append({
                "ticket": jira_key,
                "sha": commit["sha"],
                "message": message
            })

missing_jira_keys = sorted(expected_jira_keys - candidate_jira_keys)

missing_jira_tickets = [
    jira_issues[key]
    for key in missing_jira_keys
]

is_valid = not (
    missing_jira_tickets
    or commits_without_ticket
    or tickets_not_in_release
)

report = {
    "release": release_name,
    "candidateBranch": candidate_branch,
    "baseBranch": base_branch,
    "expectedJiraTickets": sorted(expected_jira_keys),
    "candidateJiraTickets": sorted(candidate_jira_keys),
    "missingJiraTickets": missing_jira_tickets,
    "commitsWithoutTicket": commits_without_ticket,
    "ticketsNotInRelease": tickets_not_in_release,
    "candidateCommits": candidate_commits,
    "isValid": is_valid
}

print_report(report)

with open("candidate-jira-comparison-report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

if not is_valid:
    sys.exit(1)
