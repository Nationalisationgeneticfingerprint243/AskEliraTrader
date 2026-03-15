"""
Alba — Research Analyst
Steps: 1 (market scan), 2 (calendar check), 3 (seed file), 4 (sim prompt), 9 (daily monitor)

Uses Claude claude-sonnet-4-6 with web_search_20250305 tool.
"""

import json
import logging
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import anthropic
from typing import Optional, Tuple, List

from models import CalendarEvent, Market, Position

# Pipeline status tracker for dashboard
try:
    from utils.pipeline_status import update_status, log_message
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from utils.pipeline_status import update_status, log_message
    except Exception:
        # Fallback if dashboard not set up
        def update_status(*args, **kwargs): pass
        def log_message(*args, **kwargs): pass

# Long-term Pinecone memory (non-fatal if unavailable)
try:
    from pinecone_memory import memory as _mem
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from pinecone_memory import memory as _mem
    except Exception:
        _mem = None

# Kalshi live data client (non-fatal if unavailable)
try:
    from kalshi_client import kalshi as _kalshi, KalshiError
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from kalshi_client import kalshi as _kalshi, KalshiError
    except Exception:
        _kalshi = None
        KalshiError = Exception

# Polymarket live data client (non-fatal if unavailable)
try:
    from polymarket_client import polymarket as _polymarket
except ImportError:
    try:
        from polymarket_client import polymarket as _polymarket
    except Exception:
        _polymarket = None

log = logging.getLogger("alba")

SEEDS_DIR = Path(__file__).parent.parent / "data" / "seeds"
SEEDS_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "claude-haiku-4-5-20251001"  # Haiku for web search — lower tokens, higher rate limits
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

SYSTEM_MARKET_SCAN = """You are Alba, a Research Analyst for a prediction market trading operation.
Your job: find the single best binary YES/NO market on Polymarket or Kalshi that looks mispriced today.

Qualifying criteria:
- Liquidity likely > $500 (major markets always qualify — Fed, elections, macro events)
- Resolves within 14 days from today
- Real-world evidence suggests the market may be mispriced by ≥5%
- NOT resolving on a single unpredictable actor (one tweet = disqualify)

Priority categories: macroeconomic events (Fed, CPI, jobs), political/regulatory decisions,
geopolitical deadlines, corporate events.
Hard block: sports, entertainment, crypto price-level markets.

IMPORTANT — you MUST always pick and commit to one market. You will not have access to
live order-book prices. Use the best price estimate you can find from news/search results.
If you only have an approximate price, use it and note the approximation in why_mispriced.
The downstream audit (Vex) will verify exact prices before any money moves.
Only return no_market if you genuinely cannot find ANY qualifying market category at all.

Return ONLY valid JSON matching this exact schema:
{
  "question": "exact contract question",
  "platform": "Polymarket" or "Kalshi",
  "yes_price": 0.XX,
  "resolution_date": "YYYY-MM-DD",
  "resolution_criteria": "best available contract language or description",
  "liquidity": 1000.0,
  "why_mispriced": "explanation — note if price is estimated",
  "uncertainty": "LOW" or "MEDIUM" or "HIGH"
}

If truly no qualifying market category exists, return: {"no_market": true, "reason": "..."}
"""

SYSTEM_CALENDAR = """You are Alba, Research Analyst. Check the economic and political calendar for high-impact events
that could flip a binary prediction market before its resolution date.

Return ONLY valid JSON:
{
  "events": [
    {"date": "YYYY-MM-DD", "event": "event name", "impact": "HIGH|MEDIUM|LOW", "could_flip": true|false}
  ],
  "verdict": "CLEAR" or "FLAGGED",
  "verdict_reason": "brief explanation"
}
"""

SYSTEM_SEED = """You are Alba, Research Analyst. Compile a structured seed file for MiroFish simulation.
Find 6-8 high-quality sources. Prioritize: government/institutional > news wire > financial analysis > forum.
All sources should be as recent as possible (prefer <72 hours).

Return ONLY valid JSON:
{
  "sources": [
    {
      "url": "...",
      "summary": "2-3 sentence summary of key facts",
      "date": "YYYY-MM-DD",
      "type": "News|Institutional|Government|Forum"
    }
  ],
  "key_facts_yes": ["fact 1", "fact 2"],
  "key_facts_no": ["fact 1", "fact 2"],
  "sentiment": "Bullish YES|Bearish YES|Contested",
  "main_uncertainty": "what could flip this"
}
"""

SYSTEM_SIM_PROMPT = """You are Alba, Research Analyst. Write the exact simulation prompt for MiroFish Box 02.

Rules:
- 3-5 sentences max
- Start with context (key actors and their positions)
- State the binary prediction question clearly
- Ask MiroFish to simulate public opinion, expert analysts, and key stakeholders
- End with: "Provide a probability estimate for YES."
- Natural language only — no bullet points, no headers

Return ONLY the plain text prompt string, nothing else.
"""

SYSTEM_MONITOR = """You are Alba, Research Analyst. Check whether an open prediction market position's
simulation thesis is still valid given today's news.

Return ONLY valid JSON:
{
  "premise_valid": true|false,
  "new_development": "description or null",
  "sentiment_shift": "Same|Reversed|Uncertain",
  "action": "HOLD|FLAG_TO_ORB|SIMULATE_AGAIN|EXIT_NOW",
  "action_reason": "brief explanation"
}
"""


def _claude_with_search(system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Call Claude with web search enabled. Returns the final text response.

    web_search_20250305 is server-executed: the API handles search automatically
    and returns stop_reason="end_turn" with the final answer. We loop only to
    handle the rare case where multiple search rounds are needed, passing the
    assistant turn back each time WITHOUT fabricating tool results.
    """
    client = anthropic.Anthropic(max_retries=0)  # we handle retries ourselves
    messages = [{"role": "user", "content": user}]

    for _ in range(6):  # max turns
        # Rate-limit retry: wait 75s on 429 before retrying (per-minute window)
        retry_waits = [90, 180, 300, 300]  # waits before retries 1-4
        for attempt in range(5):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=max_tokens,
                    system=system,
                    tools=[WEB_SEARCH_TOOL],
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                if attempt < len(retry_waits):
                    wait = retry_waits[attempt]
                    log.warning(f"[Claude] Rate limit hit — waiting {wait}s before retry {attempt+1}/{len(retry_waits)}...")
                    time.sleep(wait)
                else:
                    raise

        # Extract text from ANY block that has a .text attribute
        text_parts = []
        has_tool_use = False
        for block in response.content:
            if hasattr(block, "text") and block.text and block.text.strip():
                text_parts.append(block.text.strip())
            if getattr(block, "type", "") == "tool_use":
                has_tool_use = True

        if text_parts:
            combined = "\n".join(text_parts)
            log.debug(f"[Claude] response text ({len(combined)} chars): {combined[:200]}")
            return combined

        if response.stop_reason == "end_turn":
            # No text in end_turn — log content types for debugging
            types = [getattr(b, "type", type(b).__name__) for b in response.content]
            log.warning(f"[Claude] end_turn with no text. Block types: {types}")
            return ""

        if has_tool_use:
            # Server-side tool use: append assistant turn, continue without tool_result
            messages.append({"role": "assistant", "content": response.content})
            # Send a nudge to get the final text answer
            messages.append({"role": "user", "content": [
                {"type": "text", "text": "Please now provide your final JSON answer based on the search results."}
            ]})
            continue

        break

    return ""


def _parse_json(text: str) -> dict:
    """
    Extract and parse the first valid JSON object from a Claude response.
    Handles markdown fences, leading prose, and multiple JSON objects.
    """
    if not text or not text.strip():
        raise ValueError("Empty response from Claude — cannot parse JSON")

    # Strip markdown fences
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find all top-level JSON objects using a brace-counting scan
    candidates = []
    i = 0
    while i < len(cleaned):
        if cleaned[i] == "{":
            depth = 0
            for j in range(i, len(cleaned)):
                if cleaned[j] == "{":
                    depth += 1
                elif cleaned[j] == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(cleaned[i:j + 1])
                        i = j
                        break
        i += 1

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON found in response.\nText snippet: {cleaned[:400]}")


# ------------------------------------------------------------------ #
#  Step 1 — Market Scan                                               #
# ------------------------------------------------------------------ #

def scan_markets(today: str) -> Optional[Market]:
    """
    Step 1: Search Polymarket/Kalshi for the best mispriced binary market today.
    Prepends live Kalshi market data as context before Claude's web-search scan.
    Returns Market or None if nothing qualifies.
    """
    log.info("[Step 1] Alba scanning markets...")
    update_status('alba-scan', 'Searching Polymarket and Kalshi for mispriced markets')
    log_message('🔍 Alba: Starting market scan...')

    # Pull live market data from both Polymarket and Kalshi to give Claude real prices
    live_context_parts = []

    if _polymarket:
        try:
            poly_ctx = _polymarket.top_markets_context(limit=20)
            if poly_ctx:
                live_context_parts.append(poly_ctx)
                log.info("[Step 1] Polymarket live context injected (top 20 by liquidity).")
        except Exception as _e:
            log.warning(f"[Step 1] Polymarket context failed (non-fatal): {_e}")

    if _kalshi:
        try:
            kalshi_live = _kalshi.get_active_markets(limit=30)
            if kalshi_live:
                lines = [f"LIVE KALSHI MACRO MARKETS ({len(kalshi_live)} open, sorted by open interest):"]
                for m in kalshi_live[:20]:
                    lines.append(
                        f"  [{m['ticker']}] {m['title']} | "
                        f"YES={m['yes_price']:.0%} | "
                        f"OI={m['open_interest']:,.0f} contracts | closes {m['resolution_date']}"
                    )
                live_context_parts.append("\n".join(lines))
                log.info(f"[Step 1] Kalshi live context injected ({len(kalshi_live)} macro markets).")
        except KalshiError as _e:
            log.warning(f"[Step 1] Kalshi market fetch failed (non-fatal): {_e}")

    user = (
        f"Today is {today}. Search Polymarket and Kalshi for the best mispriced binary "
        "YES/NO market. Search: 'Polymarket trending markets', 'Kalshi most active contracts', "
        "'Polymarket biggest volume today'. Find and return one top opportunity meeting ALL criteria."
    )
    if live_context_parts:
        user = "\n\n".join(live_context_parts) + "\n\n" + user

    raw = _claude_with_search(SYSTEM_MARKET_SCAN, user)
    data = _parse_json(raw)

    if data.get("no_market"):
        log.info(f"[Step 1] No qualifying market found: {data.get('reason')}")
        return None

    market = Market(
        question=data["question"],
        platform=data["platform"],
        yes_price=float(data["yes_price"]),
        resolution_date=data["resolution_date"],
        resolution_criteria=data["resolution_criteria"],
        liquidity=float(data["liquidity"]),
        why_mispriced=data["why_mispriced"],
        uncertainty=data["uncertainty"],
    )
    log.info(f"[Step 1] TOP OPPORTUNITY: {market.question} | YES={market.yes_price:.0%} | {market.platform}")

    # Recall similar past markets from long-term memory for context
    try:
        if _mem:
            past = _mem.recall_research(market.question, top_k=3)
            if past:
                log.info(f"[Step 1] Pinecone: {len(past)} similar past markets found:")
                for h in past:
                    log.info(f"  └─ {h.get('market')} ({h.get('date')}) score={h.get('score', 0):.2f}")
    except Exception as _exc:
        log.warning(f"[Step 1] Pinecone recall failed (non-fatal): {_exc}")

    return market


# ------------------------------------------------------------------ #
#  Step 2 — Economic Calendar                                         #
# ------------------------------------------------------------------ #

def check_calendar(market: Market, today: str) -> Tuple[List[CalendarEvent], str]:
    """
    Step 2: Check for high-impact events between today and resolution date.
    Returns (events, verdict) where verdict is "CLEAR" or "FLAGGED".
    """
    log.info("[Step 2] Alba checking economic calendar...")
    update_status('alba-calendar', f'Checking economic calendar for: {market.question[:50]}...')
    log_message(f'📅 Alba: Checking calendar for {market.platform} market')
    user = (
        f"Today is {today}. Market resolves: {market.resolution_date}. "
        f"Market question: {market.question}\n\n"
        "Search: 'economic calendar high impact events', 'Fed speech schedule', "
        "'major political deadlines'. Flag any HIGH impact events between today and resolution date "
        "that could flip this market."
    )
    raw = _claude_with_search(SYSTEM_CALENDAR, user)
    data = _parse_json(raw)

    events = [
        CalendarEvent(
            date=e["date"],
            event=e["event"],
            impact=e["impact"],
            could_flip=e["could_flip"],
        )
        for e in data.get("events", [])
    ]
    verdict = data.get("verdict", "CLEAR")
    log.info(f"[Step 2] Calendar verdict: {verdict} | {len(events)} events flagged")
    return events, verdict


# ------------------------------------------------------------------ #
#  Step 3 — Build Seed File                                           #
# ------------------------------------------------------------------ #

def build_seed_file(market: Market, today: str) -> Path:
    """
    Step 3: Research 6-8 sources, compile structured seed .txt file.
    Returns path to saved file.
    """
    log.info("[Step 3] Alba building seed file...")
    update_status('alba-seed', 'Researching web sources and building seed file')
    log_message(f'📚 Alba: Gathering 6-8 sources for {market.question[:40]}...')
    user = (
        f"Today is {today}. Market: {market.question}\n"
        f"Resolution: {market.resolution_date}\n"
        f"Resolution criteria: {market.resolution_criteria}\n\n"
        "Search for 6-8 high-quality recent sources. "
        f"Search: '{market.question} news', key actors latest update, official statements."
    )
    raw = _claude_with_search(SYSTEM_SEED, user, max_tokens=6000)
    data = _parse_json(raw)

    # Fetch live market data to enrich the seed file with real prices/orderbook
    live_blocks = []

    if market.platform == "Polymarket" and _polymarket:
        try:
            candidates = _polymarket.find_market(market.question, limit=100)
            if candidates:
                best = candidates[0]
                market.yes_price = best["yes_price"]
                live_blocks.append(_polymarket.build_market_context(best))
                log.info(f"[Step 3] Polymarket live data: YES={market.yes_price:.0%}, liq=${best['liquidity_usd']:,.0f}")
        except Exception as _e:
            log.warning(f"[Step 3] Polymarket seed enrichment failed (non-fatal): {_e}")

    if market.platform == "Kalshi" and _kalshi:
        try:
            candidates = _kalshi.find_market(market.question, limit=200)
            if candidates:
                ticker = candidates[0]["ticker"]
                live_blocks.append(_kalshi.build_market_context(ticker))
                market.yes_price = candidates[0]["yes_price"]
                log.info(f"[Step 3] Kalshi live data: {ticker} YES={market.yes_price:.0%}")
        except KalshiError as _e:
            log.warning(f"[Step 3] Kalshi seed enrichment failed (non-fatal): {_e}")

    # Build the .txt content MiroFish will consume
    lines = [
        "---BEGIN SEED FILE---",
        f"MARKET QUESTION: {market.question}",
        f"RESOLUTION DATE: {market.resolution_date}",
        f"RESOLUTION CRITERIA: {market.resolution_criteria}",
        f"CURRENT YES PRICE: {market.yes_price:.0%}",
        "",
    ]

    # Inject live market data right after the header for MiroFish to use
    for block in live_blocks:
        lines += [block, ""]

    for i, src in enumerate(data.get("sources", []), 1):
        lines += [
            f"SOURCE {i}: {src.get('url', 'N/A')}",
            f"SUMMARY: {src.get('summary', '')}",
            f"DATE: {src.get('date', '')}",
            f"TYPE: {src.get('type', '')}",
            "",
        ]
    lines.append("KEY FACTS SUPPORTING YES:")
    for f_yes in data.get("key_facts_yes", []):
        lines.append(f"- {f_yes}")
    lines.append("")
    lines.append("KEY FACTS SUPPORTING NO:")
    for f_no in data.get("key_facts_no", []):
        lines.append(f"- {f_no}")
    lines += [
        "",
        f"CURRENT SENTIMENT: {data.get('sentiment', 'Contested')}",
        f"MAIN UNCERTAINTY: {data.get('main_uncertainty', '')}",
        "---END SEED FILE---",
    ]

    seed_path = SEEDS_DIR / f"{today}-{market.slug}.txt"
    seed_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"[Step 3] Seed file saved: {seed_path}")

    # Store seed in Pinecone long-term memory
    try:
        if _mem:
            tags = [market.platform.lower(), market.uncertainty.lower()]
            _mem.store_research(
                market_slug=market.slug,
                date=today,
                content="\n".join(lines),
                tags=tags,
                source="alba-seed",
                agent="Alba",
            )
    except Exception as _exc:
        log.warning(f"[Step 3] Pinecone store_research failed (non-fatal): {_exc}")

    return seed_path


# ------------------------------------------------------------------ #
#  Step 4 — Write Simulation Prompt                                   #
# ------------------------------------------------------------------ #

def write_simulation_prompt(market: Market, seed_text: str) -> str:
    """
    Step 4: Write the natural-language prompt for MiroFish Box 02.
    Returns prompt string.
    """
    log.info("[Step 4] Alba writing simulation prompt...")
    user = (
        f"Market question: {market.question}\n"
        f"Resolution criteria: {market.resolution_criteria}\n"
        f"Resolution date: {market.resolution_date}\n\n"
        f"Seed summary:\n{seed_text[:2000]}\n\n"
        "Write the MiroFish simulation prompt now."
    )
    # No web search needed for this step
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_SIM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    prompt = response.content[0].text.strip()
    log.info(f"[Step 4] Simulation prompt written ({len(prompt)} chars)")
    return prompt


# ------------------------------------------------------------------ #
#  Step 9 — Daily Position Monitor                                    #
# ------------------------------------------------------------------ #

def monitor_position(position: Position, today: str) -> dict:
    """
    Step 9: Check if the simulation premise is still valid for an open position.
    Returns dict with action: HOLD | FLAG_TO_ORB | SIMULATE_AGAIN | EXIT_NOW
    """
    log.info(f"[Step 9] Alba monitoring: {position.market[:60]}...")
    user = (
        f"Today is {today}. Open position: LONG {position.direction} @ ${position.entry_price:.2f}\n"
        f"Market: {position.market}\n"
        f"Resolution: {position.resolution_date}\n\n"
        "Search for any news that would break the simulation thesis. "
        f"Search: '{position.market[:80]} news today', key resolution actor update."
    )
    raw = _claude_with_search(SYSTEM_MONITOR, user)
    result = _parse_json(raw)
    log.info(f"[Step 9] Monitor result: action={result.get('action')} | premise_valid={result.get('premise_valid')}")
    return result
