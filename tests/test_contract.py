import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class Contract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree("harness",self.root/"harness",ignore=shutil.ignore_patterns("project.json"))
        shutil.copy(".gitignore",self.root)
        for cmd in [["git","init","-q"],["git","add","."],["git","-c","user.name=test","-c","user.email=test@example.invalid","commit","-qm","fixture"]]:
            subprocess.run(cmd,cwd=self.root,check=True)

    def invoke(self,*args):
        return subprocess.run(args,cwd=self.root,capture_output=True,text=True)

    def check(self, checks, expected):
        (self.root/"harness/project.json").write_text(json.dumps(dict(version=1,checks=checks)))
        result = self.invoke("harness/verify.sh","--target","project")
        self.assertEqual(result.returncode,expected,result)
        return result

    def command(self, script):
        return dict(id="test",argv=[sys.executable,"-c",script],required=True)

    def test_bootstrap(self):
        self.invoke("harness/bootstrap.sh","--dry-run")
        self.assertFalse((self.root/"harness/project.json").exists())
        self.invoke("harness/bootstrap.sh")
        self.assertEqual(self.invoke("harness/verify.sh","--target","project").returncode,3)

    def test_evidence(self):
        result = self.check([self.command("pass")],0)
        args = ["harness/evaluate.sh","--results",result.stdout.splitlines()[0],"--target"]
        self.assertEqual(self.invoke(*args,"project").returncode,0)
        self.assertEqual(self.invoke(*args,"template").returncode,2)
        (self.root/"new").touch()
        self.assertEqual(self.invoke(*args,"project").returncode,2)

    def test_failures(self):
        c = self.command("raise SystemExit(1)")
        self.check([c,dict(c,id="dependent",depends=["test"]),dict(self.command("pass"),id="independent")],1)
        self.check([dict(c,argv=["missing-fixture-tool"])],2)
        self.check([dict(c,depends=["test"])],2)
        self.check([c,c],2)
        self.check([dict(self.command("import time; time.sleep(10)"),timeout=1)],2)

    def test_mutation(self):
        self.check([self.command("open('new','w').close()")],2)

    def test_secret(self):
        marker = "gh" + "p_" + "x"*40
        (self.root/"fixture").write_text(marker)
        result = self.invoke(sys.executable,"harness/scan.py")
        self.assertEqual(result.returncode,1)
        self.assertNotIn(marker,result.stdout + result.stderr)
