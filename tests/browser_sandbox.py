"""Exercise the static demo without network or camera access. Requires Playwright."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    options = {'headless': True, 'args': ['--no-sandbox']}
    if os.getenv('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    browser = p.chromium.launch(**options)
    for width, height in [(1280, 800), (390, 844)]:
        page = browser.new_page(viewport={'width': width, 'height': height}, accept_downloads=True)
        requests = []
        errors = []
        page.on('request', lambda req: requests.append(req.url))
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto((root/'docs/demo/index.html').as_uri())
        page.wait_for_function("document.querySelector('#state').textContent === 'Online'")
        assert page.locator('#feed').is_visible()
        assert page.locator('#cameraSource').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#snapshot').click()
        page.locator('#photo').wait_for(state='visible')
        with page.expect_download() as d:
            page.locator('#download').click()
        assert Path(d.value.path()).read_bytes().startswith(b'\xff\xd8')
        page.locator('#pause').click(); assert page.locator('#feed').is_hidden()
        page.locator('#pause').click(); assert page.locator('#feed').is_visible()
        page.locator('#mirror').click(); assert page.locator('#mirror').get_attribute('aria-pressed') == 'true'
        page.locator('#full').click(); assert page.locator('.viewer.expanded').is_visible()
        page.keyboard.press('Escape'); assert page.locator('.viewer.expanded').count()==0
        page.locator('#cameraSelect').select_option('offline'); assert page.locator('#snapshot').is_disabled()
        page.locator('#theme').select_option('dark'); assert page.locator('html').get_attribute('data-theme')=='dark'
        page.locator('#theme').select_option('light'); assert page.locator('html').get_attribute('data-theme')=='light'
        page.locator('#securityPreview').click(); page.locator('#demoMfa').check(); page.locator('#demoVerify').click(); assert 'accepted' in page.locator('#demoSecurityStatus').inner_text(); page.locator('#closeSecurity').click()
        page.locator('#addCamera').click(); assert page.locator('#demoEndpoint').get_attribute('readonly') is not None; assert page.locator('#demoPassword').get_attribute('readonly') is not None
        page.locator('#cameraName').fill('Example camera'); page.locator('#preset').select_option('entry');page.locator('#saveCamera').click()
        assert page.locator('#cameraSelect option:checked').inner_text()=='Example camera'
        page.locator('#editCamera').click();page.locator('#cameraName').fill('Renamed');page.locator('#saveCamera').click()
        assert page.locator('#cameraSelect option:checked').inner_text()=='Renamed'
        page.once('dialog', lambda dialog:dialog.accept());page.locator('#deleteCamera').click()
        assert page.locator('#cameraSelect').input_value()=='default'
        assert not errors, errors
        assert not [r for r in requests if r.startswith(('http:', 'https:','ws:','wss:'))], requests
        if width == 1280:
            page.locator('#cameraSelect').select_option('garage'); page.locator('#snapshot').click(); page.locator('#photo').wait_for(state='visible')
            page.screenshot(path=str(root/'docs/sandbox-preview.png'))
        print(f'Sandbox checks passed: {width}x{height}')
        page.close()
    browser.close()
