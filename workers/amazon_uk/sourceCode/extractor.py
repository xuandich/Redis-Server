import os
import random
import time
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Playwright, Browser
from pyvirtualdisplay import Display

from utils import mask_proxy_password, parse_proxy, AMAZON_DOMAIN, AMAZON_POSTAL_CODE, AMAZON_COUNTRY_CODE
from models import AmazonProductResult


def _country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ''
    return chr(0x1F1E6 + ord(code[0].upper()) - ord('A')) + chr(0x1F1E6 + ord(code[1].upper()) - ord('A'))


class AmazonFetcher:
    def __init__(self, proxy_list: List[str], cookie_string: Optional[str] = None):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._display: Optional[Display] = None
        self.proxies = proxy_list.copy()
        self.cookie_string = cookie_string
        self.log_buffer: List[str] = []
        self.chromium_path = os.environ.get('CHROMIUM_PATH') or None

    def add_log(self, msg: str):
        self.log_buffer.append(msg)
        print(msg)

    def _start_display(self):
        if self._display is None:
            wsize = random.choice([(1920, 1080), (1366, 768), (1440, 900)])
            self._display = Display(visible=False, size=wsize)
            self._display.start()
            self.add_log(f"🖥️ Virtual display {wsize[0]}x{wsize[1]}")

    def _stop_display(self):
        if self._display:
            try:
                self._display.stop()
            except Exception:
                pass
            self._display = None

    async def _start_browser(self, proxy_string: Optional[str] = None) -> bool:
        try:
            self._start_display()

            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            self._playwright = await async_playwright().start()

            launch_options = {
                'headless': False,
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--lang=en-GB',
                ],
            }

            if proxy_string:
                parsed = parse_proxy(proxy_string)
                if parsed:
                    proxy_config = {'server': f"http://{parsed['host']}:{parsed['port']}"}
                    if parsed.get('username'):
                        proxy_config['username'] = parsed['username']
                        proxy_config['password'] = parsed['password']
                    launch_options['proxy'] = proxy_config
                    self.add_log(f"🌐 Proxy: {mask_proxy_password(proxy_string)}")
            else:
                self.add_log("🌐 Direct connection (no proxy)")

            self._browser = await self._playwright.chromium.launch(
                executable_path=self.chromium_path,
                **launch_options,
            )
            self.add_log("✅ Browser started successfully")
            if not await self._check_proxy_country():
                return False
            return True

        except Exception as e:
            self.add_log(f"❌ Startup error: {type(e).__name__}: {e}")
            return False

    async def _check_proxy_country(self) -> bool:
        """Kiểm tra IP thực tế + country qua proxy đang dùng. Trả False nếu thất bại HOẶC country != GB."""
        context = None
        try:
            context = await self._browser.new_context()
            page = await context.new_page()
            response = await page.goto('https://ipwho.is/', timeout=10000)
            data = await response.json()
            ip = data.get('ip', '?')
            country = data.get('country', '?')
            country_code = (data.get('country_code') or '').upper()
            flag = _country_flag(country_code)
            self.add_log(f"🌍 IP: {ip} | {country} {flag}")

            if country_code != AMAZON_COUNTRY_CODE:
                self.add_log(f"⚠️ Proxy is not {AMAZON_COUNTRY_CODE} (actual: {country_code or '?'}) → switching proxy")
                return False
            return True
        except Exception as e:
            self.add_log(f"🌍 IP check failed → switching proxy: {e}")
            return False
        finally:
            if context:
                await context.close()

    async def _inject_cookies(self, context, domain: str):
        if not self.cookie_string:
            return
        for pair in self.cookie_string.split('; '):
            if '=' in pair:
                name, value = pair.split('=', 1)
                try:
                    await context.add_cookies([{
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': f'.{domain}',
                        'path': '/',
                    }])
                except Exception:
                    pass

    async def _change_delivery_address(self, page) -> bool:
        self.add_log(f"📍 Changing postcode → {AMAZON_POSTAL_CODE}")
        try:
            await page.wait_for_timeout(2000)
            for sel in ["#nav-global-location-popover-link", "#nav-packard-glow-locale"]:
                btn = page.locator(sel)
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    break
            await page.wait_for_timeout(2000)

            zip_input = page.locator("#GLUXZipUpdateInput")
            if await zip_input.count() == 0:
                self.add_log("⚠️ Postcode input not found → will retry")
                return False

            await zip_input.fill(AMAZON_POSTAL_CODE)
            await page.wait_for_timeout(1000)
            await page.locator("#GLUXZipUpdate").click()
            await page.wait_for_timeout(3000)

            close_btn = page.locator("#GLUXConfirmClose")
            if await close_btn.count() > 0 and await close_btn.is_visible():
                await close_btn.click()
            return True

        except Exception as e:
            self.add_log(f"⚠️ Error changing postcode: {e}")
            return False

    async def _human_move_and_click(self, page, tx: float, ty: float):
        """Di chuyển chuột ngẫu nhiên rồi tiến dần tới (tx, ty)."""
        vp = page.viewport_size or {'width': 1280, 'height': 720}
        w, h = vp['width'], vp['height']

        for _ in range(random.randint(3, 6)):
            x = random.randint(w // 5, w * 4 // 5)
            y = random.randint(h // 5, h * 4 // 5)
            await page.mouse.move(x, y, steps=random.randint(10, 25))
            await page.wait_for_timeout(random.uniform(100, 350))

        steps = random.randint(15, 30)
        cur_x, cur_y = random.randint(w // 4, w * 3 // 4), random.randint(h // 4, h * 3 // 4)
        for i in range(1, steps + 1):
            nx = cur_x + (tx - cur_x) * i / steps + random.uniform(-3, 3)
            ny = cur_y + (ty - cur_y) * i / steps + random.uniform(-3, 3)
            await page.mouse.move(nx, ny)
            await page.wait_for_timeout(random.uniform(20, 60))

        await page.wait_for_timeout(random.uniform(200, 500))

    async def _try_click_turnstile(self, page) -> bool:
        """Di chuột tự nhiên rồi click Cloudflare Turnstile."""
        cf_frame = next(
            (f for f in page.frames if 'challenges.cloudflare.com' in f.url),
            None,
        )
        if not cf_frame:
            return False

        try:
            vp = page.viewport_size or {'width': 1280, 'height': 720}
            await self._human_move_and_click(page, vp['width'] / 2, vp['height'] / 2)
            await cf_frame.click('body', timeout=2000)
            self.add_log("🖱️ Clicked Turnstile")
            return True
        except Exception as e:
            self.add_log(f"  ℹ️ Turnstile click failed: {e}")
            return False

    def _is_cf_blocked(self, title: str, html: str) -> bool:
        t = title.lower()
        return (
            'just a moment' in t or
            'verify you are human' in html.lower()
        )

    async def _is_product_page(self, page) -> bool:
        """Kiểm tra trang có phải trang sản phẩm Amazon không (marker đặc hiệu — tránh selector chung
        chung như '#title' vì nó cũng xuất hiện trên trang search/lỗi)."""
        for sel in ['#productTitle', '#dp-container', '#buybox', '#add-to-cart-button']:
            elem = page.locator(sel).first
            if await elem.count() > 0:
                return True
        return False

    async def _navigate_and_extract(self, url: str) -> tuple:
        """Trả về (is_product, html, headers, cookies, status, http_code)."""
        wsize = random.choice([(1920, 1080), (1366, 768), (1440, 900)])

        context = await self._browser.new_context(
            viewport={'width': wsize[0], 'height': wsize[1]},
            locale='en-GB',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            ),
        )
        try:
            page = await context.new_page()

            # Chặn image và media để load nhanh hơn
            async def _block_media(route):
                if route.request.resource_type in ('image', 'media'):
                    await route.abort()
                else:
                    await route.continue_()

            await page.route('**/*', _block_media)

            response_headers: dict = {}

            async def on_response(response):
                # Chỉ lấy header của navigation document (không phải sub-resource ảnh/script/xhr);
                # response cuối — document mới nhất, tức trang sản phẩm — sẽ thắng.
                if response.request.resource_type == 'document' and AMAZON_DOMAIN in response.url:
                    response_headers.clear()
                    response_headers.update(dict(response.headers))

            page.on('response', on_response)

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [
                    {name: 'Chrome PDF Plugin'}, {name: 'Chrome PDF Viewer'}, {name: 'Native Client'}
                ]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en']});
                window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (params) =>
                    params.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(params);
            """)

            # Đến trang chủ để inject cookie
            await page.goto(f"https://{AMAZON_DOMAIN}", wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(random.uniform(1000, 2000))
            await self._inject_cookies(context, AMAZON_DOMAIN)
            try:
                await page.reload(wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                self.add_log(f"⚠️ Reload failed → stop + retry once: {e}")
                try:
                    await page.stop()
                except Exception:
                    pass
                try:
                    await page.reload(wait_until='domcontentloaded', timeout=30000)
                    self.add_log("✅ Second reload succeeded")
                except Exception as e2:
                    self.add_log(f"⚠️ Second reload still failed (ignoring): {e2}")
            await page.wait_for_timeout(random.uniform(2000, 3000))

            # None và False đều là "chưa đổi được postcode" → cả 2 phải retry.
            addr_ok = await self._change_delivery_address(page)
            if addr_ok is not True:
                return False, '', {}, {}, 'no_postal', 0

            # Giữ response lại để đọc HTTP status thật của navigation.
            self.add_log(f"🌐 Visiting: {url[:80]}")
            response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            http_code = response.status if response else 0
            await page.wait_for_timeout(random.uniform(2000, 4000))

            title_text = await page.title()
            html = await page.content()

            if self._is_cf_blocked(title_text, html):
                self.add_log("⏳ CF detected → trying to click Turnstile...")
                await self._try_click_turnstile(page)
                await page.wait_for_timeout(6000)

                title_text = await page.title()
                html = await page.content()

                if self._is_cf_blocked(title_text, html):
                    self.add_log("⚠️ Still CF-blocked after click → switching proxy")
                    return False, '', {}, {}, 'blocked', http_code

            self.add_log("✅ CF pass")

            # Status thật PHẢI hợp lệ trước khi tin DOM — trang lỗi của Amazon (403/503) có thể
            # vẫn render layout đầy đủ.
            if http_code == 0 or http_code >= 400:
                self.add_log(f"⚠️ Abnormal HTTP status ({http_code}) → treating as failure, not trusting DOM")
                return False, '', {}, {}, 'bad_status', http_code

            if AMAZON_POSTAL_CODE.split()[0] not in html:
                self.add_log(f"⚠️ Postcode {AMAZON_POSTAL_CODE} not found in HTML → retry")
                return False, '', {}, {}, 'no_postcode', http_code
            self.add_log(f"📍 Correct region ({AMAZON_POSTAL_CODE} found in HTML)")

            if 'captcha' in page.url.lower() or 'captcha' in html.lower():
                self.add_log("⚠️ CAPTCHA detected")
                return False, '', {}, {}, 'captcha', http_code

            is_product = await self._is_product_page(page)
            cookies_list = await context.cookies()
            cookies = {c['name']: c['value'] for c in cookies_list}
            self.add_log(f"📦 Product page: {is_product} | {len(html):,} bytes | {len(response_headers)} headers | http={http_code}")
            return is_product, html, response_headers, cookies, 'ok', http_code

        finally:
            await context.close()

    async def fetch_url(self, url: str, max_retries: int = 3) -> AmazonProductResult:
        result = AmazonProductResult(url)

        # Rút proxy KHÔNG hoàn lại từ pool đã xáo trộn — 1 proxy chỉ bị chọn lại sau khi
        # cả pool cạn 1 vòng, tránh lãng phí retry vào đúng proxy vừa chết.
        proxy_pool: List[str] = []
        if self.proxies:
            proxy_pool = self.proxies.copy()
            random.shuffle(proxy_pool)

        for attempt_idx in range(max_retries):
            if self.proxies:
                if not proxy_pool:
                    proxy_pool = self.proxies.copy()
                    random.shuffle(proxy_pool)
                proxy = proxy_pool.pop()
            else:
                proxy = None
            label = mask_proxy_password(proxy) if proxy else "direct (no proxy)"
            self.add_log(f"━ Attempt {attempt_idx + 1}/{max_retries}: {label}")

            ok = await self._start_browser(proxy)
            if not ok:
                self.add_log("⚠️ Startup failed → trying another proxy")
                continue

            try:
                start = time.time()
                is_product, html, headers, cookies, status, http_code = await self._navigate_and_extract(url)
                elapsed_ms = (time.time() - start) * 1000

                if status == 'blocked':
                    self.add_log("🔄 CF block → new browser + same proxy + retrying...")
                    ok2 = await self._start_browser(proxy)
                    if ok2:
                        is_product, html, headers, cookies, status, http_code = await self._navigate_and_extract(url)
                        elapsed_ms = (time.time() - start) * 1000
                    if status == 'blocked':
                        self.add_log("⚠️ Still blocked → switching proxy")
                        continue

                if status == 'no_postal':
                    self.add_log("🔄 Could not change postcode → retrying")
                    continue

                if status == 'bad_status':
                    self.add_log(f"🔄 Bad HTTP status ({http_code}) → switching proxy and retrying")
                    continue

                if status == 'no_postcode':
                    self.add_log("🔄 Postcode missing from HTML → retrying")
                    continue

                if status == 'captcha':
                    self.add_log("⚠️ CAPTCHA → switching proxy")
                    continue

                if is_product:
                    result.mark_success(html, headers, cookies, http_code, elapsed_ms)
                    self.add_log(f"✅ {elapsed_ms:.0f}ms")
                    return result

                self.add_log("⚠️ Not a product page → retrying")

            except Exception as e:
                self.add_log(f"❌ {type(e).__name__}: {str(e)[:100]}")

        result.mark_failed("Failed after all attempts")
        return result

    async def close_browser(self):
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._stop_display()
        self.add_log("🔒 Browser closed")
