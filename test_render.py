import requests
import time

print("Testing Health...")
try:
    res = requests.get('https://mf-faq-backend.onrender.com/health', timeout=10)
    print("Health Status Code:", res.status_code)
    print("Health Response:", res.text)
except Exception as e:
    print("Health Error:", str(e))

print("\nTesting Chat POST...")
start = time.time()
try:
    res = requests.post(
        'https://mf-faq-backend.onrender.com/chat', 
        json={"session_id": "test", "query": "What is the expense ratio for HDFC ELSS?"},
        timeout=60
    )
    print("Chat Status Code:", res.status_code)
    print("Chat Response:", res.text)
except Exception as e:
    print("Chat Error:", str(e))

print(f"Chat took {time.time() - start:.2f} seconds")
