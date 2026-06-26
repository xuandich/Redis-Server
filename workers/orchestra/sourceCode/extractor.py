import asyncio
import os
import random
import re
import subprocess
import tempfile
import time
import zipfile
from typing import List, Optional

import undetected_chromedriver as uc
from asyncio import Semaphore
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import mask_proxy_password, parse_proxy
from models import HtmlFetchResult


def _get_chrome_major_version() -> Optional[int]:
    try:
        out = subprocess.check_output(['google-chrome', '--version'], stderr=subprocess.DEVNULL).decode()
        return int(re.search(r'(\d+)\.', out).group(1))
    except Exception:
        return None


def _create_proxy_auth_extension(host: str, port: str, username: str, password: str) -> Optional[str]:
    """Tạo Chrome extension tạm để xác thực proxy (hoạt động với non-headless + Xvfb)."""
    manifest = """{
  "version": "1.0.0",
  "manifest_version": 2,
  "name": "Proxy Auth",
  "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
  "background": {"scripts": ["background.js"]},
  "minimum_chrome_version": "22.0.0"
}"""
    background = f"""var config = {{
  mode: "fixed_servers",
  rules: {{
    singleProxy: {{ scheme: "http", host: "{host}", port: parseInt("{port}") }},
    bypassList: ["localhost"]
  }}
}};
chrome.proxy.settings.set({{value: config, scope: "regular"}}, function(){{}});
function callbackFn(details) {{
  return {{ authCredentials: {{ username: "{username}", password: "{password}" }} }};
}}
chrome.webRequest.onAuthRequired.addListener(callbackFn,
  {{urls: ["<all_urls>"]}},
  ["blocking"]
);"""
    try:
        ext_dir = tempfile.mkdtemp(prefix='proxy_ext_')
        zip_path = os.path.join(ext_dir, 'proxy_auth.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('manifest.json', manifest)
            zf.writestr('background.js', background)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(ext_dir)
        os.remove(zip_path)
        return ext_dir
    except Exception:
        return None


class OrchestraFetcher:
    def __init__(self, proxy_list: List[str], worker_id: int = 0,
                 semaphore: Semaphore = None):
        self.driver = None
        self.proxies = proxy_list.copy()
        random.shuffle(self.proxies)
        self.current_proxy = None
        self.worker_id = worker_id
        self.semaphore = semaphore
        self.log_buffer: List[str] = []
        self._ext_dir: Optional[str] = None

    def add_log(self, msg: str):
        self.log_buffer.append(msg)
        print(f"[orchestra-{self.worker_id}] {msg}", flush=True)

    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        self.add_log(f"🔀 Proxy: {mask_proxy_password(proxy)}")
        return proxy

    def _cleanup_ext_dir(self):
        if self._ext_dir and os.path.exists(self._ext_dir):
            try:
                import shutil
                shutil.rmtree(self._ext_dir, ignore_errors=True)
            except Exception:
                pass
            self._ext_dir = None

    def _start_driver_sync(self, proxy_string: Optional[str] = None) -> bool:
        """Khởi động undetected_chromedriver (chạy trong thread)."""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
            self._cleanup_ext_dir()

            options = uc.ChromeOptions()
            options.binary_location = '/usr/bin/google-chrome'
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--disable-gpu')
            wsize = random.choice(['1920,1080', '1366,768', '1440,900', '1536,864', '1280,800'])
            options.add_argument(f'--window-size={wsize}')
            options.add_argument('--lang=fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7')

            if proxy_string:
                parsed = parse_proxy(proxy_string)
                if parsed and parsed.get('username'):
                    ext_dir = _create_proxy_auth_extension(
                        parsed['host'], parsed['port'],
                        parsed['username'], parsed['password']
                    )
                    if ext_dir:
                        self._ext_dir = ext_dir
                        options.add_argument(f'--load-extension={ext_dir}')
                        options.add_argument(f"--proxy-server=http://{parsed['host']}:{parsed['port']}")
                        self.add_log(f"🌐 Proxy (auth ext): {mask_proxy_password(proxy_string)}")
                    else:
                        options.add_argument(f"--proxy-server=http://{parsed['host']}:{parsed['port']}")
                        self.add_log(f"🌐 Proxy (no-auth fallback): {mask_proxy_password(proxy_string)}")
                else:
                    options.add_argument(f"--proxy-server=http://{parsed['host']}:{parsed['port']}")
                    self.add_log(f"🌐 Proxy: {mask_proxy_password(proxy_string)}")
            else:
                self.add_log("🌐 Direct connection (không proxy)")

            chrome_ver = _get_chrome_major_version()
            self.add_log(f"🔢 Chrome version: {chrome_ver}")
            self.driver = uc.Chrome(options=options, headless=False, use_subprocess=False,
                                    version_main=chrome_ver)
            self.add_log("✅ UC Browser khởi động thành công")
            return True

        except Exception as e:
            self.add_log(f"❌ Lỗi khởi động UC: {type(e).__name__}: {e}")
            return False

    def _extract_product_info(self) -> tuple:
        """Lấy title và price từ trang sản phẩm fr.shop-orchestra.com."""
        title = ""
        price = ""

        try:
            title_elem = self.driver.find_element(By.XPATH, "//h1[@class='product-name']")
            title = self.driver.execute_script(
                "return arguments[0].textContent.trim();", title_elem
            )
        except Exception:
            pass

        try:
            price_elem = self.driver.find_element(
                By.XPATH,
                "//*[@class='attributes']//div[contains(@aria-label,'Prix') and contains(@aria-label,'€')]"
            )
            aria_label = price_elem.get_attribute("aria-label")
            match = re.search(r'[\d\s]+[,\.]?\d*\s*€', aria_label)
            price = match.group(0).strip() if match else ""
        except Exception:
            try:
                match = re.search(r'"basePrice"\s*:\s*"([^"]+)"', self.driver.page_source)
                price = match.group(1) if match else ""
            except Exception:
                pass

        self.add_log(f"📦 title={title[:60]!r} | price={price!r}")
        return title, price

    def _navigate_and_get_html(self, url: str) -> tuple:
        """Navigate đến url, xử lý Cloudflare, chờ product element, trả về (html, cf_blocked, empty_page)."""
        self.driver.get(url)
        time.sleep(random.randint(4, 8))

        # CF retry: thử tối đa 2 lần wait trong cùng browser session
        _cf_patterns = ("verify you are human", "challenge-form", "cf-challenge-running")
        for cf_attempt in range(2):
            page_lower = self.driver.page_source.lower()
            if not any(p in page_lower for p in _cf_patterns):
                break
            self.add_log(f"⚠️ Cloudflare chặn (lần {cf_attempt + 1}/2), chờ 45s rồi thử lại")
            time.sleep(45)
            self.driver.get(url)
            time.sleep(random.randint(10, 18))

        # Chờ h1.product-name xuất hiện (tối đa 20s)
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//h1[@class='product-name']"))
            )
        except Exception:
            pass

        html = self.driver.page_source
        cf_blocked = any(p in html.lower() for p in _cf_patterns)
        empty_page = len(html) < 1000
        self.add_log(f"📄 {len(html):,} bytes | title: {self.driver.title[:60]}")
        return html, cf_blocked, empty_page

    def _fetch_sync(self, url: str, max_retries: int = 3) -> HtmlFetchResult:
        """Sync fetch — 1 lần thử proxy (nếu có) + direct fallback.
        Browser chỉ restart khi proxy config thay đổi (tránh tốn 20s/lần)."""
        result = HtmlFetchResult(url, self.worker_id)

        proxy_to_try = random.choice(self.proxies) if self.proxies else None
        direct_attempts = max_retries - 1 if proxy_to_try else max_retries
        attempts = ([proxy_to_try] if proxy_to_try else []) + [None] * direct_attempts

        _UNSET = object()
        last_started_proxy = _UNSET  # proxy mà browser hiện tại đang dùng

        for attempt_idx, proxy in enumerate(attempts):
            label = mask_proxy_password(proxy) if proxy else "direct (không proxy)"
            self.add_log(f"━ Lần {attempt_idx + 1}/{len(attempts)}: {label}")

            # Chỉ restart browser khi proxy config thay đổi hoặc browser chưa có
            need_restart = (proxy is not last_started_proxy) or (self.driver is None)
            if need_restart:
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass
                    self.driver = None
                self._cleanup_ext_dir()

                self.current_proxy = proxy
                ok = self._start_driver_sync(proxy)
                if not ok:
                    if proxy:
                        self.add_log("⚠️ Proxy driver fail → bỏ qua, thử direct")
                    last_started_proxy = _UNSET
                    continue
                last_started_proxy = proxy
            else:
                self.add_log("♻️ Tái sử dụng browser session")

            try:
                start = time.time()
                html, cf_blocked, empty_page = self._navigate_and_get_html(url)

                if cf_blocked:
                    self.add_log("⚠️ CF challenge không pass — thử lại")
                    continue

                if empty_page:
                    if proxy:
                        self.add_log("⚠️ Proxy IP bị block → chuyển sang direct")
                    else:
                        self.add_log("⚠️ Direct connection trống — IP bị block hoặc lỗi mạng")
                    last_started_proxy = _UNSET  # force restart để đổi mode
                    continue

                cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}
                elapsed_ms = (time.time() - start) * 1000
                title, price = self._extract_product_info()

                result.proxy_used = mask_proxy_password(proxy) if proxy else 'direct'
                result.mark_success(html, {}, 200, cookies, elapsed_ms, title=title, price=price)
                self.add_log(f"✅ {len(html):,} bytes | {elapsed_ms:.0f}ms")
                return result

            except Exception as e:
                self.add_log(f"❌ {type(e).__name__}: {str(e)[:100]}")
                last_started_proxy = _UNSET  # force restart sau exception

        result.proxy_used = 'all_failed'
        result.mark_failed("Thất bại: tất cả attempts đều bị block")
        return result

    async def fetch_url(self, url: str, max_retries: int = 3) -> HtmlFetchResult:
        """Async wrapper — chạy sync UC trong thread pool."""
        return await asyncio.to_thread(self._fetch_sync, url, max_retries)

    async def close_browser(self):
        def _quit():
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
            self._cleanup_ext_dir()
        await asyncio.to_thread(_quit)
        self.driver = None
        self.add_log("🔒 Browser đã đóng")
