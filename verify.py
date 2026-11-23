"""Independent re-run check. One command, about two minutes on a laptop:

    python verify.py

1. Checks every bundled data file against data/MANIFEST.sha256 (same input data as ours).
2. Runs the unit tests.
3. Re-runs both studies (run.py, run_vs.py) into a temporary folder.
4. Compares every result table (CSV/JSON) with the submitted results/ folder, number by number.

Warns if installed packages differ from the pins in requirements.txt. Prints PASS/FAIL per file and writes verify_report.txt. Do not use --download before verifying:
Yahoo Finance revises adjusted prices over time, so freshly downloaded data gives slightly
different numbers. That is a data difference, not a code difference; step 1 detects it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA, RES = ROOT / "data", ROOT / "results"


def sha256(p: Path) -> str:
    # line endings normalised, so a Windows git checkout (CRLF) hashes the same as the zip
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_manifest():
    files = sorted(p for p in DATA.rglob("*.csv"))
    (DATA / "MANIFEST.sha256").write_text("".join(f"{sha256(p)}  {p.relative_to(DATA).as_posix()}\n" for p in files))
    print(f"wrote manifest for {len(files)} files")


def check_data(lines: list[str]) -> bool:
    bad = []
    for row in (DATA / "MANIFEST.sha256").read_text().splitlines():
        digest, name = row.split("  ", 1)
        p = DATA / name
        if not p.exists() or sha256(p) != digest:
            bad.append(name)
    total = len((DATA / "MANIFEST.sha256").read_text().splitlines())
    msg = f"[{'PASS' if not bad else 'FAIL'}] data: {total - len(bad)}/{total} files match the manifest"
    if bad:
        msg += "; changed or missing: " + ", ".join(bad[:10])
    lines.append(msg)
    return not bad


def check_versions(lines: list[str]) -> None:
    """Warn (not fail) when installed packages differ from the pins in requirements.txt."""
    from importlib.metadata import PackageNotFoundError, version
    off = []
    for row in (ROOT / "requirements.txt").read_text().splitlines():
        if "==" in row and not row.startswith("#"):
            name, want = row.split("==")
            try:
                have = version(name.strip())
            except PackageNotFoundError:
                have = "missing"
            if have != want.strip():
                off.append(f"{name.strip()} {have} (pinned {want.strip()})")
    lines.append("[PASS] package versions match requirements.txt" if not off else
                 "[WARN] package versions differ from requirements.txt: " + ", ".join(off) +
                 ". Differences in results/vs/ can come from this (gradient boosting changes between "
                 "scikit-learn versions); run  pip install -r requirements.txt  and re-run.")


def same(a: Path, b: Path) -> tuple[bool, str]:
    if a.suffix == ".json":
        x, y = json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8"))
        nums = lambda o: {k: v for k, v in o.items() if isinstance(v, (int, float))} if isinstance(o, dict) else {}
        close = all(abs(nums(x)[k] - v) <= 1e-6 * max(1.0, abs(v)) for k, v in nums(y).items() if k in nums(x))
        rest = lambda o: {k: v for k, v in o.items() if k not in nums(o)} if isinstance(o, dict) else o
        return close and rest(x) == rest(y) and nums(x).keys() == nums(y).keys(), ""
    x, y = pd.read_csv(a), pd.read_csv(b)
    if x.shape != y.shape or list(x.columns) != list(y.columns):
        return False, f"shape {x.shape} vs {y.shape}"
    worst = 0.0
    for c in x.columns:
        nx, ny = (pd.to_numeric(s, errors="coerce").astype(float) for s in (x[c], y[c]))
        num = nx.notna() | ny.notna()
        txt = lambda s: s[~num].astype(object).fillna("").astype(str)  # blank cells compare equal
        if not (txt(x[c]) == txt(y[c])).all():
            return False, f"text differs in column '{c}'"
        if num.any():
            if not (nx[num].isna() == ny[num].isna()).all():
                return False, f"missing values differ in column '{c}'"
            d = np.abs(nx[num] - ny[num]).fillna(0)
            worst = max(worst, float((d / np.maximum(1.0, np.abs(ny[num].fillna(0)))).max()))
    return worst < 1e-6, f"largest relative difference {worst:.1e}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    if "--write-manifest" in sys.argv:
        return write_manifest()
    lines, ok = [], True
    check_versions(lines)
    ok &= check_data(lines)

    t = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    summary = (t.stdout.strip().splitlines() or ["no output"])[-1]
    lines.append(f"[{'PASS' if t.returncode == 0 else 'FAIL'}] unit tests: {summary}")
    ok &= t.returncode == 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for script, out in (("run.py", tmp / "run"), ("run_vs.py", tmp / "vs")):
            print(f"running {script} ...", flush=True)
            r = subprocess.run([sys.executable, script, "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            if r.returncode:
                lines.append(f"[FAIL] {script} crashed:\n{r.stderr[-2000:]}")
                ok = False
        pairs = [(p, tmp / "run" / p.name) for p in sorted(RES.glob("*.csv")) + sorted(RES.glob("*.json"))]
        pairs += [(p, tmp / "vs" / p.name) for p in sorted((RES / "vs").glob("*.csv")) + sorted((RES / "vs").glob("*.json"))]
        n_ok = 0
        for sub, new in pairs:
            if not new.exists():
                lines.append(f"[FAIL] {sub.relative_to(ROOT)}: not produced by the re-run")
                ok = False
                continue
            good, why = same(new, sub)
            n_ok += good
            ok &= good
            lines.append(f"[{'PASS' if good else 'FAIL'}] {sub.relative_to(ROOT).as_posix()}  {why}")
        lines.append(f"\n{n_ok}/{len(pairs)} result files reproduced.")
    lines.append("VERDICT: " + ("ALL RESULTS REPRODUCED" if ok else "MISMATCH, see FAIL lines above"))
    text = f"python {sys.version.split()[0]}, pandas {pd.__version__}, numpy {np.__version__}\n\n" + "\n".join(lines)
    (ROOT / "verify_report.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
