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
                # Look for the mat-panel-title element within the expansion panel
                pid_element_xpath = "//mat-panel-title[contains(normalize-space(), 'Person Identification Data (PID)')]"
                pid_button = wait.until(EC.element_to_be_clickable((By.XPATH, pid_element_xpath)))
                log_and_capture("Found PID panel")
                pid_button.click()
                log_and_capture("Expanding PID panel")
                
                # Wait for the panel to expand and be fully rendered
                time.sleep(1)
                
                # Verify the panel is expanded
                expanded_panel = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//mat-expansion-panel-header[contains(@class, 'mat-expanded')]")
                    )
                )
                log_and_capture("PID panel expanded successfully")
                
                # 2. Click the "attributes by" select dropdown
                attributes_select = wait.until(
                    EC.element_to_be_clickable((By.ID, "mat-select-0"))
                )
                attributes_select.click()
                log_and_capture("Opened attributes dropdown")
                
                # Wait for the options to appear
                time.sleep(0.5)
                
                # Click the "Specific attributes" option in the dropdown
                specific_attrs_option = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//mat-option[contains(normalize-space(), 'Specific attributes')]")
                    )
                )
                specific_attrs_option.click()
                log_and_capture("Selected 'Specific attributes' option")
                
                # Wait for the selection to be applied
                time.sleep(0.5)
                
                # 3. Click the "format" select dropdown
                format_select = wait.until(
                    EC.element_to_be_clickable((By.ID, "mat-select-1"))
                )
                format_select.click()
                log_and_capture("Opened format dropdown")
                
                # Wait for the options to appear
                time.sleep(0.5)
                
                # Click the "mso_mdoc" option in the dropdown
                mso_mdoc_option = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//mat-option[contains(normalize-space(), 'mso_mdoc')]")
                    )
                )
                mso_mdoc_option.click()
                log_and_capture("Selected 'mso_mdoc' format")
                
                # 4. Click the "Next" button
                next_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "button.mat-stepper-next")
                    )
                )
                next_button.click()
                log_and_capture("Clicked Next button to proceed")
                
                # 5. Click the "Select Attributes" button
                select_attrs_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "button[matbadgecolor='accent']")
                    )
                )
                select_attrs_button.click()
                log_and_capture("Opened attribute selection dialog")
                
                # Wait for dialog to appear and be fully loaded
                time.sleep(1)
                
                # Verify dialog is present
                dialog = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "mat-dialog-container")
                    )
                )
                log_and_capture("Dialog container found")
                
                # 6. Select the required checkboxes
                try:
                    # Find checkboxes by their labels within the dialog
                    checkbox_selectors = [
                        "//mat-checkbox[.//label[contains(text(), 'Family name')]]",
                        "//mat-checkbox[.//label[contains(text(), 'Given name')]]",
                        "//mat-checkbox[.//label[contains(text(), 'Birthdate')]]"
                    ]
                    
                    for selector in checkbox_selectors:
                        checkbox = wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        # Click the actual input element inside the checkbox
                        input_element = checkbox.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        if not input_element.is_selected():
                            input_element.click()
                            log_and_capture(f"Clicked checkbox: {selector}")
                            # Add a small delay after each click
                            time.sleep(1)
                        else:
                            log_and_capture(f"Checkbox already selected: {selector}")
                        
                        # Log the current state of the checkbox
                        log_and_capture(f"Checkbox state after click: {input_element.is_selected()}")
                    
                    # Wait longer for dialog to stabilize after checkbox selections
                    time.sleep(2)
                    
                    # Verify dialog is still present and visible
                    dialog = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "mat-dialog-container")
                        )
                    )
                    if not dialog.is_displayed():
                        raise Exception("Dialog is not visible after checkbox selections")
                    
                    # Find the Select button with the badge
                    select_button = wait.until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button.mat-badge-accent")
                        )
                    )
                    log_and_capture("Found Select button with badge")
                    
                    # Get the badge that's actually showing the count
                    badge = select_button.find_element(By.CSS_SELECTOR, ".mat-badge-content")
                    badge_text = badge.text.strip()
                    log_and_capture(f"Select button badge text content: '{badge_text}'")
                    
                    # Verify the badge count
                    if not badge_text.isdigit():
                        raise Exception(f"Badge text '{badge_text}' is not a valid number")
                    
                    badge_count = int(badge_text)
                    if badge_count != 3:
                        raise Exception(f"Expected 3 selected items, but badge shows {badge_count}")
                    
                    log_and_capture("Verified badge count is 3")
                    
                    # Try multiple approaches to click the button
                    try:
                        # First try regular click
                        select_button.click()
                    except:
                        try:
                            # Try JavaScript click
                            driver.execute_script("arguments[0].click();", select_button)
                        except:
                            try:
                                # Try ActionChains click
                                from selenium.webdriver.common.action_chains import ActionChains
                                ActionChains(driver).move_to_element(select_button).click().perform()
                            except Exception as e:
                                raise Exception(f"All click attempts failed: {str(e)}")
                    
                    log_and_capture("Clicked Select button to confirm attribute selection")
                    
                except Exception as e:
                    log_and_capture(f"Error during dialog interaction: {str(e)}")
                    # Log dialog state
                    try:
                        dialog_html = dialog.get_attribute('outerHTML')
                        log_and_capture(f"Dialog HTML: {dialog_html}")
                    except:
                        log_and_capture("Could not get dialog HTML")
                    raise

            except Exception as e:
                log_and_capture(f"Error in interaction: {str(e)}")
                # Log more details about the current state
                log_and_capture(f"Current page source: {driver.page_source[:1000]}...")
                try:
                    # Look for any elements in the expanded panel
                    elements = driver.find_elements(
                        By.XPATH,
                        "//mat-expansion-panel[.//mat-panel-title[contains(text(), 'Person Identification Data (PID)')]]//div[contains(@class, 'mat-expansion-panel-content')]//*"
                    )
                    for elem in elements:
                        log_and_capture(f"Found element: {elem.get_attribute('outerHTML')}")
                except:
                    log_and_capture("Could not list available elements")
                raise

            log_and_capture("All interaction steps completed successfully")
            return {
                "status": "success",
                "message": "Successfully performed interaction steps.",
                "logs": log_messages
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
