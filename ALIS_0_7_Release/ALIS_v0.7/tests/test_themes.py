import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import test_writer
from alis import themes
from alis.web import create_app
from alis.writer import ChangedOnDisk, WriteError


class ThemeTests(unittest.TestCase):
    def setUp(self):
        fixture=test_writer.WriterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root,self.path,self.raw=fixture.root,fixture.path,fixture.raw
        self.app=create_app(self.root);self.client=self.app.test_client();self.headers={'X-ALIS-Token':self.app.config['ALIS_TOKEN']}
        self.rev=themes.inventory(self.root)['revision']
        self.state={'selected':'custom-12345678','custom':{'custom-12345678':copy.deepcopy(themes.BUILTINS['alis'])}}

    def post(self,data=None,revision=None):return self.client.post('/api/themes',json={'state':data or self.state,'revision':revision or self.rev},headers=self.headers)

    def test_default_inventory_is_read_only(self):
        data=themes.inventory(self.root);self.assertEqual(data['state']['selected'],'alis');self.assertEqual(len(data['builtins']),4)
        self.assertFalse((self.root/'.alis').exists())

    def test_custom_theme_save_and_restart(self):
        self.state['custom']['custom-12345678']['name']='Jimmy theme';self.state['custom']['custom-12345678']['colors']['accent']='#FF1234'
        result=self.post();self.assertEqual(result.status_code,200)
        data=create_app(self.root).test_client().get('/api/bootstrap').get_json()['themes']
        self.assertEqual(data['state']['custom']['custom-12345678']['colors']['accent'],'#ff1234')
        self.assertEqual(data['state']['custom']['custom-12345678']['name'],'Jimmy theme');self.assertEqual(self.path.read_bytes(),self.raw)

    def test_builtins_can_be_selected_without_custom(self):
        for selected in themes.BUILTINS:
            current=themes.inventory(self.root)['revision'];result=self.post({'selected':selected,'custom':{}},current)
            self.assertEqual(result.status_code,200);self.assertEqual(result.get_json()['themes']['state']['selected'],selected)

    def test_noop_and_exact_backup(self):
        first=self.post().get_json();raw=(self.root/'.alis/ui.json').read_bytes()
        self.assertIsNone(self.post(revision=first['themes']['revision']).get_json()['backup'])
        self.state['custom']['custom-12345678']['colors']['accent']='#123456'
        saved=self.post(revision=first['themes']['revision']).get_json();self.assertEqual((self.root/saved['backup']).read_bytes(),raw)

    def test_conflict_keeps_latest_theme(self):
        self.post();raw=(self.root/'.alis/ui.json').read_bytes();self.assertEqual(self.post().status_code,409)
        self.assertEqual((self.root/'.alis/ui.json').read_bytes(),raw)

    def test_css_injection_and_missing_color_refused(self):
        for value in ['red','#fff','#ffffff;display:none','url(https://bad)','</style><script>','']:
            data=copy.deepcopy(self.state);data['custom']['custom-12345678']['colors']['accent']=value
            with self.subTest(value=value):self.assertEqual(self.post(data).status_code,400)
        data=copy.deepcopy(self.state);del data['custom']['custom-12345678']['colors']['text'];self.assertEqual(self.post(data).status_code,400)
        self.assertFalse((self.root/'.alis').exists())

    def test_bad_names_ids_and_selection_refused(self):
        for change in [{'name':''},{'name':'x\n'},{'name':'x'*61}]:
            data=copy.deepcopy(self.state);data['custom']['custom-12345678'].update(change);self.assertEqual(self.post(data).status_code,400)
        for data in [{'selected':'missing','custom':{}},{'selected':'alis','custom':{'alis':themes.BUILTINS['alis']}}]:self.assertEqual(self.post(data).status_code,400)

    def test_too_many_custom_themes_refused(self):
        data={'selected':'alis','custom':{f'custom-{i:08x}':copy.deepcopy(themes.BUILTINS['alis']) for i in range(13)}}
        self.assertEqual(self.post(data).status_code,400)

    def test_removing_custom_theme_preserves_stock_presets(self):
        first=self.post().get_json();result=self.post({'selected':'daylight','custom':{}},first['themes']['revision'])
        self.assertEqual(result.status_code,200);self.assertEqual(result.get_json()['themes']['state']['custom'],{})
        self.assertEqual(len(result.get_json()['themes']['builtins']),4)

    def test_symlinked_settings_and_lock_refused(self):
        folder=self.root/'.alis';folder.mkdir();(folder/'ui.lock').write_text('active')
        self.assertEqual(self.post().status_code,400);(folder/'ui.lock').unlink();(folder/'ui.json').symlink_to(self.path)
        with self.assertRaises(WriteError):themes.inventory(self.root)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_failed_replace_keeps_settings_and_backup(self):
        first=self.post().get_json();raw=(self.root/'.alis/ui.json').read_bytes();self.state['selected']='amber'
        with patch('alis.themes.os.replace',side_effect=OSError('locked')):self.assertEqual(self.post(revision=first['themes']['revision']).status_code,400)
        self.assertEqual((self.root/'.alis/ui.json').read_bytes(),raw);self.assertEqual(list((self.root/'.alis').glob('*.bak'))[0].read_bytes(),raw)
        self.assertFalse((self.root/'.alis/ui.lock').exists());self.assertFalse(list((self.root/'.alis').glob('*.tmp')))

    def test_local_mutation_guards(self):
        body={'state':self.state,'revision':self.rev}
        self.assertEqual(self.client.post('/api/themes',json=body).status_code,403)
        self.assertEqual(self.client.post('/api/themes',json=body,headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
        self.assertFalse((self.root/'.alis').exists())

    def test_corrupt_duplicate_or_wrong_version_settings_refused(self):
        folder=self.root/'.alis';folder.mkdir()
        for raw in [b'not json',b'{"version":1,"version":1,"themes":{}}',b'{"version":2,"themes":{}}']:
            (folder/'ui.json').write_bytes(raw)
            with self.subTest(raw=raw):self.assertEqual(self.client.get('/api/bootstrap').status_code,400)
        self.assertEqual(self.path.read_bytes(),self.raw)


if __name__=='__main__':unittest.main()
