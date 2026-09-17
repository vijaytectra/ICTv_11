import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.data_loader import load_pair_data, resample_candles

def main():
    print("Testing data loader...")
    df = load_pair_data(r"C:\Users\Vijayakumar R\Documents", "GBPUSD")
    print(f"GBPUSD 1m candles loaded: {len(df)}")
    df5m = resample_candles(df, "5m")
    print(f"GBPUSD 5m candles resampled: {len(df5m)}")
    print(df5m.head(3))

if __name__ == "__main__":
    main()
