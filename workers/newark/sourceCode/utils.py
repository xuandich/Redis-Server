import os
import pandas as pd
from typing import List


def load_proxies_from_excel(excel_path: str = "Proxy/buyproxies_List.xlsx") -> List[str]:
    try:
        print(f"\n📖 Reading proxies from file: {excel_path}")

        if not os.path.exists(excel_path):
            return []

        df = pd.read_excel(excel_path, header=None)
        proxies = []

        if df.shape[1] >= 2:
            for _, row in df.iterrows():
                proxy = row[1]
                if pd.notna(proxy) and str(proxy).strip():
                    proxies.append(str(proxy).strip())

        print(f"✅ Read {len(proxies)} proxies")
        return proxies

    except Exception as e:
        print(f"❌ Error: {e}")
        return []
