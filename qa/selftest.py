# -*- coding: utf-8 -*-
r"""selftest.py - one-command regression check for the listing pipeline.

Runs four known-good commands and compares them with the agreed baseline:
  1) qa\check_listing.py --demo --site MX   -> rc=0 and P0=0 P1=4 P2-struct=9 P2-conv=14
  2) qa\check_facts.py                      -> rc=0 and READY=81 QUARANTINED=13
  3) qa\check_facts_quality.py --demo       -> rc=0
  4) qa\check_certificates.py --demo        -> rc=0

Usage (from the repo root, or any cwd - paths are resolved from this file):
  python qa\selftest.py            # verbose: one line per check
  python qa\selftest.py --quiet    # only failures + final summary
                                   # (used by .githooks/pre-commit)

Properties:
  - stdlib only, no third-party imports;
  - finishes in a few seconds;
  - writes nothing under qa\报告 (check_listing.py gets a TEMP --out dir).
    Note: check_facts.py always refreshes kb\_index\ (gitignored by design).

Exit code: 0 = all four checks match; 1 = at least one mismatch or failure.
Called by itself with --quiet from .githooks/pre-commit.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable or "python"

CHECK_TIMEOUT = 120  # seconds per command; the whole run is normally < 2 s


def make_temp_dir():
    """Create a scratch dir for generated reports.

    Deliberately not tempfile.mkdtemp(): under the Windows file sandbox a
    mkdtemp() directory is created with 0700 and child processes are denied
    write access (WinError 5). A plain makedirs() dir inherits normal ACLs and
    works in both sandboxed and normal shells.
    """
    path = os.path.join(tempfile.gettempdir(), "dsh-selftest-" + uuid.uuid4().hex[:8])
    os.makedirs(path)
    return path


def run(args, timeout=CHECK_TIMEOUT):
    """Run one repo command; return (rc, combined_output)."""
    proc = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, timeout=timeout)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    out += (proc.stderr or b"").decode("utf-8", "replace")
    return proc.returncode, out


def find_int(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def tail_lines(text, n=4):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-n:]


def check_listing_demo(out_dir):
    """9 golden cases: P0=0 P1=4 P2-struct=9 P2-conv=14, rc=0."""
    rc, out = run([os.path.join("qa", "check_listing.py"),
                   "--demo", "--site", "MX", "--out", out_dir])
    expect = [("P0", "P0", 0), ("P1", "P1", 4),
              ("P2-结构", "P2-结构", 9), ("P2-转化", "P2-转化", 14)]
    actual = {}
    for label, pat, _want in expect:
        actual[label] = find_int(out, re.escape(pat) + r"=(-?\d+)")
    want = {label: n for label, _p, n in expect}
    ok = (rc == 0) and (actual == want)
    detail = "rc=%d P0=%s P1=%s P2-结构=%s P2-转化=%s" % (
        rc, actual["P0"], actual["P1"], actual["P2-结构"], actual["P2-转化"])
    if not ok:
        detail += " | expected rc=0 P0=0 P1=4 P2-结构=9 P2-转化=14"
    return ok, detail, out


def check_facts_baseline():
    """READY=81 QUARANTINED=13 out of 108 checked (2 apparel SKUs are skipped)."""
    rc, out = run([os.path.join("qa", "check_facts.py")])
    ready = find_int(out, r"READY=(\d+)")
    quar = find_int(out, r"QUARANTINED=(\d+)")
    skip = find_int(out, r"跳过\s*(\d+)")
    if skip is None:
        skip = find_int(out, r"SKIP=(\d+)")
    ok = (rc == 0) and (ready == 81) and (quar == 13)
    detail = "rc=%d READY=%s QUARANTINED=%s" % (rc, ready, quar)
    if skip is not None:
        detail += " skip=%d" % skip
    if not ok:
        detail += " | expected rc=0 READY=81 QUARANTINED=13"
    return ok, detail, out


def check_demo_only(label, script):
    """Demo self-tests that must exit 0."""
    rc, out = run([os.path.join("qa", script), "--demo"])
    ok = rc == 0
    detail = "rc=%d" % rc
    if not ok:
        detail += " | expected rc=0"
    return ok, detail, out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="One-command regression self-test")
    ap.add_argument("--quiet", action="store_true", help="only print failures and the summary")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(ROOT, "input")):
        print("[ERROR] input\\ not found under %s" % ROOT, file=sys.stderr)
        print("        Run this from the listing-pipeline workspace, not an installed skill copy.",
              file=sys.stderr)
        return 2

    tmp_dir = make_temp_dir()
    t0 = time.time()
    results = []
    try:
        checks = [
            ("check_listing.py --demo", lambda: check_listing_demo(tmp_dir)),
            ("check_facts.py baseline", check_facts_baseline),
            ("check_facts_quality.py --demo",
             lambda: check_demo_only("quality", "check_facts_quality.py")),
            ("check_certificates.py --demo",
             lambda: check_demo_only("certificates", "check_certificates.py")),
        ]
        for idx, (name, fn) in enumerate(checks, 1):
            try:
                ok, detail, out = fn()
            except subprocess.TimeoutExpired:
                ok, detail, out = False, "timeout after %ss" % CHECK_TIMEOUT, ""
            except Exception as exc:  # noqa: BLE001 - a crashed check must fail the suite
                ok, detail, out = False, "crashed: %r" % (exc,), ""
            results.append((idx, name, ok, detail, out))
            if not args.quiet:
                status = "PASS" if ok else "FAIL"
                print("[%d/4] %-38s %s  (%s)" % (idx, name, status, detail))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = time.time() - t0
    failed = [r for r in results if not r[2]]
    for idx, name, ok, detail, out in failed:
        print("")
        print("[FAIL] %s" % name)
        print("       got: %s" % detail)
        for ln in tail_lines(out):
            print("       | %s" % ln)
    passed = len(results) - len(failed)
    verdict = "PASS" if not failed else "FAIL"
    print("")
    print("selftest: %d/%d %s in %.1fs" % (passed, len(results), verdict, elapsed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
