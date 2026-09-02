"""Prepare and apply an idempotent GitHub Project import for Capstone tasks.

Default behavior is a dry run. Dry run performs read-only remote queries through
GitHub CLI and writes local audit artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO = "Camila-Aroca/Proyecto-Capstone"
PROJECT_OWNER = "Camila-Aroca"
PROJECT_NUMBER = "12"
PROJECT_NAME = "Tablero Kanban Capstone"
PROJECT_URL = "https://github.com/users/Camila-Aroca/projects/12"
REPORT_PATH = Path("reports/project/PROJECT_STATUS_AUDIT_2026-08-31.md")
MANIFEST_PATH = Path("docs/04-gestion-proyecto/github_project_tasks.json")
DRY_RUN_REPORT_PATH = Path("reports/project/GITHUB_PROJECT_IMPORT_DRY_RUN_2026-08-31.md")
SOURCE_REPORT = REPORT_PATH.as_posix()

TASK_MARKER_RE = re.compile(r"<!--\s*capstone-task-id:\s*([A-Z]+-\d{3})\s*-->")

MILESTONES = {
    "Fase 1": {
        "title": "Fase 1 - Presentación del proyecto",
        "due_on": "2026-09-03",
    },
    "Fase 2.1": {
        "title": "Fase 2.1 - Avance y documentación",
        "due_on": "2026-10-15",
    },
    "Fase 2.3": {
        "title": "Fase 2.3 - Presentación y entrega final",
        "due_on": "2026-11-26",
    },
    "Fase 3": {
        "title": "Fase 3 - Presentación ante comisión",
        "due_on": "2026-12-04",
    },
}

SPECIAL_ISSUE = {
    "number": 1,
    "title": "Documentar fuentes de datos y procedimiento reproducible de obtención",
    "purpose": (
        "Documentar fuentes oficiales, URLs, periodos disponibles, procedimiento "
        "de descarga, manifests, hashes y política de no versionar datos RAW."
    ),
    "kanban_status": "Backlog",
    "priority": "P1",
    "size": "M",
    "phase": "Fase 2.1",
    "area": "Datos",
    "milestone": MILESTONES["Fase 2.1"]["title"],
}

FUTURE_SIZE_BY_ID = {
    "NEXT-001": "XS",
    "NEXT-002": "S",
    "NEXT-003": "S",
    "NEXT-004": "S",
    "NEXT-005": "M",
    "NEXT-006": "S",
    "NEXT-007": "S",
    "NEXT-008": "S",
    "NEXT-009": "XS",
    "NEXT-010": "XS",
    "NEXT-011": "XS",
    "NEXT-012": "S",
    "NEXT-013": "S",
    "NEXT-014": "M",
    "NEXT-015": "M",
    "NEXT-016": "S",
    "NEXT-017": "M",
    "NEXT-018": "M",
    "NEXT-019": "M",
    "NEXT-020": "M",
    "NEXT-021": "S",
    "NEXT-022": "M",
    "NEXT-023": "M",
    "NEXT-024": "M",
    "NEXT-025": "M",
    "NEXT-026": "S",
    "NEXT-027": "M",
    "NEXT-028": "M",
    "NEXT-029": "L",
    "NEXT-030": "M",
    "NEXT-031": "M",
    "NEXT-032": "M",
    "NEXT-033": "S",
    "NEXT-034": "L",
    "NEXT-035": "S",
    "NEXT-036": "M",
    "NEXT-037": "L",
    "NEXT-038": "S",
    "NEXT-039": "M",
    "NEXT-040": "XS",
}

EXPECTED_FIELD_OPTIONS = {
    "Status": {"Backlog", "Ready", "In progress", "In review", "Done"},
    "Priority": {"P0", "P1", "P2"},
    "Size": {"XS", "S", "M", "L", "XL"},
    "Fase": {"Fase 1", "Fase 2.1", "Fase 2.3", "Fase 3"},
    "Área": {"Gestión", "Datos", "Modelo", "Geoespacial", "Plataforma", "Documentación", "QA", "Presentación"},
}


class PreflightError(RuntimeError):
    """Raised when remote state is unsafe for applying writes."""


class ApplyError(RuntimeError):
    """Raised when an apply step fails after preflight."""


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_gh(args: list[str], check: bool = False) -> CommandResult:
    """Run a GitHub CLI command without invoking a shell."""
    result = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    command_result = CommandResult(args=args, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return command_result


def parse_markdown_row(line: str) -> list[str]:
    """Parse a simple GitHub-flavored Markdown table row."""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def extract_table_rows(section_start: str, next_section: str) -> list[list[str]]:
    text = REPORT_PATH.read_text(encoding="utf-8")
    start = text.index(section_start)
    end = text.index(next_section, start)
    section = text[start:end]
    rows = []
    for line in section.splitlines():
        cells = parse_markdown_row(line)
        if not cells or cells[0] in {"ID", "---"}:
            continue
        if set(cells[0]) == {"-"}:
            continue
        rows.append(cells)
    return rows


def map_kanban_status(report_status: str, phase: str, priority: str) -> str:
    if report_status == "Terminado":
        return "Done"
    if report_status == "Requiere verificación":
        return "In review"
    if report_status == "En curso":
        return "In progress"
    if report_status == "Bloqueado":
        return "Backlog"
    if report_status == "Por hacer" and phase == "Fase 1" and priority == "Alta":
        return "Ready"
    return "Backlog"


def map_priority(source_type: str, priority: str, phase: str) -> str:
    if source_type == "historical":
        return "P2"
    if priority == "Alta" and phase == "Fase 1":
        return "P0"
    if priority == "Alta" or (phase == "Fase 1" and priority == "Media"):
        return "P1"
    return "P2"


def normalize_priority(raw_priority: str) -> str:
    if raw_priority.startswith("Alta"):
        return "Alta"
    if raw_priority.startswith("Media"):
        return "Media"
    if raw_priority.startswith("Baja"):
        return "Baja"
    return raw_priority or "Media"


def milestone_for_phase(phase: str) -> str:
    clean_phase = phase.replace(" si alcanza", "")
    return MILESTONES.get(clean_phase, MILESTONES["Fase 2.1"])["title"]


def build_issue_description(task: dict[str, Any]) -> str:
    if task["source_type"] == "historical":
        if task["report_status"] == "Terminado":
            return f"Registrar como realizado: {task['title']}."
        return f"Registrar entregable existente que requiere verificación: {task['title']}."
    return f"Ejecutar la tarea pendiente: {task['title']}."


def build_issue_body(task: dict[str, Any]) -> str:
    marker = f"<!-- capstone-task-id: {task['task_id']} -->"
    checked = task["source_type"] == "historical" and task["report_status"] == "Terminado"
    prefix = "[x]" if checked else "[ ]"
    dependencies = ", ".join(task["dependencies"]) if task["dependencies"] else "Ninguna"
    warning = ""
    if task["report_status"] == "Bloqueado":
        warning = "\n\n> Advertencia: esta tarea está bloqueada; revisar dependencia antes de ejecutarla."

    verification_note = ""
    if task["source_type"] == "historical" and task["report_status"] == "Requiere verificación":
        verification_note = (
            "\n\nEntregable existente: sí, según la evidencia del reporte.\n"
            "Verificación pendiente: reproducir ejecución, datos o pruebas según corresponda."
        )

    return (
        f"{marker}\n\n"
        "## Objetivo\n\n"
        f"{task['description']}\n\n"
        "## Evidencia o contexto\n\n"
        f"{task['evidence']}{verification_note}{warning}\n\n"
        "## Criterios de aceptación\n\n"
        f"- {prefix} {task['acceptance_criteria']}\n\n"
        "## Dependencias\n\n"
        f"{dependencies}\n\n"
        "## Metadatos\n\n"
        f"- Fase: {task['phase']}\n"
        f"- Área: {task['area']}\n"
        f"- Prioridad: {task['priority']}\n"
        f"- Tamaño: {task['size'] or 'No asignado'}\n"
        f"- Fuente: {task['source_report']}\n"
    )


def parse_dependencies(raw_dependencies: str) -> list[str]:
    if not raw_dependencies or raw_dependencies == "Ninguna" or raw_dependencies == "Esta auditoría":
        return []
    return re.findall(r"(?:DONE|NEXT)-\d{3}", raw_dependencies)


def build_manifest() -> dict[str, Any]:
    done_rows = extract_table_rows(
        "## 3. Inventario granular de trabajo ya realizado",
        "## 4. Estado por componente",
    )
    next_rows = extract_table_rows(
        "## 10. Inventario de trabajo actual y futuro",
        "### Estado del GitHub Project",
    )

    tasks: list[dict[str, Any]] = []
    for cells in done_rows:
        task_id, title, report_status, evidence, area, phase, acceptance, limitation = cells
        task = {
            "task_id": task_id,
            "title": title,
            "description": "",
            "source_type": "historical",
            "report_status": report_status,
            "kanban_status": map_kanban_status(report_status, phase, "Baja"),
            "area": area,
            "phase": phase,
            "priority": "P2",
            "size": "",
            "evidence": evidence,
            "acceptance_criteria": acceptance,
            "dependencies": [],
            "milestone": milestone_for_phase(phase),
            "close_when_applied": report_status == "Terminado",
            "source_report": SOURCE_REPORT,
            "notes": limitation,
        }
        task["description"] = build_issue_description(task)
        task["issue_body"] = build_issue_body(task)
        tasks.append(task)

    for cells in next_rows:
        task_id, title, report_status, evidence, area, priority_raw, phase, dependencies_raw, acceptance = cells
        priority_label = normalize_priority(priority_raw)
        priority = map_priority("future", priority_label, phase)
        task = {
            "task_id": task_id,
            "title": title,
            "description": "",
            "source_type": "future",
            "report_status": report_status,
            "kanban_status": map_kanban_status(report_status, phase, priority_label),
            "area": area,
            "phase": phase,
            "priority": priority,
            "size": FUTURE_SIZE_BY_ID.get(task_id, "M"),
            "evidence": evidence,
            "acceptance_criteria": acceptance,
            "dependencies": parse_dependencies(dependencies_raw),
            "milestone": milestone_for_phase(phase),
            "close_when_applied": False,
            "source_report": SOURCE_REPORT,
            "notes": f"Prioridad del reporte: {priority_raw}. Dependencias originales: {dependencies_raw}.",
        }
        task["description"] = build_issue_description(task)
        task["issue_body"] = build_issue_body(task)
        tasks.append(task)

    manifest = {
        "metadata": {
            "generated_at": date.today().isoformat(),
            "repository": REPO,
            "project_owner": PROJECT_OWNER,
            "project_number": int(PROJECT_NUMBER),
            "project_name": PROJECT_NAME,
            "project_url": PROJECT_URL,
            "source_report": SOURCE_REPORT,
            "expected_report_tasks": 62,
            "expected_historical_tasks": 22,
            "expected_future_tasks": 40,
            "expected_special_existing_issues": 1,
            "expected_final_items_without_milestones": 63,
        },
        "tasks": tasks,
        "special_existing_issue": SPECIAL_ISSUE,
        "milestones": MILESTONES,
    }
    if len(tasks) != 62:
        raise ValueError(f"Expected 62 tasks from report, got {len(tasks)}")
    historical = [task for task in tasks if task["source_type"] == "historical"]
    future = [task for task in tasks if task["source_type"] == "future"]
    if len(historical) != 22 or len(future) != 40:
        raise ValueError(f"Expected 22 historical and 40 future tasks, got {len(historical)} and {len(future)}")
    return manifest


def write_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect_remote_state() -> dict[str, Any]:
    commands = {
        "auth_status": ["auth", "status"],
        "viewer": ["api", "user"],
        "repo": ["api", f"repos/{REPO}"],
        "issues": [
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,body,state,url,milestone",
        ],
        "project": ["project", "view", PROJECT_NUMBER, "--owner", PROJECT_OWNER, "--format", "json"],
        "project_fields": ["project", "field-list", PROJECT_NUMBER, "--owner", PROJECT_OWNER, "--format", "json", "--limit", "100"],
        "project_items": [
            "project",
            "item-list",
            PROJECT_NUMBER,
            "--owner",
            PROJECT_OWNER,
            "--format",
            "json",
            "--limit",
            "1000",
        ],
        "milestones": ["api", f"repos/{REPO}/milestones?state=all"],
    }

    state: dict[str, Any] = {"commands": {}}
    for name, args in commands.items():
        result = run_gh(args)
        state["commands"][name] = {
            "args": ["gh", *args],
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }
        if result.returncode == 0:
            if name == "auth_status":
                state[name] = result.stdout.strip()
            else:
                try:
                    state[name] = json.loads(result.stdout or "{}")
                except json.JSONDecodeError:
                    state[name] = result.stdout.strip()
        else:
            state[name] = None
    return state


def issue_marker_counts(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        body = issue.get("body") or ""
        for marker in TASK_MARKER_RE.findall(body):
            found.setdefault(marker, []).append(issue)
    return found


def normalize_issue_state(issue: dict[str, Any] | None) -> str:
    if not issue:
        return ""
    return str(issue.get("state") or "").upper()


def issue_should_be_closed(task: dict[str, Any]) -> bool:
    return bool(task["close_when_applied"])


def issue_matches_task(issue: dict[str, Any], task: dict[str, Any]) -> bool:
    expected_state = "CLOSED" if issue_should_be_closed(task) else "OPEN"
    milestone = issue.get("milestone") or {}
    milestone_title = milestone.get("title") if isinstance(milestone, dict) else None
    return (
        issue.get("title") == task["title"]
        and (issue.get("body") or "") == task["issue_body"]
        and milestone_title == task["milestone"]
        and normalize_issue_state(issue) == expected_state
    )


def issue_has_closed_conflict(issue: dict[str, Any], task: dict[str, Any]) -> bool:
    return not issue_should_be_closed(task) and normalize_issue_state(issue) == "CLOSED"


def classify_actions(manifest: dict[str, Any], remote_state: dict[str, Any]) -> list[dict[str, Any]]:
    issues = remote_state.get("issues")
    if not isinstance(issues, list):
        return [
            {"task": task, "action": "CONFLICT", "issue": None, "matches": [], "reason": "issues_unavailable"}
            for task in manifest["tasks"]
        ]
    marker_map = issue_marker_counts(issues)
    actions = []
    for task in manifest["tasks"]:
        matches = marker_map.get(task["task_id"], [])
        if len(matches) == 0:
            action = "CREATE"
            issue = None
            reason = ""
        elif len(matches) == 1:
            issue = matches[0]
            if issue_has_closed_conflict(issue, task):
                action = "CONFLICT"
                reason = "issue_closed_but_expected_open"
            elif issue_matches_task(issue, task):
                item = project_item_for_issue(remote_state, issue.get("url", ""))
                if issue_project_fields_differ(item, task):
                    action = "UPDATE"
                    reason = "project_fields_differ_or_item_missing"
                else:
                    action = "REUSE"
                    reason = ""
            else:
                action = "UPDATE"
                reason = "issue_differs_from_manifest"
        else:
            issue = None
            action = "CONFLICT"
            reason = "duplicate_marker"
        if task["size"] == "NEEDS_SPLIT":
            action = "NEEDS_SPLIT"
            reason = "needs_split"
        actions.append({"task": task, "action": action, "issue": issue, "matches": matches, "reason": reason})
    return actions


def count_actions(actions: list[dict[str, Any]], include_special_issue: bool = False) -> dict[str, int]:
    counts = {"CREATE": 0, "UPDATE": 0, "REUSE": 0, "CONFLICT": 0, "NEEDS_SPLIT": 0}
    for action in actions:
        counts[action["action"]] = counts.get(action["action"], 0) + 1
    if include_special_issue:
        counts["UPDATE"] += 1
    return counts


def find_special_issue(remote_state: dict[str, Any]) -> dict[str, Any] | None:
    issues = remote_state.get("issues") or []
    if not isinstance(issues, list):
        return None
    for issue in issues:
        if issue.get("number") == SPECIAL_ISSUE["number"]:
            return issue
    return None


def get_field_options(remote_state: dict[str, Any]) -> dict[str, set[str]]:
    fields = remote_state.get("project_fields")
    if not isinstance(fields, dict):
        return {}
    options: dict[str, set[str]] = {}
    for field in fields.get("fields", []):
        name = field.get("name")
        if not name:
            continue
        options[name] = {option.get("name") for option in field.get("options", []) if option.get("name")}
    return options


def validate_field_options(remote_state: dict[str, Any]) -> None:
    options = get_field_options(remote_state)
    for field_name, expected in EXPECTED_FIELD_OPTIONS.items():
        if field_name not in options:
            raise PreflightError(f"Project field not found: {field_name}")
        actual = options[field_name]
        missing = expected - actual
        extra = actual - expected
        if missing or extra:
            missing_list = ", ".join(sorted(missing))
            extra_list = ", ".join(sorted(extra))
            raise PreflightError(
                f"Project field `{field_name}` options mismatch; missing: {missing_list or 'none'}; "
                f"extra: {extra_list or 'none'}"
            )


def parse_due_date(raw_due: str | None) -> str | None:
    if not raw_due:
        return None
    try:
        return datetime.fromisoformat(raw_due.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return raw_due[:10]


def github_milestone_due_timestamp(calendar_date: str) -> str:
    return f"{calendar_date}T12:00:00Z"


def milestone_actions(remote_state: dict[str, Any]) -> list[dict[str, str]]:
    milestones = remote_state.get("milestones")
    if not isinstance(milestones, list):
        return [
            {
                "title": milestone["title"],
                "due_on": milestone["due_on"],
                "action": "CONFLICT",
                "reason": "milestones_unavailable",
            }
            for milestone in MILESTONES.values()
        ]
    by_title = {milestone.get("title"): milestone for milestone in milestones}
    actions = []
    for milestone in MILESTONES.values():
        existing = by_title.get(milestone["title"])
        if not existing:
            actions.append({**milestone, "action": "CREATE", "reason": ""})
            continue
        existing_due = parse_due_date(existing.get("due_on"))
        if existing_due == milestone["due_on"]:
            actions.append({**milestone, "action": "REUSE", "reason": ""})
        else:
            actions.append(
                {
                    **milestone,
                    "action": "CONFLICT",
                    "reason": f"due date differs: remote={existing_due}",
                }
            )
    return actions


def validate_remote_state(remote_state: dict[str, Any]) -> None:
    required = ["auth_status", "viewer", "repo", "issues", "project", "project_fields", "project_items", "milestones"]
    for key in required:
        command = remote_state.get("commands", {}).get(key)
        if command and command.get("returncode") != 0:
            raise PreflightError(f"Remote preflight query failed: {key}: {command.get('stderr')}")
        if remote_state.get(key) is None:
            raise PreflightError(f"Remote preflight query returned no data: {key}")

    viewer = remote_state.get("viewer")
    if not isinstance(viewer, dict) or viewer.get("login") != PROJECT_OWNER:
        raise PreflightError(f"Authenticated user must be {PROJECT_OWNER}; got {viewer!r}")

    repo = remote_state.get("repo")
    if not isinstance(repo, dict) or repo.get("full_name") != REPO:
        raise PreflightError(f"Repository must be {REPO}; got {repo!r}")

    issues = remote_state.get("issues")
    if not isinstance(issues, list):
        raise PreflightError("Issues response must be a list and cannot be treated as empty.")

    project = remote_state.get("project")
    project_owner = project.get("owner", {}).get("login") if isinstance(project, dict) else None
    if not (
        isinstance(project, dict)
        and str(project.get("number")) == PROJECT_NUMBER
        and project.get("title") == PROJECT_NAME
        and project_owner == PROJECT_OWNER
    ):
        raise PreflightError(f"Project identity mismatch: {project!r}")

    if find_special_issue(remote_state) is None:
        raise PreflightError("Required existing issue #1 was not found.")

    special_issue = find_special_issue(remote_state)
    if normalize_issue_state(special_issue) == "CLOSED":
        raise PreflightError("Existing issue #1 is closed; stop for manual review instead of reopening it.")

    validate_project_items_structure(remote_state, require_special_issue_item=True)
    validate_field_options(remote_state)

    for milestone in milestone_actions(remote_state):
        if milestone["action"] == "CONFLICT":
            raise PreflightError(f"Milestone conflict for {milestone['title']}: {milestone['reason']}")


def project_item_for_issue(remote_state: dict[str, Any], issue_url: str) -> dict[str, Any] | None:
    items = remote_state.get("project_items")
    if not isinstance(items, dict):
        return None
    item_list = items.get("items")
    if not isinstance(item_list, list):
        return None
    for item in item_list:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or {}
        if not isinstance(content, dict):
            continue
        if content.get("url") == issue_url:
            return item
    return None


def validate_project_items_structure(remote_state: dict[str, Any], require_special_issue_item: bool = False) -> None:
    project_items = remote_state.get("project_items")
    if not isinstance(project_items, dict):
        raise PreflightError("Project items response must be a dictionary.")

    items = project_items.get("items")
    if not isinstance(items, list):
        raise PreflightError("Project items response must contain an `items` list.")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise PreflightError(f"Project item at index {index} must be a dictionary.")
        content = item.get("content")
        if content is None:
            continue
        if not isinstance(content, dict):
            raise PreflightError(f"Project item at index {index} has invalid content.")
        url = content.get("url")
        if url is not None and not isinstance(url, str):
            raise PreflightError(f"Project item at index {index} has invalid content.url.")

    special_issue = find_special_issue(remote_state)
    if require_special_issue_item and special_issue:
        special_url = special_issue.get("url")
        if not isinstance(special_url, str) or not project_item_for_issue(remote_state, special_url):
            raise PreflightError("Project item for existing issue #1 was not found by URL.")


def issue_project_fields_differ(item: dict[str, Any] | None, task: dict[str, Any]) -> bool:
    if item is None:
        return True
    expected = {
        "status": task["kanban_status"],
        "priority": task["priority"],
        "size": task["size"] or None,
        "fase": task["phase"].replace(" si alcanza", ""),
        "area": task["area"],
    }
    actual = {
        "status": item.get("status") or item.get("Status"),
        "priority": item.get("priority") or item.get("Priority"),
        "size": item.get("size") or item.get("Size"),
        "fase": item.get("fase") or item.get("Fase"),
        "area": item.get("area") or item.get("Área") or item.get("Area"),
    }
    return any(expected[key] and actual.get(key) != expected[key] for key in expected)


def build_plan_hash(
    manifest: dict[str, Any],
    actions: list[dict[str, Any]],
    milestone_plan: list[dict[str, str]],
    remote_state: dict[str, Any],
) -> str:
    special_issue = find_special_issue(remote_state)
    special_milestone = special_issue.get("milestone") if special_issue else None
    special_project_item = project_item_for_issue(remote_state, special_issue.get("url", "")) if special_issue else None
    payload = {
        "special_issue_update": {
            "number": SPECIAL_ISSUE["number"],
            "remote_issue": special_issue.get("url") if special_issue else None,
            "remote_current": {
                "title": special_issue.get("title") if special_issue else None,
                "body": special_issue.get("body") if special_issue else None,
                "state": normalize_issue_state(special_issue),
                "milestone": special_milestone.get("title") if isinstance(special_milestone, dict) else None,
                "project_item": special_project_item,
            },
            "title": SPECIAL_ISSUE["title"],
            "body": special_issue_body(),
            "fields": {
                "status": SPECIAL_ISSUE["kanban_status"],
                "priority": SPECIAL_ISSUE["priority"],
                "size": SPECIAL_ISSUE["size"],
                "phase": SPECIAL_ISSUE["phase"],
                "area": SPECIAL_ISSUE["area"],
            },
            "milestone": SPECIAL_ISSUE["milestone"],
        },
        "milestones": milestone_plan,
        "tasks": [],
    }
    for action in actions:
        task = action["task"]
        issue = action["issue"]
        payload["tasks"].append(
            {
                "task_id": task["task_id"],
                "action": action["action"],
                "remote_issue": issue.get("url") if issue else None,
                "title": task["title"],
                "body": task["issue_body"],
                "state": "CLOSED" if task["close_when_applied"] else "OPEN",
                "fields": {
                    "status": task["kanban_status"],
                    "priority": task["priority"],
                    "size": task["size"],
                    "phase": task["phase"],
                    "area": task["area"],
                },
                "milestone": task["milestone"],
                "close_when_applied": task["close_when_applied"],
                "reason": action.get("reason", ""),
            }
        )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_remote_summary(remote_state: dict[str, Any]) -> tuple[str, list[str]]:
    warnings = []
    lines = []
    viewer = remote_state.get("viewer")
    login = viewer.get("login") if isinstance(viewer, dict) else "No disponible"
    lines.append(f"- Cuenta autenticada: {login}")

    repo = remote_state.get("repo")
    if isinstance(repo, dict):
        lines.append(f"- Repositorio detectado: {repo.get('full_name')} ({repo.get('visibility', 'sin visibilidad')})")
    else:
        lines.append("- Repositorio detectado: No disponible")
        warnings.append("No fue posible leer el repositorio remoto.")

    project = remote_state.get("project")
    if isinstance(project, dict):
        lines.append(f"- Project detectado: {project.get('title', PROJECT_NAME)}")
    else:
        lines.append("- Project detectado: No disponible")
        warnings.append("No fue posible leer el Project remoto.")

    fields = remote_state.get("project_fields")
    if isinstance(fields, dict):
        field_names = [field.get("name") for field in fields.get("fields", [])]
        lines.append(f"- Campos detectados: {', '.join(field_names)}")
    else:
        warnings.append("No fue posible leer campos del Project.")

    items = remote_state.get("project_items")
    if isinstance(items, dict):
        lines.append(f"- Elementos actuales del Project consultados: {len(items.get('items', []))}")
    else:
        warnings.append("No fue posible leer elementos del Project.")

    for name, command in remote_state.get("commands", {}).items():
        if command["returncode"] != 0:
            warnings.append(f"Consulta `{name}` falló: {command['stderr']}")

    return "\n".join(lines), warnings


def render_dry_run_report(
    manifest: dict[str, Any],
    remote_state: dict[str, Any],
    actions: list[dict[str, Any]],
    plan_hash: str,
    report_date: str,
) -> str:
    counts = count_actions(actions, include_special_issue=True)
    historical = [task for task in manifest["tasks"] if task["source_type"] == "historical"]
    future = [task for task in manifest["tasks"] if task["source_type"] == "future"]
    closed = [action for action in actions if action["task"]["close_when_applied"]]
    opened = [action for action in actions if not action["task"]["close_when_applied"]]
    special_issue = find_special_issue(remote_state)
    remote_summary, warnings = render_remote_summary(remote_state)
    milestone_plan = milestone_actions(remote_state)
    if special_issue is None:
        warnings.append("No se pudo confirmar el issue preexistente #1 en la consulta remota.")

    lines = [
        "# Dry Run de Importación a GitHub Project",
        "",
        f"**Fecha:** {report_date}",
        "",
        f"**PLAN_HASH:** `{plan_hash}`",
        "",
        "## Confirmación de modo",
        "",
        "Este reporte fue generado en modo `--dry-run`. No se realizaron escrituras remotas: no se crearon, modificaron, cerraron ni eliminaron issues, milestones, campos o elementos del Project.",
        "",
        "## Destino",
        "",
        f"- Repositorio objetivo: `{REPO}`",
        f"- GitHub Project: #{PROJECT_NUMBER} `{PROJECT_NAME}`",
        f"- Owner del Project: `{PROJECT_OWNER}`",
        f"- URL: {PROJECT_URL}",
        "",
        "## Estado remoto consultado",
        "",
        remote_summary,
        "",
        "## Resumen del manifiesto",
        "",
        f"- Total de tareas del manifiesto: {len(manifest['tasks'])}",
        f"- Tareas historical: {len(historical)}",
        f"- Tareas future: {len(future)}",
        "- Issue preexistente especial: `Camila-Aroca/Proyecto-Capstone#1`",
        "- Cantidad final esperada de elementos, sin contar milestones: 63",
        "",
        "## Conteo de acciones propuestas",
        "",
        "| Acción | Cantidad |",
        "|---|---:|",
    ]
    for key in ["CREATE", "UPDATE", "REUSE", "CONFLICT", "NEEDS_SPLIT"]:
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines.extend(
        [
            "",
            "## Issue preexistente #1",
            "",
            f"- Detectado en consulta remota: {'Sí' if special_issue else 'No'}",
            "",
            "| Issue | Acción propuesta | Título propuesto | Status | Priority | Size | Fase | Área | Milestone |",
            "|---|---|---|---|---|---|---|---|---|",
            (
                f"| #1 | UPDATE | {SPECIAL_ISSUE['title']} | {SPECIAL_ISSUE['kanban_status']} | "
                f"{SPECIAL_ISSUE['priority']} | {SPECIAL_ISSUE['size']} | {SPECIAL_ISSUE['phase']} | "
                f"{SPECIAL_ISSUE['area']} | {SPECIAL_ISSUE['milestone']} |"
            ),
            "",
            "No se debe duplicar ni cerrar este issue. La actualización propuesta conserva el historial existente y reformula su alcance para no contradecir `.gitignore` ni la política de no versionar RAW.",
            "",
            "## Tareas del reporte",
            "",
            "| Task ID | Acción | Issue existente | Estado reporte | Status | Priority | Size | Fase | Área | Milestone | Cerraría issue |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for action in actions:
        task = action["task"]
        issue = action["issue"]
        issue_label = f"#{issue['number']}" if issue else ""
        close_label = "Sí" if task["close_when_applied"] else "No"
        lines.append(
            f"| {task['task_id']} | {action['action']} | {issue_label} | {task['report_status']} | "
            f"{task['kanban_status']} | {task['priority']} | {task['size'] or 'No asignado'} | "
            f"{task['phase']} | {task['area']} | {task['milestone']} | {close_label} |"
        )

    lines.extend(
        [
            "",
            "## Issues que quedarían cerrados",
            "",
        ]
    )
    if closed:
        for action in closed:
            task = action["task"]
            lines.append(f"- {task['task_id']}: {task['title']}")
    else:
        lines.append("- Ninguno.")

    lines.extend(["", "## Issues que quedarían abiertos", ""])
    if opened:
        for action in opened:
            task = action["task"]
            lines.append(f"- {task['task_id']}: {task['title']}")
        lines.append(f"- Issue especial #1: {SPECIAL_ISSUE['title']}")
    else:
        lines.append("- Ninguno.")

    lines.extend(["", "## Advertencias y conflictos", ""])
    conflicts = [action for action in actions if action["action"] == "CONFLICT"]
    needs_split = [action for action in actions if action["action"] == "NEEDS_SPLIT"]
    milestone_conflicts = [action for action in milestone_plan if action["action"] == "CONFLICT"]
    if warnings or conflicts or needs_split or milestone_conflicts:
        for warning in warnings:
            lines.append(f"- {warning}")
        for action in conflicts:
            reason = action.get("reason") or "conflicto no especificado"
            lines.append(f"- CONFLICT en {action['task']['task_id']}: {reason}.")
        for action in needs_split:
            lines.append(f"- NEEDS_SPLIT en {action['task']['task_id']}: tamaño no apto para importación directa.")
        for action in milestone_conflicts:
            lines.append(f"- CONFLICT en milestone `{action['title']}`: {action['reason']}.")
    else:
        lines.append("- No se detectaron conflictos ni tareas NEEDS_SPLIT.")

    lines.extend(
        [
            "",
            "## Milestones contemplados",
            "",
            "| Milestone | Due date | Acción propuesta | Motivo |",
            "|---|---|---|---|",
        ]
    )
    for milestone in milestone_plan:
        lines.append(f"| {milestone['title']} | {milestone['due_on']} | {milestone['action']} | {milestone.get('reason', '')} |")

    lines.extend(
        [
            "",
            "## Confirmación final",
            "",
            "- Modo ejecutado: `--dry-run`.",
            "- Escrituras remotas realizadas: 0.",
            "- Issues remotos creados/modificados/cerrados/eliminados: 0.",
            "- Milestones remotos creados/modificados/eliminados: 0.",
            "- Elementos o campos del Project creados/modificados/eliminados: 0.",
            "- Elementos finales esperados al aplicar, sin contar milestones: 63.",
            f"- PLAN_HASH: `{plan_hash}`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_dry_run_report(report: str) -> None:
    DRY_RUN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRY_RUN_REPORT_PATH.write_text(report, encoding="utf-8")


def validate_apply_preconditions(remote_state: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    validate_remote_state(remote_state)
    conflicts = [action for action in actions if action["action"] in {"CONFLICT", "NEEDS_SPLIT"}]
    if conflicts:
        ids = ", ".join(action["task"]["task_id"] for action in conflicts)
        raise PreflightError(f"Refusing --apply because conflicts/NEEDS_SPLIT exist: {ids}")


def ensure_milestones_apply(remote_state: dict[str, Any]) -> None:
    for milestone in milestone_actions(remote_state):
        if milestone["action"] == "REUSE":
            continue
        if milestone["action"] != "CREATE":
            raise PreflightError(f"Cannot apply milestone action {milestone}")
        run_gh(
            [
                "api",
                f"repos/{REPO}/milestones",
                "--method",
                "POST",
                "-f",
                f"title={milestone['title']}",
                "-f",
                f"due_on={github_milestone_due_timestamp(milestone['due_on'])}",
            ],
            check=True,
        )


def apply_project_fields(task: dict[str, Any], issue_url: str) -> None:
    fields = {
        "Status": task["kanban_status"],
        "Priority": task["priority"],
        "Fase": task["phase"].replace(" si alcanza", ""),
        "Área": task["area"],
    }
    if task["size"]:
        fields["Size"] = task["size"]
    for field, value in fields.items():
        run_gh(
            [
                "project",
                "item-edit",
                PROJECT_NUMBER,
                "--owner",
                PROJECT_OWNER,
                "--url",
                issue_url,
                "--field",
                field,
                "--value",
                value,
            ],
            check=True,
        )


def ensure_project_membership(remote_state: dict[str, Any], issue_url: str) -> dict[str, Any]:
    existing_item = project_item_for_issue(remote_state, issue_url)
    if existing_item:
        return existing_item
    result = run_gh(
        [
            "project",
            "item-add",
            PROJECT_NUMBER,
            "--owner",
            PROJECT_OWNER,
            "--url",
            issue_url,
            "--format",
            "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already exists" in stderr.lower() or "already added" in stderr.lower():
            refreshed = collect_remote_state()
            existing_after = project_item_for_issue(refreshed, issue_url)
            if existing_after:
                return existing_after
        raise ApplyError(f"Could not add issue to Project: {stderr}")
    try:
        added = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ApplyError(f"Project item-add returned invalid JSON: {result.stdout!r}") from exc
    if not added:
        raise ApplyError("Project item-add returned no item data.")
    if not (added.get("id") or added.get("item")):
        raise ApplyError(f"Project item-add did not return a verifiable item id: {added!r}")
    return added


def special_issue_body() -> str:
    return (
        "## Objetivo\n\n"
        f"{SPECIAL_ISSUE['purpose']}\n\n"
        "## Contexto\n\n"
        "Este issue reemplaza el alcance original de agregar datasets al repositorio por una tarea compatible con `.gitignore` y la política de no versionar datos RAW.\n\n"
        "## Criterios de aceptación\n\n"
        "- [ ] Fuentes oficiales documentadas.\n"
        "- [ ] URLs y periodos disponibles registrados.\n"
        "- [ ] Procedimiento de descarga descrito.\n"
        "- [ ] Manifests y hashes definidos.\n"
        "- [ ] Política de no versionar RAW explicitada.\n"
    )


def apply_special_issue(remote_state: dict[str, Any]) -> None:
    issue = find_special_issue(remote_state)
    if not issue:
        raise PreflightError("Required existing issue #1 was not found.")
    run_gh(
        [
            "issue",
            "edit",
            str(SPECIAL_ISSUE["number"]),
            "--repo",
            REPO,
            "--title",
            SPECIAL_ISSUE["title"],
            "--body",
            special_issue_body(),
            "--milestone",
            SPECIAL_ISSUE["milestone"],
        ],
        check=True,
    )
    ensure_project_membership(remote_state, issue["url"])
    apply_project_fields(
        {
            "kanban_status": SPECIAL_ISSUE["kanban_status"],
            "priority": SPECIAL_ISSUE["priority"],
            "size": SPECIAL_ISSUE["size"],
            "phase": SPECIAL_ISSUE["phase"],
            "area": SPECIAL_ISSUE["area"],
        },
        issue["url"],
    )


def apply_import(manifest: dict[str, Any], remote_state: dict[str, Any], actions: list[dict[str, Any]]) -> int:
    validate_apply_preconditions(remote_state, actions)
    ensure_milestones_apply(remote_state)
    errors = 0
    try:
        apply_special_issue(remote_state)
    except Exception as exc:
        errors += 1
        print(f"ERROR special-issue-1: {exc}", file=sys.stderr)
        print(f"CREATE=0 UPDATE=0 REUSE=0 CLOSED=0 ERROR={errors}")
        return 1

    created = updated = reused = closed = 0
    for action in actions:
        task = action["task"]
        try:
            if action["action"] == "CREATE":
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                    handle.write(task["issue_body"])
                    body_path = handle.name
                try:
                    result = run_gh(
                        [
                            "issue",
                            "create",
                            "--repo",
                            REPO,
                            "--title",
                            task["title"],
                            "--body-file",
                            body_path,
                            "--milestone",
                            task["milestone"],
                        ],
                        check=True,
                    )
                finally:
                    Path(body_path).unlink(missing_ok=True)
                issue_url = result.stdout.strip().splitlines()[-1]
                created += 1
            else:
                issue = action["issue"]
                issue_url = issue["url"]
                if action["action"] == "UPDATE":
                    run_gh(
                        [
                            "issue",
                            "edit",
                            str(issue["number"]),
                            "--repo",
                            REPO,
                            "--title",
                            task["title"],
                            "--body",
                            task["issue_body"],
                            "--milestone",
                            task["milestone"],
                        ],
                        check=True,
                    )
                    updated += 1
                else:
                    reused += 1

            ensure_project_membership(remote_state, issue_url)
            apply_project_fields(task, issue_url)
            if task["close_when_applied"] and (action["issue"] is None or normalize_issue_state(action["issue"]) != "CLOSED"):
                run_gh(["issue", "close", issue_url, "--repo", REPO, "--reason", "completed"], check=True)
                closed += 1
        except Exception as exc:
            errors += 1
            print(f"ERROR {task['task_id']}: {exc}", file=sys.stderr)
    print(f"CREATE={created} UPDATE={updated} REUSE={reused} CLOSED={closed} ERROR={errors}")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Capstone audit tasks to GitHub Project 12.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Simulate import and write local dry-run report.")
    mode.add_argument("--apply", action="store_true", help="Apply remote changes. Never the default.")
    parser.add_argument("--confirm-target", help="Required with --apply: Camila-Aroca/Proyecto-Capstone#12")
    parser.add_argument("--confirm-plan", help="Required with --apply: PLAN_HASH from the reviewed dry run")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.apply
    manifest = build_manifest()
    write_manifest(manifest)
    remote_state = collect_remote_state()
    actions = classify_actions(manifest, remote_state)
    milestone_plan = milestone_actions(remote_state)
    plan_hash = build_plan_hash(manifest, actions, milestone_plan, remote_state)
    report_date = date.today().isoformat()

    if dry_run:
        write_dry_run_report(render_dry_run_report(manifest, remote_state, actions, plan_hash, report_date))
        counts = count_actions(actions, include_special_issue=True)
        print(f"mode=dry-run manifest_tasks={len(manifest['tasks'])}")
        print(
            "actions "
            + " ".join(f"{key}={counts.get(key, 0)}" for key in ["CREATE", "UPDATE", "REUSE", "CONFLICT", "NEEDS_SPLIT"])
        )
        milestone_counts: dict[str, int] = {"CREATE": 0, "REUSE": 0, "CONFLICT": 0}
        for milestone in milestone_plan:
            milestone_counts[milestone["action"]] = milestone_counts.get(milestone["action"], 0) + 1
        print(
            "milestones "
            + " ".join(f"{key}={milestone_counts.get(key, 0)}" for key in ["CREATE", "REUSE", "CONFLICT"])
        )
        close_count = sum(1 for action in actions if action["task"]["close_when_applied"])
        open_count = len(actions) - close_count + 1
        print(f"issue_states open={open_count} closed={close_count}")
        print(f"PLAN_HASH={plan_hash}")
        print(f"dry_run_report={DRY_RUN_REPORT_PATH.as_posix()}")
        print("remote_writes=0")
        return 0

    expected_target = f"{REPO}#{PROJECT_NUMBER}"
    if args.confirm_target != expected_target:
        raise SystemExit(f"--apply requires --confirm-target {expected_target}")
    if args.confirm_plan != plan_hash:
        raise SystemExit("--apply requires --confirm-plan matching current PLAN_HASH")
    return apply_import(manifest, remote_state, actions)


if __name__ == "__main__":
    raise SystemExit(main())
