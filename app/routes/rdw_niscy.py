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

    try:
        log_and_capture(f"Received PID Authentication request")

        # Initialize Chrome with options for visibility
        options = webdriver.ChromeOptions()
        # Use the same binary location as the working endpoint
        options.binary_location = "/usr/bin/chromium"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Add missing options from the working endpoint
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        # Remove the user data dir argument if not strictly needed,
        # or ensure it's handled correctly (like in the working endpoint)
        # options.add_argument(f"--user-data-dir={user_data_dir}") # Re-add if needed, potentially using the same global 'user_data_dir'
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--enable-automation")
        options.add_argument("--password-store=basic")
        # Add headless mode and other potentially important flags from the working endpoint
        options.add_argument("--headless=new") # Add headless mode
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        # Add the user data directory from the working endpoint
        options.add_argument(f"--user-data-dir={user_data_dir}")


        # Use the system-installed chromedriver explicitly like in the working endpoint
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        # Increase wait time slightly for potentially slower interactions
        wait = WebDriverWait(driver, 10)

        try:
            # Navigate to the verifier website
            nav_msg = "Navigating to https://eudi-verifier.nieuwlaar.com/home"
            log_and_capture(nav_msg)
            driver.get("https://eudi-verifier.nieuwlaar.com/home")
            log_and_capture("Navigation complete.")

            # --- Interaction Steps ---

            # 1. Click "Person Identification Data (PID)"
            try:
                # Look for the mat-panel-title element
                pid_element_xpath = "//mat-panel-title[contains(normalize-space(), 'Person Identification Data (PID)')]"
                pid_button = wait.until(EC.element_to_be_clickable((By.XPATH, pid_element_xpath)))
                log_and_capture("Found PID panel title")
                pid_button.click()
                log_and_capture("Clicked PID panel")
                
                # Wait a moment for panel expansion
                time.sleep(0.5)
                
                # 2. Click the "Specific attributes" option
                specific_attrs_xpath = "//span[contains(@class, 'mdc-list-item__primary-text') and contains(text(), 'Specific attributes')]"
                specific_attrs = wait.until(EC.element_to_be_clickable((By.XPATH, specific_attrs_xpath)))
                log_and_capture("Found 'Specific attributes' option")
                specific_attrs.click()
                log_and_capture("Clicked 'Specific attributes' option")
                
            except Exception as e:
                log_and_capture(f"Error in initial interaction: {str(e)}")
                log_and_capture(f"Current page source: {driver.page_source[:500]}...")  # Log first 500 chars of page source
                raise

            # 3. Choose the "mso_mdoc" format
            #    Assuming a radio button with value 'mso_mdoc'. Adjust selector if needed.
            try:
                mso_mdoc_radio_selector = "input[type='radio'][value='mso_mdoc']"
                mso_mdoc_radio = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, mso_mdoc_radio_selector)))
                # Scroll into view if necessary, then click
                driver.execute_script("arguments[0].scrollIntoView(true);", mso_mdoc_radio)
                time.sleep(0.2) # Small pause after scroll before click
                if not mso_mdoc_radio.is_selected():
                    mso_mdoc_radio.click()
                    log_and_capture("Selected format: mso_mdoc")
                else:
                    log_and_capture("Format mso_mdoc already selected.")
            except Exception as e:
                log_and_capture(f"Error selecting mso_mdoc format: {e}")
                raise

            # 4. Click a submit button (if applicable)
            #    Assuming a generic submit button. Adjust selector if needed.
            try:
                # Try finding a submit button first
                submit_button_selector = "input[type='submit'], button[type='submit']"
                submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, submit_button_selector)))
                log_and_capture("Found submit button.")
                 # Scroll into view if necessary, then click
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(0.2) # Small pause after scroll before click
                submit_button.click()
                log_and_capture("Clicked submit button.")
                # Optional: Wait for next page/element after submission if needed
                # wait.until(...)
            except Exception as e:
                # It's possible there isn't an explicit submit button for this flow
                log_and_capture(f"Could not find or click a submit button (maybe not needed?): {e}")
                # Decide if this should raise an error or just be logged


            log_and_capture("Interaction steps completed.")
            return {
                "status": "success",
                "message": "Successfully performed interaction steps.",
                "logs": log_messages # Return the captured logs
            }

        finally:
            log_and_capture("Closing browser.") # Capture this log too
            driver.quit()

    except Exception as e:
        err_msg = f"Error in verify_pid_authentication: {str(e)}"
        logging.error(err_msg)
        logging.exception("Stack trace:")
        # Add the final error to the logs if possible
        log_messages.append(f"ERROR: {err_msg}")
        # Return logs captured so far along with the error
        raise HTTPException(status_code=500, detail={"error": str(e), "logs": log_messages})
