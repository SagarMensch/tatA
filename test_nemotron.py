import requests
import json

API_KEY = "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"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("Testing nvidia/nemotron-nano-12b-v2-vl:free...")
try:
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [{"role": "user", "content": "Say hello! What model are you?"}]
    }
    res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    print("Status:", res.status_code)
    try:
        print("Response:", res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print("Full Response:", res.text)
except Exception as e:
    print("Error:", e)
