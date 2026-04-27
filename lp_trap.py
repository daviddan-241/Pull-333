"""LP-trap explanation + math."""
from profit_calc import calculate_custom_scenario


def explain_lp_trap() -> str:
    return (
        "🪤 *The LP Trap*\n\n"
        "When YOU provide the liquidity for your own token:\n"
        "1. Your SOL gets locked in the pool.\n"
        "2. As others buy, the pool's token side shrinks but its SOL "
        "side grows - but you own that pool.\n"
        "3. When you dump your bag, your sell drains pool SOL.\n"
        "4. The LP you get back is mostly worthless tokens + a fraction "
        "of the SOL that's left.\n\n"
        "*Net:* you funded everyone else's exit ramp. Big LP = big trap.\n\n"
        "Use Pump.fun bonding curves or partner LP instead."
    )


def calculate_lp_vs_no_lp(budget_usd: float = 5.0, sol_price: float = 200.0) -> dict:
    others = budget_usd * 80

    with_lp = calculate_custom_scenario(
        budget_usd, 90, 10, others, lp_sol=10.0, sol_price_usd=sol_price
    )
    no_lp = calculate_custom_scenario(
        budget_usd, 50, 10, others, lp_sol=0.001, sol_price_usd=sol_price
    )

    return {
        "with_lp": with_lp,
        "no_lp": no_lp,
        "delta_usd": no_lp["profit_usd"] - with_lp["profit_usd"],
        "lp_locked_usd": 10.0 * sol_price,
    }


def format_lp_trap_report(c: dict) -> str:
    return (
        "🪤 *LP Trap - Math*\n\n"
        f"WITH big LP:  profit `${c['with_lp']['profit_usd']:,.2f}`\n"
        f"WITHOUT LP:   profit `${c['no_lp']['profit_usd']:,.2f}`\n\n"
        f"*Difference:* `${c['delta_usd']:,.2f}` MORE without LP\n"
        f"*LP you'd lock:* `${c['lp_locked_usd']:,.2f}`\n\n"
        "Every dollar of LP you provide is a dollar funding "
        "someone else's exit. Avoid the trap."
    )
