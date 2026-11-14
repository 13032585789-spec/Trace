"""Run the vision model on cubicasa test images ON YOUR OWN COMPUTER (needs internet + a Gemini key).
Reads images straight from the dataset zip; writes one JSON per image into ./vlm_cache/ .

PowerShell:
    $env:GEMINI_API_KEY = "your key"
    python vlm_pilot.py --n 200
Options: --model NAME (default: newest Flash)   --workers 4   --zip PATH   --n COUNT
"""
import os, sys, json, zipfile, hashlib, base64, time, argparse, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.cubicasa import PROMPT

API = "https://generativelanguage.googleapis.com/v1beta"
lock = threading.Lock()

def http(url, body=None, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())

def pick_model(key):
    names = [m["name"].split("/")[-1] for m in http(f"{API}/models?pageSize=1000&key={key}")["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    good = [n for n in names if n.startswith("gemini-") and "flash" in n and
            not any(x in n for x in ("tts", "image", "embedding", "live", "audio", "lite", "exp"))]
    def ver(n):
        try: return float(n.split("-")[1])
        except ValueError: return 0
    good.sort(key=lambda n: (ver(n), "preview" not in n), reverse=True)
    print("flash models available:", ", ".join(good[:6]) or "(none)")
    return good or ["gemini-2.5-flash"]

def call(key, model, png_bytes, timeout=180):
    body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/png",
            "data": base64.b64encode(png_bytes).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    r = http(f"{API}/models/{model}:generateContent?key={key}", body, timeout)
    return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "junction-dataset.zip"))
    ap.add_argument("--n", type=int, default=200); ap.add_argument("--model"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key: sys.exit('Set the key first:  $env:GEMINI_API_KEY = "your key"')
    candidates = [a.model] if a.model else pick_model(key)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm_cache"); os.makedirs(out, exist_ok=True)
    z = zipfile.ZipFile(a.zip)
    paths = sorted({json.loads(l)["path"] for l in z.open("junction-dataset/questions.jsonl") if b"cubicasa5k" in l})
    test = [p for p in paths if int(hashlib.md5(p.encode()).hexdigest(), 16) % 5 == 0][:a.n]
    todo = [p for p in test if not os.path.exists(os.path.join(out, os.path.basename(p) + ".json"))]
    imgs = {p: z.read("junction-dataset/" + p) for p in todo}
    print(f"{len(test) - len(todo)} already done, {len(todo)} to go", flush=True)
    if not todo: return
    # one test call first, so problems show up immediately; overloaded (503) models -> try the next one
    model = None
    for m in candidates:
        t = time.time()
        try:
            call(key, m, imgs[todo[0]], timeout=60); model = m; break
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode(errors="replace")
            if e.code in (429, 503, 404) and m != candidates[-1]:
                print(f"{m}: HTTP {e.code} (busy, rate-limited or unavailable), trying the next model", flush=True); continue
            sys.exit(f"TEST CALL FAILED with {m}  HTTP {e.code}: {msg}")
        except Exception as e:   # timeouts, dropped connections
            if m != candidates[-1]:
                print(f"{m}: {type(e).__name__} (no answer within 60s), trying the next model", flush=True); continue
            sys.exit(f"TEST CALL FAILED with {m}: {e!r}")
    print(f"using model: {model}  (test call OK in {time.time() - t:.0f}s), starting {a.workers} workers", flush=True)
    stats = {"ok": 0, "fail": 0, "t0": time.time()}
    def work(p):
        dst = os.path.join(out, os.path.basename(p) + ".json")
        for attempt in range(6):
            try:
                det = call(key, model, imgs[p])
                json.dump({"model": f"gemini:{model}", "boxes": det}, open(dst, "w"))
                with lock:
                    stats["ok"] += 1; n = stats["ok"]; el = time.time() - stats["t0"]
                    print(f"{n}/{len(todo)} done  ({el / n:.1f}s per image)  {os.path.basename(p)}", flush=True)
                return
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode(errors="replace")
                if e.code == 429:
                    with lock: print(f"rate limited (429), waiting {20 * (attempt + 1)}s ... {msg[:150]}", flush=True)
                    time.sleep(20 * (attempt + 1)); continue
                if e.code in (500, 503): time.sleep(5); continue
                with lock: print("error", e.code, msg, flush=True); stats["fail"] += 1
                return
            except Exception as e:
                with lock: print("error", os.path.basename(p), repr(e)[:200], flush=True)
                time.sleep(3)
        with lock: stats["fail"] += 1
    with ThreadPoolExecutor(a.workers) as ex: list(ex.map(work, todo))
    print(f"finished: {stats['ok']} ok, {stats['fail']} failed -> {out}")

if __name__ == "__main__":
    main()
