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


def get_proxy_host(proxy_string: str) -> str:
    """Trích xuất host:port từ proxy string để hiển thị"""
    try:
        if '@' in proxy_string:
            server_part = proxy_string.split('@')[1]
        else:
            server_part = proxy_string
        if ':' in server_part:
            return server_part.split(':')[0]
        return server_part
    except:
        return proxy_string[:20]


def get_country_flag(country_code: str) -> str:
    """Chuyển mã quốc gia 2 ký tự thành emoji flag"""
    if not country_code or len(country_code) != 2:
        return ""
    code = country_code.upper()
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))


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
