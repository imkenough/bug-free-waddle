# Automated ServiceNow Incident Triage with Google Gemini

This project provides a powerful solution for IT operations teams by automating the triage of high-priority incidents from a ServiceNow instance. It fetches active, critical incidents, uses Google's Gemini Pro model to analyze patterns and generate actionable insights, and produces a concise summary report.

## Features

- **ServiceNow Integration**: Connects to a custom ServiceNow Scripted REST API to fetch real-time incident data.
- **Intelligent Analysis**: Leverages the Google Gemini API to analyze incident descriptions, identify patterns, and cluster related issues.
- **Actionable Summaries**: Generates a comprehensive triage report in Markdown format, highlighting critical issues, patterns, and recommended actions.
- **Robust & Configurable**: Uses environment variables for secure configuration and includes error handling with logging.
- **Automated Reporting**: Saves each triage summary to a timestamped file for historical tracking.
- **Resilient API Calls**: Implements exponential backoff and retry logic for calls to the Gemini API to handle rate limits gracefully.

## How It Works

The system operates in a straightforward, orchestrated flow:

1. **ServiceNow API**: A Scripted REST API (`sn_rest_script.js`) is deployed on your ServiceNow instance. When called, it queries for active, priority 1 incidents and returns them as a structured JSON object.
2. **Python Orchestrator**: The local Python script (`incident_summary.py`) is executed.
3. **Fetch Data**: The script makes an authenticated GET request to the ServiceNow API endpoint to retrieve the list of high-priority incidents.
4. **Construct Prompt**: It processes the raw incident data, formats it into a clear and detailed prompt, and includes instructions for the AI model.
5. **Analyze with Gemini**: The script sends the structured prompt to the Google Gemini API for analysis.
6. **Generate Report**: Gemini returns a detailed triage summary. The Python script then prints this summary to the console and saves it as a timestamped Markdown file in the `reports/` directory.

## Setup and Installation

Follow these steps to set up and run the project.

### Prerequisites

- **Python 3.8+**
- **ServiceNow Instance**: Administrative access to a ServiceNow instance to create a Scripted REST API and a service account user.
- **Google Cloud Project**: A Google Cloud account with the **Generative Language API** (Gemini) enabled.
- **Git**

### Part 1: ServiceNow Configuration

1. **Create a Service Account User**:
    - In ServiceNow, navigate to **User Administration > Users** and create a new user (e.g., `gemini.integration`).
    - Assign this user the `rest_service` role. This provides the necessary permissions to access Scripted REST APIs.
    - Give the user a strong password and note down the username and password.
2. **Create the Scripted REST API**:
    - In your ServiceNow instance, navigate to **System Web Services > Scripted Web Services > Scripted REST APIs**.
    - Click **New**.
    - Fill in the form:
        - **Name**: `Gemini Integration`
        - **API ID**: `gemini_integration` (This will be part of your API path)
    - Submit the record.
3. **Create the API Resource**:
    - Open the `Gemini Integration` API you just created.
    - In the **Resources** related list at the bottom, click **New**.
    - Fill in the resource form:
        - **Name**: `High Priority Incidents`
        - **HTTP Method**: `GET`
        - **Relative path**: `/incidents/high_priority`
        - **Requires authentication**: Keep this checked.
    - In the **Script** field, copy and paste the entire content of the `sn_rest_script.js` file.
    - Submit the resource.

Your ServiceNow API is now ready. The full path will be something like `https://YOUR_INSTANCE.service-now.com/api/x_YOUR_SCOPE_ID/gemini_integration/incidents/high_priority`. You can find the exact path on the Scripted REST API record.

### Part 2: Local Machine Setup

1. **Clone the Repository**:
    
    ```bash
    git clone <https://github.com/your-username/your-repository-name.git>
    cd your-repository-name
    
    ```
    
2. **Create a Virtual Environment**:
It's highly recommended to use a virtual environment to manage dependencies.
    
    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    
    # For Windows
    python -m venv venv
    .\\venv\\Scripts\\activate
    
    ```
    
3. **Create a `requirements.txt` file**:
Create a file named `requirements.txt` and add the following lines:
    
    ```
    requests
    google-generativeai
    python-dotenv
    
    ```
    
4. **Install Dependencies**:
    
    ```bash
    pip install -r requirements.txt
    
    ```
    
5. **Configure Environment Variables**:
Create a file named `.env` in the root of the project directory. Copy the contents of `.env.example` into it and fill in your specific credentials. 
    
    **`.env.example`**
    
    ```
    # ServiceNow Configuration
    SNOW_INSTANCE="<https://your-instance.service-now.com>"
    SNOW_API_PATH="/api/1775050/gemini_integration/incidents/high_priority" # <-- IMPORTANT: Update the scope ID (1775050) to match yours
    SNOW_USERNAME="your-servicenow-service-account-username"
    SNOW_PASSWORD="your-servicenow-service-account-password"
    
    # Google Gemini Configuration
    GEMINI_API_KEY="your-google-gemini-api-key"
    
    ```
    
    > Important: To find your SNOW_API_PATH, go to the Scripted REST API record in ServiceNow. The "Base API path" field will show you the correct path, including your unique application scope ID (e.g., /api/x_123456_gemini_integ).
    > 

## Usage

Once the setup is complete, running the script is simple.

1. Make sure your virtual environment is activated.
2. Run the Python script from your terminal:
    
    ```bash
    python incident_summary.py
    
    ```
    

The script will:

1. Log its progress to the console and to `logs/incident_triage.log`.
2. Print the final, formatted Gemini Triage Summary to the console.
3. Save the summary as a Markdown file in the `reports/` directory (e.g., `reports/triage_report_20231027_103000.md`).

### Example Console Output

```
=== ServiceNow Incident Triage Started ===
2023-10-27 10:30:00,123 - INFO - Configuration check passed
2023-10-27 10:30:00,123 - INFO - Fetching high-priority incidents from ServiceNow...
2023-10-27 10:30:01,456 - INFO - Successfully fetched 8 incidents
2023-10-27 10:30:01,456 - INFO - Processing 8 incidents...
2023-10-27 10:30:01,457 - INFO - Initializing Gemini model: gemini-2.0-flash
2023-10-27 10:30:01,457 - INFO - Requesting analysis from Gemini (attempt 1/4)...
2023-10-27 10:30:03,789 - INFO - Successfully received summary from Gemini

============================================================
🎯 SERVICENOW INCIDENT TRIAGE SUMMARY
============================================================
## 🚨 CRITICAL ISSUES REQUIRING IMMEDIATE ATTENTION
- INC0010005: "Email services are down for the entire EMEA region" - This is a major outage affecting a whole region. The Network Operations team should be engaged immediately.

## 📊 INCIDENT PATTERNS & CLUSTERS
- **SAP Performance Issues**: Three incidents (INC0010002, INC0010007, INC0010008) report slow performance in the SAP Financials module. This points to a systemic issue with the SAP application or its underlying database.

... (rest of the report) ...

============================================================

📄 Report saved to: reports/triage_report_20231027_103004.md

```

## Project Structure

```
.
├── .gitignore             # Specifies files to be ignored by Git
├── .env                   # Local environment variables (created by you)
├── .env.example           # Template for the .env file
├── incident_summary.py    # Main Python script for orchestration and analysis
├── sn_rest_script.js      # ServiceNow Scripted REST API code
├── requirements.txt       # Python package dependencies
├── logs/                    # Directory for log files (created automatically)
│   └── incident_triage.log
└── reports/                 # Directory for saved reports (created automatically)
    └── triage_report_...md

```
