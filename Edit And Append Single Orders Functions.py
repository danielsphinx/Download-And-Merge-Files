import pandas as pd
from datetime import datetime

# ==========================================
# SAFE CSV READER
# Tries common encodings used by Excel / messy CSVs
# ==========================================
def read_csv_safe(path):
    for enc in ("utf-8-sig", "cp1252", "latin1"):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, engine="python", on_bad_lines="warn").fillna("")
            print(f"Loaded with {enc}: {path}")
            return df
        except Exception as e:
            print(f"Failed with {enc}: {path} -> {e}")
    raise ValueError(f"Could not read file: {path}")

# ==========================================
# WRITE LOGS
# - last_log: overwritten every run
# - history_log: appended forever
# ==========================================
def write_logs(last_log, history_log, text):
    with open(last_log, "w", encoding="utf-8-sig") as f:
        f.write(text)
    with open(history_log, "a", encoding="utf-8-sig") as f:
        f.write(text + "\n" + "=" * 100 + "\n\n")

# ==========================================
# MAIN APPEND FUNCTION
# - matches input columns to target
# - prevents duplicate appends
# - logs clearly what was added / skipped
# ==========================================
def append_matching_columns(
    input_file,
    target_file,
    output_file=None,
    key_cols=("Order ID", "Buyer"),
    last_log=None,
    history_log=None,
    max_duplicate_examples=25
):
    # Read both files
    df_input = read_csv_safe(input_file)
    df_target = read_csv_safe(target_file)

    original_input_rows = len(df_input)
    original_target_rows = len(df_target)

    # Force input schema to match target schema
    df_input = df_input.reindex(columns=df_target.columns, fill_value="")

    # Make sure dedupe columns exist in both files
    missing = [c for c in key_cols if c not in df_input.columns or c not in df_target.columns]
    if missing:
        raise ValueError(f"Missing key columns: {missing}")

    # Build normalized dedupe keys
    df_input["_key"] = df_input[list(key_cols)].astype(str).agg(" | ".join, axis=1).str.strip().str.lower()
    df_target["_key"] = df_target[list(key_cols)].astype(str).agg(" | ".join, axis=1).str.strip().str.lower()

    # Remove duplicates already repeated inside input
    before_input = len(df_input)
    df_input = df_input.drop_duplicates("_key", keep="first")
    input_dups_removed = before_input - len(df_input)

    # Remove duplicates already repeated inside target
    before_target = len(df_target)
    df_target = df_target.drop_duplicates("_key", keep="first")
    target_dups_removed = before_target - len(df_target)

    # Identify incoming rows that already exist in target
    existing_keys = set(df_target["_key"])
    skipped_dupe_rows = df_input[df_input["_key"].isin(existing_keys)].copy()
    new_rows = df_input[~df_input["_key"].isin(existing_keys)].copy()

    skipped_existing = len(skipped_dupe_rows)
    added_rows = len(new_rows)

    # Append only truly new rows
    combined = pd.concat([df_target, new_rows], ignore_index=True).drop(columns="_key", errors="ignore")

    # Save cleaned / updated file
    save_path = output_file or target_file
    combined.to_csv(save_path, index=False, encoding="utf-8-sig")
    total_rows = len(combined)

    # Console output
    print(f"Added {added_rows} new rows -> {save_path}")
    print(f"Skipped {skipped_existing} NEW incoming rows because they already existed in target")
    print(f"Removed {input_dups_removed} duplicate rows inside input")
    print(f"Removed {target_dups_removed} duplicate rows inside target")
    print(f"Total rows now: {total_rows}")

    # Example skipped keys for clear logging
    duplicate_examples = (
        skipped_dupe_rows[list(key_cols)]
        .astype(str)
        .agg(" | ".join, axis=1)
        .head(max_duplicate_examples)
        .tolist()
    )
    duplicate_examples_text = "\n".join(f"- {x}" for x in duplicate_examples) if duplicate_examples else "None"
    more_note = f"\n...and {skipped_existing - max_duplicate_examples} more not shown." if skipped_existing > max_duplicate_examples else ""

    # Build log text
    log_text = (
        f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"Input File: {input_file}\n"
        f"Target File: {target_file}\n"
        f"Saved File: {save_path}\n"
        f"Key Columns: {', '.join(key_cols)}\n\n"
        f"INPUT ROWS BEFORE CLEANING: {original_input_rows}\n"
        f"DUPLICATE ROWS REMOVED INSIDE INPUT FILE: {input_dups_removed}\n\n"
        f"TARGET ROWS BEFORE CLEANING: {original_target_rows}\n"
        f"DUPLICATE ROWS REMOVED INSIDE TARGET FILE: {target_dups_removed}\n\n"
        f"NEW ROWS SUCCESSFULLY ADDED: {added_rows}\n"
        f"WARNING: NEW INCOMING ROWS NOT ADDED BECAUSE THEY WERE DUPLICATES OF EXISTING TARGET ROWS: {skipped_existing}\n"
        f"FINAL TOTAL ROWS IN SAVED FILE: {total_rows}\n\n"
        f"DUPLICATE INCOMING ROW EXAMPLES (matched existing target rows):\n"
        f"{duplicate_examples_text}{more_note}\n"
    )

    # Write logs if paths provided
    if last_log and history_log:
        write_logs(last_log, history_log, log_text)

# ==========================================
# PATHS
# ==========================================
BASE = r"G:\Automation Google Drive\Order Exports\Completed Orders"
INPUT = rf"{BASE}\ExportedOneRowOrderLine.csv"
LAST_LOG = rf"{BASE}\last_append.txt"
HISTORY_LOG = rf"{BASE}\append_history.txt"

# ==========================================
# RUN FUNCTIONS
# Keep same structure as your old script
# IMPORTANT:
# Change key_cols if your real unique row should use
# something like ("Order ID", "SKU") or ("Name", "Lineitem sku")
# ==========================================
def run_append_AMS():
    append_matching_columns(
        input_file=INPUT,
        target_file=rf"{BASE}\AMS\Completed Orders With Profit.csv",
        key_cols=("Order ID", "Buyer"),
        last_log=LAST_LOG,
        history_log=HISTORY_LOG
    )

def run_append_Vast():
    append_matching_columns(
        input_file=INPUT,
        target_file=rf"{BASE}\Vast\Completed Orders With Profit.csv",
        key_cols=("Order ID", "Buyer"),
        last_log=LAST_LOG,
        history_log=HISTORY_LOG
    )

def run_append_both():
    append_matching_columns(
        input_file=rf"{BASE}\AMS\Completed Orders With Profit.csv",
        target_file=rf"{BASE}\All Orders Ordered With Profit\All Orders Ordered With Profit.csv",
        key_cols=("Order ID", "Buyer"),
        last_log=LAST_LOG,
        history_log=HISTORY_LOG
    )
    append_matching_columns(
        input_file=rf"{BASE}\Vast\Completed Orders With Profit.csv",
        target_file=rf"{BASE}\All Orders Ordered With Profit\All Orders Ordered With Profit.csv",
        key_cols=("Order ID", "Buyer"),
        last_log=LAST_LOG,
        history_log=HISTORY_LOG
    )

# ==========================================
# ENTRYPOINT
# Uncomment what you want to run
# ==========================================
run_append_AMS()
# run_append_Vast()
# run_append_both()