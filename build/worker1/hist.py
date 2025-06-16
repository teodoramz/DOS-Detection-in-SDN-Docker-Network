#!/usr/bin/env python3


from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import sys

CSV_IN   = Path("allpred.csv")
CSV_OUT  = Path("hist_counts.csv") 
IMG_OUT  = Path("prob_hist.png")
COL_NAME = "probability"

def main() -> None:
    if not CSV_IN.exists():
        sys.exit(f"File not found: {CSV_IN}")

    df = pd.read_csv(CSV_IN, usecols=[COL_NAME])

    counts = df.value_counts(COL_NAME).sort_index()
    counts.index.name = COL_NAME
    counts.name       = "count"


    counts.to_csv(CSV_OUT, header=True)
    print(f"Saved counts  →  {CSV_OUT}")


    plt.figure(figsize=(8,4))
    counts.plot(kind="bar")
    plt.title("Number of flows per prediction score")
    plt.ylabel("Requests")
    plt.xlabel("Prediction probability")
    plt.tight_layout()
    plt.savefig(IMG_OUT, dpi=150)
    plt.close()
    print(f"Saved histogram → {IMG_OUT}")

if __name__ == "__main__":
    main()
