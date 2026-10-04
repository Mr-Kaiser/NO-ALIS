from dataclasses import replace
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from alis.writer import ChangedOnDisk, WriteError, commit, plan_edit, plan_restore, revision
from edit_station import main
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'CAS1' / 'weaponstation1'
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'Center Pylon.json'
        self.raw = b'\xef\xbb\xbf{\r\n    "allowedWeapons": ["A", "B"],\r\n    "extra": {"label": "caf\xc3\xa9", "flag": true}\r\n}\r\n'
        self.path.write_bytes(self.raw)
        for name, rows in [
            ('hardpointdictionary_mounts.csv', [
                ['owner','jsonKey','displayName','assetName','ammo','note_code','note_detail'],
                ['vanilla','A','Alpha','asset_A',1,'',''],
                ['vanilla','B','Bravo','asset_B',2,'CHECK','check mount'],
                ['mod','C','Charlie','asset_C',1,'',''],
                ['vanilla','STALE8','Stale','REAL6',6,'STALE-KEY','use asset'],
            ]),
            ('hardpointdictionary_stations.csv', [
                ['aircraft','index','name','symmetryName','hardpointCount','precluding','owner'],
                ['CAS1',1,'Center Pylon','',1,'','vanilla'],
            ]),
        ]:
            with (self.root / name).open('w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(rows)

    def plan(self, **kwargs):
        return plan_edit(self.root, 'CAS1', 1, **kwargs)

    def assert_unchanged(self):
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertFalse(list(self.folder.glob('*.bak')))
        self.assertFalse((self.root / '.alis-write.lock').exists())

    def test_preview_writes_nothing(self):
        p = self.plan(add=['C'], remove=['A'])
        self.assertEqual(p.after, ('B', 'C'))
        self.assert_unchanged()

    def test_add_remove_preserves_unknown_fields_bom_crlf(self):
        p = self.plan(add=['C'], remove=['A'])
        result = commit(p)
        self.assertEqual(result.backup.read_bytes(), self.raw)
        written = self.path.read_bytes()
        self.assertTrue(written.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'\n', written.replace(b'\r\n',b''))
        before = json.loads(self.raw.decode('utf-8-sig'))
        after = json.loads(written.decode('utf-8-sig'))
        before['allowedWeapons'] = ['B','C']
        self.assertEqual(before, after)
        self.assertEqual(revision(written), result.revision)

    def test_noop_no_backup(self):
        self.assertFalse(commit(self.plan(add=['A'])).changed)
        self.assert_unchanged()

    def test_repeated_add_is_idempotent(self):
        first = commit(self.plan(add=['C','C']))
        saved = self.path.read_bytes()
        second = commit(self.plan(add=['C']))
        self.assertFalse(second.changed)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(len(list(self.folder.glob('*.bak'))),1)
        self.assertEqual(first.backup.read_bytes(),self.raw)

    def test_unknown_add_refused(self):
        with self.assertRaises(WriteError): self.plan(add=['missing'])
        self.assert_unchanged()

    def test_unknown_remove_refused(self):
        with self.assertRaises(WriteError): self.plan(remove=['typo'])
        self.assert_unchanged()

    def test_empty_requires_explicit_flag(self):
        with self.assertRaises(WriteError): self.plan(remove=['A','B'])
        self.assert_unchanged()
        commit(self.plan(remove=['A','B'], allow_empty=True))
        self.assertEqual(json.loads(self.path.read_text('utf-8-sig'))['allowedWeapons'],[])

    def test_add_remove_same_mount_refused(self):
        with self.assertRaises(WriteError): self.plan(add=['asset_A'],remove=['A'])
        self.assert_unchanged()

    def test_stale_key_normalized_only_when_requested(self):
        p = self.plan(add=['STALE8'])
        self.assertIn('REAL6',p.after)
        self.assertNotIn('STALE8',p.after)
        self.assertEqual(p.normalized, (('STALE8','REAL6'),))

    def test_stale_existing_key_replaced_when_added(self):
        self.path.write_text('{"allowedWeapons":["STALE8","B"]}')
        self.assertEqual(self.plan(add=['REAL6']).after, ('REAL6','B'))
        self.assertEqual(self.plan(remove=['REAL6']).after, ('B',))

    def test_unknown_existing_keys_retained_or_explicitly_removed(self):
        self.path.write_text('{"allowedWeapons":["missing","A"]}')
        self.assertEqual(self.plan(add=['C']).after, ('missing','A','C'))
        self.assertEqual(self.plan(remove=['missing']).after, ('A',))

    def test_stale_normalization_preserves_unrelated_duplicate_entries(self):
        self.path.write_text('{"allowedWeapons":["B","STALE8","B"]}')
        self.assertEqual(self.plan(add=['REAL6']).after, ('B','REAL6','B'))

    def test_asset_alias_maps_to_json_key(self):
        self.assertEqual(self.plan(add=['asset_C']).after, ('A','B','C'))

    def test_ambiguous_alias_refused(self):
        with (self.root/'hardpointdictionary_mounts.csv').open('a') as f:
            csv.writer(f).writerow(['mod','D','Delta','asset_C',1,'',''])
        with self.assertRaises(WriteError): self.plan(add=['asset_C'])
        self.assert_unchanged()

    def test_changed_since_preview_refused(self):
        p = self.plan(add=['C'])
        other = b'{"allowedWeapons":["A"]}'
        self.path.write_bytes(other)
        with self.assertRaises(ChangedOnDisk): commit(p)
        self.assertEqual(self.path.read_bytes(),other)
        self.assertFalse(list(self.folder.glob('*.bak')))

    def test_expected_revision_refused(self):
        with self.assertRaises(ChangedOnDisk): self.plan(add=['C'],expected_revision='0'*64)
        self.assert_unchanged()

    def test_other_alis_writer_lock_refused(self):
        p = self.plan(add=['C'])
        lock = self.root/'.alis-write.lock'
        lock.write_text('other writer')
        with self.assertRaises(WriteError): commit(p)
        self.assertEqual(lock.read_text(),'other writer')
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_failed_backup_leaves_station_unchanged(self):
        p = self.plan(add=['C'])
        with patch('alis.writer._backup',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): commit(p)
        self.assert_unchanged()

    def test_failed_atomic_replace_keeps_original_and_backup(self):
        p = self.plan(add=['C'])
        with patch('alis.writer.os.replace',side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError): commit(p)
        self.assertEqual(self.path.read_bytes(),self.raw)
        backups = list(self.folder.glob('*.bak'))
        self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),self.raw)
        self.assertFalse(list(self.folder.glob('.alis-*.tmp')))
        self.assertFalse((self.root/'.alis-write.lock').exists())

    def test_post_save_verification_failure_keeps_backup(self):
        p = self.plan(add=['C'])
        real_replace = os.replace
        def corrupted(src, dst):
            real_replace(src, dst)
            Path(dst).write_bytes(b'{"allowedWeapons":["B"]}')
        with patch('alis.writer.os.replace',side_effect=corrupted):
            with self.assertRaises(WriteError): commit(p)
        self.assertEqual(list(self.folder.glob('*.bak'))[0].read_bytes(),self.raw)

    def test_restore_is_byte_exact_and_backs_up_current(self):
        first = commit(self.plan(add=['C']))
        edited = self.path.read_bytes()
        restore = plan_restore(self.root,'CAS1',1,first.backup)
        self.assertEqual(self.path.read_bytes(),edited)
        second = commit(restore)
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertEqual(second.backup.read_bytes(),edited)
        self.assertNotEqual(first.backup,second.backup)
        self.assertEqual(first.backup.read_bytes(),self.raw)

    def test_other_station_backup_refused(self):
        backup = self.folder/'Other.json.20261002T000000000000Z.abcdef123456.bak'
        backup.write_bytes(self.raw)
        with self.assertRaises(WriteError): plan_restore(self.root,'CAS1',1,backup)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_invalid_json_shapes_refused(self):
        for raw in [b'[]',b'{}',b'{"allowedWeapons":null}',b'{"allowedWeapons":[1]}',
                    b'{"allowedWeapons":[],"allowedWeapons":["A"]}',
                    b'{"allowedWeapons":["A"],"extra":NaN}',b'garbage']:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(WriteError): self.plan(add=['C'])
                self.assertEqual(self.path.read_bytes(),raw)

    def test_duplicate_station_files_refused(self):
        (self.folder/'Other.json').write_bytes(self.raw)
        with self.assertRaises(WriteError): self.plan(add=['C'])
        self.assert_unchanged()

    def test_filename_mismatch_refused(self):
        self.path.rename(self.folder/'Mismatch.json')
        with self.assertRaises(WriteError): self.plan(add=['C'])

    def test_missing_station_refused(self):
        self.path.unlink()
        with self.assertRaises(WriteError): self.plan(add=['C'])

    def test_path_traversal_platform_refused(self):
        with (self.root/'hardpointdictionary_stations.csv').open('a') as f:
            csv.writer(f).writerow(['../outside',1,'Center Pylon','',1,'','mod'])
        with self.assertRaises(WriteError): plan_edit(self.root,'../outside',1,add=['C'])
        self.assert_unchanged()

    def test_station_symlink_refused(self):
        destination = self.root/'outside.json'
        destination.write_bytes(self.raw)
        self.path.unlink()
        try: self.path.symlink_to(destination)
        except OSError: self.skipTest('Symlinks unavailable on this machine.')
        with self.assertRaises(WriteError): self.plan(add=['C'])
        self.assertEqual(destination.read_bytes(),self.raw)

    def test_invalid_plan_cannot_change_other_fields(self):
        p = self.plan(add=['C'])
        data = json.loads(p.replacement.decode('utf-8-sig'))
        data['extra'] = 'unexpected'
        with self.assertRaises(WriteError): commit(replace(p,replacement=json.dumps(data).encode()))
        self.assert_unchanged()

    def test_cli_preview_apply_and_error(self):
        common = [str(self.root),'--platform','CAS1','--station','1','--add','C','--json']
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main(common),0)
        self.assertEqual(json.loads(out.getvalue())['mode'],'PREVIEW')
        self.assert_unchanged()
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main(common+['--apply']),0)
        self.assertTrue(json.loads(out.getvalue())['verified'])
        with redirect_stderr(StringIO()) as err:
            self.assertEqual(main(common+['--add','not_real']),1)
        self.assertIn('error',json.loads(err.getvalue()))


if __name__ == '__main__':
    unittest.main()
