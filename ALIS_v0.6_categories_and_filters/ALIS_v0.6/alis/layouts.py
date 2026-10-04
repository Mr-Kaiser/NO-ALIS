"""ALIS display metadata and visual layouts, kept separate from injector rules."""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import copy
import json
import math
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from .writer import ChangedOnDisk, WriteError, revision

SHAPES = {'brawler','jet','canard','delta','bomber','swingwing','twinboom',
          'helicopter','quadvtol','transport','ground','ship','blank'}
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_STORE_BYTES = 12 * 1024 * 1024


def _decode(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:raise WriteError(f'Duplicate profile field: {key}')
            result[key] = value
        return result
    try:
        data = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise WriteError(f'Invalid ALIS profile file: {exc}') from exc
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('platforms'),dict):
        raise WriteError('ALIS profile file has an unsupported format.')
    return data


def _store_path(root):
    root = Path(root).resolve(strict=True)
    folder = root/'.alis'
    path = folder/'platforms.json'
    if folder.is_symlink() or path.is_symlink():
        raise WriteError('ALIS settings paths must not be symbolic links.')
    if path.exists() and (not path.is_file() or not path.resolve().is_relative_to(root)):
        raise WriteError('ALIS settings must be a regular file inside the selected folder.')
    return path


def load_store(root):
    path = _store_path(root)
    raw = path.read_bytes() if path.exists() else b''
    if len(raw)>MAX_STORE_BYTES:raise WriteError('ALIS profile file is too large.')
    data = _decode(raw) if raw else {'version':1,'platforms':{}}
    return data,revision(raw),raw


def defaults():
    path = Path(__file__).resolve().parent.parent/'config'/'platforms.json'
    return _decode(path.read_bytes())['platforms']


def validate_profile(data, stations):
    if not isinstance(data,dict):raise WriteError('Expected a platform profile object.')
    name=data.get('display_name','')
    if not isinstance(name,str) or not name.strip() or len(name)>120 or any(ord(c)<32 for c in name):
        raise WriteError('Display name must contain 1–120 characters, without control characters.')
    shape=data.get('silhouette','blank')
    if not isinstance(shape,str) or shape not in SHAPES:raise WriteError('Choose one of the built-in silhouettes.')
    verified=data.get('verified',False)
    if type(verified) is not bool:raise WriteError('verified must be a boolean.')
    image=data.get('image')
    if image is not None:
        if not isinstance(image,str):raise WriteError('Image must be a PNG/JPEG/WebP data URL.')
        prefix,separator,encoded=image.partition(',')
        if not separator or prefix not in {'data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'}:
            raise WriteError('Use a PNG, JPEG or WebP image. SVG and external image URLs are not accepted.')
        if len(encoded)>MAX_IMAGE_BYTES*4//3+8:raise WriteError('Image must be at most 2 MiB.')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError) as exc:raise WriteError('Invalid image encoding.') from exc
        valid=(prefix=='data:image/png;base64' and raw.startswith(b'\x89PNG\r\n\x1a\n') or
               prefix=='data:image/jpeg;base64' and raw.startswith(b'\xff\xd8\xff') or
               prefix=='data:image/webp;base64' and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP')
        if not valid or not raw or len(raw)>MAX_IMAGE_BYTES:raise WriteError('Image content does not match its PNG/JPEG/WebP type.')
    markers=data.get('stations',{})
    if not isinstance(markers,dict):raise WriteError('stations must be an object.')
    known={str(s.station_index):s for s in stations}
    validated={}
    total=0
    for index, marker in markers.items():
        if index not in known:raise WriteError(f'Unknown station index: {index}')
        if not isinstance(marker,dict):raise WriteError('Expected a station marker object.')
        expected=marker.get('expected_name')
        if expected!=known[index].station_name:raise WriteError(f'Station {index} metadata changed. Reload its layout.')
        points=marker.get('points')
        if not isinstance(points,list) or not 1<=len(points)<=16:raise WriteError('Each mapped station needs 1–16 marker points.')
        result=[]
        for point in points:
            if not isinstance(point,list) or len(point)!=2:raise WriteError('Marker points must be [x,y] pairs.')
            if any(type(v) not in {int,float} or not 0<=v<=1 or not math.isfinite(v) for v in point):
                raise WriteError('Marker coordinates must be finite numbers between 0 and 1.')
            result.append(point)
        total+=len(result)
        validated[index]={'expected_name':expected,'points':result}
    if total>256:raise WriteError('Too many marker points in one layout.')
    return {'display_name':name.strip(),'silhouette':shape,'verified':verified,'image':image,'stations':validated}


def profile_for(platform, stations, store):
    builtins=defaults()
    base=builtins.get(platform)
    if base is None:
        base=next((p for name,p in builtins.items() if name.casefold()==platform.casefold()),None)
    custom=store['platforms'].get(platform)
    profile=copy.deepcopy(custom if custom is not None else base)
    if profile is None:
        profile={'display_name':platform,'silhouette':'blank','verified':False,'stations':{},'image':None}
    source='custom' if custom is not None else 'schematic' if base else 'unmapped'
    # A changed game/mod station is returned as unmapped rather than attached
    # to an old marker that now points at a different station name.
    known={str(s.station_index):s.station_name for s in stations}
    if not isinstance(profile,dict) or not isinstance(profile.get('stations',{}),dict):
        raise WriteError('Invalid ALIS platform profile.')
    if any(not isinstance(marker,dict) for marker in profile.get('stations',{}).values()):
        raise WriteError('Invalid ALIS station marker profile.')
    markers={index:marker for index,marker in profile.get('stations',{}).items()
             if index in known and marker.get('expected_name')==known[index]}
    stale=len(markers)!=len(profile.get('stations',{}))
    profile['stations']=markers
    if stale:profile['verified']=False
    profile=validate_profile(profile,stations)
    return {**profile,'source':source,'stale':stale,
            'unmapped':[s.station_index for s in stations if str(s.station_index) not in markers]}


@contextmanager
def _profile_lock(folder):
    lock=folder/'profiles.lock'
    try:descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise WriteError('Another layout save is active, or a stale ALIS profile lock exists.') from exc
    try:
        with os.fdopen(descriptor,'w') as f:f.write(str(os.getpid()))
        yield
    finally:lock.unlink()


def save_profile(root, platform, stations, data, expected_revision):
    profile=validate_profile(data,stations)
    path=_store_path(root)
    path.parent.mkdir(exist_ok=True)
    with _profile_lock(path.parent):
        store,current,raw=load_store(root)
        if expected_revision!=current:raise ChangedOnDisk('ALIS layouts changed in another session. Reload before saving.')
        previous=copy.deepcopy(store)
        store['platforms'][platform]=profile
        replacement=(json.dumps(store,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
        if len(replacement)>MAX_STORE_BYTES:raise WriteError('Combined ALIS profiles are too large. Use smaller images.')
        if previous==store:return profile,current,None
        backup=None
        if raw:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup=path.with_name(f'{path.name}.{stamp}.{uuid4().hex[:12]}.bak')
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            if backup.read_bytes()!=raw:raise WriteError('ALIS profile backup could not be verified.')
        temporary=None
        try:
            descriptor,name=tempfile.mkstemp(prefix='.profiles-',suffix='.tmp',dir=path.parent)
            temporary=Path(name)
            with os.fdopen(descriptor,'wb') as f:f.write(replacement);f.flush();os.fsync(f.fileno())
            if _decode(temporary.read_bytes())!=store:raise WriteError('Profile file verification failed.')
            if load_store(root)[1]!=current:raise ChangedOnDisk('ALIS profiles changed during save.')
            os.replace(temporary,path);temporary=None
            written=path.read_bytes()
            if written!=replacement:raise WriteError('Saved profile could not be verified. Inspect the ALIS settings backup.')
            return profile,revision(written),backup
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
