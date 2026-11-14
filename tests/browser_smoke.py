import sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera import Camera
from pyWCam import Server
cam=Camera(demo=True); cam.start(); server=Server(('127.0.0.1',0),cam); t=threading.Thread(target=server.serve_forever,daemon=True); t.start()
base=f'http://127.0.0.1:{server.server_port}'
(Path(__file__).resolve().parents[1] / "media").mkdir(exist_ok=True)
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(args=['--no-sandbox'])
  for name, viewport in [('desktop',{'width':1100,'height':1050}),('mobile',{'width':390,'height':844})]:
   page=browser.new_page(viewport=viewport,accept_downloads=True); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(base,wait_until='domcontentloaded'); expect(page.locator('#state')).to_have_text('Online',timeout=10000)
   page.wait_for_function("document.querySelector('#feed').naturalWidth > 0",timeout=10000)
   page.screenshot(path=str(Path(__file__).resolve().parents[1] / 'media' / f'{name}.png'),full_page=True,timeout=10000)
   page.locator('#pause').click(); expect(page.locator('#state')).to_have_text('Paused'); expect(page.locator('#feed')).to_be_hidden()
   page.locator('#pause').click(); page.wait_for_function("document.querySelector('#feed').naturalWidth > 0",timeout=10000)
   page.locator('#mirror').click(); expect(page.locator('#mirror')).to_have_attribute('aria-pressed','true')
   page.locator('#full').click(); expect(page.locator('.viewer')).to_have_class('viewer expanded'); page.locator('#full').click()
   page.locator('#snapshot').click(); expect(page.locator('#photo')).to_be_visible(); page.wait_for_function("document.querySelector('#photo').naturalWidth > 0")
   with page.expect_download() as d: page.locator('#download').click()
   assert d.value.suggested_filename.endswith('.jpg')
   assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
   assert not errors,errors
   page.close(); print(name, 'stream, pause/resume, mirror, expand, snapshot, download, layout PASS',flush=True)
  browser.close()
finally:
 cam.stop();server.shutdown();server.server_close();t.join()
