import os
from typing import List
import pandas as pd


PROXY_DIR = os.environ.get('PROXY_DIR', '/app/Proxy')


def ensure_directories():
    os.makedirs(PROXY_DIR, exist_ok=True)


def load_proxies_from_excel() -> List[str]:
    # Cho phép force một proxy cụ thể qua env (dùng để test)
    force_proxy = os.environ.get('FORCE_PROXY')
    if force_proxy:
        print(f"⚡ FORCE_PROXY: {force_proxy}")
        return [force_proxy]

    """Đọc proxy từ file Excel"""
    try:
        excel_path = os.path.join(PROXY_DIR, "buyproxies_List.xlsx")
        print(f"\n📖 Đang đọc proxy từ file: {excel_path}")
        
        if not os.path.exists(excel_path):
            print(f"⚠️ Không tìm thấy file {excel_path}")
            return []
        
        df = pd.read_excel(excel_path, header=None)
        proxies = []
        
        if df.shape[1] >= 2:
            for idx, row in df.iterrows():
                proxy = row[1]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())
        else:
            for idx, row in df.iterrows():
                proxy = row[0]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())
        
        print(f"✅ Đã đọc {len(proxies)} proxies")
        return proxies
        
    except Exception as e:
        print(f"❌ Lỗi đọc proxy: {e}")
        return []
