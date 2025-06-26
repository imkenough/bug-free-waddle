import os
import time
import requests
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
MAX_INCIDENTS_TO_FETCH = 10
# Changed from "gemini-1.5-pro" to the more common free-tier model "gemini-1.0-pro"
GEMINI_MODEL = "gemini-2.0-flash"

# --- FUNCTION DEFINITIONS ---

def check_configuration():
    """Checks if all required environment variables are properly set."""
    if not all([SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD, GEMINI_API_KEY]):
        print("CRITICAL ERROR: Environment variables not set.")
        print("Please check your .env file or set the variables manually.")
        return False
    return True

def get_high_priority_incidents():
    """Fetches high-priority incidents from the ServiceNow instance."""
    print(f"Fetching up to {MAX_INCIDENTS_TO_FETCH} high-priority incidents from ServiceNow...")
    # ... (rest of the function is unchanged)
    url = f"{SNOW_INSTANCE}{SNOW_API_PATH}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, auth=(SNOW_USERNAME, SNOW_PASSWORD), headers=headers, timeout=15)
        response.raise_for_status()
        incidents = response.json().get('result', [])
        limited_incidents = incidents[:MAX_INCIDENTS_TO_FETCH]
        print(f"Successfully fetched {len(incidents)} total incidents, processing {len(limited_incidents)}.")
        return limited_incidents
    except requests.exceptions.RequestException as req_err:
        print(f"A network error occurred fetching incidents: {req_err}")
    return []

def get_gemini_summary(incidents):
    """Analyzes incidents using the Gemini API with robust retry and backoff logic."""
    if not incidents:
        return "No incidents to process."

    # ... (prompt formatting is unchanged)
    formatted_list = "\n".join([
        f"- {inc.get('number', 'N/A')}: {inc.get('short_description', 'No description')} (State: {inc.get('state', 'N/A')})"
        for inc in incidents
    ])

    prompt = f"""Analyze the following list of high-priority incidents from ServiceNow and provide a concise summary.

    Here is the list of incidents:
    {formatted_list}

    Your summary should include:x   
    1. The most urgent types of issues.
    2. The suggested next best action for each incident or group of incidents (e.g., assign, escalate, monitor).
    3. Any noticeable patterns or related incidents."""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # --- MODIFIED: Use the new variable to set the model ---
        print(f"Initializing Gemini model: {GEMINI_MODEL}")
        model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        return f"Error configuring Gemini model: {e}"

    # ... (retry logic is unchanged)
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
        print("\nNo incidents were fetched or an error occurred. Exiting.")

if __name__ == "__main__":
    main()