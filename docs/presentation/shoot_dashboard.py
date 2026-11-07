# Screenshots every dashboard page through Chrome DevTools Protocol (needs: streamlit run dashboard/app.py --server.port 8599, Chrome, the websockets package in the venv).
# Run: python shoot_dashboard.py <out_dir> 25     (25 = seconds to wait per page).  Crop x 300..1600 afterwards to drop the sidebar.
"""Screenshot dashboard pages through Chrome DevTools Protocol (no extra packages: tornado ships with streamlit)."""
import asyncio, base64, json, subprocess, sys, time, urllib.request
from pathlib import Path
import websockets

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
PAGES = {"home": "", "p1": "Reddit_Volume", "p2": "Ticker_Mentions", "p3": "Price_and_Return", "p4": "Market_and_Sentiment",
         "p5": "Statistical_Analysis", "p6": "Lead_and_Lag", "p7": "Hot_Events"}
WAIT = float(sys.argv[2]) if len(sys.argv) > 2 else 35
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=9333",
                         "--user-data-dir=" + str(OUT / "profile"), "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)
targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
ws_url = [t for t in targets if t["type"] == "page"][0]["webSocketDebuggerUrl"]


async def main():
    ws = await websockets.connect(ws_url, max_size=200_000_000)
    n = 0

    async def call(method, **params):
        nonlocal n
        n += 1
        mid = n
        await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == mid:
                return msg.get("result", {})

    await call("Emulation.setDeviceMetricsOverride", width=1600, height=1000, deviceScaleFactor=1, mobile=False)
    for key, path in PAGES.items():
        await call("Page.navigate", url="http://localhost:8599/" + path)
        await asyncio.sleep(WAIT)
        # grow the viewport to the content height so the whole page is captured
        h = await call("Runtime.evaluate", expression="""(function(){var m=document.querySelector('[data-testid="stMain"]')||document.body;
            return Math.max(m.scrollHeight, document.body.scrollHeight)})()""", returnByValue=True)
        height = int(min(max(h["result"].get("value", 1000), 900), 6000))
        await call("Emulation.setDeviceMetricsOverride", width=1600, height=height, deviceScaleFactor=1, mobile=False)
        await asyncio.sleep(4)
        shot = await call("Page.captureScreenshot", format="png")
        (OUT / (key + ".png")).write_bytes(base64.b64decode(shot["data"]))
        print(key, height, flush=True)
        await call("Emulation.setDeviceMetricsOverride", width=1600, height=1000, deviceScaleFactor=1, mobile=False)
    await ws.close()

try:
    asyncio.run(main())
finally:
    proc.terminate()
