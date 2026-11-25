"""Read the team catalog and render Herdr's native role templates."""

import json
import os
from pathlib import Path
import re
import shlex
import tomllib


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "Expert_Team.toml"
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
PREFIX = "herdr-team-"
MANAGED = "herdr-team-managed: Expert_Team.toml"
RUNTIME_FIELDS = {
    "claude": {"harness", "model", "settings"},
    "codex": {"harness", "model", "profile", "provider"},
}
ROLE_FIELDS = {"description", "responsibility", "access", "prompt"}
SECTIONS = {"worker", "roles"}


def template_dir():
    default = Path.home() / ".config"
    if os.name == "nt":
        default = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    home = Path(os.environ.get("XDG_CONFIG_HOME") or default)
    return home / "herdr-core" / "templates"


def validate_runtime_fields(entry, where):
    harness = entry.get("harness")
    if not isinstance(harness, str) or harness not in RUNTIME_FIELDS:
        raise ValueError(f"{where}.harness must be claude or codex")
    for key, value in entry.items():
        if key not in RUNTIME_FIELDS[harness]:
            raise ValueError(f"unsupported {harness} field {where}.{key}")
        if not isinstance(value, str) or not value.strip() or value.startswith("-") or any(
            char in value for char in "\0\r\n"
        ):
            raise ValueError(f"{where}.{key} must be a nonempty, single-line value, not an option")
    if harness == "claude" and (settings := entry.get("settings")):
        path = (ROOT / Path(settings).expanduser()).resolve()
        if not path.is_file():
            raise ValueError(f"{where}.settings is not a file: {path}")


def variant_description(role, base):
    """Mark the runtime a variant adds, so the template list stays readable."""
    description = role.get("description")
    if not description:
        return description
    if role.get("harness") != base.get("harness"):
        detail = role.get("harness", "")
        if model := role.get("model"):
            detail = f"{detail}/{model}"
    elif role.get("model") != base.get("model"):
        detail = role.get("model") or ""
    else:
        return description
    return f"{description}（{detail}）"


def merge_roles(roles):
    """Resolve [roles.<name>].base into complete role definitions."""
    resolved = {}

    def resolve(name, chain):
        if name in chain:
            raise ValueError(f"roles.{name}.base forms a cycle: {' -> '.join(chain + (name,))}")
        if name in resolved:
            return resolved[name]
        role = roles[name]
        base_name = role.get("base")
        base = {}
        if base_name is not None:
            if not isinstance(base_name, str) or base_name not in roles:
                raise ValueError(f"roles.{name}.base must name a table in [roles]")
            base = resolve(base_name, chain + (name,))
        merged = dict(base)
        for key, value in role.items():
            if key == "base":
                continue
            if key == "prompt" and key in merged:
                merged[key] = f"{merged[key]}\n\n{value}"
            else:
                merged[key] = value
        if base_name is not None and "description" not in role:
            merged["description"] = variant_description(merged, base)
        resolved[name] = merged
        return merged

    return {name: resolve(name, ()) for name in roles}


def validate_role(name, role):
    for field in ROLE_FIELDS:
        value = role.get(field)
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            raise ValueError(f"roles.{name}.{field} must be a nonempty string")
    if len(role["description"].splitlines()) != 1:
        raise ValueError(f"roles.{name}.description must fit on one line")
    if role["access"] not in ("read-only", "workspace-write"):
        raise ValueError(f"roles.{name}.access must be read-only or workspace-write")
    runtime = {key: value for key, value in role.items() if key not in ROLE_FIELDS}
    validate_runtime_fields(runtime, f"roles.{name}")


def load_config():
    with CONFIG.open("rb") as source:
        config = tomllib.load(source)
    unknown = sorted(set(config) - SECTIONS)
    if unknown:
        raise ValueError(f"unsupported table(s) {', '.join(unknown)}; define [worker] and [roles.<name>]")
    worker = config.get("worker")
    prompt = worker.get("prompt") if isinstance(worker, dict) else None
    if not isinstance(prompt, str) or not prompt.strip() or "\0" in prompt:
        raise ValueError("define [worker].prompt with the shared communication and standby instructions")
    roles = config.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("define at least one role in [roles]")
    for name, role in roles.items():
        if not NAME.fullmatch(name) or not isinstance(role, dict):
            raise ValueError(f"invalid table [roles.{name}]")
    merged = merge_roles(roles)
    for name, role in merged.items():
        validate_role(name, role)
    return {"worker": worker, "roles": merged}


def render_template(role, worker_prompt):
    harness = role["harness"]
    argv = [harness]
    if harness == "claude":
        if settings := role.get("settings"):
            argv.extend(["--settings", str((ROOT / Path(settings).expanduser()).resolve())])
    else:
        argv.extend(["--no-daemon", "--sandbox", role["access"]])
        if profile := role.get("profile"):
            argv.extend(["--profile", profile])
        if provider := role.get("provider"):
            argv.extend(["-c", f"model_provider={json.dumps(provider, ensure_ascii=False)}"])
    if model := role.get("model"):
        argv.extend(["--model", model])
    header = (
        f"---\n{MANAGED}\n"
        f"description: {role['description'].strip()}\n"
        f"command: exec {shlex.join(argv)}\n---\n"
    )
    return (
        f"{header}{worker_prompt.strip()}\n\n"
        f"访问模式：{role['access']}\n\n{role['responsibility'].strip()}\n\n{role['prompt'].strip()}\n"
    )
