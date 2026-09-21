import glob
import json
import re

print("Searching transcripts for GitHub repo references...")
for path in glob.glob(r'C:\Users\Vijayakumar R\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript.jsonl'):
    cid = path.split('\\')[6]
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'github.com' in line:
                try:
                    data = json.loads(line)
                    content = str(data.get('content', ''))
                    # Search for github.com matches or tool calls
                    urls = re.findall(r'https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', content)
                    if urls:
                        src = data.get('source')
                        tp = data.get('type')
                        print(f"CID: {cid} | Source: {src} | Type: {tp} | URLs: {set(urls)}")
                except Exception as e:
                    pass
