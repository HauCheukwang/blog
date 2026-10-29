#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_via_api.py — 将本地 Hexo 博客源码一键镜像到 GitHub 仓库的 main 分支（无需 git push）。

适用场景
--------
- 当前环境到 github.com 的 git 协议(443)不可达，无法执行 `git push`；
- 或你只想用 Personal Access Token 把本地改动同步到远端 main。

行为
----
- 把 `git ls-files`（遵循 .gitignore）的全部文件镜像到 main 分支；
- 远端 main 上「仅远端存在」的文件会被删除，保证 远端 == 本地（全盘备份）；
- 推送后 .github/workflows/deploy.yml 会自动重新构建并部署 GitHub Pages。

用法
----
    GITHUB_TOKEN=ghp_xxx python3 scripts/sync_via_api.py \
        [--owner HauCheukwang] [--repo blog] [--branch main] \
        [--message "更新博文：xxx"] [--root /path/to/blog]

注意：本脚本会把本地跟踪文件「全量覆盖」到 main，若有人在网页端直接改过 main 且本地没有，
那些改动会被覆盖删除。本地永远是源（source of truth）。
"""
import os
import sys
import json
import time
import base64
import argparse
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

API = "https://api.github.com"


def api(method, path, token, data=None):
    """调用 GitHub REST API，带简单重试（应对 429/502/503）。"""
    url = API + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "hexo-sync")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8")
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            # 400/429/502/503 多为瞬时或限流，可安全重试（blob 创建是幂等的）
            if e.code in (400, 429, 502, 503) and attempt < 4:
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                err = json.loads(raw).get("message", raw)
            except Exception:
                err = raw
            return e.code, {"message": err}
        except Exception as e:  # 网络抖动
            if attempt < 4:
                time.sleep(1.5 * (attempt + 1))
                continue
            return 0, {"message": str(e)}
    return 0, {"message": "retry exhausted"}


def get_local_files(repo_root):
    # 使用 -z 以 NUL 分隔且不转义，正确处理含中文/空格的文件名
    out = subprocess.check_output(["git", "-C", repo_root, "ls-files", "-z"])
    return [name.decode("utf-8") for name in out.split(b"\0") if name]


def make_blob(args, token, path):
    with open(os.path.join(args.root, path), "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    st, res = api("POST", f"/repos/{args.owner}/{args.repo}/git/blobs", token,
                  {"content": content, "encoding": "base64"})
    if st != 201:
        raise RuntimeError(f"创建 blob 失败 {path}: {st} {res}")
    return path, res["sha"]


def main():
    ap = argparse.ArgumentParser(description="把本地 Hexo 源码镜像到 GitHub main（无需 git push）")
    ap.add_argument("--owner", default="HauCheukwang")
    ap.add_argument("--repo", default="blog")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="chore: sync blog source via API")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--root", default=os.path.dirname(here))
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: 请先设置环境变量 GITHUB_TOKEN（ghp_... 或细粒度令牌）")
        sys.exit(1)

    files = get_local_files(args.root)
    print(f"[1/5] 本地跟踪文件: {len(files)} 个")

    # 并发创建 blobs
    shas = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for path, sha in ex.map(lambda p: make_blob(args, token, p), files):
            shas[path] = sha
    print(f"[2/5] blobs 创建完成 ({len(shas)})")

    # 创建 tree（全量，引用 blob sha；远端多余文件因未出现在 tree 中而被删除）
    tree = [{"path": p, "mode": "100644", "type": "blob", "sha": shas[p]} for p in files]
    st, res = api("POST", f"/repos/{args.owner}/{args.repo}/git/trees", token, {"tree": tree})
    if st != 201:
        print("[3/5] 创建 tree 失败:", st, res)
        sys.exit(1)
    tree_sha = res["sha"]
    print("[3/5] tree 创建完成")

    # 确定父 commit
    parent = None
    st, res = api("GET", f"/repos/{args.owner}/{args.repo}/git/refs/heads/{args.branch}", token)
    if st == 200:
        parent = res["object"]["sha"]
    elif st == 404:
        st2, r2 = api("GET", f"/repos/{args.owner}/{args.repo}", token)
        if st2 == 200 and r2.get("default_branch"):
            st3, r3 = api("GET", f"/repos/{args.owner}/{args.repo}/git/refs/heads/{r2['default_branch']}", token)
            if st3 == 200:
                parent = r3["object"]["sha"]
    else:
        print("[4/5] 获取分支失败:", st, res)
        sys.exit(1)

    # 创建 commit
    commit_data = {"message": args.message, "tree": tree_sha}
    if parent:
        commit_data["parents"] = [parent]
    st, res = api("POST", f"/repos/{args.owner}/{args.repo}/git/commits", token, commit_data)
    if st != 201:
        print("[4/5] 创建 commit 失败:", st, res)
        sys.exit(1)
    commit_sha = res["sha"]
    print(f"[4/5] commit 创建完成 {commit_sha[:7]}")

    # 更新/创建 ref
    if parent:
        st, res = api("PATCH", f"/repos/{args.owner}/{args.repo}/git/refs/heads/{args.branch}", token,
                      {"sha": commit_sha})
    else:
        st, res = api("POST", f"/repos/{args.owner}/{args.repo}/git/refs", token,
                      {"ref": f"refs/heads/{args.branch}", "sha": commit_sha})
    if st not in (200, 201):
        print("[5/5] 更新 ref 失败:", st, res)
        sys.exit(1)

    print(f"[5/5] 已同步到 {args.owner}/{args.repo}@{args.branch} -> {commit_sha[:7]}")
    print("提示: GitHub Actions 会自动重新构建并部署 Pages（无需任何 Secret）。")


if __name__ == "__main__":
    main()
