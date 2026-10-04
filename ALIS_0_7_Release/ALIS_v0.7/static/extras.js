'use strict';
const clone=value=>JSON.parse(JSON.stringify(value));
const colorLabels={bg:'Page background',panel:'Panel background',panel2:'Raised panels',line:'Borders',text:'Main text',muted:'Secondary text',accent:'Accent / selected',warning:'Warning / precludes',danger:'Errors',group:'Symmetry markers'};
function activeTheme(data){return data.state.custom[data.state.selected]||data.builtins[data.state.selected];}
function luminance(hex){const v=hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722;}
function applyTheme(theme){
  if(!theme)return;Object.entries(theme.colors).forEach(([k,v])=>document.documentElement.style.setProperty(`--${k==='panel2'?'panel-2':k}`,v));
  const light=luminance(theme.colors.accent),dark=luminance('#102322');
  document.documentElement.style.setProperty('--accent-text',(light+.05)/(dark+.05)>=1.05/(light+.05)?'#102322':'#ffffff');
  document.documentElement.style.colorScheme=luminance(theme.colors.bg)>.5?'light':'dark';
}
function themeDirty(){return !!state.theme&&JSON.stringify(state.theme.draft)!==state.theme.base;}
function themeError(message=''){$('theme-error').textContent=message;$('theme-error').classList.toggle('hidden',!message);}
function themeBusy(value){const t=state.theme;if(!t)return;t.busy=value;$('theme-dialog').querySelectorAll('input,select,button').forEach(n=>n.disabled=value);$('theme-save').textContent=value?'Saving…':'Save theme';if(!value)themeFields();}
function themeFields(){
  const t=state.theme;if(!t)return;const themes={...state.data.themes.builtins,...t.draft.custom},selected=t.draft.selected,palette=themes[selected];
  $('theme-select').replaceChildren(...Object.entries(themes).map(([id,v])=>new Option(v.name,id)));$('theme-select').value=selected;
  $('theme-name').value=palette.name;$('theme-name').disabled=t.busy||!t.draft.custom[selected];$('theme-remove').disabled=t.busy||!t.draft.custom[selected];
  $('theme-colors').replaceChildren();
  Object.entries(colorLabels).forEach(([key,name])=>{
    const label=el('label'),title=el('span','',name),input=el('input');input.type='color';input.value=palette.colors[key];input.dataset.color=key;input.setAttribute('aria-label',name);input.disabled=t.busy;
    const value=el('span','color-value',input.value);label.append(title,input,value);$('theme-colors').append(label);
    input.addEventListener('input',()=>{if(!t.draft.custom[t.draft.selected]&&!copyTheme(false)){input.value=palette.colors[key];return;}const theme=t.draft.custom[t.draft.selected];theme.colors[key]=input.value;value.textContent=input.value;applyTheme(theme);themeContrast(theme);});
  });
  applyTheme(palette);themeContrast(palette);
}
function themeContrast(theme){const a=luminance(theme.colors.text),b=luminance(theme.colors.panel),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);$('theme-contrast').textContent=`Main text / panel contrast: ${ratio.toFixed(1)}:1 · 4.5:1 or higher works well for small text.`;}
function copyTheme(render=true){
  const t=state.theme;if(!t||t.busy)return;
  if(Object.keys(t.draft.custom).length>=12){themeError('Remove a custom theme before adding another (limit 12).');return false;}
  const current=t.draft.custom[t.draft.selected]||state.data.themes.builtins[t.draft.selected],id=`custom-${Array.from(crypto.getRandomValues(new Uint8Array(8))).map(v=>v.toString(16).padStart(2,'0')).join('')}`;
  t.draft.custom[id]=clone(current);t.draft.custom[id].name=`${current.name} copy`.slice(0,60);t.draft.selected=id;
  if(render)themeFields();else{$('theme-select').append(new Option(t.draft.custom[id].name,id));$('theme-select').value=id;$('theme-name').value=t.draft.custom[id].name;$('theme-name').disabled=false;$('theme-remove').disabled=false;}
  themeError();return true;
}
function openTheme(){
  if(state.busy||state.theme||!state.data)return;
  const draft=clone(state.data.themes.state);state.theme={draft,base:JSON.stringify(draft),revision:state.data.themes.revision,busy:false};themeError();themeBusy(false);$('theme-dialog').showModal();
}
function closeTheme(){if(!state.theme||state.theme.busy)return;if(themeDirty()&&!window.confirm('Discard the unsaved theme settings?'))return;$('theme-dialog').close();state.theme=null;applyTheme(activeTheme(state.data.themes));}
$('theme-open').addEventListener('click',openTheme);$('theme-close').addEventListener('click',closeTheme);$('theme-cancel').addEventListener('click',closeTheme);
$('theme-dialog').addEventListener('cancel',e=>{e.preventDefault();closeTheme();});
$('theme-select').addEventListener('change',()=>{state.theme.draft.selected=$('theme-select').value;themeFields();themeError();});
$('theme-copy').addEventListener('click',copyTheme);
$('theme-name').addEventListener('input',()=>{state.theme.draft.custom[state.theme.draft.selected].name=$('theme-name').value;});
$('theme-remove').addEventListener('click',()=>{const t=state.theme;delete t.draft.custom[t.draft.selected];t.draft.selected='alis';themeFields();});
$('theme-save').addEventListener('click',async()=>{
  const t=state.theme;if(!t||t.busy)return;themeBusy(true);themeError();
  try{const r=await api('/api/themes',{revision:t.revision,state:t.draft});state.data.themes=r.themes;state.theme=null;$('theme-dialog').close();applyTheme(activeTheme(r.themes));notice(`Theme saved: ${activeTheme(r.themes).name}.`);}
  catch(e){themeError(e.message);themeBusy(false);}
});

function presetUrl(suffix=''){return `/api/platforms/${encodeURIComponent(state.platform.name)}/presets${suffix}`;}
function presetSnapshot(p){return JSON.stringify({draft:p.draft,asNew:p.asNew});}
function presetDirty(){return !!state.presets?.draft&&presetSnapshot(state.presets)!==state.presets.base;}
function presetError(message=''){$('preset-error').textContent=message;$('preset-error').classList.toggle('hidden',!message);}
function presetBusy(value){const p=state.presets;if(!p)return;p.busy=value;$('preset-dialog').querySelectorAll('input,select,button').forEach(n=>n.disabled=value);$('preset-save').textContent=value?'Saving…':'Save preset';updatePresetHistoryButtons();}
function leavePreset(){return !presetDirty()||window.confirm(presetDraftSaved()?'Leave this preset? Its unsaved changes remain available in Drafts.':'Discard the unsaved loadout preset changes? Draft recovery is unavailable in this browser.');}
function closePreset(){if(!state.presets||state.presets.busy||!leavePreset())return;$('preset-dialog').close();state.presets=null;}
function presetList(){const p=state.presets;$('preset-source').replaceChildren(new Option('Choose an existing preset…',''),...p.catalog.files.map(f=>new Option(f.name,f.name)));$('preset-source').value=p.source?.name||'';}
function editPreset(){
  const p=state.presets;if(!p)return;p.ticket=null;$('preset-editor').classList.remove('hidden');$('preset-review').classList.add('hidden');$('preset-review-button').classList.remove('hidden');$('preset-save').classList.add('hidden');$('preset-back').classList.add('hidden');
}
function presetWarnings(){
  const p=state.presets,issues=[];if(!p?.draft)return;
  p.catalog.stations.forEach(s=>{const k=p.draft.selections[s.index]||'';if(k&&!s.allowed.includes(k))issues.push(`Station ${s.index}: ${k} is not available in its whitelist.`);if(k)s.precluding.forEach(j=>{if(p.draft.selections[j])issues.push(`Station ${s.index} precludes occupied station ${j}. Clear one selection.`);});});
  presetError([...new Set(issues)].join(' '));
}
function presetFields(){
  const p=state.presets,draft=p.draft;$('preset-name').value=draft.name;$('preset-fuel').value=Number((draft.fuel*100).toFixed(6));$('preset-livery').value=draft.livery;
  $('preset-stations').replaceChildren();const weapons=new Map(state.data.weapons.map(w=>[w.write_key,w]));
  p.catalog.stations.forEach(s=>{
    const row=el('label','preset-station'),title=el('span','preset-station-title',`${String(s.index).padStart(2,'0')} / ${s.name}`),select=el('select');select.dataset.station=s.index;select.setAttribute('aria-label',`Loadout for ${s.name}`);
    select.append(new Option('Empty — no mount',''));
    s.allowed.forEach(k=>{const w=weapons.get(k);select.append(new Option(`${w?.name||k} · ${k}`,k));});
    const chosen=draft.selections[s.index]||'';
    if(chosen&&!s.allowed.includes(chosen)){const option=new Option(`Unavailable: ${chosen}`,chosen);option.disabled=true;select.append(option);}
    select.value=chosen;const note=el('span','subtle',`${s.hardpoints} hardpoint${s.hardpoints===1?'':'s'} share this selection${s.precluding.length?` · precludes ${s.precluding.join(', ')}`:''}`);
    row.append(title,select,note);$('preset-stations').append(row);
    select.addEventListener('change',()=>{draft.selections[s.index]=select.value;editPreset();presetWarnings();presetEdited();});
  });
  presetList();editPreset();presetWarnings();
}
function applyPreset(source){
  const p=state.presets;
  if(source&&source.catalog_revision!==p.catalog.catalog_revision)throw new Error('The preset catalog changed. Close and reopen the editor.');
  p.source=source;p.asNew=!source;
  p.draft=source?{name:source.name,fuel:source.fuel,livery:source.livery,selections:clone(source.selections)}:{name:'New preset',fuel:1,livery:'',selections:Object.fromEntries(p.catalog.stations.map(s=>[s.index,'']))};
  p.base=presetSnapshot(p);initPresetHistory();presetFields();
}
async function openPresets(){
  if(state.busy||state.presets||!state.platform)return;
  setBusy(true);
  state.presets={busy:true,draft:null};$('preset-platform').textContent=`${state.platform.display_name} (${state.platform.name})`;presetError();presetBusy(true);
  try{
    const catalog=await api(presetUrl());state.presets.catalog=catalog;applyPreset(null);
    const first=catalog.files.find(f=>f.name==='DEFAULT')||catalog.files[0];
    if(first){try{applyPreset(await api(presetUrl('/'+encodeURIComponent(first.name))));}catch(e){presetError(`Could not load ${first.name}: ${e.message} Choose another preset or create a new one.`);}}
    presetBusy(false);$('preset-dialog').showModal();
  }
  catch(e){state.presets=null;notice(e.message,'error');}finally{setBusy(false);}
}
$('presets-open').addEventListener('click',openPresets);$('preset-close').addEventListener('click',closePreset);$('preset-cancel').addEventListener('click',closePreset);
$('preset-dialog').addEventListener('cancel',e=>{e.preventDefault();closePreset();});
$('preset-load').addEventListener('click',async()=>{
  const p=state.presets,name=$('preset-source').value;if(!p||p.busy||!name||!leavePreset())return;presetBusy(true);presetError();
  try{const catalog=await api(presetUrl());const source=await api(presetUrl('/'+encodeURIComponent(name)));if(source.catalog_revision!==catalog.catalog_revision)throw new Error('Preset catalog changed while loading. Try again.');p.catalog=catalog;applyPreset(source);}
  catch(e){presetError(e.message);}finally{presetBusy(false);}
});
$('preset-new').addEventListener('click',()=>{if(state.presets?.busy||!leavePreset())return;applyPreset(null);});
$('preset-copy').addEventListener('click',()=>{const p=state.presets;if(!p||p.busy)return;p.asNew=true;let name=`${p.draft.name} copy`.slice(0,100),suffix=2;const existing=new Set(p.catalog.files.map(f=>f.name.toLowerCase()));while(existing.has(name.toLowerCase()))name=`${p.draft.name.slice(0,85)} copy ${suffix++}`;p.draft.name=name;$('preset-name').value=name;editPreset();presetEdited();});
['preset-name','preset-livery'].forEach(id=>$(id).addEventListener('input',()=>{const p=state.presets;if(!p?.draft)return;p.draft[id==='preset-name'?'name':'livery']=$(id).value;editPreset();presetEdited(id);}));
$('preset-fuel').addEventListener('input',()=>{if(state.presets?.draft){state.presets.draft.fuel=$('preset-fuel').valueAsNumber/100;editPreset();presetEdited('preset-fuel');}});
$('preset-back').addEventListener('click',()=>{if(!state.presets?.busy)editPreset();});
$('preset-review-button').addEventListener('click',async()=>{
  const p=state.presets;if(!p||p.busy)return;if(!$('preset-name').reportValidity()||!$('preset-fuel').reportValidity())return;
  const body={...p.draft,name:p.draft.name.trim(),catalog_revision:p.catalog.catalog_revision,revision:!p.asNew&&p.source?.name===p.draft.name.trim()?p.source.revision:null,source:p.source?.name??null,source_revision:p.source?.revision??null};
  presetBusy(true);presetError();
  try{
    const r=await api(presetUrl('/preview'),body);p.ticket=r.ticket;
    const fuel=r.before_fuel===null?`${(r.fuel*100).toFixed(2)}%`:`${(r.before_fuel*100).toFixed(2)}% → ${(r.fuel*100).toFixed(2)}%`;
    $('preset-review-summary').textContent=`${r.creating?'Create':'Update'} ${r.filename} · ${r.occupied} occupied station groups · ${fuel} fuel. ${r.creating?'A new file will be created.':'The existing file will be backed up before saving.'}`;
    $('preset-review-changes').replaceChildren(...r.changes.map(c=>el('p','review-change',`${String(c.index).padStart(2,'0')} / ${c.name}: ${c.before||'Empty'} → ${c.after||'Empty'}`)));
    if(!r.changes.length)$('preset-review-changes').append(el('p','review-change','No mount differences. Fuel, livery and file creation are included in this save.'));
    if(r.livery_changed)$('preset-review-changes').append(el('p','review-change',`Livery: ${r.before_livery||'Unspecified'} → ${r.livery||'Unspecified'}`));
    $('preset-editor').classList.add('hidden');$('preset-review').classList.remove('hidden');$('preset-review-button').classList.add('hidden');$('preset-save').classList.remove('hidden');$('preset-back').classList.remove('hidden');
  }catch(e){presetError(e.message);}finally{presetBusy(false);}
});
$('preset-save').addEventListener('click',async()=>{
  const p=state.presets;if(!p||p.busy||!p.ticket)return;const ticket=p.ticket;p.ticket=null;presetBusy(true);presetError();
  try{const previous=p.catalog.files.length,r=await api('/api/preset-commit',{ticket});clearPresetDraft();p.catalog=r.catalog;applyPreset(r.preset);state.data.presets+=p.catalog.files.length-previous;$('preset-total').textContent=state.data.presets;notice(r.changed?`Preset saved and verified: ${r.preset.filename}${r.backup?` · Backup: ${r.backup}`:''}`:'Preset already matches. No files changed.');}
  catch(e){presetError(e.message+' Your draft remains available. Return to editing and reload the preset catalog before reviewing again.');$('preset-save').disabled=true;}
  finally{presetBusy(false);if(!p.ticket&&!$('preset-review').classList.contains('hidden'))$('preset-save').disabled=true;}
});
loadData();
