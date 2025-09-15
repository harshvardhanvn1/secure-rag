import re
from pathlib import Path
from bs4 import BeautifulSoup

RAW_DIR = Path("data/sec")
OUT_DIR = RAW_DIR / "clean"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def pick_10k_document(txt: str) -> str:
    docs = re.split(r"(?i)(?=<DOCUMENT>)", txt)
    best = None
    for d in docs:
        m = re.search(r"(?im)^<TYPE>\s*([^\r\n<]+)", d)
        if m and m.group(1).strip().upper() == "10-K":
            best = d
            break
    if not best and docs:
        best = docs[0]
    return best or txt

def extract_text_block(doc_block: str) -> str:
    m = re.search(r"(?is)<TEXT>(.*?)</TEXT>", doc_block)
    return m.group(1) if m else doc_block

def strip_sec_headers(txt: str) -> str:
    txt = re.sub(r"(?is)<SEC-HEADER>.*?</SEC-HEADER>", " ", txt)
    txt = re.sub(r"(?im)^<PAGE>.*?$", " ", txt)
    return txt

def html_to_text(maybe_html: str) -> str:
    lower = maybe_html.lower()
    if "<html" in lower or "<div" in lower or "<p" in lower or "<table" in lower:
        soup = BeautifulSoup(maybe_html, "html.parser")
        return soup.get_text(separator="\n")
    return maybe_html

def normalize_whitespace(txt: str) -> str:
    txt = re.sub(r"\r", "\n", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()

def clean_sec_file(raw: str) -> str:
    raw = strip_sec_headers(raw)
    doc = pick_10k_document(raw)
    body = extract_text_block(doc)
    text = html_to_text(body)
    return normalize_whitespace(text)

def main():
    in_paths = sorted(RAW_DIR.glob("*.txt"))
    if not in_paths:
        print("No .txt files in data/sec — run scripts/download_sec.py first.")
        return
    for p in in_paths:
        outp = OUT_DIR / p.name
        raw = p.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_sec_file(raw)
        outp.write_text(cleaned, encoding="utf-8")
        print(f"Cleaned -> {outp}")

if __name__ == "__main__":
    main()
