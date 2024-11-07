from fastapi import FastAPI
from app.routes import base_routes, mini_suomi

app = FastAPI()

# Register the base_routes router with the main app
app.include_router(base_routes.router)
app.include_router(mini_suomi.router, prefix="/mini_suomi")
