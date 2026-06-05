import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import base64

# --- GitHub API 設定 (用來更新 vix 網頁) ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "") # 記得在 Actions Secrets 放入 PAT
REPO_NAME = "cposram/vix"
FILE_PATH = "index.html"

def update_github_pages(content):
    """將生成的 HTML 推送到 GitHub Pages"""
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    
    # 取得當前 SHA
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    
    # Base64 編碼
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    data = {"message": "Update VIX Dashboard", "content": content_b64}
    if sha: data["sha"] = sha
    
    requests.put(url, headers=headers, json=data)
    print("✅ VIX 儀表板網頁更新成功！")

def generate_html(current_price, current_hv, hv_90th, predictions, now_tw):
    """產生極簡的 VIX 監控 HTML"""
    rows = ""
    for p in predictions:
        rows += f"<tr><td>{p['合約目標']}</td><td>{p['上方防護(Call)']}</td><td>{p['下方防護(Put)']}</td></tr>"
    
    alert_class = "danger" if current_hv > hv_90th else "safe"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body{{background:#0d1117; color:#c9d1d9; font-family:sans-serif; text-align:center; padding:20px;}}
        .card{{background:#161b22; padding:20px; border-radius:10px; max-width:600px; margin:auto; border:1px solid #30363d;}}
        .danger{{color:#ff7b72; font-weight:bold;}}
        .safe{{color:#7ee787;}}
        table{{width:100%; margin-top:20px; border-collapse:collapse;}}
        td{{padding:10px; border-bottom:1px solid #30363d; font-size:12px;}}
    </style></head>
    <body><div class="card">
        <h3>鐵鷹 VIX 監控雷達</h3>
        <p>最後更新: {now_tw.strftime('%m/%d %H:%M')}</p>
        <p>指數: <b>{current_price:.0f}</b> | 波動率: <b class="{alert_class}">{current_hv:.2f}%</b></p>
        <p>90% 臨界值: {hv_90th:.2f}%</p>
        <table>{rows}</table>
    </div></body></html>"""
    return html

# --- 原有的 main() 邏輯中，在發送 Telegram 後呼叫 ---
# 把 generate_html 和 update_github_pages 串接進去即可
