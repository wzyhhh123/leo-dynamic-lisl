"""Exact planning-only parent chain; never a runtime/scientific exception."""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
import check_f3_v2_engineering as checker


class PlanningChainTests(unittest.TestCase):
    def test_progress_cli_direct_file_execution_in_current_environment(self):
        command=[sys.executable,'tools/save_f3_v2_engineering_progress.py','--help']
        process=subprocess.run(command,cwd=checker.ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn('--acceptance-report',process.stdout)

    def fixture(self,root):
        rel='docs/F3_V2_OCTOBER_CRITICAL_PATH.md'
        old=b'original';middle=b'review2';new=b'review3'
        registry=[]
        for i,(before,after) in enumerate(((old,middle),(middle,new))):
            base=root/('evidence'+str(i));(base/'prior_plan_bytes').mkdir(parents=True)
            saved=base/'prior_plan_bytes'/Path(rel).name;saved.write_bytes(before)
            target=root/('after'+str(i));target.write_bytes(after)
            report=base/'planning_revision_report.json';report.write_text(json.dumps({'status':'PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW'}))
            seal=base/'artifact_hashes.json';seal.write_text(json.dumps({'before':{rel:checker.sha(saved)},'after':{rel:checker.sha(target)}}))
            registry.append((base.name,checker.sha(report),checker.sha(seal)))
        old_path=root/'old';old_path.write_bytes(old)
        return rel,checker.sha(old_path),checker.sha(root/'after1'),tuple(registry)

    def test_actual_two_explicit_revisions(self):
        rel='docs/F3_V2_OCTOBER_CRITICAL_PATH.md'
        first=json.loads((checker.ROOT/checker.PLANNING_REVISIONS[0][0]/'artifact_hashes.json').read_text())
        second=json.loads((checker.ROOT/checker.PLANNING_REVISIONS[1][0]/'artifact_hashes.json').read_text())
        self.assertTrue(checker.authorized_planning_revision(checker.ROOT,rel,first['before'][rel],second['after'][rel]))

    def test_chain_parent_tamper_missing_and_unregistered_fail_closed(self):
        for mutation in ('none','parent','report','seal','saved','missing','unregistered','science_path'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);rel,old,new,registry=self.fixture(root)
                if mutation=='parent':old='0'*64
                if mutation=='report':(root/'evidence1/planning_revision_report.json').write_text('{}')
                if mutation=='seal':(root/'evidence1/artifact_hashes.json').write_text('{}')
                if mutation=='saved':(root/'evidence1/prior_plan_bytes'/Path(rel).name).write_text('changed')
                if mutation=='missing':(root/'evidence1/artifact_hashes.json').unlink()
                if mutation=='unregistered':new='1'*64
                if mutation=='science_path':rel='src/dynamic_lisl/terminal_executor.py'
                with patch.object(checker,'PLANNING_REVISIONS',registry):
                    self.assertEqual(checker.authorized_planning_revision(root,rel,old,new),mutation=='none')

    def test_cannot_skip_middle_parent_with_resealed_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rel,old,new,registry=self.fixture(root)
            p=root/'evidence1/artifact_hashes.json';d=json.loads(p.read_text());d['before'][rel]=old;p.write_text(json.dumps(d))
            rows=list(registry);rows[1]=(rows[1][0],rows[1][1],checker.sha(p))
            with patch.object(checker,'PLANNING_REVISIONS',tuple(rows)):
                self.assertFalse(checker.authorized_planning_revision(root,rel,old,new))


if __name__=='__main__':unittest.main()
