"""Validate the mapped demo module without running plan or apply."""

import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from app.config import ROOT
from app.execution.contracts import WorkflowError


class Terraform:
    def prepare(self, snapshot, binding, current, target):
        files = snapshot["files"]
        # The initial integration supports our audited AWS EC2 demo template.
        # Refuse arbitrary executable providers/modules received from a repository.
        template = (ROOT / "infra/demo-terraform/main.tf").read_text(encoding="utf-8")
        if files["main.tf"].replace("\r\n", "\n") != template.replace("\r\n", "\n"):
            raise WorkflowError("Terraform module differs from the supported demo template; review its integration first")
        path = binding["variables_file"]
        before = files[path]
        variables = json.loads(before)
        if variables.get(binding["variable"]) != current:
            raise WorkflowError("Terraform variable and current instance type differ; reconcile drift first")
        allowed = snapshot["mapping"].get("candidate_instance_types", [])
        if target not in allowed:
            raise WorkflowError("Target is not an explicitly mapped Terraform candidate")
        variables[binding["variable"]] = target
        after = json.dumps(variables, indent=2) + "\n"
        executable = shutil.which("terraform")
        plugins = ROOT / "infra/demo-terraform/.terraform/providers"
        if not executable or not plugins.exists():
            raise WorkflowError("Install Terraform and initialize infra/demo-terraform first", 503)
        directory = ROOT / "data/local/validation"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            work = Path(temporary)
            for name, content in files.items():
                destination = work / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                # The audited template pins the provider version. Its locally verified
                # lock includes this platform's hash; a remote macOS-only h1 cannot
                # verify the unpacked Linux provider mirror. This file is temporary.
                if name == ".terraform.lock.hcl":
                    content = (ROOT / "infra/demo-terraform/.terraform.lock.hcl").read_text(encoding="utf-8")
                destination.write_text(after if name == path else content, encoding="utf-8")
            config = work / "terraform.rc"
            config.write_text("disable_checkpoint = true\n", encoding="utf-8")
            env = {key: value for key, value in os.environ.items() if key.upper() in {
                "PATH", "SYSTEMROOT", "COMSPEC", "USERPROFILE", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA",
            }}
            env.update({"TF_IN_AUTOMATION": "1", "TF_CLI_CONFIG_FILE": str(config)})
            for arguments in (
                ["init", "-backend=false", "-get=false", "-input=false", "-lockfile=readonly",
                 "-plugin-dir=" + str(plugins), "-no-color"],
                ["fmt", "-check", "-no-color"],
                ["validate", "-json"],
            ):
                result = subprocess.run([executable, *arguments], cwd=work, env=env,
                                        capture_output=True, timeout=120, text=True)
                if result.returncode != 0:
                    raise WorkflowError(f"Terraform {arguments[0]} failed; candidate cannot be approved", 422)
        return {"file": path, "before": before, "after": after,
                "diff": "".join(difflib.unified_diff(before.splitlines(keepends=True),
                    after.splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path)),
                "validation": {"fmt": "passed", "validate": "passed", "plan": "not_run"}}
