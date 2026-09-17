import time
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.telegram_alerts.telegram_bot import TelegramAlertBot

logger = logging.getLogger(__name__)

class MT5LiveMonitor:
    """
    Monitors live candle streams (or MT5 Python API feed) and triggers
    Telegram notifications when new ICT setup signals complete.
    """
    
    def __init__(self, data_dir: str, pairs: List[str], telegram_bot: TelegramAlertBot, check_interval_sec: int = 60):
        self.data_dir = data_dir
        self.pairs = pairs
        self.telegram_bot = telegram_bot
        self.check_interval_sec = check_interval_sec
        self.processed_signal_keys = set()
        self.is_running = False
        self.mt5_initialized = False
        
        self._init_mt5()
        
    def _init_mt5(self):
        """Attempts to initialize MetaTrader 5 connection if package installed."""
        try:
            import importlib
            mt5 = importlib.import_module("MetaTrader5")
            if mt5.initialize():
                self.mt5_initialized = True
                logger.info("MetaTrader 5 initialized successfully.")
            else:
                logger.info("MT5 initialize returned False. Using local live simulation feed.")
        except ImportError:
            logger.info("MetaTrader5 package not installed. Operating in local live monitoring mode.")
            self.mt5_initialized = False

    def scan_pair_for_signals(self, pair: str, timeframe: str = "5m") -> List[Dict[str, Any]]:
        """Scans the latest candle data for new completed setup signals."""
        try:
            df = load_pair_data(self.data_dir, pair, sample_ratio=0.2)  # Load recent data
            df_res = resample_candles(df, timeframe)
            signals = get_all_setup_signals(df_res, pair)
            return signals
        except Exception as e:
            logger.error(f"Error scanning pair {pair}: {e}")
            return []

    def run_once(self) -> List[Dict[str, Any]]:
        """Runs a single scan iteration across all monitored pairs."""
        new_signals = []
        for pair in self.pairs:
            signals = self.scan_pair_for_signals(pair)
            for sig in signals:
                sig_key = f"{sig['pair']}_{sig['setup_id']}_{sig['timestamp']}_{sig['direction']}"
                if sig_key not in self.processed_signal_keys:
                    self.processed_signal_keys.add(sig_key)
                    new_signals.append(sig)
                    
                    # Dispatch to Telegram if bot configured
                    if self.telegram_bot and self.telegram_bot.is_configured():
                        self.telegram_bot.send_trade_signal(sig)
                        
        return new_signals

    def start_loop(self):
        """Starts continuous monitoring loop."""
        self.is_running = True
        logger.info(f"Started MT5/Live Monitor loop across {len(self.pairs)} pairs.")
        
        while self.is_running:
            try:
                new_sigs = self.run_once()
                if new_sigs:
                    logger.info(f"Found {len(new_sigs)} new ICT setup signals.")
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            time.sleep(self.check_interval_sec)

    def stop(self):
        self.is_running = False
