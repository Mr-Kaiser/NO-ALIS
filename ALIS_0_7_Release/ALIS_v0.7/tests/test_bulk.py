import csv
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from alis import bulk
from alis.web import create_app
from alis.writer import ChangedOnDisk, WriteError, commit, plan_edit, revision
import test_writer


class BulkTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root=fixture.root;self.paths={1:fixture.path};self.original={1:fixture.raw}
        with (self.root/'hardpointdictionary_stations.csv').open('a',newline='') as f:
            csv.writer(f).writerow(['CAS1',2,'Wing Pylons','Wing',2,'','vanilla'])
        folder=self.root/'CAS1/weaponstation2';folder.mkdir()
        self.paths[2]=folder/'Wing Pylons.json'
        self.original[2]=b'{"allowedWeapons":["B"],"extra":{"keep":42}}\n'
        self.paths[2].write_bytes(self.original[2])

    def body(self,targets=(1,2),**kwargs):
        rows=bulk.catalog(self.root,'CAS1')
        return dict(dictionary_revision=rows['dictionary_revision'],
                    source={'index':1,'revision':revision(self.paths[1].read_bytes())},
                    targets=[{'index':i,'revision':revision(self.paths[i].read_bytes())} for i in targets],
                    add=['C'],remove=[],**kwargs) if not kwargs else self._body(rows,targets,kwargs)

    def _body(self,rows,targets,kwargs):
        return {**dict(dictionary_revision=rows['dictionary_revision'],
                    source={'index':1,'revision':revision(self.paths[1].read_bytes())},
                    targets=[{'index':i,'revision':revision(self.paths[i].read_bytes())} for i in targets],
                    add=['C'],remove=[]),**kwargs}

    def plan(self,targets=(1,2),**kwargs):return bulk.plan_batch(self.root,'CAS1',self.body(targets,**kwargs))
    def assert_originals(self):
        for i,path in self.paths.items():self.assertEqual(path.read_bytes(),self.original[i])
    def status(self):return bulk.recovery_status(self.root)
    def restore(self,status=None):
        status=status or self.status()
        return bulk.recover_batch(self.root,status['revision'],{str(s['index']):s['current_revision'] for s in status['stations']})

    def fail_second(self,plan=None,rollback_fails=False,external=False):
        plan=plan or self.plan();real=os.replace;first=0
        def failing(src,dst):
            nonlocal first
            dst=Path(dst)
            if dst==self.paths[2]:
                if external:self.paths[1].write_bytes(b'{"allowedWeapons":["A"],"external":true}')
                raise PermissionError('second target locked')
            if dst==self.paths[1]:
                first+=1
                if rollback_fails and first>1:raise PermissionError('rollback locked')
            return real(src,dst)
        with patch('alis.bulk.os.replace',side_effect=failing):
            with self.assertRaises(bulk.BatchFailed) as caught:bulk.commit_batch(plan)
        return caught.exception

    def test_review_lists_every_station_without_writes(self):
        plan=self.plan(remove=['A'])
        self.assertEqual(plan.summary['changed_count'],2)
        self.assertEqual([r['index'] for r in plan.summary['stations']],[1,2])
        self.assertEqual(plan.plans[0].after,('B','C'));self.assertEqual(plan.plans[1].after,('B','C'))
        self.assert_originals();self.assertFalse(list(self.root.rglob('*.bak')))

    def test_commit_has_exact_backups_and_preserves_extras_encoding(self):
        result=bulk.commit_batch(self.plan(remove=['A']))
        self.assertEqual(result['changed_count'],2);self.assertTrue(result['verified'])
        for i,backup in zip((1,2),result['backups']):
            self.assertEqual((self.root/backup).read_bytes(),self.original[i])
            before=json.loads(self.original[i].decode('utf-8-sig'));before['allowedWeapons']=['B','C']
            self.assertEqual(json.loads(self.paths[i].read_text('utf-8-sig')),before)
        self.assertTrue(self.paths[1].read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertIsNone(self.status());self.assertFalse((self.root/'.alis-write.lock').exists())

    def test_noops_make_no_backups(self):
        result=bulk.commit_batch(self.plan(add=['B']))
        self.assertEqual(result['changed_count'],0);self.assertFalse(result['backups']);self.assert_originals()
        self.assertFalse(list(self.root.rglob('*.bak')))

    def test_aliases_and_stale_keys_resolve_on_all_targets(self):
        plan=self.plan(add=['asset_C','STALE8'])
        for station in plan.plans:self.assertEqual(station.after[-2:],('C','REAL6'))
        bulk.commit_batch(plan)

    def test_unknown_source_removal_missing_on_target_is_noop(self):
        self.paths[1].write_text('{"allowedWeapons":["unresolved","A"]}')
        plan=self.plan(add=[],remove=['unresolved'])
        self.assertEqual(plan.plans[0].after,('A',));self.assertFalse(plan.plans[1].changed)

    def test_unknown_add_and_removal_rejected_before_writes(self):
        for kwargs in ({'add':['unknown']},{'remove':['unknown']}):
            with self.subTest(kwargs=kwargs),self.assertRaises(WriteError):self.plan(**kwargs)
        self.assert_originals()

    def test_empty_consent_applies_to_every_target(self):
        with self.assertRaises(WriteError):self.plan(add=[],remove=['A','B'])
        plan=self.plan(add=[],remove=['A','B'],allow_empty=True)
        self.assertTrue(all(not p.after for p in plan.plans));bulk.commit_batch(plan)

    def test_bad_selection_and_payload_rejected(self):
        for change in ({'targets':[]},{'targets':[{'index':1,'revision':revision(self.original[1])}]*2},
                       {'source':{'index':True,'revision':'x'}},{'allow_empty':'yes'},
                       {'add':[],'remove':[]},{'add':'C'},{'remove':[4]}):
            with self.subTest(change=change),self.assertRaises(WriteError):bulk.plan_batch(self.root,'CAS1',{**self.body(),**change})
        self.assert_originals()

    def test_target_changed_after_review_refuses_all_writes(self):
        plan=self.plan();self.paths[2].write_text('{"allowedWeapons":["A"]}')
        with self.assertRaises(ChangedOnDisk):bulk.commit_batch(plan)
        self.assertEqual(self.paths[1].read_bytes(),self.original[1]);self.assertFalse(list(self.root.rglob('*.bak')))

    def test_source_changed_when_source_excluded_refuses_batch(self):
        plan=self.plan(targets=(2,));self.paths[1].write_text('{"allowedWeapons":["A"]}')
        with self.assertRaises(ChangedOnDisk):bulk.commit_batch(plan)
        self.assertEqual(self.paths[2].read_bytes(),self.original[2])

    def test_dictionary_changed_after_review_refuses_all_writes(self):
        plan=self.plan();p=self.root/bulk.DICTIONARIES[0];p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises(ChangedOnDisk):bulk.commit_batch(plan)
        self.assert_originals();self.assertFalse(list(self.root.rglob('*.bak')))

    def test_failure_after_first_write_rolls_back_exactly(self):
        failure=self.fail_second();self.assertFalse(failure.recovery_required)
        self.assert_originals();self.assertIsNone(self.status());self.assertEqual(len(failure.backups),2)
        self.assertFalse(list(self.root.rglob('.alis-bulk-*.tmp')))

    def test_failed_rollback_retains_journal_and_blocks_station_writes(self):
        failure=self.fail_second(rollback_fails=True);self.assertTrue(failure.recovery_required)
        status=self.status();self.assertTrue(status['can_restore'])
        self.assertEqual([r['status'] for r in status['stations']],['changed','original'])
        with self.assertRaises(WriteError):commit(plan_edit(self.root,'CAS1',2,add=['A']))
        self.assertTrue(self.restore()['restored']);self.assert_originals();self.assertIsNone(self.status())

    def test_outside_edit_is_retained_and_automatic_recovery_refused(self):
        failure=self.fail_second(external=True);self.assertTrue(failure.recovery_required)
        external=self.paths[1].read_bytes();self.assertFalse(self.status()['can_restore'])
        with self.assertRaises(ChangedOnDisk):self.restore()
        self.assertEqual(self.paths[1].read_bytes(),external)
        self.assertEqual(self.paths[2].read_bytes(),self.original[2])

    def test_recovery_requires_current_record_and_target_revisions(self):
        self.fail_second(rollback_fails=True);status=self.status()
        with self.assertRaises(ChangedOnDisk):bulk.recover_batch(self.root,'stale',{})
        with self.assertRaises(ChangedOnDisk):bulk.recover_batch(self.root,status['revision'],{})
        self.restore(status);self.assert_originals()

    def test_corrupted_backup_and_forged_record_are_refused(self):
        self.fail_second(rollback_fails=True);status=self.status()
        journal=self.root/bulk.JOURNAL;original=journal.read_bytes();data=json.loads(original)
        data['entries'][0]['path']='../outside.json';journal.write_text(json.dumps(data))
        with self.assertRaises(WriteError):self.status()
        journal.write_bytes(original);backup=self.root/status['stations'][0]['backup'];backup.write_text('{"allowedWeapons":["B"]}')
        with self.assertRaises(WriteError):self.status()

    def test_forged_plan_cannot_change_other_fields_or_paths(self):
        plan=self.plan();p=plan.plans[0];obj=json.loads(p.replacement.decode('utf-8-sig'));obj['extra']='forged'
        for forged in (replace(p,replacement=json.dumps(obj).encode()),replace(p,path=self.paths[2])):
            with self.assertRaises(WriteError):bulk.commit_batch(replace(plan,plans=(forged,plan.plans[1])))
        self.assert_originals()

    def test_journal_symlink_is_rejected(self):
        outside=self.root/'outside';outside.write_text('retain')
        (self.root/bulk.JOURNAL).symlink_to(outside)
        with self.assertRaises(WriteError):self.status()
        with self.assertRaises(WriteError):bulk.commit_batch(self.plan())
        self.assertEqual(outside.read_text(),'retain');self.assert_originals()

    def client(self):
        app=create_app(self.root);return app,app.test_client(),{'X-ALIS-Token':app.config['ALIS_TOKEN']}

    def test_api_review_commit_single_use_and_expiry(self):
        app,c,h=self.client();url='/api/platforms/CAS1/bulk-preview'
        reviewed=c.post(url,json=self.body(),headers=h);self.assertEqual(reviewed.status_code,200)
        ticket=reviewed.get_json()['ticket'];self.assert_originals()
        saved=c.post('/api/bulk-commit',json={'ticket':ticket},headers=h)
        self.assertEqual(saved.status_code,200);self.assertEqual(len(saved.get_json()['stations']),2)
        self.assertEqual(c.post('/api/bulk-commit',json={'ticket':ticket},headers=h).status_code,410)
        ticket=c.post(url,json=self.body(add=['A']),headers=h).get_json()['ticket']
        stamp,plan=app.extensions['alis_bulk_plans'][ticket];app.extensions['alis_bulk_plans'][ticket]=(stamp-601,plan)
        self.assertEqual(c.post('/api/bulk-commit',json={'ticket':ticket},headers=h).status_code,410)

    def test_api_requires_token_and_local_origin(self):
        _,c,h=self.client();url='/api/platforms/CAS1/bulk-preview'
        self.assertEqual(c.post(url,json=self.body()).status_code,403)
        self.assertEqual(c.post(url,json=self.body(),headers={**h,'Origin':'https://outside.example'}).status_code,403)
        self.assertEqual(c.post('/api/bulk-recovery',json={}).status_code,403);self.assert_originals()

    def test_restart_exposes_and_recovers_incomplete_batch(self):
        self.fail_second(rollback_fails=True);_,c,h=self.client()
        self.assertTrue(c.get('/api/bootstrap').get_json()['bulk_recovery']['can_restore'])
        status=c.get('/api/bulk-recovery').get_json()['recovery']
        result=c.post('/api/bulk-recovery',headers=h,json={'revision':status['revision'],
          'stations':{str(s['index']):s['current_revision'] for s in status['stations']}})
        self.assertEqual(result.status_code,200);self.assert_originals()

    def test_abrupt_process_exit_retains_record_and_exact_backups(self):
        code='''
import json, os, sys
from pathlib import Path
from alis import bulk
root=Path(sys.argv[1]);body=json.loads(sys.argv[2]);plan=bulk.plan_batch(root,'CAS1',body)
real=os.replace
def interrupted(src,dst):
    if Path(dst).parent.name=='weaponstation2':os._exit(77)
    return real(src,dst)
bulk.os.replace=interrupted
bulk.commit_batch(plan)
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.root),json.dumps(self.body())],capture_output=True)
        self.assertEqual(result.returncode,77,result.stderr.decode())
        status=self.status();self.assertEqual([r['status'] for r in status['stations']],['changed','original'])
        self.assertTrue((self.root/'.alis-write.lock').exists())
        with self.assertRaises(WriteError):self.restore(status)
        # Operational recovery: remove an abandoned lock only after its process
        # is confirmed stopped, as documented for Windows and POSIX alike.
        (self.root/'.alis-write.lock').unlink()
        self.assertTrue(self.restore(status)['restored']);self.assert_originals()
        for i,row in zip((1,2),status['stations']):self.assertEqual((self.root/row['backup']).read_bytes(),self.original[i])


if __name__=='__main__':unittest.main()
