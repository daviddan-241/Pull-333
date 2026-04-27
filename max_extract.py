"""Compare extraction strategies side-by-side using the same AMM math."""
from profit_calc import calculate_custom_scenario


def calculate_all_strategies(budget_usd: float, sol_price_usd: float = 200.0) -> dict:
    others = budget_usd * 80

    pf = calculate_custom_scenario(budget_usd, 50, 10, others, 0.001, sol_price_usd)
    minimal = calculate_custom_scenario(budget_usd, 90, 10, others, 2.0, sol_price_usd)
    big = calculate_custom_scenario(budget_usd, 90, 10, others, 10.0, sol_price_usd)
    partner = calculate_custom_scenario(budget_usd, 90, 10, others, 0.001, sol_price_usd)

    return {
        "pumpfun_only": pf,
        "minimal_lp": minimal,
        "big_lp_trap": big,
        "partner_lp": partner,
    }


def format_extraction_report(results: dict) -> str:
    rows = [
        ("Pump.fun only", results["pumpfun_only"]),
        ("Minimal LP (2 SOL)", results["minimal_lp"]),
        ("Big LP (10 SOL)", results["big_lp_trap"]),
        ("Partner LP", results["partner_lp"]),
    ]
    lines = ["💎 *Extraction Comparison*\n"]
    for name, r in rows:
        lines.append(
            f"*{name}*\n"
            f"  Cost: `${r['cost_usd']:,.0f}` | "
            f"Revenue: `${r['revenue_usd']:,.0f}` | "
            f"*Profit: ${r['profit_usd']:,.0f}*\n"
        )
    best = max(rows, key=lambda x: x[1]["profit_usd"])
    lines.append(f"\n🏆 Best: *{best[0]}* (`${best[1]['profit_usd']:,.0f}`)")
    return "\n".join(lines)


def calculate_5_dollar_strategy() -> str:
    return format_extraction_report(calculate_all_strategies(budget_usd=5.0))
