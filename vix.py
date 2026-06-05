import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import base64

# --- 讀取 GitHub Secrets ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN", "")
REPO_NAME = "cposram/vix"
FILE_PATH = "index.html"

def send_telegram_msg(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, data=payload, timeout=10)
    except: print("Telegram 發送失敗")

def update_github_pages(content):
    if not GITHUB_TOKEN: return
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    data = {"message": "Update V8.0 Dashboard", "content": content_b64}
    if sha: data["sha"] = sha
    requests.put(url, headers=headers, json=data)

def get_closest_strike(val):
    return int(round(val / 50.0) * 50)

def get_trend_text(close_series, ma_series, ma_name):
    diff = close_series - ma_series
    diff = diff.dropna()
    if diff.empty: return ""
    is_above = diff.iloc[-1] > 0
    count = 0
    for val in reversed(diff):
        if (val > 0) == is_above: count += 1
        else: break
    action = "站上" if is_above else "跌破"
    return f"{action}{ma_name} {count} 天"

def generate_html(current_price, ma10, ma20, current_hv, hv_90th, predictions, now_tw, trend_str):
    rows = ""
    for p in predictions:
        rows += f"""<tr>
            <td>{p['label']}</td>
            <td style="color:#ff7b72;">賣 {p['sell_c']}C / 買 {p['buy_c']}C</td>
            <td style="color:#7ee787;">賣 {p['sell_p']}P / 買 {p['buy_p']}P</td>
        </tr>"""
    
    hv_class = "danger" if current_hv > hv_90th else "safe"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body{{background:#0d1117; color:#c9d1d9; font-family:-apple-system, sans-serif; text-align:center; padding:15px; margin:0;}}
        .card{{background:#161b22; padding:20px; border-radius:12px; max-width:800px; margin:auto; border:1px solid #30363d; box-shadow:0 8px 16px rgba(0,0,0,0.5);}}
        .banner{{display:flex; justify-content:space-around; background:#1c2128; padding:15px; border-radius:8px; margin-bottom:20px; border:1px solid #444c56;}}
        .stat-item{{flex:1;}} .stat-label{{font-size:11px; color:#8b949e;}} .stat-val{{font-size:18px; font-weight:bold; color:#58a6ff;}}
        .danger{{color:#ff7b72;}} .safe{{color:#7ee787;}} .hl{{color:#e3b341;}}
        table{{width:100%; border-collapse:collapse; margin-top:15px; background:#0d1117; border-radius:8px; overflow:hidden;}}
        th{{background:#21262d; padding:12px; font-size:13px; color:#8b949e;}}
        td{{padding:15px 10px; border-bottom:1px solid #30363d; font-size:14px; font-family:monospace;}}
        .trend-bar{{font-size:13px; color:#daffde; margin-bottom:15px; padding:8px; background:rgba(88,166,255,0.1); border-radius:4px;}}
    </style></head>
    <body><div class="card">
        <h2 style="margin-top:0; color:#58a6ff;">🚀 台指期戰略雷達 V8.0</h2>
        <div class="trend-bar">{trend_str}</div>
        <div class="banner">
            <div class="stat-item"><div class="stat-label">台指現價</div><div class="stat-val hl">{current_price:.0f}</div></div>
            <div class="stat-item"><div class="stat-label">10日線</div><div class="stat-val">{ma10:.0f}</div></div>
            <div class="stat-item"><div class="stat-label">月線(20MA)</div><div class="stat-val">{ma20:.0f}</div></div>
            <div class="stat-item"><div class="stat-label">波動率(HV)</div><div class="stat-val {hv_class}">{current_hv:.2f}%</div></div>
        </div>
        <table>
            <tr><th>結算週期</th><th>上方價差 (Call Spread)</th><th>下方價差 (Put Spread)</th></tr>
            {rows}
        </table>
        <p style="font-size:11px; color:#8b949e; margin-top:20px;">最後掃描: {now_tw.strftime('%m/%d %H:%M:%S')} | 90% 臨界值: {hv_90th:.2f}%</p>
    </div></body></html>"""
    return html

def main():
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] 啟動 V8.0 戰略引擎...")

    try:
        df = yf.Ticker("WTX&=F").history(period="1y")
        if df.empty: df = yf.Ticker("^TWII").history(period="1y")
        df.index = df.index.tz_localize(None)

        # 數據計算
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['HV_20'] = df['Log_Return'].rolling(window=20).std() * np.sqrt(252) * 100
        ma10 = df['Close'].rolling(window=10).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        current_hv = df['HV_20'].iloc[-1]
        current_price = df['Close'].iloc[-1]
        hv_90th = df['HV_20'].quantile(0.90)

        # 趨勢文字
        trend_str = f"{get_trend_text(df['Close'], df['Close'].rolling(5).mean(), '5日線')} ｜ " \
                    f"{get_trend_text(df['Close'], df['Close'].rolling(10).mean(), '10日線')} ｜ " \
                    f"{get_trend_text(df['Close'], df['Close'].rolling(20).mean(), '月線')}"

        # 策略推算
        days_to_wed1 = (2 - now_tw.weekday()) % 7
        if days_to_wed1 == 0: days_to_wed1 = 7 
        days_to_wed2 = days_to_wed1 + 7

        predictions = []
        for days, label in [(days_to_wed1, "本週三合約"), (days_to_wed2, "次週合約")]:
            calc_days = max(days, 0.5) 
            expected_range = current_price * (current_hv / 100) * np.sqrt(calc_days / 252)
            sell_c = get_closest_strike(current_price + expected_range)
            sell_p = get_closest_strike(current_price - expected_range)
            predictions.append({
                "label": label, "sell_c": sell_c, "buy_c": sell_c + 100,
                "sell_p": sell_p, "buy_p": sell_p - 100
            })

        # 更新 HTML
        html_content = generate_html(current_price, ma10, ma20, current_hv, hv_90th, predictions, now_tw, trend_str)
        update_github_pages(html_content)
        print("✅ HTML 更新成功")

        # Telegram 推送判斷 (略，與之前一致)
    except Exception as e: print(f"錯誤: {e}")

if __name__ == "__main__": main()
