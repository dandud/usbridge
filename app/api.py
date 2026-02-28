from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from app.auth import verify_session, authenticate_user, generate_token, logout_user
from app.config_store import config_store
from app.usbip_manager import usbip_manager
from app.logger import app_logger, get_recent_logs

api_router = APIRouter(tags=["API"])


# --- WebSockets ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Fire and forget broadcasting
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client yet, just keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# --- Models ---
class LoginRequest(BaseModel):
    username: str = Field(description="The username for authentication")
    password: str = Field(description="The plain text password")


class DeviceActionRequest(BaseModel):
    busid: str = Field(description="The USB bus ID of the device (e.g., '1-1')")


class ConfigUpdateRequest(BaseModel):
    auth_enabled: bool = Field(
        description="Whether authentication is required to access the API and UI"
    )
    auth_username: str = Field(description="The username for authentication")
    auth_password: str = Field(
        description="The plain text password to update (leave empty to keep unchanged)"
    )
    log_level: str = Field(
        description="The application log level (DEBUG, INFO, WARN, ERROR)"
    )
    app_port: int = Field(
        ge=1024,
        le=65535,
        description="The port the application listens on (requires restart)",
    )


class StatusResponse(BaseModel):
    status: str = Field(description="Success or error status message")


class Device(BaseModel):
    busid: str = Field(description="The USB bus ID (e.g., '1-1')")
    name: str = Field(description="A human-readable name or description of the device")
    bound: bool = Field(description="Whether the device is currently bound to usbip")
    attached: bool = Field(description="Whether a remote client is actively connected to this device")


class DevicesResponse(BaseModel):
    devices: list[Device] = Field(description="List of available local USB devices")


class AuthStatusResponse(BaseModel):
    authenticated: bool = Field(
        description="Whether the current session is authenticated"
    )
    auth_enabled: bool = Field(
        description="Whether the server requires authentication globally"
    )


class ConfigResponse(BaseModel):
    auth_enabled: bool = Field(description="Whether authentication is required")
    auth_username: str = Field(description="The current username")
    log_level: str = Field(description="The active log level")
    app_port: int = Field(description="The active application port")


class LogsResponse(BaseModel):
    logs: list[str] = Field(description="A list of recent text log entries")


# --- Auth ---
@api_router.post(
    "/auth/login", response_model=StatusResponse, summary="Login to create a session"
)
def login(req: LoginRequest, response: Response) -> StatusResponse:
    """Authenticates the user and sets a secure httponly cookie for future requests."""
    if authenticate_user(req.username, req.password):
        token = generate_token()
        response.set_cookie(key="session_token", value=token, httponly=True)
        app_logger.info(f"User '{req.username}' logged in successfully.")
        return StatusResponse(status="success")
    app_logger.warning(f"Failed login attempt for user '{req.username}'.")
    raise HTTPException(status_code=401, detail="Invalid credentials")


@api_router.post(
    "/auth/logout",
    response_model=StatusResponse,
    summary="Logout of the current session",
)
def logout(
    response: Response, session_token: str = Depends(verify_session)
) -> StatusResponse:
    """Invalidates the current session token and clears the cookie."""
    logout_user(session_token)
    response.delete_cookie("session_token")
    app_logger.info("User logged out.")
    return StatusResponse(status="success")


@api_router.get(
    "/auth/status",
    response_model=AuthStatusResponse,
    summary="Check authentication status",
)
def auth_status(session_token: str = Depends(verify_session)) -> AuthStatusResponse:
    """Returns whether the current user is authenticated and if authentication is enabled globally."""
    config = config_store.load()
    return AuthStatusResponse(
        authenticated=True, auth_enabled=config.get("auth_enabled", False)
    )


# --- Devices ---
@api_router.get(
    "/devices",
    dependencies=[Depends(verify_session)],
    response_model=DevicesResponse,
    summary="List available USB devices",
)
def get_devices() -> DevicesResponse:
    """Invokes `usbip list -l` system command to retrieve locally available USB devices."""
    devices = usbip_manager.list_devices()
    # The devices mapped from the core logic fit the Pydantic type we established
    return DevicesResponse(devices=devices)


@api_router.post(
    "/devices/bind",
    dependencies=[Depends(verify_session)],
    response_model=StatusResponse,
    summary="Bind a USB device",
)
async def bind_device(req: DeviceActionRequest) -> StatusResponse:
    """Binds a specific USB bus ID to make it available over the network via usbipd."""
    success = usbip_manager.bind_device(req.busid)
    if success:
        app_logger.info(f"Successfully bound USB device {req.busid}.")
        await ws_manager.broadcast({"type": "device_change"})
        return StatusResponse(status="success")
    app_logger.error(f"Failed to bind USB device {req.busid}.")
    raise HTTPException(status_code=500, detail="Failed to bind device")


@api_router.post(
    "/devices/unbind",
    dependencies=[Depends(verify_session)],
    response_model=StatusResponse,
    summary="Unbind a USB device",
)
async def unbind_device(req: DeviceActionRequest) -> StatusResponse:
    """Unbinds a specific USB bus ID so it defaults back to local host control."""
    success = usbip_manager.unbind_device(req.busid)
    if success:
        app_logger.info(f"Successfully unbound USB device {req.busid}.")
        await ws_manager.broadcast({"type": "device_change"})
        return StatusResponse(status="success")
    app_logger.error(f"Failed to unbind USB device {req.busid}.")
    raise HTTPException(status_code=500, detail="Failed to unbind device")


# --- Config ---
@api_router.get(
    "/config",
    dependencies=[Depends(verify_session)],
    response_model=ConfigResponse,
    summary="Get application configuration",
)
def get_config() -> ConfigResponse:
    """Retrieves the current application settings, scrubbing sensitive password hashes."""
    config = config_store.load()
    # Don't send passwords in plain text or hash to UI
    safe_config = config.copy()
    safe_config.pop("auth_password", None)
    safe_config.pop("auth_password_hash", None)
    return ConfigResponse(**safe_config)


@api_router.post(
    "/config",
    dependencies=[Depends(verify_session)],
    response_model=StatusResponse,
    summary="Update application configuration",
)
def update_config(req: ConfigUpdateRequest) -> StatusResponse:
    """Updates global settings including authentication requirements and log reporting level."""
    config = config_store.load()
    config["auth_enabled"] = req.auth_enabled
    config["auth_username"] = req.auth_username
    if req.auth_password:  # Only update if provided
        from app.auth import hash_password

        config["auth_password_hash"] = hash_password(req.auth_password)
    config["log_level"] = req.log_level
    config["app_port"] = req.app_port

    if config_store.save(config):
        app_logger.info("Application settings saved successfully.")

        # apply log level immediately
        from app.logger import set_log_level

        set_log_level(req.log_level)

        return StatusResponse(status="success")

    app_logger.error("Failed to save application configuration.")
    raise HTTPException(status_code=500, detail="Failed to save configuration")


# --- Logs ---
@api_router.get(
    "/logs",
    dependencies=[Depends(verify_session)],
    response_model=LogsResponse,
    summary="Get recent audit logs",
)
def get_logs(
    lines: int = Query(
        100, ge=1, le=1000, description="The maximum number of recent lines to retrieve"
    ),
) -> LogsResponse:
    """Reads the tail end of the application's rotating log file."""
    logs = get_recent_logs(lines)
    return LogsResponse(logs=logs)
