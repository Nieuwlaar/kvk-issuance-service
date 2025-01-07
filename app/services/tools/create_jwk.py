import base64
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def base64url_encode(data):
    """Encodes data to Base64Url format."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def generate_jwk_from_private_key(private_key_path):
    """Generates a JWK from a private key."""
    # Load private key
    with open(private_key_path, "rb") as f:
        private_key = load_pem_private_key(f.read(), password=None)

    # Get the public key numbers
    public_numbers = private_key.public_key().public_numbers()

    # Extract x and y as Base64Url
    x = base64url_encode(public_numbers.x.to_bytes(32, "big"))
    y = base64url_encode(public_numbers.y.to_bytes(32, "big"))

    # Create JWK
    jwk = {
        "kty": "EC",  # Key Type
        "crv": "P-256",  # Curve
        "x": x,  # X coordinate
        "y": y,  # Y coordinate
        "alg": "ES256",  # Algorithm
        "kid": "authentication-key"  # Key ID (optional, can be customized)
    }

    return jwk

# Example Usage
private_key_path = "private_key.pem"
jwk = generate_jwk_from_private_key(private_key_path)
print("Generated JWK:")
print(jwk)
