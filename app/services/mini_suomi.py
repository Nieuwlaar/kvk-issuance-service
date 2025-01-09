import requests
import logging
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from typing import Dict, Any
from jose import jwt
import hashlib
import json
import base64

# Load environment variables
load_dotenv()

# Get ISSUER_DOMAIN based on environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
ISSUER_DOMAIN = os.getenv('PROD_DOMAIN') if ENVIRONMENT == "production" else os.getenv('DEV_DOMAIN')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# def test_get_issuers():
#     url = f"{BASE_URL}/issuers"
#     response = requests.get(url)
#     assert response.status_code == 200
#     issuers = response.json()
#     return issuers

def issue_credential(credentialConfiguration: str, kvkNumber: str):
    print(f"credentialConfiguration: {credentialConfiguration}")
    try:
        # Get LPID or company data based on credential configuration
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)
        
        if credentialConfiguration == "LPIDSdJwt":
            lpid_data = KVKBevoegdhedenAPI.get_lpid(kvkNumber)
            payload = {
                "legal_person_id": lpid_data["data"]["id"],
                "legal_person_name": lpid_data["data"]["legal_person_name"],
                "issuer_id": lpid_data["metadata"]["issuer_id"],
                "issuer_name": lpid_data["metadata"]["issuing_authority_name"],
                "issuer_country": lpid_data["metadata"]["issuing_country"],
                "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "expire_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "credential_status": "active",
                "authentic_source_id": lpid_data["metadata"]["issuer_id"],
                "authentic_source_name": lpid_data["metadata"]["issuing_authority_name"]
            }
        elif credentialConfiguration == "EUCCSdJwt":
            company_data = KVKBevoegdhedenAPI.get_company_certificate(kvkNumber)
            legal_representatives = [
                {
                    "role": "J",
                    "legalEntityId": company_data["data"]["registration_number"],
                    "scopeOfRepresentation": "Jointly",
                    "family_name": person["full_name"].split()[-1],
                    "given_name": " ".join(person["full_name"].split()[:-1]),
                    "birth_date": datetime.strptime(person["date_of_birth"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                }
                for person in company_data["data"]["authorized_persons"]
            ]
            address_parts = company_data["data"]["postal_address"].split()
            postal_code = next((part for part in address_parts if len(part) == 6 and part[:4].isdigit()), "")
            
            payload = {
                "legalName": company_data["data"]["legal_person_name"],
                "legalFormType": company_data["data"]["legal_form"],
                "legalIdentifier": company_data["data"]["id"],
                "registeredAddress": {
                    "post_code": postal_code,
                    "post_name": address_parts[-1] if address_parts else "",
                    "thoroughfare": " ".join(address_parts[:-1]) if address_parts else ""
                },
                "postalAddress": {
                    "post_code": postal_code,
                    "post_name": address_parts[-1] if address_parts else "",
                    "thoroughfare": " ".join(address_parts[:-1]) if address_parts else ""
                },
                "registrationDate": datetime.strptime(company_data["data"]["date_of_registration"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "legalEntityStatus": "active",
                "legalRepresentative": legal_representatives,
                "legalEntityActivity": [{"code": "", "businessDescription": ""}],
                "contactPoint": {
                    "contactPage": "",
                    "hasEmail": company_data["data"]["electronic_address"],
                    "hasTelephone": ""
                },
                "issuer_id": company_data["metadata"]["issuer_id"],
                "issuer_name": company_data["metadata"]["issuing_authority_name"],
                "issuer_country": company_data["metadata"]["issuing_country"],
                "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "expire_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "authentic_source_id": company_data["metadata"]["issuer_id"],
                "authentic_source_name": company_data["metadata"]["issuing_authority_name"]
            }
        else:
            raise ValueError(f"Unsupported credential configuration: {credentialConfiguration}")

        # Construct the credential offer URL (this can point to an internal or mock endpoint)
        offer_id = "mockOfferId123"  # Generate a unique ID if necessary
        credential_offer_url = f"{ISSUER_DOMAIN}/mini-suomi/credential_offer?id={offer_id}"

        # Construct the credential offer URI
        credential_offer_uri = f"openid-credential-offer://?credential_offer_uri={requests.utils.quote(credential_offer_url)}"

        # Return the credential offer URI
        return {"credential_offer_uri": credential_offer_uri}

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise Exception(f"Request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

def generate_credential_jwt(credential_type: str, kvk_number: str) -> str:
    try:
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)

        if credential_type == "LPIDSdJwt":
            lpid_data = KVKBevoegdhedenAPI.get_lpid(kvk_number)
            
            # Create disclosures for each claim
            disclosures = {
                "legal_person_id": lpid_data["data"]["id"],
                "legal_person_name": lpid_data["data"]["legal_person_name"],
                "issuer_id": lpid_data["metadata"]["issuer_id"],
                "issuer_name": lpid_data["metadata"]["issuing_authority_name"],
                "issuer_country": lpid_data["metadata"]["issuing_country"],
                "issuance_date": None,
                "expire_date": None,
                "credential_status": "active",
                "authentic_source_id": lpid_data["metadata"]["issuer_id"],
                "authentic_source_name": lpid_data["metadata"]["issuing_authority_name"]
            }

            # Generate _sd array using SHA-256 hashes of the disclosures
            sd_hashes = []
            for key, value in disclosures.items():
                disclosure_data = json.dumps(value, separators=(',', ':'))
                hash_obj = hashlib.sha256(disclosure_data.encode('utf-8'))
                sd_hashes.append(base64.urlsafe_b64encode(hash_obj.digest()).decode('utf-8').rstrip('='))

            # JWT header with embedded JWK
            headers = {
                "alg": "ES256",
                "typ": "vc+sd-jwt",
                "kid": "authentication-key",
                "jwk": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                    "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                    "alg": "ES256",
                    "kid": "authentication-key",
                    "use": "sig"
                }
            }

            # Generate a random key pair for holder binding
            holder_key = {
                "kty": "EC",
                "x": "rYmxB0Pftb6Vg2hqDw5bt9ZmunVU8cr5Q0YAKlkIXmQ",
                "y": "QkAPrZ5JQUPBKnodOefFDJRYu54hk-6toTFngyEAEP8",
                "crv": "P-256",
                "kid": "authentication-key",
                "alg": "ES256"
            }

            # JWT payload
            jwt_payload = {
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()) - 2963,  # Current time minus ~49 minutes
                "vct": "LPID",
                "iss": "https://test.minisuomi.fi/api/issuers/kvk",
                "_sd": sd_hashes,
                "_sd_alg": "sha-256",
                "cnf": {
                    "jwk": holder_key
                },
                "termsOfUse": []
            }

            # Hardcoded private key for signing
            private_key = {
                "kty": "EC",
                "crv": "P-256",
                "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                "alg": "ES256",
                "kid": "authentication-key",
                "d": "kAP-MAxRTy4F77xl-9unD-9IWfneEMC7j6E4WdSEdxI",
                "use": "sig"
            }

            # Generate the JWT
            credential_jwt = jwt.encode(
                claims=jwt_payload,
                key=private_key,
                algorithm="ES256",
                headers=headers
            )

            # Log the components
            logging.info("=== SD-JWT Generation Details ===")
            logging.info(f"Headers: {headers}")
            logging.info(f"Payload: {jwt_payload}")
            logging.info(f"Disclosures: {disclosures}")
            logging.info(f"Generated JWT: {credential_jwt}")

            return credential_jwt

    except Exception as e:
        logging.error(f"Error generating credential JWT: {str(e)}")
        raise


