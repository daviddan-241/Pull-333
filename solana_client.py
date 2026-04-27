"""
Real Solana client: balance reads, SPL token ops, Jupiter swaps,
holder count + price via Jupiter / DexScreener / Helius.

Trades automatically route through Pump.fun (PumpPortal) for
pre-graduation pump.fun tokens, otherwise through Jupiter.
"""
import os
import base64
import logging
import requests

from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import Message
from solders.system_program import CreateAccountParams, create_account
from solders.transaction import Transaction as SoldersLegacyTx

from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    initialize_mint, InitializeMintParams,
    create_associated_token_account,
    mint_to_checked, MintToCheckedParams,
    get_associated_token_address,
)

from wallet_manager import wallet

logger = logging.getLogger(__name__)

RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP = "https://quote-api.jup.ag/v6/swap"
JUPITER_PRICE = "https://api.jup.ag/price/v2"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"
SOL_MINT = "So11111111111111111111111111111111111111112"
DEFAULT_DECIMALS = int(os.getenv("TOKEN_DECIMALS", "9"))

_client = Client(RPC_URL, commitment=Confirmed)


class SolanaTrader:
    def __init__(self, payer: Keypair | None = None):
        self.payer = payer or wallet.solana_keypair
        self.pubkey = self.payer.pubkey()

    def get_sol_balance(self) -> float:
        try:
            return _client.get_balance(self.pubkey).value / 1_000_000_000
        except Exception as e:
            logger.warning(f"get_sol_balance failed: {e}")
            return 0.0

    def get_token_balance(self, mint_str: str) -> dict:
        try:
            mint = Pubkey.from_string(mint_str)
            ata = get_associated_token_address(self.pubkey, mint)
            v = _client.get_token_account_balance(ata).value
            return {"ui": float(v.ui_amount or 0), "raw": int(v.amount), "decimals": int(v.decimals)}
        except Exception:
            return {"ui": 0.0, "raw": 0, "decimals": DEFAULT_DECIMALS}

    def _jupiter_swap(self, input_mint: str, output_mint: str,
                      amount_raw: int, slippage_bps: int = 100) -> str:
        q = requests.get(JUPITER_QUOTE, params={
            "inputMint": input_mint, "outputMint": output_mint,
            "amount": amount_raw, "slippageBps": slippage_bps,
            "swapMode": "ExactIn",
        }, timeout=20)
        q.raise_for_status()
        quote = q.json()
        if "error" in quote:
            raise RuntimeError(f"Jupiter quote: {quote['error']}")

        s = requests.post(JUPITER_SWAP, json={
            "quoteResponse": quote,
            "userPublicKey": str(self.pubkey),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": "auto",
        }, timeout=20)
        s.raise_for_status()
        raw = base64.b64decode(s.json()["swapTransaction"])
        vtx = VersionedTransaction.from_bytes(raw)
        signed = VersionedTransaction(vtx.message, [self.payer])
        sig = _client.send_raw_transaction(bytes(signed), opts=TxOpts(skip_preflight=False)).value
        return str(sig)

    def buy_token(self, mint_str: str, lamports: int) -> str:
        # Auto-route pre-graduation pump.fun → PumpPortal
        try:
            from pumpfun_client import is_pumpfun_pre_graduation, PumpFunTrader
            if is_pumpfun_pre_graduation(mint_str):
                logger.info(f"[ROUTE] {mint_str[:10]}... → PumpPortal (pre-grad)")
                return PumpFunTrader(self.payer).buy(mint_str, lamports / 1e9)
        except Exception as e:
            logger.warning(f"pumpfun route check failed, falling back to Jupiter: {e}")
        return self._jupiter_swap(SOL_MINT, mint_str, lamports)

    def sell_token(self, mint_str: str, raw_amount: int) -> str:
        try:
            from pumpfun_client import is_pumpfun_pre_graduation, PumpFunTrader
            if is_pumpfun_pre_graduation(mint_str):
                bal = self.get_token_balance(mint_str)
                decimals = bal["decimals"] or 6
                ui_amount = raw_amount / (10 ** decimals)
                logger.info(f"[ROUTE] sell {mint_str[:10]}... → PumpPortal")
                return PumpFunTrader(self.payer).sell(mint_str, ui_amount)
        except Exception as e:
            logger.warning(f"pumpfun route check failed, falling back to Jupiter: {e}")
        return self._jupiter_swap(mint_str, SOL_MINT, raw_amount)


class SolanaTokenManager:
    def __init__(self, payer: Keypair | None = None, decimals: int = DEFAULT_DECIMALS):
        self.payer = payer or wallet.solana_keypair
        self.pubkey = self.payer.pubkey()
        self.decimals = decimals

    def create_mint(self) -> tuple[str, str]:
        mint_kp = Keypair()
        lamports = _client.get_minimum_balance_for_rent_exemption(82).value
        ix_create = create_account(CreateAccountParams(
            from_pubkey=self.pubkey, to_pubkey=mint_kp.pubkey(),
            lamports=lamports, space=82, owner=TOKEN_PROGRAM_ID,
        ))
        ix_init = initialize_mint(InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID, mint=mint_kp.pubkey(),
            decimals=self.decimals, mint_authority=self.pubkey,
            freeze_authority=self.pubkey,
        ))
        bh = _client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix_create, ix_init], self.pubkey, bh)
        tx = SoldersLegacyTx([self.payer, mint_kp], msg, bh)
        sig = _client.send_raw_transaction(bytes(tx), opts=TxOpts(skip_preflight=False)).value
        return str(mint_kp.pubkey()), str(sig)

    def mint_to_wallet(self, mint_str: str, amount_raw: int) -> str:
        mint = Pubkey.from_string(mint_str)
        ata = get_associated_token_address(self.pubkey, mint)
        ixs = []
        if _client.get_account_info(ata).value is None:
            ixs.append(create_associated_token_account(self.pubkey, self.pubkey, mint))
        ixs.append(mint_to_checked(MintToCheckedParams(
            program_id=TOKEN_PROGRAM_ID, mint=mint, dest=ata,
            mint_authority=self.pubkey, amount=amount_raw, decimals=self.decimals,
        )))
        bh = _client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash(ixs, self.pubkey, bh)
        tx = SoldersLegacyTx([self.payer], msg, bh)
        sig = _client.send_raw_transaction(bytes(tx), opts=TxOpts(skip_preflight=False)).value
        return str(sig)


class SolanaAnalytics:
    def get_holder_count(self, mint_str: str) -> int:
        helius = os.getenv("HELIUS_RPC_URL")
        if helius:
            try:
                r = requests.post(helius, json={
                    "jsonrpc": "2.0", "id": 1, "method": "getTokenAccounts",
                    "params": {"mint": mint_str, "limit": 1000},
                }, timeout=20)
                data = r.json().get("result", {})
                return int(data.get("total", len(data.get("token_accounts", []))))
            except Exception as e:
                logger.warning(f"Helius holder count failed: {e}")
        try:
            resp = _client.get_token_largest_accounts(Pubkey.from_string(mint_str))
            return sum(1 for a in resp.value if int(a.amount.amount) > 0)
        except Exception:
            return 0

    def get_token_price(self, mint_str: str) -> float:
        try:
            r = requests.get(JUPITER_PRICE, params={"ids": mint_str}, timeout=10)
            data = r.json().get("data", {}).get(mint_str)
            if data and data.get("price"):
                return float(data["price"])
        except Exception:
            pass
        try:
            r = requests.get(f"{DEXSCREENER_TOKEN}/{mint_str}", timeout=10)
            pairs = r.json().get("pairs") or []
            if pairs:
                return float(pairs[0].get("priceUsd") or 0.0)
        except Exception:
            pass
        return 0.0
