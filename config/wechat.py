import os

WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

app_config = {
    "app_id": os.getenv("WX_APP_ID", "wx217600e18466774e"),
    "app_secret": os.getenv("WX_APP_SECRET", "c12cacdc16b19168572bdac9a3fd44de"),
}
