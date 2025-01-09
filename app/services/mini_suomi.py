import requests
import logging
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import jwt
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

def generate_credential_jwt(credential_type: str, payload: Dict[str, Any]) -> str:
    try:
        # Common JWT header
        header = {
            "typ": "sd-jwt",
            "alg": "ES256",
            "kid": "mini-suomi-signer-key-1"
        }

        # Add type-specific claims
        if credential_type == "LPIDSdJwt":
            jwt_payload = {
                "iss": payload["issuer_id"],
                "sub": payload["legal_person_id"],
                "iat": int(datetime.strptime(payload["issuance_date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()),
                "exp": int(datetime.strptime(payload["expire_date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()),
                "vc": {
                    "type": ["VerifiableCredential", "LegalPersonIdentifier"],
                    "credentialSubject": {
                        "legal_person_id": payload["legal_person_id"],
                        "legal_person_name": payload["legal_person_name"],
                        "issuer_id": payload["issuer_id"],
                        "issuer_name": payload["issuer_name"],
                        "issuer_country": payload["issuer_country"],
                        "credential_status": payload["credential_status"],
                        "authentic_source_id": payload["authentic_source_id"],
                        "authentic_source_name": payload["authentic_source_name"]
                    }
                }
            }
        elif credential_type == "EUCCSdJwt":
            jwt_payload = {
                "iss": payload["issuer_id"],
                "sub": payload["legalIdentifier"],
                "iat": int(datetime.strptime(payload["issuance_date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()),
                "exp": int(datetime.strptime(payload["expire_date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()),
                "vc": {
                    "type": ["VerifiableCredential", "EuropeanCompanyCertificate"],
                    "credentialSubject": {
                        "legalName": payload["legalName"],
                        "legalFormType": payload["legalFormType"],
                        "legalIdentifier": payload["legalIdentifier"],
                        "registeredAddress": payload["registeredAddress"],
                        "postalAddress": payload["postalAddress"],
                        "registrationDate": payload["registrationDate"],
                        "legalEntityStatus": payload["legalEntityStatus"],
                        "legalRepresentative": payload["legalRepresentative"],
                        "legalEntityActivity": payload["legalEntityActivity"],
                        "contactPoint": payload["contactPoint"],
                        "issuer_id": payload["issuer_id"],
                        "issuer_name": payload["issuer_name"],
                        "issuer_country": payload["issuer_country"]
                    }
                }
            }
        else:
            raise ValueError(f"Unsupported credential type: {credential_type}")

        # TODO: Replace with actual private key
        # For now, using a mock private key for demonstration
        mock_private_key = "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgkAP+MAxRTy4F77xl+9unD+9IWfneEMC7j6E4WdSEdxKhRANCAAS+JnDf0fnT3FG9lw0e0bDyLEV57FoXgtrVlAtlRZNRS8nTdaNC0AHT09cL/tG+GATbJkKXF835iColIYcuNjF"

        # Generate the JWT
        credential_jwt = jwt.encode(
            payload=jwt_payload,
            key=mock_private_key,
            algorithm="ES256",
            headers=header
        )

        return credential_jwt

    except Exception as e:
        logging.error(f"Error generating credential JWT: {str(e)}")
        raise

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

        # Generate JWT using the payload
        credential_jwt = generate_credential_jwt(credentialConfiguration, payload)

        # Construct the credential offer URL
        offer_id = "mockOfferId123"  # Generate a unique ID if necessary
        credential_offer_url = f"{ISSUER_DOMAIN}/mini-suomi/credential_offer?id={offer_id}"

        # Construct the credential offer URI
        credential_offer_uri = f"openid-credential-offer://?credential_offer_uri={requests.utils.quote(credential_offer_url)}"

        return {"credential_offer_uri": credential_offer_uri}

    except Exception as e:
        logger.error(f"Error in issue_credential: {str(e)}")
        raise


