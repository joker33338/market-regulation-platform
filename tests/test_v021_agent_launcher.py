"""在临时工作区执行真实启动脚本；Git 与交互入口均为隔离替身。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/start_agent_workspace.ps1"


@unittest.skipUnless(shutil.which("pwsh"), "需要既有 PowerShell 7；不安装新依赖")
class AgentLauncherTests(unittest.TestCase):
    def launch(self, branch, role):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scripts = root / "scripts"
            scripts.mkdir()
            target = scripts / SCRIPT.name
            target.write_bytes(SCRIPT.read_bytes())
            common = root / "common"
            common.mkdir()
            (common / "agent-local.json").write_text(json.dumps({
                "corpus": str(root / "synthetic-corpus"), "originalRoot": str(root / "synthetic-original")
            }), encoding="utf-8")
            env = {**os.environ, "QFA_TEST_BRANCH": branch, "QFA_TEST_ROLE": role,
                   "QFA_TEST_COMMON": str(common), "QFA_TEST_SCRIPT": str(target)}
            command = '''
function global:git {
    if ($args[0] -eq 'branch') { return $env:QFA_TEST_BRANCH }
    if ($args[0] -eq 'rev-parse') { return $env:QFA_TEST_COMMON }
    throw 'Unexpected Git operation in isolated launcher test'
}
function global:codex { Write-Output 'ISOLATED_SESSION_STUB' }
& $env:QFA_TEST_SCRIPT -Role $env:QFA_TEST_ROLE
'''
            return subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                                  env=env, cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=20)

    def test_current_and_round01_role_branches_are_accepted(self):
        for role, branch in (("QA", "codex/qa-v0.2.1"), ("Fix", "codex/fix-v0.2.1"),
                             ("QA", "qa/round1"), ("Fix", "fix/round1")):
            with self.subTest(role=role, branch=branch):
                result = self.launch(branch, role)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Workspace ready", result.stdout)
                self.assertIn("ISOLATED_SESSION_STUB", result.stdout)

    def test_other_role_is_rejected_before_session(self):
        for role, branch in (("Fix", "codex/qa-v0.2.1"), ("QA", "codex/fix-v0.2.1"),
                             ("Fix", "qa/round1"), ("QA", "fix/round1")):
            with self.subTest(role=role, branch=branch):
                result = self.launch(branch, role)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Expected branch", result.stderr)
                self.assertNotIn("ISOLATED_SESSION_STUB", result.stdout)

    def test_unknown_branch_is_rejected_before_session(self):
        for role in ("QA", "Fix"):
            with self.subTest(role=role):
                result = self.launch("codex/unknown-v0.2.1", role)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Expected branch", result.stderr)
                self.assertNotIn("ISOLATED_SESSION_STUB", result.stdout)
