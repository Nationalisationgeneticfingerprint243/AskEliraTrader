# 🎨 Custom Use Cases — Beyond Polymarket

Quantjellyfish can be adapted for ANY binary prediction task.

---

## 🔮 **Core Prediction Engine**

**What Quantjellyfish does:**
1. Research (Alba) → Gathers information
2. Simulate (David + MiroFish) → Models crowd behavior
3. Audit (Vex) → Validates prediction logic
4. Decide (Orb) → Confidence-based go/no-go
5. Execute (Steven) → Takes action

**This works for ANY binary outcome.**

---

## 📈 **Example: NQ (NASDAQ) Bullish/Bearish Today**

**Goal:** Predict if NQ closes higher/lower than open each day.

### **Step 1: Modify Alba (Research)**

**File:** `Agents/alba.py`

**Change market scan:**
```python
def scan_nq_market(today: str) -> Market:
    """
    Alba scans for NQ prediction instead of Polymarket/Kalshi.
    """
    # Get current NQ price
    nq_open = get_nq_open_price()  # Your data source
    
    # Create synthetic binary market
    market = Market(
        question=f"Will NQ close higher than ${nq_open} today?",
        platform="NQ-Trading",
        yes_price=0.50,  # Start at 50% (neutral)
        resolution_date=today,
        resolution_criteria=f"NQ futures close > {nq_open} at 4:00 PM ET",
        liquidity=0,  # Not a real market
        why_mispriced="Daily momentum prediction",
        uncertainty="MEDIUM",
        slug=f"nq-{today}"
    )
    
    return market
```

**Change web search sources:**
```python
def build_nq_seed_file(market: Market, today: str) -> Path:
    """
    Alba researches NQ instead of Polymarket markets.
    """
    # Search for:
    # - Economic calendar (Fed, CPI, jobs data)
    # - Market news (earnings, geopolitics)
    # - Futures positioning (COT reports)
    # - Technical analysis (support/resistance)
    # - Sentiment (fear/greed index)
    
    seed_sources = [
        web_search("NASDAQ futures news today"),
        web_search("US economic data releases today"),
        web_search("SPY QQQ sentiment"),
        web_search("technical analysis NQ futures"),
        # ... (6-8 total sources)
    ]
    
    # Build seed file same way
    return seed_path
```

---

### **Step 2: MiroFish Simulation (No Changes Needed!)**

**David runs MiroFish exactly as-is:**
- Input: Alba's NQ seed file
- Simulation: Crowd predicts NQ direction
- Output: Confidence (e.g., 72% BULLISH)

**MiroFish models trader sentiment → predicts NQ direction**

---

### **Step 3: Modify Vex (Audit)**

**Vex checks:**
- ✅ Simulation matches question ("NQ close > open")
- ✅ Seed sources are recent (<6h for intraday)
- ✅ No look-ahead bias (no post-close data)
- ✅ Agent population matches (traders, not voters)

**File:** `Agents/vex.py`

**Adjust agent population check:**
```python
# In check_agent_population_bias()
if "NQ" in market.question or "NASDAQ" in market.question:
    # Expect trader-heavy population
    expected_domain = "financial"
```

---

### **Step 4: Modify Orb (Decision)**

**Orb approves based on confidence:**
```python
# In go_no_go()
# If confidence ≥65% → APPROVE
# Calculate position size based on confidence tier
```

**Capital sizing:**
- Tier 1 (65-74%): 0.5% of capital
- Tier 2 (75-84%): 1.0% of capital
- Tier 3 (≥85%): 2.0% of capital

---

### **Step 5: Modify Steven (Execution)**

**Steven executes NQ trades instead of Polymarket:**

**File:** `Agents/steven.py`

**Add NQ execution:**
```python
def _execute_nq_trade(
    market: Market,
    direction: str,  # "BULLISH" or "BEARISH"
    size: float,
) -> Dict:
    """
    Execute NQ futures trade via your broker API.
    
    Brokers:
    - Interactive Brokers (IBKR API)
    - TastyTrade API
    - Tradier API
    - TD Ameritrade API
    """
    if direction == "BULLISH":
        # Buy NQ futures or /NQ options
        order = broker.buy_nq_futures(contracts=calculate_contracts(size))
    else:
        # Sell/short NQ futures
        order = broker.sell_nq_futures(contracts=calculate_contracts(size))
    
    return {
        "order_id": order.id,
        "entry_price": order.fill_price,
        "filled_size": size,
        "status": "filled"
    }
```

**Paper trading:**
```python
def _execute_nq_paper_trade(direction: str, size: float) -> Dict:
    """
    Simulated NQ trade (no real broker).
    """
    nq_price = get_current_nq_price()
    
    return {
        "order_id": f"paper_nq_{datetime.now().strftime('%H%M%S')}",
        "entry_price": nq_price,
        "direction": direction,
        "size": size,
        "status": "filled"
    }
```

---

## 📊 **Full NQ Workflow**

```
Daily at 8:30 AM ET:
├─ Alba scans NQ futures (current price)
├─ Alba researches: economic data, news, sentiment
├─ Alba builds seed file (6-8 sources)
├─ David runs MiroFish simulation
│   └─ Predicts: 72% BULLISH
├─ Vex audits (checks for bias, recent data)
├─ Orb approves: Tier 2 (72% confidence)
├─ Steven executes: Buy 1 /NQ contract (paper mode)
└─ Monitor until 4:00 PM ET (market close)

At 4:00 PM ET:
├─ Check NQ close vs open
├─ Calculate P&L
├─ Log to calibration (WIN/LOSS)
└─ Update Pinecone (learn from outcome)
```

---

## 🔧 **Code Changes Required**

**Minimal modification:**

| File | Changes | Effort |
|------|---------|--------|
| `alba.py` | scan_nq_market(), build_nq_seed_file() | 1-2 hours |
| `david.py` | (No changes needed) | 0 min |
| `vex.py` | Adjust population check | 15 min |
| `orb.py` | (No changes needed) | 0 min |
| `steven.py` | _execute_nq_trade() | 2-3 hours |
| `models.py` | Add NQMarket dataclass | 30 min |

**Total:** 4-6 hours to adapt for NQ trading

---

## 🎯 **Other Use Cases**

**Same framework works for:**

1. **Forex (EUR/USD bullish/bearish)**
   - Alba → Forex news, central bank data
   - MiroFish → Trader sentiment
   - Steven → Forex broker API

2. **Crypto (BTC up/down today)**
   - Alba → Crypto news, on-chain data
   - MiroFish → Trader crowd behavior
   - Steven → Exchange API (Binance, Coinbase)

3. **Sports (Team A wins/loses)**
   - Alba → Game stats, injury reports
   - MiroFish → Fan/bettor sentiment
   - Steven → Sportsbook API

4. **Weather (Rain yes/no tomorrow)**
   - Alba → Weather models, forecasts
   - MiroFish → Meteorologist consensus
   - Steven → (No execution, just prediction)

---

## 🚀 **Why MiroFish Works Universally**

**MiroFish doesn't know it's predicting markets.**

It models:
- How groups form opinions
- How information spreads
- How consensus emerges

**This applies to:**
- Traders predicting NQ
- Voters predicting elections
- Fans predicting sports
- Scientists predicting research outcomes

**The seed determines the domain. The simulation is universal.**

---

## 📝 **Quick Adaptation Guide**

**To adapt Quantjellyfish for YOUR use case:**

1. **Define your binary question**
   - "Will X happen by date Y?"
   - Must be YES/NO

2. **Modify Alba's research**
   - Change web searches to your domain
   - Build seed file from relevant sources

3. **Keep MiroFish as-is**
   - It adapts automatically to seed content
   - Agent population adjusts per domain

4. **Adjust Vex's checks**
   - Domain-specific validation
   - Time windows (intraday vs multi-day)

5. **Modify Steven's execution**
   - Your broker/platform API
   - Position sizing logic

**That's it!** The core prediction engine is universal.

---

## 🎁 **Community Adaptations**

We'd love to see:
- NQ/ES futures predictor (you!)
- Crypto swing trader
- Sports betting edge finder
- Political election forecaster
- Corporate earnings predictor

**Share your adaptations:** Submit PRs to the main repo!

---

**Quantjellyfish is a prediction engine, not a platform-specific bot.**

**Any binary outcome. Any timeframe. Any domain.** 🐙
