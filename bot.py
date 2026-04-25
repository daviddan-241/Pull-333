import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from config import TELEGRAM_TOKEN, TOKEN_NAME, TOKEN_SYMBOL, TOKEN_DECIMALS, TOKEN_SUPPLY
from wallet_manager import wallet
from solana_client import SolanaTrader, SolanaTokenManager, SolanaAnalytics
from volume_bot import VolumeEngine

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

trader = SolanaTrader()
token_mgr = SolanaTokenManager()
analytics = SolanaAnalytics()
volume_engines = {}

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH", callback_data="m_launch"), InlineKeyboardButton("💰 WALLET", callback_data="m_wallet")],
        [InlineKeyboardButton("📊 ANALYTICS", callback_data="m_analytics"), InlineKeyboardButton("🔴 SELL", callback_data="m_sell")],
        [InlineKeyboardButton("🟢 BUY", callback_data="m_buy"), InlineKeyboardButton("💧 LIQUIDITY", callback_data="m_liquidity")],
        [InlineKeyboardButton("📈 VOLUME", callback_data="m_volume"), InlineKeyboardButton("🧮 PROFIT", callback_data="m_profit")],
    ])

def launch_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ CREATE TOKEN", callback_data="l_create")],
        [InlineKeyboardButton("🪙 MINT SUPPLY", callback_data="l_mint")],
        [InlineKeyboardButton("🌊 CREATE POOL", callback_data="l_pool")],
        [InlineKeyboardButton("🎯 AUTO LAUNCH", callback_data="l_auto")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def sell_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 25%", callback_data="s_25"), InlineKeyboardButton("🔥 50%", callback_data="s_50"), InlineKeyboardButton("🔥 100%", callback_data="s_100")],
        [InlineKeyboardButton("📉 CHUNKS", callback_data="s_chunks")],
        [InlineKeyboardButton("📊 BALANCE", callback_data="s_balance")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def buy_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 0.1 SOL", callback_data="b_0.1"), InlineKeyboardButton("💰 0.5 SOL", callback_data="b_0.5")],
        [InlineKeyboardButton("💰 1 SOL", callback_data="b_1.0"), InlineKeyboardButton("💰 2 SOL", callback_data="b_2.0")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def volume_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ START", callback_data="v_start")],
        [InlineKeyboardButton("⏹️ STOP", callback_data="v_stop")],
        [InlineKeyboardButton("📊 STATS", callback_data="v_stats")],
        [InlineKeyboardButton("💰 FUND WALLETS", callback_data="v_fund")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sol = trader.get_sol_balance()
    mint = context.user_data.get('mint', 'Not set')
    text = f"🤖 *{TOKEN_NAME} Bot*\n\n💼 `{wallet.solana_pubkey[:8]}...`\n💰 `{sol:.3f}` SOL\n🪙 `{mint[:8]}...`\n\nChoose:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/settoken <mint>`", parse_mode="Markdown")
        return
    context.user_data['mint'] = context.args[0]
    await update.message.reply_text(f"✅ Set: `{context.args[0]}`", parse_mode="Markdown")

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data
    user_id = update.effective_user.id
    mint = context.user_data.get('mint')

    if d == "m_main":
        await start(update, context)

    elif d == "m_wallet":
        sol = trader.get_sol_balance()
        text = f"💼 *Wallet*\n\nAddress: `{wallet.solana_pubkey}`\nBalance: `{sol:.4f}` SOL\n\nUse this address to deposit SOL."
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())

    elif d == "m_launch":
        text = f"🚀 *Launch Center*\n\nToken: *{TOKEN_NAME}* ({TOKEN_SYMBOL})\nSupply: `{TOKEN_SUPPLY:,}`\n\nCreate your token, mint supply, then add liquidity."
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_create":
        await query.edit_message_text("⏳ Creating token mint...", reply_markup=None)
        try:
            mint_addr, tx = token_mgr.create_mint()
            context.user_data['mint'] = mint_addr
            text = f"✅ *Token Created!*\n\nMint: `{mint_addr}`\nTx: `{tx[:20]}...`\n\nNext: Mint your supply."
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🪙 MINT SUPPLY", callback_data="l_mint")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")]
            ])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_mint":
        if not mint:
            await query.edit_message_text("❌ Create token first!", reply_markup=launch_kb())
            return
        await query.edit_message_text(f"⏳ Minting {TOKEN_SUPPLY:,} {TOKEN_SYMBOL}...", reply_markup=None)
        try:
            amount = TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS)
            tx = token_mgr.mint_to_wallet(mint, amount)
            text = f"✅ *Supply Minted!*\n\nAmount: `{TOKEN_SUPPLY:,}` {TOKEN_SYMBOL}\nTx: `{tx[:20]}...`\n\nYour wallet now holds the full supply."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=launch_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_pool":
        if not mint:
            await query.edit_message_text("❌ Create token first!", reply_markup=launch_kb())
            return
        text = (f"🌊 *Create Liquidity Pool*\n\n"
                f"Token: `{mint}`\n\n"
                f"Use Smithii to create your Raydium pool:\n"
                f"• Connect your wallet\n"
                f"• Add 2-5 SOL + tokens\n"
                f"• Set initial price\n\n"
                f"[Open Smithii](https://tools.smithii.io/liquidity-pool/solana?base={mint})")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 OPEN SMITHII", url=f"https://tools.smithii.io/liquidity-pool/solana?base={mint}")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "l_auto":
        await query.edit_message_text("🚀 Auto launching...", reply_markup=None)
        try:
            mint_addr, _ = token_mgr.create_mint()
            context.user_data['mint'] = mint_addr
            amount = TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS)
            token_mgr.mint_to_wallet(mint_addr, amount)
            text = (f"✅ *Auto Launch Complete!*\n\n"
                    f"Mint: `{mint_addr}`\n"
                    f"Supply: `{TOKEN_SUPPLY:,}` {TOKEN_SYMBOL}\n\n"
                    f"Next: Create liquidity pool via Liquidity menu.")
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "m_sell":
        if not mint:
            await query.edit_message_text("❌ Set token first with `/settoken <mint>`", parse_mode="Markdown", reply_markup=main_kb())
            return
        bal = trader.get_token_balance(mint)
        price = analytics.get_token_price(mint)
        value = bal['ui'] * price
        text = (f"🔴 *Sell Dashboard*\n\n"
                f"Token: `{mint[:10]}...`\n"
                f"Your Balance: `{bal['ui']:,.2f}`\n"
                f"Price: `${price:.8f}`\n"
                f"Value: `${value:.2f}`\n\n"
                f"Select sell amount:")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "s_balance":
        if not mint:
            await query.edit_message_text("❌ No token set!", reply_markup=sell_kb())
            return
        bal = trader.get_token_balance(mint)
        price = analytics.get_token_price(mint)
        text = (f"💼 *Your Balance*\n\n"
                f"Tokens: `{bal['ui']:,.2f}`\n"
                f"Price: `${price:.8f}`\n"
                f"Value: `${bal['ui'] * price:.2f}`")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())

    elif d in ["s_25", "s_50", "s_100"]:
        if not mint:
            await query.edit_message_text("❌ No token set!", reply_markup=sell_kb())
            return
        pct = int(d.split("_")[1])
        bal = trader.get_token_balance(mint)
        if bal['raw'] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb())
            return
        amount = int(bal['raw'] * pct / 100)
        await query.edit_message_text(f"⏳ Selling {pct}%...", reply_markup=None)
        try:
            sig = trader.sell_token(mint, amount)
            new_bal = trader.get_token_balance(mint)
            text = (f"✅ *Sold {pct}%!*\n\n"
                    f"Tx: `{sig}`\n"
                    f"Remaining: `{new_bal['ui']:,.2f}`")
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "s_chunks":
        if not mint:
            await query.edit_message_text("❌ No token set!", reply_markup=sell_kb())
            return
        bal = trader.get_token_balance(mint)
        if bal['raw'] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb())
            return
        await query.edit_message_text("⏳ DCA selling in 5 chunks...", reply_markup=None)
        try:
            import asyncio
            sigs = []
            chunk = bal['raw'] // 5
            for i in range(5):
                sig = trader.sell_token(mint, chunk)
                sigs.append(sig)
                if i < 4:
                    await asyncio.sleep(4)
            text = f"✅ *DCA Complete!*\n\n" + "\n".join([f"`{s[:20]}...`" for s in sigs])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "m_buy":
        if not mint:
            await query.edit_message_text("❌ Set token first with `/settoken <mint>`", parse_mode="Markdown", reply_markup=main_kb())
            return
        price = analytics.get_token_price(mint)
        text = (f"🟢 *Buy Dashboard*\n\n"
                f"Token: `{mint[:10]}...`\n"
                f"Price: `${price:.8f}`\n"
                f"Your SOL: `{trader.get_sol_balance():.3f}`\n\n"
                f"Select amount:")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buy_kb())

    elif d in ["b_0.1", "b_0.5", "b_1.0", "b_2.0"]:
        if not mint:
            await query.edit_message_text("❌ No token set!", reply_markup=buy_kb())
            return
        sol_amt = float(d.split("_")[1])
        await query.edit_message_text(f"⏳ Buying with {sol_amt} SOL...", reply_markup=None)
        try:
            sig = trader.buy_token(mint, int(sol_amt * 1e9))
            text = f"✅ *Bought!*\n\nTx: `{sig}`"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buy_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=buy_kb())

    elif d == "m_volume":
        running = user_id in volume_engines and volume_engines[user_id].running
        text = (f"📈 *Volume Bot*\n\n"
                f"Generate fake trading activity with 5 burner wallets.\n\n"
                f"Status: {'🟢 Running' if running else '🔴 Stopped'}")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())

    elif d == "v_start":
        if not mint:
            await query.edit_message_text("❌ Set token first!", reply_markup=volume_kb())
            return
        if user_id in volume_engines and volume_engines[user_id].running:
            await query.edit_message_text("Already running!", reply_markup=volume_kb())
            return
        engine = VolumeEngine(mint, wallet.solana_keypair)
        engine.fund_wallets(0.3)
        result = engine.start(duration_minutes=60, buy_ratio=0.6)
        volume_engines[user_id] = engine
        await query.edit_message_text(f"▶️ {result}", reply_markup=volume_kb())

    elif d == "v_stop":
        if user_id in volume_engines:
            stats = volume_engines[user_id].stop()
            await query.edit_message_text(f"⏹️ {stats}", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Not running", reply_markup=volume_kb())

    elif d == "v_stats":
        if user_id in volume_engines:
            stats = volume_engines[user_id].get_status()
            text = (f"📊 *Volume Stats*\n\n"
                    f"Running: {'Yes' if stats['running'] else 'No'}\n"
                    f"Trades: `{stats['trades']}`\n"
                    f"Volume: `{stats['volume_sol']:.2f}` SOL")
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())
        else:
            await query.edit_message_text("No active session", reply_markup=volume_kb())

    elif d == "v_fund":
        if user_id in volume_engines:
            volume_engines[user_id].fund_wallets(0.5)
            await query.edit_message_text("💰 Wallets funded!", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Start volume bot first", reply_markup=volume_kb())

    elif d == "m_analytics":
        if not mint:
            await query.edit_message_text("❌ Set token first with `/settoken <mint>`", parse_mode="Markdown", reply_markup=main_kb())
            return
        await query.edit_message_text("⏳ Fetching data...", reply_markup=None)
        try:
            count = analytics.get_holder_count(mint)
            price = analytics.get_token_price(mint)
            text = (f"📊 *Analytics*\n\n"
                    f"Token: `{mint[:10]}...`\n"
                    f"Holders: `{count}`\n"
                    f"Price: `${price:.8f}`\n\n"
                    f"[View on Solscan](https://solscan.io/token/{mint})")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 REFRESH", callback_data="m_analytics")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")]
            ])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown", reply_markup=main_kb())

    elif d == "m_liquidity":
        if not mint:
            await query.edit_message_text("❌ Set token first with `/settoken <mint>`", parse_mode="Markdown", reply_markup=main_kb())
            return
        text = (f"💧 *Liquidity*\n\n"
                f"Token: `{mint}`\n\n"
                f"Options:\n"
                f"• Create pool on Smithii\n"
                f"• View existing pools")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 CREATE POOL", url=f"https://tools.smithii.io/liquidity-pool/solana?base={mint}")],
            [InlineKeyboardButton("🔍 VIEW ON SOLSCAN", url=f"https://solscan.io/token/{mint}")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "m_profit":
        text = (f"🧮 *Profit Calculator*\n\n"
                f"*Scenario:*\n"
                f"• You create token (free)\n"
                f"• Mint 90% to yourself (free)\n"
                f"• Add 2 SOL + 10% to LP\n"
                f"• 10 buyers x $40 = $400\n"
                f"• You dump 90% of supply\n\n"
                f"*Result:*\n"
                f"• Pool grows to ~4.67 SOL ($700)\n"
                f"• You extract: ~$668\n"
                f"• Minus LP cost: $300\n"
                f"• *Net profit: ~$368*\n\n"
                f"⚠️ *Rule:* NEVER add YOUR money to LP if you plan to dump.\n"
                f"Let someone else provide liquidity.")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())

def run_bot():
    if not TELEGRAM_TOKEN:
        print("[BOT ERROR] No TELEGRAM_TOKEN!")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settoken", set_token))
    app.add_handler(CallbackQueryHandler(router))
    print("[BOT] Starting polling...")
    app.run_polling()
