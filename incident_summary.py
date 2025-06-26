import os
import time
import requests
import json  # Make sure json is imported
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_API_PATH = "/api/1775050/gemini_integration/incidents/high_priority"
SNOW_USERNAME = os.getenv("SNOW_USERNAME")
SNOW_PASSWORD = os.getenv("SNOW_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- CONTROL VARIABLES ---
GEMINI_MODEL = "gemini-1.5-flash"

# --- FUNCTION DEFINITIONS ---

def check_configuration():
    """Checks if all required environment variables are properly set."""
    if not all([SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD, GEMINI_API_KEY]):
        print("CRITICAL ERROR: Environment variables not set.")
        print("Please check your .env file or set the variables manually.")
        return False
    return True

def get_high_priority_incidents():
    """Fetches and correctly parses high-priority incidents from ServiceNow."""
    print("Fetching all high-priority incidents from ServiceNow...")
    url = f"{SNOW_INSTANCE}{SNOW_API_PATH}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, auth=(SNOW_USERNAME, SNOW_PASSWORD), headers=headers, timeout=15)
        response.raise_for_status()

        # Debug: Print the full response to see what we're getting
        full_response = response.json()
        print(f"DEBUG: Full response type: {type(full_response)}")
        print(f"DEBUG: Full response keys: {full_response.keys() if isinstance(full_response, dict) else 'Not a dict'}")
        print(f"DEBUG: Full response content: {full_response}")

        # Get the 'result' part - handle nested structure
        raw_incidents = full_response.get('result', [])
        print(f"DEBUG: raw_incidents type: {type(raw_incidents)}")
        print(f"DEBUG: raw_incidents content: {raw_incidents}")

        # Handle nested result structure from ServiceNow
        if isinstance(raw_incidents, dict) and 'result' in raw_incidents:
            print("Detected nested result structure - extracting inner result array")
            raw_incidents = raw_incidents['result']
            print(f"DEBUG: After extraction - type: {type(raw_incidents)}, length: {len(raw_incidents) if hasattr(raw_incidents, '__len__') else 'No length'}")

        # Check if raw_incidents is actually a list
        if not isinstance(raw_incidents, list):
            print(f"ERROR: Expected 'result' to be a list, but got {type(raw_incidents)}")
            return []

        # Check if the list is empty
        if not raw_incidents:
            print("Successfully fetched 0 incidents. No further action needed.")
            return []

        # Now we know we have a non-empty list, check the first item
        print(f"DEBUG: First item type: {type(raw_incidents[0])}")
        print(f"DEBUG: First item content: {raw_incidents[0]}")

        if isinstance(raw_incidents[0], str):
            print("Detected string-encoded JSON from ServiceNow. Parsing into objects...")
            try:
                # Use a list comprehension to convert each JSON string into a Python dictionary
                parsed_incidents = [json.loads(item) for item in raw_incidents]
                print(f"Successfully parsed {len(parsed_incidents)} incidents.")
                return parsed_incidents
            except json.JSONDecodeError as e:
                print(f"CRITICAL ERROR: Failed to parse JSON string from ServiceNow. Error: {e}")
                print(f"Problematic data sample: {raw_incidents[0]}")
                return []
        else:
            # If the data is already in the correct format (list of dicts), just return it
            print(f"Successfully fetched {len(raw_incidents)} incidents in correct format.")
            return raw_incidents

    except requests.exceptions.RequestException as req_err:
        print(f"A network error occurred fetching incidents: {req_err}")
    except KeyError as key_err:
        print(f"KeyError occurred: {key_err}")
        print("This suggests the response structure is different than expected.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return []

def get_gemini_summary(incidents):
    """Analyzes incidents using the Gemini API with robust retry and backoff logic."""
    if not incidents:
        return "No incidents to process."

    formatted_list = "\n".join([
        f"- {inc.get('number', 'N/A')}: {inc.get('short_description', 'No description')} (State: {inc.get('state', 'N/A')})"
        for inc in incidents
    ])

    prompt = f"""Analyze the following list of high-priority incidents from ServiceNow and provide a concise summary.

    Here is the list of incidents:
    {formatted_list}

    Your summary should include:
    1. The most urgent types of issues.
    2. The suggested next best action for each incident or group of incidents (e.g., assign, escalate, monitor).
    3. Any noticeable patterns or related incidents."""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print(f"Initializing Gemini model: {GEMINI_MODEL}")
        model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        return f"Error configuring Gemini model: {e}"

    max_retries = 4
    base_delay_seconds = 10
    for attempt in range(max_retries):
        try:
            print("Requesting analysis from Gemini...")
            response = model.generate_content(prompt)
            print("Successfully received summary from Gemini.")
            return response.text
        except exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                wait_time = base_delay_seconds * (2 ** attempt) + (os.urandom(1)[0] / 255.0)
                print(f"Rate limit hit. Retrying in {wait_time:.2f} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print("Max retries reached.")
                return f"Error: Exceeded Gemini API rate limits. Details: {e}"
        except Exception as e:
            return f"An unexpected error occurred while contacting Gemini: {e}"

# --- MAIN EXECUTION ---
def main():
    if not check_configuration():
        return
    incidents = get_high_priority_incidents()
    if incidents:
        summary = get_gemini_summary(incidents)
        print("\n=== Gemini Triage Summary ===")
        print(summary)
    else:
        # This will now be printed when 0 incidents are found
        print("\nNo incidents were fetched or an error occurred. Exiting.")

if __name__ == "__main__":
    main()