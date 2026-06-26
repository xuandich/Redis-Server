from typing import Dict


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
        self.proxy_used = None
        self.status = "pending"
        self.title = ""
        self.price = ""

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
            'title': self.title,
            'price': self.price,
        }

    def mark_success(self, html: str, headers: Dict, http_code: int, cookies: Dict, elapsed_ms: float,
                     title: str = "", price: str = ""):
        self.html = html
        self.headers = headers
        self.http_code = http_code
        self.cookies = cookies
        self.elapsed_ms = elapsed_ms
        self.status = "success"
        self.title = title
        self.price = price

    def mark_failed(self, error: str):
        self.error = error
        self.status = "failed"
