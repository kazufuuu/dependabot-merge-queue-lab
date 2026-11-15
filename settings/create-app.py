#!/usr/bin/env python3
"""自動マージ用の GitHub App を作り、鍵を environment に登録する。

使い方: settings/create-app.py <owner>/<repo> [--name <App の名前>] [--port <番号>]

画面での操作は、ボタンを 2 回押すことと、install 先を選ぶことだけになる。
1. 表示された URL を開き、ボタンを押す。GitHub の画面で App の作成を確かめる
2. 続けて表示される install の画面で、対象のリポジトリだけを選ぶ

App ID は environment の変数に、秘密鍵は environment の secret に、直接登録する。
秘密鍵は、画面にもファイルにも出さない。
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ENVIRONMENT = "automerge"
VARIABLE = "AUTOMERGE_APP_ID"
SECRET = "AUTOMERGE_APP_PRIVATE_KEY"
PERMISSIONS = {"contents": "write", "pull_requests": "write"}


def gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(["gh", *args], input=input_text, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # 入力に秘密が入ることがあるので、引数とエラーだけを出す。
        raise SystemExit(f"gh {' '.join(args[:3])} が失敗しました: {result.stderr.strip()}")
    return result.stdout.strip()


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(app_id: int, private_key: str) -> str:
    now = int(time.time())
    unsigned = ".".join(
        b64url(json.dumps(part, separators=(",", ":")).encode())
        for part in ({"alg": "RS256", "typ": "JWT"}, {"iat": now - 60, "exp": now + 300, "iss": str(app_id)})
    )
    # openssl に鍵を渡すあいだだけ、自分だけが読める一時ファイルに置く。終わると消える。
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as key_file:
        key_file.write(private_key)
        key_file.flush()
        signature = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_file.name],
            input=unsigned.encode(),
            capture_output=True,
            check=True,
        ).stdout
    return f"{unsigned}.{b64url(signature)}"


def wait_for_code(port: int, post_url: str, manifest: dict, state: str) -> str:
    """フォームのページを出し、GitHub から戻ってくる code を受け取る。"""
    received: dict[str, str] = {}
    page = f"""<!doctype html><meta charset="utf-8"><title>GitHub App の作成</title>
<body style="font-family: sans-serif; max-width: 40em; margin: 3em auto">
<h1>GitHub App の作成</h1>
<p>ボタンを押すと GitHub の画面に移ります。そこで App の作成を確かめてください。</p>
<form action="{html.escape(post_url)}" method="post">
<input type="hidden" name="manifest" value="{html.escape(json.dumps(manifest))}">
<button type="submit" style="font-size: 1.2em; padding: .5em 1em">GitHub で App を作る</button>
</form></body>"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:  # code を端末に出さない
            return

        def respond(self, status: int, body: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path == "/callback":
                if query.get("state", [""])[0] != state or "code" not in query:
                    self.respond(400, "state が一致しません。最初からやり直してください。")
                    return
                received["code"] = query["code"][0]
                self.respond(200, '<meta charset="utf-8"><p>受け取りました。端末に戻ってください。</p>')
            elif url.path == "/":
                self.respond(200, page)
            else:
                self.respond(404, "not found")

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.timeout = 1
    print(f"次の URL をブラウザで開き、ボタンを押してください: http://localhost:{port}/", flush=True)
    deadline = time.monotonic() + 1800
    while "code" not in received:
        if time.monotonic() > deadline:
            raise SystemExit("30 分待ちましたが、GitHub から戻ってきませんでした。")
        server.handle_request()
    server.server_close()
    return received["code"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="<owner>/<repo>")
    parser.add_argument("--name", help="App の名前。GitHub 全体で重ならないこと")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    owner = args.repo.split("/")[0]

    existing = gh("api", f"repos/{args.repo}/environments/{ENVIRONMENT}/secrets", "--jq", ".secrets[].name")
    if SECRET in existing.split():
        raise SystemExit(f"{SECRET} はすでに登録されています。作り直すときは、先に secret を消してください。")

    is_org = gh("api", f"users/{owner}", "--jq", ".type") == "Organization"
    state = secrets.token_urlsafe(16)
    base = f"https://github.com/organizations/{owner}/settings/apps/new" if is_org else "https://github.com/settings/apps/new"
    manifest = {
        "name": args.name or f"{owner}-dependabot-automerge",
        "url": f"https://github.com/{args.repo}",
        "description": "検査の通った patch の更新を承認し、マージキューに入れる",
        "public": False,
        "hook_attributes": {"url": f"https://github.com/{args.repo}", "active": False},
        "redirect_url": f"http://localhost:{args.port}/callback",
        "default_permissions": PERMISSIONS,
        "default_events": [],
    }
    code = wait_for_code(args.port, f"{base}?state={state}", manifest, state)

    # code は 1 時間で切れるので、すぐに App の情報と鍵に換える。
    app = api("POST", f"/app-manifests/{code}/conversions")
    gh("variable", "set", VARIABLE, "--env", ENVIRONMENT, "--repo", args.repo, "--body", str(app["id"]))
    gh("secret", "set", SECRET, "--env", ENVIRONMENT, "--repo", args.repo, input_text=app["pem"])
    print(f"App「{app['slug']}」を作り、{VARIABLE} と {SECRET} を environment {ENVIRONMENT} に登録しました。")

    print("次の URL を開き、Only select repositories で対象のリポジトリだけを選んで install してください:")
    print(f"  https://github.com/apps/{app['slug']}/installations/new", flush=True)
    deadline = time.monotonic() + 1800
    while True:
        try:
            installation = api("GET", f"/repos/{args.repo}/installation", token=app_jwt(app["id"], app["pem"]))
            break
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        if time.monotonic() > deadline:
            raise SystemExit("30 分待ちましたが、install を確かめられませんでした。install のあと、もう一度確かめてください。")
        time.sleep(5)

    token = api("POST", f"/app/installations/{installation['id']}/access_tokens", token=app_jwt(app["id"], app["pem"]))
    repos = api("GET", "/installation/repositories", token=token["token"])
    names = [repo["full_name"] for repo in repos["repositories"]]
    print(f"install を確かめました。対象: {', '.join(names)}。権限: {installation['permissions']}")
    if names != [args.repo]:
        print("注意: 対象のリポジトリが 1 つに絞られていません。App の install の設定を見直してください。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
