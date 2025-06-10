#!/usr/bin/env python3
import sys
import time
import logging
from pathlib import Path

import pandas as pd
import joblib

MODEL_PIPELINE_PATH = Path('model_pipeline.joblib')

CSV_PATH           = Path('flows.csv')

threshold     = 0.5         # probability threshold for alerts

# ─── These must match the features used in training/inference pipeline ─────────
TOP_FEATURES = [
    'Fwd Packet Length Min', 'Min Packet Length', 'Average Packet Size',
    'Avg Fwd Segment Size', 'Inbound', 'Fwd Packet Length Mean',
    'Packet Length Mean', 'Protocol', 'Flow Bytes/s', 'Flow Packets/s',
    'URG Flag Count', 'Fwd Packets/s', 'Down/Up Ratio',
    'Fwd Packet Length Max', 'Max Packet Length', 'Init_Win_bytes_forward',
    'CWE Flag Count', 'ACK Flag Count', 'Bwd Packet Length Min',
    'RST Flag Count', 'Fwd PSH Flags', 'Packet Length Std', 'Flow Duration',
    'Avg Bwd Segment Size', 'Init_Win_bytes_backward',
    'Bwd Packet Length Mean', 'Bwd Packet Length Std',
    'Bwd Packet Length Max', 'Fwd Packet Length Std', 'Flow IAT Mean'
]


def collect_flows() -> pd.DataFrame:
    """
    Reads the CSV at CSV_PATH and returns the DataFrame (should include TOP_FEATURES).
    """
    if not CSV_PATH.exists():
        logging.error("CSV file not found: %s", CSV_PATH)
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        logging.exception("Error reading flows CSV: %s", e)
        return pd.DataFrame()

    return df


def main():
    # Ensure inference pipeline is present
    if not MODEL_PIPELINE_PATH.exists():
        logging.critical('❌ Inference pipeline absent: %s', MODEL_PIPELINE_PATH)
        sys.exit(1)

    pipe = joblib.load(MODEL_PIPELINE_PATH)
    logging.info('Inference pipeline loaded. Steps: %s', list(pipe.named_steps.keys()))
 
    while True:
        try:
            df = collect_flows()
            if df.empty:
                # time.sleep(interval_sec)
                continue

            for col in TOP_FEATURES:
                if col not in df.columns:
                    df[col] = 0.0

            X = df[TOP_FEATURES]

            probs = pipe.predict_proba(X)[:, 1]
            df['probability'] = probs

            sus = df[df['probability'] >= threshold]
            if sus.empty:
                logging.info('No suspicious flows detected.')
            else:
                count = len(sus)
                logging.warning('‼︎ %d suspicious flows detected', count)
                for _, row in sus.iterrows():
                    src = row.get('Source IP', 'unknown')
                    logging.warning('Suspicious %s → p=%.3f', src, row['probability'])

        except KeyboardInterrupt:
            logging.info('Interrupted by user, exiting.')
            break
        except Exception as exc:
            logging.exception('Error during monitoring loop: %s', exc)



if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    main()
