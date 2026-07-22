import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from validators import _extract_price_numbers, _extract_target_price_numbers  # noqa: E402


def test_extract_price_numbers_accepts_twd_words():
    assert _extract_price_numbers("基本情境目標價 TWD 1,000") == [1000.0]
    assert _extract_price_numbers("12個月目標：新台幣 1000 元") == [1000.0]
    assert _extract_price_numbers("合理價約台幣1,250.5元") == [1250.5]


def test_extract_price_numbers_rejects_non_finite_scientific_prices():
    assert _extract_price_numbers("12個月目標：NT$1e309") == []
    assert _extract_price_numbers("區間：NT$1e2-NT$1e309") == [100.0]


def test_extract_price_numbers_keeps_currency_led_range_endpoint():
    assert _extract_price_numbers("12個月目標：NT$100-160") == [100.0, 160.0]
    assert _extract_price_numbers("12個月目標：NT$1e2-1.6e2") == [100.0, 160.0]


def test_extract_price_numbers_keeps_currency_led_en_dash_range_endpoint():
    assert _extract_price_numbers("12個月目標：NT$100–160") == [100.0, 160.0]
    assert _extract_price_numbers("12個月目標：NT$100—160") == [100.0, 160.0]


def test_extract_price_numbers_keeps_currency_led_fullwidth_minus_range_endpoint():
    assert _extract_price_numbers("12個月目標：NT$100－160") == [100.0, 160.0]
    assert _extract_price_numbers("12個月目標：NT$100−160") == [100.0, 160.0]


def test_extract_price_numbers_keeps_currency_led_wave_dash_range_endpoint():
    assert _extract_price_numbers("12個月目標：NT$100〜160") == [100.0, 160.0]
    assert _extract_price_numbers("12個月目標：NT$1e2〜1.6e2") == [100.0, 160.0]


def test_extract_price_numbers_accepts_fullwidth_number_punctuation():
    assert _extract_price_numbers("12個月目標：NT$１，０００") == [1000.0]
    assert _extract_price_numbers("12個月目標：NT$１２３．４５") == [123.45]
    assert _extract_price_numbers("12個月目標：NT$１，０００〜１，６００") == [1000.0, 1600.0]


def test_extract_price_numbers_keeps_unit_suffixed_range_endpoint():
    assert _extract_price_numbers("12個月目標價：100-160元") == [100.0, 160.0]
    assert _extract_price_numbers("合理價約100元至160元") == [100.0, 160.0]


def test_extract_price_numbers_keeps_left_unit_range_endpoint():
    assert _extract_price_numbers("12個月目標價：100元-160") == [100.0, 160.0]
    assert _extract_price_numbers("合理價約100塊到160") == [100.0, 160.0]


def test_extract_price_numbers_keeps_right_currency_range_endpoint():
    assert _extract_price_numbers("12個月目標價：100至NT$160") == [100.0, 160.0]
    assert _extract_price_numbers("合理價約100到台幣160") == [100.0, 160.0]


def test_extract_price_numbers_keeps_currency_range_order_with_other_prices():
    assert _extract_price_numbers("目標價 NT$100-160，現價 NT$80") == [100.0, 160.0, 80.0]


def test_extract_price_numbers_ignores_period_prefix_before_target_range():
    assert _extract_price_numbers("12個月目標價 100-160") == [100.0, 160.0]
    assert _extract_price_numbers("2027年目標價100-160") == [100.0, 160.0]
    assert _extract_price_numbers("12M target 100-160") == [100.0, 160.0]


def test_extract_price_numbers_accepts_english_to_target_range():
    assert _extract_price_numbers("12M target price 100 to 160") == [100.0, 160.0]
    assert _extract_price_numbers("2027 target price 100 to 160") == [100.0, 160.0]
    assert _extract_price_numbers("price target 100 to NT$160") == [100.0, 160.0]


def test_extract_price_numbers_accepts_between_target_range():
    assert _extract_price_numbers("target price between 100 and 160") == [100.0, 160.0]
    assert _extract_price_numbers("12M target between 100 and 160") == [100.0, 160.0]
    assert _extract_price_numbers("12個月目標價介於100與160元") == [100.0, 160.0]
    assert _extract_price_numbers("合理價落在100與160元之間") == [100.0, 160.0]


def test_extract_price_numbers_accepts_positive_signed_currency_price():
    assert _extract_price_numbers("12個月目標價 NT$+160") == [160.0]
    assert _extract_price_numbers("12個月目標價 NT$＋160") == [160.0]


def test_extract_target_price_numbers_ignore_non_price_metrics_and_horizons():
    assert _extract_target_price_numbers("EPS目標10元") == []
    assert _extract_target_price_numbers("目標市值160億元") == []
    assert _extract_target_price_numbers("target price based on revenue target 160B") == []
    assert _extract_target_price_numbers("目標報酬率20") == []
    assert _extract_target_price_numbers("target return 20") == []
    assert _extract_target_price_numbers("target probability 70") == []
    assert _extract_target_price_numbers("目標排名1") == []
    assert _extract_target_price_numbers("target confidence score 8") == []
    assert _extract_target_price_numbers("目標價為現價的1.6倍") == []
    assert _extract_target_price_numbers("target price is 1.6x current price") == []
    assert _extract_target_price_numbers("目標價約20倍本益比") == []
    assert _extract_target_price_numbers("target price based on 16x PE and EPS NT$10") == []
    assert _extract_target_price_numbers("目標股利5元") == []
    assert _extract_target_price_numbers("股息目標5元") == []
    assert _extract_target_price_numbers("target dividend NT$5") == []
    assert _extract_target_price_numbers("target EBITDA NT$160M") == []
    assert _extract_target_price_numbers("EBITDA target NT$160M") == []
    assert _extract_target_price_numbers("target net income NT$160M") == []
    assert _extract_target_price_numbers("net profit target NT$160M") == []
    assert _extract_target_price_numbers("target operating income NT$160M") == []
    assert _extract_target_price_numbers("operating profit target NT$160M") == []
    assert _extract_target_price_numbers("target gross profit NT$160M") == []
    assert _extract_target_price_numbers("target pretax income NT$160M") == []
    assert _extract_target_price_numbers("目標淨利160億") == []
    assert _extract_target_price_numbers("目標營業利益160億") == []
    assert _extract_target_price_numbers("目標毛利160億") == []
    assert _extract_target_price_numbers("稅前淨利目標160億") == []
    assert _extract_target_price_numbers("目標估值160億元") == []
    assert _extract_target_price_numbers("估值目標160億元") == []
    assert _extract_target_price_numbers("target valuation NT$160B") == []
    assert _extract_target_price_numbers("enterprise value target NT$160B") == []
    assert _extract_target_price_numbers("EV target NT$160B") == []
    assert _extract_target_price_numbers("目標企業價值160億元") == []
    assert _extract_target_price_numbers("target gross margin 45") == []
    assert _extract_target_price_numbers("目標毛利率45") == []
    assert _extract_target_price_numbers("ROE target 20") == []
    assert _extract_target_price_numbers("target ROIC 15") == []
    assert _extract_target_price_numbers("target P/E 20") == []
    assert _extract_target_price_numbers("目標本益比20") == []
    assert _extract_target_price_numbers("target reserve replacement ratio 120") == []
    assert _extract_target_price_numbers("reserve replacement ratio target 120") == []
    assert _extract_target_price_numbers("target claims ratio 60") == []
    assert _extract_target_price_numbers("claims ratio target 60") == []
    assert _extract_target_price_numbers("target combined ratio 95") == []
    assert _extract_target_price_numbers("combined ratio target 95") == []
    assert _extract_target_price_numbers("target loss ratio 65") == []
    assert _extract_target_price_numbers("loss ratio target 65") == []
    assert _extract_target_price_numbers("目標儲量替換率120") == []
    assert _extract_target_price_numbers("理賠率目標60") == []
    assert _extract_target_price_numbers("綜合成本率目標95") == []
    assert _extract_target_price_numbers("賠付率目標65") == []
    assert _extract_target_price_numbers("損失率目標65") == []
    assert _extract_target_price_numbers("target expense ratio 30") == []
    assert _extract_target_price_numbers("expense ratio target 30") == []
    assert _extract_target_price_numbers("target solvency ratio 200") == []
    assert _extract_target_price_numbers("solvency ratio target 200") == []
    assert _extract_target_price_numbers("target coverage ratio 180") == []
    assert _extract_target_price_numbers("coverage ratio target 180") == []
    assert _extract_target_price_numbers("target loan-to-deposit ratio 80") == []
    assert _extract_target_price_numbers("loan-to-deposit ratio target 80") == []
    assert _extract_target_price_numbers("target LDR 80") == []
    assert _extract_target_price_numbers("cost-to-income ratio target 45") == []
    assert _extract_target_price_numbers("費用率目標30") == []
    assert _extract_target_price_numbers("償付能力比率目標200") == []
    assert _extract_target_price_numbers("覆蓋率目標180") == []
    assert _extract_target_price_numbers("成本收入比目標45") == []
    assert _extract_target_price_numbers("存放比目標80") == []
    assert _extract_target_price_numbers("target Tier 1 ratio 12") == []
    assert _extract_target_price_numbers("Tier 1 capital ratio target 12") == []
    assert _extract_target_price_numbers("target total capital ratio 14") == []
    assert _extract_target_price_numbers("capital ratio target 14") == []
    assert _extract_target_price_numbers("LCR target 120") == []
    assert _extract_target_price_numbers("target net stable funding ratio 110") == []
    assert _extract_target_price_numbers("NSFR target 110") == []
    assert _extract_target_price_numbers("target liquidity ratio 120") == []
    assert _extract_target_price_numbers("target current ratio 2.0") == []
    assert _extract_target_price_numbers("quick ratio target 1.5") == []
    assert _extract_target_price_numbers("一級資本比率目標12") == []
    assert _extract_target_price_numbers("資本比率目標14") == []
    assert _extract_target_price_numbers("淨穩定資金比率目標110") == []
    assert _extract_target_price_numbers("流動比率目標2.0") == []
    assert _extract_target_price_numbers("速動比率目標1.5") == []
    assert _extract_target_price_numbers("USD/TWD target 32") == []
    assert _extract_target_price_numbers("target USD/TWD 32") == []
    assert _extract_target_price_numbers("exchange rate target 32") == []
    assert _extract_target_price_numbers("target exchange rate 32") == []
    assert _extract_target_price_numbers("FX rate target 32") == []
    assert _extract_target_price_numbers("target FX rate 32") == []
    assert _extract_target_price_numbers("USDJPY target 150") == []
    assert _extract_target_price_numbers("USD/JPY target 150") == []
    assert _extract_target_price_numbers("美元兌台幣目標32") == []
    assert _extract_target_price_numbers("美元台幣目標32") == []
    assert _extract_target_price_numbers("匯率目標32") == []
    assert _extract_target_price_numbers("美元日圓目標150") == []
    assert _extract_target_price_numbers("yield curve target 100") == []
    assert _extract_target_price_numbers("target inflation 2") == []
    assert _extract_target_price_numbers("inflation rate target 2") == []
    assert _extract_target_price_numbers("CPI target 2") == []
    assert _extract_target_price_numbers("消費者物價指數目標2") == []
    assert _extract_target_price_numbers("PMI target 50") == []
    assert _extract_target_price_numbers("target GDP 3") == []
    assert _extract_target_price_numbers("unemployment rate target 4") == []
    assert _extract_target_price_numbers("VIX target 20") == []
    assert _extract_target_price_numbers("volatility index target 20") == []
    assert _extract_target_price_numbers("industrial production target 5") == []
    assert _extract_target_price_numbers("housing starts target 1.4M") == []
    assert _extract_target_price_numbers("製造業PMI目標50") == []
    assert _extract_target_price_numbers("失業率目標4") == []
    assert _extract_target_price_numbers("恐慌指數目標20") == []
    assert _extract_target_price_numbers("credit spread target 150") == []
    assert _extract_target_price_numbers("CDS spread target 100") == []
    assert _extract_target_price_numbers("default rate target 2") == []
    assert _extract_target_price_numbers("LGD target 40") == []
    assert _extract_target_price_numbers("信用利差目標150") == []
    assert _extract_target_price_numbers("tariff rate target 10") == []
    assert _extract_target_price_numbers("target import tariff 25") == []
    assert _extract_target_price_numbers("subsidy target 100") == []
    assert _extract_target_price_numbers("price cap target 40") == []
    assert _extract_target_price_numbers("關稅目標10") == []
    assert _extract_target_price_numbers("target beta 1.2") == []
    assert _extract_target_price_numbers("target volatility 20") == []
    assert _extract_target_price_numbers("target Sharpe ratio 1.5") == []
    assert _extract_target_price_numbers("target debt/equity 0.5") == []
    assert _extract_target_price_numbers("D/E target 0.5") == []
    assert _extract_target_price_numbers("target leverage 2.5") == []
    assert _extract_target_price_numbers("target payout ratio 50") == []
    assert _extract_target_price_numbers("target inventory days 45") == []
    assert _extract_target_price_numbers("target cash conversion cycle 60 days") == []
    assert _extract_target_price_numbers("target WACC 10") == []
    assert _extract_target_price_numbers("discount rate target 10") == []
    assert _extract_target_price_numbers("target tax rate 20") == []
    assert _extract_target_price_numbers("target NIM 2.5") == []
    assert _extract_target_price_numbers("NIM target 2.5") == []
    assert _extract_target_price_numbers("target net interest margin 2.5") == []
    assert _extract_target_price_numbers("target NPL ratio 1.2") == []
    assert _extract_target_price_numbers("NPL target 1.2") == []
    assert _extract_target_price_numbers("target credit cost 30 bps") == []
    assert _extract_target_price_numbers("credit cost target 30 bps") == []
    assert _extract_target_price_numbers("target CET1 ratio 12") == []
    assert _extract_target_price_numbers("CET1 target 12") == []
    assert _extract_target_price_numbers("target capital adequacy ratio 15") == []
    assert _extract_target_price_numbers("目標淨利差2.5") == []
    assert _extract_target_price_numbers("目標逾放比1.2") == []
    assert _extract_target_price_numbers("授信成本目標30bps") == []
    assert _extract_target_price_numbers("目標資本適足率15") == []
    assert _extract_target_price_numbers("target conversion rate 12") == []
    assert _extract_target_price_numbers("target retention rate 90") == []
    assert _extract_target_price_numbers("target utilization rate 80") == []
    assert _extract_target_price_numbers("target utilization 80") == []
    assert _extract_target_price_numbers("capacity utilization target 80") == []
    assert _extract_target_price_numbers("目標稼動率80") == []
    assert _extract_target_price_numbers("產能利用率目標80") == []
    assert _extract_target_price_numbers("target occupancy rate 90") == []
    assert _extract_target_price_numbers("occupancy target 90") == []
    assert _extract_target_price_numbers("入住率目標90") == []
    assert _extract_target_price_numbers("target load factor 85") == []
    assert _extract_target_price_numbers("載客率目標85") == []
    assert _extract_target_price_numbers("target breakeven 2027") == []
    assert _extract_target_price_numbers("breakeven target 2027") == []
    assert _extract_target_price_numbers("target break-even 2027") == []
    assert _extract_target_price_numbers("break even target 2027") == []
    assert _extract_target_price_numbers("target profitability 2027") == []
    assert _extract_target_price_numbers("profitability target 2027") == []
    assert _extract_target_price_numbers("target positive earnings 2027") == []
    assert _extract_target_price_numbers("positive earnings target 2027") == []
    assert _extract_target_price_numbers("目標損益兩平2027年") == []
    assert _extract_target_price_numbers("損益兩平目標2027年") == []
    assert _extract_target_price_numbers("目標轉虧為盈2027年") == []
    assert _extract_target_price_numbers("獲利轉正目標2027年") == []
    assert _extract_target_price_numbers("target CAGR 20") == []
    assert _extract_target_price_numbers("CAGR target 20") == []
    assert _extract_target_price_numbers("revenue growth target 20") == []
    assert _extract_target_price_numbers("target YoY growth 20") == []
    assert _extract_target_price_numbers("目標年複合成長率20") == []
    assert _extract_target_price_numbers("target same-store sales growth 5") == []
    assert _extract_target_price_numbers("target organic growth 10") == []
    assert _extract_target_price_numbers("target market share 25") == []
    assert _extract_target_price_numbers("target TAM 160B") == []
    assert _extract_target_price_numbers("target addressable market 160B") == []
    assert _extract_target_price_numbers("target AUM 160B") == []
    assert _extract_target_price_numbers("目標管理資產160億") == []
    assert _extract_target_price_numbers("target MAU 10M") == []
    assert _extract_target_price_numbers("目標月活1000萬") == []
    assert _extract_target_price_numbers("target subscribers 10M") == []
    assert _extract_target_price_numbers("target GMV 160B") == []
    assert _extract_target_price_numbers("target backlog 160B") == []
    assert _extract_target_price_numbers("target TPV NT$160B") == []
    assert _extract_target_price_numbers("transaction volume target NT$160B") == []
    assert _extract_target_price_numbers("total payment volume target NT$160B") == []
    assert _extract_target_price_numbers("payment volume target NT$160B") == []
    assert _extract_target_price_numbers("processed volume target NT$160B") == []
    assert _extract_target_price_numbers("transactions target 160M") == []
    assert _extract_target_price_numbers("transaction count target 160M") == []
    assert _extract_target_price_numbers("交易量目標160億") == []
    assert _extract_target_price_numbers("支付量目標160億") == []
    assert _extract_target_price_numbers("交易筆數目標160萬") == []
    assert _extract_target_price_numbers("target capex NT$160M") == []
    assert _extract_target_price_numbers("目標資本支出160億") == []
    assert _extract_target_price_numbers("target opex NT$160M") == []
    assert _extract_target_price_numbers("target R&D NT$160M") == []
    assert _extract_target_price_numbers("target free cash flow NT$160M") == []
    assert _extract_target_price_numbers("target operating cash flow NT$160M") == []
    assert _extract_target_price_numbers("target cash balance NT$160M") == []
    assert _extract_target_price_numbers("target loan balance NT$160B") == []
    assert _extract_target_price_numbers("loan book target NT$160B") == []
    assert _extract_target_price_numbers("target deposits NT$160B") == []
    assert _extract_target_price_numbers("deposit target NT$160B") == []
    assert _extract_target_price_numbers("目標放款160億") == []
    assert _extract_target_price_numbers("存款目標160億") == []
    assert _extract_target_price_numbers("net debt target NT$160M") == []
    assert _extract_target_price_numbers("target inventory NT$160M") == []
    assert _extract_target_price_numbers("target accounts receivable NT$160M") == []
    assert _extract_target_price_numbers("receivables target NT$160M") == []
    assert _extract_target_price_numbers("目標存貨160億") == []
    assert _extract_target_price_numbers("目標應收帳款160億") == []
    assert _extract_target_price_numbers("target billings NT$160M") == []
    assert _extract_target_price_numbers("billings target NT$160M") == []
    assert _extract_target_price_numbers("target calculated billings NT$160M") == []
    assert _extract_target_price_numbers("target remaining performance obligation NT$160M") == []
    assert _extract_target_price_numbers("RPO target NT$160M") == []
    assert _extract_target_price_numbers("target deferred revenue NT$160M") == []
    assert _extract_target_price_numbers("contract liabilities target NT$160M") == []
    assert _extract_target_price_numbers("訂單帳款目標160億") == []
    assert _extract_target_price_numbers("target book value NT$160B") == []
    assert _extract_target_price_numbers("target NAV NT$160B") == []
    assert _extract_target_price_numbers("target ASP NT$160") == []
    assert _extract_target_price_numbers("ARPU target NT$160") == []
    assert _extract_target_price_numbers("target order intake NT$160M") == []
    assert _extract_target_price_numbers("target capacity 160K units") == []
    assert _extract_target_price_numbers("capacity target 160K units") == []
    assert _extract_target_price_numbers("target production volume 160K units") == []
    assert _extract_target_price_numbers("target output 160K units") == []
    assert _extract_target_price_numbers("target wafer starts 160K") == []
    assert _extract_target_price_numbers("target yield 95") == []
    assert _extract_target_price_numbers("目標產能160萬台") == []
    assert _extract_target_price_numbers("產量目標160萬台") == []
    assert _extract_target_price_numbers("目標良率95") == []
    assert _extract_target_price_numbers("target deliveries 160K vehicles") == []
    assert _extract_target_price_numbers("deliveries target 160K vehicles") == []
    assert _extract_target_price_numbers("target vehicle deliveries 160K") == []
    assert _extract_target_price_numbers("target sell-through 160K units") == []
    assert _extract_target_price_numbers("target installations 160K sites") == []
    assert _extract_target_price_numbers("target store count 160") == []
    assert _extract_target_price_numbers("store count target 160") == []
    assert _extract_target_price_numbers("target locations 160") == []
    assert _extract_target_price_numbers("target outlets 160") == []
    assert _extract_target_price_numbers("target restaurants 160") == []
    assert _extract_target_price_numbers("target fleet size 160K vehicles") == []
    assert _extract_target_price_numbers("目標交付量160萬台") == []
    assert _extract_target_price_numbers("交車目標160萬台") == []
    assert _extract_target_price_numbers("目標門店數160家") == []
    assert _extract_target_price_numbers("展店目標160家") == []
    assert _extract_target_price_numbers("目標安裝量160萬套") == []
    assert _extract_target_price_numbers("target NPS 60") == []
    assert _extract_target_price_numbers("NPS target 60") == []
    assert _extract_target_price_numbers("target CSAT 90") == []
    assert _extract_target_price_numbers("target customer satisfaction 90") == []
    assert _extract_target_price_numbers("target app rating 4.8") == []
    assert _extract_target_price_numbers("target defect rate 1") == []
    assert _extract_target_price_numbers("defect rate target 1") == []
    assert _extract_target_price_numbers("target uptime 99.9") == []
    assert _extract_target_price_numbers("uptime target 99.9") == []
    assert _extract_target_price_numbers("target SLA 99.9") == []
    assert _extract_target_price_numbers("target on-time delivery 95") == []
    assert _extract_target_price_numbers("target lead time 30 days") == []
    assert _extract_target_price_numbers("cycle time target 30 days") == []
    assert _extract_target_price_numbers("latency target 100 ms") == []
    assert _extract_target_price_numbers("target latency 100 ms") == []
    assert _extract_target_price_numbers("response time target 200 ms") == []
    assert _extract_target_price_numbers("throughput target 1000 QPS") == []
    assert _extract_target_price_numbers("model accuracy target 95") == []
    assert _extract_target_price_numbers("error rate target 1") == []
    assert _extract_target_price_numbers("crash rate target 0.1") == []
    assert _extract_target_price_numbers("目標NPS 60") == []
    assert _extract_target_price_numbers("目標客戶滿意度90") == []
    assert _extract_target_price_numbers("缺陷率目標1") == []
    assert _extract_target_price_numbers("目標稼動時間99.9") == []
    assert _extract_target_price_numbers("準時交付率目標95") == []
    assert _extract_target_price_numbers("交期目標30天") == []
    assert _extract_target_price_numbers("延遲目標100毫秒") == []
    assert _extract_target_price_numbers("回應時間目標200毫秒") == []
    assert _extract_target_price_numbers("準確率目標95") == []
    assert _extract_target_price_numbers("錯誤率目標1") == []
    assert _extract_target_price_numbers("target carbon emissions 160K tons") == []
    assert _extract_target_price_numbers("carbon emissions target 160K tons") == []
    assert _extract_target_price_numbers("target emissions 160K tons") == []
    assert _extract_target_price_numbers("emissions target 160K tons") == []
    assert _extract_target_price_numbers("target CO2 emissions 160K tons") == []
    assert _extract_target_price_numbers("target scope 1 emissions 160K tons") == []
    assert _extract_target_price_numbers("target emission reduction 30") == []
    assert _extract_target_price_numbers("emission reduction target 30") == []
    assert _extract_target_price_numbers("target carbon intensity 30") == []
    assert _extract_target_price_numbers("target renewable energy 80") == []
    assert _extract_target_price_numbers("renewable energy target 80") == []
    assert _extract_target_price_numbers("target energy intensity 20") == []
    assert _extract_target_price_numbers("energy intensity target 20") == []
    assert _extract_target_price_numbers("target green power 80") == []
    assert _extract_target_price_numbers("target water use 160M liters") == []
    assert _extract_target_price_numbers("target water usage 160K tons") == []
    assert _extract_target_price_numbers("target waste reduction 30") == []
    assert _extract_target_price_numbers("target recycling rate 80") == []
    assert _extract_target_price_numbers("target injury rate 1") == []
    assert _extract_target_price_numbers("LTIR target 1") == []
    assert _extract_target_price_numbers("target net zero 2050") == []
    assert _extract_target_price_numbers("net zero target 2050") == []
    assert _extract_target_price_numbers("目標碳排160萬噸") == []
    assert _extract_target_price_numbers("碳排目標160萬噸") == []
    assert _extract_target_price_numbers("減碳目標30") == []
    assert _extract_target_price_numbers("再生能源目標80") == []
    assert _extract_target_price_numbers("能源強度目標20") == []
    assert _extract_target_price_numbers("綠電目標80") == []
    assert _extract_target_price_numbers("用水量目標160萬噸") == []
    assert _extract_target_price_numbers("廢棄物減量目標30") == []
    assert _extract_target_price_numbers("回收率目標80") == []
    assert _extract_target_price_numbers("工安事故率目標1") == []
    assert _extract_target_price_numbers("職災率目標1") == []
    assert _extract_target_price_numbers("淨零目標2050") == []
    assert _extract_target_price_numbers("target enrollment 160 patients") == []
    assert _extract_target_price_numbers("enrollment target 160 patients") == []
    assert _extract_target_price_numbers("target patient enrollment 160") == []
    assert _extract_target_price_numbers("target Phase 3 enrollment 160 patients") == []
    assert _extract_target_price_numbers("target trial sites 80") == []
    assert _extract_target_price_numbers("target response rate 30") == []
    assert _extract_target_price_numbers("objective response rate target 30") == []
    assert _extract_target_price_numbers("target ORR 30") == []
    assert _extract_target_price_numbers("target overall survival 12 months") == []
    assert _extract_target_price_numbers("overall survival target 12 months") == []
    assert _extract_target_price_numbers("target progression-free survival 8 months") == []
    assert _extract_target_price_numbers("target PFS 8 months") == []
    assert _extract_target_price_numbers("target HbA1c 7") == []
    assert _extract_target_price_numbers("target LDL 70") == []
    assert _extract_target_price_numbers("target blood pressure 130") == []
    assert _extract_target_price_numbers("目標收案160人") == []
    assert _extract_target_price_numbers("收案目標160人") == []
    assert _extract_target_price_numbers("目標臨床試驗據點80") == []
    assert _extract_target_price_numbers("反應率目標30") == []
    assert _extract_target_price_numbers("目標整體存活12個月") == []
    assert _extract_target_price_numbers("無惡化存活目標8個月") == []
    assert _extract_target_price_numbers("目標糖化血色素7") == []
    assert _extract_target_price_numbers("目標低密度膽固醇70") == []
    assert _extract_target_price_numbers("血壓目標130") == []
    assert _extract_target_price_numbers("target FDA approval 2027") == []
    assert _extract_target_price_numbers("FDA approval target 2027") == []
    assert _extract_target_price_numbers("target PDUFA date 2027") == []
    assert _extract_target_price_numbers("PDUFA target 2027") == []
    assert _extract_target_price_numbers("target NDA submission 2026") == []
    assert _extract_target_price_numbers("NDA submission target 2026") == []
    assert _extract_target_price_numbers("target BLA filing 2026") == []
    assert _extract_target_price_numbers("target regulatory approval 2027") == []
    assert _extract_target_price_numbers("target marketing authorization 2027") == []
    assert _extract_target_price_numbers("target CE mark 2026") == []
    assert _extract_target_price_numbers("target 510(k) clearance 2026") == []
    assert _extract_target_price_numbers("target PMA approval 2027") == []
    assert _extract_target_price_numbers("目標FDA核准2027年") == []
    assert _extract_target_price_numbers("FDA核准目標2027年") == []
    assert _extract_target_price_numbers("目標藥證核准2027年") == []
    assert _extract_target_price_numbers("上市許可目標2027年") == []
    assert _extract_target_price_numbers("送件目標2026年") == []
    assert _extract_target_price_numbers("NDA送件目標2026年") == []
    assert _extract_target_price_numbers("target product launch 2027") == []
    assert _extract_target_price_numbers("product launch target 2027") == []
    assert _extract_target_price_numbers("target commercial launch 2027") == []
    assert _extract_target_price_numbers("commercial launch target 2027") == []
    assert _extract_target_price_numbers("target mass production 2027") == []
    assert _extract_target_price_numbers("mass production target 2027") == []
    assert _extract_target_price_numbers("target volume production 2027") == []
    assert _extract_target_price_numbers("target pilot production 2026") == []
    assert _extract_target_price_numbers("target SOP 2027") == []
    assert _extract_target_price_numbers("SOP target 2027") == []
    assert _extract_target_price_numbers("target tape-out 2026") == []
    assert _extract_target_price_numbers("tape-out target 2026") == []
    assert _extract_target_price_numbers("target design win 10") == []
    assert _extract_target_price_numbers("design win target 10") == []
    assert _extract_target_price_numbers("target design wins 10") == []
    assert _extract_target_price_numbers("目標產品上市2027年") == []
    assert _extract_target_price_numbers("產品上市目標2027年") == []
    assert _extract_target_price_numbers("量產目標2027年") == []
    assert _extract_target_price_numbers("目標量產2027年") == []
    assert _extract_target_price_numbers("試產目標2026年") == []
    assert _extract_target_price_numbers("目標試產2026年") == []
    assert _extract_target_price_numbers("設計導入目標10件") == []
    assert _extract_target_price_numbers("target cost savings NT$160M") == []
    assert _extract_target_price_numbers("cost savings target NT$160M") == []
    assert _extract_target_price_numbers("target synergy NT$160M") == []
    assert _extract_target_price_numbers("synergy target NT$160M") == []
    assert _extract_target_price_numbers("target cost reduction NT$160M") == []
    assert _extract_target_price_numbers("target expense savings NT$160M") == []
    assert _extract_target_price_numbers("目標成本節省160億") == []
    assert _extract_target_price_numbers("目標綜效160億") == []
    assert _extract_target_price_numbers("成本降低目標160億") == []
    assert _extract_target_price_numbers("target restructuring savings NT$160M") == []
    assert _extract_target_price_numbers("target COGS NT$160M") == []
    assert _extract_target_price_numbers("COGS target NT$160M") == []
    assert _extract_target_price_numbers("target cost of goods sold NT$160M") == []
    assert _extract_target_price_numbers("target production cost NT$160M") == []
    assert _extract_target_price_numbers("manufacturing cost target NT$160M") == []
    assert _extract_target_price_numbers("target unit cost NT$160") == []
    assert _extract_target_price_numbers("cost per unit target NT$160") == []
    assert _extract_target_price_numbers("target warranty expense NT$160M") == []
    assert _extract_target_price_numbers("impairment charge target NT$160M") == []
    assert _extract_target_price_numbers("restructuring charge target NT$160M") == []
    assert _extract_target_price_numbers("asset write-down target NT$160M") == []
    assert _extract_target_price_numbers("AISC target US$1200/oz") == []
    assert _extract_target_price_numbers("all-in sustaining cost target US$1200/oz") == []
    assert _extract_target_price_numbers("cash cost target US$900/oz") == []
    assert _extract_target_price_numbers("lifting cost target US$10/bbl") == []
    assert _extract_target_price_numbers("unit lifting cost target US$10/bbl") == []
    assert _extract_target_price_numbers("銷貨成本目標160億") == []
    assert _extract_target_price_numbers("製造成本目標160億") == []
    assert _extract_target_price_numbers("單位成本目標160元") == []
    assert _extract_target_price_numbers("採礦成本目標1200美元") == []
    assert _extract_target_price_numbers("現金成本目標900美元") == []
    assert _extract_target_price_numbers("開採成本目標10美元") == []
    assert _extract_target_price_numbers("減損損失目標160億") == []
    assert _extract_target_price_numbers("重組費用目標160億") == []
    assert _extract_target_price_numbers("risk reward 1:3") == []
    assert _extract_target_price_numbers("risk/reward target 1:3") == []
    assert _extract_target_price_numbers("target risk reward ratio 1:3") == []
    assert _extract_target_price_numbers("風報比3:1") == []
    assert _extract_target_price_numbers("盈虧比2.5:1") == []
    assert _extract_target_price_numbers("12 months") == []
    assert _extract_target_price_numbers("12M") == []
    assert _extract_target_price_numbers("2027年") == []
    assert _extract_target_price_numbers("FY2027") == []
    assert _extract_target_price_numbers("2027E") == []
    assert _extract_target_price_numbers("FY2027E") == []
    assert _extract_target_price_numbers("FY27") == []
    assert _extract_target_price_numbers("FY27E") == []
    assert _extract_target_price_numbers("27E") == []
    assert _extract_target_price_numbers("Q1 2027") == []
    assert _extract_target_price_numbers("2027Q1") == []
    assert _extract_target_price_numbers("2027 Q1") == []
    assert _extract_target_price_numbers("1Q27") == []
    assert _extract_target_price_numbers("Q4 FY27") == []
    assert _extract_target_price_numbers("ＦＹ２０２７") == []
    assert _extract_target_price_numbers("２０２７Ｅ") == []
    assert _extract_target_price_numbers("ＦＹ２７Ｅ") == []
    assert _extract_target_price_numbers("２７Ｅ") == []
    assert _extract_target_price_numbers("Ｑ１ ２０２７") == []
    assert _extract_target_price_numbers("２０２７Ｑ１") == []
    assert _extract_target_price_numbers("１Ｑ２７") == []
    assert _extract_target_price_numbers("Ｑ４ ＦＹ２７") == []
    assert _extract_target_price_numbers("2027 estimates") == []
    assert _extract_target_price_numbers("2027 forecast") == []

    assert _extract_target_price_numbers("target price NT$160 with COGS target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with impairment charge target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AISC target US$1200/oz") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with lifting cost target US$10/bbl") == [160.0]
    assert _extract_target_price_numbers("目標價160元，EPS 10元") == [160.0]
    assert _extract_target_price_numbers("以EPS 10元、16x PE推估目標價160元") == [160.0]
    assert _extract_target_price_numbers("目標價160元，約20x PE") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 at 20x PE") == [160.0]
    assert _extract_target_price_numbers("目標價160元，目標股利5元") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target dividend NT$5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with EBITDA target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target net income NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with gross profit target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，目標估值160億元") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target valuation NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，目標毛利率45") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target ROE 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with P/E target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target beta 1.2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with D/E target 0.5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，目標配息率50") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with WACC target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target NIM 2.5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target CET1 ratio 12") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target conversion rate 12") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target CAGR 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with revenue growth target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target market share 25") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TAM target 160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with addressable market target 160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with capacity utilization target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with occupancy target 90") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with load factor target 85") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target breakeven 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with profitability target 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target positive FCF 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target MAU 10M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GMV target 160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TPV target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transaction count target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target capex NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FCF target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target inventory NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target loan balance NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivables target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target net debt NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target billings NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RPO target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deferred revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target ASP NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target capacity 160K units") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target yield 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target deliveries 160K vehicles") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target store count 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target NPS 60") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target uptime 99.9") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with latency target 100 ms") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with model accuracy target 95") == [160.0]
    assert _extract_target_price_numbers("目標價160元，錯誤率目標1") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target carbon emissions 160K tons") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with renewable energy target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target energy intensity 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with LTIR target 1") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target enrollment 160 patients") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target ORR 30") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target HbA1c 7") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target FDA approval 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PDUFA target 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target 510(k) clearance 2026") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target product launch 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with mass production target 2027") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target design wins 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target cost savings NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with synergy target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險報酬比1:3") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk/reward 1:3") == [160.0]
    assert _extract_target_price_numbers("目標價160元，目標報酬率20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with target probability 70") == [160.0]
    assert _extract_target_price_numbers("FY2027 target price 160") == [160.0]
    assert _extract_target_price_numbers("2027E 目標價160") == [160.0]
    assert _extract_target_price_numbers("FY27E target price 160") == [160.0]
    assert _extract_target_price_numbers("Q1 2027 target price 160") == [160.0]
    assert _extract_target_price_numbers("2027Q1 目標價160") == [160.0]
    assert _extract_target_price_numbers("ＦＹ２０２７ target price 160") == [160.0]
    assert _extract_target_price_numbers("２０２７Ｑ１ 目標價160") == [160.0]


def test_extract_target_price_numbers_accepts_bare_target_values():
    assert _extract_target_price_numbers("160") == [160.0]
    assert _extract_target_price_numbers("160.5") == [160.5]


def test_extract_target_price_numbers_ignores_stakeholder_scale_targets():
    for target in (
        "target headcount 160",
        "headcount target 160",
        "target employees 160K",
        "employee count target 160K",
        "target workforce 160K",
        "target customer count 160M",
        "customer target 160M",
        "target active customers 160M",
        "active customer target 160M",
        "target client count 160K",
        "target merchants 160K",
        "merchant target 160K",
        "target suppliers 160K",
        "target partners 160K",
        "target accounts 160M",
        "目標員工160人",
        "員工人數目標160人",
        "目標客戶數160萬",
        "活躍客戶目標160萬",
        "會員數目標160萬",
        "商戶目標160萬",
        "供應商目標160家",
        "合作夥伴目標160家",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with target headcount 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with active customers target 160M") == [160.0]


def test_extract_target_price_numbers_ignores_digital_engagement_targets():
    for target in (
        "target downloads 160M",
        "downloads target 160M",
        "target app downloads 160M",
        "target installs 160M",
        "installs target 160M",
        "target DAU 10M",
        "DAU target 10M",
        "target WAU 20M",
        "subscriber net adds target 160K",
        "paid net adds target 160K",
        "viewership target 160M",
        "monthly viewers target 160M",
        "watch time target 160M hours",
        "hours watched target 160M",
        "streaming hours target 160M",
        "content hours target 160K",
        "target page views 160M",
        "page views target 160M",
        "target sessions 160M",
        "target impressions 160M",
        "target click-through rate 5",
        "CTR target 5",
        "target engagement rate 20",
        "engagement rate target 20",
        "target bounce rate 40",
        "目標下載量160萬",
        "下載量目標160萬",
        "目標安裝數160萬",
        "日活目標1000萬",
        "週活目標2000萬",
        "付費訂閱淨增目標160萬",
        "訂閱淨增目標160萬",
        "觀看時數目標160萬小時",
        "收視率目標5",
        "廣告曝光目標160萬",
        "瀏覽量目標160萬",
        "曝光量目標160萬",
        "點擊率目標5",
        "參與率目標20",
        "跳出率目標40",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with target downloads 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DAU target 10M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with subscriber net adds target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with watch time target 160M hours") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂閱淨增目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_marketing_efficiency_targets():
    for target in (
        "target ROAS 4",
        "ROAS target 4",
        "target CPA NT$160",
        "CPA target NT$160",
        "target CPC NT$5",
        "CPC target NT$5",
        "target CPM NT$160",
        "target CAC payback 12 months",
        "CAC payback target 12 months",
        "target ad spend NT$160M",
        "ad spend target NT$160M",
        "target marketing spend NT$160M",
        "marketing expense target NT$160M",
        "target acquisition cost NT$160",
        "acquisition cost target NT$160",
        "目標廣告支出160萬",
        "廣告支出目標160萬",
        "目標行銷費用160萬",
        "獲客成本目標160元",
        "廣告投報率目標4",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with target CPA NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ROAS target 4") == [160.0]


def test_extract_target_price_numbers_ignores_monetization_retention_targets():
    for target in (
        "target take rate 20",
        "take rate target 20",
        "target commission rate 15",
        "commission rate target 15",
        "target attach rate 40",
        "attach rate target 40",
        "target net revenue retention 120",
        "net revenue retention target 120",
        "target net dollar retention 120",
        "net dollar retention target 120",
        "dollar-based net retention target 120",
        "net retention target 120",
        "target NRR 120",
        "NRR target 120",
        "target NDR 120",
        "NDR target 120",
        "DBNR target 120",
        "DBRR target 120",
        "target gross revenue retention 95",
        "target gross dollar retention 95",
        "dollar-based gross retention target 95",
        "GRR target 95",
        "target logo retention 90",
        "target renewal rate 90",
        "renewal rate target 90",
        "target expansion rate 30",
        "target upsell rate 20",
        "target cross-sell rate 20",
        "目標抽成率20",
        "抽成率目標20",
        "續約率目標90",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with target take rate 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NRR target 120") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NDR target 120") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with net dollar retention target 120") == [160.0]


def test_extract_target_price_numbers_ignores_working_capital_fulfillment_targets():
    for target in (
        "target inventory turnover 8",
        "inventory turnover target 8",
        "target inventory turns 8",
        "inventory turns target 8",
        "inventory coverage target 8 weeks",
        "inventory weeks target 8",
        "safety stock target 30 days",
        "buffer stock target 30 days",
        "target days sales outstanding 45",
        "DSO target 45",
        "target DIO 60",
        "DIO target 60",
        "target DPO 75",
        "DPO target 75",
        "target fill rate 95",
        "fill rate target 95",
        "target order fulfillment rate 95",
        "target fulfillment rate 95",
        "target stockout rate 2",
        "stockout rate target 2",
        "target logistics cost 5",
        "logistics cost target 5",
        "目標庫存週轉率8",
        "庫存週轉率目標8",
        "庫存覆蓋目標8週",
        "庫存週數目標8",
        "通路庫存目標8週",
        "安全庫存目標30天",
        "應收帳款天數目標45",
        "缺貨率目標2",
        "履約率目標95",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with inventory turnover target 8") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with inventory coverage target 8 weeks") == [160.0]
    assert _extract_target_price_numbers("目標價160元，庫存覆蓋目標8週") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DSO target 45") == [160.0]


def test_extract_target_price_numbers_ignores_mix_penetration_adoption_targets():
    for target in (
        "target penetration rate 30",
        "penetration rate target 30",
        "target adoption rate 40",
        "adoption rate target 40",
        "target product mix 50",
        "product mix target 50",
        "target premium mix 40",
        "premium mix target 40",
        "target revenue mix 60",
        "revenue mix target 60",
        "target sales mix 60",
        "target export ratio 70",
        "export ratio target 70",
        "target overseas revenue share 60",
        "overseas revenue share target 60",
        "target subscription penetration 25",
        "subscription penetration target 25",
        "滲透率目標30",
        "採用率目標40",
        "產品組合目標50",
        "高階產品比重目標40",
        "營收組合目標60",
        "海外營收占比目標60",
        "出口比重目標70",
        "訂閱滲透率目標25",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with penetration rate target 30") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with premium mix target 40") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with overseas revenue share target 60") == [160.0]
    assert _extract_target_price_numbers("target price TWD 160 with combined ratio target 95") == [160.0]
    assert _extract_target_price_numbers("target price TWD 160 with expense ratio target 30") == [160.0]
    assert _extract_target_price_numbers("target price TWD 160 with NSFR target 110") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with USD/TWD target 32") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FX rate target 32") == [160.0]


def test_extract_target_price_numbers_ignores_saas_pipeline_recurring_revenue_targets():
    for target in (
        "target annual recurring revenue NT$160M",
        "annual recurring revenue target NT$160M",
        "target recurring revenue NT$160M",
        "recurring revenue target NT$160M",
        "target sales pipeline NT$160M",
        "sales pipeline target NT$160M",
        "target qualified pipeline NT$160M",
        "qualified pipeline target NT$160M",
        "target bookings pipeline NT$160M",
        "bookings pipeline target NT$160M",
        "win rate target 40",
        "target win rate 40",
        "close rate target 35",
        "sales cycle target 60 days",
        "average sales cycle target 60 days",
        "deal cycle target 45 days",
        "pipeline conversion target 25",
        "quota attainment target 90",
        "sales productivity target NT$160K",
        "ARR per rep target NT$1.6M",
        "magic number target 1.0",
        "SaaS magic number target 1.0",
        "rule of 40 target 40",
        "sales efficiency target 1.2",
        "pipeline coverage target 3",
        "quota coverage target 3",
        "目標年化經常性收入160億",
        "年化經常性收入目標160億",
        "經常性收入目標160億",
        "銷售管線目標160億",
        "合格管線目標160億",
        "訂單管線目標160億",
        "勝率目標40",
        "成交率目標35",
        "銷售週期目標60天",
        "配額達成率目標90",
        "銷售效率目標1.2",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with annual recurring revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales pipeline target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with win rate target 40") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales cycle target 60 days") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with magic number target 1.0") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rule of 40 target 40") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales efficiency target 1.2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pipeline coverage target 3") == [160.0]
    assert _extract_target_price_numbers("目標價160元，勝率目標40") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售效率目標1.2") == [160.0]


def test_extract_target_price_numbers_ignores_share_repurchase_capital_targets():
    for target in (
        "target share repurchase NT$160M",
        "share repurchase target NT$160M",
        "target buyback NT$160M",
        "buyback target NT$160M",
        "target share buyback NT$160M",
        "target repurchase amount NT$160M",
        "repurchase amount target NT$160M",
        "target shares repurchased 160M",
        "shares repurchased target 160M",
        "target share count reduction 5",
        "share count reduction target 5",
        "target diluted share count 160M",
        "diluted share count target 160M",
        "target shares outstanding 160M",
        "shares outstanding target 160M",
        "target treasury shares 160M",
        "treasury shares target 160M",
        "institutional ownership target 60",
        "foreign ownership target 40",
        "insider ownership target 20",
        "free float target 70",
        "public float target 70",
        "ownership stake target 30",
        "shareholding ratio target 30",
        "股份回購目標160億",
        "庫藏股目標160億",
        "目標買回金額160億",
        "流通股數目標160億",
        "稀釋股數目標160億",
        "股數減少目標5",
        "機構持股目標60",
        "外資持股目標40",
        "自由流通股目標70",
        "持股比例目標30",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with buyback target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with share count reduction target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shares outstanding target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with institutional ownership target 60") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with free float target 70") == [160.0]
    assert _extract_target_price_numbers("目標價160元，外資持股目標40") == [160.0]


def test_extract_target_price_numbers_ignores_reit_and_book_to_bill_targets():
    for target in (
        "NOI target NT$160M",
        "target NOI NT$160M",
        "same-store NOI target NT$160M",
        "FFO target NT$160M",
        "AFFO target NT$160M",
        "funds from operations target NT$160M",
        "adjusted FFO target NT$160M",
        "cap rate target 5",
        "capitalization rate target 5",
        "leasing spread target 10",
        "lease spread target 10",
        "renewal spread target 5",
        "rent spread target 8",
        "rent growth spread target 8",
        "leasing volume target 160K sqft",
        "leasing activity target 160K sqft",
        "tenant retention target 80",
        "rent collection target 95",
        "occupancy cost target 15",
        "development pipeline target NT$160B",
        "book-to-bill ratio target 1.2",
        "book to bill target 1.2",
        "BTB ratio target 1.2",
        "NOI目標160億",
        "營運淨收益目標160億",
        "資本化率目標5",
        "租金價差目標10",
        "續租率目標80",
        "租金收繳率目標95",
        "開發管線目標160億",
        "訂單出貨比目標1.2",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with NOI target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FFO target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cap rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with leasing spread target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with leasing volume target 160K sqft") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tenant retention target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rent collection target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with development pipeline target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，續租率目標80") == [160.0]
    assert _extract_target_price_numbers("目標價160元，租金收繳率目標95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with book-to-bill ratio target 1.2") == [160.0]


def test_extract_target_price_numbers_ignores_hospitality_rent_and_airline_unit_targets():
    for target in (
        "average daily rate target NT$160",
        "RevPAR target NT$160",
        "revenue per available room target NT$160",
        "room rate target NT$160",
        "rental rate target NT$160",
        "rent per sqft target NT$160",
        "rent per square foot target NT$160",
        "average rent target NT$160",
        "RASK target 5",
        "CASK target 4",
        "CASM target 10",
        "RASM target 12",
        "PRASM target 12",
        "TRASM target 12",
        "fuel cost target NT$160M",
        "fuel expense target NT$160M",
        "maintenance cost target NT$160M",
        "坪租目標160",
        "每坪租金目標160",
        "平均租金目標160",
        "航空燃油成本目標160億",
        "燃油費用目標160億",
        "維修成本目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with RevPAR target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rent per sqft target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RASK target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CASM target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fuel expense target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with maintenance cost target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，平均租金目標160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，燃油費用目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_customer_supplier_concentration_targets():
    for target in (
        "customer concentration target 40",
        "top customer concentration target 40",
        "top customer share target 40",
        "supplier concentration target 30",
        "vendor concentration target 30",
        "客戶集中度目標40",
        "前五大客戶占比目標60",
        "供應商集中度目標30",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer concentration target 40") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with top customer share target 40") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶集中度目標40") == [160.0]


def test_extract_target_price_numbers_ignores_equity_issuance_dilution_targets():
    for target in (
        "target capital raise NT$160M",
        "capital raise target NT$160M",
        "target capital increase NT$160M",
        "capital increase target NT$160M",
        "target equity issuance NT$160M",
        "equity issuance target NT$160M",
        "target share issuance 160M",
        "share issuance target 160M",
        "target new shares issued 160M",
        "new shares issued target 160M",
        "target rights issue NT$160M",
        "rights issue target NT$160M",
        "target private placement NT$160M",
        "private placement target NT$160M",
        "target dilution 5",
        "dilution target 5",
        "target ownership dilution 5",
        "ownership dilution target 5",
        "增資目標160億",
        "目標增資160億",
        "現金增資目標160億",
        "目標發行新股160億",
        "發行新股目標160億",
        "股權稀釋目標5",
        "稀釋率目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with capital raise target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with equity issuance target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dilution target 5") == [160.0]


def test_extract_target_price_numbers_ignores_shareholder_distribution_return_targets():
    for target in (
        "target dividend payout NT$160M",
        "dividend payout target NT$160M",
        "target shareholder return NT$160M",
        "shareholder return target NT$160M",
        "target capital return NT$160M",
        "capital return target NT$160M",
        "target cash return NT$160M",
        "cash return target NT$160M",
        "target distribution NT$160M",
        "distribution target NT$160M",
        "target payout NT$160M",
        "payout target NT$160M",
        "股東回饋目標160億",
        "股東收益率目標8",
        "目標股東收益率8",
        "股東回報率目標8",
        "股東回饋率目標8",
        "資本回報率目標8",
        "TSR target 8",
        "資本回饋目標160億",
        "現金回饋目標160億",
        "分派金額目標160億",
        "配發目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with capital return target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TSR target 8") == [160.0]
    assert _extract_target_price_numbers("目標價160元，股東收益率目標8") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with distribution target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payout target NT$160M") == [160.0]


def test_extract_target_price_numbers_ignores_commodity_input_price_targets():
    for target in (
        "oil price target US$80/bbl",
        "target oil price US$80/bbl",
        "Brent price target US$90/bbl",
        "copper price target US$4/lb",
        "lithium carbonate price target US$16000/ton",
        "steel price target 800",
        "aluminum price target 2500",
        "nickel price target 20000",
        "cobalt price target 30000",
        "uranium price target 100",
        "potash price target 350",
        "corn price target 500",
        "wheat price target 600",
        "pulp price target 700",
        "目標油價80美元",
        "銅價目標4美元",
        "鋰價目標16000美元/噸",
        "鋼價目標800",
        "鋁價目標2500",
        "鎳價目標20000",
        "鈷價目標30000",
        "鈾價目標100",
        "紙漿價格目標700",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with oil price target US$80/bbl") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with copper price target US$4/lb") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with steel price target 800") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with uranium price target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，鋼價目標800") == [160.0]


def test_extract_target_price_numbers_ignores_product_subscription_unit_price_targets():
    for target in (
        "selling price target 120",
        "list price target 120",
        "product price target 120",
        "subscription price target 10",
        "monthly subscription price target 10",
        "unit price target 120",
        "price per unit target 120",
        "售價目標120",
        "產品價格目標120",
        "訂閱價格目標10",
        "單價目標120",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with selling price target 120") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with subscription price target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with unit price target 120") == [160.0]
    assert _extract_target_price_numbers("目標價160元，產品價格目標120") == [160.0]


def test_extract_target_price_numbers_ignores_clinical_trial_statistics_safety_targets():
    for target in (
        "hazard ratio target 0.7",
        "p-value target 0.05",
        "p value target 0.05",
        "CR rate target 30",
        "disease control rate target 60",
        "DCR target 60",
        "duration of response target 12 months",
        "DOR target 12 months",
        "adverse event rate target 10",
        "grade 3 adverse event target 5",
        "serious adverse event target 5",
        "危險比目標0.7",
        "p值目標0.05",
        "疾病控制率目標60",
        "緩解持續時間目標12個月",
        "嚴重不良事件目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with hazard ratio target 0.7") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with p-value target 0.05") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DCR target 60") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with adverse event rate target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，危險比目標0.7") == [160.0]


def test_extract_target_price_numbers_ignores_hardware_semiconductor_spec_targets():
    for target in (
        "process node target 3nm",
        "node target 3nm",
        "die size target 100 mm2",
        "transistor density target 200 MTr/mm2",
        "performance per watt target 20",
        "power consumption target 5W",
        "thermal design power target 250W",
        "TDP target 250W",
        "memory bandwidth target 1TB/s",
        "bandwidth target 1TB/s",
        "TOPS target 100",
        "FLOPS target 100",
        "製程節點目標3奈米",
        "晶片面積目標100平方毫米",
        "電晶體密度目標200",
        "每瓦效能目標20",
        "功耗目標5瓦",
        "記憶體頻寬目標1TB/s",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with die size target 100 mm2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TDP target 250W") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TOPS target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，功耗目標5瓦") == [160.0]


def test_extract_target_price_numbers_ignores_ev_battery_vehicle_spec_targets():
    for target in (
        "battery capacity target 100 kWh",
        "vehicle range target 500 miles",
        "driving range target 500 km",
        "EV range target 500 km",
        "charging time target 20 minutes",
        "fast charging time target 20 minutes",
        "charging speed target 250 kW",
        "energy density target 300 Wh/kg",
        "battery energy density target 300 Wh/kg",
        "battery cycle life target 1000 cycles",
        "cycle life target 1000 cycles",
        "vehicle efficiency target 4 mi/kWh",
        "battery cost target US$100/kWh",
        "cell cost target US$100/kWh",
        "續航里程目標500公里",
        "電池容量目標100kWh",
        "充電時間目標20分鐘",
        "充電速度目標250kW",
        "能量密度目標300Wh/kg",
        "電芯成本目標100美元/kWh",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with battery capacity target 100 kWh") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vehicle range target 500 miles") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cell cost target US$100/kWh") == [160.0]
    assert _extract_target_price_numbers("目標價160元，續航里程目標500公里") == [160.0]


def test_extract_target_price_numbers_ignores_adtech_media_delivery_quality_targets():
    for target in (
        "ad load target 5",
        "ad loads target 5",
        "ad viewability target 70",
        "viewability target 70",
        "video completion rate target 80",
        "VCR target 80",
        "廣告填充率目標90",
        "廣告負載目標5",
        "可視率目標70",
        "影片完播率目標80",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ad load target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with viewability target 70") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with VCR target 80") == [160.0]
    assert _extract_target_price_numbers("目標價160元，廣告負載目標5") == [160.0]


def test_extract_target_price_numbers_ignores_industrial_maintenance_reliability_targets():
    for target in (
        "MTBF target 160 hours",
        "mean time between failures target 160 hours",
        "mean time to repair target 4 hours",
        "MTTR target 4 hours",
        "equipment downtime target 2 hours",
        "unplanned downtime target 2 hours",
        "maintenance downtime target 2 hours",
        "preventive maintenance compliance target 95",
        "PM compliance target 95",
        "平均故障間隔目標160小時",
        "平均修復時間目標4小時",
        "設備停機時間目標2小時",
        "維修停機時間目標2小時",
        "預防保養達成率目標95",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with MTBF target 160 hours") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MTTR target 4 hours") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with equipment downtime target 2 hours") == [160.0]
    assert _extract_target_price_numbers("目標價160元，平均修復時間目標4小時") == [160.0]


def test_extract_target_price_numbers_ignores_agri_food_production_targets():
    for target in (
        "feed conversion ratio target 1.5",
        "FCR target 1.5",
        "harvest volume target 160K tons",
        "harvest tonnage target 160K tons",
        "acreage target 160K acres",
        "planted acreage target 160K acres",
        "hectares target 160K",
        "planted hectares target 160K hectares",
        "herd size target 160K",
        "單產目標160",
        "作物單產目標160",
        "乳量目標30公升",
        "收成量目標160萬噸",
        "收穫量目標160萬噸",
        "種植面積目標160萬畝",
        "牲畜頭數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with feed conversion ratio target 1.5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with harvest volume target 160K tons") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with acreage target 160K acres") == [160.0]
    assert _extract_target_price_numbers("目標價160元，種植面積目標160萬畝") == [160.0]


def test_extract_target_price_numbers_ignores_financial_services_distribution_scale_targets():
    for target in (
        "branch count target 100",
        "bank branch count target 100",
        "ATM count target 100",
        "new accounts opened target 100K",
        "account openings target 100K",
        "customer acquisition target 10K",
        "customers acquired target 10K",
        "cards in force target 10M",
        "card count target 10M",
        "credit card issuance target 1M",
        "debit card issuance target 1M",
        "active cards target 10M",
        "merchant acceptance target 1M",
        "POS terminals target 1M",
        "active terminals target 1M",
        "分行數目標100",
        "ATM數目標100",
        "新開戶數目標100萬",
        "獲客數目標10萬",
        "流通卡數目標1000萬",
        "發卡量目標100萬",
        "活躍卡數目標1000萬",
        "POS終端目標100萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with branch count target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cards in force target 10M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with POS terminals target 1M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，分行數目標100") == [160.0]


def test_extract_target_price_numbers_ignores_payment_card_spend_volume_targets():
    for target in (
        "card spend target NT$160B",
        "credit card spend target NT$160B",
        "debit card spend target NT$160B",
        "card purchase volume target NT$160B",
        "credit card purchase volume target NT$160B",
        "debit card purchase volume target NT$160B",
        "card payment value target NT$160B",
        "card transaction value target NT$160B",
        "cards issued target 160M",
        "刷卡金額目標160億",
        "信用卡刷卡金額目標160億",
        "卡片消費金額目標160億",
        "簽帳金額目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with card spend target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with card purchase volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cards issued target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，刷卡金額目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_marketplace_travel_mobility_activity_targets():
    for target in (
        "gross merchandise value target NT$160B",
        "gross merchandise volume target NT$160B",
        "net merchandise value target NT$160B",
        "gross transaction value target NT$160B",
        "GTV target NT$160B",
        "gross order value target NT$160B",
        "成交總額目標160億",
        "room nights target 160M",
        "nights booked target 160M",
        "room nights booked target 160M",
        "rides target 160M",
        "trips target 160M",
        "completed trips target 160M",
        "trip volume target 160M",
        "ride volume target 160M",
        "delivery orders target 160M",
        "orders target 160M",
        "average fare target NT$160",
        "average trip fare target NT$160",
        "monthly active consumers target 160M",
        "active consumers target 160M",
        "active drivers target 160K",
        "active couriers target 160K",
        "driver supply target 160K",
        "courier supply target 160K",
        "訂單數目標160萬",
        "餐飲外送訂單目標160萬",
        "外送訂單目標160萬",
        "間夜數目標160萬",
        "預訂間夜目標160萬",
        "旅程數目標160萬",
        "叫車次數目標160萬",
        "完成行程目標160萬",
        "活躍司機目標160萬",
        "活躍外送員目標160萬",
        "平均車資目標160元",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with gross merchandise value target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，成交總額目標160億") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with room nights target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rides target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trip volume target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average fare target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with active drivers target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單數目標160萬") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活躍司機目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_healthcare_provider_operating_targets():
    for target in (
        "hospital beds target 160",
        "bed count target 160",
        "licensed beds target 160",
        "available beds target 160",
        "admissions target 160K",
        "patient admissions target 160K",
        "inpatient admissions target 160K",
        "discharges target 160K",
        "patient discharges target 160K",
        "outpatient visits target 160K",
        "clinic visits target 160K",
        "ER visits target 160K",
        "emergency room visits target 160K",
        "surgeries target 160K",
        "surgical cases target 160K",
        "procedures target 160K",
        "procedure volume target 160K",
        "patient days target 160K",
        "inpatient days target 160K",
        "beds occupied target 160",
        "病床數目標160床",
        "住院人次目標160萬",
        "出院人次目標160萬",
        "門診量目標160萬",
        "急診量目標160萬",
        "手術量目標160萬",
        "手術件數目標160萬",
        "醫療處置量目標160萬",
        "住院日數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with hospital beds target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with outpatient visits target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with surgeries target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，病床數目標160床") == [160.0]


def test_extract_target_price_numbers_ignores_telecom_network_deployment_targets():
    for target in (
        "5G coverage target 90",
        "network coverage target 90",
        "population coverage target 95",
        "fiber homes passed target 10M",
        "homes passed target 10M",
        "5G覆蓋率目標90",
        "網路覆蓋率目標90",
        "人口覆蓋率目標95",
        "光纖覆蓋戶數目標1000萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with 5G coverage target 90") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fiber homes passed target 10M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，5G覆蓋率目標90") == [160.0]


def test_extract_target_price_numbers_ignores_retail_restaurant_operating_targets():
    for target in (
        "restaurant traffic target 10",
        "table turnover target 5",
        "seat turnover target 5",
        "footfall target 10M",
        "store conversion target 20",
        "private label mix target 30",
        "shrink rate target 2",
        "food cost target 30",
        "labor cost target 30",
        "labour cost target 30",
        "翻桌率目標5",
        "餐廳客流目標10",
        "來客數目標1000萬",
        "自有品牌比重目標30",
        "損耗率目標2",
        "食材成本目標30",
        "人工成本目標30",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with table turnover target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with footfall target 10M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shrink rate target 2") == [160.0]
    assert _extract_target_price_numbers("目標價160元，翻桌率目標5") == [160.0]


def test_extract_target_price_numbers_ignores_real_estate_development_operating_targets():
    for target in (
        "presales target NT$160B",
        "contracted sales target NT$160B",
        "pre-sale value target NT$160B",
        "land bank target 160 acres",
        "construction backlog target NT$160B",
        "units sold target 1000",
        "homes sold target 1000",
        "units delivered target 160K",
        "handover target 160K",
        "GFA target 160M sqft",
        "GFA sold target 1M sqm",
        "gross floor area target 160M sqft",
        "pre-sale area target 1M sqm",
        "saleable area target 160M sqft",
        "saleable area sold target 1M sqm",
        "sellable area target 160M sqft",
        "sellable area sold target 1M sqm",
        "預售目標160億",
        "預售金額目標160億",
        "合約銷售目標160億",
        "銷售面積目標100萬平方米",
        "已售面積目標100萬平方米",
        "土地儲備目標160萬坪",
        "交屋戶數目標160戶",
        "可售面積目標160萬坪",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with land bank target 160 acres") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GFA target 160M sqft") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with units sold target 1000") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pre-sale area target 1M sqm") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with units delivered target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，土地儲備目標160萬坪") == [160.0]


def test_extract_target_price_numbers_ignores_defense_awards_delivery_targets():
    for target in (
        "award value target NT$160B",
        "contract awards target NT$160B",
        "program awards target NT$160B",
        "合約獲獎目標160億",
        "得標金額目標160億",
        "國防訂單目標160億",
        "飛彈交付目標160枚",
        "軍機交付目標160架",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with award value target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract awards target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with program awards target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約獲獎目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_precious_product_freight_price_targets():
    for target in (
        "gold price target US$2500/oz",
        "target gold price US$2500/oz",
        "silver price target US$30/oz",
        "DRAM price target US$4",
        "NAND price target US$5",
        "panel price target US$100",
        "container freight rate target US$2000/FEU",
        "金價目標2500美元",
        "銀價目標30美元",
        "記憶體價格目標4美元",
        "面板價格目標100美元",
        "貨櫃運價目標2000美元",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with gold price target US$2500/oz") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DRAM price target US$4") == [160.0]


def test_extract_target_price_numbers_ignores_macro_interest_rate_targets():
    for target in (
        "target interest rate 4.5",
        "interest rate target 4.5",
        "Fed funds rate target 4.5",
        "federal funds rate target 4.5",
        "policy rate target 2.0",
        "benchmark rate target 3.5",
        "利率目標4.5",
        "政策利率目標2.0",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with Fed funds rate target 4.5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with policy rate target 2.0") == [160.0]


def test_extract_target_price_numbers_ignores_market_index_targets():
    for target in (
        "S&P 500 target 6500",
        "SPX target 6500",
        "target S&P 500 6500",
        "Nasdaq target 22000",
        "NASDAQ 100 target 24000",
        "SOX target 6000",
        "Dow Jones target 45000",
        "Russell 2000 target 2500",
        "TAIEX target 30000",
        "TSEC target 30000",
        "TWSE target 30000",
        "台股加權指數目標30000",
        "加權指數目標30000",
        "大盤目標30000",
        "日經指數目標40000",
        "恒生指數目標20000",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with S&P 500 target 6500") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TAIEX target 30000") == [160.0]
    assert _extract_target_price_numbers("目標價160元，大盤目標30000") == [160.0]


def test_extract_target_price_numbers_ignores_fiscal_and_sovereign_metric_targets():
    for target in (
        "fiscal deficit target 3",
        "budget deficit target 3",
        "government deficit target 3",
        "primary balance target 1",
        "current account target 2",
        "government debt target 100",
        "debt-to-GDP target 60",
        "財政赤字目標3",
        "預算赤字目標3",
        "政府債務目標100",
        "債務GDP比目標60",
        "經常帳目標2",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with fiscal deficit target 3") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with debt-to-GDP target 60") == [160.0]
    assert _extract_target_price_numbers("目標價160元，財政赤字目標3") == [160.0]


def test_extract_target_price_numbers_ignores_rating_and_rating_action_targets():
    for target in (
        "credit rating target 2 notches",
        "rating target 2",
        "target rating 2",
        "analyst rating target 1",
        "consensus rating target 2",
        "buy rating target 1",
        "overweight rating target 1",
        "target upgrade count 3",
        "rating upgrade target 2",
        "downgrade target 1",
        "評等目標2",
        "信用評等目標2",
        "分析師評等目標2",
        "買進評等目標1",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with consensus rating target 2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit rating target 2 notches") == [160.0]


def test_extract_target_price_numbers_ignores_dcf_total_valuation_targets():
    for target in (
        "terminal value target NT$160B",
        "target terminal value NT$160B",
        "DCF value target NT$160B",
        "sum-of-the-parts target NT$160B",
        "SOTP target NT$160B",
        "終值目標1600億",
        "DCF目標價值1600億",
        "淨資產價值目標1600億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with terminal value target NT$200B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DCF value target NT$200B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，終值目標2000億") == [160.0]


def test_extract_target_price_numbers_ignores_short_interest_and_options_targets():
    for target in (
        "short interest target 10",
        "short ratio target 5",
        "days to cover target 3",
        "borrow fee target 20",
        "put/call ratio target 1.2",
        "options open interest target 100000",
        "空頭部位目標10",
        "借券費率目標20",
        "選擇權未平倉量目標100000",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with short interest target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with put/call ratio target 1.2") == [160.0]
    assert _extract_target_price_numbers("目標價160元，空頭部位目標10") == [160.0]


def test_extract_target_price_numbers_ignores_technical_indicator_and_option_greek_targets():
    for target in (
        "RSI target 70",
        "target RSI 70",
        "MACD target 1.5",
        "moving average target 200",
        "200-day moving average target 150",
        "support level target 90",
        "resistance target 160",
        "option delta target 0.5",
        "gamma target 0.1",
        "vega target 0.2",
        "RSI目標70",
        "移動平均目標200",
        "支撐位目標90",
        "壓力位目標160",
        "選擇權delta目標0.5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with RSI target 70") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with option delta target 0.5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支撐位目標90") == [160.0]


def test_extract_target_price_numbers_ignores_workforce_attrition_targets():
    for target in (
        "employee turnover target 10",
        "staff turnover target 10",
        "workforce turnover target 10",
        "attrition rate target 10",
        "employee attrition target 10",
        "voluntary attrition target 5",
        "離職率目標10",
        "員工離職率目標10",
        "員工留任率目標90",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with employee turnover target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with attrition rate target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，離職率目標10") == [160.0]


def test_extract_target_price_numbers_ignores_customer_ops_quality_targets():
    for target in (
        "cancellation rate target 10",
        "order cancellation rate target 10",
        "booking cancellation target 10",
        "refund rate target 5",
        "RMA rate target 2",
        "chargeback rate target 1",
        "complaint rate target 3",
        "customer complaint rate target 3",
        "退貨率目標8",
        "退款率目標5",
        "取消率目標10",
        "客訴率目標3",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with cancellation rate target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with refund rate target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，退貨率目標8") == [160.0]


def test_extract_target_price_numbers_ignores_bank_funding_cost_targets():
    for target in (
        "deposit cost target 2",
        "funding cost target 3",
        "淨息差目標2.5",
        "存款成本目標2",
        "資金成本目標3",
        "貸款收益率目標6",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with deposit cost target 2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with funding cost target 3") == [160.0]
    assert _extract_target_price_numbers("目標價160元，存款成本目標2") == [160.0]


def test_extract_target_price_numbers_ignores_bank_asset_quality_targets():
    for target in (
        "charge-off rate target 2",
        "net charge-off rate target 2",
        "NCO target 2",
        "delinquency rate target 3",
        "30+ DPD target 3",
        "逾期率目標3",
        "呆帳率目標2",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with charge-off rate target 2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with 30+ DPD target 3") == [160.0]
    assert _extract_target_price_numbers("目標價160元，逾期率目標3") == [160.0]


def test_extract_target_price_numbers_ignores_bank_provisioning_income_rwa_targets():
    for target in (
        "provision expense target NT$160M",
        "loan loss provision target NT$160M",
        "credit loss provision target NT$160M",
        "allowance coverage target 150",
        "efficiency ratio target 50",
        "fee income target NT$160M",
        "net interest income target NT$160M",
        "NII target NT$160M",
        "pre-provision profit target NT$160M",
        "PPNR target NT$160M",
        "risk weighted assets target NT$160B",
        "RWA target NT$160B",
        "提存費用目標160億",
        "呆帳提存目標160億",
        "風險加權資產目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with provision expense target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NII target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PPNR target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RWA target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，提存費用目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_retail_traffic_ticket_targets():
    for target in (
        "same-store sales target 5",
        "comparable sales target 5",
        "comp sales target 5",
        "store traffic target 10",
        "foot traffic target 10",
        "average ticket target NT$160",
        "average check target 160",
        "guest check target 160",
        "check size target 160",
        "average spend per guest target NT$160",
        "spend per guest target NT$160",
        "average basket value target NT$160",
        "basket value target NT$160",
        "average transaction value target NT$160",
        "ticket size target NT$160",
        "basket size target NT$160",
        "同店銷售目標5",
        "客流量目標10",
        "客單目標160",
        "平均消費目標160元",
        "每客消費目標160元",
        "籃子金額目標160元",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with store traffic target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average ticket target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average check target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average spend per guest target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with basket value target NT$160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，同店銷售目標5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，平均消費目標160元") == [160.0]


def test_extract_target_price_numbers_ignores_telecom_subscription_metric_targets():
    for target in (
        "ARPA target NT$160",
        "ARPAU target NT$160",
        "average revenue per account target NT$160",
        "net adds target 160K",
        "gross adds target 160K",
        "postpaid net adds target 160K",
        "fiber net adds target 160K",
        "broadband net adds target 160K",
        "churn target 2",
        "monthly churn target 2",
        "用戶淨增目標160萬",
        "寬頻淨增目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ARPA target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ARPAU target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with net adds target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，用戶淨增目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_crypto_platform_metric_targets():
    for target in (
        "TVL target NT$160B",
        "total value locked target NT$160B",
        "hash rate target 500",
        "active addresses target 160M",
        "wallets target 160M",
        "wallet count target 160M",
        "staking ratio target 60",
        "staking rate target 60",
        "validator count target 160K",
        "交易鎖倉量目標160億",
        "總鎖倉價值目標160億",
        "活躍地址目標160萬",
        "錢包數目標160萬",
        "質押率目標60",
        "驗證者數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with TVL target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with active addresses target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活躍地址目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_gaming_monetization_metric_targets():
    for target in (
        "ARPPU target NT$160",
        "ARPDAU target NT$2",
        "average revenue per paying user target NT$160",
        "average revenue per daily active user target NT$2",
        "paying users target 160K",
        "payer count target 160K",
        "payer conversion target 5",
        "paying user conversion target 5",
        "conversion to payer target 5",
        "in-app purchase conversion target 5",
        "IAP conversion target 5",
        "bookings per user target NT$160",
        "付費用戶目標160萬",
        "付費玩家目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ARPPU target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ARPDAU target NT$2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payer conversion target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付費用戶目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_sports_betting_gaming_targets():
    for target in (
        "sportsbook handle target NT$160B",
        "betting handle target NT$160B",
        "handle target NT$160B",
        "hold rate target 10",
        "GGR target NT$160B",
        "gross gaming revenue target NT$160B",
        "net gaming revenue target NT$160B",
        "wagers target 160M",
        "sportsbook wagers target 160M",
        "博彩流水目標160億",
        "持留率目標10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with sportsbook handle target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GGR target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with hold rate target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，博彩流水目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_pharma_commercial_metric_targets():
    for target in (
        "patient starts target 160K",
        "new patient starts target 160K",
        "prescription volume target 160K",
        "script volume target 160K",
        "TRx target 160K",
        "NRx target 160K",
        "adherence rate target 80",
        "persistence rate target 80",
        "處方量目標160萬",
        "病患數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with patient starts target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TRx target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with adherence rate target 80") == [160.0]
    assert _extract_target_price_numbers("目標價160元，處方量目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_sustainability_intensity_mix_targets():
    for target in (
        "emissions intensity target 50",
        "CO2 intensity target 50",
        "renewable energy ratio target 60",
        "renewable mix target 60",
        "water withdrawal target 160M",
        "碳排強度目標50",
        "碳排放強度目標50",
        "再生能源占比目標60",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with emissions intensity target 50") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with renewable energy ratio target 60") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with water withdrawal target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，碳排強度目標50") == [160.0]


def test_extract_target_price_numbers_ignores_airline_operating_metric_targets():
    for target in (
        "ASK target 160B",
        "ASM target 160B",
        "available seat kilometers target 160B",
        "available seat kilometres target 160B",
        "available seat miles target 160B",
        "RPK target 160B",
        "RPM target 160B",
        "revenue passenger kilometers target 160B",
        "revenue passenger kilometres target 160B",
        "revenue passenger miles target 160B",
        "passenger yield target NT$2",
        "unit revenue target NT$2",
        "ancillary revenue per passenger target NT$160",
        "passenger traffic target 160M",
        "passengers carried target 160M",
        "客座率目標85",
        "旅客運量目標160萬",
        "載客量目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ASK target 160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with passenger yield target NT$2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with unit revenue target NT$2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ancillary revenue per passenger target NT$160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客座率目標85") == [160.0]


def test_extract_target_price_numbers_ignores_logistics_shipping_metric_targets():
    for target in (
        "freight volume target 160K",
        "cargo volume target 160K",
        "cargo tonnage target 160K",
        "tonnage target 160K",
        "parcel volume target 160M",
        "package volume target 160M",
        "shipment volume target 160M",
        "dwell time target 3 days",
        "container dwell time target 3 days",
        "貨運量目標160萬",
        "包裹量目標160萬",
        "船隊利用率目標85",
        "滯港時間目標3天",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with freight volume target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cargo volume target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dwell time target 3 days") == [160.0]
    assert _extract_target_price_numbers("目標價160元，貨運量目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_shipping_charter_dayrate_targets():
    for target in (
        "charter rate target NT$160K/day",
        "time charter rate target NT$160K/day",
        "daily charter rate target NT$160K",
        "dayrate target NT$160K",
        "day rate target NT$160K",
        "daily hire rate target NT$160K",
        "TCE rate target NT$160K",
        "time charter equivalent target NT$160K",
        "vessel day rate target NT$160K",
        "船舶日租金目標160萬",
        "日租金目標160萬",
        "等價期租租金目標160萬",
        "期租等價收益目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with charter rate target NT$160K/day") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TCE rate target NT$160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dayrate target NT$160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，船舶日租金目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_marketplace_gaming_monetization_targets():
    for target in (
        "active buyers target 160M",
        "active sellers target 160K",
        "buyer count target 160M",
        "seller count target 160K",
        "paying users target 160M",
        "monthly paying users target 160M",
        "repeat purchase rate target 40",
        "repeat buyer rate target 60",
        "purchase frequency target 3",
        "order frequency target 3",
        "ARPDAU target NT$2",
        "ARPPU target NT$160",
        "payer conversion target 5",
        "paying user ratio target 5",
        "conversion to paid target 5",
        "GMV per buyer target NT$160",
        "orders per buyer target 12",
        "活躍買家目標160萬",
        "活躍賣家目標160萬",
        "買家數目標160萬",
        "賣家數目標160萬",
        "商家數目標160萬",
        "付費用戶目標160萬",
        "月付費用戶目標160萬",
        "復購率目標40",
        "購買頻率目標3",
        "下單頻率目標3",
        "付費用戶占比目標5",
        "每買家訂單數目標12",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with active buyers target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with seller count target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ARPDAU target NT$2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with repeat purchase rate target 40") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with repeat buyer rate target 60") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活躍買家目標160萬") == [160.0]
    assert _extract_target_price_numbers("目標價160元，賣家數目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_digital_ad_delivery_volume_targets():
    for target in (
        "ad requests target 160M",
        "impression volume target 160M",
        "ad views target 160M",
        "ad clicks target 160M",
        "paid clicks target 160M",
        "click volume target 160M",
        "廣告請求數目標160萬",
        "廣告點擊數目標160萬",
        "展示量目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ad requests target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with impression volume target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ad clicks target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，廣告點擊數目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_capital_turnover_ratio_targets():
    for target in (
        "capital turnover target 3",
        "invested capital turnover target 1.5",
        "working capital turnover target 3",
        "net working capital turnover target 3",
        "資產週轉率目標1.2",
        "總資產週轉率目標1.2",
        "固定資產週轉率目標2",
        "資本週轉率目標3",
        "投入資本週轉率目標1.5",
        "營運資金週轉率目標3",
        "淨營運資金週轉率目標3",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with capital turnover target 3") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invested capital turnover target 1.5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with working capital turnover target 3") == [160.0]
    assert _extract_target_price_numbers("目標價160元，營運資金週轉率目標3") == [160.0]


def test_extract_target_price_numbers_ignores_retail_availability_markdown_targets():
    for target in (
        "out-of-stock rate target 5",
        "OOS rate target 5",
        "backorder rate target 5",
        "inventory shrink target 1",
        "shrinkage target 1",
        "markdown rate target 10",
        "markdowns target NT$160M",
        "促銷折價率目標10",
        "貨架可得率目標95",
        "商品可得率目標95",
        "補貨率目標95",
        "訂單滿足率目標95",
        "缺貨金額目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with out-of-stock rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with markdown rate target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with markdowns target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，貨架可得率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_cloud_it_cost_spend_targets():
    for target in (
        "cloud spend target NT$160M",
        "cloud cost target NT$160M",
        "IT spend target NT$160M",
        "technology spend target NT$160M",
        "software spend target NT$160M",
        "infrastructure spend target NT$160M",
        "compute spend target NT$160M",
        "compute cost target NT$160M",
        "storage cost target NT$160M",
        "hosting cost target NT$160M",
        "cost per query target NT$1",
        "cost per inference target NT$1",
        "cost per token target NT$0.01",
        "GPU cost target NT$160M",
        "AI infrastructure spend target NT$160M",
        "雲端支出目標160億",
        "雲端成本目標160億",
        "IT支出目標160億",
        "技術支出目標160億",
        "算力成本目標160億",
        "推論成本目標1元",
        "每次查詢成本目標1元",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with cloud spend target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with compute cost target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cost per inference target NT$1") == [160.0]
    assert _extract_target_price_numbers("目標價160元，雲端支出目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_financial_flow_lending_value_targets():
    for target in (
        "net flows target NT$160B",
        "net inflows target NT$160B",
        "gross inflows target NT$160B",
        "fund flows target NT$160B",
        "AUM net flows target NT$160B",
        "redemptions target NT$160B",
        "outflows target NT$160B",
        "loan originations target NT$160B",
        "origination volume target NT$160B",
        "new loans target NT$160B",
        "mortgage originations target NT$160B",
        "embedded value target NT$160B",
        "economic value target NT$160B",
        "book value per share target NT$160",
        "NAV per share target NT$160",
        "淨流入目標160億",
        "資金流入目標160億",
        "放款新承作目標160億",
        "新增貸款目標160億",
        "內含價值目標160億",
        "每股淨值目標160元",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with net flows target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with loan originations target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with embedded value target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，淨流入目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_natural_resource_production_reserve_targets():
    for target in (
        "production target 160K boe/d",
        "oil production target 160K bbl/d",
        "gas production target 160K boe/d",
        "gold production target 160K oz",
        "copper production target 160K tons",
        "lithium production target 160K tons",
        "coal production target 160K tons",
        "silver production target 160K oz",
        "proved reserves target 160M boe",
        "probable reserves target 160M boe",
        "2P reserves target 160M boe",
        "oil reserves target 160M bbl",
        "gas reserves target 160M boe",
        "mineral reserves target 160M tons",
        "reserve replacement target 120",
        "well count target 160",
        "rig count target 20",
        "產油量目標160萬桶",
        "探明儲量目標160百萬桶",
        "油氣儲量目標160百萬桶",
        "儲量替換目標120",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with oil production target 160K bbl/d") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with proved reserves target 160M boe") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rig count target 20") == [160.0]
    assert _extract_target_price_numbers("目標價160元，產油量目標160萬桶") == [160.0]


def test_extract_target_price_numbers_ignores_manufacturing_quality_yield_defect_targets():
    for target in (
        "FPY target 95",
        "process yield rate target 95",
        "fab yield rate target 95",
        "die yield rate target 95",
        "defect density target 0.5",
        "defect density target 0.5 defects/cm2",
        "DPPM target 100",
        "PPM defect target 100",
        "field failure rate target 1",
        "DOA rate target 1",
        "缺陷密度目標0.5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with FPY target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with defect density target 0.5 defects/cm2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with field failure rate target 1") == [160.0]
    assert _extract_target_price_numbers("目標價160元，缺陷密度目標0.5") == [160.0]


def test_extract_target_price_numbers_ignores_chemicals_process_quality_targets():
    for target in (
        "conversion yield target 95",
        "reaction yield target 95",
        "purity target 99.9",
        "product purity target 99.9",
        "off-spec rate target 1",
        "製程收率目標95",
        "反應收率目標95",
        "純度目標99.9",
        "產品純度目標99.9",
        "不合格率目標1",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with purity target 99.9") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with off-spec rate target 1") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with conversion yield target 95") == [160.0]
    assert _extract_target_price_numbers("目標價160元，製程收率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_utility_rate_base_reliability_targets():
    for target in (
        "rate base target NT$160B",
        "regulated asset base target NT$160B",
        "RAB target NT$160B",
        "customer bill target NT$160",
        "average bill target NT$160",
        "SAIDI target 60",
        "SAIFI target 1.2",
        "CAIDI target 90",
        "outage duration target 60 minutes",
        "outage frequency target 2",
        "service interruptions target 2",
        "容量費率目標160",
        "費率基礎目標160億",
        "停電時間目標60分鐘",
        "停電頻率目標2",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with rate base target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SAIDI target 60") == [160.0]
    assert _extract_target_price_numbers("目標價160元，停電時間目標60分鐘") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_operating_kpi_targets():
    for target in (
        "gross written premium target NT$160B",
        "GWP target NT$160B",
        "net written premium target NT$160B",
        "annual premium equivalent target NT$160M",
        "APE target NT$160M",
        "value of new business target NT$160M",
        "VNB target NT$160M",
        "policies in force target 160K",
        "policy count target 160K",
        "claims count target 100K",
        "claim count target 100K",
        "claims paid target NT$160B",
        "benefit payments target NT$160B",
        "surrenders target 10K",
        "MLR target 85",
        "claims frequency target 10",
        "members target 160M",
        "member count target 160M",
        "medical membership target 160M",
        "covered members target 160M",
        "health plan members target 160M",
        "member months target 160M",
        "insured lives target 160M",
        "policyholders target 160M",
        "PMPM cost target NT$160",
        "per member per month cost target NT$160",
        "medical cost PMPM target NT$160",
        "medical cost trend target 5",
        "healthcare cost trend target 5",
        "utilization per member target 160",
        "claims per member target 160",
        "新契約價值目標160億",
        "保單件數目標160萬",
        "理賠件數目標100萬",
        "理賠金額目標160億",
        "給付金額目標160億",
        "理賠頻率目標10",
        "保戶數目標160萬",
        "會員月數目標160萬",
        "每會員每月成本目標160元",
        "醫療成本趨勢目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with GWP target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with VNB target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with claims count target 100K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with claims paid target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benefit payments target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MLR target 85") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with members target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PMPM cost target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with medical cost trend target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，理賠件數目標100萬") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保單件數目標160萬") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保戶數目標160萬") == [160.0]
    assert _extract_target_price_numbers("目標價160元，每會員每月成本目標160元") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_persistency_surrender_targets():
    for target in (
        "persistency rate target 90",
        "policy persistency target 90",
        "surrender rate target 5",
        "lapse rate target 5",
        "policy lapse rate target 5",
        "退保率目標5",
        "脫退率目標5",
        "續保率目標85",
        "保單續保率目標85",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with persistency rate target 90") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with surrender rate target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，續保率目標85") == [160.0]


def test_extract_target_price_numbers_ignores_energy_manufacturing_operating_targets():
    for target in (
        "capacity factor target 50",
        "availability target 95",
        "utilization hours target 2000",
        "reserve life target 10 years",
        "production decline target 5",
        "容量因子目標50",
        "可用率目標95",
        "scrap rate target 2",
        "rework rate target 3",
        "報廢率目標2",
        "返工率目標3",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with capacity factor target 50") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with availability target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with scrap rate target 2") == [160.0]
    assert _extract_target_price_numbers("目標價160元，容量因子目標50") == [160.0]


def test_extract_target_price_numbers_ignores_workforce_education_airline_targets():
    for target in (
        "employee productivity target NT$160K",
        "staff productivity target NT$160K",
        "labor productivity target NT$160K",
        "average tuition target NT$160K",
        "tuition target NT$160K",
        "course completion rate target 80",
        "student retention target 90",
        "graduation rate target 90",
        "student acquisition target 10K",
        "student count target 160K",
        "average class size target 30",
        "teacher retention target 90",
        "job placement rate target 80",
        "certification pass rate target 90",
        "on-time performance target 90",
        "OTP target 90",
        "baggage mishandling rate target 2",
        "員工生產力目標160萬",
        "人均產值目標160萬",
        "學費目標160萬",
        "完課率目標80",
        "升學率目標90",
        "畢業率目標90",
        "就業率目標80",
        "班級規模目標30",
        "準點率目標90",
        "飛機利用率目標12小時",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with employee productivity target NT$160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average tuition target NT$160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with graduation rate target 90") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with student count target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with average class size target 30") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with on-time performance target 90") == [160.0]
    assert _extract_target_price_numbers("目標價160元，畢業率目標90") == [160.0]
    assert _extract_target_price_numbers("目標價160元，準點率目標90") == [160.0]


def test_extract_target_price_numbers_ignores_cybersecurity_operations_targets():
    for target in (
        "false positive rate target 5",
        "detection rate target 95",
        "threat detection rate target 95",
        "MTTD target 10 minutes",
        "mean time to detect target 10 minutes",
        "blocked threats target 160K",
        "security incidents target 10",
        "incident count target 10",
        "資安事件數目標10",
        "威脅攔截數目標160萬",
        "偵測率目標95",
        "誤報率目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with false positive rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MTTD target 10 minutes") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with blocked threats target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安事件數目標10") == [160.0]


def test_extract_target_price_numbers_ignores_security_audit_assessment_ops_targets():
    for target in (
        "security assessments target 160",
        "security audits target 160",
        "penetration tests target 160",
        "pen tests target 160",
        "vulnerability assessments target 160",
        "資安評估目標160件",
        "滲透測試目標160件",
        "弱點評估目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，security assessments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，security audits target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，penetration tests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，pen tests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，vulnerability assessments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，滲透測試目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，弱點評估目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_media_content_production_targets():
    for target in (
        "content slate target 20",
        "episode slate target 20",
        "episodes produced target 160",
        "episode count target 160",
        "original content hours target 160",
        "content spend target NT$160B",
        "content investment target NT$160B",
        "production budget target NT$160M",
        "原創內容時數目標160小時",
        "集數目標160",
        "內容投資目標160億",
        "製作預算目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with content slate target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with episodes produced target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with content spend target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，集數目標160") == [160.0]


def test_extract_target_price_numbers_ignores_logistics_delivery_quality_targets():
    for target in (
        "delivery success rate target 95",
        "first attempt delivery rate target 95",
        "failed delivery rate target 5",
        "route density target 10",
        "配送成功率目標95",
        "首配成功率目標95",
        "配送失敗率目標5",
        "路線密度目標10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with delivery success rate target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with first attempt delivery rate target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with route density target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，配送成功率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_saas_seat_license_targets():
    for target in (
        "paid seats target 160K",
        "license seats target 160K",
        "licensed seats target 160K",
        "seat count target 160K",
        "licenses sold target 160K",
        "enterprise seats target 160K",
        "付費席位目標160萬",
        "授權席位目標160萬",
        "授權數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with paid seats target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with license seats target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with licenses sold target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付費席位目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_datacenter_compute_targets():
    for target in (
        "PUE target 1.2",
        "power usage effectiveness target 1.2",
        "data center capacity target 100 MW",
        "datacenter capacity target 100 MW",
        "rack count target 10K",
        "server count target 100K",
        "GPU hours target 160M",
        "compute hours target 160M",
        "資料中心容量目標100MW",
        "機櫃數目標10萬",
        "伺服器數目標100萬",
        "GPU時數目標160萬",
        "算力時數目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with PUE target 1.2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rack count target 10K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GPU hours target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料中心容量目標100MW") == [160.0]


def test_extract_target_price_numbers_ignores_renewable_project_pipeline_targets():
    for target in (
        "interconnection queue target 160GW",
        "project pipeline target 10GW",
        "renewable project pipeline target 10GW",
        "capacity additions target 160MW",
        "signed PPAs target 160MW",
        "PPA backlog target 160MW",
        "併網排隊容量目標160GW",
        "專案管線目標10GW",
        "新增裝置容量目標160MW",
        "簽約購電協議目標160MW",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with interconnection queue target 160GW") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with project pipeline target 10GW") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with signed PPAs target 160MW") == [160.0]
    assert _extract_target_price_numbers("目標價160元，併網排隊容量目標160GW") == [160.0]


def test_extract_target_price_numbers_ignores_power_generation_operating_targets():
    for target in (
        "forced outage rate target 5",
        "equivalent forced outage rate target 5",
        "EFOR target 5",
        "heat rate target 7000",
        "net heat rate target 7000",
        "spark spread target 10",
        "clean spark spread target 10",
        "dark spread target 10",
        "clean dark spread target 10",
        "PPA signed target 10",
        "PPA signing target 10",
        "熱耗率目標7000",
        "淨熱耗率目標7000",
        "火花價差目標10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with forced outage rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with heat rate target 7000") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with spark spread target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PPA signed target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，熱耗率目標7000") == [160.0]


def test_extract_target_price_numbers_ignores_gaming_esports_engagement_targets():
    for target in (
        "average concurrent users target 160K",
        "concurrent users target 160K",
        "peak concurrent users target 160K",
        "play time target 160M hours",
        "hours played target 160M",
        "gameplay hours target 160M hours",
        "matches played target 160M",
        "tournament entries target 160K",
        "遊戲時數目標160萬小時",
        "對戰場次目標160萬",
        "賽事報名數目標160萬",
        "活躍玩家目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with average concurrent users target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with play time target 160M hours") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tournament entries target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，遊戲時數目標160萬小時") == [160.0]


def test_extract_target_price_numbers_ignores_working_capital_turnover_channel_targets():
    for target in (
        "asset turnover target 1.2",
        "receivable turnover target 8",
        "accounts receivable turnover target 8",
        "payables turnover target 6",
        "accounts payable turnover target 6",
        "應收帳款週轉率目標8",
        "應付帳款週轉率目標6",
        "應收天數目標45天",
        "應付天數目標60天",
        "sell-through rate target 80",
        "sell-in target 160K units",
        "channel sell-out target 160K units",
        "通路銷售目標160萬台",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with asset turnover target 1.2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sell-through rate target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with channel sell-out target 160K units") == [160.0]
    assert _extract_target_price_numbers("目標價160元，應收天數目標45天") == [160.0]


def test_extract_target_price_numbers_ignores_medtech_commercialization_targets():
    for target in (
        "installed systems target 160",
        "installed robots target 160",
        "procedure adoption target 10",
        "procedure penetration target 10",
        "surgeon training target 160",
        "trained surgeons target 160",
        "510k submissions target 2",
        "裝機台數目標160台",
        "醫師訓練目標160人",
        "手術滲透率目標10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with installed systems target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with procedure adoption target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with 510k submissions target 2") == [160.0]
    assert _extract_target_price_numbers("目標價160元，裝機台數目標160台") == [160.0]


def test_extract_target_price_numbers_ignores_ip_rd_pipeline_targets():
    for target in (
        "patent count target 100",
        "patents granted target 100",
        "patent applications target 100",
        "patent filings target 100",
        "IP portfolio target 100 patents",
        "R&D pipeline target 10 programs",
        "development programs target 10",
        "research programs target 10",
        "product candidates target 10",
        "pipeline programs target 10",
        "專利數目標100",
        "獲准專利目標100",
        "專利申請目標100",
        "研發管線目標10項",
        "研發專案目標10項",
        "產品候選目標10項",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with patent count target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with R&D pipeline target 10 programs") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with product candidates target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，專利數目標100") == [160.0]


def test_extract_target_price_numbers_ignores_supply_chain_readiness_targets():
    for target in (
        "supplier readiness target 95",
        "supplier qualification target 95",
        "dual sourcing target 2 suppliers",
        "second source target 2 suppliers",
        "supplier diversification target 10",
        "localization rate target 60",
        "local content target 60",
        "供應商準備率目標95",
        "供應商認證率目標95",
        "雙供應來源目標2家",
        "在地化率目標60",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with supplier readiness target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dual sourcing target 2 suppliers") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with localization rate target 60") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商準備率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_retail_cpg_distribution_targets():
    for target in (
        "SKU count target 100",
        "active SKUs target 100",
        "distribution points target 160K",
        "weighted distribution target 80",
        "ACV distribution target 80",
        "shelf space target 10",
        "shelf facings target 10",
        "SKU數目標100",
        "鋪貨點目標160萬",
        "加權鋪貨率目標80",
        "陳列面目標10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with SKU count target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with weighted distribution target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shelf facings target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，SKU數目標100") == [160.0]


def test_extract_target_price_numbers_ignores_payer_access_targets():
    for target in (
        "formulary coverage target 80",
        "payer coverage target 80",
        "covered lives target 100M",
        "lives covered target 100M",
        "reimbursement approval target 10 plans",
        "reimbursement approvals target 10 plans",
        "reimbursement rate target 80",
        "給付核准目標10",
        "報銷核准目標10",
        "藥價給付目標10",
        "給付率目標80",
        "報銷率目標80",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with formulary coverage target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with covered lives target 100M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reimbursement approval target 10 plans") == [160.0]
    assert _extract_target_price_numbers("目標價160元，給付核准目標10") == [160.0]


def test_extract_target_price_numbers_ignores_ecommerce_fulfillment_targets():
    for target in (
        "fulfillment center count target 160",
        "fulfillment centers target 160",
        "warehouse count target 160",
        "warehouses target 160",
        "pick rate target 160 units/hour",
        "packing rate target 160 units/hour",
        "same-day delivery target 80",
        "履約中心數目標160座",
        "倉庫數目標160座",
        "揀貨效率目標160件",
        "包裝效率目標160件",
        "當日配送目標80",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with fulfillment center count target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pick rate target 160 units/hour") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with same-day delivery target 80") == [160.0]
    assert _extract_target_price_numbers("目標價160元，履約中心數目標160座") == [160.0]


def test_extract_target_price_numbers_ignores_telecom_network_infrastructure_targets():
    for target in (
        "tower count target 1000",
        "small cells target 10K",
        "fiber route miles target 100K",
        "spectrum holdings target 100MHz",
        "MHz-POPs target 100M",
        "base stations target 10K",
        "站台數目標10000",
        "基地台數目標10000",
        "光纖里程目標100萬公里",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with tower count target 1000") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with spectrum holdings target 100MHz") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with base stations target 10K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，基地台數目標10000") == [160.0]


def test_extract_target_price_numbers_ignores_asset_management_flow_fee_targets():
    for target in (
        "assets under management target NT$160B",
        "asset management AUM target NT$160B",
        "redemption rate target 5",
        "fund redemption rate target 5",
        "fee rate target 50 bps",
        "management fee target 50 bps",
        "資產管理規模目標160億",
        "基金流量目標10億",
        "贖回率目標5",
        "管理費率目標50bps",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with assets under management target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with redemption rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with management fee target 50 bps") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資產管理規模目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_brokerage_wealth_asset_targets():
    for target in (
        "client assets target NT$160B",
        "average client assets target NT$160B",
        "assets under custody target NT$160B",
        "custody assets target NT$160B",
        "net new assets target NT$160B",
        "NNA target NT$160B",
        "advisory assets target NT$160B",
        "客戶資產目標160億",
        "託管資產目標160億",
        "淨新增資產目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with client assets target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NNA target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with assets under custody target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶資產目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_brokerage_trading_margin_targets():
    for target in (
        "DARTs target 160K",
        "daily average revenue trades target 160K",
        "margin loans target NT$160B",
        "margin financing balance target NT$160B",
        "client margin balances target NT$160B",
        "securities lending balance target NT$160B",
        "commission income target NT$160M",
        "brokerage commissions target NT$160M",
        "AUA target NT$160B",
        "assets under administration target NT$160B",
        "administered assets target NT$160B",
        "client cash balances target NT$160B",
        "sweep balances target NT$160B",
        "券商活躍帳戶目標160萬",
        "融資餘額目標160億",
        "融券餘額目標160億",
        "佣金收入目標160億",
        "客戶現金目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with DARTs target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with margin loans target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AUA target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with commission income target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，融資餘額目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_capital_markets_activity_targets():
    for target in (
        "underwriting volume target NT$160B",
        "ECM volume target NT$160B",
        "DCM volume target NT$160B",
        "M&A advisory volume target NT$160B",
        "deal volume target NT$160B",
        "mandates target 160",
        "deals closed target 160",
        "bookrunner count target 10",
        "IPO proceeds target NT$160B",
        "follow-on proceeds target NT$160B",
        "debt issuance volume target NT$160B",
        "承銷量目標160億",
        "股權承銷量目標160億",
        "債券承銷量目標160億",
        "交易案量目標160件",
        "已完成交易目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with underwriting volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ECM volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with M&A advisory volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with mandates target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，交易案量目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_asset_servicing_market_infrastructure_targets():
    for target in (
        "servicing fees target NT$160M",
        "asset servicing revenue target NT$160M",
        "fund servicing fees target NT$160M",
        "transfer agency accounts target 160M",
        "clearing volume target NT$160B",
        "settlement volume target NT$160B",
        "contracts cleared target 160M",
        "contracts settled target 160M",
        "cleared contracts target 160M",
        "settled contracts target 160M",
        "中央結算量目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with servicing fees target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clearing volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contracts cleared target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transfer agency accounts target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，中央結算量目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_data_market_targets():
    for target in (
        "market data revenue target NT$160M",
        "exchange data revenue target NT$160M",
        "data subscribers target 160M",
        "market data subscribers target 160M",
        "licensed terminals target 160M",
        "terminal licenses target 160M",
        "data terminals target 160M",
        "行情資料收入目標160億",
        "行情訂閱戶目標160萬",
        "授權終端目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with market data revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with licensed terminals target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data subscribers target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，授權終端目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_listing_index_licensing_targets():
    for target in (
        "new listings target 160",
        "listed companies target 160",
        "company listings target 160",
        "ETF listings target 160",
        "listed ETFs target 160",
        "IPO listings target 160",
        "index licensing revenue target NT$160M",
        "index licenses target 160",
        "index licences target 160",
        "licensed indexes target 160",
        "licensed indices target 160",
        "indexes licensed target 160",
        "indices licensed target 160",
        "上市公司數目標160家",
        "新上市家數目標160家",
        "ETF掛牌數目標160檔",
        "掛牌ETF目標160檔",
        "指數授權收入目標160億",
        "指數授權數目標160",
        "授權指數目標160",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with new listings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ETF listings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with index licenses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with index licensing revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，ETF掛牌數目標160檔") == [160.0]
    assert _extract_target_price_numbers("目標價160元，授權指數目標160") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_membership_market_maker_targets():
    for target in (
        "exchange members target 160",
        "clearing members target 160",
        "trading members target 160",
        "trading participants target 160",
        "market participants target 160",
        "market makers target 160",
        "market maker count target 160",
        "liquidity providers target 160",
        "authorized participants target 160",
        "會員券商目標160家",
        "交易會員目標160家",
        "結算會員目標160家",
        "交易參與者目標160家",
        "市場參與者目標160家",
        "造市商目標160家",
        "流動性提供者目標160家",
        "授權參與者目標160家",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with trading participants target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with market makers target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with liquidity providers target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with authorized participants target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，造市商目標160家") == [160.0]


def test_extract_target_price_numbers_ignores_index_benchmark_product_asset_targets():
    for target in (
        "index licensing fees target NT$160M",
        "benchmark administration fees target NT$160M",
        "index administration fees target NT$160M",
        "benchmarks administered target 160",
        "indices administered target 160",
        "indexes administered target 160",
        "index-linked products target 160",
        "index linked products target 160",
        "ETF products linked target 160",
        "assets benchmarked target NT$160B",
        "assets linked to indexes target NT$160B",
        "index assets target NT$160B",
        "指數授權費目標160億",
        "基準管理費目標160億",
        "管理基準目標160個",
        "掛鉤產品目標160個",
        "掛鉤資產目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with benchmark administration fees target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benchmarks administered target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with index-linked products target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with assets benchmarked target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，掛鉤產品目標160個") == [160.0]


def test_extract_target_price_numbers_ignores_derivatives_exchange_activity_targets():
    for target in (
        "derivatives contracts target 160M",
        "futures contracts target 160M",
        "options contracts target 160M",
        "contracts traded target 160M",
        "lots traded target 160M",
        "notional volume target NT$160B",
        "期貨合約目標160萬口",
        "選擇權合約目標160萬口",
        "成交口數目標160萬口",
        "名目交易量目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with derivatives contracts target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with futures contracts target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with options contracts target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with notional volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，期貨合約目標160萬口") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_turnover_value_targets():
    for target in (
        "trading value target NT$160B",
        "trading turnover target NT$160B",
        "market turnover target NT$160B",
        "securities turnover target NT$160B",
        "average daily turnover target NT$160B",
        "average daily trading value target NT$160B",
        "average daily value traded target NT$160B",
        "average daily volume target 160M",
        "average daily trading volume target 160M",
        "ADTV target NT$160B",
        "成交金額目標160億",
        "日均成交值目標160億",
        "平均每日成交值目標160億",
        "日均成交量目標160萬股",
        "成交量目標160萬股",
        "交易周轉金額目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with average daily trading value target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trading turnover target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ADTV target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，日均成交值目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_issuer_services_targets():
    for target in (
        "listing fees target NT$160M",
        "annual listing fees target NT$160M",
        "issuer services fees target NT$160M",
        "issuer services revenue target NT$160M",
        "issuer count target 160",
        "listed issuers target 160",
        "ETF issuers target 160",
        "fund issuers target 160",
        "depository receipts target 160",
        "DR listings target 160",
        "warrants listed target 160",
        "structured products listed target 160",
        "certificates listed target 160",
        "掛牌費收入目標160億",
        "上市費收入目標160億",
        "發行人服務費目標160億",
        "發行人數目標160家",
        "上市發行人目標160家",
        "存託憑證掛牌目標160檔",
        "權證掛牌目標160檔",
        "結構型商品掛牌目標160檔",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with listing fees target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with issuer services fees target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with issuer count target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with listed issuers target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with warrants listed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，上市發行人目標160家") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_surveillance_compliance_targets():
    for target in (
        "market surveillance alerts target 160",
        "surveillance alerts target 160",
        "market surveillance cases target 160",
        "disciplinary actions target 160",
        "compliance cases target 160",
        "market abuse cases target 160",
        "trading halts target 160",
        "監視警示目標160件",
        "市場監理案件目標160件",
        "違規處分目標160件",
        "暫停交易目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with market surveillance alerts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with market surveillance cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with disciplinary actions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trading halts target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，市場監理案件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_connectivity_data_feed_targets():
    for target in (
        "co-location revenue target NT$160M",
        "colocation revenue target NT$160M",
        "connectivity revenue target NT$160M",
        "connectivity services revenue target NT$160M",
        "data feed revenue target NT$160M",
        "market data feed revenue target NT$160M",
        "data feeds licensed target 160",
        "market data feeds licensed target 160",
        "low-latency connections target 160",
        "connectivity ports target 160",
        "cross-connects target 160",
        "colocation cabinets target 160",
        "co-location racks target 160",
        "主機代管收入目標160億",
        "共置服務收入目標160億",
        "資料饋送收入目標160億",
        "行情饋送收入目標160億",
        "資料饋送授權目標160個",
        "低延遲連線目標160條",
        "連線埠目標160個",
        "交叉連線目標160條",
        "共置機櫃目標160櫃",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with co-location revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data feeds licensed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with connectivity ports target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，共置機櫃目標160櫃") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_operational_incident_targets():
    for target in (
        "trading outages target 160",
        "clearing incidents target 160",
        "settlement fails target 160",
        "結算失敗目標160件",
        "交易中斷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with trading outages target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clearing incidents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with settlement fails target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，結算失敗目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_settlement_fail_resolution_targets():
    for target in (
        "failed trades target 160",
        "trade fails target 160",
        "settlement failures target 160",
        "fails-to-deliver target 160",
        "FTDs target 160",
        "buy-ins target 160",
        "buy-in events target 160",
        "close-out events target 160",
        "failed settlements target 160",
        "交割失敗目標160件",
        "交易失敗目標160件",
        "買入補回目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with failed trades target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fails-to-deliver target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with buy-in events target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，交割失敗目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_margin_collateral_call_targets():
    for target in (
        "margin calls target 160",
        "variation margin calls target 160",
        "intraday margin calls target 160",
        "collateral calls target 160",
        "margin call notices target 160",
        "追加保證金通知目標160件",
        "保證金追繳目標160件",
        "擔保品追繳目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with margin calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with variation margin calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collateral calls target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保證金追繳目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_margin_posted_collected_targets():
    for target in (
        "initial margin posted target NT$160B",
        "initial margin collected target NT$160B",
        "variation margin paid target NT$160M",
        "variation margin collected target NT$160M",
        "member margin balances target NT$160B",
        "變動保證金收取目標160億",
        "初始保證金繳存目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with initial margin posted target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with variation margin paid target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with member margin balances target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，初始保證金繳存目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_collateral_haircut_eligibility_targets():
    for target in (
        "collateral haircuts target 20",
        "haircut rates target 20",
        "eligible collateral target NT$160B",
        "non-cash collateral target NT$160B",
        "collateral eligibility target 160",
        "擔保品折扣率目標20",
        "合格擔保品目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with collateral haircuts target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with eligible collateral target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with non-cash collateral target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，擔保品折扣率目標20") == [160.0]


def test_extract_target_price_numbers_ignores_default_management_auction_targets():
    for target in (
        "clearing member defaults target 160",
        "default management auctions target 160",
        "default auctions target 160",
        "auction lots target 160",
        "default waterfall resources target NT$160B",
        "default management drills target 160",
        "會員違約目標160件",
        "違約處理拍賣目標160件",
        "違約瀑布資源目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with clearing member defaults target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with default management auctions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with default waterfall resources target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，會員違約目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_risk_stress_testing_targets():
    for target in (
        "stress test scenarios target 160",
        "stress testing scenarios target 160",
        "backtesting exceptions target 160",
        "liquidity stress tests target 160",
        "margin model breaches target 160",
        "margin model exceptions target 160",
        "default fund stress loss target NT$160M",
        "壓力測試情境目標160個",
        "回測例外目標160件",
        "保證金模型違規目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with stress test scenarios target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with backtesting exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with default fund stress loss target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，壓力測試情境目標160個") == [160.0]


def test_extract_target_price_numbers_ignores_clearing_liquidity_resource_targets():
    for target in (
        "prefunded resources target NT$160B",
        "available liquidity resources target NT$160B",
        "committed liquidity facilities target NT$160B",
        "liquidity resources target NT$160B",
        "cover 2 resources target NT$160B",
        "skin in the game target NT$160M",
        "assessment powers target NT$160M",
        "recovery tools target 160",
        "resolution funding target NT$160B",
        "預先籌措資源目標160億",
        "流動性資源目標160億",
        "違約處理資源目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with prefunded resources target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with committed liquidity facilities target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with skin in the game target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，流動性資源目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_settlement_bank_exposure_targets():
    for target in (
        "settlement bank exposure target NT$160B",
        "settlement bank concentration target 20",
        "settlement obligations target NT$160B",
        "intraday liquidity target NT$160B",
        "payment finality target 160",
        "delivery versus payment target 160",
        "DVP transactions target 160M",
        "結算銀行曝險目標160億",
        "日中流動性目標160億",
        "款券同步交割目標160萬筆",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with settlement bank exposure target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with intraday liquidity target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment finality target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，結算銀行曝險目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_settlement_efficiency_matching_targets():
    for target in (
        "settlement efficiency target 95",
        "settlement efficiency rate target 95",
        "trade matching rate target 95",
        "settlement matching rate target 95",
        "affirmation rate target 95",
        "confirmation rate target 95",
        "straight-through processing rate target 95",
        "STP rate target 95",
        "交割效率目標95",
        "交易比對率目標95",
        "直通式處理率目標95",
        "交易確認率目標95",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with settlement efficiency target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trade matching rate target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with straight-through processing rate target 95") == [160.0]
    assert _extract_target_price_numbers("目標價160元，交割效率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_corporate_actions_proxy_servicing_targets():
    for target in (
        "corporate actions processed target 160",
        "corporate action events target 160",
        "proxy votes processed target 160M",
        "proxy voting accounts target 160M",
        "shareholder meetings target 160",
        "dividend events processed target 160",
        "公司行動處理目標160件",
        "股東會處理目標160件",
        "委託投票處理目標160萬件",
        "股利事件處理目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with corporate actions processed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with proxy votes processed target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shareholder meetings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，公司行動處理目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_transfer_agency_shareholder_register_targets():
    for target in (
        "accounts serviced target 160M",
        "registered shareholders target 160M",
        "shareholder records target 160M",
        "shareholder register entries target 160M",
        "登記股東目標160萬戶",
        "股東帳戶目標160萬戶",
        "受益人帳戶目標160萬戶",
        "股東名冊目標160萬筆",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with accounts serviced target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with registered shareholders target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shareholder records target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，登記股東目標160萬戶") == [160.0]


def test_extract_target_price_numbers_ignores_clearing_margin_collateral_targets():
    for target in (
        "margin requirements target NT$160B",
        "initial margin requirements target NT$160B",
        "variation margin requirements target NT$160B",
        "collateral posted target NT$160B",
        "collateral balances target NT$160B",
        "default fund target NT$160B",
        "default fund contributions target NT$160M",
        "clearing fund target NT$160B",
        "guarantee fund target NT$160B",
        "保證金目標160億",
        "擔保品目標160億",
        "違約基金目標160億",
        "結算基金目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with margin requirements target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collateral posted target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with default fund contributions target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clearing fund target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保證金目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_rating_agency_activity_targets():
    for target in (
        "ratings issued target 160",
        "credit ratings issued target 160",
        "rating actions target 160",
        "surveillance reviews target 160",
        "issuer ratings target 160",
        "credit opinions target 160",
        "research reports target 160",
        "評等件數目標160件",
        "信用評等案件目標160件",
        "評等行動目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ratings issued target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rating actions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit opinions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with research reports target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，評等件數目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_custody_safekeeping_fund_admin_targets():
    for target in (
        "assets under safekeeping target NT$160B",
        "safekeeping assets target NT$160B",
        "custody mandates target 160",
        "funds administered target 160",
        "fund accounting assets target NT$160B",
        "transfer agency accounts target 160M",
        "保管資產目標160億",
        "基金會計資產目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with assets under safekeeping target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with safekeeping assets target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with funds administered target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fund accounting assets target NT$160B") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保管資產目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_collateral_repo_securities_lending_targets():
    for target in (
        "collateral balances target NT$160B",
        "collateral balance target NT$160B",
        "collateral under management target NT$160B",
        "margin collateral target NT$160B",
        "repo volume target NT$160B",
        "reverse repo volume target NT$160B",
        "tri-party repo volume target NT$160B",
        "collateral management fees target NT$160M",
        "collateral management revenue target NT$160M",
        "securities lending revenue target NT$160M",
        "securities lending fees target NT$160M",
        "securities lending volume target NT$160B",
        "securities loans outstanding target NT$160B",
        "保證金擔保品目標160億",
        "擔保品餘額目標160億",
        "擔保品管理費目標160億",
        "債券借貸餘額目標160億",
        "證券借貸收入目標160億",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with collateral balances target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with repo volume target NT$160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with securities lending revenue target NT$160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with securities lending fees target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，擔保品餘額目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_mining_resource_quality_targets():
    for target in (
        "ore grade target 2",
        "head grade target 2",
        "strip ratio target 3",
        "waste strip ratio target 3",
        "recovery rate target 90",
        "metallurgical recovery target 90",
        "processing recovery target 90",
        "礦石品位目標2",
        "入礦品位目標2",
        "剝採比目標3",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ore grade target 2") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with strip ratio target 3") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with metallurgical recovery target 90") == [160.0]
    assert _extract_target_price_numbers("目標價160元，礦石品位目標2") == [160.0]


def test_extract_target_price_numbers_ignores_oilfield_drilling_completion_targets():
    for target in (
        "well completions target 100",
        "completed wells target 100",
        "wells drilled target 100",
        "drilling footage target 100K",
        "lateral feet target 100K",
        "frac stages target 100",
        "fracturing stages target 100",
        "鑽井數目標100",
        "完井數目標100",
        "鑽井進尺目標100萬英尺",
        "壓裂段數目標100",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with well completions target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with drilling footage target 100K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with frac stages target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，鑽井數目標100") == [160.0]


def test_extract_target_price_numbers_ignores_workforce_esg_safety_targets():
    for target in (
        "employee engagement target 80",
        "employee engagement score target 80",
        "employee satisfaction target 80",
        "training hours target 40",
        "TRIR target 1.0",
        "LTIFR target 0.5",
        "lost time injury frequency rate target 0.5",
        "recordable incident rate target 1.0",
        "female representation target 40",
        "board independence target 60",
        "diversity ratio target 40",
        "員工敬業度目標80",
        "訓練時數目標40小時",
        "女性占比目標40",
        "董事獨立性目標60",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with employee engagement target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TRIR target 1.0") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with female representation target 40") == [160.0]
    assert _extract_target_price_numbers("目標價160元，女性占比目標40") == [160.0]


def test_extract_target_price_numbers_ignores_diagnostics_lab_operating_targets():
    for target in (
        "test volume target 160M",
        "diagnostic test volume target 160M",
        "samples processed target 160K",
        "sample volume target 160K",
        "tests performed target 160K",
        "positivity rate target 5",
        "turnaround time target 24 hours",
        "檢測量目標160萬",
        "樣本量目標160萬",
        "陽性率目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with diagnostic test volume target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sample volume target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with positivity rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with turnaround time target 24 hours") == [160.0]
    assert _extract_target_price_numbers("目標價160元，檢測量目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_aerospace_mro_flight_hour_targets():
    for target in (
        "flight hours target 160K",
        "block hours target 160K",
        "engine flight hours target 160K",
        "flight cycles target 160K",
        "engine cycles target 160K",
        "shop visits target 160",
        "engine shop visits target 160",
        "maintenance events target 160",
        "airframe checks target 160",
        "飛行小時目標160萬",
        "飛行循環目標160萬",
        "發動機維修次數目標160",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with flight hours target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with flight cycles target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shop visits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with maintenance events target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，飛行小時目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_mining_resource_exploration_targets():
    for target in (
        "mineral resources target 160M tons",
        "measured resources target 160M tons",
        "indicated resources target 160M tons",
        "inferred resources target 160M tons",
        "resource conversion target 80",
        "exploration meters target 100K",
        "drill holes target 160",
        "drilling meters target 160K",
        "meters drilled target 160K",
        "assay turnaround target 10 days",
        "exploration budget target NT$160M",
        "resource ounces target 10Moz",
        "reserve ounces target 10Moz",
        "drill intercept target 100m",
        "drilling intercept target 100m",
        "資源量目標160百萬噸",
        "探勘進尺目標100萬米",
        "礦孔數目標160孔",
        "鑽探米數目標160萬米",
        "化驗週期目標10天",
        "化驗樣本目標160件",
        "資源轉換率目標80",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with mineral resources target 160M tons") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with exploration meters target 100K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with drill holes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with assay turnaround target 10 days") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with resource ounces target 10Moz") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with drill intercept target 100m") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with resource conversion target 80") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資源量目標160百萬噸") == [160.0]
    assert _extract_target_price_numbers("目標價160元，鑽探米數目標160萬米") == [160.0]


def test_extract_target_price_numbers_ignores_biopharma_manufacturing_targets():
    for target in (
        "batch release target 100",
        "lot release target 100",
        "commercial batches target 100",
        "GMP batches target 100",
        "release testing target 100",
        "bioreactor capacity target 100K liters",
        "fill-finish capacity target 100M doses",
        "批次放行目標100",
        "商業批次目標100",
        "生物反應器容量目標100萬公升",
        "充填產能目標100萬劑",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with batch release target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with commercial batches target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with bioreactor capacity target 100K liters") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with release testing target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，批次放行目標100") == [160.0]


def test_extract_target_price_numbers_ignores_utility_grid_operating_targets():
    for target in (
        "grid connections target 100K",
        "customer connections target 100K",
        "interruption minutes target 60",
        "outage minutes target 60",
        "line losses target 5",
        "T&D losses target 5",
        "併網戶數目標100萬",
        "線損率目標5",
        "停電分鐘目標60",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with grid connections target 100K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with line losses target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with interruption minutes target 60") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with T&D losses target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，線損率目標5") == [160.0]


def test_extract_target_price_numbers_ignores_semiconductor_process_layer_targets():
    for target in (
        "EUV layers target 20",
        "mask layers target 80",
        "reticle count target 100",
        "photomask count target 100",
        "lithography steps target 100",
        "process steps target 1000",
        "製程層數目標80",
        "EUV層數目標20",
        "光罩層數目標80",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with EUV layers target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with mask layers target 80") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reticle count target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with lithography steps target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，製程層數目標80") == [160.0]


def test_extract_target_price_numbers_ignores_semiconductor_wafer_cost_quality_targets():
    for target in (
        "wafer cost target NT$160",
        "cost per wafer target NT$160",
        "mask count target 20",
        "yield loss target 5",
        "die yield loss target 5",
        "晶圓成本目標160元",
        "光罩數目標20",
        "良率損失目標5",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with wafer cost target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cost per wafer target NT$160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with mask count target 20") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with yield loss target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，晶圓成本目標160元") == [160.0]


def test_extract_target_price_numbers_ignores_semicap_equipment_tool_targets():
    for target in (
        "EUV tools target 10",
        "lithography tools target 10",
        "tool installs target 100",
        "deposition tools target 100",
        "etch tools target 100",
        "metrology tools target 100",
        "inspection tools target 100",
        "設備台數目標100",
        "EUV機台目標10",
        "蝕刻機台目標100",
        "檢測機台目標100",
        "tool count target 160",
        "installed tools target 160",
        "etch chambers target 160",
        "deposition chambers target 160",
        "process chambers target 160",
        "chamber count target 160",
        "工具機台數目標160台",
        "蝕刻腔體目標160個",
        "沉積腔體目標160個",
        "製程腔體數目標160個",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with EUV tools target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deposition tools target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with etch tools target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with inspection tools target 100") == [160.0]
    assert _extract_target_price_numbers("目標價160元，EUV機台目標10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tool count target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with installed tools target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with etch chambers target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，製程腔體數目標160個") == [160.0]


def test_extract_target_price_numbers_ignores_payment_quality_targets():
    for target in (
        "payment success rate target 95",
        "payment authorization rate target 95",
        "authorization rate target 95",
        "failed payment rate target 5",
        "fraud loss rate target 5",
        "dispute rate target 1",
        "支付成功率目標95",
        "授權成功率目標95",
        "付款失敗率目標5",
        "詐欺損失率目標5",
        "交易爭議率目標1",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with payment success rate target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with authorization rate target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud loss rate target 5") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dispute rate target 1") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支付成功率目標95") == [160.0]


def test_extract_target_price_numbers_ignores_cybersecurity_vulnerability_targets():
    for target in (
        "vulnerabilities remediated target 160",
        "vulnerability remediation target 160",
        "critical vulnerabilities target 10",
        "open vulnerabilities target 100",
        "patch compliance target 95",
        "patching compliance target 95",
        "MFA adoption target 90",
        "multi-factor authentication adoption target 90",
        "phishing click rate target 5",
        "phishing failure rate target 5",
        "endpoint coverage target 95",
        "EDR coverage target 95",
        "security training completion target 95",
        "mean time to remediate target 10 days",
        "弱點修補目標160項",
        "高風險弱點目標10項",
        "修補合規率目標95",
        "釣魚點擊率目標5",
        "端點覆蓋率目標95",
        "資安訓練完成率目標95",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vulnerabilities remediated target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with patch compliance target 95") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MFA adoption target 90") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with phishing click rate target 5") == [160.0]
    assert _extract_target_price_numbers("目標價160元，弱點修補目標160項") == [160.0]


def test_extract_target_price_numbers_ignores_digital_user_base_targets():
    for target in (
        "registered users target 160M",
        "total registered users target 160M",
        "digital users target 160M",
        "digital banking users target 160M",
        "mobile banking users target 160M",
        "online banking users target 160M",
        "mobile app users target 160M",
        "app users target 160M",
        "verified users target 160M",
        "KYC verified users target 160M",
        "monthly transacting users target 160M",
        "transacting users target 160M",
        "active users target 160M",
        "註冊用戶目標160萬",
        "數位用戶目標160萬",
        "行動銀行用戶目標160萬",
        "網銀用戶目標160萬",
        "已驗證用戶目標160萬",
        "交易用戶目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with registered users target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with digital banking users target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transacting users target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with active users target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，註冊用戶目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_advanced_packaging_targets():
    for target in (
        "HBM stacks target 160M",
        "HBM stack count target 160M",
        "advanced packaging lines target 10",
        "packaging lines target 10",
        "hybrid bonding tools target 100",
        "bonding machines target 100",
        "substrate layers target 20",
        "interposer count target 160M",
        "HBM堆疊數目標160萬",
        "封裝線目標10條",
        "混合鍵合設備目標100台",
        "基板層數目標20",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with HBM stacks target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with advanced packaging lines target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with hybrid bonding tools target 100") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with substrate layers target 20") == [160.0]
    assert _extract_target_price_numbers("目標價160元，HBM堆疊數目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_biotech_regulatory_milestone_targets():
    for target in (
        "IND filings target 10",
        "IND submissions target 10",
        "clinical trial starts target 10",
        "phase 2 starts target 10",
        "phase 3 starts target 10",
        "data readouts target 10",
        "clinical data readouts target 10",
        "FDA meetings target 10",
        "pre-NDA meetings target 10",
        "臨床讀出目標10項",
        "臨床試驗啟動目標10項",
        "二期試驗啟動目標10項",
        "三期試驗啟動目標10項",
        "IND送件目標10件",
        "FDA會議目標10次",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with IND filings target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clinical trial starts target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data readouts target 10") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FDA meetings target 10") == [160.0]
    assert _extract_target_price_numbers("目標價160元，臨床讀出目標10項") == [160.0]


def test_extract_target_price_numbers_ignores_ai_model_usage_targets():
    for target in (
        "tokens processed target 160B",
        "inference tokens target 160B",
        "training tokens target 10T",
        "model parameters target 100B",
        "parameter count target 100B",
        "context length target 128K",
        "API calls target 160M",
        "推論token數目標160億",
        "訓練token數目標10兆",
        "參數量目標100B",
        "上下文長度目標128K",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with tokens processed target 160B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with model parameters target 100B") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with context length target 128K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with API calls target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，推論token數目標160億") == [160.0]


def test_extract_target_price_numbers_ignores_exchange_message_capacity_targets():
    for target in (
        "order messages target 160M",
        "quote messages target 160M",
        "messages processed target 160M",
        "market data messages target 160M",
        "FIX messages target 160M",
        "gateway messages target 160M",
        "matching engine messages target 160M",
        "orders per second target 160K",
        "訊息處理量目標160萬",
        "委託訊息目標160萬",
        "撮合訊息目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with order messages target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with market data messages target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with matching engine messages target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訊息處理量目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_model_governance_targets():
    for target in (
        "model validation findings target 160",
        "model validation reviews target 160",
        "independent model reviews target 160",
        "model review findings target 160",
        "model risk findings target 160",
        "margin model changes target 160",
        "risk model changes target 160",
        "model exceptions target 160",
        "模型驗證發現目標160件",
        "獨立模型審查目標160件",
        "模型覆核例外目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with model validation findings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with independent model reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk model changes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，模型驗證發現目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_data_quality_governance_targets():
    for target in (
        "data quality issues target 160",
        "data quality findings target 160",
        "data lineage gaps target 160",
        "reference data errors target 160",
        "stale data exceptions target 160",
        "data validation failures target 160",
        "data exceptions target 160",
        "資料品質問題目標160件",
        "資料血緣缺口目標160件",
        "參考資料錯誤目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data quality issues target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reference data errors target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data lineage gaps target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料品質問題目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_data_reconciliation_exception_targets():
    for target in (
        "data reconciliation breaks target 160",
        "reconciliation breaks target 160",
        "matched breaks target 160",
        "unmatched breaks target 160",
        "breaks resolved target 160",
        "reconciliation exceptions target 160",
        "reconciliation items target 160",
        "unresolved reconciliation items target 160",
        "資料對帳差異目標160件",
        "對帳例外目標160件",
        "待處理例外目標160件",
        "未解對帳項目目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data reconciliation breaks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reconciliation exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with unresolved reconciliation items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料對帳差異目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_audit_compliance_control_targets():
    for target in (
        "audit findings target 160",
        "control deficiencies target 160",
        "SOX deficiencies target 160",
        "internal control issues target 160",
        "compliance breaches target 160",
        "policy exceptions target 160",
        "KYC alerts target 160",
        "AML alerts target 160",
        "sanctions screening alerts target 160",
        "稽核發現目標160件",
        "內控缺失目標160件",
        "合規違規目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with audit findings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control deficiencies target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AML alerts target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核發現目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compliance_evidence_collection_ops_targets():
    for target in (
        "evidence requests target 160",
        "evidence packages target 160",
        "control evidence target 160",
        "audit evidence target 160",
        "evidence submissions target 160",
        "evidence reviews target 160",
        "證據請求目標160件",
        "控制證據目標160件",
        "稽核證據目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with evidence requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control evidence target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with evidence submissions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，證據請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，控制證據目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核證據目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compliance_evidence_admin_targets():
    for target in (
        "SOX evidence requests target 160",
        "audit requests target 160",
        "evidence follow-ups target 160",
        "compliance evidence uploads target 160",
        "control owner reminders target 160",
        "access review evidence target 160",
        "policy attestations target 160",
        "compliance attestations target 160",
        "SOX certifications target 160",
        "稽核請求目標160件",
        "證據跟催目標160件",
        "合規證據上傳目標160件",
        "控制負責人提醒目標160件",
        "權限審查證據目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with audit requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with evidence follow-ups target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access review evidence target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合規證據上傳目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_data_security_targets():
    for target in (
        "privacy incidents target 160",
        "data breach incidents target 160",
        "records exposed target 160M",
        "personal data requests target 160K",
        "DSAR requests target 160K",
        "data deletion requests target 160K",
        "consent rate target 95",
        "cookie opt-in rate target 95",
        "隱私事件目標160件",
        "資料外洩事件目標160件",
        "個資請求目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with privacy incidents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with records exposed target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DSAR requests target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，隱私事件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_identity_access_governance_targets():
    for target in (
        "access reviews target 160",
        "user access reviews target 160",
        "access recertifications target 160",
        "privileged access reviews target 160",
        "privileged access violations target 160",
        "IAM exceptions target 160",
        "MFA exceptions target 160",
        "identity verification failures target 160",
        "權限審查目標160件",
        "權限覆核目標160件",
        "特權存取覆核目標160件",
        "特權存取違規目標160件",
        "身分驗證失敗目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with access reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with privileged access violations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with IAM exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，權限審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，權限覆核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，特權存取覆核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_vendor_third_party_risk_targets():
    for target in (
        "vendor risk assessments target 160",
        "third-party risk assessments target 160",
        "supplier risk reviews target 160",
        "vendor due diligence reviews target 160",
        "third-party due diligence reviews target 160",
        "third-party findings target 160",
        "vendor remediation items target 160",
        "third-party exceptions target 160",
        "vendor SLA breaches target 160",
        "供應商風險評估目標160件",
        "第三方風險評估目標160件",
        "供應商整改項目目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vendor risk assessments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third-party risk assessments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor remediation items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商風險評估目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_support_ops_targets():
    for target in (
        "support tickets target 160K",
        "customer support tickets target 160K",
        "open support tickets target 160K",
        "backlog tickets target 160K",
        "resolved tickets target 160K",
        "tickets resolved target 160K",
        "support cases target 160K",
        "customer cases target 160K",
        "客服工單目標160萬",
        "待處理工單目標160萬",
        "已解決工單目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with support tickets target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with open support tickets target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with support cases target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客服工單目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_customer_support_escalation_ops_targets():
    for target in (
        "escalations target 160",
        "customer escalations target 160",
        "support escalations target 160",
        "tier 2 cases target 160",
        "tier 3 cases target 160",
        "SLA breaches target 160",
        "priority cases target 160",
        "first responses target 160",
        "reopened tickets target 160",
        "backlog aging cases target 160",
        "customer callbacks target 160",
        "agent handoffs target 160",
        "升級案件目標160件",
        "重開工單目標160件",
        "優先案件目標160件",
        "客戶回電目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with escalations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer escalations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SLA breaches target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，升級案件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_support_admin_extension_targets():
    for target in (
        "support case updates target 160",
        "ticket triage items target 160",
        "case escalations target 160",
        "support follow-ups target 160",
        "knowledge article requests target 160",
        "macro updates target 160",
        "agent QA reviews target 160",
        "支援案件更新目標160件",
        "工單分派目標160件",
        "支援跟進目標160件",
        "客服知識文章需求目標160件",
        "客服巨集更新目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with support case updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ticket triage items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with support follow-ups target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支援跟進目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_it_incident_escalation_ops_targets():
    for target in (
        "incident escalations target 160",
        "major incidents target 160",
        "sev 1 incidents target 160",
        "sev 2 incidents target 160",
        "P1 incidents target 160",
        "P2 incidents target 160",
        "critical incidents target 160",
        "incident reviews target 160",
        "incident postmortems target 160",
        "postmortems target 160",
        "RCA reports target 160",
        "root cause analyses target 160",
        "runbook updates target 160",
        "on-call pages target 160",
        "pager alerts target 160",
        "incident tickets target 160",
        "war room activations target 160",
        "service restorations target 160",
        "重大事件目標160件",
        "一級事件目標160件",
        "二級事件目標160件",
        "事後檢討目標160件",
        "根因分析目標160件",
        "值班通報目標160件",
        "戰情室啟動目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with incident escalations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with major incidents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with runbook updates target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，重大事件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_incident_postmortem_capa_plan_targets():
    for target in (
        "corrective action plans target 160",
        "事故復盤目標160件",
        "矯正行動計畫目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，corrective action plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，事故復盤目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，矯正行動計畫目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_audit_remediation_action_plan_targets():
    for target in (
        "remediation plans target 160",
        "management action plans target 160",
        "control remediation plans target 160",
        "audit remediation items target 160",
        "corrective action owners target 160",
        "整改計畫目標160件",
        "管理行動計畫目標160件",
        "稽核整改項目目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，remediation plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，management action plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，control remediation plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，audit remediation items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，corrective action owners target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，整改計畫目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，管理行動計畫目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核整改項目目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_devops_change_release_ops_targets():
    for target in (
        "change failures target 160",
        "deployment failures target 160",
        "failed deployments target 160",
        "rollback events target 160",
        "rollbacks target 160",
        "production rollbacks target 160",
        "hotfixes target 160",
        "emergency changes target 160",
        "standard changes target 160",
        "change approvals target 160",
        "release approvals target 160",
        "CAB approvals target 160",
        "change windows target 160",
        "release windows target 160",
        "deployment freezes target 160",
        "change tickets target 160",
        "change reviews target 160",
        "release gates target 160",
        "release blockers target 160",
        "production changes target 160",
        "變更失敗目標160件",
        "回滾事件目標160件",
        "緊急變更目標160件",
        "變更審核目標160件",
        "變更核准目標160件",
        "發版核准目標160件",
        "發版窗口目標160件",
        "變更窗口目標160件",
        "上線凍結目標160件",
        "發版阻礙目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with change failures target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rollback events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with release approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，變更失敗目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_observability_alert_ops_targets():
    for target in (
        "alert rules target 160",
        "alert policies target 160",
        "alert suppressions target 160",
        "alert silences target 160",
        "alert mutes target 160",
        "muted alerts target 160",
        "noise alerts target 160",
        "noisy alerts target 160",
        "alert notifications target 160",
        "alert routes target 160",
        "alert escalations target 160",
        "escalation policies target 160",
        "monitor checks target 160",
        "monitoring checks target 160",
        "synthetic checks target 160",
        "synthetic monitors target 160",
        "canary checks target 160",
        "probe failures target 160",
        "runbook links target 160",
        "dashboard panels target 160",
        "SLO burn alerts target 160",
        "error budget alerts target 160",
        "告警規則目標160件",
        "告警策略目標160件",
        "告警抑制目標160件",
        "告警靜音目標160件",
        "噪音告警目標160件",
        "告警通知目標160件",
        "監控檢查目標160件",
        "合成檢查目標160件",
        "儀表板面板目標160件",
        "錯誤預算告警目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with alert rules target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with synthetic checks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with error budget alerts target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，告警規則目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_cloud_capacity_ops_targets():
    for target in (
        "autoscaling events target 160",
        "scaling events target 160",
        "capacity requests target 160",
        "capacity tickets target 160",
        "quota increase requests target 160",
        "quota requests target 160",
        "cluster upgrades target 160",
        "node replacements target 160",
        "node drains target 160",
        "node restarts target 160",
        "pod restarts target 160",
        "resource throttles target 160",
        "throttling events target 160",
        "provisioning failures target 160",
        "instance replacements target 160",
        "reserved instance purchases target 160",
        "spot interruptions target 160",
        "容量申請目標160件",
        "容量工單目標160件",
        "配額申請目標160件",
        "叢集升級目標160件",
        "節點更換目標160件",
        "節點重啟目標160件",
        "資源節流目標160件",
        "佈建失敗目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with autoscaling events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with capacity requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cluster upgrades target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，容量申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_infra_cost_allocation_ops_targets():
    for target in (
        "cost allocation tags target 160",
        "cost allocation rules target 160",
        "cost allocation reports target 160",
        "cost center mappings target 160",
        "resource tags target 160",
        "tagging coverage target 160",
        "untagged resources target 160",
        "orphaned resources target 160",
        "idle resources target 160",
        "rightsizing actions target 160",
        "rightsizing recommendations target 160",
        "savings plans target 160",
        "commitment changes target 160",
        "budget alerts target 160",
        "budget exceptions target 160",
        "cloud cost anomalies target 160",
        "cost anomaly alerts target 160",
        "chargeback reports target 160",
        "showback reports target 160",
        "unit cost dashboards target 160",
        "cost allocation exceptions target 160",
        "amortization reports target 160",
        "成本分攤標籤目標160件",
        "成本分攤規則目標160件",
        "成本中心對應目標160件",
        "資源標籤目標160件",
        "未標記資源目標160件",
        "閒置資源目標160件",
        "規模調整建議目標160件",
        "節省方案目標160件",
        "承諾變更目標160件",
        "預算告警目標160件",
        "預算例外目標160件",
        "成本異常目標160件",
        "成本異常告警目標160件",
        "分攤例外目標160件",
        "攤銷報表目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with cost allocation tags target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with savings plans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rightsizing actions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，成本分攤標籤目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_data_governance_catalog_ops_targets():
    for target in (
        "data catalog entries target 160",
        "data dictionary updates target 160",
        "business glossary terms target 160",
        "metadata fields target 160",
        "metadata updates target 160",
        "lineage mappings target 160",
        "lineage diagrams target 160",
        "data ownership assignments target 160",
        "data owner reviews target 160",
        "data steward reviews target 160",
        "data stewardship reviews target 160",
        "data classification labels target 160",
        "sensitive data classifications target 160",
        "PII classifications target 160",
        "schema changes target 160",
        "schema migrations target 160",
        "schema reviews target 160",
        "quality rules target 160",
        "validation rules target 160",
        "retention policies target 160",
        "data access requests target 160",
        "data sharing requests target 160",
        "data contracts target 160",
        "data contract violations target 160",
        "data product certifications target 160",
        "dataset certifications target 160",
        "dataset deprecations target 160",
        "資料目錄項目目標160件",
        "資料字典更新目標160件",
        "業務詞彙目標160件",
        "中繼資料欄位目標160件",
        "血緣對應目標160件",
        "血緣圖目標160件",
        "資料擁有者指派目標160件",
        "資料管家審查目標160件",
        "資料分類標籤目標160件",
        "敏感資料分類目標160件",
        "個資分類目標160件",
        "架構變更目標160件",
        "架構審查目標160件",
        "品質規則目標160件",
        "驗證規則目標160件",
        "保存政策目標160件",
        "資料存取申請目標160件",
        "資料分享申請目標160件",
        "資料契約目標160件",
        "資料集認證目標160件",
        "資料集下架目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data catalog entries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with lineage mappings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with schema changes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料目錄項目目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_model_governance_ops_targets():
    for target in (
        "model registry entries target 160",
        "model catalog entries target 160",
        "model cards target 160",
        "model card updates target 160",
        "model approvals target 160",
        "model approval requests target 160",
        "model risk reviews target 160",
        "model risk assessments target 160",
        "model validation reports target 160",
        "model monitoring reviews target 160",
        "model drift reviews target 160",
        "drift alerts target 160",
        "bias evaluations target 160",
        "fairness checks target 160",
        "explainability reports target 160",
        "transparency reports target 160",
        "model waivers target 160",
        "model attestations target 160",
        "guardrail updates target 160",
        "guardrail reviews target 160",
        "prompt reviews target 160",
        "prompt approvals target 160",
        "prompt registry entries target 160",
        "evaluation datasets target 160",
        "eval suites target 160",
        "test set updates target 160",
        "red team findings target 160",
        "red team exercises target 160",
        "模型登錄項目目標160件",
        "模型目錄項目目標160件",
        "模型卡目標160件",
        "模型卡更新目標160件",
        "模型核准目標160件",
        "模型核准申請目標160件",
        "模型風險審查目標160件",
        "模型風險評估目標160件",
        "模型驗證報告目標160件",
        "模型監控審查目標160件",
        "模型漂移審查目標160件",
        "偏誤評估目標160件",
        "公平性檢查目標160件",
        "可解釋性報告目標160件",
        "透明度報告目標160件",
        "模型例外目標160件",
        "模型豁免目標160件",
        "模型聲明目標160件",
        "護欄更新目標160件",
        "護欄審查目標160件",
        "提示審查目標160件",
        "提示核准目標160件",
        "評估資料集目標160件",
        "紅隊發現目標160件",
        "紅隊演練目標160件",
        "AI事件審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with model registry entries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with model cards target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with model risk reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，模型卡目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_knowledge_management_ops_targets():
    for target in (
        "knowledge articles target 160",
        "knowledge base updates target 160",
        "knowledge base articles target 160",
        "KB articles target 160",
        "FAQ updates target 160",
        "FAQ articles target 160",
        "help center articles target 160",
        "help center updates target 160",
        "support articles target 160",
        "documentation updates target 160",
        "documentation reviews target 160",
        "runbook updates target 160",
        "playbook reviews target 160",
        "playbook updates target 160",
        "wiki edits target 160",
        "wiki pages target 160",
        "wiki updates target 160",
        "article reviews target 160",
        "article approvals target 160",
        "content approvals target 160",
        "SOP updates target 160",
        "procedure updates target 160",
        "知識文章目標160件",
        "知識庫更新目標160件",
        "FAQ更新目標160件",
        "說明中心文章目標160件",
        "Wiki編輯目標160件",
        "作業手冊審查目標160件",
        "文件更新目標160件",
        "內容核准目標160件",
        "SOP更新目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with knowledge articles target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with knowledge base updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with help center articles target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with wiki edits target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，知識文章目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_training_enablement_ops_targets():
    for target in (
        "training materials target 160",
        "training modules target 160",
        "learning modules target 160",
        "enablement courses target 160",
        "enablement sessions target 160",
        "training sessions target 160",
        "workshop sessions target 160",
        "webinar registrations target 160",
        "webinar attendees target 160",
        "course completions target 160",
        "certification completions target 160",
        "certification renewals target 160",
        "training completions target 160",
        "mandatory training completions target 160",
        "learner enrollments target 160",
        "learning paths target 160",
        "coaching sessions target 160",
        "office hours sessions target 160",
        "onboarding sessions target 160",
        "onboarding courses target 160",
        "sales playbooks target 160",
        "seller training sessions target 160",
        "partner enablement sessions target 160",
        "channel trainings target 160",
        "demo certifications target 160",
        "訓練教材目標160件",
        "訓練模組目標160件",
        "學習模組目標160件",
        "賦能課程目標160件",
        "網路研討會報名目標160件",
        "課程完成目標160件",
        "認證完成目標160件",
        "訓練完成目標160件",
        "學習路徑目標160件",
        "教練場次目標160場",
        "銷售手冊目標160件",
        "通路訓練目標160場",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with training materials target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with training modules target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with learning modules target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with certification completions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練教材目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_education_community_ops_targets():
    for target in (
        "community events target 160",
        "community meetups target 160",
        "user group meetings target 160",
        "developer workshops target 160",
        "developer labs target 160",
        "tutorials published target 160",
        "tutorial updates target 160",
        "learning labs target 160",
        "lab exercises target 160",
        "academy enrollments target 160",
        "academy completions target 160",
        "hackathon participants target 160",
        "hackathon projects target 160",
        "community questions answered target 160",
        "forum replies target 160",
        "forum posts target 160",
        "developer forum answers target 160",
        "code samples target 160",
        "sample apps target 160",
        "sandbox signups target 160",
        "社群活動目標160場",
        "社群聚會目標160場",
        "使用者社群會議目標160場",
        "開發者工作坊目標160場",
        "教學發布目標160篇",
        "實作練習目標160個",
        "學院註冊目標160人",
        "黑客松參與者目標160人",
        "社群問題回答目標160件",
        "論壇回覆目標160則",
        "程式碼範例目標160件",
        "範例應用目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with community events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with developer workshops target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tutorials published target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with forum replies target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，社群活動目標160場") == [160.0]


def test_extract_target_price_numbers_ignores_partner_developer_program_ops_targets():
    for target in (
        "partner applications target 160",
        "developer applications target 160",
        "partner program applications target 160",
        "developer program applications target 160",
        "app submissions target 160",
        "app reviews target 160",
        "app approvals target 160",
        "marketplace listings target 160",
        "marketplace submissions target 160",
        "integration reviews target 160",
        "integration submissions target 160",
        "integration certifications target 160",
        "API key requests target 160",
        "API approvals target 160",
        "sandbox projects target 160",
        "sandbox activations target 160",
        "partner badges target 160",
        "developer badges target 160",
        "extension submissions target 160",
        "plugin submissions target 160",
        "夥伴申請目標160件",
        "開發者申請目標160件",
        "夥伴計畫申請目標160件",
        "開發者計畫申請目標160件",
        "應用提交目標160件",
        "應用審查目標160件",
        "市集上架目標160件",
        "整合審查目標160件",
        "整合認證目標160件",
        "API金鑰申請目標160件",
        "沙盒專案目標160件",
        "夥伴徽章目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with partner program applications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with app submissions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with API key requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with integration reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，應用提交目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_field_marketing_event_ops_targets():
    for target in (
        "events hosted target 160",
        "events attended target 160",
        "event attendees target 160",
        "event registrations target 160",
        "event check-ins target 160",
        "event no-shows target 160",
        "trade shows target 160",
        "conferences sponsored target 160",
        "booth meetings target 160",
        "booth visits target 160",
        "booth scans target 160",
        "badge scans target 160",
        "leads scanned target 160",
        "MQLs generated target 160",
        "demo meetings target 160",
        "meetings booked target 160",
        "meeting follow-ups target 160",
        "post-event follow-ups target 160",
        "field marketing meetings target 160",
        "sponsorship activations target 160",
        "roundtables hosted target 160",
        "executive dinners target 160",
        "roadshow meetings target 160",
        "event leads target 160",
        "活動報名目標160人",
        "活動出席目標160人",
        "活動簽到目標160人",
        "展會會議目標160場",
        "展會名單目標160筆",
        "展位拜訪目標160次",
        "展位掃描目標160筆",
        "名牌掃描目標160筆",
        "潛在客戶掃描目標160筆",
        "行銷合格名單目標160筆",
        "會後跟進目標160件",
        "圓桌會議目標160場",
        "贊助活動目標160場",
        "演講場次目標160場",
        "客戶活動目標160場",
        "現場展示目標160場",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with events hosted target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with event registrations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with booth meetings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MQLs generated target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活動報名目標160人") == [160.0]


def test_extract_target_price_numbers_ignores_customer_advocacy_reference_ops_targets():
    for target in (
        "customer references target 160",
        "reference calls target 160",
        "reference requests target 160",
        "reference approvals target 160",
        "customer reference requests target 160",
        "customer reference calls target 160",
        "case studies target 160",
        "case studies published target 160",
        "case study approvals target 160",
        "customer case studies target 160",
        "customer stories target 160",
        "customer story approvals target 160",
        "testimonials collected target 160",
        "testimonials published target 160",
        "review requests target 160",
        "customer reviews target 160",
        "peer reviews target 160",
        "G2 reviews target 160",
        "Capterra reviews target 160",
        "Gartner Peer Insights reviews target 160",
        "analyst briefings target 160",
        "analyst inquiries target 160",
        "analyst questionnaires target 160",
        "award submissions target 160",
        "customer awards target 160",
        "advocacy nominations target 160",
        "advocacy activities target 160",
        "reference program signups target 160",
        "客戶推薦目標160件",
        "推薦電話目標160通",
        "參考客戶請求目標160件",
        "客戶案例目標160篇",
        "案例發布目標160篇",
        "客戶故事目標160篇",
        "推薦語收集目標160則",
        "評論邀請目標160件",
        "客戶評論目標160則",
        "G2評論目標160則",
        "分析師簡報目標160場",
        "分析師問卷目標160份",
        "獎項提交目標160件",
        "客戶獎項目標160件",
        "倡議提名目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer references target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case studies target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with G2 reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with analyst briefings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶案例目標160篇") == [160.0]


def test_extract_target_price_numbers_ignores_public_relations_media_ops_targets():
    for target in (
        "media briefings target 160",
        "press interviews target 160",
        "journalist meetings target 160",
        "press mentions target 160",
        "bylines published target 160",
        "op-eds placed target 160",
        "award entries target 160",
        "媒體簡報目標160場",
        "媒體採訪目標160場",
        "獎項報名目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with media briefings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with press interviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with press mentions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with award entries target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，媒體簡報目標160場") == [160.0]


def test_extract_target_price_numbers_ignores_product_launch_readiness_ops_targets():
    for target in (
        "launch checklist items target 160",
        "launch readiness tasks target 160",
        "release notes target 160",
        "feature launches target 160",
        "feature flags target 160",
        "roadmap items target 160",
        "PRDs completed target 160",
        "launch blockers target 160",
        "上線檢查目標160項",
        "路線圖項目目標160項",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with launch checklist items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with release notes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with feature launches target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with roadmap items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，上線檢查目標160項") == [160.0]


def test_extract_target_price_numbers_ignores_sales_quoting_discount_ops_targets():
    for target in (
        "quotes generated target 160",
        "quote reviews target 160",
        "pricing approvals target 160",
        "discount approvals target 160",
        "deal desk reviews target 160",
        "order forms processed target 160",
        "contract redlines target 160",
        "MSA reviews target 160",
        "報價審查目標160件",
        "折扣核准目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with quotes generated target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pricing approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with discount approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract redlines target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，報價審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_quote_generation_chinese_residual_targets():
    for target in (
        "報價產生目標160件",
        "報價生成目標160件",
        "報價建立目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，報價產生目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，報價生成目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，報價建立目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_order_exception_residual_targets():
    for target in (
        "order exceptions target 160",
        "order errors target 160",
        "order corrections target 160",
        "order changes target 160",
        "order modifications target 160",
        "order amendments target 160",
        "order updates target 160",
        "order holds target 160",
        "order release requests target 160",
        "訂單例外目標160件",
        "訂單錯誤目標160件",
        "訂單更正目標160件",
        "訂單修改目標160件",
        "訂單取消目標160件",
        "訂單補件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with order exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with order corrections target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with order release requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單例外目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單更正目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_order_postsale_residual_targets():
    for target in (
        "order inquiries target 160",
        "order tracking requests target 160",
        "order shipment requests target 160",
        "order delivery cases target 160",
        "order reviews target 160",
        "訂單查詢目標160件",
        "訂單客服目標160件",
        "訂單追蹤目標160件",
        "訂單交付目標160件",
        "訂單對帳目標160件",
        "訂單審核目標160件",
        "訂單退回目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with order inquiries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with order tracking requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with order delivery cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單查詢目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單對帳目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_order_admin_residual_targets():
    for target in (
        "purchase order approvals target 160",
        "requisition changes target 160",
        "procurement order approvals target 160",
        "procurement requisitions target 160",
        "requisition reviews target 160",
        "採購訂單目標160件",
        "採購單審核目標160件",
        "採購單核准目標160件",
        "採購單變更目標160件",
        "採購單例外目標160件",
        "請購單審核目標160件",
        "請購單核准目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with purchase order approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with requisition changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with procurement order approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，採購訂單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，請購單核准目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_procurement_adjacent_residual_targets():
    for target in (
        "procurement tickets target 160",
        "supplier onboarding packets target 160",
        "procurement intake tickets target 160",
        "supplier setup packets target 160",
        "supplier onboarding forms target 160",
        "採購工單目標160件",
        "供應商設定包目標160件",
        "供應商導入表單目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with procurement tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier onboarding packets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier setup packets target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，採購工單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商導入表單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_vendor_finance_exception_residual_targets():
    for target in (
        "supplier payment tickets target 160",
        "vendor payment tickets target 160",
        "supplier payment exceptions target 160",
        "payment exceptions target 160",
        "supplier payment reviews target 160",
        "vendor remittance reviews target 160",
        "remittance exceptions target 160",
        "payment term exceptions target 160",
        "供應商付款工單目標160件",
        "供應商付款例外目標160件",
        "付款例外目標160件",
        "匯款例外目標160件",
        "付款條件例外目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with supplier payment tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor payment tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier payment exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier payment reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor remittance reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with remittance exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment term exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商付款工單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商付款例外目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款例外目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款條件例外目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_contract_lifecycle_ops_targets():
    for target in (
        "contracts drafted target 160",
        "contracts reviewed target 160",
        "NDAs processed target 160",
        "SOW reviews target 160",
        "legal approvals target 160",
        "signature requests target 160",
        "agreements executed target 160",
        "renewal notices target 160",
        "合約起草目標160件",
        "簽署請求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with contracts drafted target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with signature requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with agreements executed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約起草目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_legal_contract_admin_ops_targets():
    for target in (
        "contract renewals target 160",
        "contract amendments target 160",
        "contract intakes target 160",
        "legal intakes target 160",
        "legal requests target 160",
        "legal tickets target 160",
        "合約續約目標160件",
        "合約修訂目標160件",
        "法務需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with contract renewals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract amendments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約續約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約修訂目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法務需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_legal_contract_admin_extension_targets():
    for target in (
        "NDA reviews target 160",
        "DPA reviews target 160",
        "contract clause reviews target 160",
        "contract metadata updates target 160",
        "signature packets target 160",
        "contract repository updates target 160",
        "legal playbook deviations target 160",
        "legal hold notices target 160",
        "合約條款審查目標160件",
        "簽署包目標160件",
        "合約資料更新目標160件",
        "法務保全通知目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with NDA reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DPA reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract clause reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with signature packets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal hold notices target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約條款審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_workflow_admin_queue_extension_targets():
    for target in (
        "approval queue items target 160",
        "routing rule changes target 160",
        "exception logs target 160",
        "document packets target 160",
        "review packets target 160",
        "intake queue items target 160",
        "follow-up tasks target 160",
        "admin tickets target 160",
        "workflow exceptions target 160",
        "case assignments target 160",
        "核准佇列項目目標160件",
        "例外紀錄目標160件",
        "文件資料包目標160件",
        "審查資料包目標160件",
        "進件佇列項目目標160件",
        "跟進任務目標160件",
        "行政工單目標160件",
        "流程例外目標160件",
        "案件指派目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with approval queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workflow exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case assignments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行政工單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_general_review_admin_extension_targets():
    for target in (
        "approval packets target 160",
        "review queue items target 160",
        "document review tasks target 160",
        "signoff requests target 160",
        "review comments target 160",
        "approval comments target 160",
        "核准資料包目標160件",
        "審查佇列項目目標160件",
        "文件審查任務目標160件",
        "簽核需求目標160件",
        "審查意見目標160件",
        "核准意見目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with approval packets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with document review tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with review comments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，審查佇列項目目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_implementation_admin_extension_targets():
    for target in (
        "implementation checklists target 160",
        "implementation tickets target 160",
        "implementation issues target 160",
        "implementation requests target 160",
        "migration checklists target 160",
        "migration tasks target 160",
        "migration issues target 160",
        "configuration requests target 160",
        "configuration tickets target 160",
        "go-live tasks target 160",
        "go-live readiness items target 160",
        "導入清單目標160件",
        "導入工單目標160件",
        "導入議題目標160件",
        "遷移清單目標160件",
        "遷移任務目標160件",
        "設定需求目標160件",
        "上線準備項目目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with implementation checklists target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with migration tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with configuration requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with go-live readiness items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，導入清單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_implementation_go_live_residual_extension_targets():
    for target in (
        "implementation approvals target 160",
        "go-live checklists target 160",
        "go-live requests target 160",
        "onboarding tasks target 160",
        "上線準備清單目標160件",
        "上線準備任務目標160件",
        "上線需求目標160件",
        "導入需求目標160件",
        "上線核准目標160件",
        "導入核准目標160件",
        "啟用任務目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with implementation approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with go-live checklists target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with go-live requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with onboarding tasks target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，上線準備任務目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_success_extension_targets():
    for target in (
        "renewal checklists target 160",
        "renewal tasks target 160",
        "renewal requests target 160",
        "adoption plans target 160",
        "adoption tasks target 160",
        "customer success reviews target 160",
        "success reviews target 160",
        "customer health reviews target 160",
        "續約清單目標160件",
        "續約任務目標160件",
        "續約需求目標160件",
        "採用計畫目標160件",
        "採用任務目標160件",
        "客戶成功審查目標160件",
        "客戶健康審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with renewal checklists target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with adoption plans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer success reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer health reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，續約清單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_marketing_reference_extension_targets():
    for target in (
        "testimonial requests target 160",
        "testimonial approvals target 160",
        "advocacy requests target 160",
        "advocacy tasks target 160",
        "reference program tasks target 160",
        "customer advocacy reviews target 160",
        "客戶案例核准目標160件",
        "客戶故事核准目標160件",
        "推薦語需求目標160件",
        "推薦語核准目標160件",
        "倡議任務目標160件",
        "參考計畫任務目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with testimonial requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with advocacy tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reference program tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer advocacy reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，推薦語需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_training_enablement_admin_extension_targets():
    for target in (
        "training attendance target 160",
        "enablement tasks target 160",
        "course assignments target 160",
        "learning tickets target 160",
        "certification requests target 160",
        "訓練需求目標160件",
        "訓練出席目標160人",
        "賦能任務目標160件",
        "課程註冊目標160件",
        "課程指派目標160件",
        "學習工單目標160件",
        "認證需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with training attendance target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with enablement tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with course assignments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with learning tickets target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_research_ux_ops_targets():
    for target in (
        "user interviews target 160",
        "customer interviews target 160",
        "usability tests target 160",
        "research participants target 160",
        "prototype tests target 160",
        "design reviews target 160",
        "design critiques target 160",
        "user journey maps target 160",
        "使用者訪談目標160場",
        "可用性測試目標160場",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with user interviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with usability tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with prototype tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with design reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，使用者訪談目標160場") == [160.0]


def test_extract_target_price_numbers_ignores_partner_sales_operations_ops_targets():
    for target in (
        "partner referrals target 160",
        "partner leads target 160",
        "channel pipeline target 160",
        "partner sourced pipeline target 160",
        "reseller meetings target 160",
        "partner trainings target 160",
        "夥伴轉介目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with partner referrals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with channel pipeline target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reseller meetings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with partner trainings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，夥伴轉介目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_vendor_ops_targets():
    for target in (
        "vendor reviews target 160",
        "supplier reviews target 160",
        "RFPs processed target 160",
        "PO approvals target 160",
        "vendor onboardings target 160",
        "供應商審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vendor reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RFPs processed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PO approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_vendor_security_risk_ops_targets():
    for target in (
        "security reviews target 160",
        "vendor risk reviews target 160",
        "third party risk reviews target 160",
        "security questionnaires target 160",
        "SOC2 reviews target 160",
        "風險審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with security reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor risk reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with security questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SOC2 reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_forecasting_ops_targets():
    for target in (
        "forecast calls target 160",
        "pipeline reviews target 160",
        "territory reviews target 160",
        "quota plans target 160",
        "sales forecasts target 160",
        "銷售預測目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with forecast calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pipeline reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with territory reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quota plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售預測目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compliance_audit_ops_targets():
    for target in (
        "audit reviews target 160",
        "audit review target 160",
        "control testing target 160",
        "controls testing target 160",
        "SOX testing target 160",
        "compliance audit reviews target 160",
        "internal audit reviews target 160",
        "合規審查目標160件",
        "稽核審查目標160件",
        "內控測試目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with audit reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control testing target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with internal audit reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SOX testing target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合規審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_close_monthly_extension_targets():
    for target in (
        "月結任務目標160件",
        "月結工作目標160件",
        "close checklist target 160",
        "close checklist items target 160",
        "month-end checklist target 160",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with close checklist target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with close checklist items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with month-end checklist target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，月結任務目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，月結工作目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_governance_committee_ops_targets():
    for target in (
        "committee reviews target 160",
        "board reviews target 160",
        "governance reviews target 160",
        "board committee reviews target 160",
        "governance committee reviews target 160",
        "委員會審查目標160件",
        "董事會審查目標160件",
        "治理審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with committee reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with governance reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board committee reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with governance committee reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，委員會審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，治理審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_policy_control_extension_targets():
    for target in (
        "control checklist target 160",
        "controls checklist target 160",
        "internal control checklist target 160",
        "accounting policies target 160",
        "finance policies target 160",
        "financial controls target 160",
        "財務政策目標160件",
        "內控清單目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with control checklist target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with internal control checklist target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with accounting policies target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with financial controls target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，財務政策目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，內控清單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_risk_assessment_ops_targets():
    for target in (
        "risk assessments target 160",
        "risk assessment target 160",
        "risk assessment reviews target 160",
        "enterprise risk assessments target 160",
        "operational risk assessments target 160",
        "market risk assessments target 160",
        "credit risk assessments target 160",
        "風險評估目標160件",
        "營運風險評估目標160件",
        "市場風險評估目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with risk assessments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk assessment reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with enterprise risk assessments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit risk assessments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，營運風險評估目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_risk_issue_management_ops_targets():
    for target in (
        "risk issues target 160",
        "issue remediations target 160",
        "risk treatment plans target 160",
        "mitigation actions target 160",
        "control issues target 160",
        "risk observations target 160",
        "風險議題目標160件",
        "緩解行動目標160件",
        "控制議題目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with risk issues target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk treatment plans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control issues target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險議題目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，緩解行動目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，控制議題目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_training_extension_targets():
    assert _extract_target_price_numbers("訓練聲明目標160件") == []

    assert _extract_target_price_numbers("目標價160元，訓練聲明目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_attestation_extension_targets():
    for target in (
        "合規聲明目標160件",
        "政策聲明目標160件",
        "員工聲明目標160件",
        "行為準則聲明目標160件",
        "訓練確認目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練確認目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_training_general_targets():
    for target in (
        "合規訓練目標160件",
        "政策訓練目標160件",
        "倫理訓練目標160件",
        "行為準則訓練目標160件",
        "員工訓練目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規訓練目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策訓練目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，倫理訓練目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則訓練目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工訓練目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_acknowledgment_targets():
    for target in (
        "policy acknowledgments target 160",
        "employee acknowledgments target 160",
        "code of conduct acknowledgments target 160",
        "政策確認書目標160件",
        "員工確認書目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with policy acknowledgments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with employee acknowledgments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with code of conduct acknowledgments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策確認書目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工確認書目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_confirmation_targets():
    for target in (
        "合規確認目標160件",
        "政策確認目標160件",
        "員工確認目標160件",
        "行為準則確認目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規確認目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策確認目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工確認目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則確認目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_record_completion_targets():
    for target in (
        "政策簽收目標160件",
        "員工簽收目標160件",
        "行為準則簽收目標160件",
        "合規簽收目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，政策簽收目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工簽收目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則簽收目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合規簽收目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_certification_targets():
    for target in (
        "合規認證目標160件",
        "政策認證目標160件",
        "員工認證目標160件",
        "行為準則認證目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規認證目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策認證目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工認證目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則認證目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_review_targets():
    for target in (
        "合規複核目標160件",
        "政策複核目標160件",
        "員工複核目標160件",
        "行為準則複核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規複核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策複核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工複核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則複核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_approval_targets():
    for target in (
        "合規核准目標160件",
        "政策核准目標160件",
        "員工核准目標160件",
        "行為準則核准目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則核准目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_assessment_targets():
    for target in (
        "合規評估目標160件",
        "政策評估目標160件",
        "員工評估目標160件",
        "行為準則評估目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則評估目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_audit_targets():
    for target in (
        "合規稽核目標160件",
        "政策稽核目標160件",
        "員工稽核目標160件",
        "行為準則稽核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規稽核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策稽核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工稽核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則稽核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_approval_review_targets():
    for target in (
        "合規覆核目標160件",
        "政策覆核目標160件",
        "員工覆核目標160件",
        "行為準則覆核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規覆核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策覆核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工覆核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則覆核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_inspection_targets():
    for target in (
        "合規檢查目標160件",
        "政策檢查目標160件",
        "員工檢查目標160件",
        "行為準則檢查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規檢查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策檢查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工檢查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則檢查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_checking_targets():
    for target in (
        "合規查核目標160件",
        "政策查核目標160件",
        "員工查核目標160件",
        "行為準則查核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規查核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策查核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工查核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則查核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_verification_check_targets():
    for target in (
        "合規檢核目標160件",
        "政策檢核目標160件",
        "員工檢核目標160件",
        "行為準則檢核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規檢核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策檢核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工檢核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則檢核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_audit_inspection_targets():
    for target in (
        "合規稽查目標160件",
        "政策稽查目標160件",
        "員工稽查目標160件",
        "行為準則稽查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規稽查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策稽查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工稽查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則稽查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_cross_check_targets():
    for target in (
        "合規核查目標160件",
        "政策核查目標160件",
        "員工核查目標160件",
        "行為準則核查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規核查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策核查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工核查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則核查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_self_check_targets():
    for target in (
        "合規自查目標160件",
        "政策自查目標160件",
        "員工自查目標160件",
        "行為準則自查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規自查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策自查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工自查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則自查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_people_compliance_examination_targets():
    for target in (
        "合規審查目標160件",
        "政策審查目標160件",
        "員工審查目標160件",
        "行為準則審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，合規審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compliance_policy_waiver_targets():
    for target in (
        "policy waivers target 160",
        "waiver requests target 160",
        "exception approvals target 160",
        "policy exception approvals target 160",
        "compliance waiver requests target 160",
        "政策豁免目標160件",
        "例外核准目標160件",
        "合規豁免申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，policy waivers target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，waiver requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，exception approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，policy exception approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，compliance waiver requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策豁免目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，例外核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合規豁免申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_risk_acceptance_exception_ops_targets():
    for target in (
        "risk acceptances target 160",
        "accepted risks target 160",
        "security exceptions target 160",
        "risk exceptions target 160",
        "control exceptions target 160",
        "風險接受目標160件",
        "資安例外目標160件",
        "控制例外目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，risk acceptances target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，accepted risks target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，security exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，risk exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，control exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險接受目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安例外目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，控制例外目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_ethics_hotline_case_targets():
    for target in (
        "ethics hotline cases target 160",
        "whistleblower reports target 160",
        "speak-up reports target 160",
        "conduct investigations target 160",
        "code of conduct investigations target 160",
        "倫理熱線案件目標160件",
        "吹哨檢舉目標160件",
        "行為準則調查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價160元，ethics hotline cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，whistleblower reports target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，speak-up reports target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，conduct investigations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，code of conduct investigations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，倫理熱線案件目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，吹哨檢舉目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行為準則調查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_business_continuity_resilience_targets():
    for target in (
        "incident response drills target 160",
        "business continuity tests target 160",
        "business continuity exercises target 160",
        "BCP tests target 160",
        "BCP exercises target 160",
        "DR tests target 160",
        "DR exercises target 160",
        "disaster recovery tests target 160",
        "disaster recovery exercises target 160",
        "recovery exercises target 160",
        "resilience tests target 160",
        "tabletop exercises target 160",
        "failover tests target 160",
        "RTO target 4 hours",
        "recovery time objective target 4 hours",
        "RPO target 15 minutes",
        "recovery point objective target 15 minutes",
        "備援演練目標160次",
        "營運持續演練目標160次",
        "災難復原測試目標160次",
        "業務持續演練目標160次",
        "災難復原演練目標160次",
        "復原時間目標4小時",
        "復原點目標15分鐘",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with incident response drills target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with BCP tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with disaster recovery tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with failover tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RTO target 4 hours") == [160.0]
    assert _extract_target_price_numbers("目標價160元，備援演練目標160次") == [160.0]
    assert _extract_target_price_numbers("目標價160元，業務持續演練目標160次") == [160.0]


def test_extract_target_price_numbers_ignores_workplace_safety_incident_targets():
    for target in (
        "safety incidents target 160",
        "recordable incidents target 160",
        "lost time injuries target 160",
        "near misses target 160",
        "safety observations target 160",
        "OSHA recordables target 160",
        "workplace incidents target 160",
        "工安事件目標160件",
        "職安事件目標160件",
        "虛驚事件目標160件",
        "安全觀察目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with safety incidents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with lost time injuries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with near misses target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，工安事件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_facility_inspection_capa_targets():
    for target in (
        "facility inspections target 160",
        "site inspections target 160",
        "quality inspections target 160",
        "safety inspections target 160",
        "inspection findings target 160",
        "corrective actions target 160",
        "CAPA items target 160",
        "廠區稽查目標160次",
        "安全檢查目標160次",
        "矯正措施目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with facility inspections target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with inspection findings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CAPA items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，廠區稽查目標160次") == [160.0]


def test_extract_target_price_numbers_ignores_legal_litigation_count_targets():
    for target in (
        "litigation cases target 160",
        "pending litigation target 160",
        "lawsuits target 160",
        "pending lawsuits target 160",
        "class actions target 160",
        "legal claims target 160",
        "legal proceedings target 160",
        "regulatory investigations target 160",
        "litigation settlements target 160",
        "legal settlements target NT$160M",
        "訴訟案件目標160件",
        "未決訴訟目標160件",
        "法律索賠目標160件",
        "集體訴訟目標160件",
        "和解案件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with litigation cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with class actions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal claims target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訴訟案件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_legal_litigation_matter_targets():
    for target in (
        "settlement conferences target 160",
        "settlement conference target 160",
        "matter intake forms target 160",
        "matter intake form target 160",
        "case intake forms target 160",
        "hearing notices target 160",
        "settlement memos target 160",
        "和解會議目標160件",
        "調解會議目標160件",
        "案件進件表目標160件",
        "案件進件單目標160件",
        "聽證通知目標160件",
        "和解備忘錄目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with settlement conferences target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with matter intake forms target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case intake forms target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with hearing notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with settlement memos target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，和解會議目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，調解會議目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，案件進件表目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，案件進件單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，聽證通知目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，和解備忘錄目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_clinical_trial_admin_targets():
    for target in (
        "site initiations target 160",
        "site initiation visits target 160",
        "site activations target 160",
        "monitoring visits target 160",
        "clinical monitoring visits target 160",
        "protocol deviations target 160",
        "query resolutions target 160",
        "case report forms target 160",
        "CRF completion target 160",
        "CRFs target 160",
        "IRB submissions target 160",
        "IRB approvals target 160",
        "ethics submissions target 160",
        "ethics approvals target 160",
        "SAE reports target 160",
        "試驗中心啟動目標160件",
        "試驗中心活化目標160件",
        "中心啟動訪視目標160件",
        "監測訪視目標160件",
        "試驗偏差目標160件",
        "查詢回覆目標160件",
        "病例報告表目標160件",
        "倫理送審目標160件",
        "IRB核准目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with site initiations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with monitoring visits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with protocol deviations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case report forms target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with IRB submissions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SAE reports target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，試驗中心啟動目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，監測訪視目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，病例報告表目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，倫理送審目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_product_compliance_document_targets():
    for target in (
        "technical files target 160",
        "technical file target 160",
        "declaration of conformity target 160",
        "declarations of conformity target 160",
        "conformity assessments target 160",
        "conformity assessment target 160",
        "label reviews target 160",
        "label review target 160",
        "manual reviews target 160",
        "manual review target 160",
        "IFU reviews target 160",
        "IFU review target 160",
        "product registrations target 160",
        "product registration target 160",
        "regulatory dossiers target 160",
        "regulatory dossier target 160",
        "產品技術文件目標160件",
        "符合性聲明目標160件",
        "符合性評估目標160件",
        "標籤審查目標160件",
        "手冊審查目標160件",
        "產品註冊目標160件",
        "法規檔案目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with technical files target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with declaration of conformity target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with label reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with IFU reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with regulatory dossiers target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，產品技術文件目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，符合性聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，標籤審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法規檔案目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_tax_compliance_admin_targets():
    for target in (
        "GST filings target 160",
        "GST filing target 160",
        "withholding certificates target 160",
        "withholding certificate target 160",
        "transfer pricing reports target 160",
        "transfer pricing report target 160",
        "tax provision workpapers target 160",
        "tax provision workpaper target 160",
        "tax notices target 160",
        "tax notice target 160",
        "tax assessments target 160",
        "tax assessment target 160",
        "稅務申報目標160件",
        "營業稅申報目標160件",
        "扣繳憑單目標160件",
        "移轉訂價報告目標160件",
        "稅務通知目標160件",
        "稅務查核目標160件",
        "稅務評估目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with GST filings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with withholding certificates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transfer pricing reports target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tax provision workpapers target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tax assessments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稅務申報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，扣繳憑單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，移轉訂價報告目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稅務通知目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_board_governance_admin_targets():
    for target in (
        "board packets target 160",
        "board packet target 160",
        "board agendas target 160",
        "board agenda target 160",
        "board minutes target 160",
        "board minute target 160",
        "minutes approvals target 160",
        "minute approvals target 160",
        "resolution drafts target 160",
        "resolution draft target 160",
        "written consents target 160",
        "written consent target 160",
        "consent agendas target 160",
        "committee charters target 160",
        "committee charter target 160",
        "director questionnaires target 160",
        "director questionnaire target 160",
        "board evaluations target 160",
        "board evaluation target 160",
        "board action items target 160",
        "governance calendar items target 160",
        "董事會資料包目標160件",
        "董事會議程目標160件",
        "董事會紀錄目標160件",
        "會議紀錄核准目標160件",
        "決議草案目標160件",
        "書面同意目標160件",
        "同意議程目標160件",
        "委員會章程目標160件",
        "董事問卷目標160件",
        "董事會評估目標160件",
        "董事會待辦事項目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with board packets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board agendas target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board minutes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with resolution drafts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with committee charters target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with director questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會資料包目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會紀錄目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，決議草案目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_it_access_service_desk_targets():
    for target in (
        "password resets target 160",
        "password reset target 160",
        "password reset requests target 160",
        "account unlocks target 160",
        "account unlock target 160",
        "account unlock requests target 160",
        "access requests target 160",
        "user access requests target 160",
        "access provisioning tickets target 160",
        "access provisioning ticket target 160",
        "access removal tickets target 160",
        "access removal ticket target 160",
        "permission changes target 160",
        "permission change target 160",
        "group membership changes target 160",
        "group membership change target 160",
        "role change requests target 160",
        "role change request target 160",
        "MFA resets target 160",
        "MFA reset target 160",
        "VPN access requests target 160",
        "VPN access request target 160",
        "software access requests target 160",
        "software access request target 160",
        "service desk tickets target 160",
        "service desk ticket target 160",
        "help desk tickets target 160",
        "help desk ticket target 160",
        "desktop support tickets target 160",
        "desktop support ticket target 160",
        "工單密碼重設目標160件",
        "密碼重設目標160件",
        "密碼重置目標160件",
        "帳號解鎖目標160件",
        "帳戶解鎖目標160件",
        "權限申請目標160件",
        "存取權限申請目標160件",
        "權限開通目標160件",
        "權限移除目標160件",
        "權限變更目標160件",
        "群組成員變更目標160件",
        "角色變更申請目標160件",
        "MFA重設目標160件",
        "VPN權限申請目標160件",
        "軟體權限申請目標160件",
        "服務台工單目標160件",
        "資訊服務台工單目標160件",
        "桌面支援工單目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with password resets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with account unlocks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access provisioning tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with permission changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with group membership changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MFA resets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with VPN access requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with service desk tickets target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，密碼重設目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳號解鎖目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，權限申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，服務台工單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_hr_benefits_payroll_admin_targets():
    for target in (
        "benefit enrollments target 160",
        "benefit enrollment target 160",
        "benefits cases target 160",
        "benefits claims target 160",
        "payroll corrections target 160",
        "payroll correction target 160",
        "payroll tickets target 160",
        "timecard corrections target 160",
        "timesheet approvals target 160",
        "leave requests target 160",
        "PTO requests target 160",
        "employee data changes target 160",
        "address changes target 160",
        "福利登錄目標160件",
        "福利申請目標160件",
        "薪資更正目標160件",
        "薪資工單目標160件",
        "工時表更正目標160件",
        "請假申請目標160件",
        "員工資料變更目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with benefit enrollments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payroll corrections target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with timesheet approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with leave requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，福利登錄目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，薪資更正目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，請假申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_success_admin_targets():
    for target in (
        "customer onboarding tasks target 160",
        "implementation tasks target 160",
        "QBR decks target 160",
        "business review decks target 160",
        "health check reviews target 160",
        "renewal playbooks target 160",
        "success plans target 160",
        "escalation reviews target 160",
        "customer callbacks target 160",
        "客戶導入任務目標160件",
        "導入任務目標160件",
        "商務回顧簡報目標160件",
        "客戶健檢審查目標160件",
        "續約作戰手冊目標160件",
        "客戶成功計畫目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer onboarding tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with QBR decks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with health check reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with success plans target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶導入任務目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，商務回顧簡報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶成功計畫目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_hr_recruiting_admin_targets():
    for target in (
        "offer letters target 160",
        "offer letter target 160",
        "interview debriefs target 160",
        "candidate slates target 160",
        "requisition approvals target 160",
        "job requisition approvals target 160",
        "background check reviews target 160",
        "reference checks target 160",
        "onboarding checklists target 160",
        "new hire packets target 160",
        "employee transfers target 160",
        "termination tickets target 160",
        "exit interviews target 160",
        "職缺核准目標160件",
        "錄用信目標160件",
        "面試回饋目標160件",
        "候選人名單目標160件",
        "背景查核審查目標160件",
        "到職清單目標160件",
        "新人資料包目標160件",
        "員工調職目標160件",
        "離職訪談目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with offer letters target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with background check reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with onboarding checklists target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with employee transfers target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，錄用信目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，到職清單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工調職目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_marketing_web_ops_admin_targets():
    for target in (
        "webinar registrations target 160",
        "event registrations target 160",
        "campaign briefs target 160",
        "landing page requests target 160",
        "creative tickets target 160",
        "content briefs target 160",
        "asset requests target 160",
        "brand approvals target 160",
        "email approvals target 160",
        "social posts target 160",
        "網路研討會報名目標160件",
        "活動報名目標160件",
        "活動簡報目標160件",
        "登陸頁需求目標160件",
        "素材工單目標160件",
        "內容簡報目標160件",
        "品牌核准目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with webinar registrations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with landing page requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with creative tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with brand approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，網路研討會報名目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，登陸頁需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，品牌核准目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_facilities_workplace_admin_targets():
    for target in (
        "room booking requests target 160",
        "desk booking requests target 160",
        "visitor badges target 160",
        "badge requests target 160",
        "parking permits target 160",
        "mailroom requests target 160",
        "catering requests target 160",
        "move requests target 160",
        "space planning requests target 160",
        "會議室預訂需求目標160件",
        "座位預約需求目標160件",
        "訪客證目標160件",
        "門禁卡申請目標160件",
        "停車證申請目標160件",
        "郵務需求目標160件",
        "餐飲申請目標160件",
        "搬遷申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with room booking requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with visitor badges target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with space planning requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訪客證目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，會議室預訂需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_hr_learning_training_admin_targets():
    for target in (
        "training enrollments target 160",
        "learning assignments target 160",
        "course completions target 160",
        "certification renewals target 160",
        "LMS tickets target 160",
        "訓練報名目標160件",
        "學習指派目標160件",
        "課程完成目標160件",
        "證照更新目標160件",
        "學習系統工單目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with training enrollments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with learning assignments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with LMS tickets target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練報名目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，學習指派目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_office_admin_targets():
    for target in (
        "meeting room requests target 160",
        "office supply requests target 160",
        "facilities tickets target 160",
        "reception requests target 160",
        "travel requests target 160",
        "expense reports target 160",
        "visitor logs target 160",
        "courier requests target 160",
        "會議室申請目標160件",
        "辦公用品申請目標160件",
        "總務工單目標160件",
        "接待需求目標160件",
        "差旅申請目標160件",
        "費用報告目標160件",
        "快遞需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with meeting room requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with facilities tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reception requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，會議室申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，總務工單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_ap_ar_admin_targets():
    for target in (
        "invoice approvals target 160",
        "invoice exceptions target 160",
        "invoice queue items target 160",
        "invoice approval queue target 160",
        "payment runs target 160",
        "payment approvals target 160",
        "payment reviews target 160",
        "payment review items target 160",
        "payment audit items target 160",
        "payment queue items target 160",
        "payment approval queue target 160",
        "collection calls target 160",
        "collections reviews target 160",
        "receivables reviews target 160",
        "AR collections target 160",
        "AR review items target 160",
        "credit memos target 160",
        "credit memo queue items target 160",
        "credit memo queue reviews target 160",
        "credit memo work queue target 160",
        "cash application items target 160",
        "cash receipt reviews target 160",
        "cash application reviews target 160",
        "collections queue items target 160",
        "collections queue reviews target 160",
        "collections work queue target 160",
        "collection work queue target 160",
        "receivables queue items target 160",
        "receivables queue reviews target 160",
        "receivables work queue target 160",
        "receivable work queue target 160",
        "AR queue items target 160",
        "AR queue reviews target 160",
        "AR work queue target 160",
        "accounts receivable queue items target 160",
        "accounts receivable work queue target 160",
        "cash receipt queues target 160",
        "cash receipt queue items target 160",
        "cash application queue items target 160",
        "cash application exceptions target 160",
        "cash application work items target 160",
        "vendor invoices target 160",
        "vendor invoice queue reviews target 160",
        "vendor invoice work queue target 160",
        "vendor payment queue reviews target 160",
        "vendor payment work queue target 160",
        "supplier invoice queue reviews target 160",
        "supplier invoice work queue target 160",
        "supplier payment queue reviews target 160",
        "supplier payment work queue target 160",
        "payment term exception queue items target 160",
        "payment term exception work queue target 160",
        "payment exception queue items target 160",
        "payment exception work queue target 160",
        "invoice exception queue items target 160",
        "invoice exception work queue target 160",
        "vendor master update queue items target 160",
        "vendor master updates queue items target 160",
        "vendor master update work queue target 160",
        "vendor master updates work queue target 160",
        "supplier master update queue items target 160",
        "supplier master updates queue items target 160",
        "supplier master update work queue target 160",
        "supplier master updates work queue target 160",
        "vendor onboarding queue items target 160",
        "vendor onboarding queue reviews target 160",
        "vendor onboarding form queue items target 160",
        "vendor onboarding packet queue items target 160",
        "vendor onboarding packets queue reviews target 160",
        "supplier intake queue reviews target 160",
        "supplier intake form queue items target 160",
        "supplier intake forms queue reviews target 160",
        "supplier onboarding form queue items target 160",
        "supplier onboarding packet queue reviews target 160",
        "supplier setup packet queue items target 160",
        "supplier setup packets queue reviews target 160",
        "contract intake queue reviews target 160",
        "contract intake work queue target 160",
        "contract intake reviews queue items target 160",
        "vendor renewal notice queue items target 160",
        "third-party attestation queue items target 160",
        "tax provision workpaper queue items target 160",
        "supplier remittance update queue items target 160",
        "payment term change queue items target 160",
        "board packet queue items target 160",
        "board packets queue reviews target 160",
        "board agenda queue items target 160",
        "board agendas queue reviews target 160",
        "board minutes queue items target 160",
        "resolution draft queue items target 160",
        "written consent queue items target 160",
        "consent agenda queue items target 160",
        "committee charter queue reviews target 160",
        "director questionnaire queue items target 160",
        "board evaluation queue items target 160",
        "board action item queue items target 160",
        "governance calendar item queue items target 160",
        "password reset queue items target 160",
        "password reset request queue items target 160",
        "account unlock queue items target 160",
        "account unlock request queue items target 160",
        "access provisioning ticket queue items target 160",
        "access removal ticket queue items target 160",
        "permission change queue items target 160",
        "group membership change queue reviews target 160",
        "role change request queue items target 160",
        "MFA reset queue items target 160",
        "VPN access request queue items target 160",
        "software access request queue items target 160",
        "service desk ticket queue items target 160",
        "help desk ticket queue reviews target 160",
        "desktop support ticket queue items target 160",
        "technical file queue items target 160",
        "technical files queue reviews target 160",
        "declaration of conformity queue items target 160",
        "declarations of conformity queue reviews target 160",
        "conformity assessment queue reviews target 160",
        "product registration queue items target 160",
        "regulatory dossier queue items target 160",
        "settlement conference queue items target 160",
        "matter intake form queue items target 160",
        "case intake form queue reviews target 160",
        "hearing notice queue items target 160",
        "settlement memo queue items target 160",
        "benefit enrollment queue items target 160",
        "benefit case queue items target 160",
        "benefit claim queue items target 160",
        "payroll correction queue items target 160",
        "payroll ticket queue items target 160",
        "timecard correction queue items target 160",
        "leave request queue items target 160",
        "billing disputes target 160",
        "billing queue items target 160",
        "billing queue reviews target 160",
        "billing dispute queue items target 160",
        "billing dispute work queue target 160",
        "remittance advices target 160",
        "remittance reviews target 160",
        "remittance queue items target 160",
        "remittance queue reviews target 160",
        "remittance work queue target 160",
        "refund request queue items target 160",
        "refund request work queue target 160",
        "dunning queue items target 160",
        "dunning work queue target 160",
        "reconciliation reviews target 160",
        "reconciliation queue items target 160",
        "reconciliation review items target 160",
        "account reconciliation review items target 160",
        "bank reconciliation review items target 160",
        "發票核准目標160件",
        "發票例外目標160件",
        "發票審核目標160件",
        "發票查核目標160件",
        "發票佇列項目目標160件",
        "付款批次目標160件",
        "付款核准目標160件",
        "付款審查目標160件",
        "付款查核目標160件",
        "付款佇列項目目標160件",
        "催收電話目標160件",
        "催收佇列項目目標160件",
        "付款例外佇列項目目標160件",
        "折讓單目標160件",
        "折讓單佇列項目目標160件",
        "收款審查目標160件",
        "收款沖帳目標160件",
        "收款佇列項目目標160件",
        "收款佇列審查目標160件",
        "收款沖帳審查目標160件",
        "應收審查目標160件",
        "應收佇列項目目標160件",
        "應收佇列審查目標160件",
        "帳單爭議目標160件",
        "帳單佇列項目目標160件",
        "帳單爭議佇列項目目標160件",
        "匯款通知目標160件",
        "匯款審查目標160件",
        "匯款佇列項目目標160件",
        "對帳審查目標160件",
        "帳戶調節目標160件",
        "對帳佇列項目目標160件",
        "調節審查目標160件",
        "帳戶調節審查目標160件",
        "銀行調節審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with invoice exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice audit items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice approval queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment review items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment audit items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment approval queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collection calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collections reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivables reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR collections target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR review items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with remittance reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit memos target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit memo queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit memo queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit memo work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with remittance queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with remittance queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with remittance work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash receipt reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash application reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collections queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collections queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collections work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collection work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivables queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivables queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivables work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with receivable work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with accounts receivable queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with accounts receivable work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash receipt queues target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash receipt queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash application queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash application exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cash application work items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor invoice queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor invoice work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor payment queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor payment work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier invoice queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier invoice work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier payment queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier payment work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment term exception queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment term exception work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment exception queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment exception work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice exception queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice exception work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor master update queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor master updates queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor master update work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor master updates work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier master update queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier master updates queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier master update work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier master updates work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding form queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding packet queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding packets queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier intake queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier intake form queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier intake forms queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier onboarding form queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier onboarding packet queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier setup packet queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier setup packets queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract intake queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract intake work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract intake reviews queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor renewal notice queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third-party attestation queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tax provision workpaper queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier remittance update queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment term change queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board packet queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board packets queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board agenda queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board agendas queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board minutes queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with resolution draft queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with written consent queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with consent agenda queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with committee charter queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with director questionnaire queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board evaluation queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board action item queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with governance calendar item queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with password reset queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with password reset request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with account unlock queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with account unlock request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access provisioning ticket queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access removal ticket queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with permission change queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with group membership change queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with role change request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MFA reset queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with VPN access request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with software access request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with service desk ticket queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with help desk ticket queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with desktop support ticket queue items target 160") == [160.0]
    for context in (
        "technical file queue items target 160",
        "technical files queue reviews target 160",
        "declaration of conformity queue items target 160",
        "declarations of conformity queue reviews target 160",
        "conformity assessment queue reviews target 160",
        "product registration queue items target 160",
        "regulatory dossier queue items target 160",
        "settlement conference queue items target 160",
        "matter intake form queue items target 160",
        "case intake form queue reviews target 160",
        "hearing notice queue items target 160",
        "settlement memo queue items target 160",
        "benefit enrollment queue items target 160",
        "benefit case queue items target 160",
        "benefit claim queue items target 160",
        "payroll correction queue items target 160",
        "payroll ticket queue items target 160",
        "timecard correction queue items target 160",
        "leave request queue items target 160",
    ):
        assert _extract_target_price_numbers(f"target price NT$160 with {context}") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing queue reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing dispute queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing dispute work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with refund request queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with refund request work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dunning queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dunning work queue target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reconciliation reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reconciliation queue items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reconciliation review items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with account reconciliation review items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with bank reconciliation review items target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票審核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票查核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款批次目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款查核目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，催收佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款例外佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，折讓單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，折讓單佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，收款審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，應收審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，應收佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，應收佇列審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，匯款審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，匯款佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，收款佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，收款佇列審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，收款沖帳審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳單佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳單爭議佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，對帳審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳戶調節目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，對帳佇列項目目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，調節審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳戶調節審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銀行調節審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_ops_admin_targets():
    for target in (
        "quote approvals target 160",
        "deal desk tickets target 160",
        "contract redlines target 160",
        "discount approvals target 160",
        "CRM updates target 160",
        "order forms target 160",
        "salesforce cases target 160",
        "territory changes target 160",
        "commission adjustments target 160",
        "partner deal registrations target 160",
        "pricing exceptions target 160",
        "報價核准目標160件",
        "交易支援工單目標160件",
        "合約紅線目標160件",
        "折扣核准目標160件",
        "CRM更新目標160件",
        "訂單表單目標160件",
        "業務區域變更目標160件",
        "佣金調整目標160件",
        "價格例外目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with quote approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deal desk tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CRM updates target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，報價核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，佣金調整目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_data_governance_admin_targets():
    for target in (
        "data access requests target 160",
        "data deletion requests target 160",
        "DSAR requests target 160",
        "data quality tickets target 160",
        "schema change requests target 160",
        "metadata updates target 160",
        "data catalog tickets target 160",
        "data lineage tickets target 160",
        "data retention reviews target 160",
        "privacy requests target 160",
        "資料存取申請目標160件",
        "資料刪除請求目標160件",
        "資料品質工單目標160件",
        "結構變更申請目標160件",
        "中繼資料更新目標160件",
        "資料目錄工單目標160件",
        "資料血緣工單目標160件",
        "資料保存審查目標160件",
        "隱私請求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data quality tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with schema change requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data lineage tickets target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料品質工單目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料目錄工單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_close_admin_targets():
    for target in (
        "account review signoffs target 160",
        "account review approvals target 160",
        "flux analyses target 160",
        "variance analyses target 160",
        "consolidation journals target 160",
        "intercompany eliminations target 160",
        "accrual reviews target 160",
        "supporting schedules target 160",
        "financial statement reviews target 160",
        "close issue logs target 160",
        "科目審查簽核目標160件",
        "波動分析目標160件",
        "差異分析目標160件",
        "合併分錄目標160筆",
        "內部往來沖銷目標160件",
        "應計審查目標160件",
        "財報審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with account review signoffs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with flux analyses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with intercompany eliminations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，波動分析目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合併分錄目標160筆") == [160.0]


def test_extract_target_price_numbers_ignores_product_recall_warranty_quality_targets():
    for target in (
        "product recalls target 160",
        "recalls target 160",
        "recall events target 160",
        "warranty claims target 160",
        "RMA claims target 160",
        "RMA cases target 160",
        "service campaigns target 160",
        "quality complaints target 160",
        "產品召回目標160件",
        "保固索賠目標160件",
        "退貨授權目標160件",
        "服務活動目標160件",
        "品質客訴目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with product recalls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with warranty claims target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with service campaigns target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，產品召回目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_environmental_incident_compliance_targets():
    for target in (
        "environmental incidents target 160",
        "environmental violations target 160",
        "permit violations target 160",
        "spills target 160",
        "chemical spills target 160",
        "waste spills target 160",
        "environmental fines target NT$160M",
        "environmental penalties target NT$160M",
        "環境事件目標160件",
        "環保違規目標160件",
        "許可違規目標160件",
        "洩漏事件目標160件",
        "環境罰款目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with environmental incidents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with chemical spills target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with environmental fines target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，環境事件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_hr_labor_relations_case_targets():
    for target in (
        "labor grievances target 160",
        "labour grievances target 160",
        "employee grievances target 160",
        "union grievances target 160",
        "labor disputes target 160",
        "labour disputes target 160",
        "union disputes target 160",
        "employee relations cases target 160",
        "labor relations cases target 160",
        "employee complaints target 160",
        "workplace complaints target 160",
        "勞資爭議目標160件",
        "勞動爭議目標160件",
        "員工申訴目標160件",
        "工會申訴目標160件",
        "工會爭議目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with labor grievances target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with employee relations cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with union disputes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，勞資爭議目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compensation_benefits_admin_targets():
    for target in (
        "workers comp claims target 160",
        "workers compensation claims target 160",
        "benefit claims target 160",
        "benefits claims target 160",
        "benefits administration cases target 160",
        "payroll errors target 160",
        "payroll cases target 160",
        "payroll disputes target 160",
        "wage claims target 160",
        "wage complaints target 160",
        "薪資錯誤目標160件",
        "薪資爭議目標160件",
        "福利申請目標160件",
        "工傷理賠目標160件",
        "職災理賠目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with workers comp claims target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payroll errors target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benefits administration cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，薪資錯誤目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_esg_community_social_targets():
    for target in (
        "community complaints target 160",
        "community grievances target 160",
        "community incidents target 160",
        "human rights grievances target 160",
        "human rights complaints target 160",
        "land access disputes target 160",
        "resettlement cases target 160",
        "community investment target NT$160M",
        "社區申訴目標160件",
        "社區爭議目標160件",
        "人權申訴目標160件",
        "土地使用爭議目標160件",
        "安置案件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with community complaints target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with human rights grievances target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with community investment target NT$160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，社區申訴目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_supplier_compliance_targets():
    for target in (
        "supplier audits target 160",
        "supplier nonconformances target 160",
        "supplier code violations target 160",
        "responsible sourcing audits target 160",
        "conflict minerals findings target 160",
        "modern slavery findings target 160",
        "forced labor findings target 160",
        "供應商稽核目標160次",
        "供應商不符合事項目標160件",
        "責任採購稽核目標160次",
        "衝突礦產缺失目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with supplier audits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with conflict minerals findings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with modern slavery findings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商稽核目標160次") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_claims_admin_targets():
    for target in (
        "claims processed target 160",
        "claim denials target 160",
        "policyholder complaints target 160",
        "underwriting cases target 160",
        "policy renewals target 160",
        "policies issued target 160",
        "理賠處理目標160件",
        "理賠積案目標160件",
        "拒賠案件目標160件",
        "保戶申訴目標160件",
        "核保案件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with claims processed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with policyholder complaints target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with underwriting cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，理賠處理目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_dei_training_workforce_targets():
    for target in (
        "diversity hires target 160",
        "diverse hires target 160",
        "women in leadership target 160",
        "female managers target 160",
        "training completions target 160",
        "mandatory training completion target 160",
        "DEI incidents target 160",
        "diversity complaints target 160",
        "多元聘用目標160人",
        "女性主管目標160人",
        "必修訓練完成目標160人",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with diversity hires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with women in leadership target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with training completions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，多元聘用目標160人") == [160.0]


def test_extract_target_price_numbers_ignores_hiring_headcount_workforce_targets():
    for target in (
        "new hires target 160",
        "hires target 160",
        "open requisitions target 160",
        "job openings target 160",
        "vacancies target 160",
        "positions filled target 160",
        "time to fill target 160 days",
        "FTE target 160",
        "新增聘用目標160人",
        "招聘職缺目標160個",
        "補缺天數目標160天",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with new hires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with open requisitions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with time to fill target 160 days") == [160.0]
    assert _extract_target_price_numbers("目標價160元，招聘職缺目標160個") == [160.0]


def test_extract_target_price_numbers_ignores_records_audit_compliance_targets():
    for target in (
        "audit exceptions target 160",
        "compliance exceptions target 160",
        "policy breaches target 160",
        "policy attestations target 160",
        "training attestations target 160",
        "records archived target 160",
        "documents reviewed target 160",
        "document exceptions target 160",
        "稽核例外目標160件",
        "合規例外目標160件",
        "政策違反目標160件",
        "文件審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with audit exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with policy breaches target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with documents reviewed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核例外目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_tax_treasury_compliance_targets():
    for target in (
        "tax audits target 160",
        "tax disputes target 160",
        "tax filings target 160",
        "VAT filings target 160",
        "transfer pricing adjustments target 160",
        "withholding tax cases target 160",
        "treasury exceptions target 160",
        "稅務稽核目標160件",
        "稅務爭議目標160件",
        "移轉訂價調整目標160件",
        "資金調節例外目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with tax audits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transfer pricing adjustments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with treasury exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稅務稽核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_corporate_governance_filing_targets():
    for target in (
        "board meetings target 160",
        "committee meetings target 160",
        "shareholder proposals target 160",
        "proxy votes target 160",
        "governance filings target 160",
        "SEC filings target 160",
        "insider filings target 160",
        "董事會會議目標160次",
        "委員會會議目標160次",
        "股東提案目標160件",
        "關係人交易目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with board meetings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shareholder proposals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with governance filings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會會議目標160次") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_data_governance_targets():
    for target in (
        "data subject requests target 160",
        "privacy complaints target 160",
        "privacy requests target 160",
        "data retention exceptions target 160",
        "records retention exceptions target 160",
        "records disposed target 160",
        "資料主體請求目標160件",
        "資料當事人請求目標160件",
        "隱私申訴目標160件",
        "資料保存例外目標160件",
        "資料刪除請求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data subject requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with privacy complaints target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with records disposed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料主體請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料當事人請求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_billing_collections_finance_ops_targets():
    for target in (
        "invoices processed target 160",
        "billing disputes target 160",
        "collection cases target 160",
        "write-off cases target 160",
        "bad debt cases target 160",
        "發票處理目標160件",
        "帳款爭議目標160件",
        "催收案件目標160件",
        "呆帳案件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with invoices processed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing disputes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collection cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票處理目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_ap_ar_ops_targets():
    for target in (
        "invoice approvals target 160",
        "vendor invoices target 160",
        "AP invoices target 160",
        "AR invoices target 160",
        "payment runs target 160",
        "expense reports target 160",
        "purchase requisitions target 160",
        "發票核准目標160件",
        "供應商發票目標160件",
        "費用報告目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with invoice approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor invoices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AP invoices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AR invoices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment runs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with expense reports target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with purchase requisitions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商發票目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，費用報告目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_disclosure_publication_targets():
    for target in (
        "press releases target 160",
        "earnings releases target 160",
        "annual reports target 160",
        "sustainability reports target 160",
        "ESG reports target 160",
        "integrated reports target 160",
        "regulatory disclosures target 160",
        "disclosure items target 160",
        "media mentions target 160",
        "新聞稿目標160篇",
        "年報目標160份",
        "永續報告目標160份",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with press releases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with annual reports target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with regulatory disclosures target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，新聞稿目標160篇") == [160.0]


def test_extract_target_price_numbers_ignores_investor_relations_event_targets():
    for target in (
        "investor meetings target 160",
        "investor roadshows target 160",
        "roadshows target 160",
        "earnings calls target 160",
        "conference appearances target 160",
        "analyst meetings target 160",
        "shareholder inquiries target 160",
        "IR inquiries target 160",
        "法人說明會目標160場",
        "投資人會議目標160場",
        "股東詢問目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with investor meetings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with earnings calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shareholder inquiries target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法人說明會目標160場") == [160.0]


def test_extract_target_price_numbers_ignores_sales_presales_admin_targets():
    for target in (
        "RFP responses target 160",
        "proposals submitted target 160",
        "demos target 160",
        "product demos target 160",
        "trials started target 160",
        "pilots target 160",
        "POCs target 160",
        "proof-of-concepts target 160",
        "客戶提案目標160件",
        "產品展示目標160場",
        "試用啟動目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with RFP responses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with product demos target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with POCs target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶提案目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_pipeline_admin_ops_targets():
    for target in (
        "opportunities created target 160",
        "leads qualified target 160",
        "sales activities target 160",
        "pipeline updates target 160",
        "forecast submissions target 160",
        "quote requests target 160",
        "商機建立目標160件",
        "銷售活動目標160件",
        "預測提交目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with opportunities created target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with leads qualified target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales activities target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pipeline updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with forecast submissions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quote requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，商機建立目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售活動目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，預測提交目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_success_implementation_targets():
    for target in (
        "customer onboardings target 160",
        "onboarding projects target 160",
        "implementations target 160",
        "implementation projects target 160",
        "customer health checks target 160",
        "business reviews target 160",
        "QBRs target 160",
        "客戶導入目標160件",
        "導入專案目標160件",
        "客戶健檢目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer onboardings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with implementation projects target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with QBRs target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶導入目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_software_engineering_delivery_targets():
    for target in (
        "bugs fixed target 160",
        "defects resolved target 160",
        "escaped defects target 160",
        "story points target 160",
        "sprint velocity target 160",
        "deployments target 160",
        "software releases target 160",
        "code reviews target 160",
        "pull requests target 160",
        "缺陷修復目標160件",
        "程式碼審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with bugs fixed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deployments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pull requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，缺陷修復目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_close_accounting_ops_targets():
    for target in (
        "journal entries target 160",
        "manual journal entries target 160",
        "account reconciliations target 160",
        "balance sheet reconciliations target 160",
        "close tasks target 160",
        "month-end close tasks target 160",
        "manual adjustments target 160",
        "財報關帳目標160項",
        "會計分錄目標160筆",
        "調節項目目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with journal entries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with close tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with manual adjustments target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，財報關帳目標160項") == [160.0]


def test_extract_target_price_numbers_ignores_content_moderation_trust_safety_targets():
    for target in (
        "moderation actions target 160",
        "content reviews target 160",
        "abuse reports target 160",
        "policy violations target 160",
        "trust and safety cases target 160",
        "user reports target 160",
        "appeals resolved target 160",
        "內容審核目標160件",
        "濫用檢舉目標160件",
        "申訴處理目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with moderation actions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with content reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with appeals resolved target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，內容審核目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_mlops_data_labeling_targets():
    for target in (
        "model evaluations target 160",
        "model validation runs target 160",
        "labeling tasks target 160",
        "annotation tasks target 160",
        "datasets reviewed target 160",
        "training jobs target 160",
        "inference jobs target 160",
        "模型評測目標160次",
        "標註任務目標160件",
        "資料集審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with model evaluations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with labeling tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with inference jobs target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，模型評測目標160次") == [160.0]


def test_extract_target_price_numbers_ignores_project_management_delivery_targets():
    for target in (
        "milestones completed target 160",
        "project milestones target 160",
        "tasks completed target 160",
        "open tasks target 160",
        "backlog items target 160",
        "requirements completed target 160",
        "change requests target 160",
        "專案里程碑目標160項",
        "任務完成目標160件",
        "變更請求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with milestones completed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with backlog items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with change requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，專案里程碑目標160項") == [160.0]


def test_extract_target_price_numbers_ignores_fulfillment_warehouse_ops_targets():
    for target in (
        "orders fulfilled target 160K",
        "shipments processed target 160K",
        "packages sorted target 160K",
        "picks completed target 160K",
        "packs completed target 160K",
        "warehouse tasks target 160K",
        "returns processed target 160K",
        "訂單履約目標160萬",
        "包裹分揀目標160萬",
        "退貨處理目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with orders fulfilled target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shipments processed target 160K") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with returns processed target 160K") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單履約目標160萬") == [160.0]


def test_extract_target_price_numbers_ignores_field_service_ops_targets():
    for target in (
        "service visits target 160",
        "technician visits target 160",
        "truck rolls target 160",
        "work orders target 160",
        "maintenance work orders target 160",
        "dispatches target 160",
        "installs completed target 160",
        "現場服務目標160件",
        "派工目標160件",
        "工單完成目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with service visits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with truck rolls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with installs completed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，派工目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_partner_channel_enablement_targets():
    for target in (
        "partner certifications target 160",
        "partner onboarding target 160",
        "partner training sessions target 160",
        "partner enablement sessions target 160",
        "channel trainings target 160",
        "partner demos target 160",
        "co-sell opportunities target 160",
        "夥伴認證目標160件",
        "通路訓練目標160場",
        "共同銷售機會目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with partner certifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with channel trainings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with co-sell opportunities target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，夥伴認證目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_supplier_admin_targets():
    for target in (
        "supplier onboarding target 160",
        "vendor onboarding target 160",
        "supplier certifications target 160",
        "vendor certifications target 160",
        "purchase orders processed target 160",
        "POs processed target 160",
        "sourcing events target 160",
        "RFQs completed target 160",
        "供應商導入目標160件",
        "供應商認證目標160件",
        "採購單處理目標160件",
        "詢價完成目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with supplier onboarding target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with purchase orders processed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with RFQs completed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商導入目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_sourcing_admin_targets():
    for target in (
        "sourcing requests target 160",
        "bid events target 160",
        "supplier questionnaires target 160",
        "vendor questionnaires target 160",
        "contract handoffs target 160",
        "採購需求目標160件",
        "供應商問卷目標160件",
        "廠商問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with sourcing requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with bid events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，採購需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，廠商問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_facilities_workplace_ops_targets():
    for target in (
        "facility requests target 160",
        "workplace tickets target 160",
        "desk reservations target 160",
        "room bookings target 160",
        "move requests target 160",
        "space plans target 160",
        "設施需求目標160件",
        "座位預約目標160件",
        "會議室預訂目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with facility requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workplace tickets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with desk reservations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，設施需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，座位預約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，會議室預訂目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_corporate_travel_admin_ops_targets():
    for target in (
        "travel requests target 160",
        "expense preapprovals target 160",
        "trip approvals target 160",
        "旅遊申請目標160件",
        "差旅核准目標160件",
        "機票預訂目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with travel requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trip approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with flight bookings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，旅遊申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，差旅核准目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，機票預訂目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_admin_access_request_ops_targets():
    for target in (
        "badge requests target 160",
        "access card requests target 160",
        "parking permits target 160",
        "visitor passes target 160",
        "mailroom requests target 160",
        "門禁卡申請目標160件",
        "停車證申請目標160件",
        "訪客證目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with badge requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access card requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with parking permits target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，門禁卡申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，停車證申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訪客證目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_office_service_admin_ops_targets():
    for target in (
        "equipment requests target 160",
        "supply requests target 160",
        "office supply requests target 160",
        "workspace requests target 160",
        "relocation requests target 160",
        "設備需求目標160件",
        "辦公用品申請目標160件",
        "搬遷申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with equipment requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supply requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with office supply requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workspace requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with relocation requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，設備需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，辦公用品申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，搬遷申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_asset_device_admin_ops_targets():
    for target in (
        "asset requests target 160",
        "asset tags target 160",
        "device requests target 160",
        "equipment loans target 160",
        "laptop requests target 160",
        "資產申請目標160件",
        "設備借用目標160件",
        "筆電申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with asset requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with asset tags target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with device requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with equipment loans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with laptop requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資產申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，設備借用目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，筆電申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_internal_comms_admin_ops_targets():
    for target in (
        "announcement requests target 160",
        "newsletter items target 160",
        "intranet updates target 160",
        "town hall questions target 160",
        "communications requests target 160",
        "公告申請目標160件",
        "內網更新目標160件",
        "溝通需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with announcement requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with newsletter items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with intranet updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with town hall questions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with communications requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，公告申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，內網更新目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，溝通需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_forms_records_admin_ops_targets():
    for target in (
        "form submissions target 160",
        "records requests target 160",
        "document requests target 160",
        "template requests target 160",
        "workflow requests target 160",
        "表單提交目標160件",
        "紀錄申請目標160件",
        "文件申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with form submissions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with records requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with document requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with template requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workflow requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，表單提交目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，紀錄申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，文件申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_survey_feedback_admin_ops_targets():
    for target in (
        "survey responses target 160",
        "feedback items target 160",
        "pulse survey responses target 160",
        "engagement survey responses target 160",
        "feedback requests target 160",
        "問卷回覆目標160件",
        "意見回饋目標160件",
        "調查回覆目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with survey responses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with feedback items target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pulse survey responses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with engagement survey responses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with feedback requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，問卷回覆目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，意見回饋目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，調查回覆目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_creative_content_admin_ops_targets():
    for target in (
        "design requests target 160",
        "content requests target 160",
        "copy requests target 160",
        "translation requests target 160",
        "brand requests target 160",
        "設計需求目標160件",
        "內容需求目標160件",
        "翻譯申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with design requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with content requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with copy requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with translation requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with brand requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，設計需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，內容需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，翻譯申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_meeting_event_admin_ops_targets():
    for target in (
        "event requests target 160",
        "meeting requests target 160",
        "event registrations target 160",
        "catering requests target 160",
        "venue requests target 160",
        "活動申請目標160件",
        "會議需求目標160件",
        "餐飲申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with event requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with meeting requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with event registrations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with catering requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with venue requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活動申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，會議需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，餐飲申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_knowledge_training_admin_ops_targets():
    for target in (
        "training requests target 160",
        "knowledge base updates target 160",
        "learning requests target 160",
        "course requests target 160",
        "enablement requests target 160",
        "訓練申請目標160件",
        "知識庫更新目標160件",
        "課程需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with training requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with knowledge base updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with learning requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with course requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with enablement requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練申請目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，知識庫更新目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，課程需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_community_support_admin_ops_targets():
    for target in (
        "community questions target 160",
        "forum posts target 160",
        "support articles target 160",
        "user group requests target 160",
        "社群問題目標160件",
        "論壇貼文目標160件",
        "支援文章目標160件",
        "使用者社群需求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with community questions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with forum posts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with support articles target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with user group requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，社群問題目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，論壇貼文目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支援文章目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，使用者社群需求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_workspace_collaboration_admin_ops_targets():
    for target in (
        "workspace requests target 160",
        "workspace posts target 160",
        "channel requests target 160",
        "collaboration requests target 160",
        "shared document requests target 160",
        "協作需求目標160件",
        "工作區貼文目標160件",
        "頻道申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with workspace requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workspace posts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with channel requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collaboration requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with shared document requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，協作需求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，工作區貼文目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，頻道申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_residual_admin_ops_targets():
    for target in (
        "testimonials target 160",
        "customer references target 160",
        "功能發布目標160件",
        "release notes target 160",
        "訂單表單目標160件",
        "quote reviews target 160",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with testimonials target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer references target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，功能發布目標160件") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with release notes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂單表單目標160件") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quote reviews target 160") == [160.0]


def test_extract_target_price_numbers_ignores_sales_planning_admin_ops_targets():
    for target in (
        "forecast calls target 160",
        "pipeline reviews target 160",
        "territory reviews target 160",
        "quota plans target 160",
        "sales forecasts target 160",
        "銷售預測目標160件",
        "管線審查目標160件",
        "配額計畫目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with forecast calls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pipeline reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with territory reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quota plans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales forecasts target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售預測目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，管線審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，配額計畫目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_research_ops_targets():
    for target in (
        "user interviews target 160",
        "customer interviews target 160",
        "usability tests target 160",
        "research participants target 160",
        "prototype tests target 160",
        "design reviews target 160",
        "使用者訪談目標160件",
        "研究參與者目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with user interviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer interviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with usability tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with research participants target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with prototype tests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with design reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，使用者訪談目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，研究參與者目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_security_vendor_risk_admin_ops_targets():
    for target in (
        "vendor reviews target 160",
        "supplier reviews target 160",
        "vendor risk reviews target 160",
        "third party risk reviews target 160",
        "security questionnaires target 160",
        "SOC2 reviews target 160",
        "供應商審查目標160件",
        "資安問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vendor reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor risk reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third party risk reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with security questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SOC2 reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_compliance_privacy_questionnaire_targets():
    for target in (
        "compliance questionnaires target 160",
        "policy questionnaires target 160",
        "privacy questionnaires target 160",
        "risk questionnaires target 160",
        "合規問卷目標160件",
        "政策問卷目標160件",
        "隱私問卷目標160件",
        "風險問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with compliance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with policy questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with privacy questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合規問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，政策問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，隱私問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_ethics_compliance_questionnaire_targets():
    for target in (
        "anti-bribery questionnaires target 160",
        "anti-corruption questionnaires target 160",
        "sanctions questionnaires target 160",
        "AML questionnaires target 160",
        "KYC questionnaires target 160",
        "ethics questionnaires target 160",
        "code of conduct questionnaires target 160",
        "反賄賂問卷目標160件",
        "反貪腐問卷目標160件",
        "制裁問卷目標160件",
        "AML問卷目標160件",
        "KYC問卷目標160件",
        "倫理問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with anti-bribery questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with anti-corruption questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sanctions questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with AML questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with KYC questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ethics questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with code of conduct questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，反賄賂問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，反貪腐問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，制裁問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，AML問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，KYC問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，倫理問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_regulatory_medical_questionnaire_targets():
    for target in (
        "regulatory questionnaires target 160",
        "regulatory affairs questionnaires target 160",
        "FDA questionnaires target 160",
        "IRB questionnaires target 160",
        "medical questionnaires target 160",
        "healthcare questionnaires target 160",
        "pharmacovigilance questionnaires target 160",
        "clinical trial questionnaires target 160",
        "醫療問卷目標160件",
        "醫材問卷目標160件",
        "藥事問卷目標160件",
        "法規問卷目標160件",
        "監管問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with regulatory questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with regulatory affairs questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FDA questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with IRB questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with medical questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with healthcare questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with pharmacovigilance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clinical trial questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，醫療問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，醫材問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，藥事問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法規問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，監管問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_security_compliance_questionnaire_targets():
    for target in (
        "SOC 2 questionnaires target 160",
        "ISO 27001 questionnaires target 160",
        "PCI questionnaires target 160",
        "HIPAA questionnaires target 160",
        "NIST questionnaires target 160",
        "DORA questionnaires target 160",
        "GDPR questionnaires target 160",
        "CCPA questionnaires target 160",
        "SOC2問卷目標160件",
        "ISO27001問卷目標160件",
        "PCI問卷目標160件",
        "HIPAA問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with SOC 2 questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ISO 27001 questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with PCI questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with HIPAA questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NIST questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DORA questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GDPR questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CCPA questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，SOC2問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，ISO27001問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，PCI問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，HIPAA問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_supply_chain_labor_questionnaire_targets():
    for target in (
        "supplier labor questionnaires target 160",
        "supply chain labor questionnaires target 160",
        "forced labor questionnaires target 160",
        "modern slavery questionnaires target 160",
        "worker voice questionnaires target 160",
        "labor rights questionnaires target 160",
        "social compliance questionnaires target 160",
        "responsible labor questionnaires target 160",
        "勞工問卷目標160件",
        "強迫勞動問卷目標160件",
        "現代奴役問卷目標160件",
        "社會責任問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with supplier labor questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supply chain labor questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with forced labor questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with modern slavery questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with worker voice questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with labor rights questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with social compliance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with responsible labor questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，勞工問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，強迫勞動問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，現代奴役問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，社會責任問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_business_continuity_resilience_questionnaire_targets():
    for target in (
        "business continuity questionnaires target 160",
        "disaster recovery questionnaires target 160",
        "incident response questionnaires target 160",
        "crisis management questionnaires target 160",
        "operational resilience questionnaires target 160",
        "BCP questionnaires target 160",
        "DRP questionnaires target 160",
        "resilience questionnaires target 160",
        "營運持續問卷目標160件",
        "營運韌性問卷目標160件",
        "災難復原問卷目標160件",
        "事件應變問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with business continuity questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with disaster recovery questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with incident response questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with crisis management questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with operational resilience questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with BCP questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DRP questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with resilience questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，營運持續問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，營運韌性問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，災難復原問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，事件應變問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_real_estate_facilities_questionnaire_targets():
    for target in (
        "real estate questionnaires target 160",
        "property questionnaires target 160",
        "tenant questionnaires target 160",
        "lease questionnaires target 160",
        "maintenance questionnaires target 160",
        "facilities questionnaires target 160",
        "workplace questionnaires target 160",
        "occupancy questionnaires target 160",
        "不動產問卷目標160件",
        "物業問卷目標160件",
        "租戶問卷目標160件",
        "租約問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with real estate questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with property questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tenant questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with lease questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with maintenance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with facilities questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with workplace questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with occupancy questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，不動產問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，物業問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，租戶問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，租約問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_manufacturing_quality_questionnaire_targets():
    for target in (
        "manufacturing questionnaires target 160",
        "quality assurance questionnaires target 160",
        "defect questionnaires target 160",
        "yield questionnaires target 160",
        "scrap questionnaires target 160",
        "rework questionnaires target 160",
        "supplier quality questionnaires target 160",
        "CAPA questionnaires target 160",
        "製造問卷目標160件",
        "品保問卷目標160件",
        "缺陷問卷目標160件",
        "良率問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with manufacturing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quality assurance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with defect questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with yield questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with scrap questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rework questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier quality questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CAPA questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，製造問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，品保問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，缺陷問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，良率問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_public_sector_questionnaire_targets():
    for target in (
        "permit questionnaires target 160",
        "license questionnaires target 160",
        "inspection questionnaires target 160",
        "case filing questionnaires target 160",
        "public records questionnaires target 160",
        "benefit questionnaires target 160",
        "hearing questionnaires target 160",
        "appeal questionnaires target 160",
        "許可問卷目標160件",
        "執照問卷目標160件",
        "檢查問卷目標160件",
        "聽證問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with permit questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with license questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with inspection questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case filing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with public records questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benefit questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with hearing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with appeal questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，許可問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，執照問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，檢查問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，聽證問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_treasury_questionnaire_targets():
    for target in (
        "treasury questionnaires target 160",
        "accounting questionnaires target 160",
        "billing questionnaires target 160",
        "collections questionnaires target 160",
        "invoice questionnaires target 160",
        "payroll questionnaires target 160",
        "tax questionnaires target 160",
        "finance control questionnaires target 160",
        "財會問卷目標160件",
        "出納問卷目標160件",
        "帳務問卷目標160件",
        "收款問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with treasury questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with accounting questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with collections questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with invoice questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payroll questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tax questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with finance control questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，財會問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出納問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳務問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，收款問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_risk_questionnaire_targets():
    for target in (
        "underwriting questionnaires target 160",
        "actuarial questionnaires target 160",
        "claims questionnaires target 160",
        "policyholder questionnaires target 160",
        "broker questionnaires target 160",
        "reinsurance questionnaires target 160",
        "保核問卷目標160件",
        "精算問卷目標160件",
        "理賠問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with underwriting questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with actuarial questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with claims questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with policyholder questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with broker questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reinsurance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保核問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，精算問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，理賠問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_security_assurance_questionnaire_targets():
    for target in (
        "security assurance questionnaires target 160",
        "vendor assurance questionnaires target 160",
        "customer assurance questionnaires target 160",
        "資安保證問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with security assurance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor assurance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer assurance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安保證問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_experience_questionnaire_targets():
    for target in (
        "customer experience questionnaires target 160",
        "support experience questionnaires target 160",
        "service experience questionnaires target 160",
        "客戶體驗問卷目標160件",
        "支援體驗問卷目標160件",
        "服務體驗問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer experience questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with support experience questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with service experience questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶體驗問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支援體驗問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，服務體驗問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_financial_crime_questionnaire_targets():
    for target in (
        "anti-money laundering questionnaires target 160",
        "financial crime questionnaires target 160",
        "fraud questionnaires target 160",
        "fraud prevention questionnaires target 160",
        "fraud investigation questionnaires target 160",
        "suspicious activity questionnaires target 160",
        "transaction monitoring questionnaires target 160",
        "sanctions screening questionnaires target 160",
        "screening questionnaires target 160",
        "反洗錢問卷目標160件",
        "金融犯罪問卷目標160件",
        "詐欺問卷目標160件",
        "詐欺防制問卷目標160件",
        "可疑活動問卷目標160件",
        "交易監控問卷目標160件",
        "制裁篩檢問卷目標160件",
        "篩檢問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with anti-money laundering questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with financial crime questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud prevention questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud investigation questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with suspicious activity questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transaction monitoring questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sanctions screening questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with screening questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，反洗錢問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，金融犯罪問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，詐欺問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，詐欺防制問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，可疑活動問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，交易監控問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，制裁篩檢問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，篩檢問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_export_trade_compliance_questionnaire_targets():
    for target in (
        "export control questionnaires target 160",
        "trade compliance questionnaires target 160",
        "dual-use questionnaires target 160",
        "dual use questionnaires target 160",
        "end-use questionnaires target 160",
        "end use questionnaires target 160",
        "出口管制問卷目標160件",
        "貿易合規問卷目標160件",
        "兩用問卷目標160件",
        "最終用途問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with export control questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trade compliance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dual-use questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dual use questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end-use questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end use questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出口管制問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，貿易合規問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，兩用問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，最終用途問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_trade_screening_admin_targets():
    for target in (
        "denied party screenings target 160",
        "restricted party screenings target 160",
        "sanctions screenings target 160",
        "watchlist screenings target 160",
        "entity screenings target 160",
        "customer screenings target 160",
        "supplier screenings target 160",
        "beneficial owner screenings target 160",
        "拒絕往來方篩檢目標160件",
        "受限制方篩檢目標160件",
        "制裁篩檢目標160件",
        "名單篩檢目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with denied party screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with restricted party screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sanctions screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with watchlist screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with entity screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier screenings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with beneficial owner screenings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，拒絕往來方篩檢目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，受限制方篩檢目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，制裁篩檢目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，名單篩檢目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customs_trade_docs_targets():
    for target in (
        "customs declarations target 160",
        "customs entries target 160",
        "import declarations target 160",
        "export declarations target 160",
        "trade documents target 160",
        "commercial invoices target 160",
        "packing lists target 160",
        "certificates of origin target 160",
        "海關申報目標160件",
        "進口申報目標160件",
        "出口申報目標160件",
        "原產地證明目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customs declarations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customs entries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with import declarations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with export declarations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trade documents target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with commercial invoices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with packing lists target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with certificates of origin target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，海關申報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，進口申報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出口申報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，原產地證明目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_vendor_contract_commercial_targets():
    for target in (
        "vendor contracts target 160",
        "supplier contracts target 160",
        "commercial contracts target 160",
        "customer contracts target 160",
        "sales contracts target 160",
        "MSAs target 160",
        "SOWs target 160",
        "NDAs target 160",
        "order forms target 160",
        "agreement executions target 160",
        "供應商合約目標160件",
        "商業合約目標160件",
        "客戶合約目標160件",
        "銷售合約目標160件",
        "保密協議目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vendor contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with commercial contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sales contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with MSAs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SOWs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with NDAs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with order forms target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with agreement executions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商合約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，商業合約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶合約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售合約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保密協議目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_data_retention_deletion_targets():
    for target in (
        "retention exceptions target 160",
        "retention schedules target 160",
        "legal holds target 160",
        "hold releases target 160",
        "deletion jobs target 160",
        "purge jobs target 160",
        "archive jobs target 160",
        "records disposals target 160",
        "保存例外目標160件",
        "保存排程目標160件",
        "法律保留目標160件",
        "刪除作業目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with retention exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with retention schedules target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal holds target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with hold releases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deletion jobs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with purge jobs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with archive jobs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with records disposals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保存例外目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保存排程目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法律保留目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，刪除作業目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_security_exception_remediation_targets():
    for target in (
        "security exception remediations target 160",
        "risk exception remediations target 160",
        "control exception remediations target 160",
        "exception remediation plans target 160",
        "waiver remediations target 160",
        "compensating controls target 160",
        "accepted risk reviews target 160",
        "exception expirations target 160",
        "例外整改目標160件",
        "資安例外整改目標160件",
        "風險例外整改目標160件",
        "控制例外整改目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with security exception remediations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk exception remediations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control exception remediations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with exception remediation plans target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with waiver remediations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with compensating controls target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with accepted risk reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with exception expirations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，例外整改目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安例外整改目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險例外整改目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，控制例外整改目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_bid_auction_targets():
    for target in (
        "bid events target 160",
        "supplier bids target 160",
        "vendor bids target 160",
        "sourcing waves target 160",
        "auction events target 160",
        "e-sourcing events target 160",
        "reverse auctions target 160",
        "tender events target 160",
        "採購競標目標160件",
        "供應商競標目標160件",
        "反向拍賣目標160件",
        "招標活動目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with bid events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier bids target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor bids target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sourcing waves target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with auction events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with e-sourcing events target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reverse auctions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tender events target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，採購競標目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商競標目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，反向拍賣目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，招標活動目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_export_license_classification_targets():
    for target in (
        "export licenses target 160",
        "export license requests target 160",
        "license classifications target 160",
        "export control classifications target 160",
        "ECCN classifications target 160",
        "HS classifications target 160",
        "HTS classifications target 160",
        "tariff classifications target 160",
        "commodity classifications target 160",
        "dual-use reviews target 160",
        "dual use reviews target 160",
        "end-user statements target 160",
        "end user statements target 160",
        "end-use statements target 160",
        "end use statements target 160",
        "出口許可目標160件",
        "出口執照目標160件",
        "出口管制分類目標160件",
        "兩用分類目標160件",
        "最終使用者聲明目標160件",
        "最終用途聲明目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with export licenses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with export license requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with license classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with export control classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ECCN classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with HS classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with HTS classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tariff classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with commodity classifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dual-use reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with dual use reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end-user statements target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end user statements target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end-use statements target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with end use statements target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出口許可目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出口執照目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，出口管制分類目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，兩用分類目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，最終使用者聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，最終用途聲明目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_rights_request_targets():
    for target in (
        "privacy rights requests target 160",
        "data subject requests target 160",
        "DSARs target 160",
        "access requests target 160",
        "deletion requests target 160",
        "erasure requests target 160",
        "rectification requests target 160",
        "portability requests target 160",
        "opt-out requests target 160",
        "do-not-sell requests target 160",
        "consent withdrawals target 160",
        "隱私權請求目標160件",
        "當事人請求目標160件",
        "資料存取請求目標160件",
        "資料刪除請求目標160件",
        "拒絕出售請求目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with privacy rights requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data subject requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DSARs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with access requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with deletion requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with erasure requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with rectification requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with portability requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with opt-out requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with do-not-sell requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with consent withdrawals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，隱私權請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，當事人請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料存取請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料刪除請求目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，拒絕出售請求目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_data_processing_transfer_targets():
    for target in (
        "data processing agreements target 160",
        "data processing addenda target 160",
        "DPAs target 160",
        "subprocessor reviews target 160",
        "subprocessor notices target 160",
        "cross-border transfer reviews target 160",
        "transfer impact assessments target 160",
        "TIAs target 160",
        "standard contractual clauses target 160",
        "SCCs target 160",
        "binding corporate rules target 160",
        "BCRs target 160",
        "資料處理協議目標160件",
        "資料處理附約目標160件",
        "子處理者審查目標160件",
        "跨境傳輸審查目標160件",
        "傳輸影響評估目標160件",
        "標準契約條款目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with data processing agreements target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data processing addenda target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with DPAs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with subprocessor reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with subprocessor notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cross-border transfer reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with transfer impact assessments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TIAs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with standard contractual clauses target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SCCs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with binding corporate rules target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with BCRs target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料處理協議目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料處理附約目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，子處理者審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，跨境傳輸審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，傳輸影響評估目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，標準契約條款目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_breach_notification_targets():
    for target in (
        "breach notifications target 160",
        "breach notification letters target 160",
        "data breach notices target 160",
        "privacy incident notifications target 160",
        "regulatory breach notices target 160",
        "supervisory authority notifications target 160",
        "affected individuals notices target 160",
        "customer breach notices target 160",
        "incident notification drafts target 160",
        "breach notification reports target 160",
        "72-hour notices target 160",
        "notification clock reviews target 160",
        "外洩通知目標160件",
        "資料外洩通知目標160件",
        "監管通報目標160件",
        "受影響個人通知目標160件",
        "事件通報草稿目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with breach notifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with breach notification letters target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with data breach notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with privacy incident notifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with regulatory breach notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supervisory authority notifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with affected individuals notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer breach notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with incident notification drafts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with breach notification reports target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with 72-hour notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with notification clock reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，外洩通知目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資料外洩通知目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，監管通報目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，受影響個人通知目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，事件通報草稿目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_privacy_cookie_consent_targets():
    for target in (
        "cookie consent banners target 160",
        "cookie consent records target 160",
        "cookie preference updates target 160",
        "CMP configurations target 160",
        "consent receipts target 160",
        "tracking consent prompts target 160",
        "cookie opt-outs target 160",
        "cookie category reviews target 160",
        "同意管理平台設定目標160件",
        "Cookie同意橫幅目標160件",
        "Cookie偏好更新目標160件",
        "追蹤同意提示目標160件",
        "同意收據目標160件",
        "Cookie退出目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with cookie consent banners target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cookie consent records target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cookie preference updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with CMP configurations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with consent receipts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tracking consent prompts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cookie opt-outs target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with cookie category reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，同意管理平台設定目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，Cookie同意橫幅目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，Cookie偏好更新目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，追蹤同意提示目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，同意收據目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，Cookie退出目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_procurement_contract_vendor_targets():
    for target in (
        "vendor onboarding packets target 160",
        "supplier intake forms target 160",
        "contract intake reviews target 160",
        "vendor renewal notices target 160",
        "third-party attestations target 160",
        "供應商導入包目標160件",
        "合約進件審查目標160件",
        "第三方聲明目標160件",
        "供應商續約通知目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with vendor onboarding packets target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier intake forms target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with contract intake reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor renewal notices target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third-party attestations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商導入包目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約進件審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，第三方聲明目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商續約通知目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_vendor_admin_targets():
    for target in (
        "invoice exception reviews target 160",
        "supplier remittance updates target 160",
        "payment term changes target 160",
        "vendor master updates target 160",
        "tax form collections target 160",
        "發票例外審查目標160件",
        "供應商主檔更新目標160件",
        "付款條件變更目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with invoice exception reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with supplier remittance updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with payment term changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor master updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tax form collections target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，發票例外審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商主檔更新目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，付款條件變更目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_customer_market_research_questionnaire_targets():
    for target in (
        "customer questionnaires target 160",
        "market research questionnaires target 160",
        "user research questionnaires target 160",
        "survey questionnaires target 160",
        "客戶問卷目標160件",
        "市場研究問卷目標160件",
        "使用者研究問卷目標160件",
        "調查問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with customer questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with market research questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with user research questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with survey questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，市場研究問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，使用者研究問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，調查問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_product_market_feedback_questionnaire_targets():
    for target in (
        "product questionnaires target 160",
        "employee questionnaires target 160",
        "partner questionnaires target 160",
        "support questionnaires target 160",
        "產品問卷目標160件",
        "員工問卷目標160件",
        "夥伴問卷目標160件",
        "支援問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with product questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with employee questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with partner questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with support questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，產品問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，員工問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，夥伴問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，支援問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_sales_marketing_hr_training_questionnaire_targets():
    for target in (
        "sales questionnaires target 160",
        "marketing questionnaires target 160",
        "customer success questionnaires target 160",
        "field questionnaires target 160",
        "training questionnaires target 160",
        "onboarding questionnaires target 160",
        "benefits questionnaires target 160",
        "engagement questionnaires target 160",
        "銷售問卷目標160件",
        "行銷問卷目標160件",
        "客戶成功問卷目標160件",
        "現場問卷目標160件",
        "訓練問卷目標160件",
        "到職問卷目標160件",
        "福利問卷目標160件",
        "敬業度問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with sales questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with marketing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with customer success questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with field questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with training questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with onboarding questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benefits questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with engagement questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，銷售問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，行銷問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，客戶成功問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，現場問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訓練問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，到職問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，福利問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，敬業度問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_operations_clinical_education_questionnaire_targets():
    for target in (
        "finance questionnaires target 160",
        "operations questionnaires target 160",
        "procurement questionnaires target 160",
        "IT questionnaires target 160",
        "clinical questionnaires target 160",
        "patient questionnaires target 160",
        "student questionnaires target 160",
        "course questionnaires target 160",
        "財務問卷目標160件",
        "營運問卷目標160件",
        "採購問卷目標160件",
        "IT問卷目標160件",
        "臨床問卷目標160件",
        "病患問卷目標160件",
        "學生問卷目標160件",
        "課程問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with finance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with operations questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with procurement questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with IT questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with clinical questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with patient questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with student questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with course questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，財務問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，營運問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，採購問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，IT問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，臨床問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，病患問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，學生問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，課程問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_logistics_facility_legal_governance_questionnaire_targets():
    for target in (
        "logistics questionnaires target 160",
        "facility questionnaires target 160",
        "warehouse questionnaires target 160",
        "safety questionnaires target 160",
        "legal questionnaires target 160",
        "governance questionnaires target 160",
        "audit questionnaires target 160",
        "board questionnaires target 160",
        "物流問卷目標160件",
        "設施問卷目標160件",
        "倉儲問卷目標160件",
        "安全問卷目標160件",
        "法務問卷目標160件",
        "治理問卷目標160件",
        "稽核問卷目標160件",
        "董事會問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with logistics questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with facility questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with warehouse questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with safety questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with legal questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with governance questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with audit questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，物流問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，設施問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，倉儲問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，安全問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，法務問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，治理問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稽核問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_environment_security_questionnaire_targets():
    for target in (
        "environment questionnaires target 160",
        "sustainability questionnaires target 160",
        "quality questionnaires target 160",
        "security questionnaires target 160",
        "環境問卷目標160件",
        "永續問卷目標160件",
        "品質問卷目標160件",
        "資安問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with environment questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with sustainability questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with quality questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with security questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，環境問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，永續問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，品質問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_esg_reporting_questionnaire_targets():
    for target in (
        "ESG questionnaires target 160",
        "investor questionnaires target 160",
        "analyst questionnaires target 160",
        "disclosure questionnaires target 160",
        "ESG問卷目標160件",
        "投資人問卷目標160件",
        "分析師問卷目標160件",
        "揭露問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with ESG questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with investor questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with analyst questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with disclosure questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，ESG問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，投資人問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，分析師問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，揭露問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_third_party_risk_questionnaire_targets():
    for target in (
        "third-party questionnaires target 160",
        "third party questionnaires target 160",
        "vendor risk questionnaires target 160",
        "TPRM questionnaires target 160",
        "risk assessment questionnaires target 160",
        "due diligence questionnaires target 160",
        "第三方問卷目標160件",
        "供應商風險問卷目標160件",
        "盡職調查問卷目標160件",
        "風險評估問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with third-party questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third party questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with vendor risk questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with TPRM questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with risk assessment questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with due diligence questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，第三方問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應商風險問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，盡職調查問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，風險評估問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_tax_control_questionnaire_targets():
    for target in (
        "tax questionnaires target 160",
        "SOX questionnaires target 160",
        "internal control questionnaires target 160",
        "control questionnaires target 160",
        "稅務問卷目標160件",
        "SOX問卷目標160件",
        "內控問卷目標160件",
        "控制問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with tax questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SOX questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with internal control questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with control questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，稅務問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，SOX問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，內控問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，控制問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_shareholder_governance_questionnaire_targets():
    for target in (
        "shareholder questionnaires target 160",
        "proxy questionnaires target 160",
        "committee questionnaires target 160",
        "board committee questionnaires target 160",
        "股東問卷目標160件",
        "委託投票問卷目標160件",
        "委員會問卷目標160件",
        "董事會委員會問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with shareholder questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with proxy questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with committee questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with board committee questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，股東問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，委託投票問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，委員會問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，董事會委員會問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_supplier_esg_questionnaire_targets():
    for target in (
        "responsible sourcing questionnaires target 160",
        "human rights questionnaires target 160",
        "conflict minerals questionnaires target 160",
        "人權問卷目標160件",
        "衝突礦產問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with responsible sourcing questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with human rights questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with conflict minerals questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，人權問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，衝突礦產問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_climate_environment_questionnaire_targets():
    for target in (
        "carbon questionnaires target 160",
        "climate questionnaires target 160",
        "emissions questionnaires target 160",
        "GHG questionnaires target 160",
        "energy questionnaires target 160",
        "water questionnaires target 160",
        "waste questionnaires target 160",
        "biodiversity questionnaires target 160",
        "碳排問卷目標160件",
        "氣候問卷目標160件",
        "排放問卷目標160件",
        "溫室氣體問卷目標160件",
        "能源問卷目標160件",
        "水資源問卷目標160件",
        "廢棄物問卷目標160件",
        "生物多樣性問卷目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with carbon questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with climate questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with emissions questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with GHG questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with energy questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with water questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with waste questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with biodiversity questionnaires target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，碳排問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，氣候問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，排放問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，溫室氣體問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，能源問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，水資源問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，廢棄物問卷目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，生物多樣性問卷目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_professional_services_delivery_targets():
    for target in (
        "professional services hours target 160",
        "billable hours target 160",
        "implementation hours target 160",
        "services projects completed target 160",
        "project go-lives target 160",
        "go-live milestones target 160",
        "專業服務時數目標160小時",
        "導入時數目標160小時",
        "上線里程碑目標160項",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with professional services hours target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with project go-lives target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with go-live milestones target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，專業服務時數目標160小時") == [160.0]


def test_extract_target_price_numbers_ignores_legal_regulatory_case_ops_targets():
    for target in (
        "contract reviews target 160",
        "legal reviews target 160",
        "compliance reviews target 160",
        "regulatory filings completed target 160",
        "third-party reviews target 160",
        "合約審查目標160件",
        "法務審查目標160件",
        "法遵審查目標160件",
        "監管申報完成目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with contract reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with regulatory filings completed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with third-party reviews target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，合約審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_education_admin_ops_targets():
    for target in (
        "student applications target 160",
        "applications processed target 160",
        "admissions decisions target 160",
        "financial aid cases target 160",
        "course registrations target 160",
        "學籍申請目標160件",
        "入學決定目標160件",
        "助學金案件目標160件",
        "選課登記目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with student applications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with admissions decisions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with course registrations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，學籍申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_healthcare_admin_ops_targets():
    for target in (
        "patient visits target 160",
        "appointments scheduled target 160",
        "claims adjudicated target 160",
        "authorizations processed target 160",
        "referrals processed target 160",
        "prior authorizations target 160",
        "病患就診目標160件",
        "預約排程目標160件",
        "轉診處理目標160件",
        "事前審核目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with patient visits target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with claims adjudicated target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with prior authorizations target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，病患就診目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_healthcare_clinical_admin_ops_targets():
    for target in (
        "clinical chart reviews target 160",
        "care gap closures target 160",
        "care plan updates target 160",
        "clinical documentation queries target 160",
        "patient outreach calls target 160",
        "case conferences target 160",
        "病歷審查目標160件",
        "照護缺口目標160件",
        "照護計畫更新目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with clinical chart reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with care plan updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with patient outreach calls target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，病歷審查目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，照護缺口目標160件") == [160.0]
    assert _extract_target_price_numbers("目標價160元，照護計畫更新目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_hr_recruiting_admin_ops_targets():
    for target in (
        "candidates screened target 160",
        "interviews scheduled target 160",
        "offers extended target 160",
        "background checks target 160",
        "new hires onboarded target 160",
        "job requisitions closed target 160",
        "requisitions filled target 160",
        "招聘篩選目標160人",
        "面試排程目標160件",
        "錄用通知目標160件",
        "背景查核目標160件",
        "新人到職目標160人",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with candidates screened target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with job requisitions closed target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with new hires onboarded target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，招聘篩選目標160人") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_health_admin_ops_targets():
    for target in (
        "medical claims target 160",
        "claims adjudication target 160",
        "provider credentialing target 160",
        "member enrollments target 160",
        "care management cases target 160",
        "utilization reviews target 160",
        "case reviews completed target 160",
        "醫療理賠目標160件",
        "理賠審核目標160件",
        "會員登錄目標160件",
        "照護管理案件目標160件",
        "使用審查目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with medical claims target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with provider credentialing target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with care management cases target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，醫療理賠目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_payer_provider_network_ops_targets():
    for target in (
        "provider contracts target 160",
        "network adequacy reviews target 160",
        "provider directories updated target 160",
        "claims appeals target 160",
        "grievance cases target 160",
        "appeals cases target 160",
        "provider disputes target 160",
        "provider onboarding target 160",
        "provider terminations target 160",
        "醫療網路審查目標160件",
        "供應者合約目標160件",
        "申訴案件目標160件",
        "給付申訴目標160件",
        "供應者導入目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with provider contracts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with network adequacy reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with claims appeals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，供應者合約目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_billing_subscription_admin_ops_targets():
    for target in (
        "subscription renewals target 160",
        "subscriptions renewed target 160",
        "subscriptions canceled target 160",
        "renewal quotes target 160",
        "billing adjustments target 160",
        "billing tickets target 160",
        "payment disputes target 160",
        "refund requests target 160",
        "invoice disputes target 160",
        "dunning cases target 160",
        "訂閱續約目標160件",
        "帳單調整目標160件",
        "付款爭議目標160件",
        "退款申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with subscription renewals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with billing adjustments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with refund requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂閱續約目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_finance_treasury_ops_targets():
    for target in (
        "cash forecasts target 160",
        "liquidity forecasts target 160",
        "cash positions target 160",
        "bank reconciliations target 160",
        "wire transfers target 160",
        "treasury payments target 160",
        "FX hedges target 160",
        "hedge settlements target 160",
        "現金預測目標160件",
        "資金部位目標160件",
        "銀行調節目標160件",
        "匯款處理目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with cash forecasts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with wire transfers target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with FX hedges target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，現金預測目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_benefit_eligibility_ops_targets():
    for target in (
        "eligibility checks target 160",
        "benefit eligibility reviews target 160",
        "eligibility determinations target 160",
        "benefit enrollments target 160",
        "benefit appeals target 160",
        "claims eligibility reviews target 160",
        "member eligibility checks target 160",
        "資格審查目標160件",
        "福利資格審查目標160件",
        "資格判定目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with eligibility checks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with benefit eligibility reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with member eligibility checks target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資格審查目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_loan_credit_servicing_ops_targets():
    for target in (
        "loan applications target 160",
        "mortgage applications target 160",
        "loan approvals target 160",
        "credit approvals target 160",
        "loan modifications target 160",
        "forbearance requests target 160",
        "delinquency cases target 160",
        "charge-off cases target 160",
        "foreclosure referrals target 160",
        "貸款申請目標160件",
        "房貸申請目標160件",
        "貸款核准目標160件",
        "逾期案件目標160件",
        "催收帳戶目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with loan applications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with credit approvals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with loan modifications target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，貸款申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_policy_servicing_ops_targets():
    for target in (
        "policy changes target 160",
        "policy endorsements target 160",
        "policy cancellations target 160",
        "premium payments target 160",
        "premium refunds target 160",
        "coverage changes target 160",
        "certificate requests target 160",
        "policy documents issued target 160",
        "保單變更目標160件",
        "保單批改目標160件",
        "保單取消目標160件",
        "保費付款目標160件",
        "保障變更目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with policy changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with premium payments target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with coverage changes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，保單變更目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_bank_account_ops_targets():
    for target in (
        "account closures target 160",
        "account maintenance requests target 160",
        "customer verifications target 160",
        "identity verifications target 160",
        "KYC reviews target 160",
        "beneficiary updates target 160",
        "stop payment requests target 160",
        "帳戶開立目標160件",
        "帳戶關閉目標160件",
        "身分驗證目標160件",
        "受益人更新目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with account closures target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with KYC reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with beneficiary updates target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，帳戶開立目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_returns_reverse_logistics_ops_targets():
    for target in (
        "restocking tasks target 160",
        "restocking cases target 160",
        "reverse logistics cases target 160",
        "refunds processed target 160",
        "退貨申請目標160件",
        "退貨檢查目標160件",
        "換貨申請目標160件",
        "退貨標籤目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with restocking tasks target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with reverse logistics cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with refunds processed target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，換貨申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_logistics_exception_ops_targets():
    for target in (
        "delivery exceptions target 160",
        "shipping exceptions target 160",
        "address changes target 160",
        "delivery reschedules target 160",
        "lost packages target 160",
        "damaged packages target 160",
        "pickup requests target 160",
        "proof of delivery requests target 160",
        "配送異常目標160件",
        "改址申請目標160件",
        "遺失包裹目標160件",
        "破損包裹目標160件",
        "取件申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with delivery exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with address changes target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with proof of delivery requests target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，配送異常目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_travel_hospitality_service_ops_targets():
    for target in (
        "booking modifications target 160",
        "reservation changes target 160",
        "guest requests target 160",
        "housekeeping requests target 160",
        "room upgrades target 160",
        "baggage claims target 160",
        "ticket changes target 160",
        "boarding assistance requests target 160",
        "訂房修改目標160件",
        "旅客請求目標160件",
        "客房升等目標160件",
        "行李索賠目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with booking modifications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with room upgrades target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ticket changes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，訂房修改目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_telecom_subscriber_ops_targets():
    for target in (
        "service activations target 160",
        "SIM activations target 160",
        "eSIM activations target 160",
        "number porting requests target 160",
        "plan changes target 160",
        "device upgrades target 160",
        "line suspensions target 160",
        "service transfers target 160",
        "門號攜碼目標160件",
        "方案變更目標160件",
        "SIM開通目標160件",
        "停復話申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with service activations target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with number porting requests target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with plan changes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，門號攜碼目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_ecommerce_catalog_ops_targets():
    for target in (
        "catalog updates target 160",
        "product listings target 160",
        "listing approvals target 160",
        "seller tickets target 160",
        "marketplace disputes target 160",
        "pricing updates target 160",
        "promotion requests target 160",
        "content moderation appeals target 160",
        "商品上架目標160件",
        "目錄更新目標160件",
        "賣家工單目標160件",
        "促銷申請目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with catalog updates target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with product listings target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with marketplace disputes target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，商品上架目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_advertising_campaign_ops_targets():
    for target in (
        "campaign launches target 160",
        "creative reviews target 160",
        "ad approvals target 160",
        "budget changes target 160",
        "audience updates target 160",
        "optimization tasks target 160",
        "placement requests target 160",
        "brand safety reviews target 160",
        "活動上線目標160件",
        "素材審核目標160件",
        "廣告核准目標160件",
        "預算變更目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with campaign launches target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with creative reviews target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with ad approvals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，活動上線目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_public_sector_permit_ops_targets():
    for target in (
        "permit applications target 160",
        "license renewals target 160",
        "inspection requests target 160",
        "case filings target 160",
        "public records requests target 160",
        "benefit applications target 160",
        "hearing requests target 160",
        "appeals processed target 160",
        "許可申請目標160件",
        "執照續期目標160件",
        "檢查申請目標160件",
        "申訴處理目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with permit applications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with license renewals target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with case filings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，許可申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_property_leasing_ops_targets():
    for target in (
        "lease applications target 160",
        "tenant inquiries target 160",
        "move-in inspections target 160",
        "maintenance tickets target 160",
        "rent collection cases target 160",
        "lease renewals target 160",
        "property showings target 160",
        "tenant screenings target 160",
        "租約申請目標160件",
        "租戶詢問目標160件",
        "入住檢查目標160件",
        "維修工單目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with lease applications target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with tenant inquiries target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with property showings target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，租約申請目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_payments_fintech_ops_targets():
    for target in (
        "payment disputes target 160",
        "chargeback cases target 160",
        "merchant onboarding target 160",
        "merchant verifications target 160",
        "merchant applications target 160",
        "KYC reviews target 160",
        "fraud alerts target 160",
        "fraud reviews target 160",
        "payment failures target 160",
        "failed payments target 160",
        "settlement exceptions target 160",
        "settlement inquiries target 160",
        "wallet verifications target 160",
        "wallet top-ups target 160",
        "card disputes target 160",
        "authorization declines target 160",
        "payout exceptions target 160",
        "refund requests target 160",
        "invoice disputes target 160",
        "付款爭議目標160件",
        "拒付案件目標160件",
        "商戶導入目標160件",
        "商戶審核目標160件",
        "詐欺警示目標160件",
        "付款失敗目標160件",
        "結算例外目標160件",
        "錢包驗證目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with chargeback cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with merchant onboarding target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud alerts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with settlement exceptions target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，拒付案件目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_insurance_claims_recovery_ops_targets():
    for target in (
        "subrogation cases target 160",
        "subrogation recoveries target 160",
        "recovery cases target 160",
        "recovery demands target 160",
        "salvage cases target 160",
        "salvage inspections target 160",
        "fraud referrals target 160",
        "SIU referrals target 160",
        "claims investigations target 160",
        "coverage investigations target 160",
        "claim reopenings target 160",
        "settlement reviews target 160",
        "代位求償目標160件",
        "追償案件目標160件",
        "追償請求目標160件",
        "殘值案件目標160件",
        "理賠調查目標160件",
        "詐欺轉介目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with subrogation cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with recovery cases target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with fraud referrals target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，代位求償目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_security_operations_alert_targets():
    for target in (
        "DLP alerts target 160",
        "DLP incidents target 160",
        "SIEM alerts target 160",
        "EDR alerts target 160",
        "SOC tickets target 160",
        "security tickets target 160",
        "malware incidents target 160",
        "ransomware incidents target 160",
        "endpoint alerts target 160",
        "資料外洩防護警示目標160件",
        "資安工單目標160件",
        "惡意程式事件目標160件",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with DLP alerts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with SIEM alerts target 160") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with malware incidents target 160") == [160.0]
    assert _extract_target_price_numbers("目標價160元，資安工單目標160件") == [160.0]


def test_extract_target_price_numbers_ignores_post_trade_instruction_confirmation_targets():
    for target in (
        "settlement instructions target 160M",
        "settlement instructions processed target 160M",
        "instructions processed target 160M",
        "trade confirmations target 160M",
        "trade confirmations processed target 160M",
        "trade affirmations target 160M",
        "affirmations processed target 160M",
        "matching instructions target 160M",
        "settlement matching instructions target 160M",
        "交割指示目標160萬",
        "交易確認目標160萬",
        "交易確認處理目標160萬",
        "交易配對指示目標160萬",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("target price NT$160 with settlement instructions target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trade confirmations processed target 160M") == [160.0]
    assert _extract_target_price_numbers("target price NT$160 with trade affirmations target 160M") == [160.0]
    assert _extract_target_price_numbers("目標價160元，交割指示目標160萬") == [160.0]


def test_extract_target_price_numbers_prefers_long_term_target_when_multiple_horizons_are_present():
    assert _extract_target_price_numbers("12個月目標價160元，6個月目標價140元") == [160.0]
    assert _extract_target_price_numbers("6個月目標價140元，12個月目標價160元") == [160.0]
    assert _extract_target_price_numbers("12M target price NT$160; 6M target price NT$140") == [160.0]
    assert _extract_target_price_numbers("long-term target price NT$160; short-term target price NT$140") == [160.0]


def test_extract_target_price_numbers_rejects_non_positive_targets():
    for target in ("目標價-160", "目標價－160", "NT$-160", "-160", "目標價0", "NT$0"):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價100 - 160") == [100.0, 160.0]


def test_extract_target_price_numbers_ignores_adjustment_deltas_and_uses_revised_targets():
    for target in (
        "目標價上修20元",
        "目標價下調10元",
        "上調目標價20元",
        "下修目標價10元",
        "target price raised by NT$20",
        "target price cut by 10",
        "目標價上修幅度20元",
        "目標價下調幅度10元",
        "目標價調整幅度20元",
        "price target revised upward by NT$20",
        "price target adjusted downward by NT$10",
        "raise price target by NT$20",
        "cut price target by 10",
        "revised price target upward by NT$20",
        "adjusted price target downward by NT$10",
    ):
        assert _extract_target_price_numbers(target) == []

    assert _extract_target_price_numbers("目標價上修至160元") == [160.0]
    assert _extract_target_price_numbers("調升目標價至160元") == [160.0]
    assert _extract_target_price_numbers("下調目標價到90元") == [90.0]
    assert _extract_target_price_numbers("目標價由120元上調至160元") == [160.0]
    assert _extract_target_price_numbers("目標價由120元上調至160-180元") == [160.0, 180.0]
    assert _extract_target_price_numbers("目標價由120元調整至160元") == [160.0]
    assert _extract_target_price_numbers("目標價由120元修正至160元") == [160.0]
    assert _extract_target_price_numbers("目標價由120元調整為160元") == [160.0]
    assert _extract_target_price_numbers("target price raised from NT$120 to NT$160") == [160.0]
    assert _extract_target_price_numbers("target price cut from 200 to 160") == [160.0]
    assert _extract_target_price_numbers("price target revised from NT$120 to NT$160") == [160.0]
    assert _extract_target_price_numbers("price target adjusted from NT$120 to NT$160") == [160.0]
    assert _extract_target_price_numbers("price target revised upward to NT$160") == [160.0]
    assert _extract_target_price_numbers("price target adjusted downward to NT$90") == [90.0]
    assert _extract_target_price_numbers("raise price target to NT$160") == [160.0]
    assert _extract_target_price_numbers("cut price target from 200 to 160") == [160.0]


def test_extract_target_price_numbers_ignores_policy_audit_security_training_queue_targets():
    targets = (
        "policy reviews target 160",
        "policy exception queue items target 160",
        "compliance waiver request queue items target 160",
        "audit finding queue items target 160",
        "audit remediation queue items target 160",
        "control testing queue items target 160",
        "control evidence request queue items target 160",
        "SOX control queue reviews target 160",
        "risk assessment queue items target 160",
        "vendor risk assessment queue items target 160",
        "security questionnaire queue items target 160",
        "business continuity test queue items target 160",
        "incident response tabletop queue items target 160",
        "training completion queue items target 160",
        "certification tracking queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_healthcare_claims_provider_queue_targets():
    targets = (
        "claim denial queue items target 160",
        "claims appeal queue items target 160",
        "prior authorization queue items target 160",
        "prior auth queue items target 160",
        "eligibility verification queue items target 160",
        "enrollment application queue items target 160",
        "provider credentialing queue items target 160",
        "provider directory update queue items target 160",
        "referral authorization queue items target 160",
        "medical record request queue items target 160",
        "lab order queue items target 160",
        "appointment scheduling queue items target 160",
        "case management queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_banking_loan_payment_dispute_queue_targets():
    targets = (
        "loan application queue items target 160",
        "mortgage application queue items target 160",
        "credit card application queue items target 160",
        "account opening queue items target 160",
        "AML investigation queue items target 160",
        "fraud alert queue items target 160",
        "chargeback dispute queue items target 160",
        "transaction dispute queue items target 160",
        "wire exception queue items target 160",
        "payment investigation queue items target 160",
        "collections case queue items target 160",
        "loan modification queue items target 160",
        "payment investigations target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_retail_ops_order_exception_queue_targets():
    targets = (
        "return authorization queue items target 160",
        "refund authorization queue items target 160",
        "warranty claim queue items target 160",
        "RMA queue items target 160",
        "order cancellation queue items target 160",
        "subscription cancellation queue items target 160",
        "address change queue items target 160",
        "shipping exception queue items target 160",
        "delivery exception queue items target 160",
        "inventory adjustment queue items target 160",
        "stock transfer queue items target 160",
        "product catalog update queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_fulfillment_warehouse_queue_targets():
    targets = (
        "returns processing queue items target 160",
        "exchange request queue items target 160",
        "backorder queue items target 160",
        "shipment hold queue items target 160",
        "fulfillment exception queue items target 160",
        "picking queue items target 160",
        "packing queue items target 160",
        "warehouse transfer queue items target 160",
        "inventory cycle count queue items target 160",
        "stock count queue items target 160",
        "purchase order exception queue items target 160",
        "supplier return queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_carrier_logistics_execution_queue_targets():
    targets = (
        "carrier claim queue items target 160",
        "damage claim queue items target 160",
        "lost shipment claim queue items target 160",
        "delivery appointment queue items target 160",
        "route exception queue items target 160",
        "dispatch queue items target 160",
        "dock appointment queue items target 160",
        "receiving queue items target 160",
        "putaway queue items target 160",
        "replenishment queue items target 160",
        "allocation queue items target 160",
        "wave planning queue items target 160",
        "ASN exception queue items target 160",
        "EDI exception queue items target 160",
        "freight invoice exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_freight_customs_trade_logistics_queue_targets():
    targets = (
        "customs entry queue items target 160",
        "import clearance queue items target 160",
        "export documentation queue items target 160",
        "bill of lading queue items target 160",
        "container booking queue items target 160",
        "container release queue items target 160",
        "demurrage dispute queue items target 160",
        "detention dispute queue items target 160",
        "freight audit queue items target 160",
        "freight claim queue items target 160",
        "rate quote queue items target 160",
        "load tender queue items target 160",
        "tender acceptance queue items target 160",
        "carrier onboarding queue items target 160",
        "lane assignment queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_trade_compliance_import_export_queue_targets():
    targets = (
        "HTS classification queue items target 160",
        "HS code review queue items target 160",
        "country of origin review queue items target 160",
        "certificate of origin queue items target 160",
        "import license queue items target 160",
        "export license queue items target 160",
        "sanctions screening queue items target 160",
        "restricted party screening queue items target 160",
        "denied party screening queue items target 160",
        "AES filing queue items target 160",
        "ISF filing queue items target 160",
        "broker instruction queue items target 160",
        "duty drawback queue items target 160",
        "tariff engineering queue items target 160",
        "free trade agreement qualification queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_export_control_customs_post_entry_queue_targets():
    targets = (
        "export control classification queue items target 160",
        "ECCN classification queue items target 160",
        "license exception review queue items target 160",
        "customs valuation review queue items target 160",
        "entry summary queue items target 160",
        "post entry amendment queue items target 160",
        "prior disclosure queue items target 160",
        "classification ruling queue items target 160",
        "anti dumping review queue items target 160",
        "countervailing duty review queue items target 160",
        "quota allocation queue items target 160",
        "bonded warehouse entry queue items target 160",
        "duty payment queue items target 160",
        "drawback claim queue items target 160",
        "reconciliation filing queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_trade_document_customs_broker_handoff_queue_targets():
    targets = (
        "importer of record update queue items target 160",
        "ultimate consignee review queue items target 160",
        "end user statement queue items target 160",
        "end use certificate queue items target 160",
        "shipper letter of instruction queue items target 160",
        "commercial invoice review queue items target 160",
        "packing list review queue items target 160",
        "certificate compliance review queue items target 160",
        "export declaration queue items target 160",
        "import declaration queue items target 160",
        "customs broker handoff queue items target 160",
        "power of attorney queue items target 160",
        "bond sufficiency review queue items target 160",
        "surety bond renewal queue items target 160",
        "foreign trade zone admission queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_trade_finance_shipping_instruction_queue_targets():
    targets = (
        "letter of credit documentation queue items target 160",
        "import letter of credit queue items target 160",
        "export letter of credit queue items target 160",
        "bank guarantee queue items target 160",
        "documentary collection queue items target 160",
        "cargo insurance certificate review queue items target 160",
        "insurance certificate review queue items target 160",
        "inspection certificate review queue items target 160",
        "phytosanitary certificate review queue items target 160",
        "fumigation certificate review queue items target 160",
        "incoterms review queue items target 160",
        "trade finance document review queue items target 160",
        "dangerous goods declaration queue items target 160",
        "hazmat declaration queue items target 160",
        "shipping instruction queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_shipping_release_waybill_document_queue_targets():
    targets = (
        "letter of indemnity queue items target 160",
        "telex release queue items target 160",
        "sea waybill queue items target 160",
        "air waybill queue items target 160",
        "arrival notice queue items target 160",
        "delivery order queue items target 160",
        "booking confirmation queue items target 160",
        "vessel schedule update queue items target 160",
        "container tracking queue items target 160",
        "cargo release queue items target 160",
        "terminal appointment queue items target 160",
        "port congestion case queue items target 160",
        "customs exam hold queue items target 160",
        "FDA hold release queue items target 160",
        "documentation discrepancy queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_manifest_forwarder_drayage_document_queue_targets():
    targets = (
        "manifest correction queue items target 160",
        "manifest filing queue items target 160",
        "AMS filing queue items target 160",
        "ACI filing queue items target 160",
        "ENS filing queue items target 160",
        "ISF amendment queue items target 160",
        "bill of lading correction queue items target 160",
        "switch bill of lading queue items target 160",
        "house bill review queue items target 160",
        "master bill review queue items target 160",
        "freight forwarder handoff queue items target 160",
        "drayage appointment queue items target 160",
        "chassis booking queue items target 160",
        "empty container return queue items target 160",
        "container seal discrepancy queue items target 160",
        "weight certificate queue items target 160",
        "SOLAS VGM filing queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_forwarder_yard_intermodal_queue_targets():
    targets = (
        "freight forwarder invoice queue items target 160",
        "forwarder booking request queue items target 160",
        "drayage invoice exception queue items target 160",
        "chassis split billing queue items target 160",
        "container yard appointment queue items target 160",
        "container yard release queue items target 160",
        "rail ramp appointment queue items target 160",
        "intermodal transfer request queue items target 160",
        "gate appointment queue items target 160",
        "gate pass request queue items target 160",
        "container dwell exception queue items target 160",
        "per diem dispute queue items target 160",
        "storage charge dispute queue items target 160",
        "accessorial charge review queue items target 160",
        "freight accrual review queue items target 160",
        "carrier statement reconciliation queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_container_pickup_gate_invoice_queue_targets():
    targets = (
        "container pickup appointment queue items target 160",
        "container pickup order queue items target 160",
        "container dropoff appointment queue items target 160",
        "empty pickup order queue items target 160",
        "empty release order queue items target 160",
        "loaded container release queue items target 160",
        "terminal release order queue items target 160",
        "yard pull request queue items target 160",
        "prepull request queue items target 160",
        "gate in exception queue items target 160",
        "gate out exception queue items target 160",
        "port free time dispute queue items target 160",
        "demurrage invoice dispute queue items target 160",
        "detention invoice dispute queue items target 160",
        "per diem invoice dispute queue items target 160",
        "storage invoice dispute queue items target 160",
        "chassis per diem dispute queue items target 160",
        "chassis invoice dispute queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_container_notice_release_rail_storage_queue_targets():
    targets = (
        "container availability notice queue items target 160",
        "last free day notice queue items target 160",
        "LFD notice queue items target 160",
        "pickup number request queue items target 160",
        "delivery order release queue items target 160",
        "freight release order queue items target 160",
        "customs hold release order queue items target 160",
        "steamship line release queue items target 160",
        "SSL release queue items target 160",
        "terminal appointment reschedule queue items target 160",
        "container discharge notice queue items target 160",
        "rail billing request queue items target 160",
        "rail demurrage dispute queue items target 160",
        "rail storage dispute queue items target 160",
        "intermodal invoice dispute queue items target 160",
        "port storage dispute queue items target 160",
        "pier pass dispute queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_carrier_booking_cutoff_update_queue_targets():
    targets = (
        "ocean carrier booking queue items target 160",
        "ocean carrier release queue items target 160",
        "carrier booking amendment queue items target 160",
        "carrier arrival notice queue items target 160",
        "booking amendment request queue items target 160",
        "booking roll request queue items target 160",
        "vessel roll exception queue items target 160",
        "transshipment notice queue items target 160",
        "ETA update notice queue items target 160",
        "ETD update notice queue items target 160",
        "container rollover notice queue items target 160",
        "cutoff extension request queue items target 160",
        "CY cutoff update queue items target 160",
        "document cutoff update queue items target 160",
        "VGM cutoff update queue items target 160",
        "rail cutoff update queue items target 160",
        "terminal cutoff update queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_carrier_equipment_interchange_container_service_queue_targets():
    targets = (
        "carrier booking confirmation queue items target 160",
        "carrier booking cancellation queue items target 160",
        "carrier equipment release queue items target 160",
        "equipment interchange receipt queue items target 160",
        "EIR exception queue items target 160",
        "container interchange exception queue items target 160",
        "container damage notice queue items target 160",
        "container damage claim queue items target 160",
        "reefer temperature exception queue items target 160",
        "reefer plug exception queue items target 160",
        "seal verification request queue items target 160",
        "container inspection request queue items target 160",
        "container washout request queue items target 160",
        "container fumigation request queue items target 160",
        "container repair estimate queue items target 160",
        "M&R estimate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_equipment_release_chassis_reefer_service_queue_targets():
    targets = (
        "carrier equipment interchange queue items target 160",
        "equipment release order queue items target 160",
        "empty equipment release queue items target 160",
        "equipment return authorization queue items target 160",
        "container return authorization queue items target 160",
        "container pickup authorization queue items target 160",
        "container availability request queue items target 160",
        "chassis damage claim queue items target 160",
        "chassis repair estimate queue items target 160",
        "chassis inspection request queue items target 160",
        "chassis interchange receipt queue items target 160",
        "genset request queue items target 160",
        "reefer pretrip inspection queue items target 160",
        "PTI exception queue items target 160",
        "temperature download request queue items target 160",
        "container seal replacement queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_equipment_exception_reefer_temperature_seal_cleaning_queue_targets():
    targets = (
        "equipment release exception queue items target 160",
        "equipment hold release queue items target 160",
        "chassis release order queue items target 160",
        "chassis return authorization queue items target 160",
        "chassis availability request queue items target 160",
        "genset release request queue items target 160",
        "genset repair estimate queue items target 160",
        "reefer malfunction notice queue items target 160",
        "reefer alarm exception queue items target 160",
        "reefer monitoring exception queue items target 160",
        "temperature setpoint change queue items target 160",
        "temperature variance exception queue items target 160",
        "container seal discrepancy resolution queue items target 160",
        "seal replacement authorization queue items target 160",
        "container cleaning request queue items target 160",
        "container sanitation certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_sanitation_contamination_cleaning_service_queue_targets():
    targets = (
        "sanitation inspection request queue items target 160",
        "container sanitation exception queue items target 160",
        "container pest inspection queue items target 160",
        "container odor complaint queue items target 160",
        "container contamination notice queue items target 160",
        "food grade container request queue items target 160",
        "flexitank inspection request queue items target 160",
        "tanker cleaning certificate queue items target 160",
        "hazardous residue certificate queue items target 160",
        "residue cleaning request queue items target 160",
        "odor remediation request queue items target 160",
        "container sweep request queue items target 160",
        "dunnage removal request queue items target 160",
        "moisture damage notice queue items target 160",
        "container quarantine hold queue items target 160",
        "sanitation certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_mold_food_safety_fumigation_quarantine_service_queue_targets():
    targets = (
        "container mold inspection queue items target 160",
        "container mold remediation queue items target 160",
        "container allergen cleaning request queue items target 160",
        "food safety inspection request queue items target 160",
        "food safety hold queue items target 160",
        "USDA inspection request queue items target 160",
        "APHIS inspection request queue items target 160",
        "phytosanitary reinspection queue items target 160",
        "fumigation hold queue items target 160",
        "fumigation exception queue items target 160",
        "fumigation release request queue items target 160",
        "tanker wash certificate exception queue items target 160",
        "cleaning certificate discrepancy queue items target 160",
        "odor inspection request queue items target 160",
        "pest remediation request queue items target 160",
        "quarantine release request queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_hygiene_certificate_audit_service_queue_targets():
    targets = (
        "container hygiene inspection queue items target 160",
        "container hygiene certificate queue items target 160",
        "container sanitation audit queue items target 160",
        "food grade certificate request queue items target 160",
        "food grade certificate exception queue items target 160",
        "tanker hygiene inspection queue items target 160",
        "tanker washout request queue items target 160",
        "flexitank cleaning certificate queue items target 160",
        "residue inspection request queue items target 160",
        "hazardous residue inspection request queue items target 160",
        "container odor remediation certificate queue items target 160",
        "pest inspection certificate queue items target 160",
        "quarantine inspection request queue items target 160",
        "quarantine certificate exception queue items target 160",
        "fumigation inspection request queue items target 160",
        "fumigation certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_audit_certificate_discrepancy_service_queue_targets():
    targets = (
        "container hygiene audit exception queue items target 160",
        "container cleaning audit queue items target 160",
        "food safety audit queue items target 160",
        "food safety certificate exception queue items target 160",
        "food grade reinspection request queue items target 160",
        "tanker sanitation audit queue items target 160",
        "tanker cleaning audit queue items target 160",
        "flexitank sanitation certificate queue items target 160",
        "residue certificate request queue items target 160",
        "hazardous residue audit queue items target 160",
        "odor certificate exception queue items target 160",
        "pest certificate exception queue items target 160",
        "quarantine audit queue items target 160",
        "quarantine hold certificate queue items target 160",
        "fumigation audit queue items target 160",
        "fumigation certificate discrepancy queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_remediation_certificate_exception_service_queue_targets():
    targets = (
        "container hygiene remediation queue items target 160",
        "container cleaning certificate exception queue items target 160",
        "container sanitation certificate discrepancy queue items target 160",
        "food safety remediation request queue items target 160",
        "food safety reinspection request queue items target 160",
        "food grade sanitation audit queue items target 160",
        "tanker certificate discrepancy queue items target 160",
        "tanker washout certificate queue items target 160",
        "flexitank audit queue items target 160",
        "flexitank certificate exception queue items target 160",
        "residue remediation request queue items target 160",
        "hazardous residue certificate exception queue items target 160",
        "odor audit exception queue items target 160",
        "pest audit exception queue items target 160",
        "quarantine certificate discrepancy queue items target 160",
        "fumigation remediation request queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_corrective_action_remediation_certificate_service_queue_targets():
    targets = (
        "container hygiene corrective action queue items target 160",
        "container cleaning remediation request queue items target 160",
        "container sanitation remediation certificate queue items target 160",
        "food safety corrective action queue items target 160",
        "food safety hold release certificate queue items target 160",
        "tanker cleaning remediation request queue items target 160",
        "flexitank reinspection request queue items target 160",
        "flexitank remediation certificate queue items target 160",
        "residue audit exception queue items target 160",
        "hazardous residue certificate discrepancy queue items target 160",
        "odor remediation certificate exception queue items target 160",
        "pest remediation certificate queue items target 160",
        "quarantine remediation request queue items target 160",
        "fumigation reinspection request queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_hold_release_corrective_action_service_queue_targets():
    targets = (
        "container hygiene hold release queue items target 160",
        "container cleaning corrective action queue items target 160",
        "container sanitation corrective action queue items target 160",
        "food safety certificate discrepancy queue items target 160",
        "food grade corrective action queue items target 160",
        "tanker reinspection request queue items target 160",
        "tanker remediation certificate queue items target 160",
        "flexitank corrective action queue items target 160",
        "flexitank hold release certificate queue items target 160",
        "residue certificate discrepancy queue items target 160",
        "hazardous residue remediation certificate queue items target 160",
        "odor corrective action queue items target 160",
        "pest corrective action queue items target 160",
        "quarantine hold release request queue items target 160",
        "fumigation corrective action queue items target 160",
        "fumigation hold release certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_exception_closure_corrective_action_service_queue_targets():
    targets = (
        "container hygiene exception closure queue items target 160",
        "container cleaning exception closure queue items target 160",
        "container sanitation exception closure queue items target 160",
        "food safety exception closure queue items target 160",
        "food grade certificate closure queue items target 160",
        "tanker hold release queue items target 160",
        "tanker corrective action queue items target 160",
        "flexitank exception closure queue items target 160",
        "residue corrective action queue items target 160",
        "hazardous residue corrective action queue items target 160",
        "odor exception closure queue items target 160",
        "pest exception closure queue items target 160",
        "quarantine corrective action queue items target 160",
        "quarantine certificate closure queue items target 160",
        "fumigation exception closure queue items target 160",
        "fumigation certificate closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_closure_certificate_exception_service_queue_targets():
    targets = (
        "container hygiene closure certificate queue items target 160",
        "container cleaning closure certificate queue items target 160",
        "container sanitation closure certificate queue items target 160",
        "food safety closure certificate queue items target 160",
        "food grade exception closure queue items target 160",
        "tanker exception closure queue items target 160",
        "tanker certificate closure queue items target 160",
        "flexitank certificate closure queue items target 160",
        "residue exception closure queue items target 160",
        "hazardous residue exception closure queue items target 160",
        "odor certificate closure queue items target 160",
        "pest certificate closure queue items target 160",
        "quarantine exception closure queue items target 160",
        "quarantine closure certificate queue items target 160",
        "fumigation closure certificate queue items target 160",
        "fumigation corrective action certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_closure_exception_certificate_closure_service_queue_targets():
    targets = (
        "container hygiene closure exception queue items target 160",
        "container cleaning certificate exception closure queue items target 160",
        "container sanitation certificate closure exception queue items target 160",
        "food safety certificate closure exception queue items target 160",
        "food grade closure exception queue items target 160",
        "tanker closure exception queue items target 160",
        "tanker corrective action closure queue items target 160",
        "flexitank closure exception queue items target 160",
        "residue certificate closure queue items target 160",
        "hazardous residue certificate closure queue items target 160",
        "odor closure certificate queue items target 160",
        "pest closure certificate queue items target 160",
        "quarantine certificate exception closure queue items target 160",
        "quarantine corrective action closure queue items target 160",
        "fumigation certificate exception closure queue items target 160",
        "fumigation closure exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_certificate_closure_closure_exception_service_queue_targets():
    targets = (
        "container hygiene certificate closure queue items target 160",
        "container cleaning closure exception queue items target 160",
        "container sanitation closure exception queue items target 160",
        "food safety closure exception queue items target 160",
        "food grade certificate exception closure queue items target 160",
        "tanker certificate exception closure queue items target 160",
        "tanker certificate closure exception queue items target 160",
        "flexitank certificate exception closure queue items target 160",
        "residue closure certificate queue items target 160",
        "hazardous residue closure certificate queue items target 160",
        "odor certificate closure exception queue items target 160",
        "pest certificate closure exception queue items target 160",
        "quarantine closure exception queue items target 160",
        "quarantine certificate closure exception queue items target 160",
        "fumigation corrective action closure certificate queue items target 160",
        "fumigation certificate closure exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_certificate_exception_certificate_closure_service_queue_targets():
    targets = (
        "container hygiene certificate exception queue items target 160",
        "container cleaning certificate closure queue items target 160",
        "food grade closure certificate queue items target 160",
        "tanker closure certificate queue items target 160",
        "tanker closure certificate exception queue items target 160",
        "flexitank certificate closure exception queue items target 160",
        "residue certificate exception closure queue items target 160",
        "hazardous residue certificate exception closure queue items target 160",
        "odor closure exception queue items target 160",
        "pest closure exception queue items target 160",
        "fumigation closure certificate exception queue items target 160",
        "fumigation exception closure certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_closure_certificate_exception_certificate_closure_service_queue_targets():
    targets = (
        "container hygiene closure certificate exception queue items target 160",
        "food safety certificate closure queue items target 160",
        "tanker exception certificate closure queue items target 160",
        "tanker certificate exception queue items target 160",
        "flexitank closure certificate queue items target 160",
        "residue closure exception queue items target 160",
        "hazardous residue closure exception queue items target 160",
        "odor exception certificate closure queue items target 160",
        "pest exception certificate closure queue items target 160",
        "quarantine exception certificate closure queue items target 160",
        "quarantine closure certificate exception queue items target 160",
        "fumigation corrective action certificate closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_container_hygiene_corrective_action_exception_certificate_service_queue_targets():
    targets = (
        "container hygiene certificate corrective action queue items target 160",
        "container hygiene closure corrective action queue items target 160",
        "container hygiene exception certificate queue items target 160",
        "container hygiene exception corrective action queue items target 160",
        "container hygiene corrective action certificate queue items target 160",
        "container hygiene corrective action closure queue items target 160",
        "container hygiene corrective action exception queue items target 160",
        "container hygiene certificate closure exception queue items target 160",
        "container hygiene certificate closure corrective action queue items target 160",
        "container hygiene certificate exception closure queue items target 160",
        "container hygiene certificate exception corrective action queue items target 160",
        "container hygiene certificate corrective action closure queue items target 160",
        "container hygiene certificate corrective action exception queue items target 160",
        "container hygiene closure certificate corrective action queue items target 160",
        "container hygiene closure exception certificate queue items target 160",
        "container hygiene closure exception corrective action queue items target 160",
        "container hygiene closure corrective action certificate queue items target 160",
        "container hygiene closure corrective action exception queue items target 160",
        "container hygiene exception certificate closure queue items target 160",
        "container hygiene exception certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_container_hygiene_exception_closure_corrective_action_permutation_service_queue_targets():
    targets = (
        "container hygiene exception closure certificate queue items target 160",
        "container hygiene exception closure corrective action queue items target 160",
        "container hygiene exception corrective action certificate queue items target 160",
        "container hygiene exception corrective action closure queue items target 160",
        "container hygiene corrective action certificate closure queue items target 160",
        "container hygiene corrective action certificate exception queue items target 160",
        "container hygiene corrective action closure certificate queue items target 160",
        "container hygiene corrective action closure exception queue items target 160",
        "container hygiene corrective action exception certificate queue items target 160",
        "container hygiene corrective action exception closure queue items target 160",
        "container hygiene certificate closure exception corrective action queue items target 160",
        "container hygiene certificate closure corrective action exception queue items target 160",
        "container hygiene certificate exception closure corrective action queue items target 160",
        "container hygiene certificate exception corrective action closure queue items target 160",
        "container hygiene certificate corrective action closure exception queue items target 160",
        "container hygiene certificate corrective action exception closure queue items target 160",
        "container hygiene closure certificate exception corrective action queue items target 160",
        "container hygiene closure certificate corrective action exception queue items target 160",
        "container hygiene closure exception certificate corrective action queue items target 160",
        "container hygiene closure exception corrective action certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_container_cleaning_corrective_action_exception_certificate_service_queue_targets():
    targets = (
        "container cleaning certificate corrective action queue items target 160",
        "container cleaning closure corrective action queue items target 160",
        "container cleaning exception certificate queue items target 160",
        "container cleaning exception corrective action queue items target 160",
        "container cleaning corrective action certificate queue items target 160",
        "container cleaning corrective action closure queue items target 160",
        "container cleaning corrective action exception queue items target 160",
        "container cleaning certificate closure exception queue items target 160",
        "container cleaning certificate closure corrective action queue items target 160",
        "container cleaning certificate exception corrective action queue items target 160",
        "container cleaning certificate corrective action closure queue items target 160",
        "container cleaning certificate corrective action exception queue items target 160",
        "container cleaning closure certificate exception queue items target 160",
        "container cleaning closure certificate corrective action queue items target 160",
        "container cleaning closure exception certificate queue items target 160",
        "container cleaning closure exception corrective action queue items target 160",
        "container cleaning closure corrective action certificate queue items target 160",
        "container cleaning closure corrective action exception queue items target 160",
        "container cleaning exception certificate closure queue items target 160",
        "container cleaning exception certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_container_sanitation_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "container sanitation certificate closure queue items target 160",
        "container sanitation certificate corrective action queue items target 160",
        "container sanitation closure corrective action queue items target 160",
        "container sanitation exception certificate queue items target 160",
        "container sanitation exception corrective action queue items target 160",
        "container sanitation corrective action certificate queue items target 160",
        "container sanitation corrective action closure queue items target 160",
        "container sanitation corrective action exception queue items target 160",
        "container sanitation certificate closure corrective action queue items target 160",
        "container sanitation certificate exception closure queue items target 160",
        "container sanitation certificate exception corrective action queue items target 160",
        "container sanitation certificate corrective action closure queue items target 160",
        "container sanitation certificate corrective action exception queue items target 160",
        "container sanitation closure certificate exception queue items target 160",
        "container sanitation closure certificate corrective action queue items target 160",
        "container sanitation closure exception certificate queue items target 160",
        "container sanitation closure exception corrective action queue items target 160",
        "container sanitation closure corrective action certificate queue items target 160",
        "container sanitation closure corrective action exception queue items target 160",
        "container sanitation exception certificate closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_food_safety_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "food safety certificate corrective action queue items target 160",
        "food safety closure corrective action queue items target 160",
        "food safety exception certificate queue items target 160",
        "food safety exception corrective action queue items target 160",
        "food safety corrective action certificate queue items target 160",
        "food safety corrective action closure queue items target 160",
        "food safety corrective action exception queue items target 160",
        "food safety certificate closure corrective action queue items target 160",
        "food safety certificate exception closure queue items target 160",
        "food safety certificate exception corrective action queue items target 160",
        "food safety certificate corrective action closure queue items target 160",
        "food safety certificate corrective action exception queue items target 160",
        "food safety closure certificate exception queue items target 160",
        "food safety closure certificate corrective action queue items target 160",
        "food safety closure exception certificate queue items target 160",
        "food safety closure exception corrective action queue items target 160",
        "food safety closure corrective action certificate queue items target 160",
        "food safety closure corrective action exception queue items target 160",
        "food safety exception certificate closure queue items target 160",
        "food safety exception certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_food_grade_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "food grade certificate corrective action queue items target 160",
        "food grade closure corrective action queue items target 160",
        "food grade exception certificate queue items target 160",
        "food grade exception corrective action queue items target 160",
        "food grade corrective action certificate queue items target 160",
        "food grade corrective action closure queue items target 160",
        "food grade corrective action exception queue items target 160",
        "food grade certificate closure exception queue items target 160",
        "food grade certificate closure corrective action queue items target 160",
        "food grade certificate exception corrective action queue items target 160",
        "food grade certificate corrective action closure queue items target 160",
        "food grade certificate corrective action exception queue items target 160",
        "food grade closure certificate exception queue items target 160",
        "food grade closure certificate corrective action queue items target 160",
        "food grade closure exception certificate queue items target 160",
        "food grade closure exception corrective action queue items target 160",
        "food grade closure corrective action certificate queue items target 160",
        "food grade closure corrective action exception queue items target 160",
        "food grade exception certificate closure queue items target 160",
        "food grade exception certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_tanker_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "tanker certificate corrective action queue items target 160",
        "tanker closure corrective action queue items target 160",
        "tanker exception certificate queue items target 160",
        "tanker exception corrective action queue items target 160",
        "tanker corrective action certificate queue items target 160",
        "tanker corrective action exception queue items target 160",
        "tanker certificate closure corrective action queue items target 160",
        "tanker certificate exception corrective action queue items target 160",
        "tanker certificate corrective action closure queue items target 160",
        "tanker certificate corrective action exception queue items target 160",
        "tanker closure certificate corrective action queue items target 160",
        "tanker closure exception certificate queue items target 160",
        "tanker closure exception corrective action queue items target 160",
        "tanker closure corrective action certificate queue items target 160",
        "tanker closure corrective action exception queue items target 160",
        "tanker exception certificate corrective action queue items target 160",
        "tanker exception closure certificate queue items target 160",
        "tanker exception closure corrective action queue items target 160",
        "tanker exception corrective action certificate queue items target 160",
        "tanker exception corrective action closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_residue_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "residue certificate exception queue items target 160",
        "residue certificate corrective action queue items target 160",
        "residue closure corrective action queue items target 160",
        "residue exception certificate queue items target 160",
        "residue exception corrective action queue items target 160",
        "residue corrective action certificate queue items target 160",
        "residue corrective action closure queue items target 160",
        "residue corrective action exception queue items target 160",
        "residue certificate closure exception queue items target 160",
        "residue certificate closure corrective action queue items target 160",
        "residue certificate exception corrective action queue items target 160",
        "residue certificate corrective action closure queue items target 160",
        "residue certificate corrective action exception queue items target 160",
        "residue closure certificate exception queue items target 160",
        "residue closure certificate corrective action queue items target 160",
        "residue closure exception certificate queue items target 160",
        "residue closure exception corrective action queue items target 160",
        "residue closure corrective action certificate queue items target 160",
        "residue closure corrective action exception queue items target 160",
        "residue exception certificate closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_pest_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "pest certificate corrective action queue items target 160",
        "pest closure corrective action queue items target 160",
        "pest exception certificate queue items target 160",
        "pest exception corrective action queue items target 160",
        "pest corrective action certificate queue items target 160",
        "pest corrective action closure queue items target 160",
        "pest corrective action exception queue items target 160",
        "pest certificate closure corrective action queue items target 160",
        "pest certificate exception closure queue items target 160",
        "pest certificate exception corrective action queue items target 160",
        "pest certificate corrective action closure queue items target 160",
        "pest certificate corrective action exception queue items target 160",
        "pest closure certificate exception queue items target 160",
        "pest closure certificate corrective action queue items target 160",
        "pest closure exception certificate queue items target 160",
        "pest closure exception corrective action queue items target 160",
        "pest closure corrective action certificate queue items target 160",
        "pest closure corrective action exception queue items target 160",
        "pest exception certificate corrective action queue items target 160",
        "pest exception closure certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_odor_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "odor certificate corrective action queue items target 160",
        "odor closure corrective action queue items target 160",
        "odor exception certificate queue items target 160",
        "odor exception corrective action queue items target 160",
        "odor corrective action certificate queue items target 160",
        "odor corrective action closure queue items target 160",
        "odor corrective action exception queue items target 160",
        "odor certificate closure corrective action queue items target 160",
        "odor certificate exception closure queue items target 160",
        "odor certificate exception corrective action queue items target 160",
        "odor certificate corrective action closure queue items target 160",
        "odor certificate corrective action exception queue items target 160",
        "odor closure certificate exception queue items target 160",
        "odor closure certificate corrective action queue items target 160",
        "odor closure exception certificate queue items target 160",
        "odor closure exception corrective action queue items target 160",
        "odor closure corrective action certificate queue items target 160",
        "odor closure corrective action exception queue items target 160",
        "odor exception certificate corrective action queue items target 160",
        "odor exception closure certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_flexitank_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "flexitank certificate corrective action queue items target 160",
        "flexitank closure corrective action queue items target 160",
        "flexitank exception certificate queue items target 160",
        "flexitank exception corrective action queue items target 160",
        "flexitank corrective action certificate queue items target 160",
        "flexitank corrective action closure queue items target 160",
        "flexitank corrective action exception queue items target 160",
        "flexitank certificate closure corrective action queue items target 160",
        "flexitank certificate exception corrective action queue items target 160",
        "flexitank certificate corrective action closure queue items target 160",
        "flexitank certificate corrective action exception queue items target 160",
        "flexitank closure certificate exception queue items target 160",
        "flexitank closure certificate corrective action queue items target 160",
        "flexitank closure exception certificate queue items target 160",
        "flexitank closure exception corrective action queue items target 160",
        "flexitank closure corrective action certificate queue items target 160",
        "flexitank closure corrective action exception queue items target 160",
        "flexitank exception certificate closure queue items target 160",
        "flexitank exception certificate corrective action queue items target 160",
        "flexitank exception closure certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_quarantine_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "quarantine certificate corrective action queue items target 160",
        "quarantine closure corrective action queue items target 160",
        "quarantine exception certificate queue items target 160",
        "quarantine exception corrective action queue items target 160",
        "quarantine corrective action certificate queue items target 160",
        "quarantine corrective action exception queue items target 160",
        "quarantine certificate closure corrective action queue items target 160",
        "quarantine certificate exception corrective action queue items target 160",
        "quarantine certificate corrective action closure queue items target 160",
        "quarantine certificate corrective action exception queue items target 160",
        "quarantine closure certificate corrective action queue items target 160",
        "quarantine closure exception certificate queue items target 160",
        "quarantine closure exception corrective action queue items target 160",
        "quarantine closure corrective action certificate queue items target 160",
        "quarantine closure corrective action exception queue items target 160",
        "quarantine exception certificate corrective action queue items target 160",
        "quarantine exception closure certificate queue items target 160",
        "quarantine exception closure corrective action queue items target 160",
        "quarantine exception corrective action certificate queue items target 160",
        "quarantine exception corrective action closure queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_fumigation_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "fumigation certificate corrective action queue items target 160",
        "fumigation closure corrective action queue items target 160",
        "fumigation exception corrective action queue items target 160",
        "fumigation corrective action closure queue items target 160",
        "fumigation corrective action exception queue items target 160",
        "fumigation certificate closure corrective action queue items target 160",
        "fumigation certificate exception corrective action queue items target 160",
        "fumigation certificate corrective action closure queue items target 160",
        "fumigation certificate corrective action exception queue items target 160",
        "fumigation closure certificate corrective action queue items target 160",
        "fumigation closure exception corrective action queue items target 160",
        "fumigation closure corrective action certificate queue items target 160",
        "fumigation closure corrective action exception queue items target 160",
        "fumigation exception certificate corrective action queue items target 160",
        "fumigation exception closure corrective action queue items target 160",
        "fumigation exception corrective action certificate queue items target 160",
        "fumigation exception corrective action closure queue items target 160",
        "fumigation corrective action certificate exception queue items target 160",
        "fumigation corrective action closure exception queue items target 160",
        "fumigation corrective action exception certificate queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_cleaning_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "cleaning certificate corrective action queue items target 160",
        "cleaning closure corrective action queue items target 160",
        "cleaning exception corrective action queue items target 160",
        "cleaning corrective action certificate queue items target 160",
        "cleaning corrective action closure queue items target 160",
        "cleaning corrective action exception queue items target 160",
        "cleaning certificate closure corrective action queue items target 160",
        "cleaning certificate exception corrective action queue items target 160",
        "cleaning certificate corrective action closure queue items target 160",
        "cleaning certificate corrective action exception queue items target 160",
        "cleaning closure certificate corrective action queue items target 160",
        "cleaning closure exception corrective action queue items target 160",
        "cleaning closure corrective action certificate queue items target 160",
        "cleaning closure corrective action exception queue items target 160",
        "cleaning exception certificate corrective action queue items target 160",
        "cleaning exception closure corrective action queue items target 160",
        "cleaning exception corrective action certificate queue items target 160",
        "cleaning exception corrective action closure queue items target 160",
        "cleaning corrective action certificate closure queue items target 160",
        "cleaning corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_contamination_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "contamination certificate corrective action queue items target 160",
        "contamination closure corrective action queue items target 160",
        "contamination exception corrective action queue items target 160",
        "contamination corrective action certificate queue items target 160",
        "contamination corrective action closure queue items target 160",
        "contamination corrective action exception queue items target 160",
        "contamination certificate closure corrective action queue items target 160",
        "contamination certificate exception corrective action queue items target 160",
        "contamination certificate corrective action closure queue items target 160",
        "contamination certificate corrective action exception queue items target 160",
        "contamination closure certificate corrective action queue items target 160",
        "contamination closure exception corrective action queue items target 160",
        "contamination closure corrective action certificate queue items target 160",
        "contamination closure corrective action exception queue items target 160",
        "contamination exception certificate corrective action queue items target 160",
        "contamination exception closure corrective action queue items target 160",
        "contamination exception corrective action certificate queue items target 160",
        "contamination exception corrective action closure queue items target 160",
        "contamination corrective action certificate closure queue items target 160",
        "contamination corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_hygiene_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "hygiene certificate corrective action queue items target 160",
        "hygiene closure corrective action queue items target 160",
        "hygiene exception corrective action queue items target 160",
        "hygiene corrective action certificate queue items target 160",
        "hygiene corrective action closure queue items target 160",
        "hygiene corrective action exception queue items target 160",
        "hygiene certificate closure corrective action queue items target 160",
        "hygiene certificate exception corrective action queue items target 160",
        "hygiene certificate corrective action closure queue items target 160",
        "hygiene certificate corrective action exception queue items target 160",
        "hygiene closure certificate corrective action queue items target 160",
        "hygiene closure exception corrective action queue items target 160",
        "hygiene closure corrective action certificate queue items target 160",
        "hygiene closure corrective action exception queue items target 160",
        "hygiene exception certificate corrective action queue items target 160",
        "hygiene exception closure corrective action queue items target 160",
        "hygiene exception corrective action certificate queue items target 160",
        "hygiene exception corrective action closure queue items target 160",
        "hygiene corrective action certificate closure queue items target 160",
        "hygiene corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_mold_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "mold certificate corrective action queue items target 160",
        "mold closure corrective action queue items target 160",
        "mold exception corrective action queue items target 160",
        "mold corrective action certificate queue items target 160",
        "mold corrective action closure queue items target 160",
        "mold corrective action exception queue items target 160",
        "mold certificate closure corrective action queue items target 160",
        "mold certificate exception corrective action queue items target 160",
        "mold certificate corrective action closure queue items target 160",
        "mold certificate corrective action exception queue items target 160",
        "mold closure certificate corrective action queue items target 160",
        "mold closure exception corrective action queue items target 160",
        "mold closure corrective action certificate queue items target 160",
        "mold closure corrective action exception queue items target 160",
        "mold exception certificate corrective action queue items target 160",
        "mold exception closure corrective action queue items target 160",
        "mold exception corrective action certificate queue items target 160",
        "mold exception corrective action closure queue items target 160",
        "mold corrective action certificate closure queue items target 160",
        "mold corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_sanitation_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "sanitation certificate corrective action queue items target 160",
        "sanitation closure corrective action queue items target 160",
        "sanitation exception corrective action queue items target 160",
        "sanitation corrective action certificate queue items target 160",
        "sanitation corrective action closure queue items target 160",
        "sanitation corrective action exception queue items target 160",
        "sanitation certificate closure corrective action queue items target 160",
        "sanitation certificate exception corrective action queue items target 160",
        "sanitation certificate corrective action closure queue items target 160",
        "sanitation certificate corrective action exception queue items target 160",
        "sanitation closure certificate corrective action queue items target 160",
        "sanitation closure exception corrective action queue items target 160",
        "sanitation closure corrective action certificate queue items target 160",
        "sanitation closure corrective action exception queue items target 160",
        "sanitation exception certificate corrective action queue items target 160",
        "sanitation exception closure corrective action queue items target 160",
        "sanitation exception corrective action certificate queue items target 160",
        "sanitation exception corrective action closure queue items target 160",
        "sanitation corrective action certificate closure queue items target 160",
        "sanitation corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_allergen_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "allergen certificate corrective action queue items target 160",
        "allergen closure corrective action queue items target 160",
        "allergen exception corrective action queue items target 160",
        "allergen corrective action certificate queue items target 160",
        "allergen corrective action closure queue items target 160",
        "allergen corrective action exception queue items target 160",
        "allergen certificate closure corrective action queue items target 160",
        "allergen certificate exception corrective action queue items target 160",
        "allergen certificate corrective action closure queue items target 160",
        "allergen certificate corrective action exception queue items target 160",
        "allergen closure certificate corrective action queue items target 160",
        "allergen closure exception corrective action queue items target 160",
        "allergen closure corrective action certificate queue items target 160",
        "allergen closure corrective action exception queue items target 160",
        "allergen exception certificate corrective action queue items target 160",
        "allergen exception closure corrective action queue items target 160",
        "allergen exception corrective action certificate queue items target 160",
        "allergen exception corrective action closure queue items target 160",
        "allergen corrective action certificate closure queue items target 160",
        "allergen corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_spoilage_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "spoilage certificate corrective action queue items target 160",
        "spoilage closure corrective action queue items target 160",
        "spoilage exception corrective action queue items target 160",
        "spoilage corrective action certificate queue items target 160",
        "spoilage corrective action closure queue items target 160",
        "spoilage corrective action exception queue items target 160",
        "spoilage certificate closure corrective action queue items target 160",
        "spoilage certificate exception corrective action queue items target 160",
        "spoilage certificate corrective action closure queue items target 160",
        "spoilage certificate corrective action exception queue items target 160",
        "spoilage closure certificate corrective action queue items target 160",
        "spoilage closure exception corrective action queue items target 160",
        "spoilage closure corrective action certificate queue items target 160",
        "spoilage closure corrective action exception queue items target 160",
        "spoilage exception certificate corrective action queue items target 160",
        "spoilage exception closure corrective action queue items target 160",
        "spoilage exception corrective action certificate queue items target 160",
        "spoilage exception corrective action closure queue items target 160",
        "spoilage corrective action certificate closure queue items target 160",
        "spoilage corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_biosecurity_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "biosecurity certificate corrective action queue items target 160",
        "biosecurity closure corrective action queue items target 160",
        "biosecurity exception corrective action queue items target 160",
        "biosecurity corrective action certificate queue items target 160",
        "biosecurity corrective action closure queue items target 160",
        "biosecurity corrective action exception queue items target 160",
        "biosecurity certificate closure corrective action queue items target 160",
        "biosecurity certificate exception corrective action queue items target 160",
        "biosecurity certificate corrective action closure queue items target 160",
        "biosecurity certificate corrective action exception queue items target 160",
        "biosecurity closure certificate corrective action queue items target 160",
        "biosecurity closure exception corrective action queue items target 160",
        "biosecurity closure corrective action certificate queue items target 160",
        "biosecurity closure corrective action exception queue items target 160",
        "biosecurity exception certificate corrective action queue items target 160",
        "biosecurity exception closure corrective action queue items target 160",
        "biosecurity exception corrective action certificate queue items target 160",
        "biosecurity exception corrective action closure queue items target 160",
        "biosecurity corrective action certificate closure queue items target 160",
        "biosecurity corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_microbial_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "microbial certificate corrective action queue items target 160",
        "microbial closure corrective action queue items target 160",
        "microbial exception corrective action queue items target 160",
        "microbial corrective action certificate queue items target 160",
        "microbial corrective action closure queue items target 160",
        "microbial corrective action exception queue items target 160",
        "microbial certificate closure corrective action queue items target 160",
        "microbial certificate exception corrective action queue items target 160",
        "microbial certificate corrective action closure queue items target 160",
        "microbial certificate corrective action exception queue items target 160",
        "microbial closure certificate corrective action queue items target 160",
        "microbial closure exception corrective action queue items target 160",
        "microbial closure corrective action certificate queue items target 160",
        "microbial closure corrective action exception queue items target 160",
        "microbial exception certificate corrective action queue items target 160",
        "microbial exception closure corrective action queue items target 160",
        "microbial exception corrective action certificate queue items target 160",
        "microbial exception corrective action closure queue items target 160",
        "microbial corrective action certificate closure queue items target 160",
        "microbial corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_sterility_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "sterility certificate corrective action queue items target 160",
        "sterility closure corrective action queue items target 160",
        "sterility exception corrective action queue items target 160",
        "sterility corrective action certificate queue items target 160",
        "sterility corrective action closure queue items target 160",
        "sterility corrective action exception queue items target 160",
        "sterility certificate closure corrective action queue items target 160",
        "sterility certificate exception corrective action queue items target 160",
        "sterility certificate corrective action closure queue items target 160",
        "sterility certificate corrective action exception queue items target 160",
        "sterility closure certificate corrective action queue items target 160",
        "sterility closure exception corrective action queue items target 160",
        "sterility closure corrective action certificate queue items target 160",
        "sterility closure corrective action exception queue items target 160",
        "sterility exception certificate corrective action queue items target 160",
        "sterility exception closure corrective action queue items target 160",
        "sterility exception corrective action certificate queue items target 160",
        "sterility exception corrective action closure queue items target 160",
        "sterility corrective action certificate closure queue items target 160",
        "sterility corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_sterilization_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "sterilization certificate corrective action queue items target 160",
        "sterilization closure corrective action queue items target 160",
        "sterilization exception corrective action queue items target 160",
        "sterilization corrective action certificate queue items target 160",
        "sterilization corrective action closure queue items target 160",
        "sterilization corrective action exception queue items target 160",
        "sterilization certificate closure corrective action queue items target 160",
        "sterilization certificate exception corrective action queue items target 160",
        "sterilization certificate corrective action closure queue items target 160",
        "sterilization certificate corrective action exception queue items target 160",
        "sterilization closure certificate corrective action queue items target 160",
        "sterilization closure exception corrective action queue items target 160",
        "sterilization closure corrective action certificate queue items target 160",
        "sterilization closure corrective action exception queue items target 160",
        "sterilization exception certificate corrective action queue items target 160",
        "sterilization exception closure corrective action queue items target 160",
        "sterilization exception corrective action certificate queue items target 160",
        "sterilization exception corrective action closure queue items target 160",
        "sterilization corrective action certificate closure queue items target 160",
        "sterilization corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_haccp_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "haccp certificate corrective action queue items target 160",
        "haccp closure corrective action queue items target 160",
        "haccp exception corrective action queue items target 160",
        "haccp corrective action certificate queue items target 160",
        "haccp corrective action closure queue items target 160",
        "haccp corrective action exception queue items target 160",
        "haccp certificate closure corrective action queue items target 160",
        "haccp certificate exception corrective action queue items target 160",
        "haccp certificate corrective action closure queue items target 160",
        "haccp certificate corrective action exception queue items target 160",
        "haccp closure certificate corrective action queue items target 160",
        "haccp closure exception corrective action queue items target 160",
        "haccp closure corrective action certificate queue items target 160",
        "haccp closure corrective action exception queue items target 160",
        "haccp exception certificate corrective action queue items target 160",
        "haccp exception closure corrective action queue items target 160",
        "haccp exception corrective action certificate queue items target 160",
        "haccp exception corrective action closure queue items target 160",
        "haccp corrective action certificate closure queue items target 160",
        "haccp corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_recall_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "recall certificate corrective action queue items target 160",
        "recall closure corrective action queue items target 160",
        "recall exception corrective action queue items target 160",
        "recall corrective action certificate queue items target 160",
        "recall corrective action closure queue items target 160",
        "recall corrective action exception queue items target 160",
        "recall certificate closure corrective action queue items target 160",
        "recall certificate exception corrective action queue items target 160",
        "recall certificate corrective action closure queue items target 160",
        "recall certificate corrective action exception queue items target 160",
        "recall closure certificate corrective action queue items target 160",
        "recall closure exception corrective action queue items target 160",
        "recall closure corrective action certificate queue items target 160",
        "recall closure corrective action exception queue items target 160",
        "recall exception certificate corrective action queue items target 160",
        "recall exception closure corrective action queue items target 160",
        "recall exception corrective action certificate queue items target 160",
        "recall exception corrective action closure queue items target 160",
        "recall corrective action certificate closure queue items target 160",
        "recall corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_traceability_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "traceability certificate corrective action queue items target 160",
        "traceability closure corrective action queue items target 160",
        "traceability exception corrective action queue items target 160",
        "traceability corrective action certificate queue items target 160",
        "traceability corrective action closure queue items target 160",
        "traceability corrective action exception queue items target 160",
        "traceability certificate closure corrective action queue items target 160",
        "traceability certificate exception corrective action queue items target 160",
        "traceability certificate corrective action closure queue items target 160",
        "traceability certificate corrective action exception queue items target 160",
        "traceability closure certificate corrective action queue items target 160",
        "traceability closure exception corrective action queue items target 160",
        "traceability closure corrective action certificate queue items target 160",
        "traceability closure corrective action exception queue items target 160",
        "traceability exception certificate corrective action queue items target 160",
        "traceability exception closure corrective action queue items target 160",
        "traceability exception corrective action certificate queue items target 160",
        "traceability exception corrective action closure queue items target 160",
        "traceability corrective action certificate closure queue items target 160",
        "traceability corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_inspection_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "inspection certificate corrective action queue items target 160",
        "inspection closure corrective action queue items target 160",
        "inspection exception corrective action queue items target 160",
        "inspection corrective action certificate queue items target 160",
        "inspection corrective action closure queue items target 160",
        "inspection corrective action exception queue items target 160",
        "inspection certificate closure corrective action queue items target 160",
        "inspection certificate exception corrective action queue items target 160",
        "inspection certificate corrective action closure queue items target 160",
        "inspection certificate corrective action exception queue items target 160",
        "inspection closure certificate corrective action queue items target 160",
        "inspection closure exception corrective action queue items target 160",
        "inspection closure corrective action certificate queue items target 160",
        "inspection closure corrective action exception queue items target 160",
        "inspection exception certificate corrective action queue items target 160",
        "inspection exception closure corrective action queue items target 160",
        "inspection exception corrective action certificate queue items target 160",
        "inspection exception corrective action closure queue items target 160",
        "inspection corrective action certificate closure queue items target 160",
        "inspection corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_quality_assurance_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "quality assurance certificate corrective action queue items target 160",
        "quality assurance closure corrective action queue items target 160",
        "quality assurance exception corrective action queue items target 160",
        "quality assurance corrective action certificate queue items target 160",
        "quality assurance corrective action closure queue items target 160",
        "quality assurance corrective action exception queue items target 160",
        "quality assurance certificate closure corrective action queue items target 160",
        "quality assurance certificate exception corrective action queue items target 160",
        "quality assurance certificate corrective action closure queue items target 160",
        "quality assurance certificate corrective action exception queue items target 160",
        "quality assurance closure certificate corrective action queue items target 160",
        "quality assurance closure exception corrective action queue items target 160",
        "quality assurance closure corrective action certificate queue items target 160",
        "quality assurance closure corrective action exception queue items target 160",
        "quality assurance exception certificate corrective action queue items target 160",
        "quality assurance exception closure corrective action queue items target 160",
        "quality assurance exception corrective action certificate queue items target 160",
        "quality assurance exception corrective action closure queue items target 160",
        "quality assurance corrective action certificate closure queue items target 160",
        "quality assurance corrective action certificate exception queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_quality_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "quality control certificate closure queue items target 160",
        "quality control certificate exception queue items target 160",
        "quality control certificate corrective action queue items target 160",
        "quality control closure certificate queue items target 160",
        "quality control closure exception queue items target 160",
        "quality control closure corrective action queue items target 160",
        "quality control exception certificate queue items target 160",
        "quality control exception closure queue items target 160",
        "quality control exception corrective action queue items target 160",
        "quality control corrective action certificate queue items target 160",
        "quality control corrective action closure queue items target 160",
        "quality control corrective action exception queue items target 160",
        "quality control certificate closure exception queue items target 160",
        "quality control certificate closure corrective action queue items target 160",
        "quality control certificate exception closure queue items target 160",
        "quality control certificate exception corrective action queue items target 160",
        "quality control certificate corrective action closure queue items target 160",
        "quality control certificate corrective action exception queue items target 160",
        "quality control closure certificate exception queue items target 160",
        "quality control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_cold_chain_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "cold chain certificate closure queue items target 160",
        "cold chain certificate exception queue items target 160",
        "cold chain certificate corrective action queue items target 160",
        "cold chain closure certificate queue items target 160",
        "cold chain closure exception queue items target 160",
        "cold chain closure corrective action queue items target 160",
        "cold chain exception certificate queue items target 160",
        "cold chain exception closure queue items target 160",
        "cold chain exception corrective action queue items target 160",
        "cold chain corrective action certificate queue items target 160",
        "cold chain corrective action closure queue items target 160",
        "cold chain corrective action exception queue items target 160",
        "cold chain certificate closure exception queue items target 160",
        "cold chain certificate closure corrective action queue items target 160",
        "cold chain certificate exception closure queue items target 160",
        "cold chain certificate exception corrective action queue items target 160",
        "cold chain certificate corrective action closure queue items target 160",
        "cold chain certificate corrective action exception queue items target 160",
        "cold chain closure certificate exception queue items target 160",
        "cold chain closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_pathogen_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "pathogen certificate closure queue items target 160",
        "pathogen certificate exception queue items target 160",
        "pathogen certificate corrective action queue items target 160",
        "pathogen closure certificate queue items target 160",
        "pathogen closure exception queue items target 160",
        "pathogen closure corrective action queue items target 160",
        "pathogen exception certificate queue items target 160",
        "pathogen exception closure queue items target 160",
        "pathogen exception corrective action queue items target 160",
        "pathogen corrective action certificate queue items target 160",
        "pathogen corrective action closure queue items target 160",
        "pathogen corrective action exception queue items target 160",
        "pathogen certificate closure exception queue items target 160",
        "pathogen certificate closure corrective action queue items target 160",
        "pathogen certificate exception closure queue items target 160",
        "pathogen certificate exception corrective action queue items target 160",
        "pathogen certificate corrective action closure queue items target 160",
        "pathogen certificate corrective action exception queue items target 160",
        "pathogen closure certificate exception queue items target 160",
        "pathogen closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_aseptic_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "aseptic certificate closure queue items target 160",
        "aseptic certificate exception queue items target 160",
        "aseptic certificate corrective action queue items target 160",
        "aseptic closure certificate queue items target 160",
        "aseptic closure exception queue items target 160",
        "aseptic closure corrective action queue items target 160",
        "aseptic exception certificate queue items target 160",
        "aseptic exception closure queue items target 160",
        "aseptic exception corrective action queue items target 160",
        "aseptic corrective action certificate queue items target 160",
        "aseptic corrective action closure queue items target 160",
        "aseptic corrective action exception queue items target 160",
        "aseptic certificate closure exception queue items target 160",
        "aseptic certificate closure corrective action queue items target 160",
        "aseptic certificate exception closure queue items target 160",
        "aseptic certificate exception corrective action queue items target 160",
        "aseptic certificate corrective action closure queue items target 160",
        "aseptic certificate corrective action exception queue items target 160",
        "aseptic closure certificate exception queue items target 160",
        "aseptic closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_contaminant_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "contaminant certificate closure queue items target 160",
        "contaminant certificate exception queue items target 160",
        "contaminant certificate corrective action queue items target 160",
        "contaminant closure certificate queue items target 160",
        "contaminant closure exception queue items target 160",
        "contaminant closure corrective action queue items target 160",
        "contaminant exception certificate queue items target 160",
        "contaminant exception closure queue items target 160",
        "contaminant exception corrective action queue items target 160",
        "contaminant corrective action certificate queue items target 160",
        "contaminant corrective action closure queue items target 160",
        "contaminant corrective action exception queue items target 160",
        "contaminant certificate closure exception queue items target 160",
        "contaminant certificate closure corrective action queue items target 160",
        "contaminant certificate exception closure queue items target 160",
        "contaminant certificate exception corrective action queue items target 160",
        "contaminant certificate corrective action closure queue items target 160",
        "contaminant certificate corrective action exception queue items target 160",
        "contaminant closure certificate exception queue items target 160",
        "contaminant closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_sanitization_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "sanitization certificate closure queue items target 160",
        "sanitization certificate exception queue items target 160",
        "sanitization certificate corrective action queue items target 160",
        "sanitization closure certificate queue items target 160",
        "sanitization closure exception queue items target 160",
        "sanitization closure corrective action queue items target 160",
        "sanitization exception certificate queue items target 160",
        "sanitization exception closure queue items target 160",
        "sanitization exception corrective action queue items target 160",
        "sanitization corrective action certificate queue items target 160",
        "sanitization corrective action closure queue items target 160",
        "sanitization corrective action exception queue items target 160",
        "sanitization certificate closure exception queue items target 160",
        "sanitization certificate closure corrective action queue items target 160",
        "sanitization certificate exception closure queue items target 160",
        "sanitization certificate exception corrective action queue items target 160",
        "sanitization certificate corrective action closure queue items target 160",
        "sanitization certificate corrective action exception queue items target 160",
        "sanitization closure certificate exception queue items target 160",
        "sanitization closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_quality_assurance_readiness_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "quality assurance readiness certificate closure queue items target 160",
        "quality assurance readiness certificate exception queue items target 160",
        "quality assurance readiness certificate corrective action queue items target 160",
        "quality assurance readiness closure certificate queue items target 160",
        "quality assurance readiness closure exception queue items target 160",
        "quality assurance readiness closure corrective action queue items target 160",
        "quality assurance readiness exception certificate queue items target 160",
        "quality assurance readiness exception closure queue items target 160",
        "quality assurance readiness exception corrective action queue items target 160",
        "quality assurance readiness corrective action certificate queue items target 160",
        "quality assurance readiness corrective action closure queue items target 160",
        "quality assurance readiness corrective action exception queue items target 160",
        "quality assurance readiness certificate closure exception queue items target 160",
        "quality assurance readiness certificate closure corrective action queue items target 160",
        "quality assurance readiness certificate exception closure queue items target 160",
        "quality assurance readiness certificate exception corrective action queue items target 160",
        "quality assurance readiness certificate corrective action closure queue items target 160",
        "quality assurance readiness certificate corrective action exception queue items target 160",
        "quality assurance readiness closure certificate exception queue items target 160",
        "quality assurance readiness closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_cold_storage_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "cold storage certificate closure queue items target 160",
        "cold storage certificate exception queue items target 160",
        "cold storage certificate corrective action queue items target 160",
        "cold storage closure certificate queue items target 160",
        "cold storage closure exception queue items target 160",
        "cold storage closure corrective action queue items target 160",
        "cold storage exception certificate queue items target 160",
        "cold storage exception closure queue items target 160",
        "cold storage exception corrective action queue items target 160",
        "cold storage corrective action certificate queue items target 160",
        "cold storage corrective action closure queue items target 160",
        "cold storage corrective action exception queue items target 160",
        "cold storage certificate closure exception queue items target 160",
        "cold storage certificate closure corrective action queue items target 160",
        "cold storage certificate exception closure queue items target 160",
        "cold storage certificate exception corrective action queue items target 160",
        "cold storage certificate corrective action closure queue items target 160",
        "cold storage certificate corrective action exception queue items target 160",
        "cold storage closure certificate exception queue items target 160",
        "cold storage closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_temperature_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "temperature control certificate closure queue items target 160",
        "temperature control certificate exception queue items target 160",
        "temperature control certificate corrective action queue items target 160",
        "temperature control closure certificate queue items target 160",
        "temperature control closure exception queue items target 160",
        "temperature control closure corrective action queue items target 160",
        "temperature control exception certificate queue items target 160",
        "temperature control exception closure queue items target 160",
        "temperature control exception corrective action queue items target 160",
        "temperature control corrective action certificate queue items target 160",
        "temperature control corrective action closure queue items target 160",
        "temperature control corrective action exception queue items target 160",
        "temperature control certificate closure exception queue items target 160",
        "temperature control certificate closure corrective action queue items target 160",
        "temperature control certificate exception closure queue items target 160",
        "temperature control certificate exception corrective action queue items target 160",
        "temperature control certificate corrective action closure queue items target 160",
        "temperature control certificate corrective action exception queue items target 160",
        "temperature control closure certificate exception queue items target 160",
        "temperature control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_refrigeration_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "refrigeration certificate closure queue items target 160",
        "refrigeration certificate exception queue items target 160",
        "refrigeration certificate corrective action queue items target 160",
        "refrigeration closure certificate queue items target 160",
        "refrigeration closure exception queue items target 160",
        "refrigeration closure corrective action queue items target 160",
        "refrigeration exception certificate queue items target 160",
        "refrigeration exception closure queue items target 160",
        "refrigeration exception corrective action queue items target 160",
        "refrigeration corrective action certificate queue items target 160",
        "refrigeration corrective action closure queue items target 160",
        "refrigeration corrective action exception queue items target 160",
        "refrigeration certificate closure exception queue items target 160",
        "refrigeration certificate closure corrective action queue items target 160",
        "refrigeration certificate exception closure queue items target 160",
        "refrigeration certificate exception corrective action queue items target 160",
        "refrigeration certificate corrective action closure queue items target 160",
        "refrigeration certificate corrective action exception queue items target 160",
        "refrigeration closure certificate exception queue items target 160",
        "refrigeration closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_pathogen_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "pathogen control certificate closure queue items target 160",
        "pathogen control certificate exception queue items target 160",
        "pathogen control certificate corrective action queue items target 160",
        "pathogen control closure certificate queue items target 160",
        "pathogen control closure exception queue items target 160",
        "pathogen control closure corrective action queue items target 160",
        "pathogen control exception certificate queue items target 160",
        "pathogen control exception closure queue items target 160",
        "pathogen control exception corrective action queue items target 160",
        "pathogen control corrective action certificate queue items target 160",
        "pathogen control corrective action closure queue items target 160",
        "pathogen control corrective action exception queue items target 160",
        "pathogen control certificate closure exception queue items target 160",
        "pathogen control certificate closure corrective action queue items target 160",
        "pathogen control certificate exception closure queue items target 160",
        "pathogen control certificate exception corrective action queue items target 160",
        "pathogen control certificate corrective action closure queue items target 160",
        "pathogen control certificate corrective action exception queue items target 160",
        "pathogen control closure certificate exception queue items target 160",
        "pathogen control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_aseptic_processing_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "aseptic processing certificate closure queue items target 160",
        "aseptic processing certificate exception queue items target 160",
        "aseptic processing certificate corrective action queue items target 160",
        "aseptic processing closure certificate queue items target 160",
        "aseptic processing closure exception queue items target 160",
        "aseptic processing closure corrective action queue items target 160",
        "aseptic processing exception certificate queue items target 160",
        "aseptic processing exception closure queue items target 160",
        "aseptic processing exception corrective action queue items target 160",
        "aseptic processing corrective action certificate queue items target 160",
        "aseptic processing corrective action closure queue items target 160",
        "aseptic processing corrective action exception queue items target 160",
        "aseptic processing certificate closure exception queue items target 160",
        "aseptic processing certificate closure corrective action queue items target 160",
        "aseptic processing certificate exception closure queue items target 160",
        "aseptic processing certificate exception corrective action queue items target 160",
        "aseptic processing certificate corrective action closure queue items target 160",
        "aseptic processing certificate corrective action exception queue items target 160",
        "aseptic processing closure certificate exception queue items target 160",
        "aseptic processing closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_contaminant_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "contaminant control certificate closure queue items target 160",
        "contaminant control certificate exception queue items target 160",
        "contaminant control certificate corrective action queue items target 160",
        "contaminant control closure certificate queue items target 160",
        "contaminant control closure exception queue items target 160",
        "contaminant control closure corrective action queue items target 160",
        "contaminant control exception certificate queue items target 160",
        "contaminant control exception closure queue items target 160",
        "contaminant control exception corrective action queue items target 160",
        "contaminant control corrective action certificate queue items target 160",
        "contaminant control corrective action closure queue items target 160",
        "contaminant control corrective action exception queue items target 160",
        "contaminant control certificate closure exception queue items target 160",
        "contaminant control certificate closure corrective action queue items target 160",
        "contaminant control certificate exception closure queue items target 160",
        "contaminant control certificate exception corrective action queue items target 160",
        "contaminant control certificate corrective action closure queue items target 160",
        "contaminant control certificate corrective action exception queue items target 160",
        "contaminant control closure certificate exception queue items target 160",
        "contaminant control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_sanitization_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "sanitization control certificate closure queue items target 160",
        "sanitization control certificate exception queue items target 160",
        "sanitization control certificate corrective action queue items target 160",
        "sanitization control closure certificate queue items target 160",
        "sanitization control closure exception queue items target 160",
        "sanitization control closure corrective action queue items target 160",
        "sanitization control exception certificate queue items target 160",
        "sanitization control exception closure queue items target 160",
        "sanitization control exception corrective action queue items target 160",
        "sanitization control corrective action certificate queue items target 160",
        "sanitization control corrective action closure queue items target 160",
        "sanitization control corrective action exception queue items target 160",
        "sanitization control certificate closure exception queue items target 160",
        "sanitization control certificate closure corrective action queue items target 160",
        "sanitization control certificate exception closure queue items target 160",
        "sanitization control certificate exception corrective action queue items target 160",
        "sanitization control certificate corrective action closure queue items target 160",
        "sanitization control certificate corrective action exception queue items target 160",
        "sanitization control closure certificate exception queue items target 160",
        "sanitization control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_quality_readiness_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "quality readiness certificate closure queue items target 160",
        "quality readiness certificate exception queue items target 160",
        "quality readiness certificate corrective action queue items target 160",
        "quality readiness closure certificate queue items target 160",
        "quality readiness closure exception queue items target 160",
        "quality readiness closure corrective action queue items target 160",
        "quality readiness exception certificate queue items target 160",
        "quality readiness exception closure queue items target 160",
        "quality readiness exception corrective action queue items target 160",
        "quality readiness corrective action certificate queue items target 160",
        "quality readiness corrective action closure queue items target 160",
        "quality readiness corrective action exception queue items target 160",
        "quality readiness certificate closure exception queue items target 160",
        "quality readiness certificate closure corrective action queue items target 160",
        "quality readiness certificate exception closure queue items target 160",
        "quality readiness certificate exception corrective action queue items target 160",
        "quality readiness certificate corrective action closure queue items target 160",
        "quality readiness certificate corrective action exception queue items target 160",
        "quality readiness closure certificate exception queue items target 160",
        "quality readiness closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_cold_storage_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "cold storage control certificate closure queue items target 160",
        "cold storage control certificate exception queue items target 160",
        "cold storage control certificate corrective action queue items target 160",
        "cold storage control closure certificate queue items target 160",
        "cold storage control closure exception queue items target 160",
        "cold storage control closure corrective action queue items target 160",
        "cold storage control exception certificate queue items target 160",
        "cold storage control exception closure queue items target 160",
        "cold storage control exception corrective action queue items target 160",
        "cold storage control corrective action certificate queue items target 160",
        "cold storage control corrective action closure queue items target 160",
        "cold storage control corrective action exception queue items target 160",
        "cold storage control certificate closure exception queue items target 160",
        "cold storage control certificate closure corrective action queue items target 160",
        "cold storage control certificate exception closure queue items target 160",
        "cold storage control certificate exception corrective action queue items target 160",
        "cold storage control certificate corrective action closure queue items target 160",
        "cold storage control certificate corrective action exception queue items target 160",
        "cold storage control closure certificate exception queue items target 160",
        "cold storage control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_temperature_management_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "temperature management certificate closure queue items target 160",
        "temperature management certificate exception queue items target 160",
        "temperature management certificate corrective action queue items target 160",
        "temperature management closure certificate queue items target 160",
        "temperature management closure exception queue items target 160",
        "temperature management closure corrective action queue items target 160",
        "temperature management exception certificate queue items target 160",
        "temperature management exception closure queue items target 160",
        "temperature management exception corrective action queue items target 160",
        "temperature management corrective action certificate queue items target 160",
        "temperature management corrective action closure queue items target 160",
        "temperature management corrective action exception queue items target 160",
        "temperature management certificate closure exception queue items target 160",
        "temperature management certificate closure corrective action queue items target 160",
        "temperature management certificate exception closure queue items target 160",
        "temperature management certificate exception corrective action queue items target 160",
        "temperature management certificate corrective action closure queue items target 160",
        "temperature management certificate corrective action exception queue items target 160",
        "temperature management closure certificate exception queue items target 160",
        "temperature management closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]

def test_extract_target_price_numbers_ignores_refrigeration_control_certificate_closure_corrective_action_service_queue_targets():
    targets = (
        "refrigeration control certificate closure queue items target 160",
        "refrigeration control certificate exception queue items target 160",
        "refrigeration control certificate corrective action queue items target 160",
        "refrigeration control closure certificate queue items target 160",
        "refrigeration control closure exception queue items target 160",
        "refrigeration control closure corrective action queue items target 160",
        "refrigeration control exception certificate queue items target 160",
        "refrigeration control exception closure queue items target 160",
        "refrigeration control exception corrective action queue items target 160",
        "refrigeration control corrective action certificate queue items target 160",
        "refrigeration control corrective action closure queue items target 160",
        "refrigeration control corrective action exception queue items target 160",
        "refrigeration control certificate closure exception queue items target 160",
        "refrigeration control certificate closure corrective action queue items target 160",
        "refrigeration control certificate exception closure queue items target 160",
        "refrigeration control certificate exception corrective action queue items target 160",
        "refrigeration control certificate corrective action closure queue items target 160",
        "refrigeration control certificate corrective action exception queue items target 160",
        "refrigeration control closure certificate exception queue items target 160",
        "refrigeration control closure certificate corrective action queue items target 160",
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_pathogen_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pathogen response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_aseptic_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"aseptic response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_contaminant_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contaminant response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_sanitization_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitization response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_readiness_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_temperature_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"temperature assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_thermal_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"thermal management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_cold_chain_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_refrigeration_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"refrigeration management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_food_safety_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_quality_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_hygiene_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_readiness_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_temperature_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"temperature readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]


def test_extract_target_price_numbers_ignores_thermal_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"thermal assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [160.0]
def test_extract_target_price_numbers_ignores_cold_storage_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold storage management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_refrigeration_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"refrigeration assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_food_safety_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_quality_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_hygiene_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_readiness_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_temperature_management_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"temperature management assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_thermal_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"thermal readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_refrigeration_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"refrigeration readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_safety_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_assurance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain assurance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_refrigeration_assurance_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"refrigeration assurance readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_safety_assurance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety assurance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_assurance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene assurance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_assurance_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene assurance readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_assurance_management_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain assurance management readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
def test_extract_target_price_numbers_ignores_food_safety_assurance_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety assurance readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_assurance_management_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene assurance management readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_assurance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness assurance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_assurance_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain assurance readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_safety_assurance_management_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety assurance management readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_management_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness management assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_assurance_management_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness assurance management control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_management_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance management readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_management_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance management control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_management_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance management response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_management_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance management assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance readiness response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_control_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance control management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_control_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance control readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_assurance_response_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality assurance response management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality readiness response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_readiness_assurance_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"readiness assurance control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_control_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality control management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_control_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality control readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_control_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality control response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quality_control_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quality control assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_thermal_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"thermal control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_thermal_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"thermal response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_temperature_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"temperature response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_storage_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold storage assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_storage_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold storage readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_storage_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold storage response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cold_chain_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cold chain response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_refrigeration_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"refrigeration response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pathogen_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pathogen management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pathogen_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pathogen assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pathogen_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pathogen readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_aseptic_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"aseptic management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_aseptic_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"aseptic control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_aseptic_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"aseptic assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_aseptic_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"aseptic readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contaminant_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contaminant management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contaminant_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contaminant assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contaminant_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contaminant readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitization_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitization management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitization_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitization assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitization_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitization readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitation_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitation management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitation_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitation control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitation_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitation assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitation_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitation readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sanitation_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sanitation response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_hygiene_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"hygiene control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_safety_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_safety_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food safety control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_grade_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food grade management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_grade_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food grade control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_grade_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food grade assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_grade_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food grade readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_food_grade_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"food grade response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_tanker_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"tanker management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_tanker_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"tanker control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_tanker_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"tanker assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_tanker_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"tanker readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_tanker_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"tanker response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_residue_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"residue management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_residue_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"residue control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_residue_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"residue assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_residue_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"residue readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_residue_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"residue response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pest_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pest management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pest_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pest control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pest_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pest assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pest_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pest readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_pest_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"pest response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_odor_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"odor management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_odor_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"odor control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_odor_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"odor assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_odor_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"odor readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_odor_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"odor response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_flexitank_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"flexitank management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_flexitank_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"flexitank control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_flexitank_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"flexitank assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_flexitank_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"flexitank readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_flexitank_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"flexitank response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quarantine_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quarantine management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quarantine_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quarantine control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quarantine_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quarantine assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quarantine_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quarantine readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_quarantine_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"quarantine response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_fumigation_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"fumigation management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_fumigation_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"fumigation control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_fumigation_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"fumigation assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_fumigation_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"fumigation readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_fumigation_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"fumigation response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cleaning_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cleaning management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cleaning_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cleaning control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cleaning_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cleaning assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cleaning_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cleaning readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_cleaning_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"cleaning response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contamination_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contamination management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contamination_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contamination control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contamination_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contamination assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contamination_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contamination readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_contamination_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"contamination response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_mold_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"mold management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_mold_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"mold control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_mold_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"mold assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_mold_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"mold readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_mold_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"mold response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_allergen_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"allergen management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_allergen_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"allergen control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_allergen_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"allergen assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_allergen_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"allergen readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_allergen_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"allergen response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_spoilage_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"spoilage management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_spoilage_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"spoilage control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_spoilage_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"spoilage assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_spoilage_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"spoilage readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_spoilage_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"spoilage response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_biosecurity_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"biosecurity management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_biosecurity_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"biosecurity control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_biosecurity_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"biosecurity assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_biosecurity_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"biosecurity readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_biosecurity_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"biosecurity response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_microbial_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"microbial management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_microbial_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"microbial control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_microbial_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"microbial assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_microbial_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"microbial readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_microbial_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"microbial response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterility_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterility management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterility_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterility control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterility_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterility assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterility_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterility readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterility_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterility response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]



def test_extract_target_price_numbers_ignores_sterilization_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterilization management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterilization_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterilization control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterilization_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterilization assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterilization_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterilization readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sterilization_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"sterilization response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_haccp_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"haccp management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_haccp_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"haccp control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_haccp_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"haccp assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_haccp_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"haccp readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_haccp_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"haccp response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_recall_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"recall management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_recall_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"recall control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_recall_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"recall assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_recall_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"recall readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_recall_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"recall response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_traceability_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"traceability management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_traceability_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"traceability control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_traceability_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"traceability assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_traceability_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"traceability readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_traceability_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"traceability response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_inspection_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"inspection management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_inspection_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"inspection control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_inspection_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"inspection assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_inspection_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"inspection readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_inspection_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"inspection response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"audit management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"audit control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_assurance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"audit assurance {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_readiness_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"audit readiness {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"audit response {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_compliance_management_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"compliance management {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_compliance_control_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    targets = tuple(
        f"compliance control {' '.join(combo)} queue items target 160"
        for size in (2, 3, 4)
        for combo in permutations(terms, size)
    )[:20]

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_compliance_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"compliance {state} {' '.join(combo)} queue items target 160"
        for state in ("assurance", "readiness", "response")
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_policy_management_control_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"policy {state} {' '.join(combo)} queue items target 160"
        for state in states
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_regulatory_management_control_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"regulatory {state} {' '.join(combo)} queue items target 160"
        for state in states
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_plain_policy_regulatory_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    prefixes = ("policy", "regulatory")
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_control_documentation_management_control_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    prefixes = ("control documentation", *(f"control documentation {state}" for state in states))
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_governance_management_control_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    prefixes = ("governance", *(f"governance {state}" for state in states))
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_control_management_control_assurance_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    prefixes = ("control", *(f"control {state}" for state in states))
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_control_governance_regulatory_documentation_evidence_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "control documentation",
        "control evidence",
        "governance documentation",
        "governance evidence",
        "regulatory documentation",
        "regulatory evidence",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_policy_audit_certification_documentation_evidence_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "policy documentation",
        "policy evidence",
        "audit documentation",
        "audit evidence",
        "certification documentation",
        "certification evidence",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_sox_privacy_security_risk_records_attestation_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "sox",
        "privacy",
        "data privacy",
        "security",
        "cybersecurity",
        "risk",
        "vendor risk",
        "third party risk",
        "supplier risk",
        "records",
        "attestation",
        "operational risk",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_review_resilience_identity_access_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "internal audit",
        "external audit",
        "compliance review",
        "risk assessment",
        "business continuity",
        "business resilience",
        "resilience",
        "continuity planning",
        "disaster recovery",
        "crisis management",
        "incident response",
        "identity access",
        "third party assurance",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_audit_review_continuity_resilience_incident_identity_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "internal audit",
        "external audit",
        "compliance review",
        "risk assessment",
        "business continuity",
        "business resilience",
        "continuity planning",
        "resilience",
        "incident response",
        "identity access",
        "disaster recovery",
        "crisis management",
        "third party assurance",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_access_change_management_supplier_vendor_assurance_business_recovery_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "access management",
        "change management",
        "supplier assurance",
        "vendor assurance",
        "business recovery",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_vendor_supplier_review_assurance_access_change_recovery_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "access management",
        "change management",
        "business recovery",
        "vendor assurance",
        "supplier assurance",
        "vendor review",
        "supplier review",
        "third party review",
        "control review",
        "policy review",
        "audit review",
        "security review",
        "privacy review",
        "access review",
        "identity review",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_finding_remediation_exception_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "control finding",
        "audit finding",
        "compliance finding",
        "incident finding",
        "control remediation",
        "audit remediation",
        "compliance remediation",
        "security remediation",
        "privacy remediation",
        "risk remediation",
        "access remediation",
        "identity remediation",
        "control exception",
        "policy exception",
        "security exception",
        "privacy exception",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_broader_finding_remediation_exception_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "risk finding",
        "security finding",
        "privacy finding",
        "access finding",
        "identity finding",
        "policy finding",
        "vendor finding",
        "supplier finding",
        "third party finding",
        "third-party finding",
        "change finding",
        "business finding",
        "policy remediation",
        "vendor remediation",
        "supplier remediation",
        "third party remediation",
        "third-party remediation",
        "incident remediation",
        "business remediation",
        "change remediation",
        "compliance exception",
        "audit exception",
        "risk exception",
        "access exception",
        "identity exception",
        "incident exception",
        "vendor exception",
        "supplier exception",
        "third party exception",
        "third-party exception",
        "business exception",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_monitoring_validation_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "supplier monitoring",
        "vendor monitoring",
        "third party monitoring",
        "third-party monitoring",
        "identity monitoring",
        "recovery monitoring",
        "continuity monitoring",
        "resilience monitoring",
        "supplier validation",
        "vendor validation",
        "third party validation",
        "third-party validation",
        "identity validation",
        "recovery validation",
        "continuity validation",
        "resilience validation",
        "control validation",
        "audit validation",
        "compliance validation",
        "policy validation",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_enterprise_market_credit_model_data_cyber_fraud_validation_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "enterprise validation",
        "market validation",
        "credit validation",
        "model validation",
        "data validation",
        "cyber validation",
        "fraud validation",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_enterprise_market_credit_model_data_cyber_fraud_monitoring_oversight_review_assessment_testing_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("enterprise", "market", "credit", "model", "data", "cyber", "fraud")
    phases = ("monitoring", "oversight", "review", "assessment", "testing")
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_financial_legal_operational_regulatory_governance_program_process_monitoring_oversight_review_assessment_testing_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "financial",
        "legal",
        "operational",
        "regulatory",
        "governance",
        "program",
        "process",
    )
    phases = ("monitoring", "oversight", "review", "assessment", "testing")
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_financial_legal_operational_regulatory_governance_program_process_finding_remediation_exception_validation_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "financial finding",
        "financial remediation",
        "financial exception",
        "financial validation",
        "legal finding",
        "legal remediation",
        "legal exception",
        "legal validation",
        "operational finding",
        "operational remediation",
        "operational exception",
        "operational validation",
        "regulatory finding",
        "regulatory remediation",
        "regulatory exception",
        "regulatory validation",
        "governance finding",
        "governance remediation",
        "governance exception",
        "governance validation",
        "program finding",
        "program remediation",
        "program exception",
        "program validation",
        "process finding",
        "process remediation",
        "process exception",
        "process validation",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_technology_platform_vendor_supplier_third_party_risk_business_continuity_disaster_recovery_crisis_management_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "technology",
        "platform",
        "vendor risk",
        "supplier risk",
        "third party risk",
        "third-party risk",
        "business continuity",
        "disaster recovery",
        "crisis management",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_customer_client_partner_channel_sales_support_contract_order_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "customer",
        "client",
        "partner",
        "channel",
        "sales",
        "support",
        "contract",
        "order",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_product_service_account_subscription_billing_payment_invoice_renewal_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "product",
        "service",
        "account",
        "subscription",
        "billing",
        "payment",
        "invoice",
        "renewal",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_technology_platform_vendor_supplier_third_party_management_assurance_readiness_response_assessment_testing_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "technology management",
        "technology assurance",
        "technology readiness",
        "technology response",
        "platform management",
        "platform assurance",
        "platform readiness",
        "platform response",
        "vendor assessment",
        "vendor testing",
        "supplier assessment",
        "supplier testing",
        "third party assessment",
        "third party testing",
        "third-party assessment",
        "third-party testing",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_business_resilience_continuity_planning_incident_response_identity_access_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        *(f"business resilience {phase}" for phase in ("review", "assessment", "testing", "finding", "remediation")),
        *(
            f"continuity planning {phase}"
            for phase in ("monitoring", "oversight", "review", "assessment", "testing", "finding", "remediation", "validation")
        ),
        *(
            f"incident response {phase}"
            for phase in ("monitoring", "oversight", "review", "assessment", "testing", "finding", "remediation", "validation")
        ),
        *(f"identity access {phase}" for phase in ("monitoring", "oversight", "assessment", "testing", "validation")),
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_onboarding_implementation_project_delivery_success_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("onboarding", "implementation", "project", "delivery", "success")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_operations_workflow_case_ticket_request_backlog_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("operations", "workflow", "case", "ticket", "request", "backlog")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_queue_fulfillment_warehouse_claims_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("queue", "fulfillment", "warehouse", "claims")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_logistics_shipping_shipment_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("logistics", "shipping", "shipment")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_carrier_routing_dispatch_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("carrier", "routing", "dispatch")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_policy_member_provider_patient_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("policy", "member", "provider", "patient")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_supplier_vendor_assurance_business_recovery_service_queue_phase_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("supplier assurance", "vendor assurance", "business recovery")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_receiving_putaway_replenishment_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("receiving", "putaway", "replenishment")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_eligibility_authorization_enrollment_benefit_coverage_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("eligibility", "authorization", "enrollment", "benefit", "coverage")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_referral_utilization_appeal_credentialing_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = ("referral", "utilization", "appeal", "credentialing")
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_care_management_medical_claim_claims_adjudication_patient_visit_appointment_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "care management",
        "medical claim",
        "claims adjudication",
        "patient visit",
        "appointment",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_case_review_admission_financial_aid_course_registration_claim_claims_review_benefit_verification_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "case review",
        "admission",
        "financial aid",
        "course registration",
        "claim review",
        "claims review",
        "benefit verification",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_student_application_admissions_recruiting_appeal_content_review_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "student application",
        "application",
        "admissions decision",
        "candidate screening",
        "interview",
        "offer",
        "background check",
        "job requisition",
        "requisition",
        "appeal resolution",
        "content review",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_moderation_abuse_policy_user_report_model_evaluation_labeling_annotation_dataset_training_inference_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "moderation action",
        "abuse report",
        "policy violation",
        "user report",
        "model evaluation",
        "model validation",
        "labeling task",
        "annotation task",
        "dataset review",
        "training job",
        "inference job",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_milestone_project_task_backlog_requirement_service_visit_technician_truck_roll_install_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "milestones completed",
        "project milestone",
        "task completed",
        "open task",
        "backlog item",
        "requirement",
        "service visit",
        "technician visit",
        "truck roll",
        "install",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_policy_issued_app_rating_fpy_yield_defect_scrap_rework_warranty_service_campaign_quality_complaint_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    roots = (
        "policy issued",
        "app rating",
        "fpy",
        "yield rate",
        "defect rate",
        "scrap rate",
        "rework rate",
        "warranty claim",
        "service campaign",
        "quality complaint",
    )
    phases = (
        "monitoring",
        "oversight",
        "review",
        "assessment",
        "testing",
        "finding",
        "remediation",
        "exception",
        "validation",
    )
    base_prefixes = tuple(f"{root} {phase}" for root in roots for phase in phases)
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items {suffix}"
        for prefix in prefixes
        for combo in selected_combos
        for suffix in ("target 160", "reached 160 in Q4")
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_supplier_vendor_identity_management_recovery_continuity_resilience_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "supplier management",
        "vendor management",
        "third party management",
        "identity management",
        "recovery planning",
        "continuity assurance",
        "resilience planning",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_supplier_vendor_third_party_identity_recovery_continuity_resilience_readiness_response_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "supplier readiness",
        "vendor readiness",
        "third party readiness",
        "identity readiness",
        "recovery readiness",
        "continuity readiness",
        "supplier response",
        "vendor response",
        "third party response",
        "identity response",
        "recovery response",
        "continuity response",
        "resilience response",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_identity_recovery_resilience_assurance_and_oversight_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    states = ("management", "control", "assurance", "readiness", "response")
    base_prefixes = (
        "identity assurance",
        "recovery assurance",
        "resilience assurance",
        "supplier oversight",
        "vendor oversight",
        "third party oversight",
        "identity oversight",
        "recovery oversight",
        "continuity oversight",
        "resilience oversight",
    )
    prefixes = tuple(
        prefix
        for base_prefix in base_prefixes
        for prefix in (base_prefix, *(f"{base_prefix} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:20]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_certification_governance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    prefixes = (
        "certification",
        "certification audit",
        "certification management",
        "certification control",
        "certification assurance",
        "certification readiness",
        "certification response",
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:12]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]


def test_extract_target_price_numbers_ignores_compliance_documentation_evidence_conformance_certificate_closure_corrective_action_service_queue_targets():
    from itertools import permutations

    terms = ("certificate", "closure", "exception", "corrective action")
    bases = (
        "compliance documentation",
        "compliance evidence",
        "conformance",
        "conformity",
        "control evidence",
    )
    states = ("management", "control", "assurance", "readiness", "response")
    prefixes = tuple(
        prefix for base in bases for prefix in (base, *(f"{base} {state}" for state in states))
    )
    selected_combos = tuple(
        combo for size in (2, 3, 4) for combo in permutations(terms, size)
    )[:8]
    targets = tuple(
        f"{prefix} {' '.join(combo)} queue items target 160"
        for prefix in prefixes
        for combo in selected_combos
    )

    for target in targets:
        assert _extract_target_price_numbers(target) == []
        assert _extract_target_price_numbers(f"target price NT$160 with {target}") == [
            160.0
        ]
