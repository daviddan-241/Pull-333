import random
import time
import threading
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.transaction import Transaction
from config import RPC_SOLANA
from solana_client import SolanaTrader

class VolumeEngine:
    def __init__(self, token_mint: str, master_keypair=None):
        self.token_mint = token_mint
        self.master_kp = master_keypair
        self.client = Client(RPC_SOLANA)
        self.running = False
        self.stats = {"trades": 0, "volume_sol": 0.0}
        self.wallets = []

    def fund_wallets(self, amount_sol: float = 0.3):
        if not self.master_kp:
            return
        self.wallets = []
        for i in range(5):
            kp = Keypair()
            self.wallets.append({"pubkey": str(kp.pubkey()), "private_key": kp.to_json(), "index": i})
            try:
                tx = Transaction()
                tx.add(transfer(TransferParams(
                    from_pubkey=self.master_kp.pubkey(),
                    to_pubkey=Pubkey.from_string(str(kp.pubkey())),
                    lamports=int(amount_sol * 1e9)
                )))
                tx.recent_blockhash = self.client.get_latest_blockhash().value.blockhash
                tx.sign(self.master_kp)
                self.client.send_transaction(tx, self.master_kp)
                time.sleep(1)
            except Exception as e:
                print(f"[Volume] Fund error: {e}")

    def start(self, duration_minutes: int = 60, buy_ratio: float = 0.6):
        if self.running:
            return "Already running"
        self.running = True

        def run_loop():
            end_time = time.time() + (duration_minutes * 60)
            while self.running and time.time() < end_time:
                try:
                    w = random.choice(self.wallets)
                    kp = Keypair.from_json(w["private_key"])
                    trader = SolanaTrader(kp)
                    sol_amount = random.uniform(0.01, 0.05)
                    lamports = int(sol_amount * 1e9)
                    is_buy = random.random() < buy_ratio

                    if is_buy:
                        sig = trader.buy_token(self.token_mint, lamports)
                        print(f"[Volume] BUY {sol_amount:.3f} SOL -> {sig[:16]}...")
                    else:
                        bal = trader.get_token_balance(self.token_mint)
                        if bal["raw"] > 1000:
                            sell_amount = int(bal["raw"] * random.uniform(0.1, 0.5))
                            sig = trader.sell_token(self.token_mint, sell_amount)
                            print(f"[Volume] SELL {sell_amount} tokens -> {sig[:16]}...")

                    self.stats["trades"] += 1
                    self.stats["volume_sol"] += sol_amount
                    time.sleep(random.randint(30, 120))
                except Exception as e:
                    print(f"[Volume] Trade error: {e}")
                    time.sleep(10)
            self.running = False

        threading.Thread(target=run_loop, daemon=True).start()
        return f"Volume bot started for {duration_minutes} min"

    def stop(self):
        self.running = False
        return f"Stopped. Trades: {self.stats['trades']}"

    def get_status(self):
        return {"running": self.running, "trades": self.stats["trades"], "volume_sol": self.stats["volume_sol"]}
