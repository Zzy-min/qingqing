#!/bin/bash
cd /mnt/c/Users/Lenovo/projects/minimax-photo-agent/backend
set -a
source .env
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
