from typing import Dict, List, Optional
from datetime import datetime

class ProductResult:
    """Model cho kết quả sản phẩm"""
    def __init__(self, key: str, url: str, worker_id: int):
        self.key = key
        self.url = url
        self.status = 'pending'
        self.error = None
        self.name = None
        self.price = None
        self.raw_json = None
        self.timestamp = datetime.now().isoformat()
        self.proxy_used = 'No proxy'
        self.proxy_country = 'Unknown'
        self.worker_id = worker_id
    
    def to_dict(self) -> Dict:
        return {
            'key': self.key,
            'url': self.url,
            'status': self.status,
            'error': self.error,
            'name': self.name,
            'price': self.price,
            'raw_json': self.raw_json,
            'timestamp': self.timestamp,
            'proxy_used': self.proxy_used,
            'proxy_country': self.proxy_country,
            'worker_id': self.worker_id
        }
    
    def mark_success(self, name: str, price: str, json_data: Dict):
        self.status = 'success'
        self.name = name
        self.price = price
        self.raw_json = json_data
    
    def mark_failed(self, error: str):
        self.status = 'failed'
        self.error = error


class WorkerResult:
    """Model cho kết quả worker"""
    def __init__(self, worker_id: int, total_keys: int):
        self.worker_id = worker_id
        self.total = total_keys
        self.success = 0
        self.failed = 0
        self.elapsed_seconds = 0
        self.error = None
        self.results = []
    
    def to_dict(self) -> Dict:
        return {
            'worker_id': self.worker_id,
            'total': self.total,
            'success': self.success,
            'failed': self.failed,
            'elapsed_seconds': self.elapsed_seconds,
            'error': self.error,
            'results': self.results
        }