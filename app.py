import pandas as pd
from flask import Flask, request, jsonify
# from thefuzz import process
from rapidfuzz import process, fuzz

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

try:
    # IMPORTANT: Change 'StreetName' to the actual name of your column.
    streets_df = pd.read_csv('nz_streets.csv')
    
    # Get the list of street names from the DataFrame column.
    # We use .dropna() to remove any empty cells and .tolist() to convert it to a simple list.
    streets_df[f'{SUBURB_COLUMN}_lower'] = streets_df[SUBURB_COLUMN].str.lower()
    streets_df[f'{TOWN_COLUMN}_lower'] = streets_df[TOWN_COLUMN].str.lower()
    
    print(f"Successfully loaded {len(streets_df)} address records.")

except FileNotFoundError:
    print("Error: 'streets.csv' not found. Please make sure the file is in the same directory.")
    streets_df = None
except KeyError as e:
    print(f"Error: A required column was not found in 'nz_streets.csv': {e}")
    streets_df = None


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
    query = request.args.get('query')
    suburb = request.args.get('suburb')
    town = request.args.get('town')

    # Get the optional limit parameter, defaulting to 3 if not provided
    try:
        limit = int(request.args.get('limit', 3))
    except (ValueError, TypeError):
        limit = 3

    # --- Input Validation ---
    if not query:
        return jsonify({"error": "A 'query' parameter is required."}), 400

    # --- 4.  ---
    
    # Use thefuzz.process.extract to find the best matches for the query.
    # It takes the query, the list of choices, and returns a list of tuples:
    # [('match', score), ('another_match', score), ...]
    #results = process.extract(query, street_choices, limit=limit)
    search_area_df = streets_df

    # If suburb is provided, filter the DataFrame down to just that suburb
    if suburb:
        search_area_df = search_area_df[search_area_df[f'{SUBURB_COLUMN}_lower'] == suburb.lower()]
    
    # If town is provided, filter the DataFrame down to just that town
    if town:
        search_area_df = search_area_df[search_area_df[f'{TOWN_COLUMN}_lower'] == town.lower()]

    # Check if any addresses match the criteria
    if search_area_df.empty:
        return jsonify({
                        "error": "No streets found for the specified suburb/town.",
                        "query": {"street": query, "suburb": suburb, "town": town}
                        }), 404
    
    # Create the list of choices for the fuzzy search FROM THE FILTERED DATA.
    # Using .unique() is more efficient as it avoids searching the same street name multiple times.
    street_choices = search_area_df[STREET_COLUMN].unique().tolist()

    # --- 5. Fuzzy Search Logic ---
    top_matches = process.extract(
        query,
        street_choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=75 # Only include matches with a score of 75 or higher
    )

    # --- 6. Format the Response ---
    formatted_results = []
    for street_name, score, index in top_matches:
        # Find the first record matching the found street name within our filtered area.
        # This gives us access to the suburb, town, and full address.
        original_record = search_area_df[search_area_df[STREET_COLUMN] == street_name].iloc[0]

        formatted_results.append({
            "street": original_record[STREET_COLUMN],
            "suburb": original_record[SUBURB_COLUMN],
            "town": original_record[TOWN_COLUMN],
            "full_address": original_record[FULL_ADDRESS_COLUMN],
            "score": round(score, 2)
        })

    return jsonify(formatted_results)

# --- 6. Run the Application ---

if __name__ == '__main__':
    # The app.run() command starts the web server.
    # debug=True allows the server to automatically reload when you save changes.
    # Do not use debug=True in a production environment!
    app.run(host='0.0.0.0', port=5000, debug=True)
