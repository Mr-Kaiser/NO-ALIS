'use strict';
let categoryEditor=null;
const categoryAxes={weapon:['role','type','guidance'],platform:['type','role']};
const axisNames={role:'Role',type:'Type',guidance:'Guidance'};
function categorySearch(category,kind){
  const options=state.data?.category_options?.[kind]||{};
  return Object.entries(category?.tags||{}).flatMap(([axis,tags])=>tags.map(tag=>`${tag} ${options[axis]?.[tag]||''}`)).join(' ');
}
function categoryBadges(category,kind){
  const group=el('span','category-badges');group.title=category?.source||'Unclassified';
  for(const axis of categoryAxes[kind])for(const tag of category?.tags?.[axis]||[]){
    const label=state.data.category_options[kind][axis][tag];
    const badge=el('span',`category-badge ${axis}`,kind==='platform'?label:tag);badge.title=`${label} · ${category.source}`;group.append(badge);
  }
  if(!group.children.length)group.append(el('span','category-unclassified','Unclassified'));
  return group;
}
function matchesCategories(category,kind){
  return categoryAxes[kind].every(axis=>{
    const value=$(`${kind}-${axis}-filter`).value,tags=category?.tags?.[axis]||[];
    return !value||(value==='__unclassified'?tags.length===0:tags.includes(value));
  });
}
function initCategoryFilters(){
  for(const kind of Object.keys(categoryAxes))for(const axis of categoryAxes[kind]){
    const select=$(`${kind}-${axis}-filter`),previous=select.value;
    const options=state.data.category_options[kind][axis];
    select.replaceChildren(new Option(`All ${axis==='type'?'types':axis==='role'?'roles':'guidance'}`,''),
      ...Object.entries(options).map(([tag,name])=>new Option(kind==='weapon'?`${tag} · ${name}`:name,tag)),
      new Option('Unclassified','__unclassified'));
    if([...select.options].some(o=>o.value===previous))select.value=previous;
  }
}
for(const kind of Object.keys(categoryAxes)){
  for(const axis of categoryAxes[kind])$(`${kind}-${axis}-filter`).addEventListener('change',()=>{if(state.data)(kind==='weapon'?mountRows:platformList)();});
  $(`${kind}-filter-clear`).addEventListener('click',()=>{
    for(const axis of categoryAxes[kind])$(`${kind}-${axis}-filter`).value='';
    $(`${kind}-search`).value='';
    if(kind==='weapon'){
      $('owner-filter').value='';state.filter='all';
      document.querySelectorAll('[data-filter]').forEach(t=>{const active=t.dataset.filter==='all';t.classList.toggle('active',active);t.setAttribute('aria-pressed',String(active));});
    }
    if(state.data)(kind==='weapon'?mountRows:platformList)();
  });
}
function categoryItems(kind){return kind==='weapon'?state.data.weapons:state.data.platforms;}
function itemKey(kind,item){return kind==='weapon'?item.key:item.name;}
function itemLabel(kind,item){return kind==='weapon'?`${item.name} · ${item.key} · ${item.owner}`:`${item.display_name} · ${item.name}`;}
function categoryDirty(){return !!categoryEditor&&JSON.stringify(categoryEditor.draft)!==categoryEditor.base;}
function categoryMayLeave(){return !categoryDirty()||window.confirm('Discard the unsaved category labels?');}
function categoryError(message=''){$('category-error').textContent=message;$('category-error').classList.toggle('hidden',!message);}
function categoryPicker(){
  const c=categoryEditor,term=$('category-search').value.toLowerCase();
  const items=categoryItems(c.kind).filter(item=>item===c.item||itemLabel(c.kind,item).toLowerCase().includes(term));
  $('category-item').replaceChildren(...items.map(item=>new Option(itemLabel(c.kind,item),itemKey(c.kind,item))));
  $('category-item').value=itemKey(c.kind,c.item);
}
function categoryFields(){
  const c=categoryEditor;categoryError();$('category-groups').replaceChildren();
  for(const axis of categoryAxes[c.kind]){
    const group=el('fieldset'),legend=el('legend','',axisNames[axis]);group.append(legend);
    for(const [tag,name] of Object.entries(state.data.category_options[c.kind][axis])){
      const label=el('label','category-choice'),input=el('input');input.type='checkbox';input.dataset.axis=axis;input.dataset.tag=tag;input.checked=c.draft.tags[axis].includes(tag);
      input.addEventListener('change',()=>{
        c.draft.mode='custom';c.draft.tags[axis]=[...group.querySelectorAll('input:checked')].map(n=>n.dataset.tag);categoryStatus();
      });
      label.append(input,el('span','',c.kind==='weapon'?`${tag} · ${name}`:name));group.append(label);
    }
    $('category-groups').append(group);
  }
  categoryStatus();
}
function categoryStatus(){
  const c=categoryEditor;
  const source=c.draft.mode==='auto'?(categoryDirty()?'Automatic labels will be restored on save.':c.item.categories.source):(categoryDirty()?'Custom labels · Unsaved edits':c.item.categories.source);
  $('category-source').textContent=source+(c.item.categories.stale_override?' · Previous labels were ignored because the dictionary item changed.':'');
}
function categorySelect(kind,key){
  const item=categoryItems(kind).find(item=>itemKey(kind,item)===key)||categoryItems(kind)[0];
  const draft={mode:item.categories.custom?'custom':'auto',tags:JSON.parse(JSON.stringify(item.categories.tags))};
  categoryEditor={kind,item,draft,base:JSON.stringify(draft),revision:state.data.categories_revision,busy:false};
  $('category-kind').value=kind;categoryPicker();categoryFields();
}
function openCategories(kind='weapon',key){
  if(state.busy||!state.data)return;
  $('category-search').value='';categorySelect(kind,key);$('category-dialog').showModal();
}
function closeCategories(){if(categoryEditor?.busy||!categoryMayLeave())return;categoryEditor=null;$('category-dialog').close();}
$('categories-open').addEventListener('click',()=>openCategories());
$('platform-tags-edit').addEventListener('click',()=>openCategories('platform',state.platform.name));
$('category-search').addEventListener('input',categoryPicker);
$('category-kind').addEventListener('change',()=>{
  if(!categoryMayLeave()){$('category-kind').value=categoryEditor.kind;return;}
  $('category-search').value='';categorySelect($('category-kind').value);
});
$('category-item').addEventListener('change',()=>{
  if(!categoryMayLeave()){$('category-item').value=itemKey(categoryEditor.kind,categoryEditor.item);return;}
  categorySelect(categoryEditor.kind,$('category-item').value);
});
$('category-auto').addEventListener('click',()=>{
  categoryEditor.draft={mode:'auto',tags:JSON.parse(JSON.stringify(categoryEditor.item.categories.automatic))};categoryFields();
});
$('category-close').addEventListener('click',closeCategories);$('category-cancel').addEventListener('click',closeCategories);
$('category-dialog').addEventListener('cancel',e=>{e.preventDefault();closeCategories();});
$('category-save').addEventListener('click',async()=>{
  const c=categoryEditor;if(!c||c.busy)return;c.busy=true;categoryError();
  const controls=[...$('category-dialog').querySelectorAll('button,input,select')];controls.forEach(n=>n.disabled=true);setBusy(true);
  try{
    const r=await api('/api/categories',{kind:c.kind,key:itemKey(c.kind,c.item),identity:c.item.categories.identity,revision:c.revision,tags:c.draft.mode==='auto'?null:c.draft.tags});
    c.item.categories=r.categories;state.data.categories_revision=r.revision;
    if(c.kind==='weapon')for(const row of state.rows)if(row.key===c.item.key&&!row.unknown)row.categories=r.categories;
    categoryEditor=null;$('category-dialog').close();platformList();if(state.platform)stationList();mountRows();
    notice(`Categories saved for ${c.kind==='weapon'?c.item.name:c.item.display_name}.${r.backup?` Backup: ${r.backup}`:''}`);
  }catch(e){categoryError(e.message+' Your category draft is still open.');}
  finally{c.busy=false;controls.forEach(n=>n.disabled=false);setBusy(false);mountRows();}
});
