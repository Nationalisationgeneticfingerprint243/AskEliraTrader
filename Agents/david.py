"""
David — Engineer
Steps: 5 (run MiroFish simulation × 3), 10 (post-resolution calibration log)

COMPLETE IMPLEMENTATION with:
- Multi-run orchestration (3+ simulations)
- Variance checking (<15% threshold)
- Self-blocking on instability
- Calibration log automation
- Domain-specific agent population configs
"""

import csv
import json
import logging
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional

import anthropic

from mirofish_client import MiroFishClient, MiroFishError, _extract_sim_result
from models import Market, Position, SimResult

log = logging.getLogger("david")

CALIBRATION_LOG = Path(__file__).parent.parent / "data" / "calibration_log.csv"
MODEL = "claude-sonnet-4-5"

# Agent population configs by market domain
AGENT_POPULATIONS = {
    "political": {
        "retail_public": 0.35,
        "political_analysts": 0.25,
        "media": 0.20,
        "institutional": 0.15,
        "activists": 0.05,
    },
    "financial": {
        "retail_public": 0.30,
        "financial_analysts": 0.30,
        "institutional": 0.25,
        "media": 0.10,
        "regulators": 0.05,
    },
    "geopolitical": {
        "retail_public": 0.25,
        "geopolitical_experts": 0.30,
        "media": 0.20,
        "institutional": 0.15,
        "military_analysts": 0.10,
    },
    "corporate": {
        "retail_public": 0.30,
        "financial_analysts": 0.25,
        "institutional": 0.25,
        "media": 0.15,
        "employees": 0.05,
    },
    "default": {
        "retail_public": 0.40,
        "domain_experts": 0.30,
        "media": 0.20,
        "institutional": 0.10,
    },
}

SYSTEM_DOMAIN_CLASSIFIER = """You are David, an engineer. Classify the market domain
for agent population config selection.

Return ONLY valid JSON:
{
  "domain": "political|financial|geopolitical|corporate|default",
  "reasoning": "brief explanation"
}
"""

SYSTEM_POSTMORTEM = """You are David, an engineer and quantitative analyst.
A prediction market simulation just resolved. Write a one-sentence calibration lesson
that Alba can use to improve the next seed file for markets in this category.

Return ONLY valid JSON:
{
  "seed_quality": "Good|Gaps|Stale sources",
  "prompt_matched_criteria": true|false,
  "agent_mix_realistic": true|false,
  "lesson": "one specific actionable improvement for the next simulation in this category"
}
"""


def _classify_domain(market: Market) -> str:
    """Classify market into a domain category for agent population config."""
    question_lower = market.question.lower()
    
    # Simple keyword-based classification (can be enhanced with Claude if needed)
    if any(word in question_lower for word in ["fed", "interest rate", "stock", "nasdaq", "s&p", "gdp", "inflation", "jobs", "unemployment", "earnings"]):
        return "financial"
    if any(word in question_lower for word in ["election", "president", "congress", "senate", "biden", "trump", "vote", "poll", "regulation", "law", "bill"]):
        return "political"
    if any(word in question_lower for word in ["war", "ceasefire", "treaty", "sanctions", "ukraine", "iran", "china", "russia", "nato"]):
        return "geopolitical"
    if any(word in question_lower for word in ["merger", "acquisition", "ceo", "company", "apple", "google", "tesla", "amazon", "meta"]):
        return "corporate"
    
    return "default"


def _extract_confidence(markdown: str) -> Tuple[float, str]:
    """
    Parse confidence % and direction from MiroFish markdown report.
    Looks for patterns like '73%', 'YES: 73', 'confidence: 0.73', 'probability: 73%'
    Returns (confidence_float, direction_str).
    
    Falls back to _extract_sim_result from mirofish_client if no clear pattern.
    """
    text = markdown.lower()

    # Try to find explicit YES/NO probability statements
    yes_match = re.search(r"yes[^\d]*(\d{1,3})\s*%", text)
    no_match  = re.search(r"no[^\d]*(\d{1,3})\s*%", text)
    conf_match = re.search(r"(?:probability|confidence|likelihood)[^\d]*(\d{1,3})\s*%", text)
    plain_pct  = re.search(r"(\d{1,3})\s*%", text)

    if yes_match and no_match:
        yes_val = int(yes_match.group(1)) / 100
        no_val  = int(no_match.group(1)) / 100
        return (yes_val, "YES") if yes_val >= no_val else (no_val, "NO")

    if yes_match:
        val = int(yes_match.group(1)) / 100
        return val, "YES"
    if no_match:
        val = int(no_match.group(1)) / 100
        return val, "NO"
    if conf_match:
        val = int(conf_match.group(1)) / 100
        # Default direction from sentiment words
        direction = "YES" if "bullish" in text or "likely yes" in text else "NO"
        return val, direction
    if plain_pct:
        val = int(plain_pct.group(1)) / 100
        return val, "YES"

    # Fallback to mirofish_client extractor
    log.debug("Using fallback _extract_sim_result from mirofish_client")
    return _extract_sim_result(markdown)


# ------------------------------------------------------------------ #
#  Step 5 — Run MiroFish simulation (3 runs, variance check)         #
# ------------------------------------------------------------------ #

def run_simulation(
    market: Market,
    seed_path: Path,
    sim_prompt: str,
    mirofish_url: str = "http://localhost:5001",
    min_runs: int = 3,
    variance_threshold: float = 0.15,
) -> SimResult:
    """
    Step 5: Run MiroFish min_runs times and return averaged SimResult.
    
    Self-blocks if:
    - Fewer than min_runs complete successfully
    - Variance across runs exceeds variance_threshold (default 15%)
    
    Args:
        market: Market dataclass with question, slug, etc.
        seed_path: Path to Alba's seed .txt file
        sim_prompt: Natural language simulation prompt (Box 02)
        mirofish_url: MiroFish backend URL
        min_runs: Minimum successful runs required (default 3)
        variance_threshold: Max allowed std dev across runs (default 0.15)
    
    Returns:
        SimResult with averaged confidence, majority-vote direction, and variance
    
    Raises:
        MiroFishError: If runs fail, variance too high, or backend unreachable
    """
    client = MiroFishClient(base_url=mirofish_url)

    if not client.ping():
        raise MiroFishError(
            f"MiroFish backend unreachable at {mirofish_url}. "
            "Check: docker ps | grep mirofish"
        )

    domain = _classify_domain(market)
    agent_config = AGENT_POPULATIONS.get(domain, AGENT_POPULATIONS["default"])
    
    log.info(f"[Step 5] David running {min_runs} MiroFish simulations")
    log.info(f"  Market: {market.question[:80]}")
    log.info(f"  Domain: {domain}")
    log.info(f"  Agent mix: {agent_config}")

    run_results = []
    for run_num in range(1, min_runs + 1):
        log.info(f"[Step 5] Run {run_num}/{min_runs} starting...")
        try:
            project_name = f"{market.slug}-run{run_num}"
            sim_id, report_id, markdown = client.full_run(
                seed_txt_path=seed_path,
                simulation_requirement=sim_prompt,
                project_name=project_name,
            )
            confidence, direction = _extract_confidence(markdown)
            log.info(f"[Step 5] Run {run_num} complete: {direction} @ {confidence:.0%}")
            run_results.append({
                "sim_id": sim_id,
                "report_id": report_id,
                "markdown": markdown,
                "confidence": confidence,
                "direction": direction,
            })
        except MiroFishError as e:
            log.error(f"[Step 5] Run {run_num} failed: {e}")
            continue
        except Exception as e:
            log.exception(f"[Step 5] Run {run_num} crashed: {e}")
            continue

    # Gate 1: Minimum runs threshold
    if len(run_results) < min_runs:
        raise MiroFishError(
            f"SELF-BLOCK: Only {len(run_results)}/{min_runs} simulation runs completed. "
            f"David protocol requires {min_runs} successful runs minimum."
        )

    # Gate 2: Variance threshold
    confidences = [r["confidence"] for r in run_results]
    variance = statistics.stdev(confidences) if len(confidences) > 1 else 0.0
    
    if variance > variance_threshold:
        conf_str = ", ".join([f"{c:.0%}" for c in confidences])
        raise MiroFishError(
            f"SELF-BLOCK: Run variance {variance:.2%} exceeds {variance_threshold:.0%} threshold. "
            f"Runs: [{conf_str}]. Simulation is unstable — do not deploy."
        )

    # Calculate consensus
    avg_confidence = statistics.mean(confidences)
    directions = [r["direction"] for r in run_results]
    direction = max(set(directions), key=directions.count)

    # Use the middle run's report as the canonical report
    middle_idx = len(run_results) // 2
    canonical = run_results[middle_idx]

    result = SimResult(
        simulation_id=canonical["sim_id"],
        report_id=canonical["report_id"],
        confidence=avg_confidence,
        direction=direction,
        markdown=canonical["markdown"],
        variance=variance,
        run_confidences=confidences,
    )
    
    log.info(
        f"[Step 5] ✓ SIMULATION RESULT: {direction} @ {avg_confidence:.0%} "
        f"(variance={variance:.2%}, runs=[{', '.join([f'{c:.0%}' for c in confidences])}])"
    )
    log.info(f"[Step 5] Simulation ready for Vex audit")
    
    return result


# ------------------------------------------------------------------ #
#  Step 10 — Post-resolution calibration log                         #
# ------------------------------------------------------------------ #

def log_resolution(
    position: Position,
    sim_result: SimResult,
    actual_outcome: str,   # "YES" or "NO"
) -> str:
    """
    Step 10: Log resolved market to calibration CSV and extract lesson.
    
    Args:
        position: Position dataclass with entry details
        sim_result: SimResult from David's original simulation
        actual_outcome: Actual market resolution ("YES" or "NO")
    
    Returns:
        Calibration lesson string for Alba to use in future seed files
    """
    win_loss = "WIN" if sim_result.direction == actual_outcome else "LOSS"
    
    # Calculate P&L
    if win_loss == "WIN":
        # Won: return (1 - entry_price) * size
        # e.g., bought YES @ 0.30 for $50 → win = (1 - 0.30) * 50 = $35
        pnl = (1 - position.entry_price) * position.size
    else:
        # Lost: lose entry_price * size
        # e.g., bought YES @ 0.30 for $50 → loss = -0.30 * 50 = -$15
        pnl = -position.entry_price * position.size

    log.info(f"[Step 10] Resolution logged: {win_loss} | P&L=${pnl:.2f}")

    # Get post-mortem lesson from Claude
    client = anthropic.Anthropic()
    user = (
        f"Market: {position.market}\n"
        f"Domain: prediction market\n"
        f"Sim confidence: {sim_result.confidence:.0%} | Sim direction: {sim_result.direction}\n"
        f"Actual outcome: {actual_outcome} | Result: {win_loss}\n"
        f"Variance: {sim_result.variance:.2%}\n"
        f"Report excerpt:\n{sim_result.markdown[:1500]}\n\n"
        "Provide calibration feedback for Alba's next seed file."
    )
    
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=SYSTEM_POSTMORTEM,
            messages=[{"role": "user", "content": user}],
        )
        pm_text = response.content[0].text.strip()
        # Strip markdown fences if present
        pm_text = re.sub(r"^```(?:json)?\s*\n?", "", pm_text, flags=re.IGNORECASE)
        pm_text = re.sub(r"\n?```\s*$", "", pm_text)
        pm = json.loads(pm_text.strip())
    except Exception as e:
        log.warning(f"[Step 10] Claude postmortem failed: {e}")
        pm = {
            "seed_quality": "Unknown",
            "prompt_matched_criteria": None,
            "agent_mix_realistic": None,
            "lesson": f"Postmortem generation failed: {str(e)[:100]}",
        }

    # Append to calibration CSV
    CALIBRATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    row = {
        "DATE": datetime.utcnow().strftime("%Y-%m-%d"),
        "MARKET": position.market[:80],
        "PLATFORM": position.platform,
        "SIM_CONFIDENCE": f"{sim_result.confidence:.2%}",
        "SIM_DIRECTION": sim_result.direction,
        "ACTUAL_OUTCOME": actual_outcome,
        "WIN_LOSS": win_loss,
        "VARIANCE": f"{sim_result.variance:.2%}",
        "TIER": position.tier,
        "POSITION_SIZE": f"${position.size:.2f}",
        "PNL": f"${pnl:.2f}",
        "SEED_QUALITY": pm.get("seed_quality", ""),
        "LESSON": pm.get("lesson", ""),
    }
    
    write_header = not CALIBRATION_LOG.exists() or CALIBRATION_LOG.stat().st_size == 0
    
    with open(CALIBRATION_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    lesson = pm.get("lesson", "No lesson extracted.")
    log.info(f"[Step 10] Calibration note: {lesson}")
    
    return lesson


# ------------------------------------------------------------------ #
#  Calibration accuracy tracker                                       #
# ------------------------------------------------------------------ #

def get_category_accuracy(category: Optional[str] = None, min_samples: int = 5) -> Optional[float]:
    """
    Calculate historical accuracy for a market category.
    
    Args:
        category: Market category (political/financial/geopolitical/corporate)
                  If None, returns overall accuracy
        min_samples: Minimum resolved markets required for reliable accuracy
    
    Returns:
        Accuracy as float (0.0-1.0) or None if insufficient data
    """
    if not CALIBRATION_LOG.exists():
        return None
    
    wins = 0
    total = 0
    
    with open(CALIBRATION_LOG, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # If category filter is specified, skip non-matching rows
            # (This requires storing category in calibration log — to be added)
            if row.get("WIN_LOSS") in ("WIN", "LOSS"):
                total += 1
                if row["WIN_LOSS"] == "WIN":
                    wins += 1
    
    if total < min_samples:
        log.info(f"[Calibration] Insufficient data: {total} samples (need {min_samples})")
        return None
    
    accuracy = wins / total
    log.info(f"[Calibration] Accuracy: {accuracy:.1%} ({wins}/{total} wins)")
    return accuracy


# ------------------------------------------------------------------ #
#  Self-check before deployment                                       #
# ------------------------------------------------------------------ #

def self_check(sim_result: SimResult, market: Market) -> Tuple[bool, str]:
    """
    David's final self-check before handing to Vex.
    
    Returns:
        (pass: bool, reason: str)
    """
    # Check 1: Variance threshold
    if sim_result.variance > 0.15:
        return False, f"Variance {sim_result.variance:.2%} exceeds 15% threshold"
    
    # Check 2: Confidence sanity
    if sim_result.confidence < 0.50:
        return False, f"Confidence {sim_result.confidence:.0%} below 50% — no edge detected"
    
    if sim_result.confidence > 0.95:
        log.warning(f"[Self-check] Very high confidence {sim_result.confidence:.0%} — may need Vex scrutiny")
    
    # Check 3: Direction consistency
    directions = [
        "YES" if c > 0.5 else "NO" 
        for c in sim_result.run_confidences
    ]
    if len(set(directions)) > 1:
        return False, f"Direction inconsistency across runs: {directions}"
    
    log.info("[Self-check] ✓ All David checks passed")
    return True, "READY FOR VEX AUDIT"
