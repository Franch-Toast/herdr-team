#!/usr/bin/env python3
"""Register native Herdr templates from Expert_Team.toml."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
from team_config import MANAGED, PREFIX, ROOT, load_config, render_template, template_dir


def is_managed(path):
    if path.is_symlink():
        # Replace links to the first release's bundled templates during migration.
        legacy = {f"{PREFIX}{role}.md" for role in ("architect", "engineer", "tester")}
        return path.name in legacy and path.resolve() == ROOT / "assets/herdr-templates" / path.name
    if path.is_file():
        with path.open(encoding="utf-8", errors="replace") as source:
            return source.readline() == "---\n" and source.readline().strip() == MANAGED
    return False


def replace(path, content):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        try:
            out.write(content)
            out.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check drift without writing")
    args = parser.parse_args()
    try:
        config = load_config()
        directory = template_dir()
        desired = {}
        worker_prompt = config["worker"]["prompt"]
        for name, role in config["roles"].items():
            desired[directory / f"{PREFIX}{name}.md"] = render_template(role, worker_prompt)
        changes = {"missing": [], "changed": [], "obsolete": [], "conflicts": []}
        for path, content in desired.items():
            if not path.exists() and not path.is_symlink():
                changes["missing"].append(path)
            elif not is_managed(path):
                changes["conflicts"].append(path)
            elif path.is_symlink() or path.read_text(encoding="utf-8") != content:
                changes["changed"].append(path)
        changes["obsolete"] = [path for path in sorted(directory.glob(f"{PREFIX}*.md"))
                                if path not in desired and is_managed(path)]
        print(json.dumps({"directory": str(directory), **{
            key: [path.name for path in paths] for key, paths in changes.items()
        }}, ensure_ascii=False))
        if changes["conflicts"]:
            return 1
        if args.check:
            return 2 if any(changes.values()) else 0
        directory.mkdir(parents=True, exist_ok=True)
        for path in changes["missing"] + changes["changed"]:
            replace(path, desired[path])
        for path in changes["obsolete"]:
            path.unlink()
        return 0
    except (OSError, ValueError) as exc:
        print(f"herdr-team: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
