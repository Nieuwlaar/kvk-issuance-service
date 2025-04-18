from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import base_routes, kvk_bevoegdheid_rest_api, mini_suomi, well_known_routes, rdw_niscy

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development
        "https://mijn-kvk-portal.nieuwlaar.com",
        "https://kvk-issuance-ui.nieuwlaar.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount well-known routes at root level
app.include_router(well_known_routes.router)

# Mount other routes with their prefixes
app.include_router(base_routes.router)
app.include_router(mini_suomi.router, prefix="/mini-suomi")
app.include_router(rdw_niscy.router, prefix="/rdw-niscy")
app.include_router(kvk_bevoegdheid_rest_api.router, prefix="/bevoegdheid")
