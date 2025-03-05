from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import base_routes, mini_suomi, well_known_routes, rdw_niscy

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
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
