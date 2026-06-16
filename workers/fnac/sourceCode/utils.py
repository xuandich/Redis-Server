import random
from typing import Optional, Dict
import json


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
    """Parse proxy string thành dict"""
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
        return None


def save_final_results(all_products: list, worker_results: list, 
                       total_success: int, total_failed: int, 
                       duration: float, num_workers: int, max_retries: int):
    """Lưu kết quả cuối cùng"""
    import json
    import pandas as pd
    from datetime import datetime
    
    total_keys = total_success + total_failed
    
    final_output = {
        'summary': {
            'total_workers': num_workers,
            'total_keys': total_keys,
            'total_success': total_success,
            'total_failed': total_failed,
            'success_rate': f"{(total_success/total_keys*100):.1f}%" if total_keys > 0 else "0%",
            'duration_minutes': round(duration/60, 2),
            'retry_count': max_retries,
            'timestamp': datetime.now().isoformat()
        },
        'workers_summary': worker_results,
        'all_products': all_products
    }
    
    with open('output/final_summary.json', 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    
    # Export to Excel
    try:
        df_products = pd.DataFrame(all_products)
        columns_for_excel = ['key', 'name', 'price', 'status', 'proxy_used', 'proxy_country', 'worker_id', 'timestamp']
        available_cols = [col for col in columns_for_excel if col in df_products.columns]
        df_products[available_cols].to_excel('output/final_summary.xlsx', index=False)
        print(f"\n📁 Excel output: output/final_summary.xlsx")
    except Exception as e:
        print(f"\n⚠️ Không thể export Excel: {e}")