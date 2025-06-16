#!/usr/bin/env python3
import sys, time, logging
from pathlib import Path

import numpy as np
import pandas as pd
import joblib


MODEL_PATH   = Path("models.joblib")
CSV_PATH     = Path("20.csv")
OUT_PATH     = Path("allpred.csv") 
THRESHOLD    = 0.0 

MEDIANS_PATH = Path("medians25.npy")
MEAN_PATH    = Path("scaler_mean25.npy") 
STD_PATH     = Path("scaler_std25.npy") 

TOP_FEATURES = [
        'Fwd Packet Length Min', 'Min Packet Length', 'Average Packet Size', 
        'Protocol', 'URG Flag Count', 'Avg Fwd Segment Size', 'Fwd Packet Length Mean',
          'Down/Up Ratio', 'Packet Length Mean', 'Flow Packets/s', 'Fwd Packets/s', 
          'Flow Bytes/s', 'CWE Flag Count', 'Bwd Packet Length Min', 'ACK Flag Count', 
          'Avg Bwd Segment Size', 'RST Flag Count', 'Max Packet Length', 
          'Fwd Packet Length Max', 'Fwd PSH Flags', 'Bwd Packet Length Mean', 'Subflow Bwd Packets',
            'Total Backward Packets', 'Init_Win_bytes_forward', 'Bwd Packet Length Max'
        ]


try:
    MEDIANS = np.load(MEDIANS_PATH)
    MEAN    = np.load(MEAN_PATH)
    STD     = np.load(STD_PATH)
except FileNotFoundError as e:
    sys.exit(f"[FATAL] preproc files missing: {e.filename}")

assert MEDIANS.shape == MEAN.shape == STD.shape == (25,), \
    f"[FATAL] preproc files must have shape (25,) but got " \
    f"{MEDIANS.shape}, {MEAN.shape}, {STD.shape}"

STD[STD == 0] = 1.0                  
def preprocess(df_raw: pd.DataFrame) -> np.ndarray:
    for col in TOP_FEATURES:
        if col not in df_raw.columns:
            logging.warning("Missing column %s – filled with NaN.", col)
            df_raw[col] = np.nan

    X = df_raw[TOP_FEATURES].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)

    mask_nan = np.isnan(X)
    if mask_nan.any():
        X[mask_nan] = np.take(MEDIANS, np.where(mask_nan)[1])

    X = (X - MEAN) / STD
    return X

def collect_flows() -> pd.DataFrame:
    if not CSV_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(CSV_PATH, low_memory=False)
    except Exception as exc:
        logging.exception("Error reading csv: %s", exc)
        return pd.DataFrame()

def append_predictions(df_pred: pd.DataFrame) -> None:
    header = not OUT_PATH.exists()
    df_pred.to_csv(OUT_PATH, mode='a', index=False, header=header)


def main() -> None:
    if not MODEL_PATH.exists():
        sys.exit(f"[FATAL] Model not found: {MODEL_PATH}")
    clf = joblib.load(MODEL_PATH)
    logging.info("Model %s încărcat.", MODEL_PATH.name)

    while True:
        try:
            df_raw = collect_flows()
            if df_raw.empty:
                time.sleep(1)
                continue

            if 'Source IP' not in df_raw.columns:
                df_raw['Source IP'] = '0.0.0.0'

            X = preprocess(df_raw)

            probs = clf.predict_proba(X)[:, 1]
            df_raw['probability'] = probs

            append_predictions(
                df_raw[['Source IP', 'probability']]
                  .rename(columns={'Source IP': 'source_ip'})
            )

            for _, row in df_raw[df_raw['probability'] >= THRESHOLD].iterrows():
                logging.warning("Suspicious %s  p=%.3f",
                                row['Source IP'], row['probability'])

            break 

        except KeyboardInterrupt:
            logging.info("Interrupted by user – exiting.")
            break
        except Exception as exc:
            logging.exception("Processing error: %s", exc)
            time.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    main()
