import os
from typing import List

import pandas as pd

PROXY_DIR = os.environ.get('PROXY_DIR', '/app/Proxy')

MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '5'))


def load_proxies_from_excel() -> List[str]:
    """Đọc proxy từ file Excel"""
    force_proxy = os.environ.get('FORCE_PROXY')
    if force_proxy:
        print(f"⚡ FORCE_PROXY: {force_proxy}")
        return [force_proxy]

    try:
        excel_path = os.path.join(PROXY_DIR, "buyproxies_List.xlsx")
        print(f"\n📖 Reading proxies from file: {excel_path}")

        if not os.path.exists(excel_path):
            print(f"⚠️ File not found: {excel_path}")
            return []

        df = pd.read_excel(excel_path, header=None)
        proxies = []

        if df.shape[1] >= 2:
            for _, row in df.iterrows():
                proxy = row[1]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())
        else:
            for _, row in df.iterrows():
                proxy = row[0]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())

        print(f"✅ Read {len(proxies)} proxies")
        return proxies

    except Exception as e:
        print(f"❌ Error reading proxies: {e}")
        return []
