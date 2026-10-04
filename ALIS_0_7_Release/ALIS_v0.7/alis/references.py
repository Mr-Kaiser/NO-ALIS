"""Bundled user-provided aircraft reference views, served as validated data URLs."""
import base64
import json
from pathlib import Path
import re

from .writer import WriteError

ASSETS=Path(__file__).resolve().parent.parent


def inventory(platform):
    manifest=json.loads((ASSETS/'config/references.json').read_text(encoding='utf-8'))
    result=[]
    for view in manifest.get('platforms',{}).get(platform,[]):
        filename=view['file']
        if not isinstance(filename,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:png|webp|jpg|jpeg)',filename):raise WriteError('Invalid bundled reference filename.')
        path=ASSETS/'static/references'/filename
        if path.is_symlink() or not path.is_file():raise WriteError('Missing bundled reference image.')
        raw=path.read_bytes()
        if len(raw)>2*1024*1024:raise WriteError('Bundled reference image is too large.')
        mime='image/png' if path.suffix=='.png' else 'image/webp' if path.suffix=='.webp' else 'image/jpeg'
        result.append({'id':view['id'],'name':view['name'],'default':view.get('default',False),
                       'image':f'data:{mime};base64,'+base64.b64encode(raw).decode(),
                       'image_crop':view.get('crop')})
    return result


def default_reference(platform):
    return next((view for view in inventory(platform) if view['default']),None)
