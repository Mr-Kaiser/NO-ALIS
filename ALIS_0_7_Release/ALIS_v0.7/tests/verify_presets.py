"""Exercise every supplied native preset on a temporary copy."""
import argparse
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote

from alis.presets import decode, selections
from alis.stations import load_repository
from alis.themes import BUILTINS
from alis.web import create_app
from alis.writer import revision


def hashes(root):return {p.relative_to(root):revision(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    source=parser.parse_args().root.resolve();original=hashes(source);copies=noops=flagged=issues_count=0
    with tempfile.TemporaryDirectory(prefix='alis-presets-') as temporary:
        root=Path(temporary)/'preset-loadout';shutil.copytree(source,root)
        app=create_app(root);client=app.test_client();headers={'X-ALIS-Token':app.config['ALIS_TOKEN']}
        def get(url):
            r=client.get(url);assert r.status_code==200,r.get_json();return r.get_json()
        def post(url,body):
            r=client.post(url,json=body,headers=headers);assert r.status_code==200,r.get_json();return r.get_json()
        initial=get('/api/bootstrap')
        for platform in initial['platforms']:
            url=f'/api/platforms/{quote(platform["name"],safe="")}/presets';catalog=get(url)
            for file in catalog['files']:
                loaded=get(url+'/'+quote(file['name'],safe=''));raw=(root/platform['name']/file['filename']).read_bytes()
                chosen=loaded['selections'].copy()
                if loaded['issues']:
                    flagged+=1
                    for row in catalog['stations']:
                        if chosen[str(row['index'])] and chosen[str(row['index'])] not in row['allowed']:
                            chosen[str(row['index'])]='';issues_count+=1
                else:
                    body=dict(name=loaded['name'],source=loaded['name'],source_revision=loaded['revision'],revision=loaded['revision'],
                              catalog_revision=catalog['catalog_revision'],fuel=loaded['fuel'],livery=loaded['livery'],selections=chosen)
                    preview=post(url+'/preview',body);result=post('/api/preset-commit',{'ticket':preview['ticket']})
                    assert not result['changed'] and result['backup'] is None;noops+=1
                # Invalid selections are cleared only inside this verifier's temporary copy.
                body=dict(name='ALIS verify '+loaded['name'],source=loaded['name'],source_revision=loaded['revision'],revision=None,
                          catalog_revision=catalog['catalog_revision'],fuel=loaded['fuel'],livery=loaded['livery'],selections=chosen)
                preview=post(url+'/preview',body);result=post('/api/preset-commit',{'ticket':preview['ticket']})
                path=root/platform['name']/result['preset']['filename'];copy_raw=path.read_bytes();native=decode(copy_raw)
                assert selections(native,catalog['stations'])==chosen
                source_data=decode(raw)
                for key,value in source_data.items():
                    if key not in {'Stations','Hardpoints'}:assert native[key]==value,(path,key)
                if not loaded['issues']:assert copy_raw==raw
                fuel=.9 if native['Fuel']!=.9 else .8
                body.update(name=result['preset']['name'],source=result['preset']['name'],source_revision=result['preset']['revision'],revision=result['preset']['revision'],fuel=fuel)
                preview=post(url+'/preview',body);updated=post('/api/preset-commit',{'ticket':preview['ticket']})
                assert (root/updated['backup']).read_bytes()==copy_raw;assert decode(path.read_bytes())['Fuel']==fuel;copies+=1
        theme_revision=initial['themes']['revision']
        for selected in BUILTINS:
            result=post('/api/themes',{'revision':theme_revision,'state':{'selected':selected,'custom':{}}});theme_revision=result['themes']['revision']
        restarted=create_app(root).test_client().get('/api/bootstrap').get_json()
        assert restarted['themes']['state']['selected']=='daylight'
        for path,value in original.items():
            if path.parts[0]!='.alis':assert revision((root/path).read_bytes())==value,path
        final=load_repository(root);assert not final.issues
        assert not (root/'.alis-write.lock').exists();assert not (root/'.alis/ui.lock').exists();assert not list(root.rglob('.alis-preset-*.tmp'))
    assert hashes(source)==original,'Original input folder changed.'
    print(f'PASS: read/copy/review/create/update/exact backup for {copies} native presets; {noops} valid originals were byte-exact no-ops.')
    print(f'PASS: {issues_count} unavailable selections flagged across {flagged} existing presets; originals untouched.')
    print(f'PASS: all four theme presets and restart persistence; all original hashes unchanged; zero validation issues.')


if __name__=='__main__':main()
