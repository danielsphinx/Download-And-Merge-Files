import pandas as pd


def append_matching_columns(input_file, target_file, output_file=None):
    """
    Standardize the columns of an input file to match a target file and append the data.

    Parameters:
    - input_file (str): Path to the input CSV file.
    - target_file (str): Path to the target CSV file.
    - output_file (str, optional): Path to save the updated target file. If not provided, overwrites the target_file.

    Returns:
    - None: Writes the updated data to the specified output file.
    """

    def standardize_columns(df, target_columns):
        """Ensure the columns of the DataFrame match the target columns."""
        return df.reindex(columns=target_columns, fill_value=None)

    # Read the input and target files
    df_input = pd.read_csv(input_file)
    df_target = pd.read_csv(target_file)

    # Standardize the input DataFrame to match the columns of the target DataFrame
    standardized_input = standardize_columns(df_input, df_target.columns)

    # Append the standardized input DataFrame to the target DataFrame
    combined_df = pd.concat([df_target, standardized_input], ignore_index=True)

    # Determine the output file path
    save_path = output_file if output_file else target_file

    # Save the updated DataFrame
    combined_df.to_csv(save_path, index=False)
    print(f"Data has been appended to {save_path} successfully.")


def run_append_AMS():
    append_matching_columns(
        input_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\ExportedOneRowOrderLine.csv",
        target_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\AMS\Completed Orders With Profit.csv"
    )


def run_append_Vast():
    append_matching_columns(
        input_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\ExportedOneRowOrderLine.csv",
        target_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\Vast\Completed Orders With Profit.csv"
    )

def run_append_both():
    # Example of calling the function
    append_matching_columns(
        input_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\AMS\Completed Orders With Profit.csv",
        target_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\All Orders Ordered With Profit\All Orders Ordered With Profit.csv"
    )

    # Example of calling the function
    append_matching_columns(
        input_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\Vast\Completed Orders With Profit.csv",
        target_file=r"G:\Automation Google Drive\Order Exports\Completed Orders\All Orders Ordered With Profit\All Orders Ordered With Profit.csv"
    )
run_append_AMS()
