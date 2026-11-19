# Feature 014a: why the 120-line evaluation regressed

The author is holding the feature: on the 120-line evaluation the majority top-1 fell from 84 to 77 and wrong auto-accepts rose from 10 to 12, so SC-004 failed. This report separates the causes. Everything is read from the logged rows and history entries of the runs, with no model call, except the ablation of section 2 (one paid run of both sets). The twelve chapters' rulings are the same in both stores (the rebuild reused all 74,044 and added none in those chapters). The tables are rendered by `tests/eval/regression_014a.py`, which first checks that its routes reproduce every history entry it uses; the product's routing functions recompute every route. Section 5, added after the author's decisions of 2026-11-19, measures rule (a), the vague rule and option (c): under rule (a) SC-004 passes.

- **Baseline**: 120-line iteration 12, coolant iteration 1. The store of the twelve chapters (74,044 rulings); the vote over every chapter, as before 014a.
- **After-run**: iterations 13 and 2. The rebuilt store of every chapter (123,531 rulings); the vote within the candidates' chapters, as 014a ships.
- **Ablation**: iterations 19 and 7. The rebuilt store; the vote over every chapter (`--vote-scope all`, eval only).
- All three: Gemini 2.5 Flash with reasoning off, query expansion off, customs wording off, three runs, threshold 85, ask floor 50. The eval's route has the precedent override off; the app ships with it on, so section 2 shows both.

**Headline** (120 lines, precedent override off):

- **Store effect** (baseline → ablation, the same unscoped vote): majority top-1 84 → 76; wrong auto-accepts 10 → 9; auto-accepted per run 68 / 70 / 67 → 63 / 63 / 62.
- **Filter effect** (the unscoped vote replayed on the after-run's rows → the after-run: the same model answers): majority top-1 77 → 77 (with the override off the vote never changes a top-1); auto-accepted per run 63 / 63 / 62 → 65 / 65 / 65: 3 more wrong (IEBTIIENEN004-2024-BTI208 in every run) and 4 more right ones (IEBTIIENEN004-2025-BTI173 in every run, IEBTIIENEN004-2026-BTI118 once).
- **Noise** (the ablation against the replay: the same store, prompt and vote, other model answers): majority top-1 76 against 77; top-1 per run 77 / 77 / 76 against 76 / 77 / 77; auto-accepted and wrong auto-accepted per run identical.
- So the fall of the majority from 84 to 77 is the new store (through the candidate proposal, section 1) with a line of noise, and the rise of wrong auto-accepts from 10 to 12 is the chapter filter (+3, BTI208) less a line of baseline noise (−1, BTI284). With the override on: majority 87 → 79 (store) and 80 → 80 (filter); wrong auto-accepts 10 → 9 → 12.

## 1. What changed between the baseline and the after-run (no model call)

Every line whose majority outcome or auto-accepts changed, on both sets, with its cause in one of three categories: the **new store** (the rulings of the newly indexed chapters, or the rebuilt index, changed the candidate proposal, the codes the rulings propose before the model ranks, or the vote); the **chapter-filtered vote** (the scoped vote routes a row otherwise than the unscoped vote would on the same row); **run noise** (the runs of the baseline or of the after-run disagree among themselves). The rules, in the order checked, are `causes()` in the script. The window: the 12 rulings the proposal read, the same 12 the unscoped vote takes its 5 voters from; the evidence is the first after-run's.

### 1.1 The 120-line set

| Line | Expected | Change | Baseline top-1 (routes) | After-run top-1 (routes) | Cause | Evidence |
|---|---|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI245 | 3926.90 | right auto 3 → 0 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 3926.90 / 3926.90 / 3926.90 (review / review / review) | new store (vote) | baseline vote 3926.90 3, 8486.90 1, 6307.90 1; after-run's scoped vote (39, 63, 90) 9019.20 2, 3926.90 1, 9021.31 1, 9018.90 1; unscoped 3926.90 1, 2818.10 1, 9021.31 1, 8207.90 1, 9019.20 1; voters of new chapters 2818.10 (0.581), 9021.31 (0.560), 8207.90 (0.546), 9019.20 (0.544) |
| IEBTIIENEN004-2025-BTI258 | 3926.90 | right auto 3 → 0 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 3926.90 / 3926.90 / 3926.90 (review / review / review) | new store (vote) | baseline vote 3926.90 3, 3924.10 1, 3920.99 1; after-run's scoped vote (39, 90) 9019.20 2, 9033.00 2, 3926.90 1; unscoped 9019.20 2, 9033.00 2, 3926.90 1; voters of new chapters 9019.20 (0.581), 9033.00 (0.572), 9033.00 (0.564), 9019.20 (0.547) |
| IEBTIIENEN004-2025-BTI463 | 3926.90 | majority right → wrong | 3926.90 / 3926.90 / 3926.90 (review / review / review) | 4016.99 / 4016.99 / 4016.99 (review / review / review) | new store (proposal) | proposed 3926.90, 8538.90, 3919.10 → 4016.99, 3926.90, 3919.10; new-chapter rulings in the window: 4016.99 ×2 (0.615), 8708.50 (0.605) |
| IEBTIIENEN004-2024-BTI141 | 3926.90 | majority right → wrong; right auto 3 → 0 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 9111.80 / 9111.80 / 9111.80 (review / review / review) | new store (proposal) | proposed 3926.90, 4202.92, 4202.32 → 9113.90, 7616.99, 7007.19; new-chapter rulings in the window: 9113.90 ×4 (0.650), 7616.99 (0.672), 7007.19 (0.671), 9102.12 (0.640); twelve-chapter rulings the rebuilt index now returns: LUBTILU700000-2024-BTI40 8517.62 (0.652); expected code shown to the model 3/3 → 0/3 |
| IEBTIIENEN004-2023-BTI572 | 3923.10 | majority right → wrong | 3923.10 / 3923.10 / 3923.10 (review / review / review) | 8609.00 / 8609.00 / 8609.00 (review / review / review) | new store (proposal) | proposed 3923.10, 9617.00, 6307.90 → 3923.10, 8609.00, 3824.99; new-chapter rulings in the window: 8609.00 ×2 (0.751), 6806.90 ×2 (0.679), 3824.99 (0.663) |
| IEBTIIENEN004-2024-BTI284 | 4202.12 | majority stays wrong, another code; wrong auto 1 → 0 | 4202.32 / 4202.92 / 4202.32 (review / auto / review) | 4202.92 / 4202.92 / 4202.92 (review / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| FRBTIFR-BTI-2025-02100 | 4203.29 | majority right → wrong; right auto 2 → 0 | 4203.29 / 4203.29 / 6116.10 (auto / auto / review) | 6116.10 / 6116.10 / 6116.10 (review / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| IEBTIIENEN004-2024-BTI208 | 6109.90 | majority right → wrong; wrong auto 0 → 3 | 6109.90 / 6109.90 / 6109.90 (review / review / review) | 6114.30 / 6114.30 / 6114.30 (auto / auto / auto) | new store (proposal); chapter-filtered vote | proposed 6114.30, 6109.90, 6212.10 → 6114.30, 6212.10, 6212.90; new-chapter rulings in the window: 5806.31 (0.672); twelve-chapter rulings the rebuilt index now returns: DEBTI36199/24-1 6307.90 (0.644); expected code shown to the model 3/3 → 0/3; scoped vote (61): 6114.30 3, 6110.30 1, 6109.90 1 → auto; unscoped vote on the same row: 6212.10 2, 5806.31 1, 6114.30 1, 6212.90 1 → review |
| IEBTIIENEN004-2026-BTI23 | 6307.90 | majority right → wrong; right auto 3 → 0 | 6307.90 / 6307.90 / 6307.90 (auto / auto / auto) | 5808.90 / 5808.90 / 5808.90 (review / review / review) | new store (proposal) | proposed 6307.90, 3926.40, 6117.80 → 6307.90, 5806.32, 5808.90; new-chapter rulings in the window: 5806.32 ×3 (0.690), 5808.90 (0.706), 4823.90 (0.678), 5806.40 (0.675) |
| IEBTIIENEN004-2024-BTI7 | 6307.90 | majority stays wrong, another code | 4602.90 / 4602.19 / 4602.19 (review / review / review) | 4602.90 / 4602.90 / 4602.90 (review / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| IEBTIIENEN004-2024-BTI5 | 6307.90 | majority stays wrong, another code | 4602.19 / 4602.19 / 4602.19 (review / review / review) | 4602.90 / 4602.90 / 4602.90 (review / review / review) | new store (proposal) | proposed 6307.90, 6304.91, 9505.10 → 6307.90, 4602.19, 4602.90; new-chapter rulings in the window: 4602.19 ×3 (0.610), 4602.90 ×2 (0.602), 4823.90 (0.600); twelve-chapter rulings the rebuilt index now returns: FRBTIFR-BTI-2025-00696 4202.92 (0.606) |
| IEBTIIENEN004-2024-BTI8 | 6307.90 | right auto 1 → 0 | 6307.90 / 4602.90 / 4602.90 (auto / review / review) | 4602.90 / 4602.90 / 4602.90 (review / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| XIBTI505060394 | 7326.90 | majority stays wrong, another code | 8303.00 / 8303.00 / 8303.00 (review / review / review) | 8303.00 / 7310.10 / 7310.10 (review / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| IEBTIIENEN004-2025-BTI301 | 7325.99 | majority right → wrong | 7325.99 / 7325.99 / 7325.99 (review / review / review) | 9026.90 / 9026.90 / 9026.90 (review / review / review) | new store (proposal) | proposed 7325.99, 8538.90, 8481.90 → 9026.90, 7325.99, 8416.90; new-chapter rulings in the window: 9026.90 ×2 (0.649), 9027.10 (0.601), 9028.90 (0.597), 9027.90 (0.596); expected code shown to the model 3/3 → 2/3 |
| IEBTIIENEN004-2025-BTI293 | 8424.90 | majority stays wrong, another code | 8481.90 / 8481.90 / 8481.90 (review / review / review) | 9018.39 / 9018.39 / 9018.39 (review / review / review) | new store (proposal) | proposed 8481.80, 8481.90, 8422.90 → 9018.32, 9018.39, 7304.41; new-chapter rulings in the window: 9018.32 ×4 (0.587), 9018.39 ×3 (0.695), 7507.12 (0.580); twelve-chapter rulings the rebuilt index now returns: IEBTIIENEN004-2024-BTI258 7304.41 (0.611) |
| IEBTIIENEN004-2026-BTI118 | 9503.00 | right auto 2 → 3 | 9503.00 / 9503.00 / 9503.00 (auto / auto / review) | 9503.00 / 9503.00 / 9503.00 (auto / auto / auto) | chapter-filtered vote | scoped vote (63, 95): 9503.00 3, 6307.90 1, 9506.99 1 → auto; unscoped vote on the same row: 9503.00 2, 6307.90 1, 9506.99 1, 9401.79 1 → review |
| IEBTIIENEN004-2026-BTI71 | 9619.00 | majority right → wrong; right auto 2 → 1 | 6108.21 / 9619.00 / 9619.00 (review / auto / auto) | 9619.00 / 6108.21 / 6108.21 (auto / review / review) | run noise | the runs of a command disagree (top-1 or route per run in the columns) |
| IEBTIIENEN004-2026-BTI222 | 9609.10 | majority wrong → right; right auto 0 → 3 | 9609.90 / 9609.90 / 9609.90 (review / review / review) | 9609.10 / 9609.10 / 9609.10 (auto / auto / auto) | new store (proposal) | proposed 9609.10, 9609.90, 9608.10 → 9609.10, 4903.00, 9609.90; new-chapter rulings in the window: 4903.00 ×3 (0.686), 4820.10 (0.671) |

### 1.2 The coolant set

| Line | Expected | Change | Baseline top-1 (routes) | After-run top-1 (routes) | Cause | Evidence |
|---|---|---|---|---|---|---|
| coolant-1 | 2710.19 | majority wrong → right | 3819.00 / 3820.00 / 3820.00 (ask / ask / ask) | 2710.19 / 2710.19 / 2710.19 (review / review / review) | new store (proposal) | proposed 8473.30, 8419.90, 8409.99 → 3824.99, 2710.19, 3402.50; new-chapter rulings in the window: 3824.99 ×3 (0.569), 2710.19 ×3 (0.533), 3402.50 ×2 (0.523), 2710.12 (0.536), 3819.00 (0.521), 3811.21 (0.514), 8708.99 (0.510); expected code shown to the model 0/3 → 3/3 |
| coolant-4 | 3403.99 | right auto 0 → 3 | 3403.99 / 3403.99 / 3403.99 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (auto / auto / auto) | chapter-filtered vote | scoped vote (34, 38): 3403.99 3, 3403.19 1, 3824.99 1 → auto; unscoped vote on the same row: 2710.19 2, 2710.20 1, 3403.99 1, 2710.12 1 → review |
| coolant-5 | 2710.19 | right auto 0 → 3 | 2710.19 / 2710.19 / 2710.19 (review / review / review) | 2710.19 / 2710.19 / 2710.19 (auto / auto / auto) | new store (vote) | baseline vote 3907.29 2, 8419.90 1, 7310.10 1, 8431.49 1; after-run's scoped vote (27) 2710.19 4, 2710.20 1; unscoped 2710.19 4, 2710.20 1; voters of new chapters 2710.20 (0.686), 2710.19 (0.684), 2710.19 (0.684), 2710.19 (0.682), 2710.19 (0.679) |
| coolant-6 | 3403.99 | majority wrong → right | 3403.19 / 3403.19 / 3403.19 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (review / review / review) | new store (proposal) | proposed 8419.89, 8421.29, 8419.90 → 2710.19, 3403.99, 3403.19; new-chapter rulings in the window: 2710.19 ×5 (0.614), 3403.99 ×2 (0.541), 3403.19 ×2 (0.518), 2710.20 (0.631), 2710.12 (0.568), 3811.21 (0.505); expected code shown to the model 0/3 → 3/3 |
| coolant-7 | 3403.99 | right auto 0 → 3 | 3403.99 / 3403.99 / 3403.99 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (auto / auto / auto) | chapter-filtered vote | scoped vote (34, 38): 3403.99 4, 3403.19 1 → auto; unscoped vote on the same row: 2710.19 3, 2710.20 1, 2710.12 1 → review |
| coolant-8 | ask_shipper | majority right → wrong | 3820.00 / 3820.00 / 3820.00 (ask / ask / ask) | 3820.00 / 3820.00 / 3820.00 (review / review / review) | new store (proposal) | proposed 8419.89, 8419.90, 8413.30 → 3824.99, 3402.50, 8708.99; new-chapter rulings in the window: 3824.99 ×5 (0.608), 3402.50 ×2 (0.550), 8708.99 ×2 (0.532), 8708.91 (0.523), 3820.00 (0.516) |

### 1.3 Totals per cause

| Set | Cause | Majority right → wrong | Majority wrong → right | Right auto-accepts (3 runs) | Wrong auto-accepts (3 runs) |
|---|---|---|---|---|---|
| 120 lines | new store (proposal) | 6 | 1 | -3 | +0 |
| 120 lines | new store (vote) | 0 | 0 | -6 | +0 |
| 120 lines | chapter-filtered vote | 0 | 0 | +1 | +3 |
| 120 lines | run noise | 2 | 0 | -4 | -1 |
| coolant | new store (proposal) | 1 | 2 | +0 | +0 |
| coolant | new store (vote) | 0 | 0 | +3 | +0 |
| coolant | chapter-filtered vote | 0 | 0 | +6 | +0 |

On the 120 lines the majority fell by 7: the new store's proposal cost 6 lines and won 1, noise cost 2. In five of the six lines the model chose a code that rulings of a newly indexed chapter proposed, or one next to it (4016.99; 9111.80 beside the proposed 9113.90; 8609.00; 5808.90; 9026.90); in BTI208 rulings of the new store displaced the right code from the proposal (1.4). The new rulings in the vote cost 6 right auto-accepts (BTI245, BTI258: rulings of chapter 90, newly indexed, now vote, and for BTI245 also of chapters 28 and 82; as a chapter-90 code is among the model's candidates, the scoped vote searches chapter 90 too, so the filter does not keep them out). The filter added 3 wrong (BTI208) and 1 right (BTI118) auto-accept among the changed lines; with BTI173, whose auto-accepts it keeps against new rulings that would otherwise vote it to review, it adds 4 right ones (section 2). On the coolant set the new store's proposal brought the right code to coolant-1 and coolant-6 (2710.19 and 3403.99, proposed by rulings of chapters 27 and 34) and moved the plain 冷却液 from ask to review (section 4); the new rulings in the vote auto-accept coolant-5, and the filter coolant-4 and coolant-7.

### 1.4 IEBTIIENEN004-2024-BTI208

**The line**: "T-Shirt Type Garment for Unisex / Undergarment for wear by a person who has a spinal brace / Made from knitted Fabric 96% Polyester and 4% Lycra". Expected HS-6 6109.90 (CN-8 61099020).

| Run | Baseline top 3 (confidence) | After-run top 3 (confidence) | Ablation top 3 (confidence) |
|---|---|---|---|
| 1 | 6109.90 (95), 6114.30 (80), 6108.22 (30) | 6114.30 (95), 6107.19 (60), 6108.22 (55) | 6114.30 (95), 6107.19 (60), 6108.22 (55) |
| 2 | 6109.90 (95), 6114.30 (80) | 6114.30 (95), 6107.19 (60), 6108.22 (55) | 6114.30 (95), 6107.19 (60), 6108.22 (55) |
| 3 | 6109.90 (95), 6114.30 (80), 6108.22 (30) | 6114.30 (95), 6108.22 (40), 6108.29 (35) | 6114.30 (95), 6107.19 (60), 6108.22 (55) |

**What the rulings proposed** (the codes the precedent proposal added to the candidates, the same in all three runs of each command), and the 12 rulings it read, in RRF order (1 is the line's own ruling, kept out):

| # | Baseline: ruling | HS-6 | Similarity | After-run: ruling | HS-6 | Similarity |
|---|---|---|---|---|---|---|
| 1 | IEBTIIENEN004-2024-BTI208 (own) | 6109.90 | 0.943 | IEBTIIENEN004-2024-BTI208 (own) | 6109.90 | 0.943 |
| 2 | IEBTIIENEN004-2026-BTI74 | 6212.10 | 0.693 | IEBTIIENEN004-2026-BTI74 | 6212.10 | 0.692 |
| 3 | IEBTIIENEN004-2026-BTI75 | 6212.10 | 0.693 | IEBTIIENEN004-2026-BTI75 | 6212.10 | 0.691 |
| 4 | IEBTIIENEN004-2024-BTI51 | 6114.30 | 0.650 | IEBTIIENEN004-2025-BTI81 (new chapter) | 5806.31 | 0.672 |
| 5 | FRBTIFR-BTI-2025-08906 | 6212.90 | 0.647 | IEBTIIENEN004-2024-BTI51 | 6114.30 | 0.650 |
| 6 | DEBTI46152/24-1 | 6212.90 | 0.643 | FRBTIFR-BTI-2025-08906 | 6212.90 | 0.647 |
| 7 | FRBTIFR-BTI-2024-02152 | 6110.30 | 0.642 | DEBTI36199/24-1 | 6307.90 | 0.644 |
| 8 | FRBTIFR-BTI-2024-02075 | 6109.90 | 0.642 | DEBTI46152/24-1 | 6212.90 | 0.643 |
| 9 | FRBTIFR-BTI-2025-02277 | 6114.30 | 0.638 | FRBTIFR-BTI-2024-02152 | 6110.30 | 0.642 |
| 10 | FRBTIFR-BTI-2025-02279 | 6114.30 | 0.638 | FRBTIFR-BTI-2024-02075 | 6109.90 | 0.641 |
| 11 | FRBTIFR-BTI-2025-03241 | 6109.90 | 0.637 | FRBTIFR-BTI-2025-02277 | 6114.30 | 0.638 |
| 12 | SEBTITV-2025-01940 | 6109.90 | 0.637 | FRBTIFR-BTI-2025-02279 | 6114.30 | 0.637 |

Proposed: baseline 6114.30, 6109.90, 6212.10; after-run 6114.30, 6212.10, 6212.90. The expected code was among the subheadings shown to the model in 3/3 baseline runs and 0/3 after-runs.

**The votes on the after-run's rows**:

| Run | Scoped vote: chapters, the 5 voters (HS-6, similarity, country) | Route | Unscoped vote on the same row: the 5 voters | Route |
|---|---|---|---|---|
| 1 | 61: 6114.30 0.650 IE; 6110.30 0.642 FR; 6109.90 0.641 FR; 6114.30 0.638 FR; 6114.30 0.637 FR | auto (6114.30 3, 6110.30 1, 6109.90 1) | 6212.10 0.692 IE; 6212.10 0.691 IE; 5806.31 0.672 IE; 6114.30 0.650 IE; 6212.90 0.647 FR | review (6212.10 2, 5806.31 1, 6114.30 1, 6212.90 1) |
| 2 | 61: 6114.30 0.651 IE; 6110.30 0.644 FR; 6109.90 0.643 FR; 6114.30 0.638 FR; 6114.30 0.638 FR | auto (6114.30 3, 6110.30 1, 6109.90 1) | 6212.10 0.693 IE; 6212.10 0.693 IE; 5806.31 0.673 IE; 6114.30 0.651 IE; 6212.90 0.647 FR | review (6212.10 2, 5806.31 1, 6114.30 1, 6212.90 1) |
| 3 | 61: 6114.30 0.650 IE; 6109.90 0.640 FR; 6110.30 0.639 FR; 6114.30 0.639 FR; 6114.30 0.639 FR | auto (6114.30 3, 6109.90 1, 6110.30 1) | 6212.10 0.692 IE; 6212.10 0.690 IE; 5806.31 0.668 IE; 6114.30 0.650 IE; 6212.90 0.645 FR | review (6212.10 2, 5806.31 1, 6114.30 1, 6212.90 1) |

**Why the top-1 moved from 6109.90 to 6114.30.** No code of a new chapter was proposed, but two rulings the baseline's window did not hold entered the after-run's: IEBTIIENEN004-2025-BTI81 (5806.31, chapter 58, newly indexed) at 4 and DEBTI36199/24-1 (6307.90, chapter 63) at 7. DEBTI36199/24-1 is in both stores with the same text and vector: the twelve-chapter store's approximate index did not return it, the rebuilt index does. Together they pushed two of the three 6109.90 rulings out of the window, so 6109.90 fell from the second proposed code to none, the precedent leg no longer added its subheading, and the model, shown 6114.30 tagged with three rulings and no 6109.90 at all, chose 6114.30 at 95 in every run. The ablation, with the same proposal, chose it too. The evaluation report's label for it, "new-chapter proposals", comes from its rule (the proposed codes differ) but names the wrong mechanism: here the new store displaced the right code; no new-chapter code was proposed.

**Why it is auto-accepted wrong in every after-run.** The model's three candidates are all in chapter 61, so the scoped vote searched chapter 61 only. Its 5 nearest eligible rulings hold 6114.30 three times, a 3-of-5 majority for the model's code: agree, auto-accept. The unscoped vote on the same rows reads two chapter-62 rulings at 6212.10 first, then the new chapter-58 ruling, one 6114.30 and a 6212.90: majority 6212.10 at 2 of 5, review, which is what the ablation's real vote did in all three runs. The filter removed the rulings that disagreed and left a chapter-61 majority for the wrong code. In the baseline the right top-1 was never auto-accepted either: the same unscoped vote tied or disagreed.

### 1.5 Is the evaluation report's replay of the old vote exact?

The column "Old vote's routes" of eval-diff.md replays the vote of before 014a from each after-row's nearest_hits: the 5 nearest eligible rulings at or above 0.40 among the first 12. That is exact when (1) a line has one query vector, so the vote's 12 rulings are one search's (true here: query expansion off, no shipper answer, customs wording off); (2) eligibility and floor are the product's (the logged flag is: not the line's own ruling, valid on the set's date, coded to the nomenclature; no logged hit lies within 1e-5 of the floor); and (3) the first 12 of the logged search (k = 40) are the product's k = 12 search, which an approximate index does not promise. (3) was tested where the logged vote is itself unscoped: the replay equals the logged vote in 358 of 358 baseline rows with candidates (coolant 24 of 24) and, on the rebuilt store, in 360 of 360 ablation rows (coolant 24 of 24). **The replay is exact.** One limit, which does not touch it: the approximate index can miss near rulings in an unfiltered search that a filtered search finds (XIBTI505060394: five 8301.50 rulings at 0.70 found by the scoped search, absent from the 40 nearest). So the scoped vote rebuilt from the 40 logged hits equals the logged one in 355 of 360 rows (2 differ, 3 have fewer than 5 in-chapter rulings among the 40), none of them a row whose route changes. That is also why section 3 does not rebuild the scoped vote on the ablation's rows.

## 2. The ablation: the vote over every chapter on the rebuilt store

`--vote-scope all` (tests/eval/hs6_eval.py, eval only) runs the vote's ruling search without its chapter filter: the vote is the unscoped 5-nearest vote of before 014a, on the same store, prompt and candidate proposal as the after-run. It cost $0.5075 by the key's usage, read once OpenRouter had settled it ($0.4751 right after the runs), and $0.5608 by the evaluation's tallies (120 lines $0.5260, coolant $0.0348; they price tokens from the project's table and run high): within the approved $0.55.

**The 120-line set**:

| Run | Override | Majority top-1 | Top-1 per run | Auto-accepted per run | Wrong auto-accepted per run |
|---|---|---|---|---|---|
| Baseline: 12 chapters, unscoped vote (it. 12) | off | 84/120 | 83 / 84 / 83 | 68 / 70 / 67 | 3 / 4 / 3 (10) |
| Baseline: 12 chapters, unscoped vote (it. 12) | on | 87/120 | 87 / 87 / 87 | 72 / 73 / 71 | 3 / 4 / 3 (10) |
| Ablation: every chapter, unscoped vote (it. 19) | off | 76/120 | 77 / 77 / 76 | 63 / 63 / 62 | 3 / 3 / 3 (9) |
| Ablation: every chapter, unscoped vote (it. 19) | on | 79/120 | 80 / 79 / 79 | 66 / 65 / 65 | 3 / 3 / 3 (9) |
| After-run: every chapter, scoped vote (it. 13) | off | 77/120 | 76 / 77 / 77 | 65 / 65 / 65 | 4 / 4 / 4 (12) |
| After-run: every chapter, scoped vote (it. 13) | on | 80/120 | 79 / 80 / 80 | 68 / 68 / 68 | 4 / 4 / 4 (12) |
| Replay: the unscoped vote on the after-run's rows | off | 77/120 | 76 / 77 / 77 | 63 / 63 / 62 | 3 / 3 / 3 (9) |
| Replay: the unscoped vote on the after-run's rows | on | 80/120 | 79 / 80 / 80 | 66 / 66 / 65 | 3 / 3 / 3 (9) |

**The coolant set**:

| Run | Override | Majority right | Right per run | Auto-accepted per run | Wrong auto-accepted per run |
|---|---|---|---|---|---|
| Baseline: 12 chapters, unscoped vote (it. 1) | off | 6/8 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 (0) |
| Baseline: 12 chapters, unscoped vote (it. 1) | on | 6/8 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 (0) |
| Ablation: every chapter, unscoped vote (it. 7) | off | 6/8 | 7 / 6 / 6 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| Ablation: every chapter, unscoped vote (it. 7) | on | 6/8 | 7 / 6 / 6 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| After-run: every chapter, scoped vote (it. 2) | off | 7/8 | 7 / 7 / 7 | 3 / 3 / 3 | 0 / 0 / 0 (0) |
| After-run: every chapter, scoped vote (it. 2) | on | 7/8 | 7 / 7 / 7 | 3 / 3 / 3 | 0 / 0 / 0 (0) |
| Replay: the unscoped vote on the after-run's rows | off | 7/8 | 7 / 7 / 7 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| Replay: the unscoped vote on the after-run's rows | on | 7/8 | 7 / 7 / 7 | 1 / 1 / 1 | 0 / 0 / 0 (0) |

What the ablation separates:

- **The store effect** is the baseline against the ablation (the same unscoped vote): 84 → 76 majority, wrong auto-accepts 10 → 9, auto-accepted 205 → 188 over three runs; coolant 6 → 6 majority, auto-accepted 0 → 3. The new store costs top-1s through the proposal, and right auto-accepts through rulings that now vote, but no wrong auto-accept.
- **The filter effect** is the ablation against the after-run, and exactly the replay against the after-run (the same answers): auto-accepted 188 → 195, wrong 9 → 12; coolant auto-accepted 3 → 9, wrong 0 → 0. It never changes a top-1 with the override off.
- **Noise** is the ablation against the replay (everything equal but the model's answers): majority 76 against 77, coolant 6 against 7 (coolant-6 is right in one ablation run of three); routes identical per run on the 120 lines.
- The line-level causes of section 1 (the new store's proposal -5 net, noise -2) and the ablation's split (store -8, noise +1) both add up to -7; they differ in how much of the run noise falls on each comparison.

The rows where the filter changes the route (after-run):

| Line | Run | Expected | Top-1 | Scoped vote (chapters) | Route | Unscoped vote, same row | Route |
|---|---|---|---|---|---|---|---|
| IEBTIIENEN004-2024-BTI208 | 1 | 6109.90 | 6114.30 | 6114.30 3, 6110.30 1, 6109.90 1 (61) | auto | 6212.10 (0.692), 6212.10 (0.691), 5806.31 (0.672), 6114.30 (0.650), 6212.90 (0.647) | review |
| IEBTIIENEN004-2025-BTI173 | 1 | 7326.90 | 7326.90 | 7326.90 4, 3926.90 1 (39, 73, 83) | auto | 7326.90 (0.715), 4202.32 (0.694), 7616.99 (0.691), 7326.90 (0.674), 3926.90 (0.650) | review |
| IEBTIIENEN004-2024-BTI208 | 2 | 6109.90 | 6114.30 | 6114.30 3, 6110.30 1, 6109.90 1 (61) | auto | 6212.10 (0.693), 6212.10 (0.693), 5806.31 (0.673), 6114.30 (0.651), 6212.90 (0.647) | review |
| IEBTIIENEN004-2025-BTI173 | 2 | 7326.90 | 7326.90 | 7326.90 4, 3926.90 1 (39, 73, 83) | auto | 7326.90 (0.715), 4202.32 (0.694), 7616.99 (0.691), 7326.90 (0.674), 3926.90 (0.650) | review |
| IEBTIIENEN004-2024-BTI208 | 3 | 6109.90 | 6114.30 | 6114.30 3, 6109.90 1, 6110.30 1 (61) | auto | 6212.10 (0.692), 6212.10 (0.690), 5806.31 (0.668), 6114.30 (0.650), 6212.90 (0.645) | review |
| IEBTIIENEN004-2025-BTI173 | 3 | 7326.90 | 7326.90 | 7326.90 5 (73, 83) | auto | 7326.90 (0.714), 4202.32 (0.692), 7616.99 (0.686), 7326.90 (0.674), 3926.90 (0.648) | review |
| IEBTIIENEN004-2026-BTI118 | 3 | 9503.00 | 9503.00 | 9503.00 3, 6307.90 1, 9506.99 1 (63, 95) | auto | 9503.00 (0.772), 9503.00 (0.687), 6307.90 (0.674), 9506.99 (0.634), 9401.79 (0.633) | review |
| coolant-4 | 1 | 3403.99 | 3403.99 | 3403.99 3, 3403.19 1, 3824.99 1 (34, 38) | auto | 2710.20 (0.617), 3403.99 (0.614), 2710.19 (0.608), 2710.19 (0.606), 2710.12 (0.602) | review |
| coolant-7 | 1 | 3403.99 | 3403.99 | 3403.99 4, 3403.19 1 (34, 38) | auto | 2710.20 (0.649), 2710.19 (0.631), 2710.19 (0.616), 2710.12 (0.615), 2710.19 (0.606) | review |
| coolant-4 | 2 | 3403.99 | 3403.99 | 3403.99 3, 3403.19 1, 3824.99 1 (34, 38) | auto | 2710.20 (0.617), 3403.99 (0.614), 2710.19 (0.608), 2710.19 (0.606), 2710.12 (0.602) | review |
| coolant-7 | 2 | 3403.99 | 3403.99 | 3403.99 4, 3403.19 1 (34, 38) | auto | 2710.20 (0.649), 2710.19 (0.631), 2710.19 (0.616), 2710.12 (0.615), 2710.19 (0.606) | review |
| coolant-4 | 3 | 3403.99 | 3403.99 | 3403.99 3, 3403.19 1, 3824.99 1 (34, 38) | auto | 2710.20 (0.615), 3403.99 (0.613), 2710.19 (0.606), 2710.19 (0.606), 2710.12 (0.600) | review |
| coolant-7 | 3 | 3403.99 | 3403.99 | 3403.99 4, 3403.19 1 (34, 38) | auto | 2710.20 (0.651), 2710.19 (0.635), 2710.12 (0.620), 2710.19 (0.620), 2710.19 (0.606) | review |

## 3. Fix proposals (not implemented)

A fact frames (a) and (b): with the current rules, when the unfiltered vote agrees with the model's top code, the filtered vote agrees too. The rulings the unfiltered vote reads in the top code's chapter are also the nearest of that chapter, so they are among the filtered vote's 5; the filter only removes rulings of other chapters, which can only disagree. So the filter can turn a review into an auto-accept (BTI208 wrongly; BTI173, BTI118, coolant-4 and coolant-7 rightly) and never the reverse.

**(a) The filtered vote may support a review, never trigger an auto-accept on its own.** The unfiltered vote decides as before 014a; an auto-accept also needs the filtered vote, when it has voters, to auto-accept the same code. Guardrail: the gate stays code-computed agreement with the 5 nearest eligible rulings (Principle I), the rule of constitution 1.5.0 word for word; the filtered vote adds a stricter check. No amendment. By the fact above it equals the unscoped gate: after-run, wrong auto-accepts 12 → 9 and auto-accepted 195 → 188 (4 right ones lost: BTI173, BTI118); coolant auto-accepted 9 → 3 (coolant-4 and coolant-7 back to review); majority top-1 unchanged. On the ablation's rows it leaves the unscoped vote's routes as they are, 188 auto-accepted with 9 wrong, which is the same estimate on other model answers. The filtered vote keeps its use in block 3 (the captions).

**(b) An auto-accept needs both votes to agree.** As (a), and a line with only one vote goes to review; with neither, the confidence decides as today. Same guardrail, no amendment. It differs from (a) only when exactly one vote has no voter, which no row of either run had, so its effect is (a)'s.

**(c) The candidate proposal limited to the chapters of the nomenclature search's top subheadings** (option B of clarification 1). Guardrail: none touched; Principle IV's pipeline is unchanged (the proposal is part of retrieval), so no amendment, but it reverses the author's clarification 1 (the proposal searches every chapter) and needs the spec changed. Effect: needs a paid run (about $0.56 for both sets, as the ablation). The proposal changes the candidates and the precedent tags in the ranking prompt, so the model's choice cannot be replayed, and the rows do not log the nomenclature search's subheadings. Bounds: it can win back at most the 6 lines the new store's proposal cost (5 through new-chapter codes, 1 through displacement) and may lose what new-chapter proposals won (BTI222; coolant-1 and coolant-6, whose right codes rulings of chapters 27 and 34 proposed).

**(d1) The filtered vote with a share of 0.8** (4 of 5). Guardrail: HS6_VOTE_SHARE is a named constant whose value Principle I leaves to the spec, so no amendment, but the spec and its boundary tests change. After-run: wrong auto-accepts 12 → 6, auto-accepted 195 → 174, so 15 right auto-accepts lost; coolant auto-accepted 9 → 6. It halves the wrong auto-accepts at a high price.

**(d2) Stricter proposals from newly indexed chapters** (a similarity floor, or two rulings in the window). Guardrail: none touched, no amendment; a retrieval rule in the spec. Effect: needs a paid run, as (c). Offline, the rulings behind the proposals that changed a majority show that neither rule separates harm from help: the harmful proposals sit at 0.61 to 0.75 similarity, the helpful ones at 0.53 to 0.69 (the coolant lines are short, so their similarities are low).

| Set | Line | Effect of the proposal | New-chapter codes proposed: best similarity, rulings in the window | Kept at a 0.65 floor | Kept with 2 rulings or more |
|---|---|---|---|---|---|
| 120 lines | IEBTIIENEN004-2025-BTI463 | right → wrong | 4016.99: 0.615, 2 | none | 4016.99 |
| 120 lines | IEBTIIENEN004-2024-BTI141 | right → wrong | 9113.90: 0.650, 4; 7616.99: 0.672, 1; 7007.19: 0.671, 1 | 7616.99, 7007.19 | 9113.90 |
| 120 lines | IEBTIIENEN004-2023-BTI572 | right → wrong | 8609.00: 0.751, 2; 3824.99: 0.663, 1 | 8609.00, 3824.99 | 8609.00 |
| 120 lines | IEBTIIENEN004-2024-BTI208 | right → wrong | none (displacement) | none | none |
| 120 lines | IEBTIIENEN004-2026-BTI23 | right → wrong | 5806.32: 0.675, 2; 5808.90: 0.706, 1 | 5806.32, 5808.90 | 5806.32 |
| 120 lines | IEBTIIENEN004-2024-BTI5 | wrong → another wrong code | 4602.19: 0.610, 3; 4602.90: 0.602, 2 | none | 4602.19, 4602.90 |
| 120 lines | IEBTIIENEN004-2025-BTI301 | right → wrong | 9026.90: 0.649, 2 | none | 9026.90 |
| 120 lines | IEBTIIENEN004-2025-BTI293 | wrong → another wrong code | 9018.32: 0.587, 4; 9018.39: 0.695, 3 | 9018.39 | 9018.32, 9018.39 |
| 120 lines | IEBTIIENEN004-2026-BTI222 | wrong → right | 4903.00: 0.686, 3 | 4903.00 | 4903.00 |
| coolant | coolant-1 | wrong → right | 3824.99: 0.569, 3; 2710.19: 0.533, 3; 3402.50: 0.523, 2 | none | 3824.99, 2710.19, 3402.50 |
| coolant | coolant-6 | wrong → right | 2710.19: 0.614, 5; 3403.99: 0.541, 2; 3403.19: 0.518, 2 | none | 2710.19, 3403.99, 3403.19 |
| coolant | coolant-8 | right → wrong | 3824.99: 0.608, 5; 3402.50: 0.550, 2; 8708.99: 0.532, 2 | none | 3824.99, 3402.50, 8708.99 |

The effects at a glance (offline; (c) and (d2) need a paid run). Today's rule and (d1) need the scoped vote, which the ablation does not log and which cannot be rebuilt reliably from its 40 logged hits: rebuilt, it would add 6 wrong auto-accepts that the real filtered search does not give (BTI132 with no in-chapter ruling among the 40, BTI284 and BTI463 with other rulings). So they are estimated on the after-run's rows, where both votes are exact:

| Rule | Set | Rows | Majority, override off / on | Auto-accepted per run, off | Wrong auto-accepted, off | Auto-accepted per run, on | Wrong auto-accepted, on |
|---|---|---|---|---|---|---|---|
| Today (the scoped vote) | 120 lines | after | 77 / 80 of 120 | 65 / 65 / 65 | 4 / 4 / 4 (12) | 68 / 68 / 68 | 4 / 4 / 4 (12) |
| (a) filtered vote may only send to review | 120 lines | after | 77 / 80 of 120 | 63 / 63 / 62 | 3 / 3 / 3 (9) | 66 / 66 / 65 | 3 / 3 / 3 (9) |
| (b) both votes must agree | 120 lines | after | 77 / 80 of 120 | 63 / 63 / 62 | 3 / 3 / 3 (9) | 66 / 66 / 65 | 3 / 3 / 3 (9) |
| (d1) filtered vote, share 0.8 | 120 lines | after | 77 / 80 of 120 | 58 / 58 / 58 | 2 / 2 / 2 (6) | 61 / 61 / 61 | 2 / 2 / 2 (6) |
| (a) filtered vote may only send to review | 120 lines | ablation | 76 / 79 of 120 | 63 / 63 / 62 | 3 / 3 / 3 (9) | 66 / 65 / 65 | 3 / 3 / 3 (9) |
| (b) both votes must agree | 120 lines | ablation | 76 / 79 of 120 | 63 / 63 / 62 | 3 / 3 / 3 (9) | 66 / 65 / 65 | 3 / 3 / 3 (9) |
| Today (the scoped vote) | coolant | after | 7 / 7 of 8 | 3 / 3 / 3 | 0 / 0 / 0 (0) | 3 / 3 / 3 | 0 / 0 / 0 (0) |
| (a) filtered vote may only send to review | coolant | after | 7 / 7 of 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (b) both votes must agree | coolant | after | 7 / 7 of 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (d1) filtered vote, share 0.8 | coolant | after | 7 / 7 of 8 | 2 / 2 / 2 | 0 / 0 / 0 (0) | 2 / 2 / 2 | 0 / 0 / 0 (0) |
| (a) filtered vote may only send to review | coolant | ablation | 6 / 6 of 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (b) both votes must agree | coolant | ablation | 6 / 6 of 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) | 1 / 1 / 1 | 0 / 0 / 0 (0) |

## 4. Plain 冷却液: a vague line always asks the shipper

**The rule**: a line flagged vague goes to ask the shipper, whatever its confidence. Today it goes to ask the shipper only below the ask floor of 50, and to review otherwise; a vague line's confidence is capped at 59 in code, so only 50 to 59 reach review.

**Constitution and spec**: Principle I already forbids auto-accepting a flagged line (kept, and the flagged-line lock is unchanged). Principle III requires that, when a description is flagged, the assistant tell the clerk what to ask the shipper rather than present a confident code; the rule follows it more strictly. The ask floor is not in the constitution: it is feature 001's FR-020 and the author's clarification of 2026-10-14 (below 50 ask, otherwise review). So no amendment, but a spec change to feature 001 (FR-020, its clarification and its assumption) for the author, and the 12-line sample's routes and the tests that pin them change.

**The lines flagged vague** (routes and confidence per run):

| Set | Line | Expected | Baseline routes (confidence) | After-run | Ablation | With the rule |
|---|---|---|---|---|---|---|
| 120 lines | IEBTIIENEN004-2023-BTI572 | 3923.10 | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| 120 lines | IEBTIIENEN004-2025-BTI249 | 8421.39 | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| 120 lines | IEBTIIENEN004-2026-BTI124 | 8431.49 | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| 120 lines | IEBTIIENEN004-2026-BTI105 | 8474.90 | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| 120 lines | XIBTI505068566 | 8504.40 | review (59) / review (59) / review (59) | review (59) / review (50) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| coolant | coolant-1 | 2710.19 | ask (40) / ask (40) / ask (40) | review (59) / review (59) / review (59) | review (50) / review (59) / review (59) | ask / ask / ask |
| coolant | coolant-2 | ask_shipper | ask (40) / ask (40) / ask (40) | ask (40) / ask (40) / ask (40) | ask (40) / ask (40) / ask (40) | ask / ask / ask |
| coolant | coolant-3 | 3403.99 | review (50) / review (50) / review (50) | review (59) / review (59) / review (59) | review (59) / review (59) / review (59) | ask / ask / ask |
| coolant | coolant-8 | ask_shipper | ask (40) / ask (40) / ask (40) | review (50) / review (50) / review (50) | review (50) / review (50) / review (50) | ask / ask / ask |

**The effect**:

| Set | Run | Override | Majority today | With the rule | Vague rows to review today | With the rule |
|---|---|---|---|---|---|---|
| 120 lines | baseline | off | 84/120 | 84/120 | 15 | 0 |
| 120 lines | baseline | on | 87/120 | 87/120 | 15 | 0 |
| 120 lines | after | off | 77/120 | 77/120 | 15 | 0 |
| 120 lines | after | on | 80/120 | 80/120 | 15 | 0 |
| 120 lines | ablation | off | 76/120 | 76/120 | 15 | 0 |
| 120 lines | ablation | on | 79/120 | 79/120 | 15 | 0 |
| coolant | baseline | off | 6/8 | 6/8 | 3 | 0 |
| coolant | baseline | on | 6/8 | 6/8 | 3 | 0 |
| coolant | after | off | 7/8 | 8/8 | 9 | 0 |
| coolant | after | on | 7/8 | 8/8 | 9 | 0 |
| coolant | ablation | off | 6/8 | 7/8 | 9 | 0 |
| coolant | ablation | on | 6/8 | 7/8 | 9 | 0 |

On the coolant set the rule makes the plain 冷却液 right in every run: majority after-run 7 → 8, ablation 6 → 7, baseline 6 (it asked already). On the 120 lines it moves the 5 vague lines' 15 rows per command from review to ask the shipper and changes no top-1 and no auto-accept. The trade-off: coolant-1 and coolant-3 are flagged vague but have a code the model gets right (2710.19 and 3403.99); the rule would ask the shipper about them too.

## 5. Rule (a) and option (c): the measurement of 2026-11-19

The author's decisions of 2026-11-19 (spec, clarifications of that day): the app now routes by **rule (a)**, the unfiltered 5-nearest vote of constitution 1.5.0 deciding the auto-accept while the vote within the candidates' chapters can only send a line to review, and by the **vague rule**, every vague line to ask the shipper. **Option (c)** limits the candidate proposal to the chapters of the nomenclature search's subheadings; it was measured with rule (a) through `--proposal-scope nomenclature` (tests/eval/hs6_eval.py, evaluation only, no product code or setting), against (a):

- **(a) on the 120-line and coolant sets** is the exact replay of the after-runs' rows (iterations 13 and 2) by the product's routing functions under rule (a) and the vague rule: `hs6_eval.py --replay <after-run file> --floor 0.40`, no model call (history iterations 21 and 9). This script checks that its own replay of rule (a) (`rule_a_now`) gives the same measures, the override off and on.
- **(a) on the outside set** is three runs of its own (iteration 1), the control of (c). The set: 14 lines approved by the author (tests/eval/hs6_eval_outside_set.json), whose expected HS-6 lies outside the twelve chapters of the old store, each from an EBTI ruling valid on 2026-11-19 and rewritten in plain shipper wording; each line's source ruling is kept out (leave-one-out).
- **(c)**: three runs on each set (iterations 20, 8 and 2). Every run: Gemini 2.5 Flash with reasoning off, query expansion off, customs wording off, three runs, threshold 85, the rebuilt store of every chapter.
- **Cost**: $0.5544 by the key's usage, read once OpenRouter had settled it; $0.6558 by the evaluation's tallies (120 lines (c) $0.5178, coolant (c) $0.0335, outside (a) $0.0524, outside (c) $0.0521): within the approved $1.10.

**The 120-line set**:

| Run | Override | Majority top-1 | Top-1 per run | Auto-accepted per run | Wrong auto-accepted per run |
|---|---|---|---|---|---|
| Baseline (it. 12): 12 chapters, unscoped vote, the runs' routing | off | 84/120 | 83 / 84 / 83 | 68 / 70 / 67 | 3 / 4 / 3 (10) |
| Baseline (it. 12): 12 chapters, unscoped vote, the runs' routing | on | 87/120 | 87 / 87 / 87 | 72 / 73 / 71 | 3 / 4 / 3 (10) |
| (a): replay of it. 13 (it. 21) | off | 77/120 | 76 / 77 / 77 | 63 / 63 / 62 | 3 / 3 / 3 (9) |
| (a): replay of it. 13 (it. 21) | on | 80/120 | 79 / 80 / 80 | 66 / 66 / 65 | 3 / 3 / 3 (9) |
| (c) with (a) (it. 20) | off | 64/120 | 64 / 63 / 64 | 51 / 50 / 51 | 3 / 3 / 3 (9) |
| (c) with (a) (it. 20) | on | 65/120 | 65 / 65 / 65 | 52 / 52 / 52 | 3 / 3 / 3 (9) |

**The coolant set**:

| Run | Override | Majority right | Right per run | Auto-accepted per run | Wrong auto-accepted per run |
|---|---|---|---|---|---|
| Baseline (it. 1): 12 chapters, unscoped vote, the runs' routing | off | 6/8 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 (0) |
| Baseline (it. 1): 12 chapters, unscoped vote, the runs' routing | on | 6/8 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 (0) |
| (a): replay of it. 2 (it. 9) | off | 8/8 | 8 / 8 / 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (a): replay of it. 2 (it. 9) | on | 8/8 | 8 / 8 / 8 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (c) with (a) (it. 8) | off | 7/8 | 7 / 7 / 6 | 1 / 1 / 1 | 0 / 0 / 0 (0) |
| (c) with (a) (it. 8) | on | 7/8 | 7 / 7 / 6 | 1 / 1 / 1 | 0 / 0 / 0 (0) |

**The outside set**:

| Run | Override | Majority right | Right per run | Auto-accepted per run | Wrong auto-accepted per run |
|---|---|---|---|---|---|
| (a) (it. 1) | off | 12/14 | 12 / 12 / 12 | 7 / 8 / 8 | 0 / 1 / 1 (2) |
| (a) (it. 1) | on | 12/14 | 12 / 12 / 12 | 7 / 8 / 8 | 0 / 1 / 1 (2) |
| (c) with (a) (it. 2) | off | 11/14 | 11 / 11 / 11 | 7 / 7 / 7 | 1 / 1 / 1 (3) |
| (c) with (a) (it. 2) | on | 11/14 | 11 / 11 / 11 | 7 / 7 / 7 | 1 / 1 / 1 (3) |

**SC-004 under rule (a)**: wrong auto-accepts summed over the three replayed after-runs, 9, against 10 over the three baseline runs: **passes** (override on: 9 against 10). Judged on the chapter-filtered vote as first built it failed, 12 against 10 (eval-diff.md, section 4); rule (a) keeps the after-run's top-1s (the vote never changes a top-1 with the override off: majority 77, as the after-run's) and removes the 3 wrong auto-accepts of IEBTIIENEN004-2024-BTI208.

**(c) against (a)**: on the 120 lines (c) has a majority top-1 of 64 against 77 and the same wrong auto-accepts (9 against 9), with fewer auto-accepts (51 / 50 / 51 against 63 / 63 / 62 per run). It loses 16 lines that (a) gets right on majority and wins 3; in 15 of the lost lines the expected chapter is not among the chapters of the nomenclature search's subheadings, so (c)'s proposal could not bring the right code in, which is what the proposal does today (it lifted the labelled set's top-3 from 11 of 12 to 12 of 12). On the coolant set (c) loses coolant-1 (2710.19, proposed today by rulings of chapter 27); on the outside set it loses the chilli seasoning (2103.90 → 0904.22). The outside set's wrong auto-accepts are all the bike U-lock (FRBTIFR-BTI-2026-00308), 2 under (a) and 3 under (c): its source ruling gives 8301.10, while the model chose 8301.40, where 4 of its 5 nearest rulings sit. (c) is not in the app; nothing here recommends it.

The 120-line set's lines whose majority outcome differs between (a) and (c):

| Line | Expected | (a) majority | (c) majority | Expected chapter among (c)'s chapters | Proposed (a) → (c), run 1 |
|---|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI245 | 3926.90 | 3926.90 | 9033.00 | no (63, 73, 90) | 9019.20, 8108.20, 3926.90 → 9033.00, 9019.20, 9021.31 |
| IEBTIIENEN004-2025-BTI51 | 3926.90 | 3926.90 | 8538.90 | no (68, 84, 85, 87, 89) | 3926.90, 8547.20, 7326.90 → 8537.10, 8708.29, 8538.90 |
| IEBTIIENEN004-2024-BTI284 | 4202.12 | 4202.92 | 4202.32 | yes (42, 87, 96) | 4202.92, 3926.90, 7616.99 → 4202.92, 4202.12, 4202.32 |
| FRBTIFR-BTI-2025-02100 | 4203.29 | 6116.10 | 4203.29 | yes (42, 44, 61) | 4203.29 → 4203.29 |
| IEBTIIENEN004-2024-BTI132 | 6102.30 | 6112.12 | 6110.30 | yes (22, 23, 61, 72) | 3926.20 → 6102.30, 6110.30, 6113.00 |
| IEBTIIENEN004-2024-BTI208 | 6109.90 | 6114.30 | 6109.90 | yes (61, 62, 65) | 6114.30, 6212.10, 6212.90 → 6114.30, 6109.90, 6212.10 |
| DEBTI52786/23-1 | 6113.00 | 6113.00 | 6210.20 | no (62, 69, 84) | 6210.30, 6113.00, 6202.40 → 6210.30, 6210.20, 6202.40 |
| SEBTITV-2026-01096 | 6307.90 | 9503.00 | no code | no (05, 29, 41, 43, 44, 72) | 6307.90, 9503.00, 4205.00 → 4421.99, 4420.19, 4303.90 |
| XIBTI505066180 | 6307.90 | 8708.21 | 9401.99 | no (84, 87, 94) | 9404.90, 9401.80, 6307.90 → 9404.90, 9401.80, 9401.99 |
| IEBTIIENEN004-2024-BTI96 | 7326.90 | 7326.90 | 8207.70 | no (72, 82, 89) | 7326.90, 8209.00, 8207.30 → 8207.13, 8207.90, 8207.80 |
| IEBTIIENEN004-2025-BTI173 | 7326.90 | 7326.90 | 8305.90 | no (23, 31, 39, 83, 84) | 7326.90, 4202.32, 7616.99 → 3919.90, 3926.90, 3926.10 |
| IEBTIIENEN004-2025-BTI293 | 8424.90 | 9018.39 | 7304.41 | no (23, 72, 73, 89) | 9018.32, 9018.39, 7304.41 → 7326.90, 7304.41, 7307.29 |
| XIBTI505059567 | 8504.40 | 8471.80 | 8504.40 | yes (85) | 8471.80, 8504.40, 8536.69 → 8504.40, 8536.69, 8525.89 |
| XIBTI505070292 | 9403.20 | 9403.20 | 6306.90 | no (23, 63, 68, 72) | 9403.20, 6307.90, 6306.90 → 6307.90, 6306.90 |
| SEBTITV-2024-01674 | 9401.99 | 9401.99 | 6304.99 | no (29, 63, 72, 85) | 9401.99 → 6307.90, 6304.92, 6304.93 |
| SEBTITV-2024-01665 | 9401.99 | 9401.99 | 6304.99 | no (29, 63, 72, 85) | 9401.99 → 6307.90, 6304.92, 6304.93 |
| IEBTIIENEN004-2024-BTI333 | 9403.60 | 9403.60 | 4420.90 | no (44, 48, 84, 96) | 9403.60, 9023.00, 9504.90 → 4420.90, 9610.00, 4421.99 |
| SEBTITV-2024-01658 | 9401.99 | 9401.99 | 6304.99 | no (29, 63, 72, 85) | 9401.99 → 6307.90, 6304.92, 6304.93 |
| SEBTITV-2024-01615 | 9401.99 | 9401.99 | 6304.99 | no (29, 63, 72, 85) | 9401.99 → 6307.90, 6304.92, 6304.93 |
| IEBTIIENEN004-2025-BTI67 | 9503.00 | 9503.00 | 9403.60 | no (44, 72, 82, 84, 85, 94) | 9503.00, 9403.60, 4419.19 → 9403.60, 4419.19, 8215.20 |
| IEBTIIENEN004-2026-BTI99 | 9503.00 | 9503.00 | 6301.40 | no (63, 65, 66, 68) | 9503.00, 4820.10, 9404.40 → 6307.90, 6301.40 |
| IEBTIIENEN004-2026-BTI118 | 9503.00 | 9503.00 | 6306.22 | no (06, 63, 73, 74) | 9503.00, 6307.90, 9401.79 → 6307.90, 6306.22, 6304.93 |
| IEBTIIENEN004-2026-BTI72 | 9619.00 | 9619.00 | 6108.22 | no (61, 68, 92) | 9619.00 → 6108.22, 6112.41 |
| IEBTIIENEN004-2026-BTI222 | 9609.10 | 9609.10 | 9609.90 | yes (82, 96) | 9609.10, 4903.00, 9609.90 → 9609.10, 9609.90, 9608.10 |

The coolant set's:

| Line | Expected | (a) majority | (c) majority | Expected chapter among (c)'s chapters | Proposed (a) → (c), run 1 |
|---|---|---|---|---|---|
| coolant-1 | 2710.19 | 2710.19 | 3820.00 | no (38, 56, 84, 85) | 3824.99, 2710.19, 3402.50 → 3824.99, 3820.00, 3811.90 |

The outside set's:

| Line | Expected | (a) majority | (c) majority | Expected chapter among (c)'s chapters | Proposed (a) → (c), run 1 |
|---|---|---|---|---|---|
| IEBTIIENEN004-2026-BTI266 | 2103.90 | 2103.90 | 0904.22 | no (04, 09, 17, 20, 42) | 2103.90, 2004.10, 2106.90 → 0904.22, 2004.10, 0904.11 |
