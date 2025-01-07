from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

# Input JSON data
key_data = {
    "privateKey": {
        "kty": "EC",
        "crv": "P-256",
        "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
        "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
        "alg": "ES256",
        "kid": "authentication-key",
        "d": "kAP-MAxRTy4F77xl-9unD-9IWfneEMC7j6E4WdSEdxI",
        "use": "sig"
    }
}

# Decode values from base64url (add padding if necessary)
def base64url_decode(input_str):
    padding = "=" * ((4 - len(input_str) % 4) % 4)
    return base64.urlsafe_b64decode(input_str + padding)

d = base64url_decode(key_data["privateKey"]["d"])
x = base64url_decode(key_data["privateKey"]["x"])
y = base64url_decode(key_data["privateKey"]["y"])

# Create the EC private key object
private_key = ec.derive_private_key(int.from_bytes(d, "big"), ec.SECP256R1(), default_backend())

# Serialize private key to PEM format
private_pem = private_key.private_bytes(
    encoding=Encoding.PEM,
    format=PrivateFormat.PKCS8,
    encryption_algorithm=NoEncryption()
)

# Serialize public key to PEM format
public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=Encoding.PEM,
    format=PublicFormat.SubjectPublicKeyInfo
)

# Save the PEM files
with open("private_key.pem", "wb") as priv_file:
    priv_file.write(private_pem)

with open("public_key.pem", "wb") as pub_file:
    pub_file.write(public_pem)

print("Keys saved to 'private_key.pem' and 'public_key.pem'")
