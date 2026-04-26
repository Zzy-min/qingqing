import subprocess, time

# Find parent of 32856
r = subprocess.run(
    ['powershell', '-Command', '(Get-CimInstance Win32_Process -Filter "ProcessId=32856").ParentProcessId'],
    capture_output=True, text=True
)
parent_pid = r.stdout.strip()
print(f'Parent of 32856: {parent_pid}')

# Kill parent and child
if parent_pid:
    subprocess.run(['powershell', '-Command', f'Stop-Process -Id {parent_pid} -Force'], capture_output=True)
    print(f'Killed parent {parent_pid}')
subprocess.run(['powershell', '-Command', 'Stop-Process -Id 32856 -Force'], capture_output=True)

time.sleep(3)

# Verify
r2 = subprocess.run(
    ['powershell', '-Command', '(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess'],
    capture_output=True, text=True
)
print(f'Port 8000: {r2.stdout.strip() or "FREE"}')

if not r2.stdout.strip():
    print('Port is free! Starting new server...')
    import os, shutil
    base = r'C:\Users\Lenovo\projects\minimax-photo-agent\backend'

    # Clean pycache
    for root, dirs, files in os.walk(base):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)

    # Write clean main.py (no monkey-patch needed since schemas.py is correct)
    main_content = '''import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from api.routes import router

app = FastAPI(
    title="MiniMax Photo Agent API",
    description="AI-powered photo editing with MiniMax API integration",
    version="2.0.0",
)

MAX_REQUEST_BODY = 20 * 1024 * 1024


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BODY:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large (max {MAX_REQUEST_BODY // 1024 // 1024}MB)"},
                )
        except ValueError:
            pass
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")


@app.on_event("startup")
async def startup():
    logging.getLogger(__name__).info("MiniMax Photo Agent API starting up...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
'''

    with open(os.path.join(base, 'main.py'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(main_content)
    print('main.py written')

    # Write schemas.py
    schema_content = '''from pydantic import BaseModel, Field
from typing import Literal, Optional


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Image generation prompt",
    )
    image_data: Optional[str] = Field(
        default=None,
        description="Optional base64 image for img2img generation",
    )
    style: str = Field(
        default="general",
        description="Image style: general, anime, photo, oil_painting, sketch",
    )


class ProcessRequest(BaseModel):
    image_data: str = Field(
        ...,
        min_length=1,
        max_length=10000000,
        description="Base64-encoded image data",
    )
    prompt: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="Processing instruction (for AI mode)",
    )
    style: Optional[str] = Field(
        default=None,
        description="Processing style (for AI mode)",
    )
    brightness: Optional[float] = Field(default=None, ge=0, le=3)
    contrast: Optional[float] = Field(default=None, ge=0, le=3)
    saturation: Optional[float] = Field(default=None, ge=0, le=3)
    sharpness: Optional[float] = Field(default=None, ge=0, le=3)
    blur: Optional[float] = Field(default=None, ge=0, le=20)
    rotate: Optional[int] = Field(default=None, ge=-180, le=180)
    flip_h: Optional[bool] = None
    flip_v: Optional[bool] = None
    filter_type: Optional[str] = Field(
        default=None,
        description="Preset filter: vintage, bw, sepia, edge, sharpen",
    )


class ImageResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_data: Optional[str] = None
    message: str = ""
    style: Optional[str] = None
    dimensions: Optional[dict] = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
'''

    with open(os.path.join(base, 'api', 'schemas.py'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(schema_content)
    print('schemas.py written')

    # Start server WITHOUT reload
    os.chdir(base)
    proc = subprocess.Popen(
        ['python', '-c', 'import uvicorn; uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=base, creationflags=0x00000008
    )
    print(f'Server started PID: {proc.pid}')
    time.sleep(4)

    # Verify
    import urllib.request, json
    resp = urllib.request.urlopen('http://localhost:8000/openapi.json', timeout=5)
    schema = json.loads(resp.read().decode())
    gr = schema['components']['schemas']['GenerateRequest']
    ml = gr['properties']['prompt'].get('maxLength')
    print(f'OpenAPI maxLength: {ml}')

    # Test 5000 char prompt
    data = json.dumps({'prompt': 'x' * 5000, 'style': 'general'}).encode()
    req = urllib.request.Request('http://localhost:8000/api/generate', data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        print(f'5000-char prompt: {resp.status} OK!')
    except urllib.error.HTTPError as e:
        print(f'5000-char prompt: {e.code} {e.read().decode()[:200]}')
else:
    print('Port still occupied!')
