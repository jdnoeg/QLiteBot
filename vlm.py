import requests
from PIL import Image
import base64
import config
import json

# API配置
API_URL = config.vlm["url"]
API_KEY = config.vlm["key"]


# 图片处理函数
def image_to_base64(image_path):
    with Image.open(image_path) as img:
        # 转换为RGB模式（如果图片是RGBA等格式）
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 调整大小（可选，根据API要求）
        # img = img.resize((512, 512))

        # 保存为临时文件并编码
        img.save("temp.jpg", format="JPEG", quality=95)
        with open("temp.jpg", "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')


# 调用API函数
def analyze_image(image_url):

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.vlm["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "详细描述这张图片的内容"},
                    # {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
            }
        ],
        "max_tokens": 1000
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        return None

