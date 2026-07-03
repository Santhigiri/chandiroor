from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.panchangam import router as panchangam_router
from api.routes.v1.panchangam import router as panchangam_v1_router
from api.routes.v1.auth import router as auth_v1_router

from utils.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],  # let browser JS read the ETag to send back in If-None-Match
)
app.include_router(panchangam_router)
app.include_router(panchangam_v1_router, prefix="/api/v1")
app.include_router(auth_v1_router, prefix="/api/v1")

