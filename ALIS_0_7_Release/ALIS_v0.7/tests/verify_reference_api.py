"""Check the web API on a temporary copy of a complete reference export."""
import argparse
import copy
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote

from alis.stations import load_repository
from alis.web import create_app
from alis.writer import revision


def hashes(root):
    return {p.relative_to(root):revision(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    source=parser.parse_args().root.resolve();original=hashes(source)
    game={p:value for p,value in original.items() if p.parts[0]!='.alis'}
    with tempfile.TemporaryDirectory(prefix='alis-api-') as temp:
        root=Path(temp)/'preset-loadout';shutil.copytree(source,root)
        app=create_app(root);client=app.test_client();headers={'X-ALIS-Token':app.config['ALIS_TOKEN']}
        def get(url):
            result=client.get(url);assert result.status_code==200,result.get_json();return result.get_json()
        def post(url,data):
            result=client.post(url,json=data,headers=headers)
            assert result.status_code==200,result.get_json();return result.get_json()
        inventory=get('/api/bootstrap');settings_revision=inventory['profiles_revision']
        stock=[p for p in inventory['platforms'] if p['profile']['source']=='schematic']
        for p in stock:
            assert not p['profile']['stale'],p['name']
            assert not p['profile']['unmapped'],p['name']
            assert not p['profile']['verified'],p['name']
        count=0
        for p in inventory['platforms']:
            api_base=f'/api/platforms/{quote(p["name"],safe="")}'
            for meta in p['stations']:
                station_url=api_base+f'/stations/{meta["index"]}'
                station=get(station_url);path=root/station['path'];raw=path.read_bytes()
                key=next(w['write_key'] for w in inventory['weapons'] if w['write_key'] not in station['allowed'])
                preview=post(station_url+'/preview',{'revision':station['revision'],'add':[key]})
                assert path.read_bytes()==raw
                saved=post('/api/commit',{'ticket':preview['ticket']});assert saved['verified'] and saved['changed']
                assert (root/saved['backup']).read_bytes()==raw
                restore=post(station_url+'/preview',{'revision':saved['station']['revision'],'restore':Path(saved['backup']).name})
                post('/api/commit',{'ticket':restore['ticket']});assert path.read_bytes()==raw;count+=1
            # Also map a station for an unknown modded platform without guessing a name.
            profile={key:copy.deepcopy(p['profile'][key]) for key in ['display_name','silhouette','image','verified','stations']}
            if 'image_crop' in p['profile']:profile['image_crop']=copy.deepcopy(p['profile']['image_crop'])
            if not profile['stations']:
                s=p['stations'][0];profile['stations'][str(s['index'])]={'expected_name':s['name'],'points':[[0.5,0.5]]}
            profile['display_name']=p['display_name']+' API test'
            result=post(api_base+'/profile',{'revision':settings_revision,'profile':profile})
            settings_revision=result['revision'];assert result['profile']['display_name']==profile['display_name']
            assert result['profile']['stations']==profile['stations']
        restarted=create_app(root).test_client().get('/api/bootstrap').get_json()
        assert all(p['display_name'].endswith(' API test') for p in restarted['platforms'])
        assert restarted['profiles_revision']==settings_revision
        for name,value in game.items():assert revision((root/name).read_bytes())==value,name
        snapshot=load_repository(root);assert not snapshot.issues
        assert not (root/'.alis-write.lock').exists();assert not (root/'.alis/profiles.lock').exists()
    assert hashes(source)==original,'Input folder was modified'
    print(f'PASS: API preview/save/exact restore on {count} stations; {len(stock)} complete stock schematic profiles.')
    print(f'PASS: profile save and restart persistence for {len(inventory["platforms"])} platforms.')
    print(f'PASS: all game file hashes and {snapshot.preset_count} presets preserved; input folder unchanged; zero validation issues.')


if __name__=='__main__':main()
