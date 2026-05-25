#!/bin/bash
cd /home/z/my-project/宠宝树/chongbaoshu-api
export ENV=development
exec python3.12 -m uvicorn main:app --host 0.0.0.0 --port 3000
