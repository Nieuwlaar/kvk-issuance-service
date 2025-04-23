import requests

# Base URL for the KVK Bevoegdheden API
BASE_URL = "http://localhost:3333/api"

class KVKBevoegdhedenAPI:
    """
    Client for interacting with the KVK Bevoegdheden REST API.
    """

    @staticmethod
    def get_lpid(kvk_nummer):
        """
        Fetches the Legal Person Identification Data (LPID) details for the specified KVK number.
        
        :param kvk_nummer: The KVK number of the entity.
        :return: JSON response with LPID details.
        :raises: HTTPError if the request fails.
        """
        url = f"{BASE_URL}/lpid/{kvk_nummer}"
        response = requests.get(url)
        response.raise_for_status()  # Raises an exception for HTTP errors
        return response.json()

    @staticmethod
    def get_company_certificate(kvk_nummer):
        """
        Fetches the company certificate details for the specified KVK number.
        
        :param kvk_nummer: The KVK number of the entity.
        :return: JSON response with company certificate details.
        :raises: HTTPError if the request fails.
        """
        url = f"{BASE_URL}/company-certificate/{kvk_nummer}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def check_signatory_right(kvk_nummer, geslachtsnaam, voornamen, geboortedatum, voorvoegselGeslachtsnaam=""):
        """
        Checks if a natural person has signatory rights for the specified KVK number.

        :param kvk_nummer: The KVK number of the entity.
        :param geslachtsnaam: Surname of the person.
        :param voornamen: First names of the person.
        :param geboortedatum: Date of birth of the person (format: "DD-MM-YYYY").
        :param voorvoegselGeslachtsnaam: Prefix of the surname (optional).
        :return: JSON response indicating if the person has signatory rights.
        :raises: HTTPError if the request fails.
        """
        url = f"{BASE_URL}/signatory-rights/{kvk_nummer}"
        payload = {
            "geslachtsnaam": geslachtsnaam,
            "voornamen": voornamen,
            "geboortedatum": geboortedatum,
            "voorvoegselGeslachtsnaam": voorvoegselGeslachtsnaam
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_natural_person_company_certificate(given_name, family_name, birthdate):
        """
        Fetches company certificates associated with a natural person.
        
        :param given_name: First name(s) of the person.
        :param family_name: Last name of the person.
        :param birthdate: Date of birth in ISO format (YYYY-MM-DD).
        :return: JSON response with company certificates where the person has authorization.
        :raises: HTTPError if the request fails.
        """
        url = f"{BASE_URL}/natural-person/company-certificate"
        payload = {
            "givenName": given_name,
            "familyName": family_name,
            "birthdate": birthdate
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
