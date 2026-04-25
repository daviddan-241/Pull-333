from mnemonic import Mnemonic
from solders.keypair import Keypair
from eth_account import Account
import hashlib
from config import SEED_PHRASE, PRIVATE_KEY_SOL

class MultiChainWallet:
    def __init__(self):
        self._sol_keypair = None
        if SEED_PHRASE:
            try:
                mnemo = Mnemonic("english")
                seed = mnemo.to_seed(SEED_PHRASE)
                sol_seed = hashlib.sha256(seed + b"solana").digest()
                self._sol_keypair = Keypair.from_seed(sol_seed[:32])
            except Exception as e:
                print(f"[Wallet] Seed error: {e}")
        elif PRIVATE_KEY_SOL:
            try:
                self._sol_keypair = Keypair.from_base58_string(PRIVATE_KEY_SOL)
            except Exception as e:
                print(f"[Wallet] Key error: {e}")

    @property
    def solana_keypair(self):
        return self._sol_keypair

    @property
    def solana_pubkey(self):
        return str(self._sol_keypair.pubkey()) if self._sol_keypair else "Not set"

wallet = MultiChainWallet()
