import requests
import pandas as pd


def download_csv(url):
    """Download a CSV file and return as a pandas DataFrame."""
    if url:  # Check if the URL is not blank
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return pd.read_csv(pd.compat.StringIO(response.text))
    else:
        return pd.DataFrame()  # Return an empty DataFrame if URL is blank


def main():
    # URLs of the CSV files
    url1 = "https://app.matrixify.app/files/bookdelivered/a65fb920a71b995bac3aedbf7dd561c6/Vinly-ams-id-sku-price-quantity.csv?"
    url2 = ""

    # Download the CSV files
    df1 = download_csv(url1)
    df2 = download_csv(url2)

    # Optionally, process the dataframes (e.g., merge, clean)
    combined_df = pd.concat([df1, df2], ignore_index=True)

    # Write the new CSV file
    combined_df.to_csv("output.csv", index=False)
    print("New CSV file has been created with the combined data.")


if __name__ == "__main__":
    main()
