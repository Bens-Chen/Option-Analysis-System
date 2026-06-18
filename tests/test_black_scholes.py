from Methods.black_scholes import BS


def test_black_scholes_at_the_money_prices():
    call_price, put_price = BS(100, 100, 0.05, 0.0, 0.2, 1)

    assert round(call_price, 4) == 10.4506
    assert round(put_price, 4) == 5.5735
