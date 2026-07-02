import asyncio
import os
import random
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
import psutil

from utils import mask_proxy_password, get_country_flag, parse_proxy


class HtmlFetchResult:
    """Kết quả fetch HTML cho một URL"""
    def __init__(self, url: str, worker_id: int):
        self.url = url
        self.worker_id = worker_id
        self.html = ""
        self.headers = {}
        self.http_code = 0
        self.cookies = {}
        self.elapsed_ms = 0
        self.error = None
        self.status = "pending"
    
    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'html': self.html,
            'headers': self.headers,
            'http_code': self.http_code,
            'cookies': self.cookies,
            'elapsed_ms': self.elapsed_ms,
            'error': self.error,
            'status': self.status,
        }
    
    def mark_success(self, html: str, headers: Dict, http_code: int, cookies: Dict, elapsed_ms: float):
        self.html = html
        self.headers = headers
        self.http_code = http_code
        self.cookies = cookies
        self.elapsed_ms = elapsed_ms
        self.status = "success"
    
    def mark_failed(self, error: str):
        self.error = error
        self.status = "failed"


class FnacHtmlFetcher:
    def __init__(self, proxy_list: List[str], worker_id: int = 0):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.success_count = 0
        self.failed_count = 0
        self.proxies = proxy_list.copy()
        random.shuffle(self.proxies)
        self.requests_per_proxy = 20
        self.request_count_per_proxy = 0
        self.current_proxy = None
        self.current_proxy_country = None
        self.worker_id = worker_id
        self.process = psutil.Process()
        self.request_times = []
        self.total_keys = 0
        self.current_key = ""
        self.chromium_path = os.environ.get('CHROMIUM_PATH') or None
        self.log_buffer: List[str] = []

    def add_log(self, message: str):
        self.log_buffer.append(message)
        print(f"[worker-{self.worker_id}] {message}")

    async def check_proxy_country(self):
        try:
            js_code = """
            async () => {
                try {
                    const resp = await fetch('http://ip-api.com/json/?fields=query,country,countryCode,isp,org', { 
                        signal: AbortSignal.timeout(5000) 
                    });
                    const data = await resp.json();
                    if (data.status !== 'fail') {
                        return { source: 'ip-api', ip: data.query, country: data.country, code: data.countryCode, isp: data.isp || data.org || '' };
                    }
                } catch(e) {}
                
                try {
                    const resp = await fetch('http://httpbin.org/get', { signal: AbortSignal.timeout(5000) });
                    const data = await resp.json();
                    return { source: 'httpbin', ip: data.origin, country: '', code: '', isp: '' };
                } catch(e) {}
                
                try {
                    const resp = await fetch('http://ident.me/.json', { signal: AbortSignal.timeout(5000) });
                    const data = await resp.json();
                    return { source: 'identme', ip: data.ip || '', country: '', code: '', isp: '' };
                } catch(e) {}
                
                return { source: 'none', ip: '', country: '', code: '', isp: '' };
            }
            """
            result = await self.page.evaluate(js_code)
            if result and result.get('ip'):
                ip = result.get('ip', 'N/A')
                country = result.get('country', '')
                country_code = result.get('code', '')
                isp = result.get('isp', '')
                if country:
                    flag = get_country_flag(country_code) if len(country_code) == 2 else ""
                    country_info = f"{flag} {country}" if flag else country
                    self.current_proxy_country = country_info
                    self.add_log(f"🌍 Proxy IP: {ip} | {country_info} | ISP: {isp[:40]}")
                else:
                    self.current_proxy_country = f"✅ {ip}"
                    self.add_log(f"🌍 Proxy is working - IP: {ip}")
                return country or ip
            else:
                self.add_log("⚠️ Proxy is NOT working (all 3 APIs failed to respond)")
                return None
        except Exception as e:
            self.add_log(f"⚠️ Error checking proxy: {e}")
            return None
    
    async def start_browser_with_proxy(self, proxy_string: Optional[str] = None):
        # (giữ nguyên code cũ - không thay đổi)
        if proxy_string:
            proxy_config = parse_proxy(proxy_string)
            if not proxy_config:
                return False
        else:
            proxy_config = None
        try:
            if self.page:
                try:
                    await self.page.close()
                except:
                    pass
                self.page = None
            if self.context:
                try:
                    await self.context.close()
                except:
                    pass
                self.context = None
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None
            if not self.playwright:
                self.playwright = await async_playwright().start()
            args = [
                '--disable-blink-features=AutomationControlled',
                '--ignore-certificate-errors',
                '--disable-notifications',
                '--disable-popup-blocking',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--incognito',
            ]
            if proxy_config:
                masked = mask_proxy_password(proxy_string)
                self.add_log(f"🌐 Using proxy: {masked}")
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    executable_path=self.chromium_path,
                    args=args,
                    proxy=proxy_config
                )
            else:
                self.add_log("🌐 Not using proxy (direct connection)")
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    executable_path=self.chromium_path,
                    args=args
                )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                locale='fr-FR',
                no_viewport=False,
            )
            self.page = await self.context.new_page()
            self.add_log("✅ Browser started successfully")
            await self.check_proxy_country()
            return True
        except Exception as e:
            self.add_log(f"❌ Error starting browser: {e}")
            return False
    
    async def restart_browser_with_new_proxy(self):
        if not self.proxies:
            return False
        self.current_proxy = self.get_next_proxy()
        success = await self.start_browser_with_proxy(self.current_proxy)
        if success:
            self.request_count_per_proxy = 0
            return True
        return False
    
    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        self.add_log(f"🔀 Randomly selected proxy: {mask_proxy_password(proxy)}")
        return proxy
    
    def build_url(self, key: str) -> str:
        return key if key.startswith('http') else f"https://www.fnac.com/{key}"
    
    async def fetch_page(self, url: str, max_retries: int = 3) -> HtmlFetchResult:
        request_start = time.time()
        result = HtmlFetchResult(url, self.worker_id)
        for attempt in range(max_retries):
            try:
                response = await self.page.goto(url, wait_until='networkidle', timeout=60000)
                if response:
                    result.http_code = response.status
                    result.headers = dict(response.headers)
                else:
                    result.http_code = 0
                result.html = await self.page.content()
                cookies_list = await self.context.cookies()
                result.cookies = {c['name']: c['value'] for c in cookies_list}
                elapsed_ms = (time.time() - request_start) * 1000
                result.elapsed_ms = elapsed_ms
                if result.http_code in (403, 429, 503):
                    if attempt < max_retries - 1:
                        self.add_log(f"⚠️ HTTP {result.http_code} attempt {attempt+1}, retrying in 5s...")
                        await asyncio.sleep(5)
                        continue
                    result.mark_failed(f'HTTP {result.http_code}')
                    return result
                if result.http_code == 0 or result.http_code >= 400:
                    result.mark_failed(f'HTTP {result.http_code}')
                    return result
                result.mark_success(result.html, result.headers, result.http_code, result.cookies, elapsed_ms)
                return result
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    self.add_log(f"⚠️ Attempt {attempt+1} failed: {error_msg[:100]}. Retrying in 3s...")
                    await asyncio.sleep(3)
                else:
                    result.mark_failed(error_msg)
                    return result
        return result
    
    async def fetch_product_info(self, key: str, index: int, total: int) -> HtmlFetchResult:
        self.current_key = key
        url = self.build_url(key)
        result = HtmlFetchResult(url, self.worker_id)
        try:
            if self.proxies and self.request_count_per_proxy >= self.requests_per_proxy:
                await self.restart_browser_with_new_proxy()
            self.add_log(f"🌐 Loading: {url[:80]}...")
            result = await self.fetch_page(url, max_retries=3)
            if result.status == 'success':
                self.success_count += 1
                self.request_count_per_proxy += 1
                self.results.append(result)
                # KHÔNG LƯU FILE JSON
                proxy_flag = self.current_proxy_country or '🌐'
                self.add_log(f"✅ SUCCESS #{index}: HTTP {result.http_code} | {len(result.html):,} bytes | {result.elapsed_ms:.0f}ms | {proxy_flag}")
            else:
                self.failed_count += 1
                self.request_count_per_proxy += 1
                self.add_log(f"❌ FAILED #{index}: {(result.error or 'unknown error')[:100]}")
        except Exception as e:
            result.mark_failed(str(e))
            self.failed_count += 1
            self.request_count_per_proxy += 1
            self.add_log(f"❌ ERROR: {str(e)[:80]}")
        if result.elapsed_ms > 0:
            self.request_times.append(result.elapsed_ms / 1000)
        return result

    async def process_keys(self, keys: List[str]) -> List[HtmlFetchResult]:
        results = []
        self.total_keys = len(keys)
        self.success_count = 0
        self.failed_count = 0
        if self.proxies:
            self.current_proxy = self.get_next_proxy()
            if not await self.start_browser_with_proxy(self.current_proxy):
                for _ in range(min(len(self.proxies), 3)):
                    self.current_proxy = self.get_next_proxy()
                    if await self.start_browser_with_proxy(self.current_proxy):
                        break
        else:
            await self.start_browser_with_proxy(None)
        self.add_log(f"🚀 Starting to load {self.total_keys} URL(s)")
        for i, key in enumerate(keys, 1):
            result = await self.fetch_product_info(key, i, self.total_keys)
            results.append(result)
            if i < self.total_keys:
                delay = random.uniform(5, 20)
                await asyncio.sleep(delay)
        avg_time = sum(self.request_times) / len(self.request_times) if self.request_times else 0
        self.add_log(f"📊 DONE! Avg: {avg_time:.1f}s/url | ✅{self.success_count} ❌{self.failed_count}")
        return results
    
    async def process_keys_with_retry(self, keys: List[str], max_retries: int = 2) -> List[HtmlFetchResult]:
        all_results = []
        current_keys = keys.copy()
        retry_count = 0
        while current_keys and retry_count <= max_retries:
            if retry_count > 0:
                if not self.proxies:
                    self.add_log(f"❌ No proxy available to retry — stopping")
                    existing_urls = {r.url for r in all_results}
                    for key in current_keys:
                        url = self.build_url(key)
                        if url not in existing_urls:
                            r = HtmlFetchResult(url, self.worker_id)
                            r.mark_failed('No proxy available')
                            all_results.append(r)
                    return all_results
                self.add_log(f"🔄 ATTEMPT {retry_count}: Retrying {len(current_keys)} failed URL(s)...")
                await asyncio.sleep(10)
            results = await self.process_keys(current_keys)
            success_results = [r for r in results if r.status == 'success']
            failed_results = [r for r in results if r.status == 'failed']
            all_results.extend(success_results)
            current_keys = [r.url for r in failed_results]
            retry_count += 1
            self.add_log(f"📊 Round {retry_count}: Success: {len(success_results)}, Failed: {len(failed_results)}")
        if current_keys:
            self.add_log(f"⚠️ {len(current_keys)} URL(s) still failed after {max_retries} retries")
            existing_urls = {r.url for r in all_results}
            for url in current_keys:
                if url not in existing_urls:
                    failed_result = HtmlFetchResult(url, self.worker_id)
                    failed_result.mark_failed('Failed after all retries')
                    all_results.append(failed_result)
        return all_results
    
    async def close_browser(self):
        try:
            if self.page:
                await self.page.close()
        except:
            pass
        self.page = None
        try:
            if self.context:
                await self.context.close()
        except:
            pass
        self.context = None
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        self.browser = None
        self.add_log("🔒 Browser closed")