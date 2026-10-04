import copy
import csv
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import test_writer
from alis import presets
from alis.web import create_app
from alis.writer import ChangedOnDisk, WriteError, revision


class PresetTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root=fixture.root
        rows=[['aircraft','index','name','symmetryName','hardpointCount','precluding','owner'],
              ['CAS1',0,'Nose','',2,'','vanilla'],['CAS1',1,'Center Pylon','',1,'2','vanilla'],
              ['CAS1',2,'Other','',1,'1','vanilla']]
        with (self.root/'hardpointdictionary_stations.csv').open('w',newline='') as f:csv.writer(f).writerows(rows)
        for index,name in [(0,'Nose'),(2,'Other')]:
            folder=self.root/'CAS1'/f'weaponstation{index}';folder.mkdir()
            (folder/f'{name}.json').write_text('{"allowedWeapons":["A","B","REAL6"]}')
        self.data={'Fuel':.3,'Livery':'original-livery','Vanilla':1,'Stations':['Nose=A','Center Pylon=B','Other='],
                   'Hardpoints':['A','B',''],'Extra':{'untouched':[True,'café',42]}}
        self.raw=b'\xef\xbb\xbf'+(json.dumps(self.data,ensure_ascii=False,indent=2).replace('\n','\r\n')+'\r\n').encode()
        self.path=self.root/'CAS1'/'DEFAULT.preset';self.path.write_bytes(self.raw)
        self.original={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.app=create_app(self.root);self.client=self.app.test_client();self.headers={'X-ALIS-Token':self.app.config['ALIS_TOKEN']}
        self.catalog=presets.list_presets(self.root,'CAS1')

    def body(self,**changes):
        return {'name':'Test loadout','revision':None,'source':'DEFAULT','source_revision':revision(self.raw),
                'catalog_revision':self.catalog['catalog_revision'],'fuel':.3,'livery':'original-livery',
                'selections':{'0':'A','1':'B','2':''},**changes}

    def plan(self,**changes):return presets.plan_preset(self.root,'CAS1',self.body(**changes))
    def post(self,body):return self.client.post('/api/platforms/CAS1/presets/preview',json=body,headers=self.headers)
    def save(self,ticket):return self.client.post('/api/preset-commit',json={'ticket':ticket},headers=self.headers)
    def unchanged(self):
        for p,raw in self.original.items():self.assertEqual((self.root/p).read_bytes(),raw)
        self.assertFalse(list(self.root.rglob('*.bak')))

    def test_list_read_and_preview_are_read_only(self):
        self.assertEqual(self.catalog['files'][0]['name'],'DEFAULT')
        loaded=presets.read_preset(self.root,'CAS1','DEFAULT')
        self.assertEqual(loaded['selections'],{'0':'A','1':'B','2':''});self.assertEqual(loaded['issues'],[])
        self.assertTrue(self.plan().summary['creating']);self.assertFalse((self.root/'CAS1/Test loadout.preset').exists());self.unchanged()

    def test_new_copy_preserves_exact_source_bytes_and_unknown_fields(self):
        result=presets.commit_preset(self.plan());self.assertIsNone(result.backup)
        self.assertEqual(result.path.read_bytes(),self.raw);self.assertEqual(presets.decode(result.path.read_bytes())['Extra'],self.data['Extra'])
        self.unchanged()

    def test_overwrite_keeps_bom_crlf_unknown_fields_and_exact_backup(self):
        plan=self.plan(name='DEFAULT',revision=revision(self.raw),fuel=.8,selections={'0':'B','1':'A','2':''})
        result=presets.commit_preset(plan);self.assertEqual(result.backup.read_bytes(),self.raw)
        written=result.path.read_bytes();self.assertTrue(written.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'\n',written.replace(b'\r\n',b''))
        after=presets.decode(written);self.assertEqual(after['Extra'],self.data['Extra']);self.assertEqual(after['Vanilla'],1)
        self.assertEqual(after['Stations'],['Nose=B','Center Pylon=A','Other=']);self.assertEqual(after['Hardpoints'],['B','A',''])

    def test_noop_has_no_backup(self):
        result=presets.commit_preset(self.plan(name='DEFAULT',revision=revision(self.raw)))
        self.assertFalse(result.changed);self.assertIsNone(result.backup);self.unchanged()

    def test_new_blank_does_not_invent_vanilla_flag(self):
        plan=self.plan(source=None,source_revision=None,selections={'0':'','1':'','2':''},livery='',fuel=1)
        result=presets.commit_preset(plan);data=presets.decode(result.path.read_bytes())
        self.assertEqual(set(data),{'Fuel','Livery','Stations','Hardpoints'});self.assertEqual(data['Hardpoints'],['','','']);self.unchanged()

    def test_stale_key_normalizes_to_whitelisted_write_key(self):
        plan=self.plan(selections={'0':'STALE8','1':'B','2':''})
        self.assertEqual(presets.decode(plan.replacement)['Hardpoints'][0],'REAL6');self.unchanged()

    def test_unavailable_unknown_and_missing_selection_refused(self):
        for chosen in [{'0':'C','1':'B','2':''},{'0':'unknown','1':'B','2':''},{'0':'A'},{'0':'A','1':'B','2':False}]:
            with self.subTest(chosen=chosen):self.assertEqual(self.post(self.body(selections=chosen)).status_code,400)
        self.unchanged()

    def test_precluding_occupied_stations_refused(self):
        self.assertEqual(self.post(self.body(selections={'0':'A','1':'B','2':'A'})).status_code,400);self.unchanged()

    def test_invalid_filename_and_case_collision_refused(self):
        for name in ['../bad','a/b','a\\b','CON','nul.txt','bad:name','bad.',' bad','x'*101]:
            with self.subTest(name=name):
                with self.assertRaises(WriteError):self.plan(name=name)
        with self.assertRaises(WriteError):self.plan(name='default')
        self.unchanged()

    def test_duplicate_name_does_not_overwrite_without_revision(self):
        self.assertEqual(self.post(self.body(name='DEFAULT')).status_code,409);self.unchanged()

    def test_source_conflict_before_preview(self):
        self.path.write_text(json.dumps({**self.data,'Fuel':.6}))
        self.assertEqual(self.post(self.body()).status_code,409)
        self.assertFalse((self.root/'CAS1/Test loadout.preset').exists())

    def test_catalog_conflict_before_preview(self):
        path=self.root/'CAS1/weaponstation0/Nose.json';path.write_text('{"allowedWeapons":["B"]}')
        self.assertEqual(self.post(self.body()).status_code,409);self.assertFalse((self.root/'CAS1/Test loadout.preset').exists())

    def test_whitelist_or_source_change_after_review_refused(self):
        for target in [self.path,self.root/'CAS1/weaponstation0/Nose.json']:
            with self.subTest(target=target):
                raw=target.read_bytes();plan=self.plan();target.write_bytes(raw+b' ')
                with self.assertRaises(ChangedOnDisk):presets.commit_preset(plan)
                target.write_bytes(raw)
        self.unchanged()

    def test_target_appearing_after_review_is_not_overwritten(self):
        plan=self.plan();plan.path.write_bytes(self.raw+b' ')
        with self.assertRaises(ChangedOnDisk):presets.commit_preset(plan)
        self.assertEqual(plan.path.read_bytes(),self.raw+b' ');self.unchanged()

    def test_differently_cased_target_appearing_after_review_refused(self):
        plan=self.plan();other=plan.path.with_name(plan.path.name.lower());other.write_bytes(self.raw)
        with self.assertRaises(ChangedOnDisk):presets.commit_preset(plan)
        self.assertEqual(other.read_bytes(),self.raw);self.assertFalse(plan.path.exists());self.unchanged()

    def test_atomic_create_collision_keeps_other_writer_file(self):
        plan=self.plan()
        def collide(temporary,path):path.write_bytes(b'outside writer');raise FileExistsError('race')
        with patch('alis.presets.os.link',side_effect=collide):
            with self.assertRaises(ChangedOnDisk):presets.commit_preset(plan)
        self.assertEqual(plan.path.read_bytes(),b'outside writer');self.assertFalse(list(self.root.rglob('*.tmp')));self.unchanged()

    def test_failed_replace_keeps_original_and_backup(self):
        plan=self.plan(name='DEFAULT',revision=revision(self.raw),fuel=.8)
        with patch('alis.presets.os.replace',side_effect=OSError('locked')):
            with self.assertRaises(OSError):presets.commit_preset(plan)
        self.assertEqual(self.path.read_bytes(),self.raw);self.assertEqual(list(self.path.parent.glob('*.bak'))[0].read_bytes(),self.raw)
        self.assertFalse((self.root/'.alis-write.lock').exists());self.assertFalse(list(self.root.rglob('*.tmp')))

    def test_symlink_source_and_target_refused(self):
        link=self.root/'CAS1/Linked.preset';link.symlink_to(self.path)
        for kw in [{'name':'Linked'},{'source':'Linked'}]:
            with self.subTest(kw=kw):
                with self.assertRaises(WriteError):self.plan(**kw)
        self.unchanged()

    def test_forged_plan_cannot_write_outside_platform(self):
        with self.assertRaises(WriteError):presets.commit_preset(replace(self.plan(),path=self.root/'Outside.preset'))
        self.assertFalse((self.root/'Outside.preset').exists());self.unchanged()

    def test_mismatched_arrays_duplicate_fields_and_nan_refused(self):
        for raw in [b'{"Fuel":NaN,"Livery":"","Stations":[],"Hardpoints":[]}',b'{"Fuel":1,"Fuel":1,"Livery":"","Stations":[],"Hardpoints":[]}']:
            with self.assertRaises(WriteError):presets.decode(raw)
        self.path.write_text(json.dumps({**self.data,'Hardpoints':['B','B','']}))
        with self.assertRaises(WriteError):presets.read_preset(self.root,'CAS1','DEFAULT')

    def test_api_save_ticket_and_local_guards(self):
        body=self.body();url='/api/platforms/CAS1/presets/preview'
        self.assertEqual(self.client.post(url,json=body).status_code,403)
        self.assertEqual(self.client.post(url,json=body,headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
        result=self.post(body);self.assertEqual(result.status_code,200)
        ticket=result.get_json()['ticket'];saved=self.save(ticket);self.assertEqual(saved.status_code,200);self.assertTrue(saved.get_json()['verified'])
        self.assertEqual(self.save(ticket).status_code,410);self.unchanged()

    def test_expired_ticket_cannot_create_file(self):
        ticket=self.post(self.body()).get_json()['ticket'];stamp,plan=self.app.extensions['alis_preset_plans'][ticket]
        self.app.extensions['alis_preset_plans'][ticket]=(stamp-601,plan)
        self.assertEqual(self.save(ticket).status_code,410);self.unchanged()

    def test_existing_unavailable_mount_is_readable_but_save_is_blocked(self):
        self.path.write_text(json.dumps({**self.data,'Stations':['Nose=C','Center Pylon=B','Other='],'Hardpoints':['C','B','']}))
        loaded=presets.read_preset(self.root,'CAS1','DEFAULT');self.assertTrue(loaded['issues'])
        self.assertEqual(self.post(self.body(source_revision=loaded['revision'],selections=loaded['selections'])).status_code,400)


if __name__=='__main__':unittest.main()
