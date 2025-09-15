import requests
from pathlib import Path

# Where to save
outdir = Path("data/sec")
outdir.mkdir(parents=True, exist_ok=True)

# 10-K complete submission text files (public domain; polite UA required)
files = {
    "apple_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123.txt",
    "microsoft_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/0000950170-25-100235.txt",
    "netflix_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/1065280/000106528025000044/0001065280-25-000044.txt",
    "amazon_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/1018724/000101872425000004/0001018724-25-000004.txt",
    "nvidia_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/0001045810-25-000023.txt",
    "google_2025_10k.txt": "https://www.sec.gov/Archives/edgar/data/1652044/000165204425000014/0001652044-25-000014.txt",
}

headers = {"User-Agent": "SecureRAG-Project (harshvardhanvn1@gmail.com)"}

for name, url in files.items():
    path = outdir / name
    if path.exists():
        print(f"Skipping {name}, already exists")
        continue
    print(f"Downloading {name} ...")
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    path.write_text(r.text, encoding="utf-8")
    print(f"Saved {path}")
