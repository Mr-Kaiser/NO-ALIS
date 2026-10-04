'use strict';
let stationHistory=null,draftStorageFailed=false,draftDialogBusy=false;
const historyLimit=100;
function newHistory(value){return {past:[value],future:[],group:null,time:0,stamp:null};}
function pushHistory(h,value,group=null){
  if(h.past.at(-1)===value)return;
  const now=Date.now();
  if(group&&h.group===group&&now-h.time<750&&h.past.length>1)h.past[h.past.length-1]=value;
  else{h.past.push(value);if(h.past.length>historyLimit+1)h.past.shift();}
  h.future=[];h.group=group;h.time=now;
}
function stepHistory(h,redo){
  if(redo){if(!h.future.length)return null;h.past.push(h.future.pop());}
  else{if(h.past.length<2)return null;h.future.push(h.past.pop());}
  h.group=null;return h.past.at(-1);
}
function stationSnapshot(){return JSON.stringify([...state.selected].sort());}
function initStationHistory(){stationHistory=newHistory(stationSnapshot());}
function updateStationHistoryButtons(){
  $('station-undo').disabled=state.busy||!state.station||!stationHistory||stationHistory.past.length<2;
  $('station-redo').disabled=state.busy||!state.station||!stationHistory?.future.length;
}
function updatePresetHistoryButtons(){
  const p=state.presets;
  $('preset-undo').disabled=!p||p.busy||!p.history||p.history.past.length<2;
  $('preset-redo').disabled=!p||p.busy||!p.history?.future.length;
}
function initPresetHistory(){const p=state.presets;if(p?.draft){p.history=newHistory(presetSnapshot(p));p.recoveryKey=`preset:${state.platform.name}:${p.source?.name||crypto.randomUUID()}`;}updatePresetHistoryButtons();}
function storageKey(){return state.data?`alis-drafts-v1:${encodeURIComponent(state.data.root)}`:null;}
function readDrafts(){
  const key=storageKey();if(!key)return {version:1,root:null,entries:{}};
  const raw=localStorage.getItem(key);if(!raw)return {version:1,root:state.data.root,entries:{}};
  if(raw.length>2*1024*1024)throw new Error('Saved drafts exceed the recovery limit.');
  const data=JSON.parse(raw);
  if(!data||data.version!==1||data.root!==state.data.root||!data.entries||Array.isArray(data.entries)||typeof data.entries!=='object'||Object.keys(data.entries).length>100)throw new Error('Saved draft data is invalid; it has been retained.');
  for(const entry of Object.values(data.entries)){
    if(!entry||!['station','preset'].includes(entry.kind)||typeof entry.platform!=='string'||typeof entry.stamp!=='string'||typeof entry.updated!=='number')throw new Error('A saved draft is invalid; it has been retained.');
    if(entry.kind==='station'&&(typeof entry.name!=='string'||!Number.isInteger(entry.index)||typeof entry.revision!=='string'||['add','remove'].some(k=>!Array.isArray(entry[k])||entry[k].length>10000||entry[k].some(v=>typeof v!=='string'))))throw new Error('A station draft is invalid; it has been retained.');
    if(entry.kind==='preset'&&(typeof entry.asNew!=='boolean'||!entry.draft||typeof entry.draft.name!=='string'||typeof entry.draft.livery!=='string'||!(entry.draft.fuel===null||typeof entry.draft.fuel==='number'&&Number.isFinite(entry.draft.fuel))||!entry.draft.selections||typeof entry.draft.selections!=='object'||Object.values(entry.draft.selections).some(v=>typeof v!=='string')||!Array.isArray(entry.stations)||entry.stations.some(s=>!s||!Number.isInteger(s.index)||typeof s.name!=='string')))throw new Error('A preset draft is invalid; it has been retained.');
  }
  return data;
}
function draftFailure(error){
  draftStorageFailed=true;$('drafts-open').title=`Recovery storage unavailable: ${error.message}`;$('drafts-count').textContent='!';
}
function refreshDraftCount(){
  if(!state.data)return;
  try{const entries=readDrafts().entries;$('drafts-count').textContent=Object.keys(entries).length;$('drafts-open').title='Recover station and preset drafts saved in this browser';draftStorageFailed=false;}
  catch(e){draftFailure(e);}
}
function writeDraft(id,entry){
  try{
    const data=readDrafts();if(!data.entries[id]&&Object.keys(data.entries).length>=100)throw new Error('100 drafts are stored. Delete an old recovery copy before adding another.');
    const stamp=`${Date.now()}-${crypto.randomUUID()}`;data.entries[id]={...entry,stamp,updated:Date.now()};
    const raw=JSON.stringify(data);if(raw.length>2*1024*1024)throw new Error('Draft storage is full.');
    localStorage.setItem(storageKey(),raw);refreshDraftCount();return stamp;
  }catch(e){draftFailure(e);return null;}
}
function removeDraft(id,stamp=null){
  if(!id)return;
  try{const data=readDrafts();if(!data.entries[id]||stamp&&data.entries[id].stamp!==stamp)return;delete data.entries[id];localStorage.setItem(storageKey(),JSON.stringify(data));refreshDraftCount();}
  catch(e){draftFailure(e);}
}
function stationDraftKey(){return state.platform&&state.station?`station:${state.platform.name}:${state.station.index}`:null;}
function stationDraftSaved(){
  try{return !!stationHistory?.stamp&&readDrafts().entries[stationDraftKey()]?.stamp===stationHistory.stamp;}catch{return false;}
}
function clearStationDraft(){if(stationHistory?.stamp)removeDraft(stationDraftKey(),stationHistory.stamp);}
function saveStationDraft(){
  if(!state.station||!stationHistory)return;
  if(!dirty()){clearStationDraft();stationHistory.stamp=null;return;}
  stationHistory.stamp=writeDraft(stationDraftKey(),{kind:'station',platform:state.platform.name,index:state.station.index,name:state.station.name,
    revision:state.station.revision,dictionary_revision:state.data.dictionary_revision,...changes()});
}
function stationEdited(){if(!stationHistory)initStationHistory();pushHistory(stationHistory,stationSnapshot());saveStationDraft();}
function clearPresetDraft(){const p=state.presets;if(p?.history?.stamp)removeDraft(p.recoveryKey,p.history.stamp);}
function presetDraftSaved(){const p=state.presets;try{return !!p?.history?.stamp&&readDrafts().entries[p.recoveryKey]?.stamp===p.history.stamp;}catch{return false;}}
function savePresetDraft(){
  const p=state.presets;if(!p?.draft||!p.history)return;
  if(!presetDirty()){clearPresetDraft();p.history.stamp=null;return;}
  p.history.stamp=writeDraft(p.recoveryKey,{kind:'preset',platform:state.platform.name,draft:p.draft,asNew:p.asNew,
    source:p.source?.name||null,source_revision:p.source?.revision||null,catalog_revision:p.catalog.catalog_revision,
    stations:p.catalog.stations.map(s=>({index:s.index,name:s.name}))});
}
function presetEdited(group=null){const p=state.presets;if(!p?.history)return;pushHistory(p.history,presetSnapshot(p),group);savePresetDraft();updatePresetHistoryButtons();}
function stationUndo(redo=false){
  if(state.busy||!stationHistory)return;const snapshot=stepHistory(stationHistory,redo);if(snapshot===null)return;
  state.selected=new Set(JSON.parse(snapshot));state.ticket=null;saveStationDraft();updateDraft();mountRows();
}
function presetUndo(redo=false){
  const p=state.presets;if(!p||p.busy||!p.history)return;const snapshot=stepHistory(p.history,redo);if(snapshot===null)return;
  const value=JSON.parse(snapshot);p.asNew=value.asNew;p.draft=value.draft;if(p.draft.fuel===null)p.draft.fuel=NaN;
  presetFields();savePresetDraft();updatePresetHistoryButtons();
}
$('station-undo').addEventListener('click',()=>stationUndo());$('station-redo').addEventListener('click',()=>stationUndo(true));
$('preset-undo').addEventListener('click',()=>presetUndo());$('preset-redo').addEventListener('click',()=>presetUndo(true));
document.addEventListener('keydown',e=>{
  if(!(e.ctrlKey||e.metaKey)||e.key.toLowerCase()!=='z'||e.altKey)return;
  if(e.target.matches('textarea,input:not([type="checkbox"]):not([type="radio"]),[contenteditable="true"]'))return;
  const dialogs=[...document.querySelectorAll('dialog[open]')];
  if(dialogs.length&&dialogs.at(-1).id!=='preset-dialog')return;e.preventDefault();
  if($('preset-dialog').open)presetUndo(e.shiftKey);else stationUndo(e.shiftKey);
});
function draftsError(message=''){$('drafts-error').textContent=message;$('drafts-error').classList.toggle('hidden',!message);}
function draftList(){
  draftsError();$('drafts-list').replaceChildren();
  try{
    const entries=Object.entries(readDrafts().entries).sort((a,b)=>b[1].updated-a[1].updated);
    for(const [id,entry] of entries){
      const row=el('section','draft-recovery-row'),copy=el('div');
      copy.append(el('strong','',entry.kind==='station'?`${entry.platform} / ${entry.index} · ${entry.name}`:`${entry.platform} / ${entry.draft.name}`),el('small','',`${entry.kind==='station'?'Station whitelist':'Loadout preset'} · ${new Date(entry.updated).toLocaleString()}`));
      if(entry.kind==='station')copy.append(el('small','',`${entry.add.length} additions · ${entry.remove.length} removals`));
      const actions=el('div','draft-recovery-actions'),recover=el('button','quiet','Recover'),discard=el('button','text-button','Delete recovery copy');
      recover.dataset.draftId=id;recover.addEventListener('click',()=>recoverDraft(id));
      discard.addEventListener('click',()=>{if(window.confirm('Delete this saved recovery copy?')){removeDraft(id,entry.stamp);draftList();}});
      actions.append(recover,discard);row.append(copy,actions);$('drafts-list').append(row);
    }
    if(!entries.length)$('drafts-list').append(el('p','empty','No saved drafts for this data folder.'));
  }catch(e){draftsError(e.message);}
}
function adoptRecoveryData(data){
  state.data=data;initCategoryFilters();updateBulkRecoveryButton();refreshDraftCount();
  $('platform-total').textContent=data.platforms.length;$('station-total').textContent=data.platforms.reduce((n,p)=>n+p.stations.length,0);
  $('mount-total').textContent=data.weapons.length;$('preset-total').textContent=data.presets;
  const owner=$('owner-filter').value,owners=[...new Set(data.weapons.map(w=>w.owner))].sort();
  $('owner-filter').replaceChildren(new Option('All owners',''),...owners.map(o=>new Option(o,o)));if(owners.includes(owner))$('owner-filter').value=owner;
}
async function recoverDraft(id){
  if(draftDialogBusy||state.busy||!mayLeave())return;draftDialogBusy=true;draftsError();setBusy(true);
  $('drafts-dialog').querySelectorAll('button').forEach(n=>n.disabled=true);
  try{
    const entry=readDrafts().entries[id];if(!entry)throw new Error('This draft was removed in another tab. Refresh the draft list.');
    const data=await api('/api/bootstrap');if(data.root!==state.data.root)throw new Error('The data folder changed. Reload ALIS.');
    const platform=data.platforms.find(p=>p.name===entry.platform);if(!platform)throw new Error('The platform is absent from the current dictionary. The draft has been retained.');
    if(entry.kind==='station'){
      const station=await api(`/api/platforms/${encodeURIComponent(platform.name)}/stations/${entry.index}`);
      if(station.name!==entry.name)throw new Error('Station metadata changed. The saved draft has been retained for inspection.');
      const changed=station.revision!==entry.revision||data.dictionary_revision!==entry.dictionary_revision;
      if(changed&&!window.confirm('The station or dictionary changed since this draft. Reapply its additions/removals to the current station, then review before saving?'))return;
      adoptRecoveryData(data);state.platform=platform;applyStation(station);stationHistory.stamp=entry.stamp;
      for(const key of entry.remove){
        let rowId=state.keyRows.get(key);
        if(!rowId){let row=state.rows.find(w=>w.key===key);if(!row){const aliases=state.rows.filter(w=>w.asset===key);if(aliases.length===1)row=aliases[0];}rowId=row?.id;}
        if(rowId)state.selected.delete(rowId);
      }
      for(const key of entry.add){
        let row=state.rows.find(w=>w.key===key);if(!row){const aliases=state.rows.filter(w=>w.asset===key);if(aliases.length===1)row=aliases[0];}
        if(!row){row={id:`u:${key}`,key,name:key,owner:'Unresolved',ammo:0,unknown:true};state.rows.push(row);}
        state.selected.add(row.id);
      }
      stationEdited();updateDraft();mountRows();platformList();$('drafts-dialog').close();notice(`Station draft recovered.${changed?' It was reapplied to current files; review its changes carefully.':''}`);
    }else{
      const base=`/api/platforms/${encodeURIComponent(platform.name)}/presets`,catalog=await api(base),source=entry.source?await api(base+'/'+encodeURIComponent(entry.source)):null;
      if(source&&source.catalog_revision!==catalog.catalog_revision)throw new Error('Preset catalog changed while loading. Try recovery again.');
      if(entry.stations.length!==catalog.stations.length||entry.stations.some(s=>!catalog.stations.some(t=>t.index===s.index&&t.name===s.name)))throw new Error('Preset station names/order changed. The draft has been retained for inspection.');
      const changed=catalog.catalog_revision!==entry.catalog_revision||(source?.revision||null)!==entry.source_revision;
      if(changed&&!window.confirm('The source preset or station whitelists changed since this draft. Recover its choices against current files, then review before saving?'))return;
      const ready=platform.stations.find(s=>s.ready);if(!ready)throw new Error('No station is ready on this platform.');
      const station=await api(`/api/platforms/${encodeURIComponent(platform.name)}/stations/${ready.index}`);
      adoptRecoveryData(data);state.platform=platform;applyStation(station);platformList();
      state.presets={catalog,busy:false};applyPreset(source);state.presets.recoveryKey=id;state.presets.history.stamp=entry.stamp;
      state.presets.asNew=entry.asNew;state.presets.draft=JSON.parse(JSON.stringify(entry.draft));if(state.presets.draft.fuel===null)state.presets.draft.fuel=NaN;
      presetFields();presetEdited();$('preset-platform').textContent=`${platform.display_name} (${platform.name})`;
      $('drafts-dialog').close();$('preset-dialog').showModal();notice(`Preset draft recovered.${changed?' Current source/whitelists were loaded; review before saving.':''}`);
    }
  }catch(e){draftsError(e.message);}finally{draftDialogBusy=false;$('drafts-dialog').querySelectorAll('button').forEach(n=>n.disabled=false);setBusy(false);if(state.presets)updatePresetHistoryButtons();}
}
$('drafts-open').addEventListener('click',()=>{draftList();$('drafts-dialog').showModal();});
function closeDrafts(){if(!draftDialogBusy)$('drafts-dialog').close();}
$('drafts-close').addEventListener('click',closeDrafts);$('drafts-done').addEventListener('click',closeDrafts);
$('drafts-dialog').addEventListener('cancel',e=>{if(draftDialogBusy)e.preventDefault();});
window.addEventListener('storage',e=>{if(e.key===storageKey()){refreshDraftCount();if($('drafts-dialog').open&&!draftDialogBusy)draftList();}});
