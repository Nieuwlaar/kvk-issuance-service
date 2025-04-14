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

@router.get("/pid-extraction/{request_id}")
async def extract_pid_data(request_id: str):
    # Check if we have an active session for this request
    if request_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"No active session found for request ID {request_id}. Please start a new authentication flow.")
    
    # Get the driver and wait from the active session
    session_data = active_sessions[request_id]
    driver = session_data.get("driver")
    wait = session_data.get("wait")
    file_path = session_data.get("file_path")
    
    if not driver or not wait or not file_path:
        raise HTTPException(status_code=500, detail="Session data is incomplete")
    
    # Read the current request data from file
    with open(file_path, "r") as f:
        request_data = json.load(f)
    
    # Initialize log collection
    log_messages = request_data.get("logs", [])
    def log_and_capture(message: str):
        logging.info(message)
        log_messages.append(message)
    
    try:
        # Try to find results and extract data using the existing driver session
        log_and_capture(f"Using existing driver session for request {request_id}")
        
        # First try to find the results container
        log_and_capture("Checking if presentation results exist")
        try:
            # Use a moderate wait for UI elements - increased from original but not too long
            wait_medium = WebDriverWait(driver, 10)
            
            # Check current URL
            current_url = driver.current_url
            log_and_capture(f"Current driver URL: {current_url}")
            
            # Find the results container
            results_container = wait_medium.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "vc-presentations-results"))
            )
            log_and_capture("Found vc-presentations-results element - presentation is complete")
            
            # Find the mat-card containing the PID credential and the View Content button in one operation
            log_and_capture("Looking for PID card and View Content button")
            view_button_xpath = "//mat-card[.//mat-card-title[contains(text(), 'eu.europa.ec.eudi.pid.1')]]//button.mdc-button--outlined"
            view_content_button = wait_medium.until(
                EC.element_to_be_clickable((By.XPATH, view_button_xpath))
            )
            log_and_capture("Found View Content button")
            
            # Try to click directly with JavaScript to avoid potential interception issues
            try:
                driver.execute_script("arguments[0].click();", view_content_button)
                log_and_capture("Clicked View Content button using JavaScript")
            except Exception as e:
                log_and_capture(f"JavaScript click failed, trying regular click: {str(e)}")
                view_content_button.click()
                log_and_capture("Clicked View Content button")
            
            # Wait for the dialog to appear - optimized selectors
            log_and_capture("Waiting for dialog to appear")
            dialog_selector = "div[class*='dialog'], div[role='dialog'], mat-dialog-container"
            
            try:
                dialog = wait_medium.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, dialog_selector))
                )
                log_and_capture(f"Found dialog")
            except Exception as e:
                log_and_capture(f"Dialog not found with standard selectors: {str(e)}")
                # Fallback attempt
                try:
                    dialogs = driver.find_elements(By.CSS_SELECTOR, "div:not([class])") 
                    for d in dialogs:
                        if "Attributes" in d.text and "Close" in d.text:
                            dialog = d
                            log_and_capture("Found dialog using text content heuristic")
                            break
                    if not dialog:
                        raise Exception("Dialog not found after multiple attempts")
                except Exception as e2:
                    log_and_capture(f"Fallback dialog search failed: {str(e2)}")
                    raise Exception("Dialog not found after multiple attempts")
            
            # Get the dialog content
            log_and_capture("Getting dialog content")
            try:
                dialog_text = dialog.text if dialog else ""
                log_and_capture(f"Dialog content Text: {dialog_text}")
                # Only get innerHTML if we really need it - save time
                dialog_content_length = len(dialog.get_attribute('outerHTML')) if dialog else 0
            except Exception as e:
                log_and_capture(f"Error getting dialog content: {str(e)}")
                dialog_text = ""
                dialog_content_length = 0

            # Fast extraction using improved patterns
            log_and_capture("Extracting data from dialog text")
            extracted_data = {}
            
            # Optimized regex patterns
            field_patterns = {
                "birth_date": [r"birth_date\s+value:\s*(\d{4}-\d{2}-\d{2})"],
                "family_name": [r"family_name\s*\n([^\n\r]+)"],
                "given_name": [r"given_name\s*\n([^\n\r]+)"]
            }
            
            # Process all fields at once
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, dialog_text, re.IGNORECASE)
                    if match:
                        extracted_data[field] = match.group(1).strip()
                        log_and_capture(f"*** Extracted {field}: {extracted_data[field]} ***")
                        break
            
            # If line-by-line is needed, use this optimized approach
            if len(extracted_data) < 3:
                lines = dialog_text.split('\n')
                log_and_capture(f"Using line-by-line parsing")
                
                field_map = {}
                current_field = None
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line: continue
                    
                    if "birth_date" in line.lower():
                        current_field = "birth_date"
                        field_map[current_field] = i
                    elif "family_name" in line.lower():
                        current_field = "family_name"
                        field_map[current_field] = i
                    elif "given_name" in line.lower():
                        current_field = "given_name"
                        field_map[current_field] = i
                
                # Process fields and values from adjacent lines
                for field, idx in field_map.items():
                    if field not in extracted_data and idx + 1 < len(lines):
                        value = lines[idx + 1].strip()
                        if value and not any(keyword in value.lower() for keyword in ["birth_date", "family_name", "given_name", "close", "attributes"]):
                            extracted_data[field] = value
                            log_and_capture(f"*** Extracted {field} from line: {value} ***")
            
            # Update the request data to include the extracted information
            if extracted_data:
                log_and_capture(f"Successfully extracted {len(extracted_data)} fields: {', '.join(extracted_data.keys())}")
                
                # Initialize presentation_data if it doesn't exist
                if request_data.get("presentation_data") is None:
                    request_data["presentation_data"] = {}
                
                # Update the request_data
                request_data["status"] = "success"
                request_data["presentation_data"]["extracted_data"] = extracted_data
                request_data["presentation_data"]["dialog_html_length"] = dialog_content_length
                request_data["presentation_data"]["capture_timestamp"] = datetime.now().isoformat()
                request_data["logs"] = log_messages
                
                # Save updated request data
                with open(file_path, "w") as f:
                    json.dump(request_data, f, indent=4)
                
                # Clean up the driver session
                driver.quit()
                del active_sessions[request_id]
                log_and_capture(f"Closed driver session for request {request_id}")
                
                return {
                    "status": "success",
                    "data": {
                        "extracted_data": extracted_data
                    },
                    "logs": log_messages
                }
            else:
                log_and_capture("No fields were extracted from the dialog")
                request_data["status"] = "extraction_failed"
                request_data["logs"] = log_messages
                with open(file_path, "w") as f:
                    json.dump(request_data, f, indent=4)
                
                return {
                    "status": "extraction_failed",
                    "message": "No fields could be extracted from the dialog",
                    "logs": log_messages
                }
                
        except Exception as e:
            # If we can't find the results container, the presentation isn't complete yet
            log_and_capture(f"Error checking presentation status: {str(e)}")
            if "vc-presentations-results" in str(e):
                log_and_capture("Presentation not yet complete")
                request_data["status"] = "pending"
                request_data["logs"] = log_messages
                with open(file_path, "w") as f:
                    json.dump(request_data, f, indent=4)
                return {
                    "status": "pending",
                    "message": "Presentation not yet complete. Complete the wallet flow and check again.",
                    "logs": log_messages
                }
            else:
                # Some other error occurred
                log_and_capture(f"Error during extraction: {str(e)}")
                request_data["status"] = "error"
                request_data["error"] = str(e)
                request_data["logs"] = log_messages
                with open(file_path, "w") as f:
                    json.dump(request_data, f, indent=4)
                return {
                    "status": "error",
                    "message": f"Error checking presentation status: {str(e)}",
                    "logs": log_messages
                }
            
    except Exception as e:
        log_and_capture(f"Error in extract_pid_data: {str(e)}")
        request_data["status"] = "error"
        request_data["error"] = str(e)
        request_data["logs"] = log_messages
        with open(file_path, "w") as f:
            json.dump(request_data, f, indent=4)
        
        # Clean up the session on error
        try:
            driver.quit()
        except:
            pass
        if request_id in active_sessions:
            del active_sessions[request_id]
        
        return {
            "status": "error",
            "message": f"Error extracting data: {str(e)}",
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
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--headless=new")
    # Enable this for faster page loads
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--window-size=1280x720")  # Smaller window size
    options.add_argument("--single-process")
    options.add_argument("--disable-web-security")  # Helps with some sites
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # Performance optimizations
    prefs = {
        'disk-cache-size': 4096,
        'profile.default_content_settings.images': 2,  # Disable images
        'profile.managed_default_content_settings.images': 2
    }
    options.add_experimental_option('prefs', prefs)

    # Use the system-installed chromedriver
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)  # Reduce timeout
    wait = WebDriverWait(driver, 5)  # Shorter waits

    try:
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

        # Find the text editor and input the JSON
        log_and_capture("Inputting JSON into the editor")
        try:
            # Try faster direct script injection first
            driver.execute_script(
                """
                const editorContent = document.querySelector('div.cm-content');
                if (editorContent) {
                    editorContent.textContent = arguments[0];
                    // Trigger change event for Angular to detect
                    const event = new Event('input', { bubbles: true });
                    editorContent.dispatchEvent(event);
                }
                """, 
                json_content
            )
        except Exception as e:
            log_and_capture(f"Direct script injection failed: {str(e)}. Trying standard method.")
            editor = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cm-content")))
            driver.execute_script("arguments[0].textContent = arguments[1]", editor, json_content)

        # Click the Next button
        log_and_capture("Clicking Next button")
        next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.primary")))
        driver.execute_script("arguments[0].click();", next_button)  # JavaScript click is faster

        # Wait for the QR code page to load and get the wallet link
        log_and_capture("Waiting for QR code page to load")
        wallet_link = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "a[href^='eudi-openid4vp://']")
        )).get_attribute('href')
        
        log_and_capture(f"Wallet link: {wallet_link}")
        
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
            "logs": log_messages  # Store all logs in the JSON file
        }

        # Save initial JSON file
        file_path = auth_requests_dir / f"{request_id}.json"
        with open(file_path, "w") as f:
            json.dump(request_data, f, indent=4)

        log_and_capture(f"Saved authentication request data to {file_path}")
        
        # Store the driver and wait in the active_sessions dictionary
        active_sessions[request_id] = {
            "driver": driver,
            "wait": WebDriverWait(driver, 30),  # Shorter wait than before but still reasonable
            "file_path": file_path,
            "timestamp": datetime.now().isoformat()
        }
        log_and_capture(f"Stored driver session for request ID: {request_id}")
        
        # Return initial response with QR code and instructions for data extraction
        initial_response = {
            "status": "success",
            "data": {
                "id": request_id,
                "wallet_link": wallet_link,
                "extraction_endpoint": f"/pid-extraction/{request_id}"
            },
            "message": "After completing the wallet flow, call the extraction endpoint to get the data",
            "logs": log_messages
        }
        
        return initial_response

    except Exception as e:
        err_msg = f"Error in verify_pid_authentication: {str(e)}"
        logging.error(err_msg)
        logging.exception("Stack trace:")
        log_messages.append(f"ERROR: {err_msg}")
        try:
            driver.quit()
        except:
            pass
        raise HTTPException(status_code=500, detail={"error": str(e), "logs": log_messages})

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

@router.get("/debug/cleanup-stale-sessions")
async def cleanup_stale_sessions():
    """Clean up stale sessions that have been idle for more than 10 minutes."""
    try:
        current_time = datetime.now()
        stale_session_ids = []
        
        # Find stale sessions
        for session_id, session_data in list(active_sessions.items()):
            try:
                session_time = datetime.fromisoformat(session_data.get("timestamp", "2000-01-01T00:00:00"))
                # If session is older than 10 minutes, mark it for cleanup
                if (current_time - session_time).total_seconds() > 600:  # 10 minutes
                    stale_session_ids.append(session_id)
            except Exception as e:
                # If we can't parse the timestamp, assume it's stale
                logging.error(f"Error parsing timestamp for session {session_id}: {str(e)}")
                stale_session_ids.append(session_id)
        
        # Clean up stale sessions
        cleaned_sessions = []
        for session_id in stale_session_ids:
            try:
                # Try to quit the driver
                driver = active_sessions[session_id].get("driver")
                if driver:
                    driver.quit()
                # Remove from active sessions
                del active_sessions[session_id]
                cleaned_sessions.append(session_id)
            except Exception as e:
                logging.error(f"Error cleaning up session {session_id}: {str(e)}")
        
        return {
            "status": "success",
            "cleaned_sessions_count": len(cleaned_sessions),
            "cleaned_sessions": cleaned_sessions,
            "remaining_sessions_count": len(active_sessions)
        }
    except Exception as e:
        logging.error(f"Error in cleanup_stale_sessions: {str(e)}")
        return {
            "status": "error",
            "message": f"Error cleaning up stale sessions: {str(e)}"
        }
