import os
import random
import time
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Playwright, Browser
from pyvirtualdisplay import Display

from utils import mask_proxy_password, parse_proxy, AMAZON_DOMAIN, AMAZON_POSTAL_CODE


def _country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ''
    return chr(0x1F1E6 + ord(code[0].upper()) - ord('A')) + chr(0x1F1E6 + ord(code[1].upper()) - ord('A'))
from models import AmazonProductResult


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
                    '--lang=fr-FR',
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
                self.add_log("🌐 Direct connection (không proxy)")

            self._browser = await self._playwright.chromium.launch(
                executable_path=self.chromium_path,
                **launch_options,
            )
            self.add_log("✅ Browser khởi động thành công")
            if not await self._check_proxy_country():
                return False
            return True

        except Exception as e:
            self.add_log(f"❌ Lỗi khởi động: {type(e).__name__}: {e}")
            return False

    async def _check_proxy_country(self) -> bool:
        """Kiểm tra IP thực tế và country qua proxy đang dùng. Trả False nếu thất bại."""
        try:
            context = await self._browser.new_context()
            page = await context.new_page()
            response = await page.goto('https://ipwho.is/', timeout=10000)
            data = await response.json()
            await context.close()
            ip = data.get('ip', '?')
            country = data.get('country', '?')
            flag = _country_flag(data.get('country_code', ''))
            self.add_log(f"🌍 IP: {ip} | {country} {flag}")
            return True
        except Exception as e:
            self.add_log(f"🌍 IP check thất bại → đổi proxy: {e}")
            return False

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
        self.add_log(f"📍 Đổi địa chỉ → {AMAZON_POSTAL_CODE}")
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
                self.add_log("⚠️ Không tìm thấy ô nhập postal code → sẽ retry")
                return None

            await zip_input.fill(AMAZON_POSTAL_CODE)
            await page.wait_for_timeout(1000)
            await page.locator("#GLUXZipUpdate").click()
            await page.wait_for_timeout(3000)

            close_btn = page.locator("#GLUXConfirmClose")
            if await close_btn.count() > 0 and await close_btn.is_visible():
                await close_btn.click()
            return True

        except Exception as e:
            self.add_log(f"⚠️ Lỗi đổi địa chỉ: {e}")
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
            self.add_log(f"  ℹ️ Turnstile click thất bại: {e}")
            return False

    def _is_cf_blocked(self, title: str, html: str) -> bool:
        t = title.lower()
        return (
            'just a moment' in t or
            'un instant' in t or
            'verify you are human' in html.lower()
        )

    async def _is_product_page(self, page) -> bool:
        """Kiểm tra trang có phải trang sản phẩm Amazon không."""
        for sel in ['#productTitle', '#title', '#add-to-cart-button', '#buybox']:
            elem = page.locator(sel).first
            if await elem.count() > 0:
                return True
        return False

    async def _navigate_and_extract(self, url: str) -> tuple:
        wsize = random.choice([(1920, 1080), (1366, 768), (1440, 900)])

        context = await self._browser.new_context(
            viewport={'width': wsize[0], 'height': wsize[1]},
            locale='fr-FR',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            ),
        )
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
            if 'amazon' in response.url and response.status == 200:
                response_headers.update(dict(response.headers))

        page.on('response', on_response)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [
                {name: 'Chrome PDF Plugin'}, {name: 'Chrome PDF Viewer'}, {name: 'Native Client'}
            ]});
            Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-US', 'en']});
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({state: Notification.permission})
                    : originalQuery(params);
        """)

        try:
            # Đến trang chủ để inject cookie
            await page.goto(f"https://{AMAZON_DOMAIN}", wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(random.uniform(1000, 2000))
            await self._inject_cookies(context, AMAZON_DOMAIN)
            try:
                await page.reload(wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                self.add_log(f"⚠️ Reload thất bại → stop + thử lại 1 lần: {e}")
                try:
                    await page.stop()
                except Exception:
                    pass
                try:
                    await page.reload(wait_until='domcontentloaded', timeout=30000)
                    self.add_log("✅ Reload lần 2 thành công")
                except Exception as e2:
                    self.add_log(f"⚠️ Reload lần 2 vẫn thất bại (bỏ qua): {e2}")
            await page.wait_for_timeout(random.uniform(2000, 3000))

            addr_ok = await self._change_delivery_address(page)
            if addr_ok is None:
                return False, '', {}, {}, 'no_postal'

            # Truy cập trang sản phẩm
            self.add_log(f"🌐 Truy cập: {url[:80]}")
            await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            await page.wait_for_timeout(random.uniform(2000, 4000))

            title_text = await page.title()
            html = await page.content()

            if self._is_cf_blocked(title_text, html):
                self.add_log("⏳ CF detected → thử tick Turnstile...")
                await self._try_click_turnstile(page)
                await page.wait_for_timeout(6000)

                title_text = await page.title()
                html = await page.content()

                if self._is_cf_blocked(title_text, html):
                    self.add_log("⚠️ Vẫn bị CF sau khi tick → đổi proxy mới")
                    return False, '', {}, {}, 'blocked'

            self.add_log("✅ CF pass")

            if AMAZON_POSTAL_CODE not in html:
                self.add_log(f"⚠️ Postal code {AMAZON_POSTAL_CODE} không có trong HTML → retry")
                return False, '', {}, {}, 'no_postcode'
            self.add_log(f"📍 Đúng quốc gia ({AMAZON_POSTAL_CODE} có trong HTML)")

            if 'captcha' in page.url.lower() or 'captcha' in html.lower():
                self.add_log("⚠️ Phát hiện CAPTCHA")
                return False, '', {}, {}, 'captcha'

            is_product = await self._is_product_page(page)
            cookies_list = await context.cookies()
            cookies = {c['name']: c['value'] for c in cookies_list}
            self.add_log(f"📦 Product page: {is_product} | {len(html):,} bytes | {len(response_headers)} headers")
            return is_product, html, response_headers, cookies, 'ok'

        finally:
            await context.close()

    async def fetch_url(self, url: str, max_retries: int = 5) -> AmazonProductResult:
        result = AmazonProductResult(url)

        for attempt_idx in range(max_retries):
            proxy = random.choice(self.proxies) if self.proxies else None
            label = mask_proxy_password(proxy) if proxy else "direct (không proxy)"
            self.add_log(f"━ Lần {attempt_idx + 1}/{max_retries}: {label}")

            ok = await self._start_browser(proxy)
            if not ok:
                self.add_log("⚠️ Khởi động thất bại → thử proxy khác")
                continue

            try:
                start = time.time()
                is_product, html, headers, cookies, status = await self._navigate_and_extract(url)
                elapsed_ms = (time.time() - start) * 1000

                if status == 'blocked':
                    self.add_log("🔄 CF block → browser mới + proxy hiện tại + thử lại...")
                    ok2 = await self._start_browser(proxy)
                    if ok2:
                        is_product, html, headers, cookies, status = await self._navigate_and_extract(url)
                        elapsed_ms = (time.time() - start) * 1000
                    if status == 'blocked':
                        self.add_log("⚠️ Vẫn bị block → đổi proxy mới")
                        continue

                if status == 'no_postal':
                    self.add_log("🔄 Không tìm thấy postal code → reload + thử lại")
                    continue

                if status == 'no_postcode':
                    self.add_log("🔄 Postal code vắng trong HTML → thử lại")
                    continue

                if status == 'captcha':
                    self.add_log("⚠️ CAPTCHA → đổi proxy")
                    continue

                if is_product:
                    result.proxy_used = mask_proxy_password(proxy) if proxy else 'direct'
                    result.mark_success(html, headers, cookies, 200, elapsed_ms)
                    self.add_log(f"✅ {elapsed_ms:.0f}ms")
                    return result

                self.add_log("⚠️ Không phải trang sản phẩm → thử lại")

            except Exception as e:
                self.add_log(f"❌ {type(e).__name__}: {str(e)[:100]}")

        result.proxy_used = 'all_failed'
        result.mark_failed("Thất bại sau tất cả lần thử")
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
        self.add_log("🔒 Browser đã đóng")
