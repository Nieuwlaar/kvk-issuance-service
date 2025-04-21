from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status, Header, Cookie
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging
import tempfile
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
from typing import List, Optional, Dict, Any, Union
import uuid
import json
import os
from pathlib import Path
import re
from enum import Enum
import jwt
import hashlib
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Create router with prefix
router = APIRouter()
user_data_dir = tempfile.mkdtemp()

# In-memory store for active driver sessions
active_sessions = {}

# In-memory store for revoked tokens (should be replaced with a database in production)
revoked_tokens = set()

# Define the request models
class PowerOfRepresentationRequest(BaseModel):
    legal_person_identifier: str
    legal_name: str

# Define format enum for clarity (optional but recommended)
class PorFormat(str, Enum):
    MDOC = "mdoc"
    SD_JWT_VC = "sd_jwt_vc"

# Auth models
class TokenRequest(BaseModel):
    auth_id: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class TokenData(BaseModel):
    sub: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    birth_date: Optional[str] = None
    exp: Optional[int] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# OAuth2 scheme for token verification
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Helper Functions ---
def get_request_data_from_file(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve request data from the session JSON file."""
    file_path = Path("authentication-requests") / f"{session_id}.json"
    if not file_path.exists():
        logger.warning(f"No data file found for session ID: {session_id} at {file_path}")
        return None
    try:
        with open(file_path, "r") as f:
            # Handle empty file case
            content = f.read()
            if not content:
                logger.warning(f"Session file {file_path} is empty.")
                # Return a dict indicating the error state
                return {"status": "error", "error": "Empty session file", "logs": []}
            return json.loads(content)
    except json.JSONDecodeError as decode_err:
         logger.error(f"Error decoding JSON from {file_path}: {decode_err}")
         # Return a dict indicating the error state
         return {"status": "error", "error": f"Corrupted session file: {decode_err}", "logs": []}
    except Exception as e:
        logger.error(f"Error reading session data file {file_path}: {str(e)}")
        return None # Indicate general read error

def create_user_id(given_name: str, family_name: str, birth_date: str) -> str:
    """Create a consistent user ID from user attributes."""
    # Combine attributes and create a hash to use as user ID
    combined = f"{given_name}:{family_name}:{birth_date}"
    return hashlib.sha256(combined.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT token and return token data."""
    try:
        # Check if token is revoked
        if token in revoked_tokens:
            return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        # Check for token expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
            return None
            
        return TokenData(
            sub=user_id,
            given_name=payload.get("given_name"),
            family_name=payload.get("family_name"),
            birth_date=payload.get("birth_date"),
            exp=exp
        )
    except jwt.PyJWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Dependency to get the current authenticated user from a token."""
    token_data = verify_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data

# --- Auth Endpoints ---
@router.post("/auth/token", response_model=Token)
async def generate_token(request: TokenRequest):
    """Generate JWT tokens after successful PID verification."""
    # Get authentication data
    request_data = get_request_data_from_file(request.auth_id)
    
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentication session not found"
        )
        
    if request_data.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication not successful. Status: {request_data.get('status')}"
        )
        
    # Extract user data
    presentation_data = request_data.get("presentation_data", {})
    extracted_data = presentation_data.get("extracted_data", {})
    
    if not extracted_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user data extracted from authentication"
        )
        
    given_name = extracted_data.get("given_name")
    family_name = extracted_data.get("family_name")
    birth_date = extracted_data.get("birth_date")
    
    if not given_name or not family_name or not birth_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete user data in authentication"
        )
        
    # Create user ID
    user_id = create_user_id(given_name, family_name, birth_date)
    
    # Create token data
    token_data = {
        "sub": user_id,
        "given_name": given_name,
        "family_name": family_name,
        "birth_date": birth_date
    }
    
    # Generate tokens
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # in seconds
    }

@router.post("/auth/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    """Generate new access token using refresh token."""
    try:
        # Verify refresh token
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check if token is revoked
        if request.refresh_token in revoked_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
            
        # Check if it's actually a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not a valid refresh token"
            )
            
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing user ID"
            )
            
        # Create new token data (without user details as we don't have them here)
        token_data = {"sub": user_id}
        
        # Generate new tokens
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(user_id)
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # in seconds
        }
        
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/auth/validate")
async def validate_token(current_user: TokenData = Depends(get_current_user)):
    """Validate token and return user information."""
    return {
        "user_id": current_user.sub,
        "given_name": current_user.given_name,
        "family_name": current_user.family_name,
        "birth_date": current_user.birth_date,
        "exp": current_user.exp
    }

@router.post("/auth/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """Invalidate the current token."""
    # Add token to revoked list
    revoked_tokens.add(token)
    return {"detail": "Successfully logged out"}

@router.get("/user/profile")
async def get_user_profile(current_user: TokenData = Depends(get_current_user)):
    """Return the authenticated user's profile data."""
    return {
        "user_id": current_user.sub,
        "given_name": current_user.given_name,
        "family_name": current_user.family_name,
        "birth_date": current_user.birth_date
    }

@router.post("/power-of-representation")
async def create_power_of_representation(request: PowerOfRepresentationRequest, format: PorFormat = PorFormat.SD_JWT_VC):
    try:
        logging.info(f"Received Power of Representation request for: {request.legal_name} ({request.legal_person_identifier}) with format: {format.value}")
        
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
            driver.get("https://eudi-issuer.nieuwlaar.com/credential_offer_choice")
            
            # Use WebDriverWait with shorter timeouts
            wait = WebDriverWait(driver, 5)
            
            # Select Power of Representation based on the format query parameter
            if format == PorFormat.SD_JWT_VC:
                por_element_name = "eu.europa.ec.eudi.por_sd_jwt_vc"
                logging.info("Selecting SD-JWT-VC format")
            else: 
                por_element_name = "eu.europa.ec.eudi.por_mdoc"
                logging.info("Selecting mdoc format (default)")

            wait.until(EC.presence_of_element_located((By.NAME, por_element_name))).click()
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
        log_and_capture("Initializing WebDriver...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)  # Increased slightly from 15
        short_wait = WebDriverWait(driver, 10) # Increased slightly from 7

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
            short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, editor_selector)))
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
            next_button = short_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector)))
            driver.execute_script("arguments[0].click();", next_button) 
        except Exception as e:
             log_and_capture(f"JS click failed for Next button: {str(e)}. Raising error.")
             raise # Re-raise

        # Wait for the QR code page (wallet link) to load
        log_and_capture("Waiting for wallet link to appear")
        wallet_link_selector = "a[href^='eudi-openid4vp://']"
        wallet_link = short_wait.until(EC.presence_of_element_located(
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
        
        # Schedule the background task
        background_tasks.add_task(handle_pid_extraction_in_background, request_id)
        log_and_capture(f"Scheduled background task for {request_id}")

        # Prevent driver cleanup in finally block as it's needed by the background task
        driver_passed_to_bg = driver
        driver = None

        # Return initial response
        initial_response = {
            "status": "success",
            "data": {
                "id": request_id,
                "wallet_link": wallet_link,
                "extraction_endpoint": f"/pid-extraction/{request_id}"
            },
            "message": "Authentication initiated. Background task started. Poll the extraction endpoint for status.",
            "logs": log_messages
        }
        
        return initial_response

    except Exception as e:
        err_msg = f"Error in verify_pid_authentication: {str(e)}"
        logging.error(err_msg)
        logging.exception("Stack trace:") # Log full stack trace for debugging
        log_messages.append(f"ERROR: {err_msg}")
        # Ensure driver is quit if error happens *before* passing to background task
        if driver:
             try: driver.quit()
             except: pass
        raise HTTPException(status_code=500, detail={"error": str(e), "logs": log_messages})
    finally:
        # Cleanup driver only if it was NOT passed to the background task successfully
        if driver:
            try:
                log_and_capture("Cleaning up driver in finally block (error before scheduling task)")
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

async def handle_pid_extraction_in_background(request_id: str):
    """Background task to handle Selenium interaction and data extraction."""
    session_data = active_sessions.get(request_id)
    if not session_data:
        logging.error(f"[BG Task {request_id}] Session data not found in active_sessions.")
        return # Cannot proceed

    driver = session_data.get("driver")
    # Use the long wait object specifically for waiting for user interaction (results container)
    user_interaction_wait = session_data.get("wait")
    file_path_str = session_data.get("file_path")

    if not driver or not user_interaction_wait or not file_path_str:
        logging.error(f"[BG Task {request_id}] Incomplete session data (driver/wait/path missing).")
        # Attempt cleanup if session exists
        if request_id in active_sessions:
            if driver: 
                try: 
                    driver.quit()
                    logging.info(f"[BG Task {request_id}] Quitting driver due to incomplete data.") 
                except Exception: pass # Corrected here
            try: 
                del active_sessions[request_id]
                logging.info(f"[BG Task {request_id}] Deleting session due to incomplete data.") 
            except KeyError: pass # Corrected here
        return

    file_path = Path(file_path_str)
    log_messages = []
    request_data = {}

    def log_and_capture(message: str):
        logging.info(f"[BG Task {request_id}] {message}")
        log_messages.append(message)

    # Define a shorter wait for actions within the background task
    action_wait = WebDriverWait(driver, 15) # 15 seconds for element interactions

    try:
        # Load initial request data and logs from file
        try:
            with open(file_path, "r") as f:
                request_data = json.load(f)
            # Prepend existing logs
            existing_logs = request_data.get("logs", [])
            log_messages.extend(existing_logs)
            log_and_capture("Background task started.")
        except Exception as e:
            log_and_capture(f"Error reading initial session file: {e}")
            # If file read fails but we have driver, still proceed to try extraction
            if not request_data: request_data = {} # Ensure request_data is a dict

        # --- Start of Selenium Logic ---
        results_selector = "vc-presentations-results"
        log_and_capture(f"Waiting up to {user_interaction_wait._timeout}s for results container: {results_selector}")
        # Use the LONG wait here, waiting for the user + wallet interaction
        results_container = user_interaction_wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, results_selector)),
            message=f"Timeout waiting for presentation results container '{results_selector}'."
        )
        log_and_capture("Found vc-presentations-results element - presentation is complete")

        # Find the 'View Content' button (use action_wait now)
        log_and_capture("Looking for PID card's View Content button")
        view_button_xpath = "//mat-card[.//mat-card-title[contains(text(), 'eu.europa.ec.eudi.pid.1')]]//button[.//span[contains(text(), 'View Content')]]"
        view_content_button = action_wait.until(
            EC.element_to_be_clickable((By.XPATH, view_button_xpath)),
            message="Timeout waiting for 'View Content' button to be clickable."
        )
        log_and_capture("Found View Content button")

        # Click the button (JS click preferred)
        try:
            driver.execute_script("arguments[0].click();", view_content_button)
            log_and_capture("Clicked View Content button using JavaScript")
        except Exception as click_err:
            log_and_capture(f"JS click failed ({click_err}), trying regular click.")
            try:
                view_content_button.click()
                log_and_capture("Clicked View Content button (fallback)")
            except Exception as fallback_click_err:
                 log_and_capture(f"Fallback click also failed: {fallback_click_err}")
                 raise WebDriverException(f"Failed to click View Content button: {fallback_click_err}") from fallback_click_err

        # Wait for the dialog (use action_wait)
        log_and_capture("Waiting for dialog to appear")
        # More stable selector often involves specific attributes or container types
        dialog_selector = "mat-dialog-container, div[role='dialog']"
        dialog = action_wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, dialog_selector)),
            message=f"Timeout waiting for dialog with selector '{dialog_selector}'."
        )
        log_and_capture(f"Found dialog using selector: {dialog_selector}")

        # Get dialog text
        log_and_capture("Getting dialog text content")
        dialog_text = dialog.text if dialog else ""
        log_and_capture(f"Dialog Text Length: {len(dialog_text)}")

        # Extract data
        log_and_capture("Extracting data using primary regex patterns")
        extracted_data = {}
        field_patterns = {
            "birth_date": r"birth_date\s+value:\s*(\d{4}-\d{2}-\d{2})",
            "family_name": r"family_name\s*\n\s*([^\n\r]+)",
            "given_name": r"given_name\s*\n\s*([^\n\r]+)"
        }
        for field, pattern in field_patterns.items():
            match = re.search(pattern, dialog_text, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_data[field] = match.group(1).strip()
                log_and_capture(f"*** Extracted {field}: {extracted_data[field]} ***")
            else:
                 log_and_capture(f"Pattern did not match for {field}")
        # --- End of Selenium Logic ---

        # Update status based on extraction result
        required_fields = set(field_patterns.keys())
        found_fields = set(extracted_data.keys())
        if found_fields == required_fields:
            log_and_capture("Successfully extracted all required fields.")
            request_data["status"] = "success"
        else:
            missing = required_fields - found_fields
            log_and_capture(f"Extraction incomplete. Missing fields: {', '.join(missing)}")
            request_data["status"] = "extraction_incomplete"

        # Update presentation data
        if request_data.get("presentation_data") is None: request_data["presentation_data"] = {}
        request_data["presentation_data"]["extracted_data"] = extracted_data
        request_data["presentation_data"]["dialog_text_length"] = len(dialog_text)
        request_data["presentation_data"]["capture_timestamp"] = datetime.now().isoformat()
        request_data["error"] = None # Clear previous error if successful now

    except (TimeoutException, NoSuchElementException, WebDriverException) as selenium_err:
        # Handle Selenium-specific errors gracefully
        error_msg = f"Selenium error during background extraction: {str(selenium_err).splitlines()[0]}" # Get first line
        log_and_capture(error_msg)
        logging.warning(f"[BG Task {request_id}] Full Selenium error: {selenium_err}") # Log full error less verbosely
        request_data["status"] = "error"
        request_data["error"] = error_msg
        if request_data.get("presentation_data") is None: request_data["presentation_data"] = {}
        request_data["presentation_data"]["extracted_data"] = None

    except Exception as e:
        # Catch other unexpected errors
        error_msg = f"Unexpected error during background extraction: {str(e)}"
        log_and_capture(error_msg)
        logging.exception(f"[BG Task {request_id}] Stack Trace:")
        request_data["status"] = "error"
        request_data["error"] = error_msg
        if request_data.get("presentation_data") is None: request_data["presentation_data"] = {}
        request_data["presentation_data"]["extracted_data"] = None

    finally:
        log_and_capture("Background task finishing. Updating JSON and cleaning up.")
        # Update the JSON file with final status and logs
        request_data["logs"] = log_messages
        try:
            with open(file_path, "w") as f:
                json.dump(request_data, f, indent=4)
            log_and_capture(f"Successfully updated session file: {file_path}")
        except Exception as write_err:
            log_and_capture(f"ERROR updating session file {file_path}: {write_err}")
            logging.error(f"[BG Task {request_id}] Failed to write final status to {file_path}: {write_err}")

        # Cleanup: Quit driver and remove session
        if driver:
            try:
                driver.quit()
                log_and_capture("Driver quit successfully.")
            except Exception as quit_err:
                log_and_capture(f"Error quitting driver: {quit_err}")
        if request_id in active_sessions:
            try:
                del active_sessions[request_id]
                log_and_capture("Removed session from active_sessions.")
            except KeyError:
                 log_and_capture("Session already removed from active_sessions.")

@router.get("/authentication-requests/{session_id}", response_model=Optional[Dict[str, Any]])
async def get_authentication_request_file(session_id: str):
    """Retrieves the full content of a specific authentication request JSON file."""
    logger.info(f"Attempting to retrieve authentication request file for session: {session_id}")
    
    request_data = get_request_data_from_file(session_id)
    
    if request_data is None:
        # This covers file not found or general read errors (logged in helper)
        logger.warning(f"Request file for session {session_id} not found or unreadable.")
        raise HTTPException(
            status_code=404,
            detail=f"Authentication request file not found or unreadable for session ID: {session_id}"
        )
        
    # If the helper returned an error dict (e.g., for empty/corrupted file), return it directly.
    # FastAPI will serialize this dict to JSON.
    logger.info(f"Successfully retrieved request file content for session {session_id}. Status in file: {request_data.get('status', 'N/A')}")
    return request_data

