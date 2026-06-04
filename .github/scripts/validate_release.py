import os
import re
import json
import base64
import urllib.parse
import urllib.request
import subprocess
import sys

ticket_regex = re.compile(r"STM-\d+", re.IGNORECASE)

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

def commits_between(branch):
    output = run(f'git log --pretty=format:"%H|%s" origin/develop..origin/{branch}')

    commits = []
    for line in output.splitlines():
        if "|" not in line:
            continue

        sha, message = line.split("|", 1)
        tickets = sorted(set(t.upper() for t in ticket_regex.findall(message)))

        commits.append({
            "sha": sha[:7],
            "message": message,
            "tickets": tickets
        })

    return commits

run("git fetch origin develop --prune")
run(f"git fetch origin {candidate_branch} --prune")

jira_issues = jira_get_issues()
expected_tickets = set(jira_issues.keys())

candidate_commits = commits_between(candidate_branch)

candidate_tickets = set()
unknown_commits = []
extra_ticket_commits = []

for commit in candidate_commits:
    if not commit["tickets"]:
        unknown_commits.append(commit)
        continue

    for ticket in commit["tickets"]:
        candidate_tickets.add(ticket)

        if ticket not in expected_tickets:
            extra_ticket_commits.append({
                "ticket": ticket,
                "sha": commit["sha"],
                "message": commit["message"]
            })

missing_tickets = sorted(expected_tickets - candidate_tickets)

report = {
    "release": release_name,
    "candidateBranch": candidate_branch,
    "expectedTickets": sorted(expected_tickets),
    "candidateTickets": sorted(candidate_tickets),
    "missingTickets": missing_tickets,
    "unknownCommits": unknown_commits,
    "extraTicketCommits": extra_ticket_commits
}

print(json.dumps(report, indent=2, ensure_ascii=False))

with open("release-validation-report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

if missing_tickets or unknown_commits or extra_ticket_commits:
    print("❌ Release candidate inválida.")
    sys.exit(1)

print("✅ Release candidate válida.")
