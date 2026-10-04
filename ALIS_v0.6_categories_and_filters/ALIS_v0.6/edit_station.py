"""ALIS v0.2 station editor. Read-only unless --apply is supplied."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from alis.dictionary import load_dictionary
from alis.writer import WriteError, commit, plan_edit, plan_restore


def main(argv=None):
    parser = argparse.ArgumentParser(description='ALIS v0.2 safe station writer (preview by default).')
    parser.add_argument('root', type=Path, help='Path to preset-loadout.')
    parser.add_argument('--platform', '--aircraft', dest='platform')
    parser.add_argument('--station', type=int, help='Station index from test_parser.py.')
    parser.add_argument('--add', action='append', default=[], metavar='KEY', help='Repeat to add multiple mounts.')
    parser.add_argument('--remove', action='append', default=[], metavar='KEY', help='Repeat to remove multiple mounts.')
    parser.add_argument('--restore', type=Path, metavar='BACKUP', help='Preview or apply an ALIS station backup.')
    parser.add_argument('--allow-empty', action='store_true', help='Permit deliberately emptying allowedWeapons.')
    parser.add_argument('--apply', action='store_true', help='Write the previewed change, with backup and verification.')
    parser.add_argument('--expect-revision', help='Optional SHA-256 revision from an earlier preview.')
    parser.add_argument('--find-weapon', metavar='TEXT', help='Search mount keys, display names, owners and notes.')
    parser.add_argument('--json', action='store_true', help='Output a machine-readable result.')
    args = parser.parse_args(argv)
    try:
        if args.find_weapon is not None:
            if args.add or args.remove or args.restore or args.apply:
                parser.error('--find-weapon cannot be combined with write options.')
            term = args.find_weapon.casefold()
            matches = [w for w in load_dictionary(args.root).weapons
                       if term in ' '.join((w.json_key, w.asset_name, w.display_name, w.owner, w.note)).casefold()]
            records = [dict(key=w.json_key, write_key=w.write_key, display_name=w.display_name,
                            owner=w.owner, note=w.note) for w in matches]
            if args.json:
                print(json.dumps(records, indent=2))
            else:
                for w in records:
                    print(f"{w['key']} | {w['display_name']} | {w['owner']}")
                    if w['note']:
                        print(f"  {w['note']} | write key: {w['write_key']}")
                print(f'{len(matches)} mount(s) found.')
            return 0
        if args.platform is None or args.station is None:
            parser.error('--platform and --station are required for station editing.')
        if args.restore and (args.add or args.remove or args.allow_empty or args.expect_revision):
            parser.error('--restore cannot be combined with edit options.')
        if args.restore:
            plan = plan_restore(args.root, args.platform, args.station, args.restore)
        else:
            plan = plan_edit(args.root, args.platform, args.station, add=args.add, remove=args.remove,
                             allow_empty=args.allow_empty, expected_revision=args.expect_revision)
        result = plan.summary()
        result['mode'] = 'APPLY' if args.apply else 'PREVIEW'
        if args.apply:
            saved = commit(plan)
            result['backup'] = str(saved.backup) if saved.backup else None
            result['saved_revision'] = saved.revision
            result['verified'] = True
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"ALIS v0.2 // {result['mode']}")
            print(f"Station: {plan.path}")
            print(f"Allowed mounts: {len(plan.before)} -> {len(plan.after)}")
            for key in result['removed']:
                print(f'  - {key}')
            for key in result['added']:
                print(f'  + {key}')
            for old, new in plan.normalized:
                print(f'  Resolved stale/asset alias: {old} -> {new}')
            if plan.restoring:
                print(f'Restore source: {plan.restoring}')
            print(f'Revision: {plan.expected_revision}')
            if args.apply:
                if result['backup']:
                    print(f"Backup: {result['backup']}")
                    print('Saved and verified.')
                else:
                    print('Already matches; no files changed and no backup created.')
            elif plan.changed:
                print('Preview only. Repeat with --apply to save.')
            else:
                print('Already matches; no change needed.')
        return 0
    except (WriteError, ValueError, OSError) as exc:
        if args.json:
            print(json.dumps({'error': str(exc)}), file=sys.stderr)
        else:
            print(f'ALIS refused or could not complete the operation: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
