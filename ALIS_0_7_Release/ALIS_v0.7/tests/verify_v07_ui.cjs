// New v0.7 DOM workflows over real Flask HTTP. Dialogs are stubbed, not rendered.
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{JSDOM,VirtualConsole}=require('jsdom');
const source=process.argv[2];if(!source){console.error('Usage: node tests/verify_v07_ui.cjs PATH_TO_PRESET_LOADOUT');process.exit(2);}
const codeRoot=path.resolve(__dirname,'..'),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'alis-v07-ui-'));
const testRoot=path.join(temporary,'preset-loadout');fs.cpSync(path.resolve(source),testRoot,{recursive:true});
const base='http://127.0.0.1:5054';
const server=spawn(process.env.ALIS_TEST_PYTHON||'python',[path.join(codeRoot,'app.py'),testRoot,'--port','5054','--no-browser'],{stdio:['ignore','pipe','pipe']});
let output='';server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);server.on('error',e=>output+=e);
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(pred,label='UI state'){for(let i=0;i<250;i++){if(pred())return;await pause(20);}throw new Error('Timed out: '+label);}
const script=['app.js','categories.js','bulk.js','drafts.js','extras.js'].map(n=>fs.readFileSync(path.join(codeRoot,'static',n),'utf8')).join('\n');
const windows=[];let dom,w,d,$,confirmValue=true,confirmCount=0,errors=[];
const click=id=>{const n=typeof id==='string'?$(id):id;assert(n,'Missing control '+id);assert(!n.disabled,'Disabled control '+id);if(typeof n.click==='function')n.click();else n.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));};
const type=(id,value)=>{const n=$(id);n.value=value;n.dispatchEvent(new w.Event('input',{bubbles:true}));};
const choose=(id,value)=>{const n=typeof id==='string'?$(id):id;n.value=value;n.dispatchEvent(new w.Event('change',{bubbles:true}));};
const check=(node,value)=>{assert(node,'Missing checkbox');node.checked=value;node.dispatchEvent(new w.Event('change',{bubbles:true}));};
const mount=key=>[...d.querySelectorAll('.weapon-row input')].find(n=>n.getAttribute('aria-label').endsWith(`(${key})`));
const stored=()=>Object.fromEntries(Array.from({length:w.localStorage.length},(_,i)=>{const k=w.localStorage.key(i);return [k,w.localStorage.getItem(k)];}));
function entries(){const raw=Object.values(stored()).find(v=>v.includes('"entries"'));return raw?JSON.parse(raw).entries:{};}
async function boot(storage={}){
  if(dom)dom.window.close();
  const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  dom=new JSDOM(await(await fetch(base)).text(),{url:base,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:console});windows.push(dom.window);
  w=dom.window;d=w.document;$=id=>d.getElementById(id);
  for(const [k,v] of Object.entries(storage))w.localStorage.setItem(k,v);
  w.confirm=()=>{confirmCount++;return confirmValue;};w.fetch=(p,o={})=>fetch(new URL(p,base),o);
  w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
  w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
  w.eval(script);await until(()=>$('draft-status').textContent==='SYNCED','bootstrap');
}
async function station(i){click(d.querySelector(`#platform-map .map-marker[data-station="${i}"]`));await until(()=>$('station-kicker').textContent.endsWith(String(i).padStart(2,'0'))&&!$('reload-all').disabled,'select station');}
async function recover(kind){
  click('drafts-open');const row=[...d.querySelectorAll('.draft-recovery-row')].find(r=>r.textContent.includes(kind==='station'?'Station whitelist':'Loadout preset'));
  assert(row,'Missing '+kind+' recovery row');click(row.querySelector('button'));
  await until(()=>!$('drafts-dialog').open||!$('drafts-error').classList.contains('hidden')||!$('drafts-done').disabled,'recover '+kind);
}
async function layout(){click('edit-layout');await until(()=>$('layout-dialog').open&&!$('layout-reference').disabled,'load references');}
const gameFiles=()=>{const result={};function walk(folder){for(const e of fs.readdirSync(folder,{withFileTypes:true})){if(e.name==='.alis')continue;const p=path.join(folder,e.name);if(e.isDirectory())walk(p);else if(!e.name.endsWith('.bak'))result[path.relative(testRoot,p)]=fs.readFileSync(p).toString('base64');}}walk(testRoot);return result;};
(async()=>{
  let ready=false;for(let i=0;i<100;i++){try{if((await fetch(base)).ok){ready=true;break;}}catch{}await pause(50);}assert(ready,output);
  const initial=gameFiles(),paths={};for(let i=0;i<3;i++){const folder=path.join(testRoot,'CAS1',`weaponstation${i}`);paths[i]=path.join(folder,fs.readdirSync(folder).find(n=>n.endsWith('.json')));}
  const original=Object.fromEntries(Object.entries(paths).map(([i,p])=>[i,fs.readFileSync(p)]));
  await boot();assert(d.querySelector('#platform-map image').getAttribute('href').startsWith('data:image/webp;base64,'));
  await station(1);type('weapon-search','AAM1_single');assert(!mount('AAM1_single').checked);check(mount('AAM1_single'),true);
  assert.equal($('drafts-count').textContent,'1');assert.equal($('draft-status').textContent,'DRAFT');assert.deepEqual(gameFiles(),initial);
  click('station-undo');assert(!mount('AAM1_single').checked);assert.equal($('drafts-count').textContent,'0');
  click('station-redo');assert(mount('AAM1_single').checked);assert.equal($('drafts-count').textContent,'1');
  const copy=stored();await boot(copy);assert.equal($('drafts-count').textContent,'1');await recover('station');
  await until(()=>$('station-name').textContent==='Center Pylon'&&$('draft-status').textContent==='DRAFT','recovered whitelist');
  type('weapon-search','AAM1_single');assert(mount('AAM1_single').checked);assert.deepEqual(gameFiles(),initial);
  click('station-undo');assert.equal($('draft-status').textContent,'SYNCED');click('station-redo');
  click('bulk-open');await until(()=>$('bulk-dialog').open,'bulk catalog');
  assert.equal(d.querySelectorAll('#bulk-stations input').length,9);assert.equal(d.querySelectorAll('#bulk-stations input:checked').length,1);
  check(d.querySelector('#bulk-stations input[data-index="0"]'),true);click('bulk-preview');await until(()=>!$('bulk-save').disabled,'bulk review');
  assert.equal(d.querySelectorAll('.bulk-review-station').length,2);assert.deepEqual(gameFiles(),initial);
  click('bulk-save');await until(()=>!$('bulk-dialog').open&&$('draft-status').textContent==='SYNCED','bulk save');
  assert.equal($('drafts-count').textContent,'0');
  for(const i of [0,1]){
    assert(JSON.parse(fs.readFileSync(paths[i],'utf8')).allowedWeapons.includes('AAM1_single'));
    const backups=fs.readdirSync(path.dirname(paths[i])).filter(n=>n.endsWith('.bak'));assert.equal(backups.length,1);
    assert(fs.readFileSync(path.join(path.dirname(paths[i]),backups[0])).equals(original[i]));
  }
  assert(fs.readFileSync(paths[2]).equals(original[2]));
  // Conflict between review and commit writes none of the reviewed targets.
  type('weapon-search','AAM2_single');check(mount('AAM2_single'),true);click('bulk-open');await until(()=>$('bulk-dialog').open);
  check(d.querySelector('#bulk-stations input[data-index="0"]'),true);click('bulk-preview');await until(()=>!$('bulk-save').disabled);
  const one=fs.readFileSync(paths[1]),outside=Buffer.concat([fs.readFileSync(paths[0]),Buffer.from('\n')]);fs.writeFileSync(paths[0],outside);
  click('bulk-save');await until(()=>!$('bulk-error').classList.contains('hidden')&&!$('reload-all').disabled,'bulk conflict');
  assert(fs.readFileSync(paths[0]).equals(outside));assert(fs.readFileSync(paths[1]).equals(one));assert.equal($('draft-status').textContent,'DRAFT');
  click('bulk-cancel');click('discard');assert.equal($('drafts-count').textContent,'0');
  // Excluding the source saves only the selected target and retains its draft.
  type('weapon-search','AAM2_single');check(mount('AAM2_single'),true);click('bulk-open');await until(()=>$('bulk-dialog').open);
  click('bulk-none');check(d.querySelector('#bulk-stations input[data-index="2"]'),true);click('bulk-preview');await until(()=>!$('bulk-save').disabled);
  click('bulk-save');await until(()=>!$('bulk-dialog').open&&!$('reload-all').disabled);
  assert.equal($('draft-status').textContent,'DRAFT');assert.equal($('drafts-count').textContent,'1');assert(fs.readFileSync(paths[1]).equals(one));
  assert(JSON.parse(fs.readFileSync(paths[2],'utf8')).allowedWeapons.includes('AAM2_single'));click('discard');
  for(const [i,p] of Object.entries(paths))fs.writeFileSync(p,original[i]);click('reload-all');await until(()=>$('station-name').textContent==='Internal 35mm Autocannons'&&!$('reload-all').disabled);
  assert.deepEqual(gameFiles(),initial);
  // References stay local; changing views retains markers until a full default reset.
  await layout();assert.equal($('layout-reference').options.length,3);
  const markerBefore=d.querySelector('#layout-canvas .map-marker').getAttribute('transform');
  choose('layout-reference','front');assert(d.querySelector('#layout-canvas image').getAttribute('href').startsWith('data:image/png;base64,'));
  assert.equal(d.querySelector('#layout-canvas .map-marker').getAttribute('transform'),markerBefore);assert(!$('layout-verified').checked);
  click('cancel-layout');assert.deepEqual(gameFiles(),initial);assert(!fs.existsSync(path.join(testRoot,'.alis/platforms.json')));
  await layout();click('remove-image');click('save-layout');await until(()=>!$('layout-dialog').open,'save custom layout');
  assert(!d.querySelector('#platform-map image').getAttribute('href').startsWith('data:'));
  const customRaw=fs.readFileSync(path.join(testRoot,'.alis/platforms.json'));
  await boot(stored());assert(!d.querySelector('#platform-map image').getAttribute('href').startsWith('data:'));
  await layout();click('layout-default');await until(()=>$('layout-image-status').textContent.includes('Reference image')&&!$('save-layout').disabled,'use default');
  assert(fs.readFileSync(path.join(testRoot,'.alis/platforms.json')).equals(customRaw));click('save-layout');await until(()=>!$('layout-dialog').open);
  assert(d.querySelector('#platform-map image').getAttribute('href').startsWith('data:image/webp;base64,'));assert.deepEqual(gameFiles(),initial);
  click([...d.querySelectorAll('.platform-item')].find(n=>n.textContent.includes('Medusa')));await until(()=>$('platform-id').textContent==='EW1'&&!$('reload-all').disabled);
  assert.equal(d.querySelector('#platform-map svg').getAttribute('viewBox'),'100 200 800 800');
  await layout();choose('layout-reference','plate');assert(!d.querySelector('#layout-canvas svg'));click('layout-default');await until(()=>d.querySelector('#layout-canvas svg')&&!$('save-layout').disabled);
  click('save-layout');await until(()=>!$('layout-dialog').open);assert.deepEqual(JSON.parse(fs.readFileSync(path.join(testRoot,'.alis/platforms.json'))).platforms.EW1.image_crop,[.1,.2,.8,.8]);
  // Preset changes persist through a new page, and history never writes native files.
  click([...d.querySelectorAll('.platform-item')].find(n=>n.textContent.includes('Brawler')));await until(()=>$('platform-id').textContent==='CAS1'&&!$('reload-all').disabled);
  const native=path.join(testRoot,'CAS1/DEFAULT.preset'),nativeRaw=fs.readFileSync(native);
  click('presets-open');await until(()=>$('preset-dialog').open,'preset open');click('preset-copy');type('preset-name','ALIS v07 recovered');type('preset-fuel','55');type('preset-livery','v07-test');
  assert.equal($('drafts-count').textContent,'1');click('preset-undo');assert.notEqual($('preset-livery').value,'v07-test');click('preset-redo');assert.equal($('preset-livery').value,'v07-test');
  assert(fs.readFileSync(native).equals(nativeRaw));click('preset-cancel');await boot(stored());await recover('preset');await until(()=>$('preset-dialog').open,'preset recovery');
  assert.equal($('preset-name').value,'ALIS v07 recovered');assert.equal($('preset-fuel').value,'55');assert.equal($('preset-livery').value,'v07-test');
  click('preset-undo');assert.equal($('preset-name').value,'DEFAULT');click('preset-redo');assert.equal($('preset-name').value,'ALIS v07 recovered');
  click('preset-review-button');await until(()=>!$('preset-save').disabled,'preset review');click('preset-save');await until(()=>$('drafts-count').textContent==='0'&&!$('preset-review-button').disabled,'preset save');
  const recovered=JSON.parse(fs.readFileSync(path.join(testRoot,'CAS1/ALIS v07 recovered.preset'),'utf8'));assert.equal(recovered.Fuel,.55);assert.equal(recovered.Livery,'v07-test');assert(fs.readFileSync(native).equals(nativeRaw));click('preset-cancel');
  // Changed station recovery requires an explicit choice and retains outside bytes.
  await station(1);type('weapon-search','AAM1_single');check(mount('AAM1_single'),true);const recoveryCopy=stored();
  const newer=Buffer.concat([original[1],Buffer.from('\n')]);fs.writeFileSync(paths[1],newer);await boot(recoveryCopy);confirmValue=false;
  await recover('station');assert($('drafts-dialog').open);assert.equal($('drafts-count').textContent,'1');assert(fs.readFileSync(paths[1]).equals(newer));
  confirmValue=true;click(d.querySelector('.draft-recovery-row button'));await until(()=>!$('drafts-dialog').open&&!$('reload-all').disabled);type('weapon-search','AAM1_single');assert(mount('AAM1_single').checked);assert(fs.readFileSync(paths[1]).equals(newer));click('discard');
  // Storage failure surfaces an indicator while normal reviewed saves still work.
  const realSet=w.Storage.prototype.setItem;w.Storage.prototype.setItem=function(){throw new Error('quota full');};
  check(mount('AAM1_single'),true);assert.equal($('drafts-count').textContent,'!');assert(!$('review').disabled);assert($('drafts-open').title.includes('quota full'));
  w.Storage.prototype.setItem=realSet;click('discard');assert(fs.readFileSync(paths[1]).equals(newer));
  assert(confirmCount>=3);assert.deepEqual(errors,[]);
  console.log('PASS: v0.7 real-HTTP DOM: station Undo/Redo; stored drafts through page restart; changed-file recovery decline/accept; bulk review/save/exact backups/conflict/source exclusion; paired markers select one file; storage quota failure.');
  console.log('PASS: bundled top/front references; custom profiles survive restart; explicit default reset/save; Medusa crop persistence; preset Undo/Redo/recovery/review/save with original preset bytes retained.');
  console.log('Rendering, image decoding, pointer geometry and native dialogs are not covered by jsdom.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{for(const window of windows)window.close();server.kill('SIGINT');server.once('exit',()=>fs.rmSync(temporary,{recursive:true,force:true}));});
