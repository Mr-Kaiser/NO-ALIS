import base64
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import test_writer
from alis.dictionary import load_dictionary
from alis.layouts import SHAPES, load_store, profile_for, save_profile, validate_profile
from alis.web import create_app
from alis.writer import WriteError, ChangedOnDisk


class LayoutTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root,self.path,self.raw=fixture.root,fixture.path,fixture.raw
        self.stations=load_dictionary(self.root).platforms['CAS1'].stations
        self.app=create_app(self.root);self.client=self.app.test_client()
        self.headers={'X-ALIS-Token':self.app.config['ALIS_TOKEN']}
        self.inventory=self.client.get('/api/bootstrap').get_json()
        self.rev=self.inventory['profiles_revision']
        self.profile={'display_name':'My Brawler','silhouette':'brawler','verified':True,'image':None,
                      'stations':{'1':{'expected_name':'Center Pylon','points':[[0.4,0.6],[0.6,0.6]]}}}
        self.original={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def post(self,profile=None,revision=None):
        return self.client.post('/api/platforms/CAS1/profile',json={'profile':self.profile if profile is None else profile,
                                'revision':self.rev if revision is None else revision},headers=self.headers)

    def assert_game_unchanged(self):
        for name,raw in self.original.items():self.assertEqual((self.root/name).read_bytes(),raw)
        self.assertFalse(list(self.path.parent.glob('*.bak')))

    def test_bootstrap_stock_name_and_filtered_defaults(self):
        p=self.inventory['platforms'][0]
        self.assertEqual(p['name'],'CAS1');self.assertEqual(p['display_name'],'A-19 Brawler')
        self.assertFalse(p['profile']['verified'])
        self.assertEqual(set(p['profile']['stations']),{'1'})
        self.assertTrue(p['profile']['stale']) # fixture is a smaller export
        self.assertFalse((self.root/'.alis').exists());self.assert_game_unchanged()

    def test_schematic_assets_avoid_inline_styles_under_csp(self):
        import xml.etree.ElementTree as ET
        for shape in SHAPES:
            response=self.client.get(f'/static/silhouettes/{shape}.svg')
            self.assertEqual(response.status_code,200)
            self.assertIn("style-src 'self'",response.headers['Content-Security-Policy'])
            root=ET.fromstring(response.data);self.assertEqual(root.get('viewBox'),'0 0 1000 1000')
            for node in root.iter():
                self.assertNotIn(node.tag.split('}')[-1],{'style','script','foreignObject'})
                self.assertNotIn('style',node.attrib)
                if node.tag.split('}')[-1] in {'path','circle','rect'}:self.assertIsNotNone(node.get('fill'))
            response.close()

    def test_unknown_platform_falls_back_without_guessing(self):
        p=profile_for('MyMod',self.stations,{'version':1,'platforms':{}})
        self.assertEqual(p['display_name'],'MyMod');self.assertEqual(p['source'],'unmapped')
        self.assertEqual(p['stations'],{});self.assertEqual(p['unmapped'],[1])

    def test_save_and_restart_preserve_layout_without_game_changes(self):
        response=self.post();self.assertEqual(response.status_code,200)
        result=response.get_json();self.assertIsNone(result['backup'])
        self.assertEqual(result['profile']['stations']['1']['points'],[[0.4,0.6],[0.6,0.6]])
        self.assertTrue(result['profile']['verified']);self.assertNotEqual(result['revision'],self.rev)
        restarted=create_app(self.root).test_client().get('/api/bootstrap').get_json()
        self.assertEqual(restarted['platforms'][0]['display_name'],'My Brawler')
        self.assertEqual(restarted['profiles_revision'],result['revision']);self.assert_game_unchanged()

    def test_second_save_has_exact_backup_and_noop_does_not(self):
        first=self.post().get_json();before=(self.root/'.alis/platforms.json').read_bytes()
        second=self.post(revision=first['revision']).get_json()
        self.assertEqual(first['revision'],second['revision']);self.assertIsNone(second['backup'])
        self.profile['display_name']='Another name'
        changed=self.post(revision=first['revision']).get_json()
        self.assertEqual((self.root/changed['backup']).read_bytes(),before);self.assert_game_unchanged()

    def test_stale_revision_preserves_newer_profile(self):
        result=self.post().get_json();raw=(self.root/'.alis/platforms.json').read_bytes()
        self.profile['display_name']='Stale client'
        self.assertEqual(self.post().status_code,409)
        self.assertEqual((self.root/'.alis/platforms.json').read_bytes(),raw)
        self.assertEqual(load_store(self.root)[1],result['revision']);self.assert_game_unchanged()

    def test_different_platform_save_retains_existing_profile(self):
        first=self.post().get_json()
        profile=copy.deepcopy(self.profile);profile['display_name']='Mod platform'
        save_profile(self.root,'MyMod',self.stations,profile,first['revision'])
        store,_,_=load_store(self.root)
        self.assertEqual(set(store['platforms']),{'CAS1','MyMod'})
        self.assertEqual(store['platforms']['CAS1'],self.profile);self.assert_game_unchanged()

    def test_changed_station_name_removes_stale_markers(self):
        self.post()
        from dataclasses import replace
        stations=[replace(self.stations[0],station_name='New station')]
        p=profile_for('CAS1',stations,load_store(self.root)[0])
        self.assertEqual(p['stations'],{});self.assertEqual(p['unmapped'],[1])
        self.assertTrue(p['stale']);self.assertFalse(p['verified']);self.assert_game_unchanged()

    def test_invalid_coordinate_inputs_rejected_without_files(self):
        for point in [[-0.1,0.5],[0.5,1.01],[True,0.5],['0.4',0.5],[float('nan'),0.5],
                      [float('inf'),0.5],[10**1000,0.5],[0.5],None]:
            profile=copy.deepcopy(self.profile);profile['stations']['1']['points']=[point]
            with self.subTest(point=point):
                with self.assertRaises(WriteError):validate_profile(profile,self.stations)
        self.assertFalse((self.root/'.alis').exists());self.assert_game_unchanged()

    def test_bad_name_shape_station_and_counts(self):
        cases=[{'display_name':''},{'display_name':'x\n'}, {'display_name':'x'*121}, {'silhouette':[]},
               {'silhouette':'../../other'}, {'verified':'yes'}, {'stations':{'99':{'expected_name':'bad','points':[[0,0]]}}},
               {'stations':{'1':{'expected_name':'Wrong','points':[[0,0]]}}},
               {'stations':{'1':{'expected_name':'Center Pylon','points':[]}}},
               {'stations':{'1':{'expected_name':'Center Pylon','points':[[0,0]]*17}}}]
        for change in cases:
            with self.subTest(change=change):self.assertEqual(self.post({**self.profile,**change}).status_code,400)
        self.assertFalse((self.root/'.alis').exists());self.assert_game_unchanged()

    def test_png_image_saved_and_external_svg_invalid_images_refused(self):
        png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/cWQAAAAASUVORK5CYII='
        profile={**self.profile,'image':png}
        result=self.post(profile).get_json();self.assertEqual(result['profile']['image'],png)
        for image in ['https://example.com/image.png','data:image/svg+xml;base64,PHN2Zy8+','data:image/png;base64,!!!',
                      'data:image/png;base64,'+base64.b64encode(b'wrong content').decode(),
                      'data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'x'*(2*1024*1024)).decode()]:
            with self.subTest(image=image[:80]):self.assertEqual(self.post({**self.profile,'image':image},result['revision']).status_code,400)
        self.assert_game_unchanged()

    def test_profile_endpoint_guards_and_unknown_platform(self):
        body={'revision':self.rev,'profile':self.profile}
        self.assertEqual(self.client.post('/api/platforms/CAS1/profile',json=body).status_code,403)
        self.assertEqual(self.client.post('/api/platforms/CAS1/profile',json=body,headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/platforms/nope/profile',json=body,headers=self.headers).status_code,404)
        self.assertEqual(self.post(revision='bad').status_code,400)
        self.assertFalse((self.root/'.alis').exists())

    def test_corrupt_or_duplicate_profile_store_refused(self):
        folder=self.root/'.alis';folder.mkdir()
        for raw in [b'not json',b'{"version":1,"platforms":{},"platforms":{}}',b'{"version":2,"platforms":{}}']:
            (folder/'platforms.json').write_bytes(raw)
            with self.subTest(raw=raw):self.assertEqual(self.client.get('/api/bootstrap').status_code,400)
        self.assert_game_unchanged()

    def test_symlinked_settings_refused(self):
        outside=self.root/'outside';outside.mkdir();(self.root/'.alis').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(WriteError):load_store(self.root)
        with self.assertRaises(WriteError):save_profile(self.root,'CAS1',self.stations,self.profile,self.rev)
        self.assertEqual(list(outside.iterdir()),[]);self.assert_game_unchanged()

    def test_other_layout_writer_lock_refused(self):
        folder=self.root/'.alis';folder.mkdir();(folder/'profiles.lock').write_text('another writer')
        self.assertEqual(self.post().status_code,400)
        self.assertFalse((folder/'platforms.json').exists());self.assert_game_unchanged()

    def test_failed_replace_retains_original_profile_and_backup(self):
        first=self.post().get_json();raw=(self.root/'.alis/platforms.json').read_bytes()
        self.profile['display_name']='New name'
        with patch('alis.layouts.os.replace',side_effect=OSError('Simulated lock')):
            self.assertEqual(self.post(revision=first['revision']).status_code,400)
        self.assertEqual((self.root/'.alis/platforms.json').read_bytes(),raw)
        backups=list((self.root/'.alis').glob('*.bak'));self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),raw)
        self.assertFalse((self.root/'.alis/profiles.lock').exists())
        self.assertFalse(list((self.root/'.alis').glob('*.tmp')));self.assert_game_unchanged()


if __name__=='__main__':unittest.main()
