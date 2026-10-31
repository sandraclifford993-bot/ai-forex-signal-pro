import os, asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from data import fetch_candles
from strategy import analyze
from store import init_db, add_signal, list_signals, get_stats, save_token, get_tokens, update_result

load_dotenv()
API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "80"))
PAIRS = os.getenv("PAIRS", "EUR/USD,GBP/USD,USD/JPY,AUD/USD,USD/CAD,USD/CHF,NZD/USD,EUR/JPY,GBP/JPY,EUR/GBP").split(",")
scheduler = AsyncIOScheduler(timezone="UTC")

async def send_push(title, body, data=None):
    # Firebase Admin is optional until Firebase service-account credentials are configured.
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        if not firebase_admin._apps:
            cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "")
            if not cred_path or not os.path.exists(cred_path):
                return
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        tokens = get_tokens()
        if tokens:
            msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                tokens=tokens[:500]
            )
            messaging.send_each_for_multicast(msg)
    except Exception as e:
        print("Push notification unavailable:", e)

async def scan_markets():
    if not API_KEY:
        print("Set TWELVEDATA_API_KEY before scanning.")
        return
    for pair in PAIRS:
        pair = pair.strip()
        try:
            candles = await asyncio.to_thread(fetch_candles, pair, API_KEY)
            signal = analyze(pair, candles)
            if signal["decision"] in ("CALL", "PUT") and signal["score"] >= MIN_SCORE:
                created = add_signal(signal, expiry_minutes=5)
                if created:
                    await send_push(
                        f'{pair} {signal["decision"]} signal',
                        f'5-minute research signal • score {signal["score"]}/100 • verify platform quote',
                        {"signal_id": str(created), "pair": pair, "direction": signal["decision"]}
                    )
        except Exception as e:
            print(f"Scan error for {pair}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(scan_markets, "interval", seconds=SCAN_INTERVAL_SECONDS, id="scan", max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="AI Forex Signal Pro API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TokenInput(BaseModel):
    token: str

@app.get("/health")
def health():
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat(),
            "scanner_interval_seconds": SCAN_INTERVAL_SECONDS, "pairs": PAIRS}

@app.get("/signals")
def signals(limit: int = 100):
    return list_signals(min(max(limit, 1), 500))

@app.get("/stats")
def stats():
    return get_stats()

@app.post("/device-token")
def register_token(payload: TokenInput):
    if len(payload.token) < 20:
        raise HTTPException(400, "Invalid device token")
    save_token(payload.token)
    return {"registered": True}

@app.post("/scan-now")
async def scan_now():
    await scan_markets()
    return {"scan_requested": True}
