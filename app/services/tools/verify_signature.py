from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

# Load the private key
with open("private_key.pem", "rb") as f:
    private_key = load_pem_private_key(f.read(), password=None)

# Get the public key
public_key = private_key.public_key()

# Export the public key in PEM format (SPKI)
public_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
print("Public Key (PEM):")
print(public_pem.decode())
