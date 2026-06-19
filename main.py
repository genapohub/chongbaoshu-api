import os
import asyncio
from dotenv import load_dotenv
load_dotenv()  # 必须在所有 import 之前加载环境变量

from config.sentry_config import init_sentry
init_sentry()  # 尽早初始化 Sentry SDK

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config.database import Base, engine
from config.logging_config import setup_logging, get_access_logger, get_error_logger
from config.health import health_check_deep
from config.error_codes import Errors
from middleware.audit import audit_middleware
from middleware.monitoring import MonitoringMiddleware
from utils.sanitize import mask_phone
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
from routes.feedback import router as feedback_router
from routes.buyer_leads import router as buyer_leads_router
from routes.pet_sales import router as pet_sales_router
from routes.litters import router as litters_router
from routes.ledger import router as ledger_router
from routes.admin import router as admin_router
from routes.monitoring import router as monitoring_router

app = FastAPI(
    title="宠宝树V1.1 API",
    version="1.1.0",
    redirect_slashes=False
)

# ── 速率限制 ──────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 初始化日志系统 ──────────────────────────────────────
loggers = setup_logging()
access_logger = get_access_logger()
error_logger = get_error_logger()

# ── GZip 压缩 ──────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS 配置：从环境变量读取允许的来源域名
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True if ALLOWED_ORIGINS != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 性能监控中间件（替换原 log_requests） ──────────────────────
app.add_middleware(
    MonitoringMiddleware,
    slow_threshold_ms=int(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "3000")),
)

# ── 安全响应头中间件 ──────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ── 请求体大小限制中间件 ──────────────────────────────────────
@app.middleware("http")
async def limit_request_body(request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"code": Errors.PARAM_INVALID, "message": "请求体过大，最大10MB"})
    return await call_next(request)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/api/health-check")
async def health_check():
    """简单存活检查"""
    return {"code": 0, "message": "ok", "status": "ok", "version": "1.1.0"}


@app.get("/api/health-check/deep")
async def health_check_full():
    """深度健康检查：数据库、磁盘、内存"""
    try:
        result = await health_check_deep()
        code = Errors.SUCCESS if result["status"] == "ok" else Errors.DEEP_CHECK_FAILED
        return {"code": code, "data": result}
    except Exception as e:
        error_logger.error(f"[HealthCheck] 深度检查异常: {e}")
        return {"code": Errors.DEEP_CHECK_FAILED, "data": {"status": "error", "message": str(e)}}

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
app.include_router(buyer_leads_router)
app.include_router(pet_sales_router)
app.include_router(litters_router)
app.include_router(ledger_router)
app.include_router(admin_router)
app.include_router(feedback_router, prefix="/api/feedback", tags=["feedback"])
app.include_router(monitoring_router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    custom_code = exc.status_code  # 业务错误码，映射逻辑保留
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

    error_logger.warning(
        "HTTP %s %s → %d (code=%s, detail=%s)",
        request.method, request.url.path, http_status, custom_code, exc.detail
    )

    return JSONResponse(
        status_code=http_status,
        content={"code": custom_code, "message": exc.detail}
    )

from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"code": Errors.PARAM_INVALID, "message": "参数验证失败"}
    )


async def reminder_push_sweeper():
    """后台定时任务：每天9:00扫描待办提醒，推送微信模板消息"""
    from config.database import SessionLocal
    from utils.push import send_reminder_push
    import asyncio
    while True:
        # 每天北京时间 9:00 执行
        now = datetime.utcnow()
        target = now.replace(hour=1, minute=0, second=0, microsecond=0)  # UTC 1:00 = 北京 9:00
        if now > target:
            target = target + timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        push_logger.info("下次提醒推送将在 %s 执行（%.0f 分钟后）", target, wait_seconds / 60)
        await asyncio.sleep(wait_seconds)
        db = SessionLocal()
        try:
            count = send_reminder_push(db)
            push_logger.info("提醒推送完成: %s", count)
        except Exception as e:
            push_logger.error("提醒推送异常: %s", e)
        finally:
            db.close()
async def subscription_expiry_sweeper():
    """后台定时任务：每小时扫描过期订阅并自动降级"""
    from config.database import SessionLocal
    from routes.subscription import downgrade_expired_subscriptions
    while True:
        await asyncio.sleep(3600)
        db = SessionLocal()
        try:
            count = downgrade_expired_subscriptions(db)
            if count > 0:
                access_logger.info("自动降级 %d 个过期订阅", count)
        except Exception as e:
            error_logger.error("订阅清扫异常: %s", e)
        finally:
            db.close()


@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(subscription_expiry_sweeper())
    asyncio.create_task(reminder_push_sweeper())
    access_logger.info("数据库同步完成")
    access_logger.info("订阅到期自动清扫任务已启动")
    access_logger.info("宠宝树V1.1 API 启动, ENV=%s, PORT=%s",
                       os.getenv("ENV", "development"), os.getenv("PORT", 3000))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(
        app, host="0.0.0.0", port=port,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "default": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
            },
        },
    )
