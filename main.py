import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from config.database import Base, engine
from routes.auth import router as auth_router
from routes.pets import router as pets_router
from routes.breeding import router as breeding_router
from routes.health import router as health_router
from routes.subscription import router as subscription_router
from routes.invite import router as invite_router
from routes.photos import router as photos_router
from routes.certificates import router as certificates_router
from routes.export import router as export_router
from routes.notifications import router as notifications_router

load_dotenv()

app = FastAPI(
    title="宠宝树V1.1 API",
    version="1.1.0",
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.middleware("http")
async def log_requests(request, call_next):
    if os.getenv("ENV") == "development":
        print(f"[{request.method}] {request.url}")
    response = await call_next(request)
    return response

@app.get("/api/health-check")
async def health_check():
    return {"code": 0, "message": "ok", "version": "1.1.0"}

app.include_router(auth_router)
app.include_router(pets_router)
app.include_router(breeding_router)
app.include_router(health_router)
app.include_router(subscription_router)
app.include_router(invite_router)
app.include_router(photos_router)
app.include_router(certificates_router)
app.include_router(export_router)
app.include_router(notifications_router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    custom_code = exc.status_code
    if custom_code == 1001:
        http_status = 400
    elif custom_code == 1002:
        http_status = 401
    elif custom_code == 2001:
        http_status = 403
    elif custom_code == 5001:
        http_status = 403
    elif 400 <= custom_code < 600:
        http_status = custom_code
    else:
        http_status = 400
    
    return JSONResponse(
        status_code=http_status,
        content={"code": custom_code, "message": exc.detail}
    )

from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"code": 1001, "message": "参数验证失败"}
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"code": 404, "message": "接口不存在"}
    )

@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库同步完成")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    print(f"🚀 宠宝树V1.1 服务端已启动: http://localhost:{port}")
    print(f"📋 环境: {os.getenv('ENV', 'development')}")
    print(f"💾 数据库: {os.getenv('DB_DIALECT', 'sqlite')}")
