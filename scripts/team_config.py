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


def load_config():
    with CONFIG.open("rb") as source:
        config = tomllib.load(source)
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
    return config


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
