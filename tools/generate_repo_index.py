#!/usr/bin/env python3
"""Generate lightweight repository context/index artifacts.

Outputs:
  - .codex/repo-index.json
  - .codex/repo-index.md
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import subprocess


EXCLUDED_DIR_NAMES = {".git", "build", ".gradle", ".kotlin", ".idea", "out", "target"}


def include_file(path: pathlib.Path) -> bool:
    return not any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def git(cmd: list[str]) -> str:
    return subprocess.check_output(["git", *cmd], text=True).strip()


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent

    files = [p for p in root.rglob("*") if p.is_file() and include_file(p.relative_to(root))]
    rel_files = [p.relative_to(root) for p in files]

    ext_counts: collections.Counter[str] = collections.Counter()
    for rel_path in rel_files:
        ext_counts[rel_path.suffix.lower() or "<noext>"] += 1

    modules: list[dict[str, int | str]] = []
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith("spring-"):
            mfiles = [x for x in p.rglob("*") if x.is_file() and include_file(x.relative_to(root))]
            modules.append(
                {
                    "name": p.name,
                    "file_count": len(mfiles),
                    "src_main_java": sum(1 for x in mfiles if "src/main/java" in str(x)),
                    "src_test_java": sum(1 for x in mfiles if "src/test/java" in str(x)),
                }
            )
    modules.sort(key=lambda m: str(m["name"]))

    pkg_roots: collections.Counter[str] = collections.Counter()
    for p in root.glob("**/src/main/java/**/*.java"):
        relp = p.relative_to(root)
        if not include_file(relp):
            continue
        parts = relp.parts
        java_idx = parts.index("java")
        pkg_parts = parts[java_idx + 1 : -1]
        if not pkg_parts:
            continue
        pkg_root = ".".join(pkg_parts[:3])
        pkg_roots[pkg_root] += 1

    meta = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head_commit": git(["rev-parse", "HEAD"]),
        "total_files_excluding_generated_dirs": len(rel_files),
        "top_extensions": ext_counts.most_common(25),
        "modules": modules,
        "top_package_roots": pkg_roots.most_common(30),
    }

    codex_dir = root / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    (codex_dir / "repo-index.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = [
        "# Repository Context Index",
        "",
        f"Generated (UTC): {meta['generated_at_utc']}",
        f"Branch: `{meta['branch']}`",
        f"HEAD: `{meta['head_commit']}`",
        f"Total files (excluding generated/build/git dirs): **{meta['total_files_excluding_generated_dirs']}**",
        "",
        "## Modules",
    ]

    for m in modules:
        lines.append(
            f"- `{m['name']}`: files={m['file_count']}, "
            f"src/main/java={m['src_main_java']}, src/test/java={m['src_test_java']}"
        )

    lines.append("")
    lines.append("## Top file extensions")
    for ext, count in meta["top_extensions"]:
        lines.append(f"- `{ext}`: {count}")

    lines.append("")
    lines.append("## Top Java package roots (first 3 segments)")
    for pkg, count in meta["top_package_roots"]:
        lines.append(f"- `{pkg}`: {count}")

    lines.extend(
        [
            "",
            "## Regenerate",
            "- `python tools/generate_repo_index.py`",
            "",
            "## Notes",
            "- Local context artifact intended to speed repository orientation for future tasks.",
            "- Commit updates when repository structure changes substantially.",
        ]
    )

    (codex_dir / "repo-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
