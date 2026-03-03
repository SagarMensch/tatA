import requests, json
res = requests.get('https://openrouter.ai/api/v1/models')
data = res.json().get('data', [])
free = [m['id'] for m in data if 'free' in m['id']]
with open('free_models.txt', 'w') as f:
    f.write('\n'.join(free))
