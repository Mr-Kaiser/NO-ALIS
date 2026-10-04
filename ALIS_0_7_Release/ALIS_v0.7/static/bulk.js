'use strict';
let bulkEditor=null,bulkRecovery=null,bulkRecoveryBusy=false;
function bulkError(message=''){$('bulk-error').textContent=message;$('bulk-error').classList.toggle('hidden',!message);}
function bulkBusy(value){
  if(!bulkEditor)return;bulkEditor.busy=value;setBusy(value);$('bulk-dialog').querySelectorAll('button,input').forEach(n=>n.disabled=value);
  if(!value)document.querySelectorAll('#bulk-stations input').forEach(n=>n.disabled=n.dataset.ready!=='true');
  $('bulk-save').disabled=value||!bulkEditor.ticket;
}
function editBulk(){
  const b=bulkEditor;if(!b)return;b.ticket=null;$('bulk-editor').classList.remove('hidden');$('bulk-review').classList.add('hidden');
  $('bulk-preview').classList.remove('hidden');$('bulk-save').classList.add('hidden');$('bulk-back').classList.add('hidden');
}
function bulkTargets(){return [...$('bulk-stations').querySelectorAll('input:checked')].map(n=>Number(n.dataset.index));}
async function openBulk(){
  if(state.busy||!state.station||!dirty())return;
  setBusy(true);bulkError();
  try{
    const catalog=await api(`/api/platforms/${encodeURIComponent(state.platform.name)}/bulk-catalog`);
    bulkEditor={catalog,patch:changes(),source:{index:state.station.index,revision:state.station.revision},ticket:null,busy:false};
    $('bulk-description').textContent=`${state.platform.display_name} · Add/remove the pending mounts on each selected station. Each row represents one station file, including groups with multiple map markers.`;
    $('bulk-patch').replaceChildren(...bulkEditor.patch.add.map(k=>el('p','review-change add',`+ ${k}`)),...bulkEditor.patch.remove.map(k=>el('p','review-change remove',`− ${k}`)));
    $('bulk-stations').replaceChildren();
    catalog.stations.forEach(s=>{
      const row=el('label','bulk-station'),input=el('input');input.type='checkbox';input.dataset.index=s.index;input.dataset.ready=String(s.ready);input.disabled=!s.ready;input.checked=s.ready&&s.index===state.station.index;
      const copy=el('span');copy.append(el('strong','',`${String(s.index).padStart(2,'0')} / ${s.name}`),el('small','',s.ready?`${s.count} allowed mounts${s.symmetry?` · group ${s.symmetry}`:''}`:s.error));
      input.addEventListener('change',editBulk);row.append(input,copy);$('bulk-stations').append(row);
    });
    $('bulk-allow-empty').checked=false;editBulk();$('bulk-dialog').showModal();
  }catch(e){notice(e.message,'error');bulkEditor=null;}finally{if(bulkEditor)bulkBusy(false);else setBusy(false);}
}
function closeBulk(){if(bulkEditor?.busy)return;$('bulk-dialog').close();bulkEditor=null;}
$('bulk-open').addEventListener('click',openBulk);
['bulk-close','bulk-cancel'].forEach(id=>$(id).addEventListener('click',closeBulk));
$('bulk-dialog').addEventListener('cancel',e=>{e.preventDefault();closeBulk();});
$('bulk-back').addEventListener('click',editBulk);$('bulk-allow-empty').addEventListener('change',editBulk);
for(const [id,mode] of [['bulk-all','all'],['bulk-none','none'],['bulk-symmetry','symmetry']])$(id).addEventListener('click',()=>{
  const source=bulkEditor.catalog.stations.find(s=>s.index===bulkEditor.source.index);
  document.querySelectorAll('#bulk-stations input').forEach(n=>{const row=bulkEditor.catalog.stations.find(s=>s.index===Number(n.dataset.index));n.checked=row.ready&&(mode==='all'||mode==='symmetry'&&(row.index===source.index||source.symmetry&&row.symmetry===source.symmetry));});editBulk();
});
$('bulk-preview').addEventListener('click',async()=>{
  const b=bulkEditor;if(!b||b.busy)return;const indices=bulkTargets();if(!indices.length){bulkError('Choose at least one station.');return;}
  bulkBusy(true);bulkError();
  try{
    const result=await api(`/api/platforms/${encodeURIComponent(state.platform.name)}/bulk-preview`,{
      ...b.patch,source:b.source,dictionary_revision:b.catalog.dictionary_revision,
      targets:indices.map(i=>({index:i,revision:b.catalog.stations.find(s=>s.index===i).revision})),allow_empty:$('bulk-allow-empty').checked});
    b.ticket=result.ticket;$('bulk-summary').textContent=`${result.changed_count} file(s) will change across ${result.stations.length} reviewed stations. Each changed file receives an exact backup.`;
    $('bulk-changes').replaceChildren();
    result.stations.forEach(s=>{
      const row=el('section','bulk-review-station');row.append(el('strong','',`${String(s.index).padStart(2,'0')} / ${s.name} · ${s.before_count} → ${s.after_count} mounts`),el('small','',s.path));
      for(const k of s.added)row.append(el('p','review-change add',`+ ${k}`));for(const k of s.removed)row.append(el('p','review-change remove',`− ${k}`));
      if(!s.changed)row.append(el('p','subtle','Already matches; no file or backup will be written.'));
      $('bulk-changes').append(row);
    });
    $('bulk-editor').classList.add('hidden');$('bulk-review').classList.remove('hidden');$('bulk-preview').classList.add('hidden');$('bulk-save').classList.remove('hidden');$('bulk-back').classList.remove('hidden');
  }catch(e){bulkError(e.message);}finally{bulkBusy(false);}
});
$('bulk-save').addEventListener('click',async()=>{
  const b=bulkEditor;if(!b||b.busy||!b.ticket)return;const ticket=b.ticket;b.ticket=null;bulkBusy(true);bulkError();
  try{
    const result=await api('/api/bulk-commit',{ticket});
    for(const s of result.stations){const meta=state.platform.stations.find(t=>t.index===s.index);if(meta)meta.allowed_count=s.allowed.length;}
    const current=result.stations.find(s=>s.index===state.station.index);
    if(current){clearStationDraft();applyStation(current);}else stationList();
    $('bulk-dialog').close();bulkEditor=null;notice(`Bulk save verified: ${result.changed_count} station file(s) changed · ${result.backups.length} exact backup(s).${current?'':' The source station draft remains open.'}`);
  }catch(e){
    bulkError(e.message+' Your source station draft remains available. Review again after refreshing the affected files.');
    try{const status=await api('/api/bulk-recovery');state.data.bulk_recovery=status.recovery;updateBulkRecoveryButton();}catch{}
  }finally{if(bulkEditor)bulkBusy(false);else setBusy(false);mountRows();}
});
function updateBulkRecoveryButton(){$('bulk-recovery-open').classList.toggle('hidden',!state.data?.bulk_recovery);}
function recoveryError(message=''){$('bulk-recovery-error').textContent=message;$('bulk-recovery-error').classList.toggle('hidden',!message);}
async function loadBulkRecovery(){
  if(bulkRecoveryBusy)return;bulkRecoveryBusy=true;recoveryError();$('bulk-recovery-save').disabled=true;
  try{
    const result=await api('/api/bulk-recovery');bulkRecovery=result.recovery;state.data.bulk_recovery=bulkRecovery;updateBulkRecoveryButton();$('bulk-recovery-files').replaceChildren();
    if(!bulkRecovery){$('bulk-recovery-files').append(el('p','subtle','No unfinished bulk save.'));return;}
    for(const s of bulkRecovery.stations){const row=el('section','bulk-review-station');row.append(el('strong','',`${bulkRecovery.platform} / ${s.index} · ${s.status==='original'?'Already original':s.status==='changed'?'Batch change — can restore':'Changed outside the batch — inspect'}`),el('small','',s.path),el('small','',`Backup: ${s.backup}`));$('bulk-recovery-files').append(row);}
    if(!bulkRecovery.can_restore)recoveryError('At least one station has outside changes. Those edits are retained. Inspect its listed backup and current file before recovery.');
    $('bulk-recovery-save').disabled=!bulkRecovery.can_restore;
  }catch(e){recoveryError(e.message);}finally{bulkRecoveryBusy=false;}
}
$('bulk-recovery-open').addEventListener('click',()=>{$('bulk-recovery-dialog').showModal();loadBulkRecovery();});
$('bulk-recovery-reload').addEventListener('click',loadBulkRecovery);
$('bulk-recovery-close').addEventListener('click',()=>{if(!bulkRecoveryBusy)$('bulk-recovery-dialog').close();});
$('bulk-recovery-dialog').addEventListener('cancel',e=>{if(bulkRecoveryBusy)e.preventDefault();});
$('bulk-recovery-save').addEventListener('click',async()=>{
  if(!bulkRecovery||bulkRecoveryBusy||!bulkRecovery.can_restore)return;bulkRecoveryBusy=true;$('bulk-recovery-save').disabled=true;setBusy(true);recoveryError();
  try{
    await api('/api/bulk-recovery',{revision:bulkRecovery.revision,stations:Object.fromEntries(bulkRecovery.stations.map(s=>[s.index,s.current_revision]))});
    state.data.bulk_recovery=null;updateBulkRecoveryButton();$('bulk-recovery-dialog').close();
    notice('Bulk originals restored and verified. Reload station data before saving an existing draft.');
  }catch(e){recoveryError(e.message);}finally{bulkRecoveryBusy=false;setBusy(false);}
});
