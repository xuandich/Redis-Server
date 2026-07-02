import asyncio
import re
import json
import os
import random
import time
from playwright.async_api import async_playwright
from typing import Optional, List, Dict


class NewarkProductExtractor:
    def __init__(self, proxy_list: List[str]):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.proxies = proxy_list.copy()
        self.requests_per_proxy = 2
        self.request_count_per_proxy = 0
        self.current_proxy = None
        self.log_buffer: List[str] = []
        self.chromium_path = os.environ.get('CHROMIUM_PATH') or None

    def _log(self, msg: str):
        print(msg)
        self.log_buffer.append(msg)

    def mask_proxy_password(self, proxy: str) -> str:
        if not proxy:
            return "None"
        if '@' in proxy:
            parts = proxy.split('@')
            if ':' in parts[0]:
                user = parts[0].split(':')[0]
                return f"{user}:****@{parts[1]}"
        return proxy

    def parse_proxy(self, proxy_string: str) -> Optional[Dict]:
        proxy_string = str(proxy_string).strip()

        try:
            if '@' in proxy_string:
                auth_part, server_part = proxy_string.split('@')
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                else:
                    username, password = auth_part, ''

                if ':' in server_part:
                    host, port = server_part.split(':')
                else:
                    host, port = server_part, '8080'

                return {
                    'server': f'http://{host}:{port}',
                    'username': username,
                    'password': password
                }
            else:
                if ':' in proxy_string:
                    host, port = proxy_string.split(':')
                else:
                    host, port = proxy_string, '8080'

                return {
                    'server': f'http://{host}:{port}',
                    'username': None,
                    'password': None
                }
        except Exception as e:
            self._log(f"❌ Error parsing proxy: {e}")
            return None

    async def start_browser_with_proxy(self, proxy_string: Optional[str] = None):
        if proxy_string:
            display_proxy = self.mask_proxy_password(proxy_string)
            self._log(f"🚀 Starting browser with proxy: {display_proxy}")
            proxy_config = self.parse_proxy(proxy_string)
            if not proxy_config:
                return False
        else:
            self._log(f"🚀 Starting browser without proxy...")
            proxy_config = None

        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            self.playwright = await async_playwright().start()

            args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--ignore-certificate-errors',
                '--disable-notifications',
                '--disable-popup-blocking',
            ]

            if self.chromium_path:
                self._log(f"📍 Chromium: {self.chromium_path}")

            launch_kwargs = {'headless': True, 'args': args}
            if proxy_config:
                launch_kwargs['proxy'] = proxy_config
            if self.chromium_path:
                launch_kwargs['executable_path'] = self.chromium_path
            self.browser = await self.playwright.chromium.launch(**launch_kwargs)

            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True
            )

            self.page = await self.context.new_page()
            self._log(f"✅ Browser is ready")
            return True

        except Exception as e:
            self._log(f"❌ Error starting browser: {e}")
            return False

    async def restart_browser_with_new_proxy(self):
        self._log(f"🔄 Restarting browser with new proxy")

        self.current_proxy = self.get_next_proxy()

        if not self.current_proxy:
            success = await self.start_browser_with_proxy(None)
        else:
            success = await self.start_browser_with_proxy(self.current_proxy)

        if success:
            self.request_count_per_proxy = 0
            await self.check_proxy_country()
            try:
                await self.page.goto('https://www.newark.com/', timeout=30000)
                await asyncio.sleep(5)
                return True
            except Exception as e:
                self._log(f"⚠️ New proxy also failed on homepage: {e}")
                return False
        return False

    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None

        proxy = random.choice(self.proxies)
        self._log(f"🔄 Randomly selected proxy: {self.mask_proxy_password(proxy)}")
        return proxy

    async def check_proxy_country(self):
        try:
            await self.page.goto('http://ip-api.com/json/', wait_until='networkidle', timeout=15000)
            content = await self.page.content()
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                country = data.get('country', 'Unknown')
                city    = data.get('city', '')
                ip      = data.get('query', '')
                isp     = data.get('isp', '')
                self._log(f"🌍 Proxy IP: {ip} | {country} - {city} | {isp}")
            else:
                self._log(f"🌍 Could not parse country")
        except Exception as e:
            self._log(f"⚠️ Could not check proxy country: {e}")

    async def _dismiss_popups(self):
        try:
            await self.page.evaluate("""
                () => {
                    const selectors = [
                        '#ECOM-8819-PopUp-overlay',
                        '[id*="PopUp-overlay"]',
                        '[id*="popup-overlay"]',
                        '[class*="modal-overlay"]',
                        '[class*="popup-overlay"]',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) el.remove();
                    }
                }
            """)
            await asyncio.sleep(0.3)
        except:
            pass

    async def search_product(self, keyword: str) -> bool:
        try:
            await asyncio.sleep(random.uniform(2, 3))
            await self.page.wait_for_load_state('networkidle', timeout=10000)

            await self._dismiss_popups()

            search_box = await self.page.query_selector('input[role="searchbox"], input[type="search"], input[name="q"]')
            if not search_box:
                return False

            await search_box.click()
            await asyncio.sleep(0.5)
            await search_box.fill('')
            await asyncio.sleep(0.3)

            self._log(f"  📝 Searching: {keyword}")
            await search_box.fill(keyword)
            await asyncio.sleep(0.5)

            await search_box.press('Enter')
            await asyncio.sleep(5)
            await self.page.wait_for_load_state('networkidle', timeout=15000)

            current_url = self.page.url
            if '/dp/' in current_url:
                return True
            elif 'search' in current_url:
                await self._dismiss_popups()

                first_result = await self.page.query_selector('.product-item a, [data-testid="product-item"] a')
                if first_result:
                    await first_result.click()
                    await asyncio.sleep(5)
                    if '/dp/' in self.page.url:
                        return True
            return False

        except Exception as e:
            self._log(f"  ❌ Search error: {e}")
            return False

    async def fetch_url_data(self, url: str, index: int, total: int) -> Dict:
        self._log(f"{'='*50}")
        self._log(f"🔍 [{index}/{total}]: {url}")

        start_req = time.time()

        if '/dp/' in url:
            key = url.split('/dp/')[-1].split('?')[0].split('#')[0]
        else:
            key = url.split('/')[-1]

        max_retries = 3
        result = None

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                if not self.proxies:
                    result = {
                        'html': None,
                        'headers': {},
                        'http_code': 0,
                        'cookies': [],
                        'elapsed_ms': int((time.time() - start_req) * 1000),
                        'error': 'No proxy available',
                    }
                    break
                self._log(f"🔄 Retry {attempt}/{max_retries} — switching proxy + restarting browser...")
                restarted = False
                for _ in range(min(len(self.proxies) if self.proxies else 1, 5)):
                    restarted = await self.restart_browser_with_new_proxy()
                    if restarted:
                        break
                    self._log(f"  ⚠️ Proxy blocked, trying another proxy...")
                if not restarted:
                    self._log(f"  ❌ Could not reach homepage after multiple attempts")
                    break

            try:
                if attempt == 1 and self.proxies and self.request_count_per_proxy >= self.requests_per_proxy:
                    self._log(f"⚠️ Request quota exhausted, switching proxy...")
                    await self.restart_browser_with_new_proxy()

                response_data = {'status': 0, 'headers': {}}

                def handle_response(response):
                    try:
                        if 'graphql' in response.url and 'operationName=Product' in response.url:
                            response_data['status'] = response.status
                            response_data['headers'] = dict(response.headers)
                    except:
                        pass

                self.page.on('response', handle_response)

                found = await self.search_product(key)

                self.page.remove_listener('response', handle_response)

                if not found:
                    self._log(f"  ❌ Attempt {attempt}: '{key}' not found")
                    if attempt < max_retries:
                        continue
                    result = {
                        'html': None,
                        'headers': {},
                        'http_code': 0,
                        'cookies': [],
                        'elapsed_ms': int((time.time() - start_req) * 1000),
                        'error': 'Product not found after 3 attempts',
                    }
                else:
                    html = await self.page.content()
                    cookies = await self.context.cookies()
                    result = {
                        'html': html,
                        'headers': response_data['headers'],
                        'http_code': response_data['status'],
                        'cookies': [{'name': c['name'], 'value': c['value'], 'domain': c.get('domain', '')} for c in cookies],
                        'elapsed_ms': int((time.time() - start_req) * 1000),
                        'error': None,
                    }
                    self.request_count_per_proxy += 1
                    self._log(f"  ✅ {self.page.url} | {len(html)} bytes")
                    break

            except Exception as e:
                self._log(f"  ❌ Attempt {attempt} exception: {e}")
                if attempt < max_retries:
                    continue
                result = {
                    'html': None,
                    'headers': {},
                    'http_code': 0,
                    'cookies': [],
                    'elapsed_ms': int((time.time() - start_req) * 1000),
                    'error': str(e),
                }

        if result is None:
            result = {
                'html': None,
                'headers': {},
                'http_code': 0,
                'cookies': [],
                'elapsed_ms': int((time.time() - start_req) * 1000),
                'error': 'Failed to restart browser',
            }

        result['log'] = self.log_buffer
        return result

    async def process_urls(self, urls: List[str]) -> List[Dict]:
        results = []
        total = len(urls)

        browser_started = False
        if self.proxies:
            self.current_proxy = self.get_next_proxy()
            browser_started = await self.start_browser_with_proxy(self.current_proxy)
            if not browser_started:
                for _ in range(min(len(self.proxies), 3)):
                    self.current_proxy = self.get_next_proxy()
                    browser_started = await self.start_browser_with_proxy(self.current_proxy)
                    if browser_started:
                        break
        else:
            browser_started = await self.start_browser_with_proxy(None)

        if not browser_started:
            self._log(f"❌ Could not start browser, skipping this worker")
            return []

        self._log(f"✅ Browser ready")

        await self.check_proxy_country()

        homepage_ok = False
        for _ in range(min(len(self.proxies) if self.proxies else 1, 5)):
            try:
                self._log(f"🌐 Opening homepage...")
                await self.page.goto('https://www.newark.com/', timeout=30000)
                await asyncio.sleep(8)
                self._log(f"✅ Homepage loaded")
                homepage_ok = True
                break
            except Exception as e:
                self._log(f"⚠️ Proxy blocked on homepage: {e}")
                if not self.proxies:
                    break
                self._log(f"🔄 Trying a new proxy...")
                self.current_proxy = self.get_next_proxy()
                await self.start_browser_with_proxy(self.current_proxy)
                self.request_count_per_proxy = 0
                await self.check_proxy_country()

        if not homepage_ok:
            self._log(f"❌ Could not reach Newark homepage after multiple attempts")
            return []

        for i, url in enumerate(urls, 1):
            result = await self.fetch_url_data(url, i, total)
            results.append(result)

            if i < total:
                delay = random.uniform(8, 15)
                await asyncio.sleep(delay)

        return results

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self._log(f"✅ Browser closed")
