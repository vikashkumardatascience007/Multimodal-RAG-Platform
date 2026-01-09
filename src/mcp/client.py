import requests

payload = {
    "query": "operating profit risk",
    "top_k": 5,
    "user_email": "vk00794007@gmail.com"
}

response = requests.post(
    "http://localhost:3333/tools/query_enterprise_pdf",
    json=payload,
    timeout=30
)

print(response.json())
