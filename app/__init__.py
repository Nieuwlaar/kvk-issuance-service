from fastapi import FastAPI
from app.routes import base_routes

app = FastAPI()

# Register the base_routes router with the main app
app.include_router(base_routes.router)
