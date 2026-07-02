from typing import Dict, Optional

__all__ = ['AmazonProductResult']


class AmazonProductResult:
    """Kết quả scrape một sản phẩm Amazon"""
    def __init__(self, url: str):
        self.url = url
        self.html: str = ""
        self.headers: Dict = {}
        self.cookies: Dict = {}
        self.http_code: int = 0
        self.elapsed_ms: float = 0
        self.error: Optional[str] = None
        self.status: str = "pending"

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

    def mark_success(self, html: str, headers: Dict, cookies: Dict, http_code: int, elapsed_ms: float):
        self.html = html
        self.headers = headers
        self.cookies = cookies
        self.http_code = http_code
        self.elapsed_ms = elapsed_ms
        self.status = "success"
        self.error = None

    def mark_failed(self, error: str):
        self.error = error
        self.status = "failed"
