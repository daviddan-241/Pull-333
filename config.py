import os
from dotenv import load_dotenv

load_dotenv()

SEED_PHRASE = os.getenv("SEED_PHRASE")
PRIVATE_KEY_SOL = os.getenv("PRIVATE_KEY_SOL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
JUPITER_API_KEY = os.getenv("JUPITER_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
RPC_SOLANA = os.getenv("RPC_SOLANA", "https://api.mainnet-beta.solana.com")
TOKEN_NAME = os.getenv("TOKEN_NAME", "MyToken")
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "MTK")
TOKEN_DECIMALS = int(os.getenv("TOKEN_DECIMALS", "9"))
TOKEN_SUPPLY = int(os.getenv("TOKEN_SUPPLY", "1000000000"))
