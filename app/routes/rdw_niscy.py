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
    try:
        logging.info(f"Received PID Authentication request")

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

        try:
            # Navigate to the verifier website
            logging.info("Navigating to https://eudi-verifier.nieuwlaar.com/home")
            driver.get("https://eudi-verifier.nieuwlaar.com/home")

            # It's generally better to wait for a specific element than using time.sleep
            # If you need to check something on the page, use WebDriverWait
            # For example:
            # wait = WebDriverWait(driver, 10)
            # wait.until(EC.presence_of_element_located((By.TAG_NAME, "body"))) # Wait for body tag to be present

            # Removing the sleep unless it's specifically needed for manual observation
            # logging.info("Page loaded. Pausing for 10 seconds...")
            # time.sleep(10)

            # Instead of pausing, you might want to return some confirmation or check page content
            logging.info("Successfully navigated to the verifier page.")
            return {
                "status": "success",
                "message": "Successfully navigated to the verifier URL." # Updated message
            }

        finally:
            logging.info("Closing browser.")
            driver.quit()

    except Exception as e:
        logging.error(f"Error in verify_pid_authentication: {str(e)}")
        # Log the stack trace for better debugging
        logging.exception("Stack trace:")
        raise HTTPException(status_code=500, detail=str(e))
