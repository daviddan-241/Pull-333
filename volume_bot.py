"""
Real volume engine: spawns a background thread that does randomized
Jupiter buys/sells from a payer wallet to generate trading volume.
LiquidityManager queries DexScreener for live pools.
"""
import time
import random
import logging
import threading
import requests

from solders.keypair import Keypair
from solana_client import SolanaTrader

logger = logging.getLogger(__name__)

DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"


class VolumeEngine:
    def __init__(self, mint: str, payer: Keypair):
        self.mint = mint
        self.payer = payer
        self.trader = SolanaTrader(payer)
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._stats = {"trades": 0, "volume_sol": 0.0, "errors": 0}

    def fund_wallets(self, sol_each: float):
        bal = self.trader.get_sol_balance()
        logger.info(f"[VOLUME] payer balance {bal} SOL (target {sol_each})")
        return bal >= sol_each

    def _loop(self, duration_s: int, buy_ratio: float):
        end = time.time() + duration_s
        while not self._stop_evt.is_set() and time.time() < end:
            try:
                trade_sol = round(random.uniform(0.005, 0.03), 4)
                lamports = int(trade_sol * 1e9)

                if random.random() < buy_ratio:
                    sig = self.trader.buy_token(self.mint, lamports)
                    self._stats["trades"] += 1
                    self._stats["volume_sol"] += trade_sol
                    logger.info(f"[VOLUME] buy {trade_sol} SOL -> {sig[:16]}...")
                else:
                    bal = self.trader.get_token_balance(self.mint)
                    if bal["raw"] > 0:
                        portion = int(bal["raw"] * random.uniform(0.05, 0.2))
                        if portion > 0:
                            sig = self.trader.sell_token(self.mint, portion)
                            self._stats["trades"] += 1
                            self._stats["volume_sol"] += trade_sol
                            logger.info(f"[VOLUME] sell {portion} -> {sig[:16]}...")
            except Exception as e:
                self._stats["errors"] += 1
                logger.warning(f"[VOLUME] trade error: {e}")

            self._stop_evt.wait(random.uniform(8, 25))
        self.running = False
        logger.info(f"[VOLUME] loop ended: {self._stats}")

    def start(self, duration_minutes: int = 60, buy_ratio: float = 0.6) -> str:
        if self.running:
            return "Already running"
        self._stop_evt.clear()
        self.running = True
        self._thread = threading.Thread(
            target=self._loop, args=(duration_minutes * 60, buy_ratio),
            daemon=True, name=f"volume-{self.mint[:8]}",
        )
        self._thread.start()
        return f"Started ({duration_minutes}m, buy_ratio={buy_ratio})"

    def stop(self) -> str:
        self._stop_evt.set()
        self.running = False
        return f"Stopped - {self._stats['trades']} trades, {self._stats['volume_sol']:.3f} SOL"

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "trades": self._stats["trades"],
            "volume_sol": self._stats["volume_sol"],
            "errors": self._stats["errors"],
        }


class LiquidityManager:
    def find_pools(self, mint: str) -> list[dict]:
        try:
            r = requests.get(f"{DEXSCREENER_TOKEN}/{mint}", timeout=10)
            pairs = r.json().get("pairs") or []
            out = []
            for p in pairs:
                out.append({
                    "id": p.get("pairAddress", "N/A"),
                    "dex": p.get("dexId", "?"),
                    "tvl": float((p.get("liquidity") or {}).get("usd") or 0),
                    "price": float(p.get("priceUsd") or 0),
                    "url": p.get("url"),
                })
            out.sort(key=lambda x: x["tvl"], reverse=True)
            return out
        except Exception as e:
            logger.warning(f"find_pools failed: {e}")
            return []
