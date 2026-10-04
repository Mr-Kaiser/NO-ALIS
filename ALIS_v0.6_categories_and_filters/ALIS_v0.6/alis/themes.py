"""Small, validated theme settings stored alongside other ALIS preferences."""
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

COLOR_KEYS=('bg','panel','panel2','line','text','muted','accent','warning','danger','group')
BUILTINS={
 'alis':{'name':'ALIS Original','colors':dict(zip(COLOR_KEYS,['#0b1016','#101820','#141e28','#25313d','#e0e8ef','#81929f','#77dfd1','#ecb46b','#f79797','#88baff']))},
 'amber':{'name':'Amber Terminal','colors':dict(zip(COLOR_KEYS,['#14110b','#201b12','#2a2316','#493d29','#f2e5c9','#b3a58a','#ffc66d','#e9a854','#ff9696','#a9c4ff']))},
 'midnight':{'name':'Midnight Blue','colors':dict(zip(COLOR_KEYS,['#090e1c','#121a2e','#19243b','#2e405a','#e5eaf5','#95a5c1','#8dbaff','#f1c46e','#ffa0a8','#c3a7ff']))},
 'daylight':{'name':'Daylight','colors':dict(zip(COLOR_KEYS,['#edf1f5','#ffffff','#e4ebf1','#bdcad4','#172632','#536575','#087e70','#8e5c09','#b52d3c','#335eb2']))}
}


def validate(data):
    if not isinstance(data,dict) or not isinstance(data.get('custom'),dict):raise WriteError('Expected theme settings.')
    custom=data['custom']
    if len(custom)>12:raise WriteError('Save at most 12 custom themes.')
    normalized={}
    for key,theme in custom.items():
        if not isinstance(key,str) or not re.fullmatch(r'custom-[a-f0-9]{8,32}',key):raise WriteError('Invalid custom theme ID.')
        if not isinstance(theme,dict):raise WriteError('Invalid custom theme.')
        name=theme.get('name');colors=theme.get('colors')
        if not isinstance(name,str) or not name.strip() or len(name)>60 or any(ord(c)<32 for c in name):raise WriteError('Theme name must have 1–60 characters without control characters.')
        if not isinstance(colors,dict) or set(colors)!=set(COLOR_KEYS) or any(not isinstance(v,str) or not re.fullmatch(r'#[a-fA-F0-9]{6}',v) for v in colors.values()):raise WriteError('Every theme color must use a six-digit hex value.')
        normalized[key]={'name':name.strip(),'colors':{k:v.lower() for k,v in colors.items()}}
    selected=data.get('selected')
    if not isinstance(selected,str) or selected not in {*BUILTINS,*normalized}:raise WriteError('Choose an existing theme.')
    return {'selected':selected,'custom':normalized}


def path_for(root):
    root=Path(root).resolve(strict=True);folder=root/'.alis';path=folder/'ui.json'
    if folder.is_symlink() or path.is_symlink():raise WriteError('ALIS theme settings must not use symbolic links.')
    if folder.exists() and not folder.is_dir():raise WriteError('ALIS settings folder must be a directory.')
    if path.exists() and not path.is_file():raise WriteError('ALIS theme settings must be a regular file.')
    return path


def load(root):
    path=path_for(root);raw=path.read_bytes() if path.exists() else b''
    if len(raw)>65536:raise WriteError('ALIS theme settings file is too large.')
    data={'selected':'alis','custom':{}}
    if raw:
        def pairs(items):
            d={}
            for key,value in items:
                if key in d:raise WriteError(f'Duplicate theme field: {key}')
                d[key]=value
            return d
        try:stored=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
        except (UnicodeError,json.JSONDecodeError) as exc:raise WriteError(f'Invalid theme settings: {exc}') from exc
        if not isinstance(stored,dict) or stored.get('version')!=1:raise WriteError('Unsupported theme settings version.')
        data=validate(stored.get('themes'))
    return data,revision(raw),raw


def inventory(root):
    data,rev,_=load(root)
    return {'state':data,'revision':rev,'builtins':copy.deepcopy(BUILTINS)}


@contextmanager
def lock(folder):
    path=folder/'ui.lock'
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise WriteError('Another theme save is active, or an abandoned ALIS ui.lock exists.') from exc
    try:
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid()))
        yield
    finally:path.unlink()


def save(root,data,expected):
    normalized=validate(data);path=path_for(root);path.parent.mkdir(exist_ok=True)
    with lock(path.parent):
        before,current,raw=load(root)
        if expected!=current:raise ChangedOnDisk('Theme settings changed in another session. Reload data before saving.')
        if before==normalized:return inventory(root),None
        replacement=(json.dumps({'version':1,'themes':normalized},indent=2,ensure_ascii=False)+'\n').encode()
        if len(replacement)>65536:raise WriteError('Theme settings are too large.')
        backup=None
        if raw:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=path.with_name(f'{path.name}.{stamp}.{uuid4().hex[:12]}.bak')
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            if backup.read_bytes()!=raw:raise WriteError('Theme settings backup verification failed.')
        temporary=None
        try:
            fd,name=tempfile.mkstemp(prefix='.ui-',suffix='.tmp',dir=path.parent);temporary=Path(name)
            with os.fdopen(fd,'wb') as f:f.write(replacement);f.flush();os.fsync(f.fileno())
            if temporary.read_bytes()!=replacement:raise WriteError('Theme temporary file verification failed.')
            if load(root)[1]!=current:raise ChangedOnDisk('Theme settings changed during save.')
            os.replace(temporary,path);temporary=None
            if path.read_bytes()!=replacement:raise WriteError('Saved theme verification failed. Inspect its backup.')
            return inventory(root),backup
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
