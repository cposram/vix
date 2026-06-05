import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone

# --- 讀取 GitHub Secrets ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram_msg(msg):
    """發送 Telegram 訊息"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Telegram Token 或 Chat ID，跳過推播。")
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

def get_closest_strike(val):
    """台指選擇權履約價以 50 點為一階，自動四捨五入取整"""
    return int(round(val / 50.0) * 50)

def main():
    # 設定台灣時間 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] 啟動 VIX 鐵鷹監控雷達...")

    # --- 新增：判斷是否為定時回報時間 (早上 09:30 或 晚上 21:30) ---
    # 因為 GitHub Actions 每 30 分鐘執行一次，我們檢查小時與分鐘區間
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

        # 4. 如果「既沒有異常」也「不是定時回報時間」，就直接結束
        if not is_abnormal and not is_report_time:
            print("✅ 目前波動率正常，且非定時回報時間，不發送通知。")
            return

        # 5. 開始建立推播訊息
        if is_abnormal:
            title = "🚨 <b>【VIX 鐵鷹建倉警報】</b> 🚨"
            status_text = "💡 <i>狀態：權利金極度肥大，風險已鎖定，可直接建倉！</i>"
        else:
            title = "📊 <b>【VIX 鐵鷹定時回報】</b> 📊"
            status_text = "💡 <i>狀態：目前波動率正常，程式運行中。</i>"

        # 自動計算距離接下來兩個「星期三」的實際天數
        days_to_wed1 = (2 - now_tw.weekday()) % 7
        if days_to_wed1 == 0: days_to_wed1 = 7 # 如果今天是週三，直接抓下週三
        days_to_wed2 = days_to_wed1 + 7

        msg_lines = [
            title,
            f"📅 時間：<code>{now_tw.strftime('%m/%d %H:%M')}</code> (台灣)",
            f"📈 指數：<b>{current_price:.0f}</b>",
            f"🔥 波動率：<b>{current_hv:.2f}%</b> (90% 臨界值: {hv_90th:.2f}%)",
            status_text,
            ""
        ]

        # 迴圈產出「近週」與「次週」合約指令
        for days, label in [(days_to_wed1, "近週合約 (本週三結算)"), (days_to_wed2, "次週合約 (下週三或月結算)")]:
            calc_days = max(days, 0.5) # 防止天數為 0 導致數學錯誤
            expected_range = current_price * (current_hv / 100) * np.sqrt(calc_days / 252)
            
            sell_call_strike = get_closest_strike(current_price + expected_range)
            sell_put_strike = get_closest_strike(current_price - expected_range)
            buy_call_strike = sell_call_strike + 100
            buy_put_strike = sell_put_strike - 100
            
            msg_lines.append(f"🛡️ <b>【{label}】</b>")
            msg_lines.append(f"🔺 上方防護：賣 <code>{sell_call_strike}C</code> / 買 <code>{buy_call_strike}C</code>")
            msg_lines.append(f"🔻 下方防護：賣 <code>{sell_put_strike}P</code> / 買 <code>{buy_put_strike}P</code>")
            msg_lines.append("")

        # 發送 Telegram
        final_msg = "\n".join(msg_lines)
        send_telegram_msg(final_msg)

    except Exception as e:
        print(f"❌ 執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
