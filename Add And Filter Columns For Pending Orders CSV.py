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
    Groups by order number/id and outputs one In Hand summary for the entire order.
    Keeps all original rows, including those with no barcode.
    Only outputs the _matched_simple.csv file.
    """
    orders = pd.read_csv(order_file, dtype=str)
    barcode_qty = pd.read_csv(barcode_file, dtype=str)

    barcode_qty.columns = [c.strip() for c in barcode_qty.columns]
    barcode_col = next((c for c in barcode_qty.columns if "barcode" in c.lower()), "Barcode")
    qty_col = next((c for c in barcode_qty.columns if "qty" in c.lower() or "quantity" in c.lower()), "Quantity")

    barcode_qty[barcode_col] = barcode_qty[barcode_col].astype(str).str.strip().str.lstrip('0')
    barcode_qty = barcode_qty.rename(columns={qty_col: 'Inventory Quantity'})
    barcode_qty['Inventory Quantity'] = pd.to_numeric(barcode_qty['Inventory Quantity'], errors='coerce').fillna(0)

    def extract_barcodes_and_qty(row):
        quantity = int(row.get('Quantity', 1)) if str(row.get('Quantity', '')).isdigit() else 1
        barcodes = []
        if pd.notna(row.get('Bundle SKUs', '')) and row['Bundle SKUs'].strip() != "":
            for code in row['Bundle SKUs'].split(','):
                code = code.strip().rstrip(',')
                match = re.search(r'(\d{8,})', code)
                if match:
                    barcodes.append((match.group(1).lstrip('0'), quantity))
        elif pd.notna(row.get('Retail ID', '')) and row['Retail ID'].strip() != "":
            code = row['Retail ID'].strip()
            match = re.search(r'(\d{8,})', code)
            if match:
                barcodes.append((match.group(1).lstrip('0'), quantity))
        return barcodes

    order_columns_list = list(orders.columns)
    records = []

    for idx, row in orders.iterrows():
        barcodes_and_qty = extract_barcodes_and_qty(row)
        if barcodes_and_qty:
            for bc, qty in barcodes_and_qty:
                record = {col: row.get(col, '') for col in order_columns_list}
                record['Matched Barcode'] = bc
                record['Order Quantity'] = qty
                records.append(record)
        else:
            # Add the row with empty barcode/quantity info if no barcode found
            record = {col: row.get(col, '') for col in order_columns_list}
            record['Matched Barcode'] = ''
            record['Order Quantity'] = ''
            records.append(record)

    matched_orders = pd.DataFrame(records)

    # Merge inventory data (for empty barcodes, result will be NaN)
    result = matched_orders.merge(
        barcode_qty[[barcode_col, 'Inventory Quantity']],
        left_on='Matched Barcode',
        right_on=barcode_col,
        how='left'
    )

    # Fill Inventory Quantity only where there's a barcode; else leave as blank
    def fill_inventory_qty(row):
        if pd.isna(row['Matched Barcode']) or row['Matched Barcode'] == '':
            return ''
        return int(row['Inventory Quantity']) if pd.notna(row['Inventory Quantity']) else 0
    result['Inventory Quantity'] = result.apply(fill_inventory_qty, axis=1)
    # Same for Order Quantity (make blank if missing)
    result['Order Quantity'] = result['Order Quantity'].apply(lambda x: x if x != '' else '')

    # Use order-level column for grouping
    if "Order ID" in matched_orders.columns:
        order_id_column = "Order ID"
    elif "Order Number" in matched_orders.columns:
        order_id_column = "Order Number"
    else:
        raise Exception("No suitable order number column found!")

    def summarize_in_hand(group):
        oos = []
        in_hand = []
        partial = []
        for _, row in group.iterrows():
            sku = row['Matched Barcode']
            if not sku:
                continue  # skip rows with no barcode for summary
            need = row['Order Quantity']
            have = row['Inventory Quantity']
            try:
                need = int(need)
            except:
                need = 0
            try:
                have = int(have)
            except:
                have = 0
            if have >= need and need > 0:
                in_hand.append(f"{sku}({need})")
            elif have > 0 and need > 0 and have < need:
                partial.append(f"{sku}({have} in hand, {need} need)")
            elif need > 0:
                oos.append(f"{sku}({need} need, {have} in hand)")
        # --- NEW LOGIC ---
        if (oos or partial) and in_hand:
            # If there is any OOS or partial, but also some in hand, call the whole thing Partial
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
            # fallback, should never hit
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
        result_with_inhand = result.groupby(order_id_column, dropna=False).apply(summarize_in_hand).reset_index()

    final_result = pd.merge(result, result_with_inhand, on=order_id_column, how='left')

    # Output only the required columns (if present) + In Hand Data + In Hand
    all_order_columns = [col for col in required_headers if col in final_result.columns]
    output_columns = all_order_columns + ["In Hand Data", "In Hand"]
    filtered_result = final_result[output_columns].drop_duplicates()

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
