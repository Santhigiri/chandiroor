from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.routes.panchangam import router as panchangam_router
from features.auth.router import router as auth_v1_router
from features.guruvani.router import router as guruvani_v1_router
from features.kollavarsham.router import router as kollavarsham_v1_router
from features.panchangam.generation_router import router as panchangam_generation_v1_router
from features.panchangam.router import router as panchangam_v1_router
from features.santhigiri_events.router import router as santhigiri_events_v1_router
from features.settings.router import router as settings_v1_router

from utils.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],  # let browser JS read the ETag to send back in If-None-Match
)
app.include_router(panchangam_router)
app.include_router(panchangam_v1_router, prefix="/api/v1")
app.include_router(auth_v1_router, prefix="/api/v1")
app.include_router(santhigiri_events_v1_router, prefix="/api/v1")
app.include_router(kollavarsham_v1_router, prefix="/api/v1")
app.include_router(panchangam_generation_v1_router, prefix="/api/v1")
app.include_router(guruvani_v1_router, prefix="/api/v1")
app.include_router(settings_v1_router, prefix="/api/v1")
