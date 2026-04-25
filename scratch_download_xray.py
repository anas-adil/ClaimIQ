import os
import requests

assets_dir = os.path.join("c:\\Users\\User\\Downloads\\tpa\\execution\\frontend", "assets")
os.makedirs(assets_dir, exist_ok=True)

url = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Chest_Xray_PA_3-8-2010.png/512px-Chest_Xray_PA_3-8-2010.png"
filepath = os.path.join(assets_dir, "sample_xray.png")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
response = requests.get(url, headers=headers)
with open(filepath, 'wb') as f:
    f.write(response.content)

print(f"Downloaded to {filepath}")
