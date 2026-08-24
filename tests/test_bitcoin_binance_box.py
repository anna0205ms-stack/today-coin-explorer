from scanner.bitcoin_regime import analyze_binance_box


def test_binance_box_uses_completed_btcusdt_prices():
    daily=[]
    for i in range(30):
        close=80_000+i*100
        daily.append([i, str(close-100), str(close+500), str(close-500), str(close), "10", i+1])
    four=[[0,"0","0","0","82000","1",1_800_000]]

    result=analyze_binance_box(daily, four)

    assert result["market"] == "BINANCE:BTCUSDT"
    assert result["price"] == 82_900
    assert result["box"]["high"] < 100_000
    assert result["box"]["buy_zone"][0] == result["box"]["low"]
