import requests
from config.wechat import WX_CODE2SESSION_URL, app_config

def code2session(code: str) -> dict:
    params = {
        "appid": app_config["app_id"],
        "secret": app_config["app_secret"],
        "js_code": code,
        "grant_type": "authorization_code",
    }
    response = requests.get(WX_CODE2SESSION_URL, params=params)
    data = response.json()
    
    if "errcode" in data:
        raise Exception(f"微信登录失败: {data['errcode']} - {data.get('errmsg', '')}")
    
    return {
        "openid": data["openid"],
        "session_key": data.get("session_key"),
        "unionid": data.get("unionid"),
    }
