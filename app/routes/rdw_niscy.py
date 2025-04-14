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
            # Use a longer wait for UI elements
            wait_longer = WebDriverWait(driver, 20)
            
            # Check current URL
            current_url = driver.current_url
            log_and_capture(f"Current driver URL: {current_url}")
            
            # Find the results container
            results_container = wait_longer.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "vc-presentations-results"))
            )
            log_and_capture("Found vc-presentations-results element - presentation is complete")
            
            # Find the mat-card containing the PID credential
            log_and_capture("Looking for PID card")
            pid_card = wait_longer.until(
                EC.presence_of_element_located((By.XPATH, "//mat-card[.//mat-card-title[contains(text(), 'eu.europa.ec.eudi.pid.1')]]"))
            )
            log_and_capture("Found PID card")

            # Find and click the View Content button
            log_and_capture("Looking for View Content button")
            view_content_button = pid_card.find_element(By.CSS_SELECTOR, "button.mdc-button--outlined span.mdc-button__label")
            log_and_capture("Found View Content button")
            view_content_button.click()
            log_and_capture("Clicked View Content button")
            
            # Wait for the dialog to appear
            log_and_capture("Waiting for dialog to appear")
            dialog_selectors = [
                (By.CSS_SELECTOR, "div[role='dialog']"),
                (By.CSS_SELECTOR, "div.modal-content"),
                (By.CSS_SELECTOR, "div.modal-dialog"),
                (By.CSS_SELECTOR, "div[class*='modal']"),
                (By.CSS_SELECTOR, "div[class*='dialog']")
            ]
            
            dialog = None
            for selector in dialog_selectors:
                try:
                    log_and_capture(f"Trying dialog selector: {selector[1]}")
                    dialog = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(selector)
                    )
                    log_and_capture(f"Found dialog using selector: {selector[1]}")
                    break
                except Exception as e:
                    log_and_capture(f"Did not find dialog with selector {selector[1]}")
                    continue
            
            if not dialog:
                raise Exception("Dialog not found after clicking 'View Content'")
            
            # Get the dialog content
            log_and_capture("Getting dialog content")
            try:
                dialog_content = dialog.get_attribute('innerHTML') if dialog else ""
                dialog_text = dialog.text if dialog else ""
                log_and_capture(f"Dialog content Text: {dialog_text}")
            except Exception as e:
                log_and_capture(f"Error getting dialog content: {str(e)}")
                dialog_content = ""
                dialog_text = ""

            # Extract the specific fields we need
            log_and_capture("Extracting specific fields (birth_date, given_name, family_name) from dialog text")
            extracted_data = {}
            
            # Try to extract from dialog text
            try:
                # More robust parsing logic for the Angular Material dialog format
                birth_date_patterns = [
                    r"eu\.europa\.ec\.eudi\.pid\.1:birth_date\s+value:\s*(\d{4}-\d{2}-\d{2})",
                    r"birth_date\s+(?:value:)?\s*(\d{4}-\d{2}-\d{2})",
                    r"birth.date.*?(\d{4}-\d{2}-\d{2})",
                    r"value:\s*(\d{4}-\d{2}-\d{2})"
                ]
                
                family_name_patterns = [
                    r"eu\.europa\.ec\.eudi\.pid\.1:family_name\s+(?:\n|\r\n?)([^\n\r]+)",
                    r"family.name.*?(?:\n|\r\n?)([^\n\r]+)",
                    r"family.name[^\n\r]*?([^\n\r:]+)$"
                ]
                
                given_name_patterns = [
                    r"eu\.europa\.ec\.eudi\.pid\.1:given_name\s+(?:\n|\r\n?)([^\n\r]+)",
                    r"given.name.*?(?:\n|\r\n?)([^\n\r]+)",
                    r"given.name[^\n\r]*?([^\n\r:]+)$"
                ]
                
                # Try each pattern for birth_date
                for pattern in birth_date_patterns:
                    birth_date_match = re.search(pattern, dialog_text, re.IGNORECASE)
                    if birth_date_match:
                        extracted_data["birth_date"] = birth_date_match.group(1).strip()
                        log_and_capture(f"*** Extracted birth_date: {extracted_data['birth_date']} using pattern: {pattern} ***")
                        break
                
                # Try each pattern for family_name
                for pattern in family_name_patterns:
                    family_name_match = re.search(pattern, dialog_text, re.IGNORECASE)
                    if family_name_match:
                        extracted_data["family_name"] = family_name_match.group(1).strip()
                        log_and_capture(f"*** Extracted family_name: {extracted_data['family_name']} using pattern: {pattern} ***")
                        break
                
                # Try each pattern for given_name
                for pattern in given_name_patterns:
                    given_name_match = re.search(pattern, dialog_text, re.IGNORECASE)
                    if given_name_match:
                        extracted_data["given_name"] = given_name_match.group(1).strip()
                        log_and_capture(f"*** Extracted given_name: {extracted_data['given_name']} using pattern: {pattern} ***")
                        break
                
                # Fallback: Try to parse by lines
                if len(extracted_data) < 3:
                    lines = dialog_text.split('\n')  # Split by newline characters
                    log_and_capture(f"Trying line-by-line parsing of {len(lines)} lines")
                    
                    current_field = None
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Check if this is a field name line
                        if "birth_date" in line.lower():
                            current_field = "birth_date"
                            # Try to extract from this line too
                            if ":" in line:
                                value = line.split(":", 1)[1].strip()
                                if re.match(r"\d{4}-\d{2}-\d{2}", value):
                                    extracted_data["birth_date"] = value
                                    log_and_capture(f"*** Extracted birth_date from line: {value} ***")
                        elif "family_name" in line.lower():
                            current_field = "family_name"
                        elif "given_name" in line.lower():
                            current_field = "given_name"
                        # If not a field name and we have a current field, this might be the value
                        elif current_field and current_field not in extracted_data:
                            # For birth_date, ensure it matches date format
                            if current_field == "birth_date":
                                if re.match(r"\d{4}-\d{2}-\d{2}", line):
                                    extracted_data["birth_date"] = line
                                    log_and_capture(f"*** Extracted {current_field} from next line: {line} ***")
                            else:
                                extracted_data[current_field] = line
                                log_and_capture(f"*** Extracted {current_field} from next line: {line} ***")
                            current_field = None
                
                # Final fallback: Try to extract directly from HTML elements if regex didn't work
                required_fields = {'given_name', 'family_name', 'birth_date'}
                missing_fields = required_fields - set(extracted_data.keys())
                
                if missing_fields:
                    log_and_capture(f"Missing fields after parsing: {missing_fields}. Trying direct element extraction.")
                    
                    try:
                        # Find list items in the dialog that contain the field data
                        list_items = dialog.find_elements(By.CSS_SELECTOR, "mat-list-item, .list-item, li")
                        log_and_capture(f"Found {len(list_items)} list items in dialog")
                        
                        for item in list_items:
                            item_text = item.text
                            log_and_capture(f"List item text: {item_text}")
                            
                            if "birth_date" in item_text.lower() and "birth_date" not in extracted_data:
                                # Get value part from item like "birth_date value: 2025-04-02 tag: 1004"
                                value_match = re.search(r"value:\s*(\d{4}-\d{2}-\d{2})", item_text)
                                if value_match:
                                    extracted_data["birth_date"] = value_match.group(1)
                                    log_and_capture(f"*** Extracted birth_date from element: {extracted_data['birth_date']} ***")
                            
                            elif "family_name" in item_text.lower() and "family_name" not in extracted_data:
                                # Try to extract based on line break or colon
                                if "\n" in item_text:
                                    parts = item_text.split("\n")
                                    if len(parts) > 1:
                                        extracted_data["family_name"] = parts[1].strip()
                                        log_and_capture(f"*** Extracted family_name from element: {extracted_data['family_name']} ***")
                            
                            elif "given_name" in item_text.lower() and "given_name" not in extracted_data:
                                # Try to extract based on line break or colon
                                if "\n" in item_text:
                                    parts = item_text.split("\n")
                                    if len(parts) > 1:
                                        extracted_data["given_name"] = parts[1].strip()
                                        log_and_capture(f"*** Extracted given_name from element: {extracted_data['given_name']} ***")
                    
                    except Exception as e:
                        log_and_capture(f"Error during element extraction: {str(e)}")
            except Exception as ex:
                log_and_capture(f"Error during dialog text extraction: {str(ex)}")
            
            # Update the request data to include the extracted information
            if extracted_data:
                log_and_capture(f"Successfully extracted {len(extracted_data)} fields: {', '.join(extracted_data.keys())}")
                
                # Initialize presentation_data if it doesn't exist
                if request_data.get("presentation_data") is None:
                    request_data["presentation_data"] = {}
                
                # Update the request_data
                request_data["status"] = "success"
                request_data["presentation_data"]["extracted_data"] = extracted_data
                request_data["presentation_data"]["dialog_html_length"] = len(dialog_content) if dialog_content else 0
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

    # Initialize Chrome with options for visibility
    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--safebrowsing-disable-auto-update")
    options.add_argument("--enable-automation")
    options.add_argument("--password-store=basic")
    options.add_argument("--headless=new")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--single-process")
    options.add_argument("--no-zygote")
    options.add_argument(f"--user-data-dir={user_data_dir}")

    # Use the system-installed chromedriver
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 10)

    try:
        # Navigate to the verifier website
        log_and_capture("Navigating to verifier website")
        driver.get("https://eudi-verifier.nieuwlaar.com/custom-request/create")

        # Generate random UUIDs for id and nonce
        request_id = str(uuid.uuid4())
        nonce = str(uuid.uuid4())
        log_and_capture(f"Generated request ID: {request_id}")
        log_and_capture(f"Generated nonce: {nonce}")

        # Prepare the JSON to be entered
        json_content = f"""{{
    "type": "vp_token",
    "presentation_definition": {{
        "id": "{request_id}",
        "input_descriptors": [
            {{
                "id": "eu.europa.ec.eudi.pid.1",
                "format": {{
                    "mso_mdoc": {{
                        "alg": [
                            "ES256"
                        ]
                    }}
                }},
                "constraints": {{
                    "limit_disclosure": "required",
                    "fields": [
                        {{
                            "path": [
                                "$['eu.europa.ec.eudi.pid.1']['family_name']"
                            ],
                            "intent_to_retain": false
                        }},
                        {{
                            "path": [
                                "$['eu.europa.ec.eudi.pid.1']['given_name']"
                            ],
                            "intent_to_retain": false
                        }},
                        {{
                            "path": [
                                "$['eu.europa.ec.eudi.pid.1']['birth_date']"
                            ],
                            "intent_to_retain": false
                        }}
                    ]
                }}
            }}
        ]
    }},
    "nonce": "{nonce}"
}}"""

        # Find the text editor and input the JSON
        log_and_capture("Inputting JSON into the editor")
        editor = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cm-content")))
        driver.execute_script("arguments[0].textContent = arguments[1]", editor, json_content)

        # Click the Next button
        log_and_capture("Clicking Next button")
        next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.primary")))
        next_button.click()

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
            "wait": WebDriverWait(driver, 60),  # Use a longer wait for later extraction
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
