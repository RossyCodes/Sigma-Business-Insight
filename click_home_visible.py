"""Click the Home button in the visible Chrome window (port 9223) and verify navigation."""

import asyncio
import json
import urllib.request

import websockets

DEBUG = "http://127.0.0.1:9223"
ANCHOR = 'a[href="app/static/landing.html"]'


async def cdp(ws, method, params=None, msg_id=0):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == msg_id:
            return msg


async def evaluate(ws, expr, msg_id):
    r = await cdp(
        ws,
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": True},
        msg_id,
    )
    return r.get("result", {}).get("result", {}).get("value")


async def main():
    with urllib.request.urlopen(DEBUG + "/json/list") as resp:
        targets = json.loads(resp.read())
    page = next(t for t in targets if t["type"] == "page" and "8601" in t["url"])
    print("Attaching to visible tab:", page["url"])
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=2**26) as ws:
        await cdp(ws, "Page.enable", {}, 1)
        await cdp(ws, "Runtime.enable", {}, 2)

        found = False
        for i in range(60):
            exists = await evaluate(ws, f"!!document.querySelector('{ANCHOR}')", 100 + i)
            if exists:
                found = True
                break
            await asyncio.sleep(0.5)
        if not found:
            print("TIMEOUT: Home button not found")
            return 1

        info = await evaluate(
            ws,
            f"""
            (() => {{
              const a = document.querySelector('{ANCHOR}');
              const cs = getComputedStyle(a);
              return JSON.stringify({{
                text: a.textContent.trim(),
                target: a.getAttribute('target'),
                borderRadius: cs.borderRadius,
                padding: cs.padding,
                background: cs.backgroundImage.slice(0, 60),
                color: cs.color,
                display: cs.display
              }});
            }})()
            """,
            300,
        )
        print("Button before click:", info)

        await evaluate(ws, f"document.querySelector('{ANCHOR}').click(); true", 301)

        final_href = None
        for i in range(24):
            await asyncio.sleep(0.5)
            final_href = await evaluate(ws, "window.location.href", 400 + i)
            if final_href and "landing.html" in final_href:
                break
        title = await evaluate(ws, "document.title", 500)
        print("After click:", final_href)
        print("Landing title:", title)
        ok = final_href is not None and "landing.html" in final_href
        print("SAME-TAB NAVIGATION OK:", ok)
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
