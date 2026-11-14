"""Door/window pass on 2x2 tiles (made by make_tiles.py). Run ON YOUR OWN COMPUTER:
    $env:GEMINI_API_KEY = "your key"
    python vlm_tiles.py --model gemini-3.6-flash
Writes vlm_tiles_out/<tile>.json ; re-running skips finished tiles."""
import os, sys, json, base64, time, argparse, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

API = "https://generativelanguage.googleapis.com/v1beta"
PROMPT = ("This image is one quarter (with a small overlap) of a Finnish residential floor plan. "
          "Find every DOOR and every WINDOW that is visible in this crop. "
          "door = a doorway fitted with a door leaf (swing arc and leaf, or a sliding leaf); an open doorway with no leaf is NOT a door. "
          "window = a window opening drawn in a wall (thin parallel lines or a glazing symbol inside the wall). "
          "Include items cut by the crop edge. Count each double door or multi-pane window as ONE. "
          "Return JSON only: {\"door\": [[x0,y0,x1,y1], ...], \"window\": [[x0,y0,x1,y1], ...]} "
          "with boxes in 0-1000 coordinates of THIS crop (x right, y down).")
lock = threading.Lock()

def call(key, model, jpg, timeout=120):
    body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/jpeg",
            "data": base64.b64encode(jpg).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    req = urllib.request.Request(f"{API}/models/{model}:generateContent?key={key}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gemini-3.6-flash"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(); key = os.environ.get("GEMINI_API_KEY")
    if not key: sys.exit('Set the key first:  $env:GEMINI_API_KEY = "your key"')
    here = os.path.dirname(os.path.abspath(__file__)); src = os.path.join(here, "vlm_tiles"); out = os.path.join(here, "vlm_tiles_out")
    os.makedirs(out, exist_ok=True)
    todo = [f for f in sorted(os.listdir(src)) if f.endswith(".jpg") and not os.path.exists(os.path.join(out, f + ".json"))]
    print(f"{len(todo)} tiles to go with {a.model}", flush=True); st = {"n": 0, "t0": time.time()}
    def work(f):
        for attempt in range(6):
            try:
                det = call(key, a.model, open(os.path.join(src, f), "rb").read())
                json.dump(det, open(os.path.join(out, f + ".json"), "w"))
                with lock:
                    st["n"] += 1; print(f"{st['n']}/{len(todo)}  ({(time.time() - st['t0']) / st['n']:.1f}s each)", flush=True)
                return
            except urllib.error.HTTPError as e:
                msg = e.read()[:150].decode(errors="replace")
                with lock: print(f"HTTP {e.code}, retrying in {10 * (attempt + 1)}s  {msg}", flush=True)
                time.sleep(10 * (attempt + 1))
            except Exception as e:
                with lock: print("retry", f, type(e).__name__, flush=True)
                time.sleep(5)
    with ThreadPoolExecutor(a.workers) as ex: list(ex.map(work, todo))
    print("finished:", st["n"], "tiles ->", out)

if __name__ == "__main__":
    main()
