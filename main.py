from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.panchangam import router as panchangam_router

from utils.lifespan import lifespan


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(panchangam_router)

