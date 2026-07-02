from pathlib import Path
from typing import Optional, Dict

AMAZON_DOMAIN = 'amazon.fr'
AMAZON_COUNTRY = 'France'
AMAZON_POSTAL_CODE = '75001'

COOKIE_DIR = 'cookies'


def mask_proxy_password(proxy: str) -> str:
    """Che giấu mật khẩu proxy"""
    if not proxy:
        return "None"
    if '@' in proxy:
        parts = proxy.split('@')
        if ':' in parts[0]:
            user = parts[0].split(':')[0]
            return f"{user}:****@{parts[1]}"
    return proxy


def parse_proxy(proxy_string: str) -> Optional[Dict]:
    """Parse proxy string thành dict với host, port, username, password"""
    proxy_string = str(proxy_string).strip()
    try:
        if '@' in proxy_string:
            auth_part, server_part = proxy_string.split('@')
            username, password = auth_part.split(':', 1) if ':' in auth_part else (auth_part, '')
            host, port = server_part.rsplit(':', 1) if ':' in server_part else (server_part, '8080')
            return {
                'server': f'http://{host}:{port}',
                'username': username,
                'password': password,
                'host': host,
                'port': port,
            }
        else:
            host, port = proxy_string.rsplit(':', 1) if ':' in proxy_string else (proxy_string, '8080')
            return {
                'server': f'http://{host}:{port}',
                'username': None,
                'password': None,
                'host': host,
                'port': port,
            }
    except Exception:
        return None


def load_cookie_string() -> Optional[str]:
    """Đọc cookie string của amazon.fr"""
    cookie_file = Path(COOKIE_DIR) / f"cookie_string_{AMAZON_COUNTRY}.txt"
    if cookie_file.exists():
        return cookie_file.read_text().strip() or None
    return None
