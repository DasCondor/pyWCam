'use strict';
const $ = id => document.getElementById(id);
const feed = $('feed');
let paused = false, healthy = false, streaming = false, photoURL = null, lastPoll = 0, retryAfter = 0;
let selected = 'default', profiles = [], editID = null, listRequest = 0;
const endpoint = path => path + '?camera=' + encodeURIComponent(selected);
const notice = msg => { $('notice').textContent = msg; };
function stopFeed(message) {
  streaming = false; feed.removeAttribute('src'); feed.hidden = true;
  $('empty').hidden = false; $('screenlabel').hidden = true;
  $('message').textContent = message;
}
function startFeed() {
  if (streaming || paused || !healthy || Date.now() < retryAfter) return;
  streaming = true;
  feed.src = endpoint('/video_feed') + '&t=' + Date.now();
  feed.hidden = false; $('empty').hidden = true; $('screenlabel').hidden = false;
}
feed.addEventListener('error', () => {
  if (!streaming) return;
  retryAfter = Date.now() + 2500; stopFeed('Stream unavailable; retrying…');
});
let pollTimer;
async function poll() {
  clearTimeout(pollTimer);
  const request = ++lastPoll;
  const ctl = new AbortController(); const timeout = setTimeout(() => ctl.abort(), 4000);
  try {
    const response = await fetch(endpoint('/api/status'), { cache: 'no-store', signal: ctl.signal });
    if (response.status === 404 && request === lastPoll) { await loadCameras(); return; }
    if (response.status === 401) {location.replace('/');return;}
    if (!response.ok) throw Error('Status unavailable');
    const s = await response.json();
    if (request !== lastPoll) return;
    $('logout').hidden=!s.mfa;
    healthy = s.state === 'live';
    $('state').textContent = paused ? 'Paused' : healthy ? 'Online' : s.state;
    $('status').classList.toggle('live', healthy && !paused);
    $('mode').textContent = s.mode === 'demo' ? 'Demo' : 'Camera';
    $('resolution').textContent = s.width ? `${s.width} × ${s.height}` : '—';
    $('fps').textContent = healthy ? `${s.fps} fps` : '—';
    $('viewers').textContent = s.viewers; $('reconnects').textContent = s.reconnects;
    $('snapshot').disabled = !healthy || paused;
    document.body.classList.toggle('compact', s.compact);
    if (paused) stopFeed('Viewing paused');
    else if (healthy) startFeed();
    else stopFeed('Camera unavailable; reconnecting…');
    if (!healthy) notice('Waiting for camera');
    else if (!paused && $('notice').textContent === 'Waiting for camera') notice('Connected');
  } catch (err) {
    if (request !== lastPoll) return;
    healthy = false; $('state').textContent = 'Offline'; $('status').classList.remove('live');
    $('snapshot').disabled = true; stopFeed(paused ? 'Viewing paused' : 'Server unreachable; retrying…');
    notice('Waiting for camera');
  } finally { clearTimeout(timeout); if (request === lastPoll) pollTimer = setTimeout(poll, 1800); }
}
$('pause').addEventListener('click', () => {
  paused = !paused; $('pause').textContent = paused ? 'Resume' : 'Pause';
  $('state').textContent = paused ? 'Paused' : healthy ? 'Online' : 'Connecting';
  $('status').classList.toggle('live', healthy && !paused); $('snapshot').disabled = paused || !healthy;
  if (paused) stopFeed('Viewing paused'); else startFeed();
});
$('mirror').addEventListener('click', () => {
  const on = feed.classList.toggle('mirrored'); $('mirror').setAttribute('aria-pressed', String(on));
});
const viewer = document.querySelector('.viewer');
function expand(on) { viewer.classList.toggle('expanded', on); $('full').textContent = on ? 'Exit expanded' : 'Expand'; }
$('full').addEventListener('click', () => expand(!viewer.classList.contains('expanded')));
document.addEventListener('keydown', e => { if (e.key === 'Escape') expand(false); });
$('snapshot').addEventListener('click', async () => {
  $('snapshot').disabled = true;
  try {
    const cameraAtCapture = selected;
    const res = await fetch(endpoint('/snapshot.jpg'), {cache:'no-store'});
    if (!res.ok) throw Error('Camera unavailable');
    const blob = await res.blob(); if (cameraAtCapture !== selected) return; if (photoURL) URL.revokeObjectURL(photoURL);
    photoURL = URL.createObjectURL(blob);
    $('photo').src = photoURL; $('photo').hidden = false; $('captureEmpty').hidden = true;
    $('download').href = photoURL; $('download').download = `pywcam-${new Date().toISOString().replace(/[:.]/g,'-')}.jpg`; $('download').hidden = false;
    if (document.body.classList.contains('compact')) {
      const link = document.createElement('a'); link.href=photoURL; link.download=$('download').download;
      document.body.append(link); link.click(); link.remove();
    }
    notice('Photo captured at ' + new Date().toLocaleTimeString());
  } catch (err) { notice('Snapshot unavailable; try again.'); }
  finally { $('snapshot').disabled = !healthy || paused; }
});
window.addEventListener('pagehide', () => { stopFeed('Viewing paused'); if (photoURL) URL.revokeObjectURL(photoURL); });
window.addEventListener('pageshow', e => { if (e.persisted) location.reload(); });
function selectCamera(id) {
  if (selected === id) return;
  selected = id; $('cameraSelect').value = id;
  healthy = false; retryAfter = 0; $('snapshot').disabled = true;
  if (photoURL) { URL.revokeObjectURL(photoURL); photoURL = null; }
  $('photo').removeAttribute('src'); $('photo').hidden = true;
  $('captureEmpty').hidden = false; $('download').hidden = true; $('download').removeAttribute('href');
  stopFeed(paused ? 'Viewing paused' : 'Connecting to camera…');
  poll();
}
function updateButtons() {
  const editable = profiles.some(p => p.id === selected && p.editable);
  $('editCamera').disabled = !editable; $('deleteCamera').disabled = !editable;
}
async function loadCameras(preferred) {
  const n = ++listRequest;
  const res = await fetch('/api/cameras', {cache:'no-store'});
  if (!res.ok) throw Error('Could not load cameras');
  const rows = await res.json();
  if (n !== listRequest) return;
  profiles = rows;
  const desired = profiles.some(p => p.id === (preferred || selected)) ? (preferred || selected) : 'default';
  $('cameraSelect').replaceChildren(...profiles.map(p => new Option(p.name, p.id)));
  $('cameraSelect').value = desired; selectCamera(desired); updateButtons();
}
$('cameraSelect').addEventListener('change', e => { selectCamera(e.target.value); updateButtons(); });
function openCamera(edit) {
  editID = edit ? selected : null;
  $('cameraDialogTitle').textContent = edit ? 'Edit IP camera' : 'Add IP camera';
  $('cameraName').value = edit ? profiles.find(p => p.id === selected).name : '';
  $('cameraUser').value=''; $('cameraPassword').value=''; $('secureTransport').checked=false; $('cameraSource').value = ''; $('cameraSource').type = 'password'; $('showSource').checked = false;
  $('sourceHint').textContent = edit ? 'Leave URL blank to retain the existing stream and credentials.' : 'RTSP, RTSPS or HTTP(S) video stream. Use the camera’s actual stream URL.';
  $('cameraError').textContent = ''; $('cameraDialog').showModal(); $('cameraName').focus();
}
$('addCamera').addEventListener('click', () => openCamera(false));
$('editCamera').addEventListener('click', () => openCamera(true));
$('cancelCamera').addEventListener('click', () => $('cameraDialog').close());
$('cameraDialog').addEventListener('close', () => { $('cameraSource').value = ''; $('cameraUser').value=''; $('cameraPassword').value=''; });
$('showSource').addEventListener('change', e => { $('cameraSource').type = e.target.checked ? 'text' : 'password'; });
async function mutateCamera(method, id, body) {
  const res = await fetch('/api/cameras' + (id ? '/' + encodeURIComponent(id) : ''), {
    method, headers: {'Content-Type':'application/json','X-PyWCam':'1'},
    ...(body ? {body:JSON.stringify(body)} : {})
  });
  const result = await res.json(); if (!res.ok) throw Error(result.error || 'Camera update failed'); return result;
}
$('saveCamera').addEventListener('click', async () => {
  const button = $('saveCamera'); button.disabled = true; $('cameraError').textContent = '';
  try {
    const result = await mutateCamera(editID ? 'PUT' : 'POST', editID, {name:$('cameraName').value, source:$('cameraSource').value.trim(),username:$('cameraUser').value,password:$('cameraPassword').value,secure:$('secureTransport').checked});
    stopFeed('Connecting to camera…'); healthy = false;
    $('cameraDialog').close(); await loadCameras(result.id); poll(); notice('Camera saved');
  } catch (e) { $('cameraError').textContent = e.message; notice(e.message); }
  finally { button.disabled = false; }
});
$('deleteCamera').addEventListener('click', async () => {
  const id = selected;
  if (!confirm('Remove this saved camera?')) return;
  try { await mutateCamera('DELETE', id); await loadCameras('default'); notice('Camera removed'); }
  catch (e) { notice(e.message); }
});
loadCameras().catch(e => notice(e.message));
poll();

$('logout').addEventListener('click', async ()=>{const r=await fetch('/api/logout',{method:'POST',headers:{'X-PyWCam':'1'}});if(r.ok){stopFeed('Signed out');location.replace('/');}else notice('Sign out failed');});
