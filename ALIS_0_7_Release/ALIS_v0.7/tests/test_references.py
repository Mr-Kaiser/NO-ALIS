import base64
import copy
import json
from pathlib import Path
import unittest

from alis import references
from alis.dictionary import load_dictionary
from alis.layouts import defaults, profile_for, validate_profile
from alis.web import create_app
from alis.writer import WriteError
import test_writer


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root=fixture.root;self.path=fixture.path;self.raw=fixture.raw
        self.stations=load_dictionary(self.root).platforms['CAS1'].stations
        self.app=create_app(self.root);self.client=self.app.test_client()
        self.headers={'X-ALIS-Token':self.app.config['ALIS_TOKEN']}

    def test_thirteen_defaults_twenty_views_nineteen_original_assets(self):
        manifest=json.loads((references.ASSETS/'config/references.json').read_text())['platforms']
        self.assertEqual(len(manifest),13);self.assertEqual(sum(map(len,manifest.values())),20)
        self.assertEqual(len(list((references.ASSETS/'static/references').iterdir())),19)
        builtins=defaults()
        for platform,views in manifest.items():
            with self.subTest(platform=platform):
                self.assertEqual(sum(v['default'] for v in views),1)
                inventory=references.inventory(platform)
                self.assertEqual(len(inventory),len(views))
                self.assertEqual(builtins[platform]['image'],next(v['image'] for v in inventory if v['default']))
                for view,loaded in zip(views,inventory):
                    raw=base64.b64decode(loaded['image'].split(',')[1],validate=True)
                    self.assertEqual(raw,(references.ASSETS/'static/references'/view['file']).read_bytes())
                    # The normal profile validator also verifies type signatures.
                    validate_profile({'display_name':platform,'image':loaded['image'],'image_crop':loaded['image_crop']},[])

    def test_stock_bootstrap_has_reference_and_get_default_writes_nothing(self):
        data=self.client.get('/api/bootstrap').get_json()
        profile=data['platforms'][0]['profile'];self.assertTrue(profile['image'].startswith('data:image/webp;base64,'))
        fetched=self.client.get('/api/platforms/CAS1/profile-default')
        self.assertEqual(fetched.status_code,200);self.assertEqual(fetched.get_json()['profile']['image'],profile['image'])
        self.assertEqual(self.path.read_bytes(),self.raw);self.assertFalse((self.root/'.alis').exists())

    def test_custom_profile_wins_until_explicit_default_save(self):
        data=self.client.get('/api/bootstrap').get_json();profile=copy.deepcopy(data['platforms'][0]['profile'])
        profile['image']=None;profile['display_name']='My saved layout'
        saved=self.client.post('/api/platforms/CAS1/profile',headers=self.headers,json={'profile':profile,'revision':data['profiles_revision']}).get_json()
        before=(self.root/'.alis/platforms.json').read_bytes()
        restarted=create_app(self.root).test_client().get('/api/bootstrap').get_json()
        self.assertEqual(restarted['platforms'][0]['profile']['display_name'],'My saved layout')
        self.assertIsNone(restarted['platforms'][0]['profile']['image'])
        default=self.client.get('/api/platforms/CAS1/profile-default').get_json()['profile']
        self.assertEqual((self.root/'.alis/platforms.json').read_bytes(),before)
        restored=self.client.post('/api/platforms/CAS1/profile',headers=self.headers,json={'profile':default,'revision':saved['revision']})
        self.assertEqual(restored.status_code,200);self.assertEqual(restored.get_json()['profile']['image'],default['image'])
        self.assertEqual((self.root/restored.get_json()['backup']).read_bytes(),before)

    def test_medusa_crop_preserves_original_plate(self):
        profile=defaults()['EW1'];self.assertEqual(profile['image_crop'],[.1,.2,.8,.8])
        top,plate=references.inventory('EW1');self.assertEqual(top['image'],plate['image']);self.assertIsNone(plate['image_crop'])
        self.assertEqual(validate_profile({**profile,'stations':{}},[])['image_crop'],profile['image_crop'])

    def test_invalid_crops_rejected(self):
        image=references.default_reference('CAS1')['image']
        for crop in ([0,0,0,1],[-.1,0,1,1],[0,0,1.1,1],[0,0,True,1],
                     [0,0,float('inf'),1],[0,0,1],[.5,0,1,1],'crop'):
            with self.subTest(crop=crop),self.assertRaises(WriteError):validate_profile({'display_name':'test','image':image,'image_crop':crop},[])
        with self.assertRaises(WriteError):validate_profile({'display_name':'test','image_crop':[0,0,1,1]},[])

    def test_front_and_top_views_selectable_without_game_writes(self):
        response=self.client.get('/api/platforms/CAS1/references')
        self.assertEqual(response.status_code,200)
        self.assertEqual([v['id'] for v in response.get_json()['views']],['top','front'])
        self.assertEqual(self.path.read_bytes(),self.raw);self.assertFalse((self.root/'.alis').exists())

    def test_unknown_mod_has_no_guessed_reference(self):
        self.assertEqual(references.inventory('MyMod'),[])
        profile=profile_for('MyMod',self.stations,{'version':1,'platforms':{}})
        self.assertIsNone(profile['image'])
        self.assertEqual(self.client.get('/api/platforms/Unknown/references').status_code,404)


if __name__=='__main__':unittest.main()
