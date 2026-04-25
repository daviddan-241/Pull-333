import base64
import requests
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.transaction import VersionedTransaction
from spl.token.instructions import (
    get_associated_token_address, create_associated_token_account,
    mint_to, MintToParams, initialize_mint, InitializeMintParams
)
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.transaction import Transaction
from solders.system_program import CreateAccountParams, create_account
from solders.pubkey import Pubkey
from config import RPC_SOLANA, JUPITER_API_KEY, TOKEN_DECIMALS
from wallet_manager import wallet

client = Client(RPC_SOLANA)
kp = wallet.solana_keypair

class SolanaTrader:
    def __init__(self, keypair=None):
        self.keypair = keypair or kp
        self.wallet = str(self.keypair.pubkey()) if self.keypair else None
        self.client = Client(RPC_SOLANA)

    def get_sol_balance(self):
        try:
            return self.client.get_balance(self.keypair.pubkey()).value / 1e9
        except:
            return 0.0

    def get_token_balance(self, mint: str):
        try:
            mint_pk = Pubkey.from_string(mint)
            ata = get_associated_token_address(self.keypair.pubkey(), mint_pk)
            resp = self.client.get_token_account_balance(ata)
            if resp.value:
                return {"ui": resp.value.ui_amount or 0, "raw": int(resp.value.amount)}
            return {"ui": 0, "raw": 0}
        except:
            return {"ui": 0, "raw": 0}

    def get_quote(self, input_mint, output_mint, amount, slippage_bps=100):
        url = "https://api.jup.ag/swap/v1/quote"
        headers = {"x-api-key": JUPITER_API_KEY} if JUPITER_API_KEY else {}
        params = {"inputMint": input_mint, "outputMint": output_mint, "amount": amount, "slippageBps": slippage_bps}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        return resp.json()

    def execute_swap(self, quote: dict):
        url = "https://api.jup.ag/swap/v1/swap"
        headers = {"Content-Type": "application/json"}
        if JUPITER_API_KEY:
            headers["x-api-key"] = JUPITER_API_KEY
        payload = {"quoteResponse": quote, "userPublicKey": self.wallet, "wrapAndUnwrapSol": True}
        swap_resp = requests.post(url, headers=headers, json=payload, timeout=30)
        swap_data = swap_resp.json()
        raw_tx = base64.b64decode(swap_data["swapTransaction"])
        tx = VersionedTransaction.from_bytes(raw_tx)
        signed_tx = VersionedTransaction(tx.message, [self.keypair])
        opts = TxOpts(skip_preflight=False, preflight_commitment="confirmed")
        result = self.client.send_transaction(signed_tx, opts=opts)
        return str(result.value)

    def sell_token(self, token_mint: str, amount_raw: int):
        quote = self.get_quote(token_mint, "So11111111111111111111111111111111111111112", amount_raw)
        return self.execute_swap(quote)

    def buy_token(self, token_mint: str, sol_amount_lamports: int):
        quote = self.get_quote("So11111111111111111111111111111111111111112", token_mint, sol_amount_lamports)
        return self.execute_swap(quote)

    def send_sol(self, to_address: str, amount_lamports: int):
        from solders.system_program import transfer, TransferParams
        tx = Transaction()
        tx.add(transfer(TransferParams(
            from_pubkey=self.keypair.pubkey(),
            to_pubkey=Pubkey.from_string(to_address),
            lamports=amount_lamports
        )))
        tx.recent_blockhash = self.client.get_latest_blockhash().value.blockhash
        tx.sign(self.keypair)
        result = self.client.send_transaction(tx, self.keypair)
        return str(result.value)

class SolanaTokenManager:
    def __init__(self, keypair=None):
        self.keypair = keypair or kp
        self.client = Client(RPC_SOLANA)

    def create_mint(self, decimals=TOKEN_DECIMALS):
        mint_kp = Keypair()
        mint_len = 82
        rent = self.client.get_minimum_balance_for_rent_exemption(mint_len).value
        tx = Transaction()
        tx.add(create_account(CreateAccountParams(
            from_pubkey=self.keypair.pubkey(), to_pubkey=mint_kp.pubkey(),
            lamports=rent, space=mint_len, owner=TOKEN_PROGRAM_ID
        )))
        tx.add(initialize_mint(InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID, mint=mint_kp.pubkey(),
            decimals=decimals, mint_authority=self.keypair.pubkey(), freeze_authority=None
        )))
        tx.recent_blockhash = self.client.get_latest_blockhash().value.blockhash
        tx.sign(self.keypair, mint_kp)
        result = self.client.send_transaction(tx, self.keypair, mint_kp)
        return str(mint_kp.pubkey()), str(result.value)

    def mint_to_wallet(self, mint: str, amount: int, recipient=None):
        mint_pk = Pubkey.from_string(mint)
        recipient_pk = Pubkey.from_string(recipient) if recipient else self.keypair.pubkey()
        ata = get_associated_token_address(recipient_pk, mint_pk)
        if not self.client.get_account_info(ata).value:
            tx = Transaction()
            tx.add(create_associated_token_account(payer=self.keypair.pubkey(), owner=recipient_pk, mint=mint_pk))
            tx.recent_blockhash = self.client.get_latest_blockhash().value.blockhash
            tx.sign(self.keypair)
            self.client.send_transaction(tx, self.keypair)
        tx = Transaction()
        tx.add(mint_to(MintToParams(
            program_id=TOKEN_PROGRAM_ID, mint=mint_pk, dest=ata,
            authority=self.keypair.pubkey(), amount=amount
        )))
        tx.recent_blockhash = self.client.get_latest_blockhash().value.blockhash
        tx.sign(self.keypair)
        result = self.client.send_transaction(tx, self.keypair)
        return str(result.value)

class SolanaAnalytics:
    def get_holder_count(self, mint: str):
        try:
            url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "getProgramAccounts",
                "params": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    {"encoding": "jsonParsed", "filters": [{"dataSize": 165}, {"memcmp": {"offset": 0, "bytes": mint}}]}]
            }
            resp = requests.post(url, json=payload, timeout=60)
            data = resp.json()
            count = 0
            for acc in data.get("result", []):
                try:
                    if int(acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) > 0:
                        count += 1
                except:
                    continue
            return count
        except:
            return 0

    def get_token_price(self, mint: str):
        try:
            url = f"https://api.jup.ag/price/v2?ids={mint}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return float(data["data"][mint]["price"]) if "data" in data and mint in data["data"] else 0.0
        except:
            return 0.0
