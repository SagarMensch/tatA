import requests
import json

API_KEY = "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"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("Testing google/gemini-2.5-flash:free...")
try:
    payload = {
        "model": "google/gemini-2.5-flash:free",
        "messages": [{"role": "user", "content": "Say hello!"}]
    }
    res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    print("Status:", res.status_code)
    try:
        print("Response:", res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print("Full Response:", res.text)
except Exception as e:
    print("Error:", e)

print("\nTesting meta-llama/llama-3.3-70b-instruct:free...")
try:
    payload2 = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": "Say hello!"}]
    }
    res2 = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload2)
    print("Status:", res2.status_code)
    try:
        print("Response:", res2.json()['choices'][0]['message']['content'])
    except Exception as e:
        print("Full Response:", res2.text)
except Exception as e:
    print("Error:", e)
