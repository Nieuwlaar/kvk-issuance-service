import requests
import logging
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
from jwt import JWT, jwk_from_dict
from jwt.utils import get_int_from_datetime
from typing import Dict, Any

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
    """
    Generate a JWT credential based on the credential type and KVK number.
    Uses KVK API to fetch required data.
    """
    try:
        # Create a JWT instance
        instance = JWT()
        
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)

        # Get data from KVK API based on credential type
        if credential_type == "LPIDSdJwt":
            lpid_data = KVKBevoegdhedenAPI.get_lpid(kvk_number)
            
            jwt_payload = {
                "iss": lpid_data["metadata"]["issuer_id"],
                "sub": lpid_data["data"]["id"],
                "iat": int(now.timestamp()),
                "exp": int(one_year_from_now.timestamp()),
                "vc": {
                    "type": ["VerifiableCredential", "LegalPersonIdentifier"],
                    "credentialSubject": {
                        "legal_person_id": lpid_data["data"]["id"],
                        "legal_person_name": lpid_data["data"]["legal_person_name"],
                        "issuer_id": lpid_data["metadata"]["issuer_id"],
                        "issuer_name": lpid_data["metadata"]["issuing_authority_name"],
                        "issuer_country": lpid_data["metadata"]["issuing_country"],
                        "credential_status": "active",
                        "authentic_source_id": lpid_data["metadata"]["issuer_id"],
                        "authentic_source_name": lpid_data["metadata"]["issuing_authority_name"]
                    }
                }
            }

        elif credential_type == "EUCCSdJwt":
            company_data = KVKBevoegdhedenAPI.get_company_certificate(kvk_number)
            
            # Process legal representatives
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

            # Process address
            address_parts = company_data["data"]["postal_address"].split()
            postal_code = next((part for part in address_parts if len(part) == 6 and part[:4].isdigit()), "")
            
            jwt_payload = {
                "iss": company_data["metadata"]["issuer_id"],
                "sub": company_data["data"]["id"],
                "iat": int(now.timestamp()),
                "exp": int(one_year_from_now.timestamp()),
                "vc": {
                    "type": ["VerifiableCredential", "EuropeanCompanyCertificate"],
                    "credentialSubject": {
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
                        "registrationDate": datetime.strptime(
                            company_data["data"]["date_of_registration"], 
                            "%d-%m-%Y"
                        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "legalEntityStatus": "active",
                        "legalRepresentative": legal_representatives,
                        "legalEntityActivity": [{"code": "", "businessDescription": ""}],
                        "contactPoint": {
                            "contactPage": "",
                            "hasEmail": company_data["data"]["electronic_address"],
                            "hasTelephone": ""
                        }
                    }
                }
            }
        else:
            raise ValueError(f"Unsupported credential type: {credential_type}")

        # Common JWT header
        header = {
            "typ": "sd-jwt",
            "alg": "ES256",
            "kid": "mini-suomi-signer-key-1"
        }

        # TODO: Replace with actual private key
        # For now, using a mock key (you'll need to replace this with your actual key)
        mock_private_key = {
            "kty": "EC",
            "d": "your-private-key-here",
            "crv": "P-256",
            "x": "your-public-x-coordinate",
            "y": "your-public-y-coordinate"
        }

        signing_key = jwk_from_dict(mock_private_key)

        # Generate the JWT
        credential_jwt = instance.encode(
            header,
            jwt_payload,
            signing_key
        )

        return credential_jwt

    except Exception as e:
        logging.error(f"Error generating credential JWT: {str(e)}")
        raise


