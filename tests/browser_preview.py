"""Optional deterministic browser UI test using fixture HTTP responses, not real MJPEG."""
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera import Camera
import cv2

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'media'
MEDIA.mkdir(exist_ok=True)
_, jpg = cv2.imencode('.jpg', Camera(demo=True)._synthetic())
status = {'state': 'live', 'mode': 'demo', 'width': 1280, 'height': 720, 'fps': 15, 'viewers': 1, 'reconnects': 0, 'compact': False}
assets = {'/': ('templates/index.html', 'text/html'), '/static/app.css': ('static/app.css', 'text/css'), '/static/app.js': ('static/app.js', 'text/javascript')}
def respond(route):
    from urllib.parse import urlsplit
    path = urlsplit(route.request.url).path
    if path in assets:
        file, kind = assets[path]
        route.fulfill(status=200, content_type=kind, body=(ROOT/file).read_bytes())
    elif path == '/api/cameras':
        route.fulfill(status=200, content_type='application/json', body=json.dumps([{'id':'default','name':'Demo','editable':False}]))
    elif path == '/api/status':
        route.fulfill(status=200, content_type='application/json', body=json.dumps(status))
    elif path in ('/video_feed', '/snapshot.jpg'):
        route.fulfill(status=200, content_type='image/jpeg', body=jpg.tobytes())
    else:
        route.fulfill(status=404, body='Not found')

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=__import__('shutil').which('chromium'), args=['--no-sandbox'])
    for name, viewport, scheme in [('desktop', {'width': 1320, 'height': 650}, 'light'), ('mobile', {'width': 390, 'height': 844}, 'light'), ('desktop-dark', {'width': 1320, 'height': 650}, 'dark')]:
        page = browser.new_page(viewport=viewport, color_scheme=scheme, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.route('**/*', respond)
        page.goto('http://pywcam.test/', wait_until='domcontentloaded', timeout=10000)
        expect(page.locator('#state')).to_have_text('Online')
        page.wait_for_function("document.querySelector('#feed').naturalWidth > 0")
        page.locator('#snapshot').click()
        page.wait_for_function("document.querySelector('#photo').naturalWidth > 0")
        page.screenshot(path=str(MEDIA / f'preview-{name}.png'), full_page=True, timeout=10000)
        page.locator('#pause').click()
        expect(page.locator('#feed')).to_be_hidden()
        page.locator('#pause').click()
        page.wait_for_function("document.querySelector('#feed').naturalWidth > 0")
        page.locator('#mirror').click()
        expect(page.locator('#mirror')).to_have_attribute('aria-pressed', 'true')
        page.locator('#full').click()
        expect(page.locator('.viewer')).to_have_class('viewer expanded')
        page.keyboard.press('Escape')
        expect(page.locator('.viewer')).to_have_class('viewer')
        with page.expect_download() as download:
            page.locator('#download').click()
        assert download.value.suggested_filename.endswith('.jpg')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        print(name, 'fixture UI PASS', flush=True)
        page.close()
    browser.close()
