
# main.py
import os
import re
import socket
import time
import statistics
from datetime import datetime
from urllib.parse import urlparse

import requests
from appwrite.client import Client
from appwrite.services.storage import Storage

# ====== Configuration ======
SOURCES = os.getenv("V2RAY_SOURCES", "").split(",")
TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "3"))
BUCKET_ID = os.getenv("BUCKET_ID")

# ====== Appwrite Client ======
client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
client.set_key(os.getenv("APPWRITE_API_KEY"))
storage = Storage(client)

PATTERN = r"(vmess://[^\s]+|vless://[^\s]+|trojan://[^\s]+|ss://[^\s]+)"

def fetch_links():
    links = []
    for src in SOURCES:
        if not src:
            continue
        try:
            r = requests.get(src, timeout=10)
            if r.status_code == 200:
                links.extend(re.findall(PATTERN, r.text))
        except Exception as e:
            print(f"Source error {src}: {e}")
    return list(set(links))

def extract_host(link):
    try:
        parsed = urlparse(link)
        return parsed.hostname
    except Exception:
        return None

def tcp_ping(host, port=443, attempts=3):
    times = []
    for _ in range(attempts):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(TIMEOUT)
            start = time.time()
            s.connect((host, port))
            times.append((time.time() - start) * 1000)
            s.close()
        except Exception:
            pass
    if not times:
        return None
    return statistics.mean(times)

def evaluate_links(links):
    scored = []
    for link in links:
        host = extract_host(link)
        if not host:
            continue
        latency = tcp_ping(host)
        if latency:
            scored.append((latency, link))
    scored.sort(key=lambda x: x[0])
    return [l for _, l in scored]

def write_and_upload(links):
    date = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"v2ray-links-{date}.txt"
    path = os.path.join("/tmp", filename)
    with open(path, "w", encoding="utf-8") as f:
        for l in links:
            f.write(l + "\n")
    storage.create_file(bucket_id=BUCKET_ID, file_id="unique()", file_path=path)
    print("Uploaded:", filename)

def main(req, res):
    links = fetch_links()
    good = evaluate_links(links)
    write_and_upload(good)
    return res.json({"status": "ok", "count": len(good)})
