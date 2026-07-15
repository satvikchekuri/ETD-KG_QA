import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
import numpy as np

etd_csv = "processed_data_26k_etd_enriched.csv"
figures_csv = "etd_figures.csv"
tables_csv = "etd_tables.csv"
abstract_csv = "26k_etd_as_classified.csv"

abstract_df = pd.read_csv(abstract_csv)
total_rows = len(abstract_df)
print(f"Total rows: {total_rows}")

if "classified_label" in abstract_df.columns:
    label_counts = abstract_df["classified_label"].value_counts(dropna=False)
    print("Label distribution (counts):")
    print(label_counts)
    print("Label distribution (percentages):")
    print((label_counts / total_rows * 100).round(2))
else:
    print("Column 'label' not found.")