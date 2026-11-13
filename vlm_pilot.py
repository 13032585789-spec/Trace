"""Run the vision model on cubicasa test images ON YOUR OWN COMPUTER (needs internet + a Gemini key).
Reads images straight from the dataset zip; writes one JSON per image into ./vlm_cache/ .

PowerShell:
    $env:GEMINI_API_KEY = "your key"
    python vlm_pilot.py --n 200
Options: --zip PATH (default ../junction-dataset.zip)  --model NAME (default: auto-pick)  --n COUNT
"""
import os, sys, json, zipfile, hashlib, base64, time, argparse, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.cubicasa import PROMPT

API = "https://generativelanguage.googleapis.com/v1beta"

def http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read())

def pick_model(key):
    names = [m["name"].split("/")[-1] for m in http(f"{API}/models?pageSize=1000&key={key}")["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    good = [n for n in names if n.startswith("gemini-") and not any(x in n for x in ("tts", "image", "embedding", "live", "audio", "lite"))]
    def rank(n):  # newest version first, pro before flash
        v = n.split("-")[1]
        try: ver = float(v)
        except ValueError: ver = 0
        return (ver, "pro" in n, "preview" not in n and "exp" not in n)
    good.sort(key=rank, reverse=True)
    print("models available:", ", ".join(good[:8]))
    return good[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "junction-dataset.zip"))
    ap.add_argument("--n", type=int, default=200); ap.add_argument("--model")
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key: sys.exit('Set the key first:  $env:GEMINI_API_KEY = "your key"')
    model = a.model or pick_model(key); print("using model:", model)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm_cache"); os.makedirs(out, exist_ok=True)
    z = zipfile.ZipFile(a.zip)
    paths = sorted({json.loads(l)["path"] for l in z.open("junction-dataset/questions.jsonl") if b"cubicasa5k" in l})
    test = [p for p in paths if int(hashlib.md5(p.encode()).hexdigest(), 16) % 5 == 0][:a.n]
    done = 0
    for i, p in enumerate(test):
        dst = os.path.join(out, os.path.basename(p) + ".json")
        if os.path.exists(dst): continue
        b64 = base64.b64encode(z.read("junction-dataset/" + p)).decode()
        body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/png", "data": b64}}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        for attempt in range(5):
            try:
                r = http(f"{API}/models/{model}:generateContent?key={key}", body)
                det = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
                json.dump({"model": f"gemini:{model}", "boxes": det}, open(dst, "w")); done += 1; break
            except urllib.error.HTTPError as e:
                msg = e.read()[:200]
                if e.code in (429, 500, 503): time.sleep(10 * (attempt + 1)); continue
                print("error", e.code, msg); break
            except Exception as e:
                print("error", p, repr(e)[:200]); time.sleep(3)
        print(f"{i+1}/{len(test)} {os.path.basename(p)}", flush=True)
    print("done, new results:", done, "->", out)

if __name__ == "__main__":
    main()
