from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
from typing import List, Optional, Dict, Any
import uuid
import json
import os
from pathlib import Path
import re

# Create router with prefix
router = APIRouter()
user_data_dir = tempfile.mkdtemp()

# In-memory store for active driver sessions
active_sessions = {}

logger = logging.getLogger(__name__) # Make logger available at module level

# Define the request models
class PowerOfRepresentationRequest(BaseModel):
    legal_person_identifier: str
    legal_name: str

@router.post("/power-of-representation")
async def create_power_of_representation(request: PowerOfRepresentationRequest):
    try:
        logging.info(f"Received Power of Representation request for: {request.legal_name} ({request.legal_person_identifier})")
        
        # Initialize Chrome in headless mode with optimized settings
        options = webdriver.ChromeOptions()
        options.binary_location = "/usr/bin/chromium"  # Ensure chromium is used
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--window-size=1920x1080")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--enable-automation")
        options.add_argument("--password-store=basic")
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")

        # Use the system-installed chromedriver
        service = Service("/usr/bin/chromedriver")  # Specify path to the chromedriver
        driver = webdriver.Chrome(
            service=service,
            options=options
        )
        driver.set_page_load_timeout(30)
        
        try:
            # Navigate and fill forms with minimal waits
            driver.get("https://niscy-issuer.nieuwlaar.com/credential_offer_choice")
            
            # Use WebDriverWait with shorter timeouts
            wait = WebDriverWait(driver, 5)
            
            # Select Power of Representation and Pre-Auth
            wait.until(EC.presence_of_element_located((By.NAME, "eu.europa.ec.eudi.por_mdoc"))).click()
            driver.find_element(By.CSS_SELECTOR, 'input[value="pre_auth_code"]').click()
            driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Submit']").click()
            
            # Fill the form
            wait.until(EC.presence_of_element_located((By.NAME, "legal_person_identifier"))).send_keys(request.legal_person_identifier)
            driver.find_element(By.NAME, "legal_name").send_keys(request.legal_name)
            
            full_powers = driver.find_element(By.ID, "full_powers")
            if not full_powers.is_selected():
                full_powers.click()
            
            today = datetime.now().strftime("%Y-%m-%d")
            effective_date = driver.find_element(By.NAME, "effective_from_date")
            driver.execute_script(f"arguments[0].value = '{today}'", effective_date)
            
            driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Submit']").click()
            
            # Click Authorize
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'][value='Authorize']"))).click()
            
            # Extract final data
            qr_code = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "img[src^='data:image/png;base64,']")
            )).get_attribute('src')
            
            tx_code = driver.find_element(By.NAME, "tx_code").get_attribute('value')
            eudiw_link = driver.find_element(By.CSS_SELECTOR, "a[href^='openid-credential-offer://']").get_attribute('href')
            
            return {
                "status": "success",
                "data": {
                    "qr_code": qr_code,
                    "transaction_code": tx_code,
                    "eudiw_link": eudiw_link
                }
            }
            
        finally:
            driver.quit()
            
    except Exception as e:
        logging.error(f"Error in create_power_of_representation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pid-extraction/{request_id}")
async def get_pid_extraction_status(request_id: str):
    """(Fast) Gets the status/data for a PID request directly from the saved JSON file."""
    logging.info(f"Received status request for session: {request_id}")
    
    request_data = get_request_data_from_file(request_id)
    
    if request_data is None:
        # General file read error (logged in helper)
        raise HTTPException(
            status_code=404, 
            detail=f"Session file not found or could not be read for request ID {request_id}."
        )
        
    # Handle case where file itself indicates an error (e.g., corrupted JSON)
    if request_data.get("status") == "error" and "Corrupted session file" in request_data.get("error", ""):
         raise HTTPException(
             status_code=500, 
             detail=f"Session file for {request_id} is corrupted: {request_data.get('error')}"
         )

    # Extract relevant information from the stored data
    status = request_data.get("status", "unknown")
    extracted_data = request_data.get("presentation_data", {}).get("extracted_data") 
    error_message = request_data.get("error")
    logs = request_data.get("logs", [])

    response_body = {
        "status": status,
        "data": { "extracted_data": extracted_data } if extracted_data else {},
        "logs": logs 
    }
    
    # Add message based on status
    if status == "pending":
        response_body["message"] = "Extraction is pending. Background task processing or awaiting wallet interaction."
    elif status == "success":
        response_body["message"] = "Extraction completed successfully."
    elif status == "extraction_incomplete":
        response_body["message"] = f"Extraction finished but incomplete. Check logs/data."
        missing = list(set(["birth_date", "family_name", "given_name"]) - set(extracted_data.keys() if extracted_data else []))
        if missing:
             response_body["data"]["missing_fields"] = missing
    elif status == "error":
        response_body["message"] = f"An error occurred during background extraction: {error_message}"
        response_body["error_details"] = error_message
    else:
        response_body["message"] = f"Session status is '{status}'."

    logging.info(f"Returning status '{status}' for session {request_id}")
    return response_body

# --- Helper Function --- 
def get_request_data_from_file(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve request data from the session JSON file."""
    file_path = Path("authentication-requests") / f"{session_id}.json"
    if not file_path.exists():
        logger.warning(f"No data file found for session ID: {session_id} at {file_path}")
        return None
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as decode_err:
         logger.error(f"Error decoding JSON from {file_path}: {decode_err}")
         return {"status": "error", "error": f"Corrupted session file: {decode_err}", "logs": []} # Return specific error
    except Exception as e:
        logger.error(f"Error reading session data file {file_path}: {str(e)}")
        return None # Indicate general read error

@router.get("/pid-authentication")
async def verify_pid_authentication(background_tasks: BackgroundTasks):
    # List to capture log messages for the response
    log_messages: List[str] = []
    def log_and_capture(message: str):
        logging.info(message)
        log_messages.append(message)

    # Initialize Chrome with optimized settings for speed
    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Optimize for speed
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    # options.add_argument("--disable-default-apps") # Can sometimes cause issues
    # options.add_argument("--disable-sync")         # Generally safe but let's keep defaults
    # options.add_argument("--metrics-recording-only") # Less critical
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--headless=new") 
    # Enable this for faster page loads
    options.add_argument("--blink-settings=imagesEnabled=false") 
    options.add_argument("--window-size=1280x720") # Smaller window size can be faster
    options.add_argument("--single-process") # May improve speed on some systems
    # Avoid options that might break sites or be less effective
    # options.add_argument("--disable-web-security")
    # options.add_argument("--disable-site-isolation-trials")
    # options.add_argument(f"--user-data-dir={user_data_dir}") # Re-evaluate if needed, can slow down startup

    # Performance preferences - keep it minimal
    prefs = {
        'profile.default_content_settings.images': 2,  # Disable images
        'profile.managed_default_content_settings.images': 2
    }
    options.add_experimental_option('prefs', prefs)

    service = Service("/usr/bin/chromedriver")
    driver = None 
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(15)  
        wait = WebDriverWait(driver, 7)  

        log_and_capture("Navigating to verifier website")
        driver.get("https://eudi-verifier.nieuwlaar.com/custom-request/create")

        request_id = str(uuid.uuid4())
        nonce = str(uuid.uuid4())
        log_and_capture(f"Generated request ID: {request_id}")
        log_and_capture(f"Generated nonce: {nonce}")

        # Prepare the JSON to be entered (optimized for readability and size)
        json_content = f"""{{
  "type": "vp_token",
  "presentation_definition": {{
    "id": "{request_id}",
    "input_descriptors": [
      {{
        "id": "eu.europa.ec.eudi.pid.1",
        "format": {{ "mso_mdoc": {{ "alg": ["ES256"] }} }},
        "constraints": {{
          "limit_disclosure": "required",
          "fields": [
            {{ "path": ["$['eu.europa.ec.eudi.pid.1']['family_name']"], "intent_to_retain": false }},
            {{ "path": ["$['eu.europa.ec.eudi.pid.1']['given_name']"], "intent_to_retain": false }},
            {{ "path": ["$['eu.europa.ec.eudi.pid.1']['birth_date']"], "intent_to_retain": false }}
          ]
        }}
      }}
    ]
  }},
  "nonce": "{nonce}"
}}"""

        log_and_capture("Inputting JSON into the editor via JS")
        try:
            editor_selector = "div.cm-content"
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, editor_selector)))
            driver.execute_script(
                f"document.querySelector('{editor_selector}').textContent = arguments[0]; "
                f"document.querySelector('{editor_selector}').dispatchEvent(new Event('input', {{ bubbles: true }}));", 
                json_content
            )
        except Exception as e:
            log_and_capture(f"JS injection failed: {str(e)}. Raising error.")
            raise 

        log_and_capture("Clicking Next button via JS")
        try:
            next_button_selector = "button.primary"
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector)))
            driver.execute_script("arguments[0].click();", next_button) 
        except Exception as e:
             log_and_capture(f"JS click failed for Next button: {str(e)}. Raising error.")
             raise 

        log_and_capture("Waiting for wallet link to appear")
        wallet_link_selector = "a[href^='eudi-openid4vp://']"
        wallet_link = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, wallet_link_selector)
        )).get_attribute('href')
        
        log_and_capture(f"Wallet link obtained: {wallet_link[:50]}...") 
        
        auth_requests_dir = Path("authentication-requests")
        auth_requests_dir.mkdir(exist_ok=True)

        request_data = {
            "id": request_id,
            "nonce": nonce,
            "wallet_link": wallet_link,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
            "presentation_data": None,
            "logs": log_messages  
        }

        file_path = auth_requests_dir / f"{request_id}.json"
        with open(file_path, "w") as f:
            json.dump(request_data, f, indent=4)

        log_and_capture(f"Saved authentication request data to {file_path}")
        
        # Store driver and WAIT OBJECT (with longer timeout) for the background task
        active_sessions[request_id] = {
            "driver": driver, 
            "wait": WebDriverWait(driver, 300),  # << INCREASED WAIT FOR USER: 5 minutes for wallet interaction
            "file_path": str(file_path), # Store as string
            "timestamp": request_data["timestamp"] 
        }
        log_and_capture(f"Stored driver session for request ID: {request_id}")
        
        # Schedule the background task
        background_tasks.add_task(handle_pid_extraction_in_background, request_id)
        log_and_capture(f"Scheduled background task for {request_id}")

        # Prevent driver from being cleaned up in finally block NOW
        driver_to_keep = driver 
        driver = None # Set driver to None so finally block doesn't quit it

        initial_response = {
            "status": "success",
            "data": {
                "id": request_id,
                "wallet_link": wallet_link,
                "extraction_endpoint": f"/pid-extraction/{request_id}"
            },
            "message": "Authentication initiated. Background task started for extraction. Poll the extraction endpoint.",
            "logs": log_messages
        }
        
        return initial_response

    except Exception as e:
        # ... (exception handling remains similar) ...
        err_msg = f"Error in verify_pid_authentication: {str(e)}"
        # ... (logging) ...
        raise HTTPException(status_code=500, detail={"error": str(e), "logs": log_messages})
    finally:
        # Cleanup the driver ONLY if it wasn't successfully passed to active_sessions
        if driver: 
            try:
                log_and_capture("Cleaning up driver in finally block (error occurred before session storage or task scheduling)")
                driver.quit()
            except Exception as quit_err:
                 log_and_capture(f"Error quitting driver in finally block: {quit_err}")

@router.get("/debug/active-sessions")
async def get_active_sessions():
    """Return information about active sessions for debugging purposes."""
    try:
        session_info = {}
        for session_id, session_data in active_sessions.items():
            # Don't include the driver or wait objects in the response
            session_info[session_id] = {
                "timestamp": session_data.get("timestamp", "unknown"),
                "file_path": str(session_data.get("file_path", "unknown")),
                "has_driver": session_data.get("driver") is not None,
                "has_wait": session_data.get("wait") is not None
            }
        
        return {
            "status": "success",
            "active_session_count": len(active_sessions),
            "sessions": session_info
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error retrieving active sessions: {str(e)}"
        }

@router.delete("/debug/active-sessions/{session_id}")
async def delete_active_session(session_id: str):
    """Delete an active session by ID."""
    try:
        if session_id not in active_sessions:
            return {
                "status": "not_found",
                "message": f"No active session found with ID: {session_id}"
            }
        
        # Close the driver if it exists
        try:
            driver = active_sessions[session_id].get("driver")
            if driver:
                driver.quit()
        except Exception as e:
            logging.error(f"Error closing driver for session {session_id}: {str(e)}")
        
        # Remove the session
        del active_sessions[session_id]
        
        return {
            "status": "success",
            "message": f"Session {session_id} deleted successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error deleting session {session_id}: {str(e)}"
        }
