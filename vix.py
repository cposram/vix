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
    """發送 Telegram 訊息"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ 未設定 Telegram Token 或 Chat ID，跳過推播。")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload, timeout=10)
        print("✅ Telegram 警報發送成功！")
    except Exception as e:
        print(f"❌ Telegram 發送失敗: {e}")

def update_github_pages(content):
    """將生成的 HTML 推送到 GitHub Pages"""
    if not GITHUB_TOKEN:
        print("⚠️ 未設定 MY_GITHUB_TOKEN，無法更新網頁。")
        return

    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}", 
        "Content-Type": "application/json"
    }
    
    # 取得當前檔案的 SHA (覆蓋檔案必須)
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    
    # Base64 編碼
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    data = {"message": "Auto-update VIX Dashboard", "content": content_b64}
    if sha: 
        data["sha"] = sha
    
    # 執行寫入
    resp = requests.put(url, headers=headers, json=data)
    if resp.status_code in [200, 201]:
        print("✅ HTML 成功寫入 GitHub Repository！網頁準備更新。")
    else:
        print(f"❌ 網頁寫入失敗: {resp.status_code} - {resp.text}")

def generate_html(current_price, current_hv, hv_90th, predictions, now_tw):
    """產生極簡的 VIX 監控 HTML"""
    rows = ""
    for p in predictions:
        rows += f"<tr><td>{p['合約目標']}</td><td>{p['上方防護(Call)']}</td><td>{p['下方防護(Put)']}</td></tr>"
    
    alert_class = "danger" if current_hv > hv_90th else "safe"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VIX 鐵鷹雷達</title>
    <style>
        body{{background:#0d1117; color:#c9d1d9; font-family:-apple-system, sans-serif; text-align:center; padding:20px; margin:0;}}
        .card{{background:#161b22; padding:20px; border-radius:10px; max-width:600px; margin:auto; border:1px solid #30363d; box-shadow: 0 4px 8px rgba(0,0,0,0.5);}}
        h3{{color:#58a6ff; margin-top:0;}}
        .danger{{color:#ff7b72; font-weight:bold;}}
        .safe{{color:#7ee787; font-weight:bold;}}
        .hl{{color:#e3b341; font-weight:bold; font-size:1.2em;}}
        table{{width:100%; margin-top:20px; border-collapse:collapse;}}
        th{{background:#21262d; padding:10px; font-size:13px; color:#8b949e; border-bottom:2px solid #30363d;}}
        td{{padding:12px 10px; border-bottom:1px solid #30363d; font-size:14px;}}
        .time{{font-size:12px; color:#8b949e; margin-bottom:20px;}}
    </style></head>
    <body><div class="card">
        <h3>🚨 VIX 鐵鷹監控雷達 🚨</h3>
        <div class="time">最後掃描: {now_tw.strftime('%Y/%m/%d %H:%M:%S')}</div>
        <p>台指期現價: <span class="hl">{current_price:.0f}</span></p>
        <p>當前 HV20 波動率: <span class="{alert_class}">{current_hv:.2f}%</span></p>
        <p style="font-size:12px; color:#8b949e;">(近一年 90% 警戒線: {hv_90th:.2f}%)</p>
        <table>
            <tr><th>結算週期</th><th>上方防護 (賣Call)</th><th>下方防護 (賣Put)</th></tr>
            {rows}
        </table>
    </div></body></html>"""
    return html

def get_closest_strike(val):
    return int(round(val / 50.0) * 50)

def main():
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] 啟動 VIX 鐵鷹監控雷達...")

    is_morning_report = (now_tw.hour == 9 and now_tw.minute >= 30)
    is_evening_report = (now_tw.hour == 21 and now_tw.minute >= 30)
    is_report_time = is_morning_report or is_evening_report

    try:
        # 1. 抓取大盤資料 (近一年)
        df = yf.Ticker("^TWII").history(period="1y")
        if df.empty:
            print("⚠️ 無法取得大盤資料，結束程式。")
            return

        # 2. 計算 20 日歷史波動率 (HV20) 與 90% 分位數
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['HV_20'] = df['Log_Return'].rolling(window=20).std() * np.sqrt(252) * 100
        df = df.dropna()
        
        current_hv = df['HV_20'].iloc[-1]
        current_price = df['Close'].iloc[-1]
        hv_90th = df['HV_20'].quantile(0.90)

        print(f"當前指數: {current_price:.0f} | 當前 HV20: {current_hv:.2f}% | 90% 警戒線: {hv_90th:.2f}%")

        # 3. 判斷是否觸發異常
        is_abnormal = current_hv > hv_90th

        # 自動計算距離接下來兩個「星期三」的實際天數
        days_to_wed1 = (2 - now_tw.weekday()) % 7
        if days_to_wed1 == 0: days_to_wed1 = 7 
        days_to_wed2 = days_to_wed1 + 7

        predictions = []
        for days, label in [(days_to_wed1, "本週三"), (days_to_wed2, "下週三")]:
            calc_days = max(days, 0.5) 
            expected_range = current_price * (current_hv / 100) * np.sqrt(calc_days / 252)
            
            sell_call_strike = get_closest_strike(current_price + expected_range)
            sell_put_strike = get_closest_strike(current_price - expected_range)
            buy_call_strike = sell_call_strike + 100
            buy_put_strike = sell_put_strike - 100
            
            predictions.append({
                "合約目標": label,
                "上方防護(Call)": f"{sell_call_strike}C",
                "下方防護(Put)": f"{sell_put_strike}P"
            })

        # ==========================================
        # 核心改動：無條件先產生並更新 HTML 網頁！
        # ==========================================
        html_content = generate_html(current_price, current_hv, hv_90th, predictions, now_tw)
        update_github_pages(html_content)

        # ==========================================
        # 網頁更新完後，再來判斷要不要吵你 (Telegram)
        # ==========================================
        if not is_abnormal and not is_report_time:
            print("✅ 波動率正常，網頁已更新，不發送 TG 通知。")
            return

        # 5. 開始建立推播訊息
        if is_abnormal:
            title = "🚨 <b>【VIX 鐵鷹建倉警報】</b> 🚨"
            status_text = "💡 <i>狀態：權利金極度肥大，可直接建倉！</i>"
        else:
            title = "📊 <b>【VIX 鐵鷹定時回報】</b> 📊"
            status_text = "💡 <i>狀態：目前波動率正常，程式運行中。</i>"

        msg_lines = [
            title,
            f"📅 時間：<code>{now_tw.strftime('%m/%d %H:%M')}</code> (台灣)",
            f"📈 指數：<b>{current_price:.0f}</b>",
            f"🔥 波動率：<b>{current_hv:.2f}%</b> (警戒值: {hv_90th:.2f}%)",
            status_text, ""
        ]

        for p in predictions:
            msg_lines.append(f"🛡️ <b>【{p['合約目標']}】</b>")
            msg_lines.append(f"🔺 上方防護：賣 <code>{p['上方防護(Call)']}</code>")
            msg_lines.append(f"🔻 下方防護：賣 <code>{p['下方防護(Put)']}</code>")
            msg_lines.append("")

        final_msg = "\n".join(msg_lines)
        send_telegram_msg(final_msg)

    except Exception as e:
        print(f"❌ 執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
