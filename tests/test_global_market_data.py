from scanner.global_market_data import calculate_proxy


def test_calculate_proxy_builds_btcd_total2_and_others():
    global_payload = {
        "data": {
            "total_market_cap": {"usd": 1_000.0},
            "market_cap_change_percentage_24h_usd": 10.0,
        }
    }
    coins = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "market_cap": 500.0,
            "market_cap_rank": 1,
            "market_cap_change_percentage_24h": 25.0,
            "price_change_percentage_24h": 7.5,
        }
    ]
    coins += [
        {
            "id": f"coin-{rank}",
            "symbol": f"c{rank}",
            "market_cap": 10.0,
            "market_cap_rank": rank,
            "market_cap_change_percentage_24h": 0.0,
            "price_change_percentage_24h": 0.0,
        }
        for rank in range(2, 13)
    ]

    result = calculate_proxy(global_payload, coins)

    # /global의 1,000은 사용하지 않고 동일 응답의 상위 코인 시총 610만 합산한다.
    assert round(result["btc_d"]["value"], 2) == 81.97
    assert round(result["btc_d"]["change_24h_pct_point"], 2) == 3.54
    assert result["total2"]["value_usd"] == 110.0
    assert result["total2"]["change_24h_pct"] == 0.0
    assert result["others"]["value_usd"] == 20.0
    assert result["others"]["change_24h_pct"] == 0.0
    assert result["tracked_coin_count"] == 12
    assert result["source"] == "coingecko_top125_proxy"
    assert result["method_version"] == "top125-v2"
    assert result["is_exact_tradingview"] is False
