import os
import pandas as pd
from typing import List


def load_proxies_from_excel(excel_path: str = "Proxy/buyproxies_List.xlsx") -> List[str]:
    try:
        print(f"\n📖 Đang đọc proxy từ file: {excel_path}")

        if not os.path.exists(excel_path):
            return []

        df = pd.read_excel(excel_path, header=None)
        proxies = []

        if df.shape[1] >= 2:
            for _, row in df.iterrows():
                proxy = row[1]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())

        print(f"✅ Đã đọc {len(proxies)} proxies")
        return proxies

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return []


def normalize_urls(raw_urls: List[str]) -> List[str]:
    urls = []
    for raw in raw_urls:
        raw = str(raw).strip()
        if not raw:
            continue
        if raw.startswith('http'):
            urls.append(raw)
        else:
            urls.append(f'https://www.newark.com/dp/{raw}')
    return urls


def read_keys_from_excel(excel_path: str = "input/url.xlsx") -> List[str]:
    try:
        print(f"\n📖 Đang đọc file: {excel_path}")

        if not os.path.exists(excel_path):
            return []

        df = pd.read_excel(excel_path, header=None)
        raw_urls = df[0].tolist()
        raw_urls = [u for u in raw_urls if pd.notna(u) and str(u).strip()]

        urls = normalize_urls(raw_urls)

        print(f"✅ Đã đọc {len(urls)} URLs")
        return urls

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return []
