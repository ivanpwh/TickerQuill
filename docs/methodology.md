# Methodology

How every number on the dashboard is produced. The split of responsibilities is deliberate:

- **Whisper** turns speech into text (imperfect).
- **The LLM** reads the transcript and fills in a form: which stocks, stance, reasons, price levels, risks. It is told to record only what was said and to leave anything unstated as `null`.
- **The app** (`report.py`) does all calculations from that form and the transcript. No figure on the dashboard is computed by the AI.

All formulas below are implemented in [`report.py`](../report.py).

## What the LLM is asked to return

A single JSON object:

```json
{
  "summary": "2-4 sentences",
  "market_sentiment": "BULLISH | BEARISH | NEUTRAL | MIXED",
  "market_outlook": "speaker's view of the market / IHSG",
  "stocks": [{
    "ticker": "BBCA", "name": "...", "spoken_as": ["BCA"],
    "stance": "BUY | HOLD | SELL | WATCH | AVOID",
    "reason": "...", "expectation": "...",
    "levels": {"entry": "9.000", "target": "10.000", "stop_loss": "8.500", "support": null, "resistance": null},
    "speaker_confidence": "HIGH | MEDIUM | LOW",
    "times": ["01:10"], "doubtful": false, "note": null
  }],
  "risks": ["..."],
  "transcript_quality": "..."
}
```

Rules in the prompt: record what the speaker said, never invent tickers/prices/targets; set `doubtful: true` when a ticker or number may be misheard; `spoken_as` records exactly how the stock appears in the transcript (for example ticker MEDC spoken as "MEDCO") so it can be counted; free-text values are written in the language selected in the app; replies must be short (at most 12 stocks, 2-sentence reasons, 5 risks) so they are not cut off.

## Parsing and recovery

The reply is cleaned before use: `<think>…</think>` blocks and Markdown code fences are removed and trailing commas fixed. If the reply was **truncated** mid-way, the parser cuts back to the last complete value and closes the open brackets. The last stock is then marked incomplete and the dashboard shows a red warning. If nothing can be recovered, the raw text is shown in the ANALYSIS tab instead.

Unknown values are normalised: stance outside the five allowed values becomes WATCH; confidence outside HIGH/MEDIUM/LOW is dropped; the text values `null` and `none` are treated as missing; stocks without a ticker are discarded.

## Price parsing

Spoken levels stay as text for display, and are parsed to numbers only for calculations:

| Text | Number | Rule |
|---|---|---|
| `9.000` | 9000 | `.` or `,` followed by exactly three digits is a thousands separator |
| `1,5` | 1.5 | otherwise a single `,` or `.` is a decimal point |
| `Rp 1.200 - 1.250` | 1200 | the first number in a range is used |
| `12` | 12 | plain integer |

Ambiguous strings (several separators that do not form a thousands pattern) are not parsed.

## Mentions and share

For each stock the app counts case-insensitive, whole-word matches in the transcript of the ticker, the company name and every `spoken_as` variant.

```
Mentions = occurrences of ticker / name / spoken-as variants
Share    = Mentions / (all stocks' mentions) × 100
```

Stocks are sorted by mentions, highest first. Mentions measure how much of the video was about a stock, not how good the stock is.

## Tone score

Each stance has a value:

| Stance | Value |
|---|---|
| BUY | +1 |
| WATCH | +0.25 |
| HOLD | 0 |
| SELL | −1 |
| AVOID | −1 |

```
Tone score = Σ (stance value × weight) / Σ weight          weight = max(mentions, 1)
```

The score runs from −1 (very negative) to +1 (very positive). Labels:

| Score | Label |
|---|---|
| ≥ +0.50 | Very positive |
| ≥ +0.15 | Leaning positive |
| between −0.15 and +0.15 | Neutral / mixed |
| ≤ −0.15 | Leaning negative |
| ≤ −0.50 | Very negative |

**Example.** BBCA = BUY mentioned 3×, MEDC = SELL mentioned 1×: (1×3 + (−1)×1) / (3 + 1) = **+0.50** → *Very positive*.

This is separate from the speaker's own overall view (`market_sentiment`), which the LLM reports and the dashboard shows next to the score.

## Plan completeness (0–100)

20 points for each of: buy price stated, sell target stated, loss limit (stop loss) stated, a reason given, and name/numbers **not** flagged as doubtful. It measures how fully the speaker specified a plan, not whether the plan is sound.

## Reward : risk

Computed only when entry, target and stop loss are all present and `stop loss < entry < target`.

```
Potential gain % = (target − entry) / entry × 100
Potential loss % = (entry − stop loss) / entry × 100
Reward:Risk      = (target − entry) / (entry − stop loss)  = gain % / loss %
```

**Example.** Entry 9.000, target 10.000, stop loss 8.500: gain 11.1 %, loss 5.6 %, ratio **2.0**. A ratio of 2 means the upside is twice the downside. When any level is missing or the order is illogical, the card says it cannot be computed.

## Transcript reliability

```
Reliability = round(100 × (1 − doubtful stocks / total stocks))
```

Example: 1 doubtful stock out of 2 → 50 %. It is shown in the stats line under the summary. It reflects only the stocks the LLM flagged; undetected mishearing is not captured.

## Tips

Rules that produce the "Tips for you" list, in order:

1. **Always:** this summarises the speaker's opinions, not facts; compare with your own data.
2. If the reply was truncated: the dashboard may be missing stocks; re-run before relying on it.
3. If any stock is doubtful: replay those parts of the video and confirm names and numbers.
4. If a BUY has no stop loss: decide your own acceptable loss before buying (a common rule of thumb is roughly 5–8 % below the buy price).
5. For each stock with a computable ratio: below **1.5** → upside is small compared with the risk; otherwise → looks reasonable on the stated numbers, but check the numbers were not misheard and the current price is near the buy price.
6. If tone ≥ **+0.50**: beware of FOMO; buying in steps is safer than all at once.
7. If tone ≤ **−0.15**: review your plan if you hold these stocks, but do not panic-sell over a single video.
8. **Always:** do not put all funds in one stock (typical guidance 5–10 % per stock, only money you can afford to see fall); advice in videos goes stale quickly, so check the date and the latest price; consult a licensed adviser for large decisions.

If no stock was detected, the tips say so and suggest a fuller transcript or a larger Whisper model.

The 5–8 % and 5–10 % figures are general rules of thumb shown for orientation, not recommendations.

## Limitations

- Every number comes from what was said in the video, not from market data. The app never checks real prices, company performance, or whether the speaker's earlier predictions came true.
- ASR errors on tickers and numbers are the main source of wrong output. Flags help but cannot catch everything.
- The LLM can mislabel a stance or attach a level to the wrong stock. Treat the dashboard as an index into the video and verify at the listed timestamps.
- Mention counts depend on the spelling variants the LLM lists; a stock spoken in a way not listed may be undercounted.
