"""Chỉ đọc: so sánh hợp đồng AI v1 giữa Backend và AI Service.

Không ghi file, không cập nhật contract.lock.json.
Thoát 0 nếu khớp, 1 nếu lệch, 2 nếu lỗi môi trường.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = "contracts/ai/v1/openapi.yaml"
DEFAULT_BACKEND = ROOT.parent / "ai-it-service-desk"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def diff_values(local: Any, remote: Any, path: str = "$") -> list[str]:
    if type(local) is not type(remote):
        return [f"{path}: kiểu {type(local).__name__} khác {type(remote).__name__}"]
    if isinstance(local, dict):
        problems: list[str] = []
        for key in sorted(set(local) | set(remote)):
            child = f"{path}.{key}"
            if key not in local:
                problems.append(f"{child}: chỉ có ở Backend")
            elif key not in remote:
                problems.append(f"{child}: chỉ có ở AI Service")
            else:
                problems.extend(diff_values(local[key], remote[key], child))
        return problems
    if isinstance(local, list):
        if len(local) != len(remote):
            return [f"{path}: số phần tử {len(local)} khác {len(remote)}"]
        problems = []
        for index, (left, right) in enumerate(zip(local, remote, strict=True)):
            problems.extend(diff_values(left, right, f"{path}[{index}]"))
        return problems
    if local != remote:
        return [f"{path}: {local!r} khác {remote!r}"]
    return []


def compare(local_bytes: bytes, remote_bytes: bytes, lock: dict) -> list[str]:
    problems: list[str] = []
    local_sha = sha256(local_bytes)
    if lock.get("sha256") != local_sha:
        problems.append("contract.lock.json không khớp file hợp đồng cục bộ")
    if remote_bytes != local_bytes:
        problems.append("Bản byte của hợp đồng ở Backend khác AI Service")

    try:
        local_spec = json.loads(local_bytes)
        remote_spec = json.loads(remote_bytes)
    except json.JSONDecodeError as error:
        return problems + [f"không đọc được JSON: {error}"]

    problems.extend(diff_values(local_spec, remote_spec))
    return problems


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", type=Path, default=DEFAULT_BACKEND)
    parser.add_argument("--ref", default="origin/dev", help="Ref Backend cần đối chiếu")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="git fetch trong Backend để cập nhật ref từ xa (không merge, không đổi working tree)",
    )
    args = parser.parse_args(argv)

    backend: Path = args.backend.resolve()
    try:
        _git(backend, "rev-parse", "--git-dir")
        if args.fetch:
            _git(backend, "fetch", "--quiet", "origin")
        remote_bytes = _git(backend, "show", f"{args.ref}:{CONTRACT_PATH}")
        backend_commit = _git(backend, "rev-parse", "--short", args.ref).decode().strip()
        last_change = (
            _git(
                backend,
                "log",
                "-1",
                "--format=%h %ad",
                "--date=short",
                args.ref,
                "--",
                CONTRACT_PATH,
            )
            .decode()
            .strip()
        )
    except (RuntimeError, FileNotFoundError) as error:
        print(f"Lỗi đọc Backend tại {backend}: {error}")
        return 2

    local_path = ROOT / CONTRACT_PATH
    local_bytes = local_path.read_bytes()
    lock = json.loads((ROOT / "contract.lock.json").read_text(encoding="utf-8"))

    problems = compare(local_bytes, remote_bytes, lock)

    print(f"Backend: {backend} ({args.ref} = {backend_commit})")
    print(f"Hợp đồng ở Backend lần đổi cuối: {last_change}")
    print(f"SHA-256 AI Service:  {sha256(local_bytes)}")
    print(f"SHA-256 Backend:     {sha256(remote_bytes)}")
    print(f"SHA-256 trong lock:  {lock.get('sha256')} (sourceRef {lock.get('sourceRef')})")
    if problems:
        print("KHÔNG KHỚP:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Khớp: byte và cấu trúc hợp đồng v1 giống nhau.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
