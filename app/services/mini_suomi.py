import requests
import logging
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI
from datetime import datetime, timedelta
import json

BASE_URL = "https://test.minisuomi.fi/api"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_get_issuers():
    url = f"{BASE_URL}/issuers"
    response = requests.get(url)
    assert response.status_code == 200
    issuers = response.json()
    return issuers

def issue_credential(credentialConfiguration: str, kvkNumber: str):
    try:
        # Get LPID data
        lpid_data = KVKBevoegdhedenAPI.get_lpid(kvkNumber)
        
        url = f"{BASE_URL}/issuers/kvk/openid4vci/issue/{credentialConfiguration}"
        
        # Generate timestamps
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)
        
        params = {
            "useCredentialOfferUri": "true",
            "validFrom": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "validTo": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }
        
        if credentialConfiguration == "LPIDSdJwt":
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
            
            # Parse and format authorized persons
            legal_representatives = []
            for person in company_data["data"]["authorized_persons"]:
                name_parts = person["full_name"].split()
                legal_representatives.append({
                    "role": "J",  # Default role as we don't have this info
                    "legalEntityId": company_data["data"]["registration_number"],
                    "scopeOfRepresentation": "Jointly",  # Default value
                    "family_name": name_parts[-1],
                    "given_name": " ".join(name_parts[:-1]),
                    "birth_date": datetime.strptime(person["date_of_birth"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                })

            # Parse address
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

        response = requests.post(url, params=params, json=payload)
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Error from minisuomi API: {response.text}")
            raise Exception(f"API returned status code {response.status_code}")
        
        # Return the credential offer URI directly
        return {"credential_offer_uri": response.text}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise Exception(f"Request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

