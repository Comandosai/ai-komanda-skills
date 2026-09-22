import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('status',Path(__file__).resolve().parents[1]/'scripts/build_status.py')
status=importlib.util.module_from_spec(spec); spec.loader.exec_module(status)

class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        folder=self.root/'dela/01/a1'; folder.mkdir(parents=True)
        for name in ('result.md','check.md'): (folder/name).write_text('evidence')
        (self.root/'input.md').write_text('input')
        self.a=dict(id='a1',case_id='01',process_id='p',scope_version='s1',config_version='c1',series_id='f1',mode='final',status='completed',check_passed=True,accepted=None,touches=None,content_corrections=0,input_files=['input.md'],result_files=['dela/01/a1/result.md'],check_files=['dela/01/a1/check.md'])
    def tearDown(self): self.tmp.cleanup()
    def summary(self,items=None): return status.summarize(self.root,dict(schema_version=1,attempts=items or [self.a]))
    def test_complete_not_accepted_unknown_not_zero(self):
        s=self.summary()[0]; self.assertEqual((s['complete'],s['accepted'],s['no_hands'],s['unknown_touches']),(1,0,0,1))
    def test_acceptance_and_touches_independent(self):
        self.a.update(accepted=True,touches=1); s=self.summary()[0]
        self.assertEqual((s['accepted'],s['no_hands']),(1,0))
    def test_missing_check_rejects(self):
        (self.root/self.a['check_files'][0]).unlink(); self.assertEqual(self.summary()[0]['complete'],0)
    def test_same_result_check_rejected(self):
        self.a['check_files']=self.a['result_files']; self.assertEqual(self.summary()[0]['complete'],0)
    def test_duplicate_id_rejected(self):
        self.assertEqual(self.summary([self.a,copy.deepcopy(self.a)])[0]['complete'],0)
    def test_escape_and_symlink(self):
        self.assertFalse(status.checked_file(self.root,'../anything'))
        (self.root/'link').symlink_to('/etc/hosts'); self.assertFalse(status.checked_file(self.root,'link'))
    def test_version_groups_separate(self):
        other=copy.deepcopy(self.a); other.update(id='a2',config_version='c2')
        self.assertEqual(len(self.summary([self.a,other])),2)
    def test_waiting_not_complete(self):
        self.a.update(status='waiting',reason='Согласование'); s=self.summary()[0]
        self.assertEqual(s['complete'],0); self.assertIn('Согласование',s['attempts'][0]['problems'])
    def test_html_escape(self):
        self.a.update(reason='<script>alert(1)</script>',status='failed')
        result=status.render(self.summary()); self.assertNotIn('<script>',result); self.assertIn('&lt;script&gt;',result)
    def test_no_inputs_rejects(self):
        self.a['input_files']=[]; self.assertEqual(self.summary()[0]['complete'],0)

if __name__=='__main__': unittest.main()
