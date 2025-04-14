from datetime import datetime
from fastapi import APIRouter, HTTPException
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

# Create router with prefix
router = APIRouter()
user_data_dir = tempfile.mkdtemp()

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
        
        # Return initial response with QR code
        initial_response = {
            "status": "success",
            "data": {
                "id": request_id,
                "wallet_link": wallet_link
            },
            "logs": log_messages
        }

        # Start a background task to monitor the presentation results
        async def monitor_presentation_results():
            try:
                log_and_capture("Starting to monitor for presentation results")
                
                # Wait for the presentation results to appear with a longer timeout
                log_and_capture("Waiting for vc-presentations-results element")
                wait = WebDriverWait(driver, 120)  # Increased timeout to 120 seconds
                
                try:
                    # First try to find the results container
                    log_and_capture("Attempting to find results container")
                    results_container = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "vc-presentations-results"))
                    )
                    log_and_capture("Found vc-presentations-results element")
                    
                    # Log the current page source for debugging
                    log_and_capture("Current page source:")
                    log_and_capture(driver.page_source)
                    
                    try:
                        # Find the mat-card containing the PID credential
                        log_and_capture("Looking for PID card")
                        pid_card = wait.until(
                            EC.presence_of_element_located((By.XPATH, "//mat-card[.//mat-card-title[contains(text(), 'eu.europa.ec.eudi.pid.1')]]"))
                        )
                        log_and_capture(f"Found PID card: {pid_card.get_attribute('outerHTML')}")
                        
                        # Find and click the View Content button
                        log_and_capture("Looking for View Content button")
                        view_content_button = pid_card.find_element(By.CSS_SELECTOR, "button.mdc-button--outlined span.mdc-button__label")
                        log_and_capture(f"Found View Content button: {view_content_button.get_attribute('outerHTML')}")
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
                                log_and_capture(f"Failed to find dialog with selector {selector[1]}: {str(e)}")
                                continue
                        
                        if not dialog:
                            raise Exception("Dialog not found with any of the selectors")
                        
                        # Get the dialog content
                        log_and_capture("Getting dialog content")
                        dialog_content = dialog.get_attribute('innerHTML')
                        log_and_capture(f"Dialog content: {dialog_content}")
                        
                        # Try to find the data elements in the dialog
                        log_and_capture("Extracting data from dialog")
                        data_selectors = [
                            ".//div[contains(@class, 'data-row')]",
                            ".//div[contains(@class, 'field')]",
                            ".//div[contains(@class, 'value')]",
                            ".//div[contains(@class, 'content')]",
                            ".//div[contains(@class, 'item')]"
                        ]
                        
                        extracted_data = {}
                        for selector in data_selectors:
                            try:
                                log_and_capture(f"Trying data selector: {selector}")
                                data_elements = dialog.find_elements(By.XPATH, selector)
                                if data_elements:
                                    log_and_capture(f"Found {len(data_elements)} data elements using selector: {selector}")
                                    for element in data_elements:
                                        try:
                                            text = element.text.strip()
                                            if text:
                                                if ':' in text:
                                                    key, value = text.split(':', 1)
                                                    extracted_data[key.strip()] = value.strip()
                                                    log_and_capture(f"Extracted key-value pair: {key.strip()} = {value.strip()}")
                                                else:
                                                    extracted_data[text] = True
                                                    log_and_capture(f"Extracted value: {text}")
                                        except Exception as e:
                                            log_and_capture(f"Error processing element: {str(e)}")
                                            continue
                                    if extracted_data:
                                        break
                            except Exception as e:
                                log_and_capture(f"Error with selector {selector}: {str(e)}")
                                continue
                        
                        log_and_capture(f"Final extracted data: {extracted_data}")
                        
                        # Update the JSON file with the extracted data and logs
                        request_data["status"] = "success"
                        request_data["presentation_data"] = {
                            "extracted_data": extracted_data,
                            "dialog_html": dialog_content,
                            "capture_timestamp": datetime.now().isoformat()
                        }
                        request_data["logs"] = log_messages
                        
                        # Save the final state
                        log_and_capture("Saving final state to JSON file")
                        with open(file_path, "w") as f:
                            json.dump(request_data, f, indent=4)
                        log_and_capture("Successfully saved final state")
                        
                    except Exception as e:
                        log_and_capture(f"Error during data extraction: {str(e)}")
                        request_data["status"] = "error"
                        request_data["error"] = {
                            "message": str(e),
                            "type": type(e).__name__,
                            "timestamp": datetime.now().isoformat()
                        }
                        request_data["logs"] = log_messages
                        try:
                            page_source = driver.page_source
                            request_data["presentation_data"] = {
                                "page_source": page_source,
                                "error": str(e),
                                "capture_timestamp": datetime.now().isoformat()
                            }
                            with open(file_path, "w") as f:
                                json.dump(request_data, f, indent=4)
                        except Exception as page_source_error:
                            log_and_capture(f"Error capturing page source: {str(page_source_error)}")
                    
                except Exception as e:
                    log_and_capture(f"Error during data capture: {str(e)}")
                    try:
                        page_source = driver.page_source
                        request_data["presentation_data"] = {
                            "page_source": page_source,
                            "error": str(e),
                            "capture_timestamp": datetime.now().isoformat()
                        }
                        request_data["logs"] = log_messages
                        with open(file_path, "w") as f:
                            json.dump(request_data, f, indent=4)
                    except:
                        pass
                    raise
                
            except Exception as e:
                log_and_capture(f"Error monitoring presentation results: {str(e)}")
                request_data["status"] = "error"
                request_data["error"] = str(e)
                request_data["logs"] = log_messages
                with open(file_path, "w") as f:
                    json.dump(request_data, f, indent=4)
            finally:
                try:
                    log_and_capture("Cleaning up and closing browser")
                    driver.quit()
                except Exception as e:
                    log_and_capture(f"Error closing browser: {str(e)}")

        # Start the monitoring task
        import asyncio
        asyncio.create_task(monitor_presentation_results())
        
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
