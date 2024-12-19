# Succesvolle registratie:
# 
# {
# "publicKey": {
#   "kty": "EC",
#   "crv": "P-521",
#   "x": "AWgbPodyJKFHtlD8WsqErQn8dIWpBjfMiCPQ3SrSY2G0JLUxLLihRb8ruH7GFRs7YlfPYK2DMmtAicuJAJZA0a3F",
#   "y": "AZtfo3AAE0JndwvmoxFsldLzIGZ1d4YVrmkLVQFUJZzP2oT_z3ojoUWB0Q9iwzIhIVlQTOnY5Xi-xWMRBOVQW3gB",
#   "use": "sig"
# },
# "privateKey": {
#   "kty": "EC",
#   "crv": "P-521",
#   "x": "AWgbPodyJKFHtlD8WsqErQn8dIWpBjfMiCPQ3SrSY2G0JLUxLLihRb8ruH7GFRs7YlfPYK2DMmtAicuJAJZA0a3F",
#   "y": "AZtfo3AAE0JndwvmoxFsldLzIGZ1d4YVrmkLVQFUJZzP2oT_z3ojoUWB0Q9iwzIhIVlQTOnY5Xi-xWMRBOVQW3gB",
#   "use": "sig",
#   "d": "AcT2WOnoT5a0pj5wOMbW3FEP8ArJbeXT7h4mYohOvIz_QdIk30xquNfR5rPdbY08RYki2y8vcXmhHj32FITzTXpa"
# }
# }



from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64
import json

def to_base64_url(data):
    """Convert bytes to base64-url-encoded string."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def generate_ec_key_pair():
    # Generate a private key using P-256 curve
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Extract private numbers
    private_numbers = private_key.private_numbers()
    public_numbers = private_numbers.public_numbers

    # Convert key parts to base64-url format
    d = to_base64_url(private_numbers.private_value.to_bytes(32, byteorder='big'))
    x = to_base64_url(public_numbers.x.to_bytes(32, byteorder='big'))
    y = to_base64_url(public_numbers.y.to_bytes(32, byteorder='big'))

    # Create JWK representations
    public_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": x,
        "y": y,
        "alg": "ES256",
        "kid": "authentication-key"
    }

    private_jwk = {
        **public_jwk,  # Include all public key fields
        "d": d
    }

    return public_jwk, private_jwk

# Generate keys
public_key, private_key = generate_ec_key_pair()

# Output the keys in JWK format
print("Public JWK:", json.dumps(public_key, indent=2))
print("Private JWK:", json.dumps(private_key, indent=2))
