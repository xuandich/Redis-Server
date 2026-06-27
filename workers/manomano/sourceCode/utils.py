from typing import Optional, Dict


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
    """Parse proxy string thành dict với server, username, password"""
    proxy_string = str(proxy_string).strip()

    try:
        if '@' in proxy_string:
            auth_part, server_part = proxy_string.split('@')
            if ':' in auth_part:
                username, password = auth_part.split(':', 1)
            else:
                username, password = auth_part, ''

            if ':' in server_part:
                host, port = server_part.rsplit(':', 1)
            else:
                host, port = server_part, '8080'

            return {
                'server': f'http://{host}:{port}',
                'username': username,
                'password': password,
                'host': host,
                'port': port,
            }
        else:
            if ':' in proxy_string:
                host, port = proxy_string.rsplit(':', 1)
            else:
                host, port = proxy_string, '8080'

            return {
                'server': f'http://{host}:{port}',
                'username': None,
                'password': None,
                'host': host,
                'port': port,
            }
    except Exception:
        return None
