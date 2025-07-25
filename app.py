import pandas as pd
from flask import Flask, request, jsonify
from rapidfuzz import process, fuzz
import requests
import io

import requests.exceptions
# --- 1. Initialization ---

# Create the Flask application instance
app = Flask(__name__)

# --- 2. Data Loading ---

# Load the CSV data into a pandas DataFrame right when the app starts.
# This is efficient because it's only done once, not on every request.
STREET_COLUMN = 'street'
SUBURB_COLUMN = 'suburb'
TOWN_COLUMN = 'town'
FULL_ADDRESS_COLUMN = 'full_address'

SUBURB_COLUMN_LOWER = f'{SUBURB_COLUMN}_lower'
TOWN_COLUMN_LOWER = f'{TOWN_COLUMN}_lower'


streets_df = None
unique_location_choices = []


def get_google_drive_file_id(url):
    """ Extracts the file ID from a Google Drive shareable link"""
    try:
        return url.split('/d/')[1].split('/')[0]
    except IndexError:
        print("Error: Invalid Google Drive URL Format.")
        return None
    
def load_data_from_google_drive():
    """ Loads the CSV data from a Google Drive link. """
    gdrive_shareable_link = "https://drive.google.com/file/d/1xIT98i_O_M6dBZH77PrKsCQRfLM5fRVR/view?usp=sharing"

    file_id = get_google_drive_file_id(gdrive_shareable_link)
    #file_id = "1xIT98i_O_M6dBZH77PrKsCQRfLM5fRVR"
    if not file_id: return None, []
    
    download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
    print(f"Attempting to download the data from Google Drive...")

    try:
        response = requests.get(download_url)
        response.raise_for_status()
        csv_data = io.StringIO(response.text)
        df = pd.read_csv(csv_data)

        df[SUBURB_COLUMN_LOWER] = df[SUBURB_COLUMN].str.lower().fillna('')
        df[TOWN_COLUMN_LOWER] = df[TOWN_COLUMN].str.lower().fillna('')

        unique_suburbs = set(df[SUBURB_COLUMN_LOWER].unique())
        unique_towns = set(df[TOWN_COLUMN_LOWER].unique())

        combined_locations = list(unique_suburbs.union(unique_towns) - {''})

        print(f"Successfully loaded {len(df)} address records.")
        print(f"Created a combined search list with {len(combined_locations)} unique locations for searching.")

        return df, combined_locations

    except requests.exceptions.RequestException as e:
        print(f"Error downloading the file from Google Drive: {e}")
        return None, []
    except KeyError as e:
        print(f"Error: A required column was not found in the csv: {e}")
        return None, []
    except Exception as e:
        print(f"An unexpected error occured during data loading {e}")
        return None, []

streets_df, unique_location_choices = load_data_from_google_drive()

# --- 3. API Endpoint Definition ---

@app.route('/search', methods=['GET'])
def search_street():
    """
    Performs a fuzzy search for a street name, optionally with suburb and/or town.

    Query Parameters:
     - query (required): The street name to search for.
     - suburb (optional): The suburb to limit the search to.
     - town (optional): The town to limit the search to.
     - limit (optional): The number of results to return.
    """
    # --- Input Validation and Pre-processing ---
    if streets_df is None:
        return jsonify({"error": "Address data is not loaded. Check server logs."}), 500

    # Get the search query from the URL parameters (e.g., /search?query=Main St)
    query_address = request.args.get('query')
    query_location = request.args.get('location')

    # Get the optional limit parameter, defaulting to 3 if not provided
    try:
        limit = int(request.args.get('limit', 3))
    except (ValueError, TypeError):
        limit = 3

    # --- Input Validation ---
    if not query_address or not query_location:
        return jsonify({"error": "Both 'query' (street) and 'location' parameters are required."}), 400

    # --- 4.  ---
    
    # Use thefuzz.process.extract to find the best matches for the query.
    # It takes the query, the list of choices, and returns a list of tuples:
    # [('match', score), ('another_match', score), ...]
    #results = process.extract(query, street_choices, limit=limit)
    best_location_match = process.extractOne(
        query_location.lower(),
        unique_location_choices
    )
    
    if not best_location_match:
        return jsonify({
            "error": "Could not find a confident location match.",
            "suburb_query": query_suburb
        }), 404
    
    matched_location_name, location_score, _ = best_location_match
    search_area_df = streets_df[
        (streets_df[SUBURB_COLUMN_LOWER] == matched_location_name) |
        (streets_df[TOWN_COLUMN_LOWER] == matched_location_name)
    ]
    
    if search_area_df.empty:
        return jsonify({"error": "No addresses found for the matched location.", "location_match": matched_location_name}), 404
    
    address_choices = search_area_df[FULL_ADDRESS_COLUMN].unique().tolist()
    top_address_matches = process.extract(
        query_address,
        address_choices,
        limit=limit
    )

    response_data = {
        "suburb_match": {
            "input": "query_location",
            "matched_to": matched_location_name.title(),
            "score": round(location_score, 2)
        },
        "address_results": []
    }

    for matched_address, score, index in top_address_matches:
        # Find the first record matching the found street name within our filtered area.
        # This gives us access to the suburb, town, and full address.
        original_record = search_area_df[search_area_df[FULL_ADDRESS_COLUMN] == matched_address].iloc[0]

        response_data["address_results"].append({
            "street": original_record[STREET_COLUMN],
            "suburb": original_record[SUBURB_COLUMN],
            "town": original_record[TOWN_COLUMN],
            "full_address": original_record[FULL_ADDRESS_COLUMN],
            "score": round(score, 2)
        })

    return jsonify(response_data)


    # # If suburb is provided, filter the DataFrame down to just that suburb
    # if suburb:
    #     search_area_df = search_area_df[search_area_df[f'{SUBURB_COLUMN}_lower'] == suburb.lower()]
    
    # # If town is provided, filter the DataFrame down to just that town
    # if town:
    #     search_area_df = search_area_df[search_area_df[f'{TOWN_COLUMN}_lower'] == town.lower()]

    # # Check if any addresses match the criteria
    # if search_area_df.empty:
    #     return jsonify({
    #                     "error": "No streets found for the specified suburb/town.",
    #                     "query": {"street": query, "suburb": suburb, "town": town}
    #                     }), 404
    
    # # Create the list of choices for the fuzzy search FROM THE FILTERED DATA.
    # # Using .unique() is more efficient as it avoids searching the same street name multiple times.
    # street_choices = search_area_df[STREET_COLUMN].unique().tolist()

    # # --- 5. Fuzzy Search Logic ---
    

    # # --- 6. Format the Response ---
    # formatted_results = []
    

# --- 6. Run the Application ---

if __name__ == '__main__':
    # The app.run() command starts the web server.
    # debug=True allows the server to automatically reload when you save changes.
    # Do not use debug=True in a production environment!
    app.run(host='0.0.0.0', port=5000, debug=True)
