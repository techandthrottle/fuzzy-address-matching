import pandas as pd
from flask import Flask, request, jsonify
from thefuzz import process

# --- 1. Initialization ---

# Create the Flask application instance
app = Flask(__name__)

# --- 2. Data Loading ---

# Load the CSV data into a pandas DataFrame right when the app starts.
# This is efficient because it's only done once, not on every request.
try:
    # IMPORTANT: Change 'StreetName' to the actual name of your column.
    STREET_NAME_COLUMN = 'street_name' 
    
    streets_df = pd.read_csv('woburn_street_names.csv')
    
    # Get the list of street names from the DataFrame column.
    # We use .dropna() to remove any empty cells and .tolist() to convert it to a simple list.
    street_choices = streets_df[STREET_NAME_COLUMN].dropna().tolist()
    
    print(f"Successfully loaded {len(street_choices)} street names.")

except FileNotFoundError:
    print("Error: 'streets.csv' not found. Please make sure the file is in the same directory.")
    street_choices = []
except KeyError:
    print(f"Error: Column '{STREET_NAME_COLUMN}' not found in 'streets.csv'. Please check the column name.")
    street_choices = []


# --- 3. API Endpoint Definition ---

@app.route('/search', methods=['GET'])
def search_street():
    """
    Performs a fuzzy search for a street name.
    Accepts a 'query' parameter for the street name to search for.
    Accepts an optional 'limit' parameter for the number of results to return.
    """
    # Get the search query from the URL parameters (e.g., /search?query=Main St)
    query = request.args.get('query')
    
    # Get the optional limit parameter, defaulting to 3 if not provided
    try:
        limit = int(request.args.get('limit', 3))
    except (ValueError, TypeError):
        limit = 3

    # --- Input Validation ---
    if not query:
        return jsonify({"error": "A 'query' parameter is required."}), 400

    if not street_choices:
        return jsonify({"error": "Street name data is not loaded. Check server logs."}), 500

    # --- 4. Fuzzy Search Logic ---
    
    # Use thefuzz.process.extract to find the best matches for the query.
    # It takes the query, the list of choices, and returns a list of tuples:
    # [('match', score), ('another_match', score), ...]
    results = process.extract(query, street_choices, limit=limit)

    # --- 5. Format the Response ---
    
    # Convert the list of tuples into a more friendly list of dictionaries
    formatted_results = [
        {"match": result[0], "score": result[1]} for result in results
    ]

    return jsonify(formatted_results)

# --- 6. Run the Application ---

if __name__ == '__main__':
    # The app.run() command starts the web server.
    # debug=True allows the server to automatically reload when you save changes.
    # Do not use debug=True in a production environment!
    app.run(host='0.0.0.0', port=5000, debug=True)
