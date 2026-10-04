from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parent))
import test_writer
from alis.web import create_app
from alis.writer import revision


class WebTests(unittest.TestCase):
    def setUp(self):
        fixture = test_writer.WriterTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root,self.path,self.raw = fixture.root,fixture.path,fixture.raw
        self.app = create_app(self.root)
        self.client = self.app.test_client()
        self.headers = {'X-ALIS-Token':self.app.config['ALIS_TOKEN']}
        self.station_url = '/api/platforms/CAS1/stations/1'
        self.station = self.client.get(self.station_url).get_json()

    def preview(self, **kwargs):
        return self.client.post(self.station_url+'/preview',json={'revision':self.station['revision'],**kwargs},headers=self.headers)

    def save(self,ticket):
        return self.client.post('/api/commit',json={'ticket':ticket},headers=self.headers)

    def test_bootstrap_and_station(self):
        r = self.client.get('/api/bootstrap')
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.get_json()['weapons']),4)
        self.assertEqual(self.station['allowed'],['A','B'])
        self.assertEqual(self.station['revision'],revision(self.raw))

    def test_preview_no_write_and_verified_commit(self):
        r = self.preview(add=['C'],remove=['A'])
        self.assertEqual(r.status_code,200)
        p = r.get_json()
        self.assertEqual(p['added'],['C'])
        self.assertEqual(p['removed'],['A'])
        self.assertEqual(self.path.read_bytes(),self.raw)
        saved = self.save(p['ticket'])
        self.assertEqual(saved.status_code,200)
        self.assertTrue(saved.get_json()['verified'])
        self.assertEqual(saved.get_json()['station']['allowed'],['B','C'])
        self.assertEqual((self.root/saved.get_json()['backup']).read_bytes(),self.raw)

    def test_save_without_preview_refused(self):
        self.assertEqual(self.save('invented').status_code,410)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_ticket_is_single_use(self):
        ticket=self.preview(add=['C']).get_json()['ticket']
        self.assertEqual(self.save(ticket).status_code,200)
        self.assertEqual(self.save(ticket).status_code,410)

    def test_conflict_at_preview(self):
        self.path.write_bytes(b'{"allowedWeapons":["B"]}')
        self.assertEqual(self.preview(add=['C']).status_code,409)
        self.assertFalse(list(self.path.parent.glob('*.bak')))

    def test_conflict_at_commit(self):
        ticket=self.preview(add=['C']).get_json()['ticket']
        changed=b'{"allowedWeapons":["B"]}'
        self.path.write_bytes(changed)
        self.assertEqual(self.save(ticket).status_code,409)
        self.assertEqual(self.path.read_bytes(),changed)

    def test_tokens_and_origin_required(self):
        body={'revision':self.station['revision'],'add':['C']}
        self.assertEqual(self.client.post(self.station_url+'/preview',json=body).status_code,403)
        headers={**self.headers,'Origin':'https://unrelated.example'}
        self.assertEqual(self.client.post(self.station_url+'/preview',json=body,headers=headers).status_code,403)
        headers={**self.headers,'Origin':'http://localhost'}
        self.assertEqual(self.client.post(self.station_url+'/preview',json=body,headers=headers).status_code,200)

    def test_invalid_host_and_remote_address(self):
        self.assertEqual(self.client.get('/api/bootstrap',headers={'Host':'evil.example'}).status_code,400)
        self.assertEqual(self.client.get('/api/bootstrap',environ_overrides={'REMOTE_ADDR':'192.0.2.1'}).status_code,403)

    def test_invalid_payloads(self):
        for body in [[],{'revision':self.station['revision'],'add':'C'},
                     {'revision':self.station['revision'],'remove':[1]},
                     {'revision':self.station['revision'],'allow_empty':'yes'},
                     {'add':['C']}, {'revision':self.station['revision'],'restore':'../../other.bak'}]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.station_url+'/preview',json=body,headers=self.headers).status_code,400)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_empty_whitelist_needs_consent(self):
        self.assertEqual(self.preview(remove=['A','B']).status_code,400)
        ticket=self.preview(remove=['A','B'],allow_empty=True).get_json()['ticket']
        self.assertEqual(self.save(ticket).get_json()['station']['allowed'],[])

    def test_restore_uses_revision_and_keeps_exact_original(self):
        ticket=self.preview(add=['C']).get_json()['ticket']
        saved=self.save(ticket).get_json()
        self.station=saved['station']
        name=Path(saved['backup']).name
        ticket=self.preview(restore=name).get_json()['ticket']
        restored=self.save(ticket)
        self.assertEqual(restored.status_code,200)
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))),2)

    def test_expired_preview(self):
        ticket=self.preview(add=['C']).get_json()['ticket']
        stamp,plan=self.app.extensions['alis_plans'][ticket]
        self.app.extensions['alis_plans'][ticket]=(stamp-601,plan)
        self.assertEqual(self.save(ticket).status_code,410)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_noop_creates_no_backup(self):
        ticket=self.preview(add=['A']).get_json()['ticket']
        saved=self.save(ticket).get_json()
        self.assertFalse(saved['changed'])
        self.assertIsNone(saved['backup'])
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_unknown_key_and_missing_station(self):
        self.assertEqual(self.preview(add=['bad_key']).status_code,400)
        self.assertEqual(self.client.get('/api/platforms/CAS1/stations/99').status_code,400)

    def test_headers_and_no_debugger(self):
        r=self.client.get('/')
        self.assertIn('frame-ancestors',r.headers['Content-Security-Policy'])
        self.assertEqual(r.headers['X-Frame-Options'],'DENY')
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertFalse(self.app.debug)


if __name__=='__main__':
    unittest.main()
