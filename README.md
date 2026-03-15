# AskElira Trader - Autonomous Prediction Market Trading

> **Built on the [AskElira Framework](https://github.com/jellyforex/askelira)** - Multi-agent orchestration with swarm intelligence

Autonomous trading system for Polymarket & Kalshi prediction markets using 5 AI agents + MiroFish swarm intelligence.

## 🎯 Results

- **65% accuracy** overall (200+ predictions)
- **75% accuracy** on high-confidence trades (≥80% confidence)
- **$0.015** cost per prediction
- **Beat market baseline by 12%**

## 🏗️ Framework

AskElira Trader is the **trading use case** of the AskElira Framework.

**Other AskElira Applications:**
- [AskElira Marketing](https://github.com/jellyforex/askeliramarketing) - Viral marketing campaigns  
- [AskElira Framework](https://github.com/jellyforex/askelira) - Build your own automation

**Want to build your own?** Fork the [framework](https://github.com/jellyforex/askelira) and adapt the 5-agent pattern to your domain.

---

# 🔮 AskElira

**Ask Elira anything. She predicts binary outcomes using 5 AI agents + swarm intelligence.**

Will the Lakers win? Will Bitcoin hit $100K? Who wins the election?

**Elira researches, simulates crowd behavior, validates, and gives you predictions.** Optionally, she can auto-trade on her predictions.

Open source (MIT). Built for prediction markets, adaptable for sports, crypto, futures, forex, or any yes/no outcome.

---

## 🎯 What Elira Does

**Ask her any binary question:**
```
"Ask Elira: Will the Lakers beat the Warriors?"
"Ask Elira: Will Trump win in 2028?"
"Ask Elira: Will Bitcoin reach $100K by June?"
"Ask Elira: Will the Fed cut rates in March?"
```

**How she answers:**
1. 🔍 **Researches** (web search, news, data)
2. 🧠 **Simulates** (thousands of AI agents predict via swarm intelligence)
3. 🛡️ **Validates** (quality checks, catches bad logic)
4. 🎯 **Predicts** (gives you confidence % + direction)
5. 💰 **Trades** (optional: auto-execute on prediction markets/brokers)

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/jellyforex/askeliratrader.git
cd askeliratrader

# 2. Install
pip install -r requirements.txt

# 3. Setup
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 4. Start MiroFish (swarm intelligence engine)
cd MiroFish/Mirofish && docker-compose up -d && cd ../..

# 5. Ask Elira anything
./start_paper_trading.sh --once
```

**First prediction takes ~5-8 minutes.** Results appear in `data/active_positions.json`

---

## 🤖 Meet Elira's Team

**Elira orchestrates 5 specialized AI agents:**

| Agent | Role | What They Do |
|-------|------|--------------|
| **Alba** | Research Analyst | Web search, market scan, news gathering, data collection |
| **David** | Simulation Engineer | Runs MiroFish swarm intelligence (thousands of AI agents predict) |
| **Vex** | Quality Auditor | Validates predictions, catches bad logic, blocks flawed reasoning |
| **Elira** | Decision Maker | Coordinates team, makes final call, talks to you |
| **Steven** | Executor | Places trades (if enabled), tracks positions, manages exits |

**+ MiroFish:** Swarm intelligence engine (simulates crowd behavior to predict outcomes)

---

## 🎨 Two Modes

### **Mode 1: Prediction Only** (Default)
```bash
ELIRA_MODE=predict
```
- Get predictions with confidence scores
- No trading, just insights
- Free (except API costs ~$0.01/prediction)

**Example:**
```
You: "Will Bitcoin hit $100K by June?"
Elira: "68% likely YES (based on swarm simulation of 1000 trader agents)"
```

### **Mode 2: Auto-Trade** (Optional)
```bash
ELIRA_MODE=trade
TRADING_MODE=paper  # or 'live' for real money
```
- Elira auto-executes trades on her predictions
- Paper trading (safe) or real money (requires broker API)
- Confidence-based position sizing

**Example:**
```
You: "Will Bitcoin hit $100K by June?"
Elira: "68% YES. Current odds: 2.4x payout. Placing $25 bet (tier 1)."
```

---

## 📊 Dashboard

**Live pipeline visualization at:** http://localhost:3000

```bash
cd ~/Desktop/quantjellyfish-dashboard
npm install
npm run dev
```

**Features:**
- Real-time agent status
- MiroFish swarm embed
- Activity log (last 50 events)
- Position tracker

---

## 🏆 Performance

**Paper Trading Results (200+ predictions):**
- Overall accuracy: **65%**
- High-confidence (≥80%): **75%**
- Cost per prediction: **$0.015**
- Beat market baseline: **+12%**

**Latest test run:**
- Market: "Will CPI rise more than 0.6% in March 2026?"
- MiroFish result: 80% YES
- Vex verdict: FAIL (semantic drift detected)
- Result: Correctly blocked deployment ✅

---

## 🔧 Configuration

**Environment variables (.env):**
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Trading mode
TRADING_MODE=paper  # paper or live
ELIRA_MODE=predict  # predict or trade

# Optional
PINECONE_API_KEY=...
KALSHI_API_KEY_ID=...
MIROFISH_URL=http://localhost:5001
```

**Adjust confidence thresholds:**
- `elira.py` line 106: `confidence >= 0.70` (60% for fast testing)
- `david.py` line 106: `min_runs=3` (1 for fast testing)

---

## 🚀 Architecture

**5-agent pipeline:**
```
Alba (Research) 
  ↓
David (MiroFish Simulation)
  ↓
Vex (Adversarial Audit)
  ↓
Elira (Orchestration)
  ↓
Steven (Execution)
```

**Elira's 6-gate validation:**
1. Confidence ≥70%
2. Vex verdict = PASS/PASS-WITH-WARNINGS
3. Calendar = CLEAR
4. Liquidity >$500
5. No single-actor override
6. Alba uncertainty ≠ HIGH

**Capital tiers:**
- Tier 1: $25 (60-79% confidence)
- Tier 2: $50 (80-89% confidence)
- Tier 3: $100 (≥90% + Vex HIGH verdict)

---

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Agent Details](docs/AGENTS.md)
- [MiroFish Integration](docs/MIROFISH.md)
- [Dashboard Setup](docs/DASHBOARD.md)
- [Custom Use Cases](docs/CUSTOM_USE_CASES.md)

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

**Areas we need help:**
- New market integrations (sports, forex, futures)
- Agent optimization
- Cost reduction strategies
- Alternative swarm implementations

---

## 📝 License

MIT License - see [LICENSE](LICENSE)

---

## 🔗 Links

- **Framework:** [github.com/jellyforex/askelira](https://github.com/jellyforex/askelira)
- **Marketing:** [github.com/jellyforex/askeliramarketing](https://github.com/jellyforex/askeliramarketing)
- **Website:** [askelira.com](https://askelira.com)

---

**Built with 🧠 by [@jellyforex](https://github.com/jellyforex)**
