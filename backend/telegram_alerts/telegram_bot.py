import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TelegramAlertBot:
    """Telegram Bot wrapper for dispatching ICT trade setup alerts."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and "YOUR_TELEGRAM" not in self.bot_token)
        
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured():
            logger.warning("Telegram bot is not configured properly.")
            return False
            
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            resp = requests.post(self.api_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error(f"Failed to send Telegram message. HTTP {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False

    def send_trade_signal(self, signal: Dict[str, Any], account_balance: float = 200.0, risk_pct: float = 1.0) -> bool:
        """Formats and sends a high-priority ICT trade signal to Telegram."""
        emoji = "🟢 BUY (LONG)" if signal['direction'] == 'BUY' else "🔴 SELL (SHORT)"
        risk_dollars = round(account_balance * (risk_pct / 100.0), 2)
        
        message = f"""⚡ <b>ICT TRADE SIGNAL DETECTED</b> ⚡
----------------------------------------------
<b>Pair:</b> <code>{signal['pair']}</code>
<b>Setup:</b> Setup #{signal['setup_id']} — <i>{signal['setup_name']}</i>
<b>Action:</b> {emoji}

<b>Price Levels:</b>
• <b>Entry:</b> <code>{signal['entry']}</code>
• <b>Stop Loss:</b> <code>{signal['sl']}</code> ({signal['sl_pips']} pips)
• <b>Take Profit:</b> <code>{signal['tp']}</code> (1:{signal['rr']} RR)

<b>Risk Management ($200 Account):</b>
• <b>Risk Amount:</b> ${risk_dollars} ({risk_pct}% risk)
• <b>Est. Spread:</b> {signal['spread_pips']} pips

<b>Time:</b> {signal['timestamp']} EST
----------------------------------------------
⚠️ <i>Check your chart and execute manual trade if conditions hold.</i>"""
        return self.send_message(message)

    def send_test_message(self) -> bool:
        """Sends a test message to verify Telegram setup."""
        text = """✅ <b>ICT Trading Bot Connection Successful!</b>
----------------------------------------------
Your Telegram alert notifications are active and ready.
You will receive real-time signals for ICT Setups 1 through 5 across your monitored pairs."""
        return self.send_message(text)
