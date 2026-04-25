import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig
import base64
from io import BytesIO
from PIL import Image

from dotenv import load_dotenv
load_dotenv()

from huggingface_hub import login
token = os.getenv("HF_TOKEN")
if token:
    login(token=token)
else:
    print("Warning: HF_TOKEN not found!")

app = FastAPI(title="Local MedGemma API")

model_id = "google/medgemma-1.5-4b-it"

print("Loading MedGemma (CPU mode for 32GB System RAM)...")

try:
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        device_map="cpu",
        torch_dtype=torch.float16
    )
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    print("Make sure you installed bitsandbytes and accelerate!")
    model, processor = None, None

class AnalyzeRequest(BaseModel):
    image_base64: str
    prompt: str

@app.get("/health")
def health():
    if model is None:
        return {"status": "error", "message": "Model failed to load"}
    return {"status": "ok", "message": "MedGemma API is running"}

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    try:
        # Strip data URL prefix if present
        b64_data = req.image_base64
        if "base64," in b64_data:
            b64_data = b64_data.split("base64,")[1]
            
        img_data = base64.b64decode(b64_data)
        image = Image.open(BytesIO(img_data)).convert("RGB")
        
        messages = [
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": req.prompt}
            ]}
        ]
        
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=256)
            
        decoded = processor.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        return {"status": "success", "result": decoded}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("medgemma_server:app", host="0.0.0.0", port=8001)
