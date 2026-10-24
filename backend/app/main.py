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
from app.engine.service import CloudPilot, DecisionConflict
from app.models.contracts import ErrorResponse
from app.repositories.estate import import_dataset


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import_dataset(config.resolved_database_path, config.resolved_dataset_path)
        app.state.cloudpilot = CloudPilot(config.resolved_database_path)
        yield

    app = FastAPI(
        title="CloudPilot API", version="0.2.0", lifespan=lifespan,
        responses={422: {"model": ErrorResponse}},
    )
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware, allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"],
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
        details = [{"type": item["type"], "location": list(item["loc"]), "message": item["msg"]} for item in exc.errors()]
        return error(request, 422, "validation_error", "Invalid request", details)

    @app.exception_handler(LookupError)
    async def not_found(request: Request, exc: LookupError):
        return error(request, 404, "http_404", str(exc))

    @app.exception_handler(DecisionConflict)
    async def conflict(request: Request, exc: DecisionConflict):
        return error(request, 409, "decision_conflict", str(exc))

    app.include_router(router)
    return app


app = create_app()

