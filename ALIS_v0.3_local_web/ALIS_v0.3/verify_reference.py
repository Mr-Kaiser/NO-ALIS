"""Exercise every station on a temporary copy; never write to the input folder."""
import argparse
from pathlib import Path
import shutil
import tempfile

from alis.stations import load_repository
from alis.writer import commit, plan_edit, plan_restore, revision


def hashes(root):
    return {str(p.relative_to(root)): revision(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    source = args.root.resolve()
    initial_hashes = hashes(source)
    count = 0
    with tempfile.TemporaryDirectory(prefix='alis-reference-') as temp:
        root = Path(temp)/'preset-loadout'
        shutil.copytree(source, root)
        snapshot = load_repository(root)
        if snapshot.issues:
            raise RuntimeError(f'Reference has {len(snapshot.issues)} validation issues.')
        keys = [w.write_key for w in snapshot.dictionary.weapons]
        for platform, stations in snapshot.station_configs.items():
            for index, files in stations.items():
                if len(files) != 1:
                    raise RuntimeError('Expected exactly one station JSON.')
                original = files[0].path.read_bytes()
                new_key = next(k for k in keys if k not in files[0].allowed_weapons)
                plan = plan_edit(root,platform,index,add=[new_key])
                saved = commit(plan)
                assert saved.backup.read_bytes() == original
                assert files[0].path.read_bytes() == plan.replacement
                assert not commit(plan_edit(root,platform,index,add=[new_key])).changed
                removed = commit(plan_edit(root,platform,index,remove=[new_key],allow_empty=True))
                assert removed.backup.read_bytes() == plan.replacement
                restored = commit(plan_restore(root,platform,index,saved.backup))
                assert files[0].path.read_bytes() == original
                count += 1
        final = load_repository(root)
        assert not final.issues
        for name, checksum in initial_hashes.items():
            assert revision((root/name).read_bytes()) == checksum, name
        assert not list(root.rglob('.alis-*.tmp'))
        assert not (root/'.alis-write.lock').exists()
    assert hashes(source) == initial_hashes, 'Input folder was modified!'
    print(f'PASS: add, idempotent repeat, remove and exact restore on {count} stations.')
    print(f'PASS: {snapshot.preset_count} presets and all original files retain their hashes.')
    print(f'PASS: {len(snapshot.dictionary.weapons)} mounts; {len(final.issues)} validation issues.')
    print('PASS: original input folder unchanged; no temporary files or locks remain.')


if __name__ == '__main__':
    main()
