"""Read category metadata and exercise saves on a temporary full export copy."""
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from alis.categories import OPTIONS, validate_tags
from alis.web import create_app


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '.alis' not in p.relative_to(root).parts}


def main(source):
    source=Path(source).resolve(strict=True);original=hashes(source)
    with tempfile.TemporaryDirectory(prefix='alis-categories-') as folder:
        root=Path(folder)/'preset-loadout';shutil.copytree(source,root)
        app=create_app(root);client=app.test_client();headers={'X-ALIS-Token':app.config['ALIS_TOKEN']}
        data=client.get('/api/bootstrap').get_json();assert len(data['weapons'])==986;assert len(data['platforms'])==32
        for kind,items in [('weapon',data['weapons']),('platform',data['platforms'])]:
            for item in items:validate_tags(kind,item['categories']['tags'])
        print('PASS: valid automatic category groups for all 986 weapons and 32 platforms.')
        revision=data['categories_revision'];samples=['AAM1_single','AAM2_single','AGM1_single',
            'bomb_250_glide_internal','Rocket2_4Pod','UGV1_SAMx1','PB_Side_Rocket_INS']
        saved=[]
        def save(kind,item,tags):
            nonlocal revision
            path=root/'.alis/categories.json';before=path.read_bytes() if path.exists() else b''
            key=item['key'] if kind=='weapon' else item['name']
            response=client.post('/api/categories',headers=headers,json={'kind':kind,'key':key,'tags':tags,
                'identity':item['categories']['identity'],'revision':revision})
            assert response.status_code==200,response.get_json();result=response.get_json();revision=result['revision']
            if before:assert (root/result['backup']).read_bytes()==before
            return result
        for key in samples:
            item=next(w for w in data['weapons'] if w['key']==key);tags=copy.deepcopy(item['categories']['tags']);tags['guidance']=['SARH']
            save('weapon',item,tags);saved.append(('weapon',key,tags))
        for item in data['platforms']:
            tags=copy.deepcopy(item['categories']['tags'])
            if 'UTILITY' not in tags['role']:tags['role'].append('UTILITY')
            save('platform',item,tags);saved.append(('platform',item['name'],tags))
        restarted=create_app(root).test_client().get('/api/bootstrap').get_json()
        for kind,key,tags in saved:
            items=restarted['weapons' if kind=='weapon' else 'platforms'];field='key' if kind=='weapon' else 'name'
            item=next(i for i in items if i[field]==key)
            assert item['categories']['custom'];assert item['categories']['tags']==validate_tags(kind,tags)
        for key in samples:
            item=next(w for w in data['weapons'] if w['key']==key)
            assert not save('weapon',item,None)['categories']['custom']
        assert hashes(root)==original;assert not list((root/'.alis').glob('*.tmp'));assert not (root/'.alis/categories.lock').exists()
        print('PASS: custom labels on 7 representative mounts and all 32 platforms; restart persistence; exact backups; automatic-label restore.')
        print('PASS: all original dictionaries, station JSON and native presets unchanged; temporary-copy checks only.')
    assert hashes(source)==original


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python -m tests.verify_categories PATH_TO_PRESET_LOADOUT')
    main(sys.argv[1])
