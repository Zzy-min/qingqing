import sys, os
os.chdir(r"C:\Users\Lenovo\projects\minimax-photo-agent\backend")
sys.path.insert(0, r"C:\Users\Lenovo\projects\minimax-photo-agent\backend")

# Force remove any cached modules
for mod_name in list(sys.modules.keys()):
    if 'schemas' in mod_name or 'api' in mod_name:
        del sys.modules[mod_name]

# Import and patch
from api.schemas import GenerateRequest, ProcessRequest
for field_name, model in [('prompt', GenerateRequest), ('prompt', ProcessRequest)]:
    if field_name in model.model_fields:
        fi = model.model_fields[field_name]
        if hasattr(fi, 'metadata'):
            print(f"  {model.__name__}.{field_name} metadata: {fi.metadata}")

print(f"GenerateRequest.prompt constraints: max_length={GenerateRequest.model_fields['prompt'].max_length}")

import uvicorn
uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
