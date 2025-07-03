# Street Name Fuzzy Search API

A simple Flask API that provides fuzzy search capabilities for street names based on a master CSV file.

Uses RapidFuzz and JellyFish

## How to Run

1.  Clone the repository.
2.  Install the dependencies:
    `pip install -r requirements.txt`
3.  Run the Flask application:
    `python app.py`

## API Endpoint

### `GET /search`
Performs a fuzzy search for a street name.

**Query Parameters:**
- `query` (string, required): The street name to search for.
- `limit` (integer, optional): The number of top matches to return. Defaults to 3.

**Example Request:**
`curl "http://127.0.0.1:5000/search?query=Main%20Stret"`

**Example Response:**
```json
[
  {
    "match": "Main Street",
    "score": 95
  }
]