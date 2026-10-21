# -*- coding: utf-8 -*-
r"""bridge.py — 浏览器桥：把 JS 丢进页面执行，取回并解码 B64 JSON。

只做四件事：调 CLI、切页面、执行 JS、解码 B64。
所有浏览器动作都走 dumate-browser-cli（规则见 `dumate-browser-use` 技能）：
  - 每次会话先 `init`；命中 [REJECT_IAB_MARK] 则本轮 re-init 用 `init --mode=extension`
  - IAB 通道不支持多 tab，本流程本来就串行，无需多 tab
本模块**不做**重试风暴：拿不到 B64 就抛错，由调用方决定是否换出口。

环境变量 DBCLI 可覆盖 CLI 可执行名（默认 `dumate-browser-cli`）。
"""
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

CLI = os.environ.get("DBCLI", "dumate-browser-cli")


class BridgeError(RuntimeError):
    pass


def run_cli(args, timeout=180):
    exe = shutil.which(CLI) or CLI
    try:
        p = subprocess.run([exe] + list(args), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise BridgeError("找不到 %s —— 先按 dumate-browser-use 技能安装 CLI" % CLI)
    except subprocess.TimeoutExpired:
        raise BridgeError("CLI 超时(%ss): %s" % (timeout, " ".join(map(str, args))[:120]))
    return ((p.stdout or "") + "\n" + (p.stderr or "")).strip(), p.returncode


def version():
    return run_cli(["--version"], timeout=30)[0]


def init(mode=None, timeout=120):
    args = ["init"] if not mode else ["init", "--mode=" + mode]
    return run_cli(args, timeout=timeout)


def goto(url, timeout=180):
    return run_cli(["goto", url], timeout=timeout)


def pick_b64(out):
    """从 CLI 输出里挑出一段能解码的 base64，返回解码后的字符串。"""
    last = "no base64 candidate"
    for text in (out, re.sub(r"\s+", "", out)):
        cands = sorted(set(re.findall(r"[A-Za-z0-9+/=]{120,}", text)), key=len, reverse=True)
        for c in cands[:6]:
            c2 = c.rstrip("=")
            c2 += "=" * (-len(c2) % 4)
            try:
                return base64.b64decode(c2).decode("utf-8"), ""
            except Exception as e:  # noqa: BLE001
                last = "decode failed: %s" % e
    return None, last


def eval_js_source(src, timeout=300):
    """执行一段 JS 表达式（IIFE 形式），返回解码后的 JSON 文本。"""
    fd, tmp = tempfile.mkstemp(suffix=".js", prefix="mlcollect_")
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        out, rc = run_cli(["eval", "--file", tmp], timeout=timeout)
        txt, why = pick_b64(out)
        if txt is None:
            # --file 不可用时退化到内联表达式
            out2, rc2 = run_cli(["eval", src], timeout=timeout)
            txt, why2 = pick_b64(out2)
            if txt is None:
                raise BridgeError("页面未返回可解码结果(%s / %s)：%s" % (why, why2, out[:400]))
        if txt.startswith("ERR:"):
            raise BridgeError("页面返回错误：" + txt[:400])
        return txt
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def eval_js_file(path, timeout=300):
    with open(path, encoding="utf-8") as f:
        return eval_js_source(f.read(), timeout=timeout)


def eval_js_returning_json(src, timeout=300):
    txt = eval_js_source(src, timeout=timeout)
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        raise BridgeError("返回的不是 JSON(%s)：%s" % (e, txt[:300]))


def eval_js_file_json(path, timeout=300):
    return eval_js_returning_json(open(path, encoding="utf-8").read(), timeout=timeout)


def js_set(expr):
    """把值挂到 window 变量上（expr 已是 JS 字面量/表达式）。"""
    return eval_js_source("(() => { %s return btoa('ok'); })()" % expr)


def sleep(sec):
    time.sleep(sec)