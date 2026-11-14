'use strict';
const $ = id => document.getElementById(id);
const canvas = $('feed'), ctx = canvas.getContext('2d');
const presets = {'test':'Test pattern','garage':'Garage (simulated)','entry':'Front door (simulated)','offline':'Unavailable camera','parking':'Parking lot (simulated)'};
let cameras = [ {id:'default',name:'Test pattern',preset:'test'}, {id:'garage',name:'Garage',preset:'garage'}, {id:'entry',name:'Front door',preset:'entry'}, {id:'parking',name:'Parking lot (simulated)',preset:'parking'}, {id:'offline',name:'Offline camera',preset:'offline'} ];
let selected='default', paused=false, edit=null, seq=0, photoURL=null, last=0;
const notice = s => $('notice').textContent=s;
const current = () => cameras.find(c=>c.id===selected);
function clearPhoto(){ if(photoURL) URL.revokeObjectURL(photoURL); photoURL=null; $('photo').removeAttribute('src'); $('photo').hidden=true; $('captureEmpty').hidden=false; $('download').hidden=true; $('download').removeAttribute('href'); }
const stills={};for(const [key,source] of Object.entries(demoImages)){const img=new Image();img.src=source;stills[key]=img;}
function draw(t){
 const {width:w,height:h}=canvas, p=current().preset;
 ctx.fillStyle='#101820'; ctx.fillRect(0,0,w,h);
 if(p==='test'){
   ['#d3d3d3','#d8c94e','#54bbbf','#54ba67','#be64b7','#bf4e4b','#4c68ba'].forEach((c,i)=>{ctx.fillStyle=c;ctx.fillRect(i*w/7,0,w/7+1,h*.72);});
   ctx.fillStyle='#25272b';ctx.fillRect(0,h*.72,w,h*.28);
   ctx.fillStyle='#f5f5f5';ctx.fillRect((t*0.13)%(w-60),h*.8,60,16);
 }else if(stills[p]?.complete && stills[p]?.naturalWidth){
   ctx.drawImage(stills[p],0,0,w,h);
 }else if(p==='parking'){
   ctx.fillStyle='#8a979f';ctx.fillRect(0,0,w,h*.36);ctx.fillStyle='#767974';ctx.fillRect(0,h*.36,w,h*.64);
   ctx.fillStyle='#aea99d';ctx.fillRect(0,40,w,140);ctx.fillStyle='#484f51';for(let i=0;i<8;i++){ctx.fillRect(i*118+10,85,94,65);}
   ctx.strokeStyle='#e8e7cd';ctx.lineWidth=3;for(let i=0;i<9;i++){ctx.beginPath();ctx.moveTo(i*120,205);ctx.lineTo(i*135-60,380);ctx.stroke();}
   ['#494f58','#c7c9ca','#8c292e','#b3b0a2','#1e292f','#c8cacf'].forEach((color,i)=>{let x=30+i*150,y=220+(i%2)*28;ctx.fillStyle='#2226';ctx.fillRect(x+9,y+12,95,145);ctx.fillStyle=color;ctx.beginPath();ctx.roundRect(x,y,86,140,14);ctx.fill();ctx.fillStyle='#29343d';ctx.fillRect(x+8,y+22,70,35);ctx.fillRect(x+8,y+94,70,23);ctx.fillStyle='#e4e6de';ctx.fillRect(x+8,y+4,17,7);ctx.fillRect(x+60,y+4,17,7);});
 }else{
   ctx.fillStyle=p==='garage'?'#858782':'#8ca5af';ctx.fillRect(0,0,w,h*.65);
   ctx.fillStyle='#42484a';ctx.beginPath();ctx.moveTo(0,h*.65);ctx.lineTo(w,h*.65);ctx.lineTo(w,h);ctx.lineTo(0,h);ctx.fill();
   ctx.fillStyle='#b4b6ad';ctx.fillRect(w*.13,h*.17,w*.58,h*.49);
   ctx.strokeStyle='#646b6c';ctx.lineWidth=4;
   if(p==='garage'){for(let y=h*.22;y<h*.65;y+=26){ctx.beginPath();ctx.moveTo(w*.13,y);ctx.lineTo(w*.71,y);ctx.stroke();}ctx.fillStyle='#53463a';ctx.fillRect(w*.76,h*.40,w*.2,h*.04);ctx.fillRect(w*.78,h*.44,12,h*.22);}
   else{ctx.fillStyle='#36494e';ctx.fillRect(w*.36,h*.20,w*.28,h*.46);ctx.fillStyle='#b6c8d1';ctx.fillRect(w*.40,h*.25,w*.20,h*.16);ctx.fillStyle='#dfd8a4';ctx.fillRect(w*.59,h*.48,9,9);ctx.fillStyle='#6b805a';ctx.fillRect(w*.79,h*.37,w*.11,h*.28);}
   ctx.fillStyle='#c9aa75';ctx.fillRect((t*.022)%(w-42),h*.80,42,11);
 }
 ctx.fillStyle='#000b';ctx.fillRect(0,h-40,w,40);ctx.font='17px monospace';ctx.fillStyle='#fff';ctx.fillText('SIMULATION  /  '+new Date().toLocaleTimeString(),12,h-14);
}
function frame(t){if(!paused && current().preset!=='offline' && t-last>=1000/15){draw(t);last=t;}requestAnimationFrame(frame);}
function refresh(){const off=current().preset==='offline', live=!off&&!paused; $('feed').hidden=!live;$('empty').hidden=live;$('screenlabel').hidden=!live;$('state').textContent=paused?'Paused':off?'Offline':'Online';$('status').classList.toggle('live',live);$('message').textContent=paused?'Viewing paused':'Simulated camera unavailable';$('snapshot').disabled=!live;$('fps').textContent=live?'15 fps':'—';$('resolution').textContent=off?'—':'960 × 540';$('viewers').textContent=live?'1':'0';$('reconnects').textContent=off?'1':'0';$('mode').textContent='Simulated';$('editCamera').disabled=selected==='default';$('deleteCamera').disabled=selected==='default';if(live)draw(performance.now());}
function list(){ $('cameraSelect').replaceChildren(...cameras.map(c=>new Option(c.name,c.id)));$('cameraSelect').value=selected;refresh(); }
function choose(id){selected=id;clearPhoto();refresh();notice('Selected '+current().name);}
$('cameraSelect').onchange=e=>choose(e.target.value);
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'Resume':'Pause';refresh();};
$('mirror').onclick=()=>{$('mirror').setAttribute('aria-pressed',String(canvas.classList.toggle('mirrored')));};
const viewer=document.querySelector('.viewer');function expand(on){viewer.classList.toggle('expanded',on);$('full').textContent=on?'Exit expanded':'Expand';} $('full').onclick=()=>expand(!viewer.classList.contains('expanded'));document.addEventListener('keydown',e=>{if(e.key==='Escape')expand(false);});
$('snapshot').onclick=()=>{const id=selected;canvas.toBlob(blob=>{if(!blob||selected!==id)return;clearPhoto();photoURL=URL.createObjectURL(blob);$('photo').src=photoURL;$('photo').hidden=false;$('captureEmpty').hidden=true;$('download').href=photoURL;$('download').download='pywcam-demo.jpg';$('download').hidden=false;notice('Simulated photo captured');},'image/jpeg',.85);};
function open(editing){edit=editing?selected:null;$('cameraDialogTitle').textContent=editing?'Edit simulated IP camera':'Add IP camera (simulation)';$('cameraName').value=editing?current().name:'';$('preset').value=editing?current().preset:'parking';$('cameraError').textContent='';$('cameraDialog').showModal();$('cameraName').focus();}
$('addCamera').onclick=()=>open(false);$('editCamera').onclick=()=>open(true);$('cancelCamera').onclick=()=>$('cameraDialog').close();
$('saveCamera').onclick=()=>{const name=$('cameraName').value.trim(),preset=$('preset').value;if(!name||name.length>80){$('cameraError').textContent='Enter a camera name (1–80 characters).';return;}if(!Object.hasOwn(presets,preset)){ $('cameraError').textContent='Choose a simulated source.';return;}if(!edit&&cameras.length>=9){$('cameraError').textContent='Camera limit reached.';return;}const id=edit||'mock-'+(++seq);if(edit){Object.assign(cameras.find(c=>c.id===edit),{name,preset});}else cameras.push({id,name,preset});$('cameraDialog').close();selected=id;clearPhoto();list();notice('Simulated camera saved');};
$('deleteCamera').onclick=()=>{if(selected==='default'||!confirm('Remove this simulated camera?'))return;cameras=cameras.filter(c=>c.id!==selected);selected='default';clearPhoto();list();notice('Simulated camera removed');};
window.addEventListener('pagehide',()=>{if(photoURL)URL.revokeObjectURL(photoURL);});
list();requestAnimationFrame(frame);notice('Sandbox — no camera or network access');

function updateSample(){const p=$('demoProtocol').value.toLowerCase().split(' ')[0];$('demoEndpoint').value=p+'://192.0.2.10/parking';$('demoUser').disabled=!$('demoAuth').checked;$('demoPassword').disabled=!$('demoAuth').checked;}
$('demoProtocol').onchange=updateSample;$('demoAuth').onchange=updateSample;updateSample();
$('securityPreview').onclick=()=>$('securityDialog').showModal();$('closeSecurity').onclick=()=>$('securityDialog').close();$('demoMfa').onchange=()=>{$('demoSecurityStatus').textContent=$('demoMfa').checked?'MFA enabled in this simulation.':'MFA is off in this simulation.';};$('demoVerify').onclick=()=>{$('demoSecurityStatus').textContent=$('demoMfa').checked?'Simulated sign-in: password and sample code accepted.':'Simulated password-only sign-in accepted.';};
