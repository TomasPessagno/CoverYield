/**
 * Plain-language explanations shown behind every (?) in the app.
 * Written for someone new to options; symbols are kept to one short definition.
 */
export const GLOSSARY = {
  ticker: "The stock or ETF.",
  price: "The stock's current price.",
  expiry:
    "The date the option expires. After it, the buyer can no longer buy your shares at the strike.",
  dte: "Days to expiry: calendar days until the option expires.",
  strike:
    "The price the buyer can buy your shares at. In brackets: how far it is from today's stock price.",
  strikePlain: "The price the buyer can buy your shares at.",
  dist: "How far the stock must rise to reach the strike: (strike − price) ÷ price.",
  bid: "The most a buyer will pay for this call right now, per share. Selling at the bid is the premium you collect.",
  mid: "Halfway between bid and ask. A limit order near it may get filled at a better price than the bid.",
  ask: "The lowest price a seller is asking, per share. It's what you'd pay to buy the call back.",
  spread: "Ask − bid: the cost of trading in and out. Smaller means a fairer, more active market.",
  breakeven:
    "Stock price minus the premium. If the stock falls below this, the whole position (shares + call) loses money.",
  static:
    "Bid ÷ stock price: your return over the contract's life if the stock doesn't move. Real cash, not a projection.",
  annual:
    "Static return × 365 ÷ days to expiry, so contracts with different expiries can be compared. A projection, not a guarantee.",
  perDay:
    "Theta (Θ = ∂C/∂t): how much value the call loses each day. You sold it, so that's what you earn per day per contract (100 shares) if nothing else changes.",
  assign:
    "Probability in the money: the Black-Scholes chance, N(d₂), that the stock ends above the strike at expiry, so your shares get called away. Early assignment (usually just before a dividend) isn't included. Click a row for the full breakdown.",
  iv: "Implied volatility: how much the market expects the stock to move over a year. It's the volatility at which Black-Scholes gives this option's market price (solved from the bid/ask mid). Higher IV means bigger premiums and bigger moves. — means no volatility explains the quote (e.g. no bid).",
  volume: "Contracts traded today. More means an active market.",
  oi: "Open interest: how many of these contracts are currently open. More means it's easier to trade at a fair price.",
  contract: "Open this exact contract on Yahoo Finance.",
  score:
    "Opportunity Score, 0–100: a weighted blend of yield, assignment risk, liquidity and volatility. Hover a score for its components.",
} as const;
