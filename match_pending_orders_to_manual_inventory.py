import pandas as pd
import re
import warnings

# Example: Use case-specific header configurations
shopify_required_headers = [
    "Sales Channel", "Order Number", "Date", "Buyer", "Price", "Tax",
    "Tax Remitted", "Shipping", "Shipping Type", "Products", "Quantity",
    "Retail ID", "Street 1", "Street 2", "City", "State", "ZIP Code",
    "Merchant Order Reference", "Order Status", "Invoice origin",
    "Receiver ID", "Country", "Bundle SKUs",
    "Full Items Cost Without Base Shipping For Profit Calculation",
    "Estimated Profit", "Order Earnings", "Order SKU",
    "Buyer Requested Cancel", "Is Replacement Order", "Full Order ID"
]

marketplace_required_headers = [
    "Sales Channel", "Order ID", "Date", "Buyer", "Price", "Tax",
    "Tax Remitted", "Shipping", "Shipping Type", "Products", "Quantity",
    "Retail ID", "Street 1", "Street 2", "City", "State", "ZIP Code",
    "Merchant Order Reference", "Order Status", "Invoice origin",
    "Receiver ID", "Country", "Bundle SKUs",
    "Full Items Cost Without Base Shipping For Profit Calculation",
    "Estimated Profit", "Order Earnings", "Order SKU",
    "Buyer Requested Cancel", "Is Replacement Order", "Full Order ID"
]

def process_orders(input_file, output_file, required_headers):
    """
    Ensure all required headers exist, reorder columns, and save as UTF-8. Only updates columns, never rows.
    """
    df = pd.read_csv(input_file, dtype=str)

    for header in required_headers:
        if header not in df.columns:
            df[header] = None
    df = df[required_headers]
    df.to_csv(output_file, index=False, encoding='utf-8')

def order_inventory_match(order_file, barcode_file, required_headers, output_file=None):
    """
    Matches barcodes in an order file (from Retail ID or Bundle SKUs) to a barcode/quantity file.
    Groups by order number/id to compute one "In Hand" summary per order.
    BUT: Output rows are the original order rows (no row merging), just with
    "In Hand Data" and "In Hand" appended.
    """

    # -----------------------------
    # 1. Load orders
    # -----------------------------
    orders = pd.read_csv(order_file, dtype=str)
    print("Loaded orders:", len(orders))
    print("Columns in orders:", orders.columns)

    if 'Bundle SKUs' in orders.columns:
        print("Sample Bundle SKUs:", orders['Bundle SKUs'].dropna().unique()[:5])
    if 'Retail ID' in orders.columns:
        print("Sample Retail IDs:", orders['Retail ID'].dropna().unique()[:5])

    if orders.empty or orders.shape[0] == 0:
        print("⚠️ No orders found in the file. Skipping matching.")
        # Still ensure headers + empty In Hand cols and write out
        final_result = orders.copy()
        if 'In Hand Data' not in final_result.columns:
            final_result['In Hand Data'] = ''
        if 'In Hand' not in final_result.columns:
            final_result['In Hand'] = ''

        for header in required_headers:
            if header not in final_result.columns:
                final_result[header] = ''

        output_columns = required_headers + ["In Hand Data", "In Hand"]
        if not output_file:
            output_file = order_file.rsplit('.', 1)[0] + '_matched_simple.csv'
        final_result[output_columns].to_csv(output_file, index=False, encoding='utf-8')
        print(f"Saved (empty orders): {output_file}")
        return final_result

    # Determine the order-id column once, from the original orders
    if "Order ID" in orders.columns:
        order_id_column = "Order ID"
    elif "Order Number" in orders.columns:
        order_id_column = "Order Number"
    else:
        raise Exception("No suitable order number column found in orders!")

    # -----------------------------
    # 2. Load inventory barcode/qty
    # -----------------------------
    barcode_qty = pd.read_csv(barcode_file, dtype=str)
    barcode_qty.columns = [c.strip() for c in barcode_qty.columns]

    barcode_col = next((c for c in barcode_qty.columns if "barcode" in c.lower()), "Barcode")
    qty_col = next((c for c in barcode_qty.columns
                    if "qty" in c.lower() or "quantity" in c.lower()), "Quantity")

    print("barcode_qty columns:", barcode_qty.columns)

    barcode_qty[barcode_col] = (
        barcode_qty[barcode_col]
        .astype(str)
        .str.strip()
        .str.lstrip('0')
    )

    barcode_qty = barcode_qty.rename(columns={qty_col: 'Inventory Quantity'})
    barcode_qty['Inventory Quantity'] = pd.to_numeric(
        barcode_qty['Inventory Quantity'], errors='coerce'
    ).fillna(0)

    # -----------------------------
    # 3. Extract barcodes per row
    # -----------------------------
    def extract_barcodes_and_qty(row):
        quantity = int(row.get('Quantity', 1)) if str(row.get('Quantity', '')).isdigit() else 1
        barcodes = []

        bundle_skus = row.get('Bundle SKUs', '')
        retail_id = row.get('Retail ID', '')

        if pd.notna(bundle_skus) and str(bundle_skus).strip() != "":
            for code in str(bundle_skus).split(','):
                code = code.strip().rstrip(',')
                match = re.search(r'(\d{8,})', code)
                if match:
                    barcodes.append((match.group(1).lstrip('0'), quantity))
        elif pd.notna(retail_id) and str(retail_id).strip() != "":
            code = str(retail_id).strip()
            match = re.search(r'(\d{8,})', code)
            if match:
                barcodes.append((match.group(1).lstrip('0'), quantity))

        return barcodes

    # Build a per-line expanded table: one row per (order, barcode)
    records = []
    for idx, row in orders.iterrows():
        barcodes_and_qty = extract_barcodes_and_qty(row)
        if barcodes_and_qty:
            for bc, qty in barcodes_and_qty:
                records.append({
                    order_id_column: row.get(order_id_column, ''),
                    'Matched Barcode': bc,
                    'Order Quantity': qty
                })

    if not records:
        # No barcodes in any row → just attach empty In Hand fields and bail
        print("No barcodes found in any order line. Writing file with blank In Hand columns.")
        final_result = orders.copy()
        final_result['In Hand Data'] = ''
        final_result['In Hand'] = ''
        for header in required_headers:
            if header not in final_result.columns:
                final_result[header] = ''

        output_columns = required_headers + ["In Hand Data", "In Hand"]
        if not output_file:
            output_file = order_file.rsplit('.', 1)[0] + '_matched_simple.csv'
        final_result[output_columns].to_csv(output_file, index=False, encoding='utf-8')
        print(f"Saved (no barcodes): {output_file}")
        return final_result

    matched_orders = pd.DataFrame(records)
    print("matched_orders (expanded) rows:", len(matched_orders))
    print("matched_orders columns:", matched_orders.columns)

    # -----------------------------
    # 4. Collapse duplicate barcodes per order (for summary ONLY)
    # -----------------------------
    barcode_level = matched_orders.copy()
    barcode_level['Order Quantity'] = pd.to_numeric(
        barcode_level['Order Quantity'], errors='coerce'
    ).fillna(0)

    # group by (Order, Barcode) and sum Order Quantity
    grouped = (
        barcode_level
        .groupby([order_id_column, 'Matched Barcode'], dropna=False)['Order Quantity']
        .sum()
        .reset_index()
    )

    # -----------------------------
    # 5. Merge with inventory for per-barcode "have" quantity
    # -----------------------------
    result = grouped.merge(
        barcode_qty[[barcode_col, 'Inventory Quantity']],
        left_on='Matched Barcode',
        right_on=barcode_col,
        how='left'
    )

    result['Inventory Quantity'] = pd.to_numeric(
        result['Inventory Quantity'], errors='coerce'
    ).fillna(0)

    # -----------------------------
    # 6. Order-level "In Hand" summary
    # -----------------------------
    def summarize_in_hand(group):
        oos = []
        in_hand = []
        partial = []

        for _, row in group.iterrows():
            sku = str(row['Matched Barcode'])
            if not sku or sku == 'nan':
                continue  # skip if no usable barcode

            need = row['Order Quantity']
            have = row['Inventory Quantity']

            try:
                need = int(need)
            except Exception:
                need = 0
            try:
                have = int(have)
            except Exception:
                have = 0

            if have >= need and need > 0:
                in_hand.append(f"{sku}({need})")
            elif have > 0 and need > 0 and have < need:
                partial.append(f"{sku}({have} in hand, {need} need)")
            elif need > 0:
                oos.append(f"{sku}({need} need, {have} in hand)")

        # ---- same logic you had before ----
        if (oos or partial) and in_hand:
            partial_summary = []
            if partial:
                partial_summary.append("Partial: " + ", ".join(partial))
            if oos:
                partial_summary.append("OOS: " + ", ".join(oos))
            if in_hand:
                partial_summary.append("In Hand: " + ", ".join(in_hand))
            in_hand_data = " | ".join(partial_summary)
            in_hand_flag = "Partial"
        elif not oos and not partial and in_hand:
            in_hand_data = "Fully In Hand"
            in_hand_flag = True
        elif not in_hand and not partial and oos:
            in_hand_data = "OOS: " + ", ".join(oos)
            in_hand_flag = False
        elif partial:
            in_hand_data = "Partial: " + ", ".join(partial)
            in_hand_flag = "Partial"
        elif not in_hand and not partial and not oos:
            in_hand_data = ""
            in_hand_flag = ""
        else:
            # fallback
            parts = []
            if partial:
                parts.append("Partial: " + ", ".join(partial))
            if oos:
                parts.append("OOS: " + ", ".join(oos))
            if in_hand:
                parts.append("In Hand: " + ", ".join(in_hand))
            in_hand_data = " | ".join(parts)
            in_hand_flag = False

        return pd.Series({'In Hand Data': in_hand_data, 'In Hand': in_hand_flag})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        result_with_inhand = (
            result
            .groupby(order_id_column, dropna=False)
            .apply(summarize_in_hand)
            .reset_index()
        )

    # -----------------------------
    # 7. Merge summary back into original orders
    # -----------------------------
    final_result = orders.merge(result_with_inhand, on=order_id_column, how='left')

    # Fill NaNs in In Hand fields with blanks
    if 'In Hand Data' not in final_result.columns:
        final_result['In Hand Data'] = ''
    else:
        final_result['In Hand Data'] = final_result['In Hand Data'].fillna('')
    if 'In Hand' not in final_result.columns:
        final_result['In Hand'] = ''
    else:
        final_result['In Hand'] = final_result['In Hand'].fillna('')

    # Ensure all required headers exist
    for header in required_headers:
        if header not in final_result.columns:
            final_result[header] = ''

    # -----------------------------
    # 8. Output only required columns + In Hand
    # -----------------------------
    output_columns = required_headers + ["In Hand Data", "In Hand"]

    # IMPORTANT: no drop_duplicates() here – we want a 1:1 with original rows
    filtered_result = final_result[output_columns]

    if not output_file:
        output_file = order_file.rsplit('.', 1)[0] + '_matched_simple.csv'

    filtered_result.to_csv(output_file, index=False, encoding='utf-8')
    print(f"Saved: {output_file}")

    return filtered_result

# ----------- Main logic for both file types ---------------

order_inventory_match(
    "G:\\Automation Google Drive\\Order Exports\\Python Shopify Store Orders\\All Shopify Stores\\Merged Shopify Format Orders.csv",
    "G:\\Automation Google Drive\\Wholesale UI CSVs\\Manual-ish Feed\\Barcode Scanner\\Google Sheet Inventory\\Inventory Barcode Scanner Sheet Pull.csv",
    shopify_required_headers
)

order_inventory_match(
    "G:\\Automation Google Drive\\Google Sheet Connected CSVs\\Pending Order Exports\\All Marketplaces\\All Pending Marketplace Orders For Ordering.csv",
    "G:\\Automation Google Drive\\Wholesale UI CSVs\\Manual-ish Feed\\Barcode Scanner\\Google Sheet Inventory\\Inventory Barcode Scanner Sheet Pull.csv",
    marketplace_required_headers
)
process_orders(
    "G:\\Automation Google Drive\\Order Exports\\Python Shopify Store Orders\\All Shopify Stores\\Merged Shopify Format Orders.csv",
    "G:\\Automation Google Drive\\Order Exports\\Python Shopify Store Orders\\All Shopify Stores\\Merged Shopify Format Orders.csv",
    shopify_required_headers
)

process_orders(
    "G:\\Automation Google Drive\\Google Sheet Connected CSVs\\Pending Order Exports\\All Marketplaces\\All Pending Marketplace Orders For Ordering.csv",
    "G:\\Automation Google Drive\\Google Sheet Connected CSVs\\Pending Order Exports\\All Marketplaces\\All Pending Marketplace Orders For Ordering.csv",
    marketplace_required_headers
)