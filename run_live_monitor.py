import sys
import os
import json
import logging
import uvicorn
from threading import Thread

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.telegram_alerts.telegram_bot import TelegramAlertBot
from backend.telegram_alerts.mt5_monitor import MT5LiveMonitor
from backend.api.server import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ict_live")

def main():
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    data_dir = r"C:\Users\Vijayakumar R\Documents"
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF", "USATECHIDXUSD", "USA500IDXUSD", "USA30IDXUSD", "XAUUSD"]
    
    bot_token = ""
    chat_id = ""
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            data_dir = cfg.get("data_dir", data_dir)
            tg_cfg = cfg.get("telegram", {})
            bot_token = tg_cfg.get("bot_token", "")
            chat_id = tg_cfg.get("chat_id", "")
            
    telegram_bot = TelegramAlertBot(bot_token, chat_id)
    if telegram_bot.is_configured():
        logger.info("Telegram Bot is configured and active.")
        telegram_bot.send_test_message()
    else:
        logger.warning("Telegram Bot is not fully configured in config/config.json. Update credentials to receive mobile alerts.")
        
    monitor = MT5LiveMonitor(data_dir, pairs, telegram_bot, check_interval_sec=30)
    
    # Start live scanner background thread
    monitor_thread = Thread(target=monitor.start_loop, daemon=True)
    monitor_thread.start()
    
    logger.info("Starting Web Dashboard & API Server on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
