from flask import Flask
import os
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Token Bot Running"

@app.route("/health")
def health():
    return {"status": "ok", "message": "alive"}

def start_bot():
    try:
        from bot import run_bot
        run_bot()
    except Exception as e:
        print(f"[BOT ERROR] {e}")

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
