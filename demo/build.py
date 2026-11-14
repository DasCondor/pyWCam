"""Build the self-contained GitHub Pages demo from the production layout."""
from pathlib import Path
import base64
import json
root = Path(__file__).resolve().parents[1]
html = (root/'templates/index.html').read_text()
css = (root/'static/app.css').read_text() + '\n.screen canvas { width:100%;height:100%;position:absolute;inset:0;object-fit:contain; } .screen canvas.mirrored { transform:scaleX(-1); } .demo-note {margin:0;padding:9px 16px;border-bottom:1px solid var(--line);background:var(--panel);color:var(--muted);font-size:13px;}\n'
images = {p.stem:'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode() for p in sorted((root/'demo/images').glob('*.jpg'))}
js = (root/'static/theme.js').read_text() + '\n;\nconst demoImages='+json.dumps(images)+';\n'+(root/'demo/sandbox.js').read_text()
html = html.replace('<title>pyWCam 2.0</title>', '<title>pyWCam 2.0 — Sandbox</title>\n  <meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src blob: data:; connect-src \'none\'; media-src \'none\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'">')
html = html.replace('<link rel="stylesheet" href="/static/app.css">',f'<style>{css}</style>').replace('<script src="/static/app.js" defer></script>','').replace('<script src="/static/theme.js" defer></script>','')
html = html.replace('</header>','</header>\n  <p class="demo-note"><strong>Public sandbox.</strong> All feeds are generated in your browser. Real camera URLs and access are disabled; changes reset when you reload.</p>')
html = html.replace('<button id="logout" hidden>Sign out</button>','<button id="securityPreview" type="button">Security</button>')
start = html.index('    <label for="cameraSource">'); end = html.index('    <p id="cameraError"',start)
html = html[:start] + '''    <label for="preset">Simulated source</label>
    <select id="preset"><option value="test">Test pattern</option><option value="garage">Garage</option><option value="entry">Front door</option><option value="parking">Parking lot</option><option value="offline">Offline camera</option></select>
    <label for="demoProtocol">Protocol</label><select id="demoProtocol"><option>RTSPS</option><option>HTTPS</option><option>RTSP</option><option>HTTP / MJPEG</option></select>
    <label for="demoEndpoint">Sample URL (locked)</label><input id="demoEndpoint" value="rtsps://192.0.2.10:322/parking" readonly>
    <label class="show-source"><input type="checkbox" id="demoAuth" checked> Camera authentication</label>
    <label for="demoUser">Username (sample)</label><input id="demoUser" value="demo-viewer" readonly>
    <label for="demoPassword">Password (sample)</label><input id="demoPassword" type="password" value="sample-only" readonly>
    <p class="caption">Sample sources only. The URL and credentials are locked and never used to connect.</p>
''' + html[end:]
html = html.replace('<img id="feed" alt="Live camera stream" hidden>','<canvas id="feed" width="960" height="540" aria-label="Simulated camera stream" hidden></canvas>').replace('>LIVE</span>','>SIMULATED</span>').replace('Local webcam server','Browser-only demo')
html=html.replace('</body>', '''<dialog id="securityDialog"><h2>Server security (preview)</h2><p>The self-hosted server can use a fixed password, HTTPS and optional authenticator-based MFA. This sandbox only demonstrates the workflow.</p><label class="show-source"><input id="demoMfa" type="checkbox"> Require authenticator code</label><label for="demoCode">Verification code (sample only)</label><input id="demoCode" readonly value="123456"><p id="demoSecurityStatus" role="status">MFA is off in this simulation.</p><div class="dialog-buttons"><button id="demoVerify" type="button">Simulate sign-in</button><button id="closeSecurity" type="button">Close</button></div></dialog>'''+f'<script>{js}</script>\n</body>')
out=root/'docs/demo';out.mkdir(parents=True,exist_ok=True);(out/'index.html').write_text(html,encoding='utf-8');(out/'.nojekyll').touch()
