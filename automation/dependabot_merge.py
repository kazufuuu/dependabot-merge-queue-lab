"""Dependabot の PR を、自動マージするものと人が見るものに振り分ける。

開いている Dependabot の PR を毎回すべて見直し、あるべき状態に寄せる。
何度動かしても結果が変わらないように作ってある。

自動マージの条件（すべて満たすこと）
- PR の作成者が Dependabot で、コミットが 1 つだけ
- そのコミットの作者が Dependabot で、GitHub 自身の鍵で署名されている
- その head を push したのが Dependabot である（人が push し直したコミットは、中身が本物でも対象外）
- 変わったファイルがロックファイルだけ
- 更新がすべて、自動マージの対象のグループに属している
  （セキュリティ更新はグループに属さないので、対象にならない）
- 更新の種別がすべて patch（設定で、開発用の依存の minor も足せる）
- 必須の検査が、その head で成功している

設定で足せる範囲が 2 つある。どちらも既定では無効。
- 開発用の依存の minor（AUTOMERGE_DEV_MINOR）
- Python と Node の公式イメージの patch（AUTOMERGE_RUNTIME_PATCH）。セキュリティの修正に速く追随するため。
  この PR は、Dependabot のコミットに、版の同期が積んだコミットが 1 つ続く形になる

条件を満たさない PR には、レビューを依頼してラベルを付ける。
承認とマージキューへの投入は、専用の GitHub App のトークンで行う。
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("policy.json")

LABEL_AUTO = "automerge"
LABEL_HUMAN = "needs-review"

PATCH = "version-update:semver-patch"
MINOR = "version-update:semver-minor"
DEV = "direct:development"

DEPENDABOT_AUTHOR = "dependabot"  # GraphQL での PR の作成者（Bot）
DEPENDABOT_COMMITTER = "dependabot[bot]"  # コミットの作者


@dataclass(frozen=True)
class Policy:
    reviewers: tuple[str, ...]
    required_check: str
    ci_workflow: str
    lockfiles: tuple[str, ...]
    patch_group: str
    dev_minor_group: str
    sync_app: str
    sentinel: str
    runtime_files: dict[str, str]
    dev_minor: bool = False
    runtime_patch: bool = False


@dataclass(frozen=True)
class Decision:
    auto: bool
    reasons: tuple[str, ...] = ()


@dataclass
class Plan:
    """1 本の PR に対して行う操作。"""

    number: int
    summary: str
    approve: bool = False
    enqueue: bool = False
    disable_auto_merge: bool = False
    add_labels: list[str] = field(default_factory=list)
    remove_labels: list[str] = field(default_factory=list)
    request_reviewers: list[str] = field(default_factory=list)
    comment: str | None = None

    def is_noop(self) -> bool:
        return not (
            self.approve
            or self.enqueue
            or self.disable_auto_merge
            or self.add_labels
            or self.remove_labels
            or self.request_reviewers
            or self.comment
        )


def load_policy(env: dict[str, str] | None = None) -> Policy:
    env = os.environ if env is None else env
    raw = json.loads(POLICY_PATH.read_text())
    return Policy(
        reviewers=tuple(raw["reviewers"]),
        required_check=raw["required_check"],
        ci_workflow=raw["ci_workflow"],
        lockfiles=tuple(raw["lockfiles"]),
        patch_group=raw["patch_group"],
        dev_minor_group=raw["dev_minor_group"],
        sync_app=raw["sync_app"],
        sentinel=raw["sentinel"],
        runtime_files=raw["runtime_files"],
        dev_minor=env.get("AUTOMERGE_DEV_MINOR", "").lower() == "true",
        runtime_patch=env.get("AUTOMERGE_RUNTIME_PATCH", "").lower() == "true",
    )


def parse_updated_dependencies(message: str) -> list[dict[str, str]]:
    """Dependabot がコミットメッセージに書くメタデータを読む。"""
    lines = message.splitlines()
    try:
        start = lines.index("updated-dependencies:")
    except ValueError:
        return []
    items: list[dict[str, str]] = []
    for line in lines[start + 1 :]:
        if line.strip() == "...":
            break
        if line.startswith("- "):
            items.append({})
            line = "  " + line[2:]
        if not line.startswith("  ") or not items or ":" not in line:
            continue
        key, _, value = line.strip().partition(":")
        items[-1][key.strip()] = value.strip().strip("'\"")
    return items


def in_auto_scope(dep: dict[str, str], policy: Policy) -> bool:
    """グループに属する更新が、自動マージの範囲に入るかを返す。"""
    group = dep.get("dependency-group")
    update_type = dep.get("update-type")
    if group == policy.patch_group:
        return update_type == PATCH
    if policy.dev_minor and group == policy.dev_minor_group:
        return update_type in (PATCH, MINOR) and dep.get("dependency-type") == DEV
    return False


def runtime_patch_reasons(pr: dict, policy: Policy) -> list[str]:
    """公式イメージの patch の PR として、自動マージできない理由を返す。空なら対象。

    対象の形は 1 つだけ。Dependabot が見張り役を上げたコミットに、版の同期が積んだコミットが続く。
    """
    reasons: list[str] = []
    first, second = pr["commits"]
    if first["author"] != DEPENDABOT_COMMITTER or not first["signed_by_github"]:
        reasons.append("1 つ目のコミットが Dependabot のものではありません")
    if set(first["pushers"]) != {DEPENDABOT_COMMITTER}:
        reasons.append("1 つ目のコミットを push したのが Dependabot ではありません")
    if second["author"] != policy.sync_app or not second["signed_by_github"]:
        reasons.append("2 つ目のコミットが、版の同期のものではありません")
    if set(pr["head_pushers"]) != {policy.sync_app}:
        reasons.append("head を push したのが、版の同期ではありません: " + ", ".join(sorted(pr["head_pushers"])))

    deps = parse_updated_dependencies(first["message"])
    if not deps:
        reasons.append("更新のメタデータを読めません")
    wanted = {policy.sentinel}
    for dep in deps:
        name = dep.get("dependency-name", "?")
        if name not in policy.runtime_files:
            reasons.append(f"{name}: 公式イメージの python と node 以外は人が見ます")
        elif dep.get("dependency-group") != policy.patch_group or dep.get("update-type") != PATCH:
            reasons.append(f"{name}: patch 以外は人が見ます")
        else:
            wanted.add(policy.runtime_files[name])
    if pr["files_truncated"] or set(pr["files"]) != wanted:
        reasons.append("変わったファイルが、見張り役と正本だけではありません: " + ", ".join(sorted(pr["files"])[:5]))
    return reasons


def classify(pr: dict, policy: Policy) -> Decision:
    """検査の結果を見る前に、自動マージの候補かどうかを決める。"""
    if policy.runtime_patch and len(pr["commits"]) == 2:
        runtime = runtime_patch_reasons(pr, policy)
        if not runtime:
            return Decision(auto=True)
        # 当てはまらなければ、下のふつうの判定に進む（コミットが 2 つあるので、人が見ることになる）。

    reasons: list[str] = []

    commits = pr["commits"]
    if len(commits) != 1:
        reasons.append(f"コミットが {len(commits)} 個あります")
    for commit in commits:
        if commit["author"] != DEPENDABOT_COMMITTER or not commit["signed_by_github"]:
            reasons.append("Dependabot の署名の無いコミットがあります")
            break

    # head の検査を起こした主体は、その head を push した主体と同じになる。
    # 過去の本物のコミットを人が別のブランチへ持ってきた場合を、ここで弾く。
    pushers = set(pr["head_pushers"])
    if pushers - {DEPENDABOT_COMMITTER}:
        reasons.append("head を push したのが Dependabot ではありません: " + ", ".join(sorted(pushers)))
    elif not pushers and pr["check"] != "pending":
        reasons.append("head を push した主体を確かめられません")

    other_files = [p for p in pr["files"] if p.rsplit("/", 1)[-1] not in policy.lockfiles]
    if pr["files_truncated"]:
        reasons.append("変更されたファイルが多く、全部を確かめられません")
    elif not pr["files"]:
        reasons.append("変更されたファイルがありません")
    elif other_files:
        reasons.append("ロックファイル以外が変わっています: " + ", ".join(other_files[:5]))

    deps = parse_updated_dependencies(commits[-1]["message"]) if commits else []
    if not deps:
        reasons.append("更新のメタデータを読めません")
    for dep in deps:
        name = dep.get("dependency-name", "?")
        group = dep.get("dependency-group")
        update_type = dep.get("update-type")
        if group is None:
            reasons.append(f"{name}: グループに属していません（セキュリティ更新など）")
        elif not in_auto_scope(dep, policy):
            reasons.append(f"{name}: {group} の {(update_type or '種別不明').rsplit(':', 1)[-1]} は人が見ます")

    return Decision(auto=not reasons, reasons=tuple(dict.fromkeys(reasons)))


def plan_for(pr: dict, policy: Policy) -> Plan:
    """PR の今の状態から、行う操作を決める。"""
    number = pr["number"]
    labels = set(pr["labels"])
    decision = classify(pr, policy)
    approved_head = pr["head"] in pr["approved_commits"]
    waiting = pr["in_merge_queue"] or pr["auto_merge_enabled"]

    def to_human(reasons: tuple[str, ...]) -> Plan:
        plan = Plan(number, "人が見る: " + " / ".join(reasons))
        if LABEL_AUTO in labels:
            plan.remove_labels.append(LABEL_AUTO)
        if pr["auto_merge_enabled"]:
            plan.disable_auto_merge = True
        if LABEL_HUMAN not in labels:
            plan.add_labels.append(LABEL_HUMAN)
            plan.comment = "自動マージの対象外です。レビューをお願いします。\n\n" + "\n".join(
                f"- {reason}" for reason in reasons
            )
        done = set(pr["requested_reviewers"]) | set(pr["human_reviewers"])
        plan.request_reviewers = [r for r in policy.reviewers if r not in done]
        return plan

    if not decision.auto:
        return to_human(decision.reasons)

    check = pr["check"]
    if check == "failure":
        return to_human(("必須の検査が落ちました",))
    if check != "success":
        return Plan(number, "自動マージの候補。検査の結果を待っています")
    if waiting:
        return Plan(number, "自動マージの候補。マージの順番を待っています")
    if approved_head:
        # 一度キューに入れたのに、マージされずに外れている。
        return to_human(("マージキューの検査で外されました",))

    plan = Plan(number, "自動マージ: 承認してマージキューに入れます", approve=True, enqueue=True)
    if LABEL_AUTO not in labels:
        plan.add_labels.append(LABEL_AUTO)
    if LABEL_HUMAN in labels:
        plan.remove_labels.append(LABEL_HUMAN)
    return plan


# ここから下は GitHub とのやり取り。

QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 40, orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        number
        headRefOid
        author { __typename login }
        labels(first: 30) { nodes { name } }
        reviewRequests(first: 20) { nodes { requestedReviewer { ... on User { login } } } }
        latestReviews(first: 30) { nodes { state author { __typename login } commit { oid } } }
        commits(first: 10) {
          totalCount
          nodes { commit {
            oid message
            author { user { login } }
            signature { isValid wasSignedByGitHub }
          } }
        }
        statusCheckRollup { contexts(first: 60) { nodes { __typename ... on CheckRun { name status conclusion } } } }
        files(first: 100) { totalCount nodes { path } }
        mergeQueueEntry { state }
        autoMergeRequest { enabledAt }
      }
    }
  }
}
"""


def gh(*args: str, token: str | None = None) -> str:
    env = {**os.environ, "GH_TOKEN": token} if token else None
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:4])}: {result.stderr.strip()}")
    return result.stdout


def check_state(rollup: dict | None, required_check: str) -> str:
    """head のコミットでの、必須の検査の結果を返す。"""
    nodes = rollup["contexts"]["nodes"] if rollup else []
    runs = [run for run in nodes if run["__typename"] == "CheckRun" and run["name"] == required_check]
    if not runs or any(run["status"] != "COMPLETED" for run in runs):
        return "pending"
    return "success" if all(run["conclusion"] == "SUCCESS" for run in runs) else "failure"


def normalize(node: dict, policy: Policy, pushers: dict[str, list[str]]) -> dict:
    """GraphQL の結果を、判定に使う形にする。pushers は、コミットごとの、検査を起こした主体。"""
    commits = [c["commit"] for c in node["commits"]["nodes"]]
    reviews = node["latestReviews"]["nodes"]
    return {
        "number": node["number"],
        "head": node["headRefOid"],
        "head_pushers": pushers.get(node["headRefOid"], []),
        "labels": [label["name"] for label in node["labels"]["nodes"]],
        "commits": [
            {
                "message": c["message"],
                "pushers": pushers.get(c["oid"], []),
                "author": ((c["author"] or {}).get("user") or {}).get("login"),
                "signed_by_github": bool(
                    c["signature"] and c["signature"]["isValid"] and c["signature"]["wasSignedByGitHub"]
                ),
            }
            for c in commits
        ]
        + [{"message": "", "pushers": [], "author": None, "signed_by_github": False}]
        * (node["commits"]["totalCount"] - len(commits)),
        "files": [f["path"] for f in node["files"]["nodes"]],
        "files_truncated": node["files"]["totalCount"] > len(node["files"]["nodes"]),
        "requested_reviewers": [
            r["requestedReviewer"]["login"]
            for r in node["reviewRequests"]["nodes"]
            if r["requestedReviewer"] and "login" in r["requestedReviewer"]
        ],
        "human_reviewers": [
            r["author"]["login"] for r in reviews if r["author"] and r["author"]["__typename"] == "User"
        ],
        "approved_commits": [
            r["commit"]["oid"]
            for r in reviews
            if r["state"] == "APPROVED" and r["author"] and r["author"]["__typename"] == "Bot" and r["commit"]
        ],
        "check": check_state(node["statusCheckRollup"], policy.required_check),
        "in_merge_queue": node["mergeQueueEntry"] is not None,
        "auto_merge_enabled": node["autoMergeRequest"] is not None,
    }


def fetch_pull_requests(repo: str, policy: Policy) -> list[dict]:
    owner, name = repo.split("/")
    out = gh("api", "graphql", "-f", f"query={QUERY}", "-f", f"owner={owner}", "-f", f"name={name}")
    nodes = json.loads(out)["data"]["repository"]["pullRequests"]["nodes"]
    pulls = []
    for node in nodes:
        author = node["author"]
        if not author or author["__typename"] != "Bot" or author["login"] != DEPENDABOT_AUTHOR:
            continue
        pushers = {}
        for commit in node["commits"]["nodes"][-2:]:
            oid = commit["commit"]["oid"]
            runs = gh(
                "api", f"repos/{repo}/actions/workflows/{policy.ci_workflow}/runs?event=pull_request&head_sha={oid}",
                "--jq", "[.workflow_runs[].actor.login]",
            )  # fmt: skip
            pushers[oid] = json.loads(runs)
        pulls.append(normalize(node, policy, pushers))
    return pulls


def apply_triage(plan: Plan, repo: str) -> None:
    """ラベル、レビュー依頼、コメントを付ける。GITHUB_TOKEN で行う。"""
    number = str(plan.number)
    for label in plan.remove_labels:
        gh("pr", "edit", number, "--repo", repo, "--remove-label", label)
    if plan.disable_auto_merge:
        gh("pr", "merge", number, "--repo", repo, "--disable-auto")
    for label in plan.add_labels:
        if label != LABEL_AUTO:
            gh("pr", "edit", number, "--repo", repo, "--add-label", label)
    if plan.request_reviewers:
        gh(
            "api", "-X", "POST", f"repos/{repo}/pulls/{number}/requested_reviewers",
            *[arg for reviewer in plan.request_reviewers for arg in ("-f", f"reviewers[]={reviewer}")],
        )  # fmt: skip
    if plan.comment:
        gh("pr", "comment", number, "--repo", repo, "--body", plan.comment)


def apply_merge(plan: Plan, pr: dict, repo: str, token: str) -> None:
    """承認してマージキューに入れる。専用の GitHub App のトークンで行う。

    GITHUB_TOKEN でキューに入れると、merge_group の検査が起動せず、キューが止まる。
    """
    number = str(plan.number)
    gh(
        "api", "-X", "POST", f"repos/{repo}/pulls/{number}/reviews",
        "-f", "event=APPROVE", "-f", f"commit_id={pr['head']}",
        "-f", "body=patch の更新で、検査が通っています。自動で承認します。",
        token=token,
    )  # fmt: skip
    gh("pr", "edit", number, "--repo", repo, "--add-label", LABEL_AUTO, token=token)
    gh("pr", "merge", number, "--repo", repo, "--auto", "--match-head-commit", pr["head"], token=token)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_token(repo: str, app_id: str, private_key: str) -> str:
    """GitHub App の、このリポジトリだけに効くトークンを作る。"""
    now = int(time.time())
    unsigned = ".".join(
        b64url(json.dumps(part, separators=(",", ":")).encode())
        for part in ({"alg": "RS256", "typ": "JWT"}, {"iat": now - 60, "exp": now + 300, "iss": app_id})
    )
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as key_file:
        key_file.write(private_key)
        key_file.flush()
        signature = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_file.name],
            input=unsigned.encode(), capture_output=True, check=True,
        ).stdout  # fmt: skip
    jwt = f"{unsigned}.{b64url(signature)}"

    def call(method: str, path: str, body: dict | None = None) -> dict:
        request = urllib.request.Request(
            f"https://api.github.com{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    installation = call("GET", f"/repos/{repo}/installation")
    token = call(
        "POST",
        f"/app/installations/{installation['id']}/access_tokens",
        {"repositories": [repo.split("/")[1]]},
    )["token"]
    print(f"::add-mask::{token}")
    return token


def main() -> int:
    """triage はラベルと依頼を付け、merge は承認とキューへの投入を行う。

    merge は、鍵を持つ別の job から呼ぶ。対象の PR は、その場で判定し直す。
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    if mode not in ("triage", "merge", "dry-run"):
        print("usage: dependabot_merge.py [triage|merge|dry-run]")
        return 2
    repo = os.environ["GITHUB_REPOSITORY"]
    policy = load_policy()
    print(f"policy: dev_minor={policy.dev_minor} runtime_patch={policy.runtime_patch} reviewers={list(policy.reviewers)}")
    token = None
    failed = False
    to_merge = 0
    for pr in fetch_pull_requests(repo, policy):
        plan = plan_for(pr, policy)
        print(f"#{plan.number}: {plan.summary}" + (" (変更なし)" if plan.is_noop() else ""))
        to_merge += plan.enqueue
        try:
            if mode == "triage" and not plan.is_noop():
                apply_triage(plan, repo)
            elif mode == "merge" and plan.enqueue:
                token = token or app_token(
                    repo, os.environ["AUTOMERGE_APP_ID"], os.environ["AUTOMERGE_APP_PRIVATE_KEY"]
                )
                apply_merge(plan, pr, repo, token)
        except RuntimeError as error:
            failed = True
            print(f"::error::#{plan.number}: {error}")
    if mode == "triage" and "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"to_merge={to_merge}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
