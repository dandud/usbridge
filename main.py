from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.api import api_router
from app.config_store import config_store
from app.mdns import mdns_advertiser
from app.usbip_manager import usbip_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    config = config_store.load()
    port = config.get("app_port", 8000)

    # Start mDNS
    mdns_advertiser.start(port=port)

    # Rebind persistent devices
    usbip_manager.apply_auto_binds()

    yield

    # Shutdown
    mdns_advertiser.stop()


app = FastAPI(
    title="USBridge API",
    description="REST API for managing `usbip` device bindings, configurations, and logs on a local Linux device.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Mount API routes
app.include_router(api_router, prefix="/api")

# Serve the static frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    from app.config_store import config_store

    config = config_store.load()
    app_port = config.get("app_port", 8000)
    uvicorn.run("main:app", host="0.0.0.0", port=app_port, reload=True)
