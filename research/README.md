# Research: strategies we tried and dropped

Before the futures-curve strategy in [`../strategy/`](../strategy/), we tested eight other ideas. None held up out of sample. They are kept here, unchanged, so anyone can see what was tried and why it was dropped.

| Folder | Ideas | Outcome |
|---|---|---|
| [`xle-flow-and-pairs/`](xle-flow-and-pairs/) | Seven variants: trading ahead of XLE's quarterly rebalance, index selling of buyback stocks, three kinds of pairs trading, the bounce-back after XLE's forced sells, and XLE volatility scaling with a CVX/XOP pair | All "not supported" on the held-out period. Full log in `attempts-log.md`; frozen rules and fingerprints in that folder's `output/frozen_fingerprints.txt`. |
| [`crack-spread/`](crack-spread/) | The 3-2-1 crack spread for timing refiners against producers | The crack spread explains same-day returns (t about 6) but predicts nothing. A 60-day trend rule looked profitable but depended on the look-back and was really a static long-refiner bet. See `RESULTS.md`. |

`xle-flow-and-pairs/` was moved here as one folder, so every path inside it, including those in `frozen_fingerprints.txt`, is still correct relative to that folder, and no frozen file was edited. Its own README describes the folder as the repo root; read its paths as relative to `research/xle-flow-and-pairs/`.
