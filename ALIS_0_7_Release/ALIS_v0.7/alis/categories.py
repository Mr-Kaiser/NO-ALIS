"""UI-only category labels. Dictionary names are hints, never compatibility rules."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from .writer import ChangedOnDisk, WriteError, revision

OPTIONS = {
    'weapon': {
        'role': {'A2A':'Air-to-air', 'A2G':'Air-to-ground', 'ASHM':'Anti-ship',
                 'ARM':'Anti-radiation', 'SAM':'Surface-to-air', 'G2G':'Ground-to-ground',
                 'REC':'Reconnaissance', 'EW':'Electronic warfare', 'UTIL':'Utility'},
        'type': {'MIS':'Missile', 'BMB':'Bomb', 'RKT':'Rocket', 'GUN':'Gun / ammunition',
                 'DEW':'Directed energy', 'POD':'Equipment pod', 'FUEL':'Fuel', 'CARGO':'Cargo / vehicle',
                 'TORP':'Torpedo', 'SENSOR':'Sensor / reconnaissance'},
        'guidance': {'IR':'Infrared', 'ARH':'Active radar homing', 'SARH':'Semi-active radar homing',
                     'OPT':'Optical', 'LAS':'Laser guided', 'PRH':'Passive radar homing',
                     'INS':'Inertial', 'GPS':'Satellite guided', 'UNG':'Unguided'},
    },
    'platform': {
        'type': {'FW':'Fixed wing', 'VTOL':'VTOL', 'HELO':'Helicopter', 'GROUND':'Ground vehicle', 'SHIP':'Ship'},
        'role': {'FIGHTER':'Fighter', 'ATTACK':'Attack', 'BOMBER':'Bomber', 'MULTI':'Multirole',
                 'EW':'Electronic warfare', 'TRANSPORT':'Transport', 'UTILITY':'Utility', 'TRAINER':'Trainer'},
    },
}

# Guidance is restricted to recognizable stock model names. Sources and caveats
# live in CATEGORY_NOTES.md; real-world missile names do not establish mod seekers.
STOCK_GUIDANCE = {
    'MMR-S3':'IR', 'IRM-S1':'IR', 'IRM-S2':'IR', 'AAM-29 Scythe':'ARH',
    'AAM-36 Scimitar':'ARH', 'AGM-48':'OPT', 'AGM-68':'OPT', 'ATP-1':'OPT',
    'AT-145':'OPT', 'PAB-80LR':'OPT', 'PAB-250LR':'OPT', 'GBM-500LR':'OPT',
    'PAB-125':'OPT', 'PAB-250':'OPT', 'GPO-500':'OPT', 'Eyeball Mk.II':'OPT',
    'AGR-18 Lynchpin':'LAS', 'AGR-24 Kingpin':'LAS',
}
STOCK_PLATFORMS = {
    'CAS1':(['FW'],['ATTACK']), 'COIN':(['FW'],['ATTACK']),
    'trainer':(['FW'],['TRAINER']), 'VTOLTrainer1':(['FW','VTOL'],['MULTI','TRAINER']),
    'Fighter1':(['FW'],['FIGHTER']), 'SmallFighter1':(['FW','VTOL'],['FIGHTER']),
    'Multirole1':(['FW'],['MULTI']), 'EW1':(['FW','VTOL'],['EW']),
    'Darkreach':(['FW'],['BOMBER']), 'FastBomber1':(['FW'],['BOMBER']),
    'AttackHelo1':(['HELO'],['ATTACK']), 'UtilityHelo1':(['HELO'],['UTILITY','TRANSPORT']),
    'QuadVTOL1':(['VTOL'],['TRANSPORT']),
}


def empty(kind):
    return {axis:[] for axis in OPTIONS[kind]}


def weapon_defaults(w):
    tags=empty('weapon');key=w.json_key.lower();name=w.display_name.lower()
    text=f'{key} {name}'
    def add(axis,*values):
        for value in values:
            if value not in tags[axis]:tags[axis].append(value)
    # Entire carried vehicles and supply payloads take precedence over SAM/gun
    # words inside their names. A laser weapon is not laser-guided ammunition.
    cargo = (bool(re.search(r'(?:x\d+$)',key)) and bool(re.search(r'(?:^|_)(?:6x6_|lighttruck|ugv|samturret|hlt-|mbt|afv|spaag|crvl|frcv)',key))) or bool(re.search(r'cargo|pallet|container|infantry|troops|supply|ammo box',text))
    if 'fuel' in text or 'droptank' in text or 'drop tank' in text:
        add('type','FUEL');add('role','UTIL')
    elif cargo:
        add('type','CARGO');add('role','UTIL')
    elif re.search(r'eyeball|scanner|recon',text):
        add('role','REC');add('type','SENSOR')
        if re.match(r'eyeball mk\.ii(?:$|\s+x\d+\b)',name):add('type','MIS')
    elif re.search(r'jamming|jammer|ecm',text):
        add('type','POD');add('role','EW')
    elif re.search(r'flare|smoke|radome|radar pod|targeting pod',text):
        add('type','POD');add('role','UTIL')
    elif re.search(r'torpedo',text):
        add('type','TORP');add('role','ASHM')
    elif re.search(r'laser|railgun',text) and not re.search(r'rocket|missile|bomb|\bagm|\baam|\baim',text):
        add('type','DEW')
    elif re.search(r'gun|cannon|turret|howitzer|ciws|\d+mm.*(?:round|\b(?:ap|he|apds|aphe|ahead)\b)',text):
        add('type','GUN')
    elif re.search(r'bomb|\bpab[-_]|\bgpo[-_]|\bgbm[-_]|\bcbo[-_]|\bgbu[-_]|\bmk[- ]?8[234]\b',text):
        add('type','BMB');add('role','A2G')
    elif re.search(r'rocket|\bagr[-_]|\bmlrs',text):
        add('type','RKT');add('role','A2G')
    elif re.search(r'^(?:aam\d|irms?\d|aim[-_]?\d|meridianirm)|\baam[-_\d]|\baim[- ]?\d|\birm[-_]|\bmmr[-_]|missile|\bagm[-_\d]|\batgm|_atgm|\bat[-_]145|\batp[-_]|\balm[-_]c450|\balnd[-_]4|\barm\d|\barad[-_]|ashm|cruise|ballistic|\btbm\b|\bsam\b|_sam_',text):
        add('type','MIS')
        if re.search(r'\bsam\b|_sam_',text):add('role','SAM')
        elif re.search(r'^(?:aam\d|irms?\d|aim[-_]?\d|meridianirm)|\baam[-_\d]|\baim[- ]?\d|\birm[-_]|\bmmr[-_]|air.to.air',text):add('role','A2A')
        elif re.search(r'\bagm[-_\d]|\batgm|_atgm|\bat[-_]145|\batp[-_]|\balm[-_]c450|\balnd[-_]4|\barm\d|\barad[-_]|ashm|cruise|ballistic|\btbm\b|air.to.ground',text):add('role','A2G')
        if re.search(r'ashm|anti.ship',text):add('role','ASHM')
        if re.search(r'\barm\d|\barad[-_]|anti.radiation',text):add('role','ARM')
    source='Name / key hints'
    if set(tags['type']) & {'MIS','BMB','RKT'}:
        for model,guidance in STOCK_GUIDANCE.items():
            if re.match(re.escape(model.lower())+r'(?:$|\s+x\d+\b|\s*\()',name):
                add('guidance',guidance);source='Stock model labels + name / key hints';break
        # Explicit seeker words in mod keys are useful hints; AIM-120 or R-27
        # alone deliberately does not imply ARH/SARH/IR.
        for pattern,tag in [(r'\bsarh\b|_sarh','SARH'),(r'\barh\b|_arh','ARH'),
                            (r'infrared|\birm[-_]|_ir(?:_|\d|$)','IR'),
                            (r'optical|_opt(?:_|$)','OPT'),(r'laser','LAS'),
                            (r'(?:^|[_\W])ins(?:[_\W]|$)','INS'),(r'\bgps\b|_gps','GPS'),
                            (r'unguided','UNG')]:
            if re.search(pattern,text):add('guidance',tag)
    return {'tags':tags,'source':source if any(tags.values()) else 'Unclassified'}


def platform_defaults(p):
    tags=empty('platform');name=p.internal_name;lower=name.lower()
    if name in STOCK_PLATFORMS:
        tags['type'],tags['role']=copy.deepcopy(STOCK_PLATFORMS[name])
        return {'tags':tags,'source':'Stock platform labels'}
    if re.search(r'helo|helicopter',lower):tags['type']=['HELO']
    elif 'vtol' in lower:tags['type']=['VTOL']
    elif re.search(r'^kar_(?:ugv|afv|lcv|tonk|truk)|ugv|tank|truck|tonk',lower):tags['type']=['GROUND']
    elif re.search(r'landingkraft|ship|boat',lower):tags['type']=['SHIP']
    elif re.search(r'fighter|interceptor|attacker|cargoplane|bomber',lower):tags['type']=['FW']
    for pattern,tag in [(r'fighter|interceptor','FIGHTER'),(r'attacker|attackhelo','ATTACK'),
                        (r'bomber','BOMBER'),(r'cargo','TRANSPORT'),(r'trainer','TRAINER')]:
        if re.search(pattern,lower):tags['role'].append(tag)
    return {'tags':tags,'source':'Name / key hints' if any(tags.values()) else 'Unclassified'}


def identity(kind,item):
    if kind=='platform':return item.internal_name
    return revision(json.dumps([item.owner,item.json_key,item.asset_name,item.display_name],ensure_ascii=False).encode())


def validate_tags(kind,tags):
    if not isinstance(tags,dict) or set(tags)!=set(OPTIONS[kind]):raise WriteError('Supply every category group.')
    result={}
    for axis,options in OPTIONS[kind].items():
        values=tags[axis]
        if not isinstance(values,list) or any(not isinstance(v,str) or v not in options for v in values) or len(set(values))!=len(values):raise WriteError(f'Invalid {axis} categories.')
        result[axis]=[v for v in options if v in values]
    return result


def path_for(root):
    path=Path(root).resolve(strict=True)/'.alis'/'categories.json'
    if path.parent.is_symlink() or path.is_symlink():raise WriteError('Category settings must not use symbolic links.')
    if path.parent.exists() and not path.parent.is_dir():raise WriteError('ALIS settings folder must be a directory.')
    if path.exists() and not path.is_file():raise WriteError('Category settings must be a regular file.')
    return path


def load(root):
    path=path_for(root);raw=path.read_bytes() if path.exists() else b''
    if len(raw)>2*1024*1024:raise WriteError('Category settings are too large.')
    store={'version':1,'weapon':{},'platform':{}}
    if raw:
        def pairs(items):
            data={}
            for key,value in items:
                if key in data:raise WriteError(f'Duplicate category field: {key}')
                data[key]=value
            return data
        try:store=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
        except (UnicodeError,json.JSONDecodeError) as exc:raise WriteError(f'Invalid category settings: {exc}') from exc
        if not isinstance(store,dict) or set(store)!={'version','weapon','platform'} or type(store['version']) is not int or store['version']!=1:raise WriteError('Unsupported category settings format.')
        for kind in OPTIONS:
            if not isinstance(store[kind],dict) or len(store[kind])>10000:raise WriteError('Invalid category overrides.')
            for key,value in store[kind].items():
                if not key or not isinstance(value,dict) or set(value)!={'identity','tags'} or not isinstance(value['identity'],str):raise WriteError('Invalid category override.')
                value['tags']=validate_tags(kind,value['tags'])
    return store,revision(raw),raw


def labels(kind,item,store):
    automatic=weapon_defaults(item) if kind=='weapon' else platform_defaults(item)
    key=item.json_key if kind=='weapon' else item.internal_name
    override=store[kind].get(key);valid=bool(override and override['identity']==identity(kind,item))
    return {**automatic,'tags':copy.deepcopy(override['tags']) if valid else automatic['tags'],
            'source':'Custom labels' if valid else automatic['source'], 'automatic':automatic['tags'],
            'custom':valid,'identity':identity(kind,item),'stale_override':bool(override and not valid)}


@contextmanager
def lock(folder):
    path=folder/'categories.lock'
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise WriteError('Another category save is active, or an abandoned categories.lock exists.') from exc
    try:
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid()))
        yield
    finally:path.unlink()


def save(root,kind,item,tags,expected,expected_identity):
    if expected_identity!=identity(kind,item):raise ChangedOnDisk('Dictionary item changed. Reload data before labeling it.')
    normalized=validate_tags(kind,tags) if tags is not None else None
    path=path_for(root);path.parent.mkdir(exist_ok=True)
    with lock(path.parent):
        store,current,raw=load(root)
        if expected!=current:raise ChangedOnDisk('Categories changed in another session. Reload data before saving.')
        before=copy.deepcopy(store);key=item.json_key if kind=='weapon' else item.internal_name
        if normalized is None:store[kind].pop(key,None)
        else:store[kind][key]={'identity':identity(kind,item),'tags':normalized}
        if before==store:return labels(kind,item,store),current,None
        replacement=(json.dumps(store,indent=2,ensure_ascii=False)+'\n').encode()
        if len(replacement)>2*1024*1024:raise WriteError('Category settings are too large.')
        backup=None
        if raw:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=path.with_name(f'{path.name}.{stamp}.{uuid4().hex[:12]}.bak')
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            if backup.read_bytes()!=raw:raise WriteError('Category backup verification failed.')
        temporary=None
        try:
            fd,name=tempfile.mkstemp(prefix='.categories-',suffix='.tmp',dir=path.parent);temporary=Path(name)
            with os.fdopen(fd,'wb') as f:f.write(replacement);f.flush();os.fsync(f.fileno())
            if temporary.read_bytes()!=replacement:raise WriteError('Category temporary file verification failed.')
            if load(root)[1]!=current:raise ChangedOnDisk('Categories changed during save.')
            os.replace(temporary,path);temporary=None
            if path.read_bytes()!=replacement:raise WriteError('Saved category verification failed. Inspect its backup.')
            return labels(kind,item,store),revision(replacement),backup
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
