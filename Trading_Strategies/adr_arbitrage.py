def adr_premium_ratio(adr_price_usd, local_share_price, shares_per_adr, exchange_rate):
    adr_value_local = adr_price_usd * exchange_rate
    local_package_value = local_share_price * shares_per_adr
    return (adr_value_local - local_package_value) / local_package_value


def adr_signal(
    premium_ratio,
    long_term_average,
    upper_bound,
    lower_bound,
):
    if lower_bound >= long_term_average or long_term_average >= upper_bound:
        raise ValueError("Expected lower_bound < long_term_average < upper_bound.")

    if premium_ratio >= upper_bound:
        return {
            "signal": "long_local_short_adr",
            "reason": "ADR is expensive relative to local shares.",
            "close_when": "premium_ratio returns to long_term_average",
        }

    if premium_ratio <= lower_bound:
        return {
            "signal": "short_local_long_adr",
            "reason": "ADR is cheap relative to local shares.",
            "close_when": "premium_ratio returns to long_term_average",
        }

    return {
        "signal": "hold",
        "reason": "premium ratio is inside the no-trade band.",
        "close_when": None,
    }
