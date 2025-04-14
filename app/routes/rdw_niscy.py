from datetime import datetime
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
from typing import List
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

# this version works
@router.get("/pid-extraction/{request_id}")
async def extract_pid_data(request_id: str):
    # Check if we have an active session for this request
    if request_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"No active session found for request ID {request_id}. Please start a new authentication flow.")
    
    # Get the driver and wait from the active session
    session_data = active_sessions.get(request_id) # Use .get for safer access
    if not session_data:
         raise HTTPException(status_code=404, detail=f"Session data unexpectedly missing for request ID {request_id}.")
         
    driver = session_data.get("driver")
    wait = session_data.get("wait") # This wait object might have a longer timeout set during auth
    file_path = session_data.get("file_path")
    
    if not driver or not wait or not file_path:
        # Attempt to cleanup if possible
        if driver:
            try: driver.quit() 
            except: pass
        if request_id in active_sessions:
            del active_sessions[request_id]
        raise HTTPException(status_code=500, detail="Session data is incomplete or corrupted.")
    
    # Read the current request data from file
    try:
        with open(file_path, "r") as f:
            request_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read session file {file_path}: {str(e)}")

    # Initialize log collection
    log_messages = request_data.get("logs", [])
    def log_and_capture(message: str):
        logging.info(message)
        log_messages.append(message)
    
    # Use a shorter, dedicated wait for this extraction phase
    extract_wait = WebDriverWait(driver, 10) # 10 seconds should be sufficient for elements to appear after page load

    try:
        # Try to find results and extract data using the existing driver session
        log_and_capture(f"Using existing driver session for request {request_id}")
        
        # First try to find the results container
        log_and_capture("Checking if presentation results exist")
        try:
            # Check current URL (quick check)
            current_url = driver.current_url
            log_and_capture(f"Current driver URL: {current_url}")
            
            # Find the results container - indicates presentation is done
            results_selector = "vc-presentations-results"
            log_and_capture(f"Waiting for results container: {results_selector}")
            results_container = extract_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, results_selector))
            )
            log_and_capture("Found vc-presentations-results element - presentation is complete")
            
            # Find the 'View Content' button within the specific PID card more directly
            log_and_capture("Looking for PID card's View Content button")
            # This XPath is more specific and likely faster
            view_button_xpath = "//mat-card[.//mat-card-title[contains(text(), 'eu.europa.ec.eudi.pid.1')]]//button[.//span[contains(text(), 'View Content')]]"
            view_content_button = extract_wait.until(
                EC.element_to_be_clickable((By.XPATH, view_button_xpath))
            )
            log_and_capture("Found View Content button")
            
            # Click the button (JS click is often more reliable)
            try:
                driver.execute_script("arguments[0].click();", view_content_button)
                log_and_capture("Clicked View Content button using JavaScript")
            except Exception as click_err:
                log_and_capture(f"JS click failed ({click_err}), trying regular click.")
                view_content_button.click() # Fallback click
                log_and_capture("Clicked View Content button (fallback)")

            # Wait for the dialog using the selector that worked previously or a more stable one
            log_and_capture("Waiting for dialog to appear")
            # Prioritize mat-dialog-container or the one from logs
            dialog_selector = "mat-dialog-container, div[class*='dialog'][role='dialog']" 
            try:
                dialog = extract_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, dialog_selector))
                )
                log_and_capture(f"Found dialog using selector: {dialog_selector}")
            except Exception as dialog_err:
                 log_and_capture(f"Dialog not found with primary selector: {dialog_err}. Raising error.")
                 raise Exception("Dialog not found after clicking 'View Content'") # Fail faster

            # Get only the dialog text, which is needed for extraction
            log_and_capture("Getting dialog text content")
            try:
                dialog_text = dialog.text if dialog else ""
                log_and_capture(f"Dialog Text Length: {len(dialog_text)}")
                if not dialog_text:
                    log_and_capture("Warning: Dialog text is empty.")
            except Exception as e:
                log_and_capture(f"Error getting dialog text: {str(e)}")
                dialog_text = ""

            # Simplified Extraction - Rely on the working regex patterns
            log_and_capture("Extracting data using primary regex patterns")
            extracted_data = {}
            field_patterns = {
                "birth_date": r"birth_date\s+value:\s*(\d{4}-\d{2}-\d{2})",
                "family_name": r"family_name\s*\n\s*([^\n\r]+)", # Assumes name is on the next line
                "given_name": r"given_name\s*\n\s*([^\n\r]+)"    # Assumes name is on the next line
            }

            for field, pattern in field_patterns.items():
                match = re.search(pattern, dialog_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    extracted_data[field] = match.group(1).strip()
                    log_and_capture(f"*** Extracted {field}: {extracted_data[field]} ***")
                else:
                     log_and_capture(f"Pattern did not match for {field}") # Log if pattern fails

            # Check if all required fields were found
            required_fields = set(field_patterns.keys())
            found_fields = set(extracted_data.keys())
            
            if found_fields == required_fields:
                log_and_capture("Successfully extracted all required fields.")
                request_data["status"] = "success"
                
                # Initialize presentation_data safely
                if request_data.get("presentation_data") is None:
                    request_data["presentation_data"] = {}
                    
                request_data["presentation_data"]["extracted_data"] = extracted_data
                # Store length of text, not HTML, as it's less resource intensive
                request_data["presentation_data"]["dialog_text_length"] = len(dialog_text) 
                request_data["presentation_data"]["capture_timestamp"] = datetime.now().isoformat()
                
                final_status = "success"
                final_message = "Extraction successful."
            
            else: # Some fields missing
                missing = required_fields - found_fields
                log_and_capture(f"Extraction incomplete. Missing fields: {', '.join(missing)}")
                request_data["status"] = "extraction_incomplete" # More specific status
                final_status = "extraction_incomplete"
                final_message = f"Extraction incomplete. Missing: {', '.join(missing)}"

            # Save updated request data and logs
            request_data["logs"] = log_messages
            with open(file_path, "w") as f:
                json.dump(request_data, f, indent=4)
            
            # Clean up the driver session
            log_and_capture(f"Closing driver session for request {request_id}")
            driver.quit()
            del active_sessions[request_id]
            
            return {
                "status": final_status,
                "message": final_message,
                "data": { "extracted_data": extracted_data },
                "logs": log_messages # Return logs for debugging
            }

        except Exception as e:
            log_and_capture(f"Error during extraction process: {str(e)}")
            # Check if it's just that the presentation isn't complete
            if isinstance(e, (webdriver.exceptions.TimeoutException)) and "vc-presentations-results" in str(e):
                log_and_capture("Presentation not yet complete (Timeout waiting for results).")
                request_data["status"] = "pending"
                status_to_return = "pending"
                message_to_return = "Presentation not yet complete. Complete the wallet flow and check again."
            else:
                # Different error occurred
                request_data["status"] = "error"
                request_data["error"] = str(e)
                status_to_return = "error"
                message_to_return = f"Error during extraction: {str(e)}"
            
            # Save status and logs
            request_data["logs"] = log_messages
            with open(file_path, "w") as f:
                json.dump(request_data, f, indent=4)
                
            # Don't close driver if pending, otherwise close if error
            if status_to_return == "error":
                try: 
                    if driver: driver.quit()
                except: pass # Ignore errors quitting driver
                if request_id in active_sessions:
                    del active_sessions[request_id]

            return {
                "status": status_to_return,
                "message": message_to_return,
                "logs": log_messages
            }
            
    except Exception as e:
        # Catch-all for unexpected errors outside the inner try-except
        log_and_capture(f"Outer error in extract_pid_data: {str(e)}")
        if request_id in active_sessions:
            try:
                 if active_sessions[request_id].get("driver"):
                     active_sessions[request_id].get("driver").quit()
            except: pass
            del active_sessions[request_id] # Ensure cleanup
        # Try to update status in file if possible
        try:
            request_data["status"] = "error"
            request_data["error"] = f"Outer exception: {str(e)}"
            request_data["logs"] = log_messages
            with open(file_path, "w") as f:
                json.dump(request_data, f, indent=4)
        except: pass # Ignore if file writing fails here

        # Return a generic error response
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}",
            "logs": log_messages
        }

@router.get("/pid-authentication")
async def verify_pid_authentication():
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
    options.add_argument("--disable-default-apps") # Can sometimes cause issues
    options.add_argument("--disable-sync")         # Generally safe but let's keep defaults
    options.add_argument("--metrics-recording-only") # Less critical
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--headless=new") 
    # Enable this for faster page loads
    options.add_argument("--blink-settings=imagesEnabled=false") 
    options.add_argument("--window-size=1280x720") # Smaller window size can be faster
    options.add_argument("--single-process") # May improve speed on some systems
    # Avoid options that might break sites or be less effective
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument(f"--user-data-dir={user_data_dir}") # Re-evaluate if needed, can slow down startup

    # Performance preferences - keep it minimal
    prefs = {
        'profile.default_content_settings.images': 2,  # Disable images
        'profile.managed_default_content_settings.images': 2
    }
    options.add_experimental_option('prefs', prefs)

    # Use the system-installed chromedriver
    service = Service("/usr/bin/chromedriver")
    driver = None # Initialize driver to None for cleanup
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(15)  # Reduced timeout: 15 seconds
        wait = WebDriverWait(driver, 7)  # Slightly longer default wait: 7 seconds

        # Navigate to the verifier website
        log_and_capture("Navigating to verifier website")
        driver.get("https://eudi-verifier.nieuwlaar.com/custom-request/create")

        # Generate random UUIDs for id and nonce
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

        # Find the text editor and input the JSON using JavaScript
        log_and_capture("Inputting JSON into the editor via JS")
        try:
            editor_selector = "div.cm-content"
            # Ensure element is present before executing script
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, editor_selector)))
            driver.execute_script(
                f"document.querySelector('{editor_selector}').textContent = arguments[0]; "
                f"document.querySelector('{editor_selector}').dispatchEvent(new Event('input', {{ bubbles: true }}));", 
                json_content
            )
        except Exception as e:
            log_and_capture(f"JS injection failed: {str(e)}. Raising error.")
            raise # Re-raise the exception to fail fast

        # Click the Next button using JavaScript
        log_and_capture("Clicking Next button via JS")
        try:
            next_button_selector = "button.primary"
            # Ensure button is clickable
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector)))
            driver.execute_script("arguments[0].click();", next_button) 
        except Exception as e:
             log_and_capture(f"JS click failed for Next button: {str(e)}. Raising error.")
             raise # Re-raise

        # Wait for the QR code page (wallet link) to load
        log_and_capture("Waiting for wallet link to appear")
        wallet_link_selector = "a[href^='eudi-openid4vp://']"
        wallet_link = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, wallet_link_selector)
        )).get_attribute('href')
        
        log_and_capture(f"Wallet link obtained: {wallet_link[:50]}...") # Log truncated link
        
        # Create authentication-requests directory if it doesn't exist
        auth_requests_dir = Path("authentication-requests")
        auth_requests_dir.mkdir(exist_ok=True)

        # Prepare initial data to store
        request_data = {
            "id": request_id,
            "nonce": nonce,
            "wallet_link": wallet_link,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
            "presentation_data": None,
            "logs": log_messages  # Store initial logs
        }

        # Save initial JSON file
        file_path = auth_requests_dir / f"{request_id}.json"
        with open(file_path, "w") as f:
            json.dump(request_data, f, indent=4)

        log_and_capture(f"Saved authentication request data to {file_path}")
        
        # Store the driver and a reasonable wait time for extraction phase
        active_sessions[request_id] = {
            "driver": driver, 
            "wait": WebDriverWait(driver, 30),  # 30s wait for user interaction during extraction
            "file_path": file_path,
            "timestamp": request_data["timestamp"] # Use timestamp from request_data
        }
        log_and_capture(f"Stored driver session for request ID: {request_id}")
        
        # **Important**: Don't return the driver object here
        # It stays alive for the extraction endpoint
        driver = None # Prevent driver from being cleaned up in finally block

        # Return initial response
        initial_response = {
            "status": "success",
            "data": {
                "id": request_id,
                "wallet_link": wallet_link,
                "extraction_endpoint": f"/pid-extraction/{request_id}"
            },
            "message": "Authentication initiated. Complete wallet flow, then call extraction endpoint.",
            "logs": log_messages
        }
        
        return initial_response

    except Exception as e:
        err_msg = f"Error in verify_pid_authentication: {str(e)}"
        logging.error(err_msg)
        logging.exception("Stack trace:") # Log full stack trace for debugging
        log_messages.append(f"ERROR: {err_msg}")
        raise HTTPException(status_code=500, detail={"error": str(e), "logs": log_messages})
    finally:
        # Cleanup the driver ONLY if it wasn't passed to active_sessions
        if driver: 
            try:
                log_and_capture("Cleaning up driver in finally block (error occurred before session storage)")
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

