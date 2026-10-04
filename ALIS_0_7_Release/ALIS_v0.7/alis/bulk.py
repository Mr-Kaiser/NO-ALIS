"""Reviewed station patches, exact backups, rollback and interruption recovery."""
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import tempfile

from .dictionary import load_dictionary
from .writer import (ChangedOnDisk, WriteError, _backup, _lock, _object,
                     _safe_file, _target, _write_key, plan_edit, revision)

JOURNAL='.alis-bulk-journal.json'
DICTIONARIES=('hardpointdictionary_mounts.csv','hardpointdictionary_stations.csv')


def dictionaries(root):
    root=Path(root).resolve(strict=True)
    return tuple((_safe_file(root,root/name), (root/name).read_bytes()) for name in DICTIONARIES)


def dictionary_revision(root):
    return revision(json.dumps([(p.name,revision(raw)) for p,raw in dictionaries(root)]).encode())


def _same_dependencies(dependencies):
    for path,raw in dependencies:
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=raw:
            raise ChangedOnDisk('A dictionary or the source station changed. Reload and review the bulk edit again.')


def catalog(root,platform):
    deps=dictionaries(root);dictionary=load_dictionary(root)
    if platform not in dictionary.platforms:raise WriteError('Unknown platform.')
    rows=[]
    for s in dictionary.platforms[platform].sorted_stations():
        row={'index':s.station_index,'name':s.station_name,'symmetry':s.symmetry_name}
        try:
            plan=plan_edit(root,platform,s.station_index)
            row.update(ready=True,revision=plan.expected_revision,count=len(plan.before),allowed=list(plan.before))
        except (OSError,WriteError) as exc:row.update(ready=False,error=str(exc))
        rows.append(row)
    _same_dependencies(deps)
    return {'platform':platform,'stations':rows,'dictionary_revision':dictionary_revision(root)}


@dataclass(frozen=True)
class BatchPlan:
    root:Path
    platform:str
    indices:tuple
    plans:tuple
    dependencies:tuple

    @property
    def summary(self):
        return {'platform':self.platform,'changed_count':sum(p.changed for p in self.plans),
                'stations':[dict(p.summary(),index=i,path=str(p.path.relative_to(self.root)),
                                 name=p.path.stem) for i,p in zip(self.indices,self.plans)]}


def plan_batch(root,platform,body):
    root=Path(root).resolve(strict=True);deps=dictionaries(root)
    if body.get('dictionary_revision')!=dictionary_revision(root):raise ChangedOnDisk('Dictionary changed. Reload the bulk station list.')
    targets=body.get('targets');source=body.get('source')
    if not isinstance(targets,list) or not 1<=len(targets)<=64:raise WriteError('Choose 1–64 stations.')
    if not isinstance(source,dict) or type(source.get('index')) is not int or not isinstance(source.get('revision'),str):raise WriteError('A loaded source station is required.')
    source_plan=plan_edit(root,platform,source['index'],expected_revision=source['revision'])
    deps+=((source_plan.path,source_plan.original),)
    for field in ('add','remove'):
        values=body.get(field)
        if not isinstance(values,list) or len(values)>10000 or any(not isinstance(k,str) or not k for k in values):raise WriteError(f'{field} must be an array of weapon keys.')
    if not body['add'] and not body['remove']:raise WriteError('Make a station draft before applying it in bulk.')
    allow_empty=body.get('allow_empty',False)
    if type(allow_empty) is not bool:raise WriteError('allow_empty must be a boolean.')
    dictionary=load_dictionary(root)
    # An unresolved removal is valid only if it exists on the source; missing
    # copies on other stations are a no-op rather than an unknown-key failure.
    for key in body['remove']:
        if key not in source_plan.before:_write_key(dictionary,key)
    indices=[];plans=[]
    for target in targets:
        if not isinstance(target,dict) or type(target.get('index')) is not int or not isinstance(target.get('revision'),str):raise WriteError('Every target needs its loaded station index and revision.')
        index=target['index']
        if index in indices:raise WriteError('Choose each station only once.')
        current=plan_edit(root,platform,index,expected_revision=target['revision'])
        removals=[]
        for key in body['remove']:
            if key in current.before:removals.append(key)
            else:
                try:_write_key(dictionary,key)
                except WriteError:continue
                removals.append(key)
        plan=plan_edit(root,platform,index,add=body['add'],remove=removals,
                       allow_empty=allow_empty,expected_revision=target['revision'])
        indices.append(index);plans.append(plan)
    _same_dependencies(deps)
    return BatchPlan(root,platform,tuple(indices),tuple(plans),deps)


def _stage(path,raw):
    fd,name=tempfile.mkstemp(prefix='.alis-bulk-',suffix='.tmp',dir=path.parent);temporary=Path(name)
    try:
        with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.chmod(temporary,stat.S_IMODE(path.stat().st_mode))
        if temporary.read_bytes()!=raw:raise WriteError('Bulk temporary file verification failed.')
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True);raise


def _replace_expected(root,path,expected,replacement):
    _safe_file(root,path)
    temporary=_stage(path,replacement)
    try:
        if path.read_bytes()!=expected:raise ChangedOnDisk(f'{path.name} changed during bulk save.')
        _safe_file(root,path);os.replace(temporary,path)
        if path.read_bytes()!=replacement:raise WriteError(f'Could not verify {path.name}.')
    finally:temporary.unlink(missing_ok=True)


def _journal_path(root):
    path=Path(root)/JOURNAL
    if path.is_symlink() or path.exists() and not path.is_file():raise WriteError('Bulk recovery record must be a regular file.')
    return path


def _create_journal(root,platform,entries):
    path=_journal_path(root)
    if path.exists():raise WriteError('A previous bulk save needs recovery.')
    raw=(json.dumps({'version':1,'platform':platform,'entries':entries},indent=2)+'\n').encode()
    if len(raw)>8*1024*1024:raise WriteError('Bulk recovery record is too large.')
    fd,name=tempfile.mkstemp(prefix='.alis-bulk-journal-',suffix='.tmp',dir=root);temporary=Path(name)
    try:
        with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        if temporary.read_bytes()!=raw:raise WriteError('Could not verify bulk recovery record.')
        if path.exists():raise WriteError('Another bulk recovery record appeared.')
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def _load_journal(root):
    path=_journal_path(root)
    if not path.exists():return None,None,[]
    raw=path.read_bytes()
    if len(raw)>8*1024*1024:raise WriteError('Bulk recovery record is too large.')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise WriteError('Duplicate bulk recovery field.')
            result[k]=v
        return result
    try:data=json.loads(raw,object_pairs_hook=pairs)
    except (UnicodeError,json.JSONDecodeError) as exc:raise WriteError('Invalid bulk recovery record. Retain it and inspect the station backups.') from exc
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('platform'),str) or not isinstance(data.get('entries'),list) or not 1<=len(data['entries'])<=64:raise WriteError('Invalid bulk recovery record.')
    rows=[];seen=set()
    for entry in data['entries']:
        if not isinstance(entry,dict) or type(entry.get('index')) is not int:raise WriteError('Invalid bulk recovery station.')
        _,target,_=_target(root,data['platform'],entry['index'])
        if entry.get('path')!=str(target.relative_to(root)) or target in seen:raise WriteError('Bulk recovery path does not match its station.')
        seen.add(target)
        try:before=base64.b64decode(entry['before'],validate=True);after=base64.b64decode(entry['after'],validate=True)
        except (KeyError,TypeError,ValueError) as exc:raise WriteError('Invalid bulk recovery bytes.') from exc
        expected=_object(before);actual=_object(after);expected['allowedWeapons']=actual['allowedWeapons']
        if expected!=actual:raise WriteError('Bulk recovery changed fields outside the whitelist.')
        backup=entry.get('backup')
        if not isinstance(backup,str):raise WriteError('Missing bulk backup.')
        # Reuse the station restore validator rather than trusting a path from
        # the recovery record. It also checks backup naming and confinement.
        from .writer import plan_restore
        restoration=plan_restore(root,data['platform'],entry['index'],Path(root)/backup)
        if restoration.replacement!=before:raise WriteError('Bulk backup does not match the recovery record.')
        current=target.read_bytes()
        rows.append({'index':entry['index'],'path':target,'before':before,'after':after,'backup':backup,
                     'status':'original' if current==before else 'changed' if current==after else 'external',
                     'current_revision':revision(current)})
    return data,revision(raw),rows


def recovery_status(root):
    data,rev,rows=_load_journal(root)
    if data is None:return None
    return {'platform':data['platform'],'revision':rev,'can_restore':all(r['status']!='external' for r in rows),
            'stations':[{k:(str(v.relative_to(root)) if k=='path' else v) for k,v in r.items() if k not in {'before','after'}} for r in rows]}


def _rollback(root,rows):
    errors=[]
    for row in reversed(rows):
        try:
            path=_safe_file(root,row['path']);current=path.read_bytes()
            if current==row['before']:continue
            if current!=row['after']:raise ChangedOnDisk(f'{path.name} was edited outside this batch; it was retained.')
            _replace_expected(root,path,row['after'],row['before'])
        except (OSError,WriteError) as exc:errors.append(str(exc))
    return errors


class BatchFailed(WriteError):
    def __init__(self,cause,errors,backups):
        self.recovery_required=bool(errors);self.backups=backups
        message='Bulk save failed. '+('Some files still need recovery. ' if errors else 'All batch changes were rolled back. ')+str(cause)
        if errors:message+=' '+' '.join(errors)
        super().__init__(message)


def commit_batch(batch):
    if not 1<=len(batch.indices)<=64 or len(batch.indices)!=len(batch.plans) or len(set(batch.indices))!=len(batch.indices):raise WriteError('Invalid bulk station selection.')
    with _lock(batch.root):
        _same_dependencies(batch.dependencies)
        for index,plan in zip(batch.indices,batch.plans):
            _,target,_=_target(batch.root,batch.platform,index)
            expected=_object(plan.original);intended=_object(plan.replacement);expected['allowedWeapons']=list(plan.after)
            if target!=plan.path or plan.root!=batch.root or expected!=intended or tuple(_object(plan.original)['allowedWeapons'])!=plan.before or plan.restoring is not None:raise WriteError('Invalid bulk edit plan.')
            if target.read_bytes()!=plan.original:raise ChangedOnDisk('A target station changed after review. Nothing was saved.')
        changed=[(i,p) for i,p in zip(batch.indices,batch.plans) if p.changed]
        if not changed:return {'changed_count':0,'verified':True,'backups':[]}
        entries=[];rows=[];staged=[];backups=[];journal_created=False
        try:
            for index,plan in changed:
                backup=_backup(plan.path,plan.original);relative=str(backup.relative_to(batch.root));backups.append(relative)
                staged.append((plan,_stage(plan.path,plan.replacement)))
                entries.append({'index':index,'path':str(plan.path.relative_to(batch.root)),'backup':relative,
                    'before':base64.b64encode(plan.original).decode(),'after':base64.b64encode(plan.replacement).decode()})
                rows.append({'path':plan.path,'before':plan.original,'after':plan.replacement})
            _same_dependencies(batch.dependencies)
            for plan in batch.plans:
                if _safe_file(batch.root,plan.path).read_bytes()!=plan.original:raise ChangedOnDisk('A target changed during preparation.')
            _create_journal(batch.root,batch.platform,entries);journal_created=True
            for plan,temporary in staged:
                if _safe_file(batch.root,plan.path).read_bytes()!=plan.original:raise ChangedOnDisk('A target changed during bulk save.')
                os.replace(temporary,plan.path)
                if plan.path.read_bytes()!=plan.replacement:raise WriteError('Bulk save verification failed.')
            # The source may itself be a target, so verify its expected post-save
            # bytes while dictionaries and untouched dependencies remain exact.
            after_by_path={p.path:p.replacement for p in batch.plans}
            _same_dependencies(tuple((path,after_by_path.get(path,raw)) for path,raw in batch.dependencies))
            for plan in batch.plans:
                if plan.path.read_bytes()!=plan.replacement:raise ChangedOnDisk('A station changed before final verification.')
            _journal_path(batch.root).unlink();journal_created=False
            return {'changed_count':len(changed),'verified':True,'backups':backups}
        except Exception as exc:
            errors=_rollback(batch.root,rows) if journal_created else []
            if journal_created and not errors:_journal_path(batch.root).unlink()
            raise BatchFailed(exc,errors,backups) from exc
        finally:
            for _,temporary in staged:temporary.unlink(missing_ok=True)


def recover_batch(root,expected,expected_stations):
    root=Path(root).resolve(strict=True)
    with _lock(root,allow_bulk_recovery=True):
        data,rev,rows=_load_journal(root)
        if data is None:raise WriteError('No bulk save needs recovery.')
        if expected!=rev:raise ChangedOnDisk('Bulk recovery record changed. Reload the recovery view.')
        actual={str(r['index']):r['current_revision'] for r in rows}
        if expected_stations!=actual:raise ChangedOnDisk('Station files changed since the recovery view. Reload it.')
        if any(r['status']=='external' for r in rows):raise ChangedOnDisk('A station was changed outside the batch. Retain its edits and inspect the backups before recovery.')
        errors=_rollback(root,rows)
        if errors:raise BatchFailed('Recovery was incomplete.',errors,[r['backup'] for r in rows])
        _journal_path(root).unlink()
        return {'restored':True,'platform':data['platform'],'stations':[r['index'] for r in rows]}
