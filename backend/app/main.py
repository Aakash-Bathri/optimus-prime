from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.config import Settings
from app.database import initialize
from app.models.contracts import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(config.resolved_database_path)
        yield

    app = FastAPI(
        title="CloudPilot API", version="0.1.0", lifespan=lifespan,
        responses={422: {"model": ErrorResponse}},
    )
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware, allow_origins=config.cors_origins,
        allow_methods=["GET"], allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def error(request: Request, status: int, code: str, message: str, details=None, headers=None):
        body = ErrorResponse(
            code=code, message=message, details=details or [],
            request_id=request.state.request_id,
        )
        return JSONResponse(status_code=status, content=jsonable_encoder(body), headers=headers)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(
            request, exc.status_code, f"http_{exc.status_code}", str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(request, 422, "validation_error", "Invalid request", exc.errors())

    app.include_router(router)
    return app


app = create_app()

