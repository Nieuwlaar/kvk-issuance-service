from fastapi import APIRouter

# Create a router instance
router = APIRouter()

# Define a simple GET route at the root
@router.get("/")
def root():
    return {"message": "Welcome to the KVK Issuance Service!"}
