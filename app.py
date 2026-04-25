from flask import Flask, request
import os
import sys
import traceback

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Token Bot Running"

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/debug")
def debug():
    return {
        "env": {
            "TELEGRAM_TOKEN": "set" if os.getenv("TELEGRAM_TOKEN") else "missing",
            "RENDER_EXTERNAL_URL": os.getenv("RENDER_EXTERNAL_URL", "not set"),
        }
    }

def start_bot():
    print("[BOT] Starting...", flush=True)
    try:
        from bot import run_bot
        run_bot()
    except Exception as e:
        print(f"[BOT ERROR] {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    import threading
    print("[MAIN] Starting...", flush=True)
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
