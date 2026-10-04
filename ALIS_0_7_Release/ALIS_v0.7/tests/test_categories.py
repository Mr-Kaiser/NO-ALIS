import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import test_writer
from alis import categories as c
from alis.dictionary import load_dictionary
from alis.models import WeaponMount, Platform
from alis.web import create_app


class CategoryTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root,self.path,self.raw=fixture.root,fixture.path,fixture.raw
        self.app=create_app(self.root);self.client=self.app.test_client()
        self.headers={'X-ALIS-Token':self.app.config['ALIS_TOKEN']}
        self.dictionary=load_dictionary(self.root);self.weapon=self.dictionary.weapons_by_json_key['A']
        self.rev=c.load(self.root)[1]
        self.tags={'role':['A2A'],'type':['MIS'],'guidance':['IR','SARH']}

    def post(self,**kwargs):
        body={'kind':'weapon','key':'A','identity':c.identity('weapon',self.weapon),'revision':self.rev,'tags':self.tags}
        body.update(kwargs)
        return self.client.post('/api/categories',json=body,headers=self.headers)

    def weapon_tags(self,key,name):
        return c.weapon_defaults(WeaponMount('mod',key,name,key,1))['tags']

    def test_stock_guidance_and_explicit_hints(self):
        for key,name,guidance in [('AAM1_single','MMR-S3','IR'),('AAM2_double','AAM-29 Scythe x2','ARH'),
                                  ('AGM1_single','AGM-48','OPT'),('Rocket2_4Pod','AGR-24 Kingpin x4','LAS'),
                                  ('bomb_glide1','PAB-80LR','OPT'),('bomb_500','GPO-500','OPT'),
                                  ('AGM_scanner1','Eyeball Mk.II','OPT'),('mod_sam_sarh','SAM missile','SARH')]:
            with self.subTest(name=name):self.assertIn(guidance,self.weapon_tags(key,name)['guidance'])

    def test_real_world_name_does_not_guess_mod_seeker(self):
        for name in ['AIM-120D AMRAAM','AIM-9M','R-27ER','Mystery missile']:
            with self.subTest(name=name):self.assertEqual(self.weapon_tags('modded',name)['guidance'],[])

    def test_vehicle_and_support_false_positives(self):
        for key,name,kind in [('UGV1_SAMx1','Hexhound SAM','CARGO'),('SAMTurret1x1','RAM45 Launcher','CARGO'),
                             ('FuelContainer1x1','Fuel Container 1500L','FUEL'),('laser_EW1','120kw High Energy Laser','DEW'),
                             ('JammingPod1','Radar Jamming Pod','POD'),('RocketPod75mm','75mm rockets','RKT')]:
            with self.subTest(key=key):
                tags=self.weapon_tags(key,name);self.assertEqual(tags['type'],[kind]);self.assertNotIn('LAS',tags['guidance'])
        self.assertEqual(self.weapon_tags('AGM_scanner1','Eyeball Mk.II')['role'],['REC'])
        self.assertEqual(self.weapon_tags('unknown','Unknown'),c.empty('weapon'))

    def test_platform_labels_ignore_modifying_owner(self):
        tags=c.platform_defaults(Platform('AttackHelo1'))['tags']
        self.assertEqual(tags,{'type':['HELO'],'role':['ATTACK']})
        self.assertEqual(c.platform_defaults(Platform('kar_tonk'))['tags']['type'],['GROUND'])
        self.assertEqual(c.platform_defaults(Platform('LandingKraft'))['tags']['type'],['SHIP'])
        self.assertEqual(c.platform_defaults(Platform('kestrel'))['tags'],c.empty('platform'))
        self.assertEqual(c.platform_defaults(Platform('Multirole1'))['tags']['type'],['FW'])
        self.assertEqual(c.platform_defaults(Platform('SmallFighter1'))['tags']['type'],['FW','VTOL'])

    def test_bootstrap_read_only_and_groups_exposed(self):
        data=self.client.get('/api/bootstrap').get_json()
        self.assertEqual(data['version'],'0.7.0');self.assertIn('SARH',data['category_options']['weapon']['guidance'])
        self.assertEqual(data['weapons'][0]['categories']['tags'],c.empty('weapon'))
        self.assertFalse((self.root/'.alis').exists());self.assertEqual(self.path.read_bytes(),self.raw)

    def test_save_restart_and_game_files_unchanged(self):
        before={p.name:p.read_bytes() for p in self.root.glob('*.csv')}
        response=self.post();self.assertEqual(response.status_code,200)
        app=create_app(self.root);data=app.test_client().get('/api/bootstrap').get_json()
        weapon=next(w for w in data['weapons'] if w['key']=='A')
        self.assertTrue(weapon['categories']['custom']);self.assertEqual(set(weapon['categories']['tags']['guidance']),{'IR','SARH'})
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.glob('*.csv')})

    def test_multiple_overrides_exact_backup_noop_and_revert(self):
        first=self.post().get_json();path=self.root/'.alis/categories.json';raw=path.read_bytes()
        noop=self.post(revision=first['revision']).get_json();self.assertIsNone(noop['backup']);self.assertEqual(path.read_bytes(),raw)
        second=self.post(kind='platform',key='CAS1',identity='CAS1',revision=first['revision'],tags={'type':['VTOL'],'role':['MULTI']}).get_json()
        self.assertEqual((self.root/second['backup']).read_bytes(),raw)
        store=c.load(self.root)[0];self.assertIn('A',store['weapon']);self.assertIn('CAS1',store['platform'])
        reverted=self.post(revision=second['revision'],tags=None).get_json()
        self.assertFalse(reverted['categories']['custom']);self.assertEqual(reverted['categories']['tags'],c.empty('weapon'))
        self.assertIn('CAS1',c.load(self.root)[0]['platform'])
        self.assertFalse(list(path.parent.glob('*.tmp')));self.assertFalse((path.parent/'categories.lock').exists())

    def test_empty_custom_groups_remain_custom(self):
        data=self.post(tags=c.empty('weapon')).get_json()
        self.assertTrue(data['categories']['custom']);self.assertEqual(data['categories']['tags'],c.empty('weapon'))

    def test_revision_and_dictionary_conflicts(self):
        first=self.post().get_json();raw=(self.root/'.alis/categories.json').read_bytes()
        self.assertEqual(self.post().status_code,409)
        self.assertEqual(self.post(revision=first['revision'],identity='bad').status_code,409)
        self.assertEqual((self.root/'.alis/categories.json').read_bytes(),raw)

    def test_changed_weapon_identity_ignores_old_tags(self):
        self.post();store=c.load(self.root)[0]
        newer=replace(self.weapon,display_name='Reused key')
        labels=c.labels('weapon',newer,store)
        self.assertFalse(labels['custom']);self.assertTrue(labels['stale_override']);self.assertEqual(labels['tags'],c.empty('weapon'))

    def test_invalid_tags_and_missing_items_refused(self):
        for tags in [None,{}, {'role':[],'type':[],'guidance':['<script>']},
                     {'role':['A2A','A2A'],'type':['MIS'],'guidance':[]}]:
            if tags is None:continue
            with self.subTest(tags=tags):self.assertEqual(self.post(tags=tags).status_code,400)
        self.assertEqual(self.post(key='../../no').status_code,404)
        self.assertEqual(self.post(kind={}).status_code,400)
        self.assertFalse((self.root/'.alis').exists())

    def test_mutation_guards(self):
        self.assertEqual(self.client.post('/api/categories',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/categories',json={},headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
        self.assertFalse((self.root/'.alis').exists())

    def test_corrupt_duplicate_or_wrong_version_refused(self):
        folder=self.root/'.alis';folder.mkdir()
        for raw in [b'not json',b'{"version":1,"version":1,"weapon":{},"platform":{}}',
                    b'{"version":2,"weapon":{},"platform":{}}']:
            (folder/'categories.json').write_bytes(raw)
            with self.subTest(raw=raw):self.assertEqual(self.client.get('/api/bootstrap').status_code,400)

    def test_symlink_and_active_lock_refused(self):
        folder=self.root/'.alis';folder.mkdir();(folder/'categories.json').symlink_to(self.path)
        self.assertEqual(self.client.get('/api/bootstrap').status_code,400);(folder/'categories.json').unlink()
        (folder/'categories.lock').write_text('other writer')
        self.assertEqual(self.post().status_code,400);self.assertFalse((folder/'categories.json').exists())
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_failed_atomic_replace_retains_original_and_backup(self):
        first=self.post().get_json();path=self.root/'.alis/categories.json';raw=path.read_bytes()
        with patch('alis.categories.os.replace',side_effect=OSError('simulated')):
            response=self.post(revision=first['revision'],tags=c.empty('weapon'))
        self.assertEqual(response.status_code,400);self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(next(path.parent.glob('*.bak')).read_bytes(),raw)
        self.assertFalse((path.parent/'categories.lock').exists());self.assertFalse(list(path.parent.glob('*.tmp')))


if __name__=='__main__':unittest.main()
