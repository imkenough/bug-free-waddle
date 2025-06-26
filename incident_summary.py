import os
import time
import requests
import json
import logging
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
from datetime import datetime

# Load variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_API_PATH = "/api/1775050/gemini_integration/incidents/high_priority"
SNOW_USERNAME = os.getenv("SNOW_USERNAME")
SNOW_PASSWORD = os.getenv("SNOW_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash"

# --- LOGGING SETUP ---
def setup_logging():
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    log_file = os.path.join(logs_dir, 'incident_triage.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# --- FUNCTION DEFINITIONS ---

def check_configuration():
    """Checks if all required environment variables are properly set."""
    missing_vars = []
    
    if not SNOW_INSTANCE:
        missing_vars.append("SNOW_INSTANCE")
    if not SNOW_USERNAME:
        missing_vars.append("SNOW_USERNAME") 
    if not SNOW_PASSWORD:
        missing_vars.append("SNOW_PASSWORD")
    if not GEMINI_API_KEY:
        missing_vars.append("GEMINI_API_KEY")
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or set the variables manually.")
        return False
    
    logger.info("Configuration check passed")
    return True

def get_high_priority_incidents():
    """Fetches and parses high-priority incidents from ServiceNow."""
    logger.info("Fetching high-priority incidents from ServiceNow...")
    url = f"{SNOW_INSTANCE}{SNOW_API_PATH}"
    headers = {"Accept": "application/json"}
    
    try:
        response = requests.get(
            url, 
            auth=(SNOW_USERNAME, SNOW_PASSWORD), 
            headers=headers, 
            timeout=30
        )
        response.raise_for_status()

        full_response = response.json()
        raw_incidents = full_response.get('result', [])

        # Handle nested result structure from ServiceNow
        if isinstance(raw_incidents, dict) and 'result' in raw_incidents:
            logger.info("Detected nested result structure - extracting inner result array")
            raw_incidents = raw_incidents['result']

        # Validate that we have a list
        if not isinstance(raw_incidents, list):
            logger.error(f"Expected 'result' to be a list, but got {type(raw_incidents)}")
            return []

        # Check if the list is empty
        if not raw_incidents:
            logger.info("No high-priority incidents found")
            return []

        # Handle string-encoded JSON (if needed)
        if isinstance(raw_incidents[0], str):
            logger.info("Detected string-encoded JSON - parsing into objects...")
            try:
                parsed_incidents = [json.loads(item) for item in raw_incidents]
                logger.info(f"Successfully parsed {len(parsed_incidents)} incidents")
                return parsed_incidents
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON string from ServiceNow: {e}")
                return []
        else:
            logger.info(f"Successfully fetched {len(raw_incidents)} incidents")
            return raw_incidents

    except requests.exceptions.Timeout:
        logger.error("Request to ServiceNow timed out")
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to ServiceNow - check your SNOW_INSTANCE URL")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from ServiceNow: {e}")
        if e.response.status_code == 401:
            logger.error("Authentication failed - check your credentials")
        elif e.response.status_code == 404:
            logger.error("API endpoint not found - check your SNOW_API_PATH")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error occurred: {e}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON response from ServiceNow")
    except Exception as e:
        logger.error(f"Unexpected error fetching incidents: {e}")

    return []

def analyze_incident_patterns(incidents):
    """Analyze incidents for patterns and categorize them."""
    patterns = {
        'sap_issues': [],
        'network_issues': [],
        'email_issues': [],
        'hardware_issues': [],
        'software_issues': [],
        'other_issues': []
    }
    
    for incident in incidents:
        desc = incident.get('short_description', '').lower()
        
        if 'sap' in desc:
            patterns['sap_issues'].append(incident)
        elif any(word in desc for word in ['network', 'wireless', 'vpn', 'dns']):
            patterns['network_issues'].append(incident)
        elif any(word in desc for word in ['email', 'exchange', 'outlook']):
            patterns['email_issues'].append(incident)
        elif any(word in desc for word in ['server', 'hardware', 'memory', 'laptop']):
            patterns['hardware_issues'].append(incident)
        elif any(word in desc for word in ['software', 'application', 'app']):
            patterns['software_issues'].append(incident)
        else:
            patterns['other_issues'].append(incident)
    
    # Log patterns found
    for category, items in patterns.items():
        if items:
            logger.info(f"Found {len(items)} {category.replace('_', ' ')}")
    
    return patterns

def get_gemini_summary(incidents):
    """Analyzes incidents using the Gemini API with robust retry and backoff logic."""
    if not incidents:
        return "No incidents to process."

    # Analyze patterns first
    patterns = analyze_incident_patterns(incidents)
    
    # Create formatted list with priority grouping
    formatted_sections = []
    
    # Group by state for better organization
    by_state = {}
    for inc in incidents:
        state = inc.get('state', 'Unknown')
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(inc)
    
    for state, state_incidents in by_state.items():
        formatted_sections.append(f"\n--- {state} Incidents ---")
        for inc in state_incidents:
            assignment = inc.get('assignment_group', 'Unassigned')
            ci = inc.get('cmdb_ci', 'No CI')
            formatted_sections.append(
                f"- {inc.get('number', 'N/A')}: {inc.get('short_description', 'No description')} "
                f"(Assigned: {assignment}, CI: {ci})"
            )

    formatted_list = "\n".join(formatted_sections)

    prompt = f"""Analyze the following list of {len(incidents)} high-priority incidents from ServiceNow and provide a comprehensive triage summary.

    INCIDENTS:
    {formatted_list}

    Please provide your analysis in the following format:

    ## 🚨 CRITICAL ISSUES REQUIRING IMMEDIATE ATTENTION
    [List the most urgent issues that need immediate response]

    ## 📊 INCIDENT PATTERNS & CLUSTERS
    [Identify related incidents that might indicate broader systemic issues]

    ## 🎯 RECOMMENDED ACTIONS
    [Provide specific next steps for each major issue or group of issues]

    ## ⚠️ POTENTIAL IMPACT ASSESSMENT
    [Assess business impact and user impact of major issues]

    Focus on actionable insights and prioritization for IT operations teams."""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info(f"Initializing Gemini model: {GEMINI_MODEL}")
        model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        logger.error(f"Error configuring Gemini model: {e}")
        return f"Error configuring Gemini model: {e}"

    max_retries = 4
    base_delay_seconds = 10
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Requesting analysis from Gemini (attempt {attempt + 1}/{max_retries})...")
            response = model.generate_content(prompt)
            logger.info("Successfully received summary from Gemini")
            return response.text
            
        except exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                wait_time = base_delay_seconds * (2 ** attempt) + (time.time() % 1)
                logger.warning(f"Rate limit hit. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Max retries reached for Gemini API")
                return f"Error: Exceeded Gemini API rate limits after {max_retries} attempts. Details: {e}"
                
        except Exception as e:
            logger.error(f"Unexpected error while contacting Gemini: {e}")
            return f"An unexpected error occurred while contacting Gemini: {e}"

def save_triage_report(summary, incidents_count):
    """Save the triage report to a file with timestamp."""
    # Create reports directory if it doesn't exist
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"triage_report_{timestamp}.md"
    filepath = os.path.join(reports_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# ServiceNow Incident Triage Report\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total High-Priority Incidents:** {incidents_count}\n\n")
            f.write("---\n\n")
            f.write(summary)
        
        logger.info(f"Triage report saved to: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save triage report: {e}")
        return None

# --- MAIN EXECUTION ---
def main():
    """Main execution function."""
    logger.info("=== ServiceNow Incident Triage Started ===")
    
    if not check_configuration():
        return 1
    
    incidents = get_high_priority_incidents()
    
    if incidents:
        logger.info(f"Processing {len(incidents)} incidents...")
        summary = get_gemini_summary(incidents)
        
        print("\n" + "="*60)
        print("🎯 SERVICENOW INCIDENT TRIAGE SUMMARY")
        print("="*60)
        print(summary)
        print("="*60)
        
        # Save report to file
        report_file = save_triage_report(summary, len(incidents))
        if report_file:
            print(f"\n📄 Report saved to: {report_file}")
        
        logger.info("Triage analysis completed successfully")
        return 0
    else:
        logger.info("No incidents to process - exiting")
        print("\n✅ No high-priority incidents found or an error occurred.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)