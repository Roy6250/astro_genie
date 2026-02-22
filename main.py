import logging
from fastapi import FastAPI
from api.webhook import router as webhook_router

# So logger.info() etc. from agents and other modules show in the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(title="Astro Genie Backend")

app.include_router(webhook_router)
