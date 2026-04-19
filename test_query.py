import urllib.request
import json

url = 'http://127.0.0.1:8001/chat'
data = {
    "session_id": "test1",
    "query": "What is the expense ratio of HDFC ELSS?"
}

req = urllib.request.Request(url, method='POST')
req.add_header('Content-Type', 'application/json')
encoded_data = json.dumps(data).encode('utf-8')

try:
    response = urllib.request.urlopen(req, data=encoded_data)
    print(response.read().decode('utf-8'))
except urllib.error.URLError as e:
    print(f"Error connecting to server: {e}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    print(e.read().decode('utf-8'))
