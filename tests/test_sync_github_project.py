import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scripts.sync_github_project as sync


def command_result(args, stdout="", stderr="", returncode=0):
    return sync.CommandResult(args=args, stdout=stdout, stderr=stderr, returncode=returncode)


def sample_fields(missing_status_option=False):
    fields = []
    for name, options in sync.EXPECTED_FIELD_OPTIONS.items():
        option_names = sorted(options)
        if missing_status_option and name == "Status":
            option_names.remove("Done")
        fields.append({"name": name, "options": [{"name": option} for option in option_names]})
    return {"fields": fields, "totalCount": len(fields)}


def sample_issue(number=1, title="Agregar datasets utilizados al repositorio", body="", state="OPEN", url=None, milestone=None):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "url": url or f"https://github.com/Camila-Aroca/Proyecto-Capstone/issues/{number}",
        "milestone": {"title": milestone} if milestone else None,
    }


def sample_remote_state(issues=None, fields=None, items=None, milestones=None):
    if issues is None:
        issues = [sample_issue()]
    if fields is None:
        fields = sample_fields()
    if items is None:
        items = {
            "items": [
                {
                    "content": {"url": "https://github.com/Camila-Aroca/Proyecto-Capstone/issues/1"},
                    "status": "Backlog",
                    "priority": "P1",
                    "size": "M",
                    "fase": "Fase 2.1",
                    "area": "Datos",
                }
            ]
        }
    if milestones is None:
        milestones = [
            {"title": milestone["title"], "due_on": f"{milestone['due_on']}T00:00:00Z"}
            for milestone in sync.MILESTONES.values()
        ]
    return {
        "commands": {
            key: {"returncode": 0, "stderr": ""}
            for key in ["auth_status", "viewer", "repo", "issues", "project", "project_fields", "project_items", "milestones"]
        },
        "auth_status": "Logged in",
        "viewer": {"login": "Camila-Aroca"},
        "repo": {"full_name": "Camila-Aroca/Proyecto-Capstone", "visibility": "public"},
        "issues": issues,
        "project": {
            "number": 12,
            "title": "Tablero Kanban Capstone",
            "owner": {"login": "Camila-Aroca"},
            "url": "https://github.com/users/Camila-Aroca/projects/12",
        },
        "project_fields": fields,
        "project_items": items,
        "milestones": milestones,
    }


class SyncGithubProjectTests(unittest.TestCase):
    def test_dry_run_does_not_execute_remote_writes(self):
        payloads = {
            ("auth", "status"): command_result(["auth", "status"], stdout="Logged in"),
            ("api", "user"): command_result(["api", "user"], stdout=json.dumps({"login": "Camila-Aroca"})),
            ("api", f"repos/{sync.REPO}"): command_result(["api", f"repos/{sync.REPO}"], stdout=json.dumps({"full_name": sync.REPO, "visibility": "public"})),
            ("issue", "list"): command_result(["issue", "list"], stdout=json.dumps([sample_issue()])),
            ("project", "view"): command_result(["project", "view"], stdout=json.dumps(sample_remote_state()["project"])),
            ("project", "field-list"): command_result(["project", "field-list"], stdout=json.dumps(sample_fields())),
            ("project", "item-list"): command_result(["project", "item-list"], stdout=json.dumps({"items": []})),
            ("api", f"repos/{sync.REPO}/milestones?state=all"): command_result(
                ["api", f"repos/{sync.REPO}/milestones?state=all"],
                stdout=json.dumps(sample_remote_state()["milestones"]),
            ),
        }

        def fake_run_gh(args, check=False):
            key = tuple(args[:2])
            return payloads[key]

        with patch.object(sync, "run_gh", side_effect=fake_run_gh) as run_mock:
            with patch.object(sys, "argv", ["sync_github_project.py", "--dry-run"]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(sync.main(), 0)

        forbidden = [
            ("issue", "create"),
            ("issue", "edit"),
            ("issue", "close"),
            ("project", "item-add"),
            ("project", "item-edit"),
        ]
        called_prefixes = [tuple(call.args[0][:2]) for call in run_mock.call_args_list]
        for prefix in forbidden:
            self.assertNotIn(prefix, called_prefixes)

    def test_preflight_fails_if_issues_unavailable(self):
        state = sample_remote_state()
        state["issues"] = None
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_issue_1_missing(self):
        state = sample_remote_state(issues=[sample_issue(number=2)])
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_field_option_missing(self):
        state = sample_remote_state(fields=sample_fields(missing_status_option=True))
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_project_items_missing(self):
        state = sample_remote_state()
        state["project_items"] = None
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_project_items_type_invalid(self):
        state = sample_remote_state()
        state["project_items"] = []
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_items_type_invalid(self):
        state = sample_remote_state(items={"items": {}})
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_preflight_fails_if_special_issue_closed(self):
        state = sample_remote_state(issues=[sample_issue(state="CLOSED")])
        with self.assertRaises(sync.PreflightError):
            sync.validate_remote_state(state)

    def test_duplicate_marker_produces_conflict(self):
        manifest = sync.build_manifest()
        task = manifest["tasks"][0]
        issue_a = sample_issue(number=10, body=f"<!-- capstone-task-id: {task['task_id']} -->")
        issue_b = sample_issue(number=11, body=f"<!-- capstone-task-id: {task['task_id']} -->")
        state = sample_remote_state(issues=[sample_issue(), issue_a, issue_b])
        actions = sync.classify_actions({"tasks": [task]}, state)
        self.assertEqual(actions[0]["action"], "CONFLICT")

    def test_closed_issue_expected_open_produces_conflict(self):
        manifest = sync.build_manifest()
        task = next(task for task in manifest["tasks"] if task["task_id"] == "NEXT-001")
        issue = sample_issue(number=10, title=task["title"], body=task["issue_body"], state="CLOSED", milestone=task["milestone"])
        state = sample_remote_state(issues=[sample_issue(), issue])
        actions = sync.classify_actions({"tasks": [task]}, state)
        self.assertEqual(actions[0]["action"], "CONFLICT")
        self.assertEqual(actions[0]["reason"], "issue_closed_but_expected_open")

    def test_already_closed_expected_closed_does_not_close_again(self):
        manifest = sync.build_manifest()
        task = next(task for task in manifest["tasks"] if task["task_id"] == "DONE-001")
        issue = sample_issue(number=10, title=task["title"], body=task["issue_body"], state="CLOSED", milestone=task["milestone"])
        state = sample_remote_state(issues=[sample_issue(), issue])
        actions = [{"task": task, "action": "REUSE", "issue": issue, "matches": [issue], "reason": ""}]

        with patch.object(sync, "ensure_milestones_apply"), patch.object(sync, "apply_special_issue"):
            with patch.object(sync, "ensure_project_membership"), patch.object(sync, "apply_project_fields"):
                with patch.object(sync, "run_gh", return_value=command_result(["noop"])) as run_mock:
                    sync.apply_import({"tasks": [task]}, state, actions)

        close_calls = [call for call in run_mock.call_args_list if call.args[0][:2] == ["issue", "close"]]
        self.assertEqual(close_calls, [])

    def test_plan_hash_is_stable_and_changes_with_remote_state(self):
        manifest = sync.build_manifest()
        state = sample_remote_state()
        actions = sync.classify_actions(manifest, state)
        milestones = sync.milestone_actions(state)
        first = sync.build_plan_hash(manifest, actions, milestones, state)
        second = sync.build_plan_hash(manifest, actions, milestones, state)
        self.assertEqual(first, second)

        changed_state = sample_remote_state(issues=[sample_issue(title="Título cambiado")])
        changed_actions = sync.classify_actions(manifest, changed_state)
        changed_hash = sync.build_plan_hash(manifest, changed_actions, sync.milestone_actions(changed_state), changed_state)
        self.assertNotEqual(first, changed_hash)

    def test_plan_hash_changes_when_special_issue_desired_body_changes(self):
        manifest = sync.build_manifest()
        state = sample_remote_state()
        actions = sync.classify_actions(manifest, state)
        milestones = sync.milestone_actions(state)
        original = sync.build_plan_hash(manifest, actions, milestones, state)

        with patch.object(sync, "special_issue_body", return_value=sync.special_issue_body() + "\n- [ ] Línea nueva.\n"):
            changed = sync.build_plan_hash(manifest, actions, milestones, state)

        self.assertNotEqual(original, changed)

    def test_special_issue_gets_all_project_fields_in_apply(self):
        state = sample_remote_state()
        special = sample_issue()
        state["issues"] = [special]

        with patch.object(sync, "run_gh", return_value=command_result(["ok"])):
            with patch.object(sync, "ensure_project_membership") as membership_mock:
                with patch.object(sync, "apply_project_fields") as fields_mock:
                    sync.apply_special_issue(state)

        membership_mock.assert_called_once_with(state, special["url"])
        fields_arg = fields_mock.call_args.args[0]
        self.assertEqual(fields_arg["kanban_status"], "Backlog")
        self.assertEqual(fields_arg["priority"], "P1")
        self.assertEqual(fields_arg["size"], "M")
        self.assertEqual(fields_arg["phase"], "Fase 2.1")
        self.assertEqual(fields_arg["area"], "Datos")

    def test_apply_stops_if_special_issue_update_fails(self):
        manifest = sync.build_manifest()
        state = sample_remote_state()
        actions = sync.classify_actions(manifest, state)

        with patch.object(sync, "ensure_milestones_apply"):
            with patch.object(sync, "apply_special_issue", side_effect=sync.ApplyError("boom")):
                with patch.object(sync, "run_gh", return_value=command_result(["noop"])) as run_mock:
                    with redirect_stdout(io.StringIO()):
                        result = sync.apply_import(manifest, state, actions)

        self.assertEqual(result, 1)
        create_calls = [call for call in run_mock.call_args_list if call.args[0][:2] == ["issue", "create"]]
        self.assertEqual(create_calls, [])


if __name__ == "__main__":
    unittest.main()
