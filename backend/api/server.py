import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest
from backend.telegram_alerts.telegram_bot import TelegramAlertBot
from backend.telegram_alerts.mt5_monitor import MT5LiveMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ict_server")

app = FastAPI(title="ICT Trading System & Backtesting API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.json")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

class BacktestRequest(BaseModel):
    pairs: List[str] = ["GBPUSD", "EURUSD", "USDJPY"]
    timeframe: str = "5m"
    starting_balance: float = 200.0
    risk_percent: float = 1.0
    min_rr: float = 2.0
    max_slippage_pips: float = 0.5
    commission_per_lot: float = 3.50
    setup_ids: Optional[List[int]] = None  # None = all 10 setups

class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str

@app.get("/api/config")
def get_config_endpoint():
    return load_config()

@app.post("/api/config")
def update_config_endpoint(new_cfg: Dict[str, Any]):
    save_config(new_cfg)
    return {"status": "success", "config": new_cfg}

@app.post("/api/telegram/test")
def test_telegram_endpoint(req: TelegramTestRequest):
    bot = TelegramAlertBot(req.bot_token, req.chat_id)
    success = bot.send_test_message()
    if success:
        return {"status": "success", "message": "Test notification sent to Telegram!"}
    else:
        raise HTTPException(status_code=400, detail="Failed to send Telegram message. Check Bot Token & Chat ID.")

@app.post("/api/backtest")
def run_backtest_endpoint(req: BacktestRequest):
    cfg = load_config()
    data_dir = cfg.get("data_dir", r"C:\Users\Vijayakumar R\Documents")
    
    results_by_pair = {}
    aggregated_trades = []
    
    for pair in req.pairs:
        try:
            df = load_pair_data(data_dir, pair, sample_ratio=0.3)
            df_res = resample_candles(df, req.timeframe)
            signals = get_all_setup_signals(df_res, pair, min_rr=req.min_rr)
            
            if req.setup_ids:
                signals = [s for s in signals if s['setup_id'] in req.setup_ids]
                
            res = execute_backtest(
                df_res,
                signals,
                pair,
                starting_balance=req.starting_balance,
                risk_percent=req.risk_percent,
                max_slippage_pips=req.max_slippage_pips,
                commission_per_lot=req.commission_per_lot
            )
            results_by_pair[pair] = res
            aggregated_trades.extend(res['trades'])
        except Exception as e:
            logger.error(f"Error backtesting pair {pair}: {e}")
            results_by_pair[pair] = {"error": str(e)}
            
    # Calculate Overall Portfolio Metrics
    total_trades = sum(r.get('total_trades', 0) for r in results_by_pair.values() if 'total_trades' in r)
    total_wins = sum(r.get('winning_trades', 0) for r in results_by_pair.values() if 'winning_trades' in r)
    total_losses = sum(r.get('losing_trades', 0) for r in results_by_pair.values() if 'losing_trades' in r)
    overall_win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
    
    total_profit = sum(r.get('net_profit', 0.0) for r in results_by_pair.values() if 'net_profit' in r)
    
    # Calculate per-setup metrics for ALL 10 SETUPS
    setup_names_map = {
        1: "Liquidity Sweep + FVG",
        2: "Liquidity Sweep + IFVG",
        3: "ICT Silver Bullet",
        4: "Turtle Soup Reversal",
        5: "OB + FVG Confluence",
        6: "🦄 Unicorn (Breaker + FVG)",
        7: "🐢 Turtle Soup (MSS + FVG)",
        8: "🎯 OTE (61.8%-78.6% Fib)",
        9: "🔄 Breaker Block Retest",
        10: "📈 AMD / Power of 3"
    }
    
    setup_stats = {i: {"setup_id": i, "name": setup_names_map[i], "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_pnl": 0.0} for i in range(1, 11)}
    for t in aggregated_trades:
        sid = t['setup_id']
        if sid in setup_stats:
            setup_stats[sid]['trades'] += 1
            if t['outcome'] == 'WIN':
                setup_stats[sid]['wins'] += 1
            else:
                setup_stats[sid]['losses'] += 1
            setup_stats[sid]['net_pnl'] += t['net_pnl']
            
    for sid, s in setup_stats.items():
        if s['trades'] > 0:
            s['win_rate'] = round((s['wins'] / s['trades']) * 100.0, 1)
            s['net_pnl'] = round(s['net_pnl'], 2)
            
    return {
        "overall": {
            "total_trades": total_trades,
            "winning_trades": total_wins,
            "losing_trades": total_losses,
            "win_rate_pct": round(overall_win_rate, 2),
            "total_net_profit": round(total_profit, 2),
            "starting_balance": req.starting_balance,
            "ending_balance": round(req.starting_balance + total_profit, 2)
        },
        "by_setup": list(setup_stats.values()),
        "by_pair": results_by_pair
    }

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
