import urllib.request
import json

try:
    req = urllib.request.Request('http://127.0.0.1:5000/api/lands')
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    print(f"Total lands fetched: {data.get('total')}")
    if data.get('data'):
        pid = data['data'][0]['id']
        req2 = urllib.request.Request(f'http://127.0.0.1:5000/api/lands/{pid}')
        resp2 = urllib.request.urlopen(req2)
        d2 = json.loads(resp2.read().decode('utf-8'))
        print(f"Parcel fetched: {d2['parcel']['survey_number']}")
        print(f"ML ROI 5yr: {d2['ml_analysis'].get('roi_5yr')}")
except Exception as e:
    print(f"Error: {e}")
