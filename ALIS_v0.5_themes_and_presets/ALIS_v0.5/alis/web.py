"""Local browser API. All writes go through the v0.2 plan/commit writer."""
from dataclasses import asdict
from pathlib import Path
import secrets
import threading
import time

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .stations import load_repository
from .dictionary import load_dictionary
from .layouts import load_store, profile_for, save_profile
from . import presets, themes
from .writer import ChangedOnDisk, WriteError, commit, plan_edit, plan_restore, _target


def create_app(root):
    root = Path(root).expanduser().resolve(strict=True)
    # Validate the folder before exposing any interface.
    load_repository(root)
    assets = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(assets/'templates'), static_folder=str(assets/'static'))
    app.config.update(MAX_CONTENT_LENGTH=3 * 1024 * 1024, TRUSTED_HOSTS=['127.0.0.1', 'localhost'],
                      ALIS_ROOT=root, ALIS_TOKEN=secrets.token_urlsafe(32))
    plans = {}
    guard = threading.Lock()
    app.extensions['alis_plans'] = plans
    preset_plans = {}
    app.extensions['alis_preset_plans'] = preset_plans

    @app.before_request
    def local_only():
        if request.remote_addr not in {'127.0.0.1', '::1'}:
            abort(403, description='ALIS accepts local connections only.')
        origin = request.headers.get('Origin')
        if origin and origin != f'http://{request.host}':
            abort(403, description='Cross-origin requests are not allowed.')
        if request.method not in {'GET','HEAD','OPTIONS'}:
            token = request.headers.get('X-ALIS-Token', '')
            if not secrets.compare_digest(token, app.config['ALIS_TOKEN']):
                abort(403, description='Session expired. Reload ALIS before saving.')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        return response

    @app.errorhandler(ChangedOnDisk)
    def conflict(exc):
        return jsonify(error=str(exc), code='CHANGED_ON_DISK'), 409

    @app.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc), code='INVALID_INPUT'), 400

    @app.errorhandler(OSError)
    def io_error(exc):
        return jsonify(error=str(exc), code='FILE_ERROR'), 400

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description, code=exc.name), exc.code

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            abort(400, description='Expected a JSON object.')
        return data

    def station(root, platform, index):
        p = plan_edit(root, platform, index)
        _, path, dictionary = _target(root, platform, index)
        name = path.parent.parent.name
        metadata = next(s for s in dictionary.platforms[name].stations if s.station_index == index)
        backups = [dict(name=b.name, modified=b.stat().st_mtime, bytes=b.stat().st_size)
                   for b in sorted(path.parent.glob(path.name+'.*.bak'), key=lambda b: b.name, reverse=True)
                   if b.is_file() and not b.is_symlink()]
        return dict(platform=name, index=index, name=metadata.station_name,
                    symmetry=metadata.symmetry_name, hardpoints=metadata.hardpoint_count,
                    precluding=list(metadata.precluding), owner=metadata.owner,
                    allowed=list(p.before), revision=p.expected_revision,
                    path=str(path.relative_to(root)), backups=backups)

    @app.get('/')
    def index():
        return render_template('index.html', token=app.config['ALIS_TOKEN'])

    @app.get('/api/bootstrap')
    def bootstrap():
        snap = load_repository(root)
        store, profiles_revision, _ = load_store(root)
        platforms = []
        for p in sorted(snap.dictionary.platforms.values(), key=lambda p:p.internal_name.casefold()):
            stations = []
            for s in p.sorted_stations():
                configs = snap.station_configs.get(p.internal_name, {}).get(s.station_index, [])
                stations.append(dict(index=s.station_index, name=s.station_name, symmetry=s.symmetry_name,
                    hardpoints=s.hardpoint_count, precluding=list(s.precluding), owner=s.owner,
                    allowed_count=len(configs[0].allowed_weapons) if len(configs)==1 else None,
                    ready=len(configs)==1))
            profile = profile_for(p.internal_name,p.stations,store)
            platforms.append(dict(name=p.internal_name, display_name=profile["display_name"], stations=stations, profile=profile))
        weapons = [dict(key=w.json_key, write_key=w.write_key, asset=w.asset_name,
                        name=w.display_name, owner=w.owner, ammo=w.ammo,
                        note=w.note, stale=w.is_stale_key) for w in snap.dictionary.weapons]
        return jsonify(version='0.5.0', root=str(root), schema=snap.schema_version, platforms=platforms, themes=themes.inventory(root),
                       weapons=weapons, profiles_revision=profiles_revision, presets=snap.preset_count, issues=[asdict(i) for i in snap.issues])

    @app.post('/api/themes')
    def save_themes():
        data=body()
        result,backup=themes.save(root,data.get('state'),data.get('revision'))
        return jsonify(themes=result,backup=str(backup.relative_to(root)) if backup else None)

    @app.get('/api/platforms/<platform>/presets')
    def preset_list(platform):
        return jsonify(presets.list_presets(root,platform))

    @app.get('/api/platforms/<platform>/presets/<name>')
    def get_preset(platform,name):
        return jsonify(presets.read_preset(root,platform,name))

    @app.post('/api/platforms/<platform>/presets/preview')
    def preview_preset(platform):
        plan=presets.plan_preset(root,platform,body())
        ticket=secrets.token_urlsafe(32)
        with guard:
            now=time.monotonic()
            for old in list(preset_plans):
                if preset_plans[old][0]<now-600:del preset_plans[old]
            if len(preset_plans)>=128:abort(429,description='Too many open preset reviews. Restart ALIS or wait for them to expire.')
            preset_plans[ticket]=(now,plan)
        return jsonify(**plan.summary,ticket=ticket)

    @app.post('/api/preset-commit')
    def save_preset():
        ticket=body().get('ticket')
        if not isinstance(ticket,str):abort(400,description='A preset review ticket is required.')
        with guard:item=preset_plans.pop(ticket,None)
        if item is None or item[0]<time.monotonic()-600:abort(410,description='Preset review expired or was already used. Review it again.')
        plan=item[1];result=presets.commit_preset(plan)
        return jsonify(changed=result.changed,verified=True,backup=str(result.backup.relative_to(root)) if result.backup else None,
                       preset=presets.read_preset(root,plan.platform,plan.path.name),catalog=presets.list_presets(root,plan.platform))

    @app.post('/api/platforms/<platform>/profile')
    def update_profile(platform):
        data = body()
        expected = data.get('revision')
        if not isinstance(expected,str) or len(expected)!=64:
            abort(400, description='A loaded ALIS profile revision is required.')
        dictionary = load_dictionary(root)
        if platform not in dictionary.platforms:
            abort(404, description='Unknown platform.')
        stations = dictionary.platforms[platform].stations
        _, current, backup = save_profile(root,platform,stations,data.get('profile'),expected)
        store, actual_revision, _ = load_store(root)
        return jsonify(profile=profile_for(platform,stations,store),revision=actual_revision,
                       backup=str(backup.relative_to(root)) if backup else None)

    @app.get('/api/platforms/<platform>/stations/<int:index>')
    def get_station(platform, index):
        return jsonify(station(root, platform, index))

    @app.post('/api/platforms/<platform>/stations/<int:index>/preview')
    def preview(platform, index):
        data = body()
        expected = data.get('revision')
        if not isinstance(expected, str) or len(expected)!=64:
            abort(400, description='A loaded station revision is required.')
        if 'restore' in data:
            if any(k in data for k in ('add','remove','allow_empty')):
                abort(400, description='Restore cannot be combined with weapon edits.')
            name = data['restore']
            if not isinstance(name,str) or Path(name).name != name or '/' in name or '\\' in name:
                abort(400, description='Expected a backup filename, not a path.')
            _, path, _ = _target(root,platform,index)
            p = plan_restore(root,platform,index,path.parent/name)
            if p.expected_revision != expected:
                raise ChangedOnDisk('Station changed on disk. Reload before restoring.')
        else:
            for field in ('add','remove'):
                value = data.get(field, [])
                if not isinstance(value,list) or any(not isinstance(k,str) for k in value):
                    abort(400, description=f'{field} must be an array of weapon keys.')
            allow_empty = data.get('allow_empty',False)
            if type(allow_empty) is not bool:
                abort(400, description='allow_empty must be a boolean.')
            p = plan_edit(root,platform,index,add=data.get('add',[]),remove=data.get('remove',[]),
                          allow_empty=allow_empty,expected_revision=expected)
        ticket = secrets.token_urlsafe(24)
        with guard:
            now = time.monotonic()
            for old in list(plans):
                if plans[old][0] < now-600:
                    del plans[old]
            if len(plans)>=128:
                abort(429, description='Too many open previews. Close old previews or restart ALIS.')
            plans[ticket] = (now,p)
        summary = p.summary()
        summary['path'] = str(p.path.relative_to(root))
        summary['ticket'] = ticket
        summary['after'] = list(p.after)
        return jsonify(summary)

    @app.post('/api/commit')
    def save():
        ticket = body().get('ticket')
        if not isinstance(ticket,str):
            abort(400, description='A preview ticket is required.')
        with guard:
            item = plans.pop(ticket,None)
        if item is None or item[0] < time.monotonic()-600:
            abort(410, description='Preview expired or was already used. Review the change again.')
        result = commit(item[1])
        platform = result.path.parent.parent.name
        index = int(result.path.parent.name[len('weaponstation'):])
        return jsonify(changed=result.changed, verified=True,
                       backup=str(result.backup.relative_to(root)) if result.backup else None,
                       station=station(root,platform,index))

    return app
