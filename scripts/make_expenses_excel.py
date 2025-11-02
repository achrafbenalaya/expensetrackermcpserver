import sys
import pandas as pd

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "expenses.sample.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "expenses.xlsx"
    df = pd.read_csv(src)
    df.to_excel(dst, index=False, engine="openpyxl")
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
