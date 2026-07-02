import os
import random
import time
from typing import List, Optional

from playwright.async_api import async_playwright, Playwright, Browser
from pyvirtualdisplay import Display

from utils import mask_proxy_password, parse_proxy
from models import HtmlFetchResult


def _country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ''
    return chr(0x1F1E6 + ord(code[0].upper()) - ord('A')) + chr(0x1F1E6 + ord(code[1].upper()) - ord('A'))


class OrchestraFetcher:
    def __init__(self, proxy_list: List[str]):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._display: Optional[Display] = None
        self.proxies = proxy_list.copy()
        self.log_buffer: List[str] = []
        self.chromium_path = os.environ.get('CHROMIUM_PATH') or None

    def add_log(self, msg: str):
        self.log_buffer.append(msg)
        print(f"[orchestra] {msg}", flush=True)

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

    async def _check_proxy_country(self):
        """Kiểm tra IP thực tế và country qua proxy đang dùng."""
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
        except Exception as e:
            self.add_log(f"🌍 IP check failed: {e}")

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
                self.add_log("🌐 Direct connection (no proxy)")

            self._browser = await self._playwright.chromium.launch(
                executable_path=self.chromium_path,
                **launch_options,
            )
            self.add_log("✅ Browser started successfully")
            await self._check_proxy_country()
            return True

        except Exception as e:
            self.add_log(f"❌ Startup error: {type(e).__name__}: {e}")
            return False

    async def _human_move_and_click(self, page, tx: float, ty: float):
        """Di chuyển chuột ngẫu nhiên rồi tiến dần tới (tx, ty) — không click."""
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
            None
        )
        if not cf_frame:
            return False

        try:
            vp = page.viewport_size or {'width': 1280, 'height': 720}
            w, h = vp['width'], vp['height']

            await self._human_move_and_click(page, w / 2, h / 2)

            await cf_frame.click('body', timeout=2000)
            self.add_log("🖱️ Clicked Turnstile")
            return True
        except Exception as e:
            self.add_log(f"  ℹ️ Turnstile click failed: {e}")
            return False

    _REFERERS = [
        'https://www.google.fr/',
        'https://www.google.com/',
        'https://www.bing.com/',
        'https://duckduckgo.com/',
        'https://fr.yahoo.com/',
    ]

    async def _validate_product_page(self, page) -> bool:
        """
            Kiểm URL + nội dung để xác minh là trang sản phẩm thực.
        """
        try:
            current_url = page.url.lower()

            # Kiểm URL vẫn thuộc domain orchestra (không redirect ra ngoài)
            if 'shop-orchestra.com' not in current_url and 'orchestra.fr' not in current_url:
                self.add_log(f"⚠️ URL redirected outside domain: {current_url[:80]}")
                return False

            # Kiểm tìm thấy product selector
            try:
                await page.wait_for_selector(
                    'h1, .product-name, [data-testid="product-title"], [class*="product-title"]',
                    timeout=5000
                )
                self.add_log("✓ Product found")
                return True
            except Exception:
                self.add_log("⚠️ Product selector not found")
                return False

        except Exception as e:
            self.add_log(f"⚠️ Validate error: {e}")
            return False

    async def _navigate_via_referer(self, page, target_url: str, used_referers: set):
        """Navigate với referer chưa dùng trong vòng loop hiện tại."""
        available = [r for r in self._REFERERS if r not in used_referers]
        if not available:
            available = self._REFERERS
        referer = random.choice(available)
        used_referers.add(referer)
        self.add_log(f"🌐 Navigating with referer: {referer}")
        await page.goto(target_url, wait_until='domcontentloaded', timeout=30000,
                        referer=referer)

    async def _navigate_and_get_html(self, url: str, used_referers: set) -> tuple:
        """Navigate đến url, xử lý Cloudflare, trả về (html, status, empty_page, cookies, headers)."""
        wsize = random.choice([(1920, 1080), (1366, 768), (1440, 900)])
        context = await self._browser.new_context(
            viewport={'width': wsize[0], 'height': wsize[1]},
            locale='fr-FR',
            user_agent=(
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            ),
        )
        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [
                {name: 'Chrome PDF Plugin'}, {name: 'Chrome PDF Viewer'}, {name: 'Native Client'}
            ]});
            Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-US', 'en']});
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
        """)

        response_headers = {}

        async def on_response(response):
            if 'orchestra' in response.url and response.status == 200:
                response_headers.update(dict(response.headers))

        page.on('response', on_response)

        def _is_cf_blocked(title_lower: str, html: str) -> bool:
            return (
                'just a moment' in title_lower or
                'un instant' in title_lower or
                'verify you are human' in html.lower() or
                'challenge-form' in html.lower()
            )

        try:
            await self._navigate_via_referer(page, url, used_referers)
            await page.wait_for_timeout(random.uniform(2000, 4000))

            page_title = (await page.title()).lower()
            html = await page.content()

            if _is_cf_blocked(page_title, html):
                self.add_log("⏳ CF detected → trying to click Turnstile...")
                await self._try_click_turnstile(page)
                await page.wait_for_timeout(6000)

                page_title = (await page.title()).lower()
                html = await page.content()

                if _is_cf_blocked(page_title, html):
                    self.add_log("⚠️ Still CF-blocked after click → switching proxy")
                    return html, 'blocked', False, {}, {}

            self.add_log(f"✅ CF pass")
            try:
                await page.wait_for_function(
                    'document.body && document.body.innerHTML.length > 5000',
                    timeout=20000,
                )
            except TimeoutError:
                self.add_log("⚠️ Render timeout → page doesn't have enough content")
                html = await page.content()
                return html, 'render_timeout', False, {}, {}
            except Exception:
                pass

            html = await page.content()
            cookies_list = await context.cookies()
            cookies = {c['name']: c['value'] for c in cookies_list}

            empty_page = len(html) < 1000
            self.add_log(f"📄 {len(html):,} bytes | {len(response_headers)} headers")

            # Validation: kiểm URL + nội dung trước khi return
            is_valid = await self._validate_product_page(page)
            return html, 'ok' if is_valid else 'invalid_content', empty_page, cookies, response_headers

        finally:
            await context.close()

    async def fetch_url(self, url: str, max_retries: int = 3) -> HtmlFetchResult:
        result = HtmlFetchResult(url)

        for attempt_idx in range(max_retries):
            proxy = random.choice(self.proxies) if self.proxies else None
            label = mask_proxy_password(proxy) if proxy else "direct (no proxy)"
            self.add_log(f"━ Attempt {attempt_idx + 1}/{max_retries}: {label}")

            ok = await self._start_browser(proxy)
            if not ok:
                self.add_log("⚠️ Startup failed → trying another proxy")
                continue

            try:
                start = time.time()
                used_referers: set = set()
                html, status, empty_page, cookies, headers = await self._navigate_and_get_html(url, used_referers)

                if status == 'blocked':
                    self.add_log("🔄 CF block → new browser + same proxy + new referer...")
                    ok2 = await self._start_browser(proxy)
                    if ok2:
                        html, status, empty_page, cookies, headers = await self._navigate_and_get_html(url, used_referers)
                    if status == 'blocked':
                        self.add_log("⚠️ Still blocked → switching proxy")
                        continue

                if status == 'render_timeout':
                    self.add_log("⚠️ Render timeout → switching proxy")
                    continue

                if status == 'invalid_content':
                    self.add_log("⚠️ Not a product page (redirect/404) → switching proxy")
                    continue

                if status != 'ok' or empty_page:
                    self.add_log("⚠️ Empty page (blocked) → switching proxy")
                    continue

                elapsed_ms = (time.time() - start) * 1000
                result.mark_success(html, headers, 200, cookies, elapsed_ms)
                self.add_log(f"✅ {len(html):,} bytes | {elapsed_ms:.0f}ms")
                return result

            except Exception as e:
                self.add_log(f"❌ {type(e).__name__}: {str(e)[:100]}")

        result.mark_failed("Failed: proxy blocked or IP CF-blocked")
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
