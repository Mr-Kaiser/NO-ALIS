"""Native loadout presets: strict parsing, reviewed writes and exact backups."""
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from .dictionary import load_dictionary
from .writer import ChangedOnDisk, WriteError, SaveResult, _lock, _safe_file, _target, _write_key, revision

MAX_PRESET_BYTES=1024*1024


def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise WriteError(f'Duplicate preset field: {key}')
            result[key]=value
        return result
    def invalid(value):raise WriteError(f'Nonstandard preset JSON value: {value}')
    try:data=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)
    except (UnicodeError,json.JSONDecodeError) as exc:raise WriteError(f'Invalid preset JSON: {exc}') from exc
    if not isinstance(data,dict):raise WriteError('Preset must be a JSON object.')
    fuel=data.get('Fuel');livery=data.get('Livery')
    if type(fuel) not in {int,float} or not 0<=fuel<=1 or not math.isfinite(fuel):raise WriteError('Preset fuel must be between 0 and 1.')
    if not isinstance(livery,str):raise WriteError('Preset livery must be a string.')
    for field in ['Stations','Hardpoints']:
        if not isinstance(data.get(field),list) or any(not isinstance(v,str) for v in data[field]):raise WriteError(f'{field} must be an array of strings.')
    return data


def filename(name):
    if not isinstance(name,str):raise WriteError('Enter a preset name.')
    if name.endswith('.preset'):name=name[:-7]
    if not name or len(name)>100 or name!=name.strip() or name.endswith('.') or any(ord(c)<32 or c in '<>:"/\\|?*' for c in name):
        raise WriteError('Use a preset name of 1–100 characters without path separators or Windows filename symbols.')
    if name in {'.','..'} or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',name.split('.')[0],re.I):raise WriteError('That preset name is reserved by Windows.')
    return name+'.preset'


def platform_folder(root,platform):
    root=Path(root).resolve(strict=True);dictionary=load_dictionary(root)
    if platform not in dictionary.platforms:raise WriteError('Unknown platform.')
    if not isinstance(platform,str) or Path(platform).name!=platform or '/' in platform or '\\' in platform or platform in {'.','..'}:raise WriteError('Unsafe platform ID.')
    folder=root/platform
    if folder.is_symlink() or not folder.is_dir() or not folder.resolve().is_relative_to(root):raise WriteError('Platform must be a regular folder beneath preset-loadout.')
    return root,folder,dictionary


def context(root,platform):
    root=Path(root).resolve(strict=True)
    dependencies={root/name:(root/name).read_bytes() for name in ['hardpointdictionary_mounts.csv','hardpointdictionary_stations.csv']}
    root,folder,dictionary=platform_folder(root,platform)
    stations=dictionary.platforms[platform].sorted_stations()
    if [s.station_index for s in stations]!=list(range(len(stations))) or any('=' in s.station_name for s in stations):
        raise WriteError('Preset editing requires unique station indexes starting at zero and station names without =.')
    rows=[]
    for s in stations:
        _,path,_=_target(root,platform,s.station_index);raw=path.read_bytes()
        from .writer import _object
        allowed=_object(raw)['allowedWeapons'];dependencies[path]=raw
        canonical=[];unresolved=[]
        for key in allowed:
            try:resolved=_write_key(dictionary,key)
            except WriteError:unresolved.append(key)
            else:
                if resolved not in canonical:canonical.append(resolved)
        rows.append(dict(index=s.station_index,name=s.station_name,hardpoints=s.hardpoint_count,
                         precluding=list(s.precluding),allowed=canonical,unresolved=unresolved))
    for path,raw in dependencies.items():
        if _safe_file(root,path).read_bytes()!=raw:raise ChangedOnDisk('Preset catalog changed while loading. Reload it.')
    catalog_revision=revision(json.dumps([(str(p.relative_to(root)),revision(raw)) for p,raw in sorted(dependencies.items())]).encode())
    return root,folder,dictionary,rows,dependencies,catalog_revision


def selections(data,rows):
    if len(data['Stations'])!=len(rows) or len(data['Hardpoints'])!=len(rows):raise WriteError('Preset station count does not match the current dictionary.')
    result={}
    for row,entry,key in zip(rows,data['Stations'],data['Hardpoints']):
        name,separator,value=entry.partition('=')
        if not separator or name!=row['name'] or value!=key:raise WriteError('Preset station order/names or hardpoint arrays do not match. Inspect the file before editing.')
        result[str(row['index'])]=key
    return result


def selection_issues(chosen,rows):
    issues=[]
    for row in rows:
        key=chosen.get(str(row['index']),'')
        if key and key not in row['allowed']:issues.append(f'Station {row["index"]} ({row["name"]}): {key} is not available in its whitelist.')
        if key:
            for other in row['precluding']:
                if chosen.get(str(other)):issues.append(f'Station {row["index"]} precludes occupied station {other}. Clear one selection.')
    return list(dict.fromkeys(issues))


def read_file(root,folder,name):
    path=folder/filename(name);path=_safe_file(root,path);raw=path.read_bytes()
    if len(raw)>MAX_PRESET_BYTES:raise WriteError('Preset file is too large.')
    return path,raw,decode(raw)


def list_presets(root,platform):
    root,folder,_,rows,_,rev=context(root,platform)
    files=[]
    for p in sorted(folder.glob('*.preset'),key=lambda p:p.name.casefold()):
        if p.is_symlink():continue
        if p.is_file():files.append({'name':p.stem,'filename':p.name})
    return {'files':files,'stations':rows,'catalog_revision':rev}


def read_preset(root,platform,name):
    root,folder,_,rows,_,rev=context(root,platform)
    path,raw,data=read_file(root,folder,name);chosen=selections(data,rows)
    return dict(name=path.stem,filename=path.name,revision=revision(raw),fuel=data['Fuel'],livery=data['Livery'],
                selections=chosen,issues=selection_issues(chosen,rows),catalog_revision=rev)


def render(data,original):
    text=original.decode('utf-8-sig') if original is not None else ''
    indent=re.search(r'^([ \t]+)"',text,re.M)
    rendered=json.dumps(data,ensure_ascii=False,allow_nan=False,indent=indent.group(1) if indent else None)
    if '\r\n' in text:rendered=rendered.replace('\n','\r\n')
    if text.endswith('\n'):rendered+='\r\n' if '\r\n' in text else '\n'
    raw=rendered.encode('utf-8')
    if original and original.startswith(b'\xef\xbb\xbf'):raw=b'\xef\xbb\xbf'+raw
    if decode(raw)!=data:raise WriteError('Preset JSON rendering could not be verified.')
    return raw


@dataclass(frozen=True)
class PresetPlan:
    root:Path
    platform:str
    path:Path
    original:bytes|None
    replacement:bytes
    dependencies:tuple
    summary:dict


def plan_preset(root,platform,body):
    root,folder,dictionary,rows,dependencies,catalog_rev=context(root,platform)
    if body.get('catalog_revision')!=catalog_rev:raise ChangedOnDisk('Station whitelists or dictionaries changed. Reload the preset editor.')
    path=folder/filename(body.get('name'))
    # Case collisions are refused on Linux too, keeping names safe for Windows.
    collisions=[p for p in folder.iterdir() if p.name.casefold()==path.name.casefold()]
    if collisions and (len(collisions)!=1 or collisions[0].name!=path.name):raise WriteError('A preset with that name already exists with different capitalization.')
    original=None
    if path.exists() or path.is_symlink():
        path,original,_=read_file(root,folder,path.name)
        if body.get('revision')!=revision(original):raise ChangedOnDisk('Preset exists or changed on disk. Load that preset before overwriting it.')
    elif body.get('revision') is not None:raise ChangedOnDisk('Preset was removed on disk. Reload before saving.')
    source=body.get('source');source_raw=original;data=decode(original) if original is not None else {}
    if source is not None:
        source_path,source_raw,data=read_file(root,folder,source)
        if body.get('source_revision')!=revision(source_raw):raise ChangedOnDisk('Source preset changed on disk. Reload before copying or saving.')
        selections(data,rows);dependencies[source_path]=source_raw
    data=copy.deepcopy(data)
    fuel=body.get('fuel');livery=body.get('livery');chosen=body.get('selections')
    if type(fuel) not in {int,float} or not 0<=fuel<=1 or not math.isfinite(fuel):raise WriteError('Fuel must be between 0 and 100%.')
    if not isinstance(livery,str) or len(livery)>2048 or any(ord(c)<32 for c in livery):raise WriteError('Livery reference must be text without control characters (at most 2048 characters).')
    if not isinstance(chosen,dict) or set(chosen)!={str(r['index']) for r in rows} or any(not isinstance(k,str) for k in chosen.values()):raise WriteError('Choose a mount or Empty for every station.')
    normalized={}
    for row in rows:
        key=chosen[str(row['index'])];normalized[str(row['index'])]=_write_key(dictionary,key) if key else ''
    issues=selection_issues(normalized,rows)
    if issues:raise WriteError(' '.join(issues))
    before=selections(decode(original),rows) if original is not None else {str(r['index']):'' for r in rows}
    data.update(Fuel=fuel,Livery=livery,Stations=[f'{r["name"]}={normalized[str(r["index"])]}' for r in rows],
                Hardpoints=[normalized[str(r['index'])] for r in rows])
    replacement=source_raw if source_raw is not None and decode(source_raw)==data else render(data,source_raw)
    if len(replacement)>MAX_PRESET_BYTES:raise WriteError('Preset is too large.')
    summary=dict(name=path.stem,filename=path.name,creating=original is None,changed=original!=replacement,
                 occupied=sum(bool(k) for k in normalized.values()),fuel=fuel,before_fuel=decode(original)['Fuel'] if original is not None else None,
                 livery=livery,before_livery=decode(original)['Livery'] if original is not None else None,livery_changed=original is None or decode(original)['Livery']!=livery,
                 changes=[dict(index=r['index'],name=r['name'],before=before[str(r['index'])],after=normalized[str(r['index'])]) for r in rows if before[str(r['index'])]!=normalized[str(r['index'])]])
    return PresetPlan(root,platform,path,original,replacement,tuple(dependencies.items()),summary)


def commit_preset(plan):
    if not isinstance(plan,PresetPlan):raise WriteError('Expected a reviewed preset plan.')
    root,folder,_=platform_folder(plan.root,plan.platform)
    if plan.root!=root or plan.path.parent!=folder or filename(plan.path.name)!=plan.path.name:raise WriteError('Preset plan target is outside its platform folder.')
    data=decode(plan.replacement)
    with _lock(plan.root):
        for path,raw in plan.dependencies:
            if _safe_file(plan.root,path).read_bytes()!=raw:raise ChangedOnDisk('Preset source or station catalog changed after review. Reload the editor.')
        _,_,_,rows,_,_=context(plan.root,plan.platform)
        issues=selection_issues(selections(data,rows),rows)
        if issues:raise WriteError(' '.join(issues))
        def check_target():
            collisions=[p for p in plan.path.parent.iterdir() if p.name.casefold()==plan.path.name.casefold()]
            if collisions and (len(collisions)!=1 or collisions[0].name!=plan.path.name):raise ChangedOnDisk('A preset with different capitalization appeared. Reload before saving.')
            if plan.original is None:
                if plan.path.exists() or plan.path.is_symlink():raise ChangedOnDisk('Preset was created after review. Choose another name or load it first.')
            elif _safe_file(plan.root,plan.path).read_bytes()!=plan.original:raise ChangedOnDisk('Preset changed after review. Reload it before saving.')
            if plan.path.parent.is_symlink() or plan.path.parent.resolve()!=plan.path.parent:raise WriteError('Preset folder changed during save.')
        check_target()
        if plan.original==plan.replacement:return SaveResult(plan.path,False,None,revision(plan.replacement))
        backup=None
        if plan.original is not None:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=plan.path.with_name(f'{plan.path.name}.{stamp}.{uuid4().hex[:12]}.bak')
            with backup.open('xb') as f:f.write(plan.original);f.flush();os.fsync(f.fileno())
            if backup.read_bytes()!=plan.original:raise WriteError('Preset backup could not be verified.')
        temporary=None
        try:
            descriptor,name=tempfile.mkstemp(prefix='.alis-preset-',suffix='.tmp',dir=plan.path.parent);temporary=Path(name)
            with os.fdopen(descriptor,'wb') as f:f.write(plan.replacement);f.flush();os.fsync(f.fileno())
            if temporary.read_bytes()!=plan.replacement:raise WriteError('Temporary preset could not be verified.')
            if plan.original is not None:os.chmod(temporary,stat.S_IMODE(plan.path.stat().st_mode))
            check_target()
            if plan.original is None:
                try:os.link(temporary,plan.path)
                except FileExistsError as exc:raise ChangedOnDisk('Preset appeared during save. Reload before overwriting.') from exc
                temporary.unlink();temporary=None
            else:os.replace(temporary,plan.path);temporary=None
            if _safe_file(plan.root,plan.path).read_bytes()!=plan.replacement:raise WriteError('Saved preset verification failed. Inspect its backup before restoring.')
            return SaveResult(plan.path,True,backup,revision(plan.replacement))
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
