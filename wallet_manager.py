"""
Real wallet derivation from a BIP39 seed phrase.
Solana keypair: m/44'/501'/0'/0' (Phantom-compatible)
Ethereum addr:  m/44'/60'/0'/0/0  (MetaMask-compatible)
"""
import os
import logging

from solders.keypair import Keypair
from bip_utils import (
    Bip39MnemonicGenerator, Bip39SeedGenerator, Bip39WordsNum,
    Bip44, Bip44Coins, Bip44Changes,
    Bip32Slip10Ed25519,
)

logger = logging.getLogger(__name__)


def _solana_keypair_from_seed(seed_bytes: bytes) -> Keypair:
    bip32 = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    derived = bip32.DerivePath("m/44'/501'/0'/0'")
    priv32 = derived.PrivateKey().Raw().ToBytes()
    return Keypair.from_seed(priv32)


def _ethereum_address_from_seed(seed_bytes: bytes) -> tuple[str, str]:
    bip44 = (
        Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        .Purpose().Coin().Account(0)
        .Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    )
    addr = bip44.PublicKey().ToAddress()
    priv_hex = bip44.PrivateKey().Raw().ToHex()
    return addr, priv_hex


class Wallet:
    def __init__(self, mnemonic: str):
        self.seed_phrase = mnemonic.strip()
        seed_bytes = Bip39SeedGenerator(self.seed_phrase).Generate()

        self.solana_keypair: Keypair = _solana_keypair_from_seed(seed_bytes)
        self.solana_pubkey: str = str(self.solana_keypair.pubkey())

        self.eth_address, self.eth_private_key = _ethereum_address_from_seed(seed_bytes)

    def get_all_addresses(self) -> dict:
        return {"solana": self.solana_pubkey, "ethereum": self.eth_address}


def _load_or_generate_mnemonic() -> str:
    mnemonic = os.getenv("SEED_PHRASE", "").strip()
    if mnemonic:
        return mnemonic

    new_mn = str(Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12))
    logger.warning("=" * 70)
    logger.warning("NO SEED_PHRASE ENV VAR - GENERATED A NEW WALLET FOR THIS RUN")
    logger.warning("SAVE THIS NOW or you'll lose access on next restart:")
    logger.warning(f'    SEED_PHRASE="{new_mn}"')
    logger.warning("Add it as an env var in Render, then redeploy.")
    logger.warning("=" * 70)
    return new_mn


wallet = Wallet(_load_or_generate_mnemonic())


def generate_volume_wallets(n: int = 5) -> list[Keypair]:
    """Generate N fresh ephemeral Keypairs for the volume bot."""
    return [Keypair() for _ in range(n)]
