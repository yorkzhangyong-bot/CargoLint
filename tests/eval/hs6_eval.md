# HS-6 evaluation report (feature 006)

- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's 120 EBTI rulings (built 2026-10-23); a line's correct HS-6 is the first six digits of its ruling's CN-8.
- **Method**: each ruling's goods description, as given, is a new line through the app's path: the description check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold 85, ask floor 50). A line's own ruling is never a precedent (leave-one-out); ruling validity on the set's build date. `python tests/eval/hs6_eval.py --repeat 3`.
- **Top-1** is the first candidate; a line without one (a stop word, a failure) is a miss. **In top 3**: the correct HS-6 among the candidates the clerk picks from on review. **Majority**: the most frequent top-1 over the runs (a tie goes to the earliest run). **Wrong, auto-accepted**: routed to auto-accept with a wrong top-1; the CN-8 step then runs on the wrong HS-6.
- **Vote gate** (the entries with gate reasons): the 5 nearest eligible rulings at or above a cosine similarity of 0.4 vote on the first six digits, and the model's top-1 is auto-accepted when it is their majority with a share of at least 0.5; the threshold applies only when none votes. **Lost**: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Iteration | Run on | Tag | Runs | Top-1 per run | Majority top-1 | In top 3 per run | Same top-1 | Same route | Wrong, auto-accepted per run | End to end per run | Auto-accepted per run | Right auto-accepts lost per run | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-25 | hs6-baseline | 3 | 72 / 68 / 69 of 120 | 69/120 | 103 / 103 / 101 of 120 | 114/120 | 119/120 | 43 / 48 / 46 | 59 / 54 / 56 of 120 | 108 / 109 / 108 | - | $0.1932 (€0.1778), 350 s |
| 2 | 2026-10-26 | hs6-vote-gate | 3 | 68 / 69 / 70 of 120 | 69/120 | 101 / 101 / 101 of 120 | 112/120 | 112/120 | 3 / 2 / 2 | 55 / 54 / 56 of 120 | 54 / 53 / 53 | 10 / 11 / 12 | $0.1931 (€0.1777), 379 s |
| 3 | 2026-10-26 | hs6-deepseek-v4-flash | 3 | 82 / 76 / 78 of 120 | 78/120 | 110 / 109 / 107 of 120 | 108/120 | 103/120 | 4 / 6 / 6 | 63 / 59 / 61 of 120 | 64 / 60 / 61 | 13 / 12 / 12 | $0.1069 (€0.0983), 635 s |
| 4 | 2026-10-26 | hs6-gemini25-flash | 3 | 82 / 84 / 82 of 120 | 82/120 | 107 / 108 / 107 of 120 | 113/120 | 115/120 | 5 / 4 / 4 | 67 / 68 / 67 of 120 | 64 / 66 / 62 | 15 / 14 / 16 | $0.5221 (€0.4803), 240 s |
| 5 | 2026-10-26 | hs6-gpt41-mini | 3 | 76 / 75 / 76 of 120 | 76/120 | 105 / 104 / 102 of 120 | 111/120 | 116/120 | 4 / 5 / 4 | 62 / 60 / 61 of 120 | 60 / 61 / 60 | 11 / 10 / 11 | $0.5320 (€0.4895), 328 s |
| 6 | 2026-10-26 | hs6-haiku45 | 1 | 83 of 120 | 83/120 | 107 of 120 | 120/120 | 120/120 | 5 | 69 of 120 | 69 | 10 | $0.6267 (€0.5766), 173 s |
| 7 | 2026-10-26 | hs6-override | 1 | 83 of 120 | 83/120 | 108 of 120 | 120/120 | 120/120 | 3 | 74 of 120 | 67 | 17 | $0.1749 (€0.1609), 169 s |
| 8 | 2026-10-26 | hs6-override-min5 | 1 | 83 of 120 | 83/120 | 108 of 120 | 120/120 | 120/120 | 3 | 74 of 120 | 67 | 17 | $0.0000 (€0.0000), 0 s |
| 9 | 2026-10-27 | zh-off | 1 | 17 of 30 | 17/30 | 26 of 30 | 30/30 | 30/30 | 0 | 12 of 30 | 9 | 8 | $0.0425 (€0.0391), 24 s |
| 10 | 2026-10-27 | zh-on | 1 | 17 of 30 | 17/30 | 25 of 30 | 30/30 | 30/30 | 2 | 12 of 30 | 15 | 4 | $0.0481 (€0.0443), 33 s |
| 11 | 2026-10-27 | en-on | 1 | 81 of 120 | 81/120 | 109 of 120 | 120/120 | 120/120 | 3 | 65 of 120 | 64 | 18 | $0.2024 (€0.1863), 115 s |

## Iteration 1 (hs6-baseline, openai/gpt-4o-mini, 2026-10-25)

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 72/120 | 103/120 | 108 | 5 | 7 | 43 |
| 2 | 68/120 | 103/120 | 109 | 4 | 7 | 48 |
| 3 | 69/120 | 101/120 | 108 | 5 | 7 | 46 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 56 | 13 | 41 | 10 |
| Run 1 | 59 | 13 | 38 | 10 |
| Run 2 | 54 | 14 | 41 | 11 |
| Run 3 | 56 | 13 | 40 | 11 |

On majority results 64 of 120 lines end wrong: 51 from the HS-6 step (the CN-8 step would have failed too on 10 of them), 13 from the CN-8 step alone. End-to-end estimate per run: 59 / 54 / 56 of 120.

Wrong top-1 results (line × run): 151; the correct HS-6 was among the candidates shown to the model in 124 (82.1%).

Leakage guard: each line's own ruling was its nearest ruling in 110 / 111 / 110 of 120 lines (per run), among the 12 the precedent search reads in 120 / 120 / 120; the guard kept it out of the precedents.

### Lines wrong in every run (48)

- XIBTI505068468 (chapter 39, expected 3926.90): 7321.81 (85, ask_shipper) · 7321.81 (85, ask_shipper) · 7321.81 (85, ask_shipper); correct in the top 3 in 0 of 3 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.92 (95, auto_accept) · 4202.92 (95, auto_accept) · 4202.92 (95, auto_accept); correct in the top 3 in 2 of 3 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2024-BTI141 (chapter 39, expected 3926.90): 9111.80 (95, auto_accept) · 9111.80 (95, auto_accept) · 9111.80 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "The product is a snap on protective case for a smart watch. Its function is to …"
- IEBTIIENEN004-2023-BTI572 (chapter 39, expected 3923.10): 9617.00 (95, auto_accept) · 9617.00 (95, auto_accept) · 9617.00 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Celsius SSM Shipper It is used to ship Pharmaceutical Drug Substance on an inte…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (95, auto_accept) · 4202.32 (95, auto_accept) · 4202.32 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (95, auto_accept) · 4202.22 (95, auto_accept) · 4202.22 (95, auto_accept); correct in the top 3 in 2 of 3 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2024-BTI189 (chapter 42, expected 4202.92): 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "24L Pack Pack Standard Issue 24-liter backpacks - multiple compartments at diff…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, auto_accept) · 4202.22 (95, auto_accept) · 4202.22 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept) · 4202.12 (95, auto_accept); correct in the top 3 in 2 of 3 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (95, auto_accept) · 6112.12 (95, auto_accept) · 6112.12 (95, auto_accept); correct in the top 3 in 2 of 3 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (95, auto_accept) · 6114.30 (95, auto_accept) · 6114.30 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, auto_accept) · 6104.33 (95, auto_accept) · 6104.33 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- FRBTIFR-BTI-2025-08672 (chapter 61, expected 6111.20): 6209.20 (95, auto_accept) · 6209.20 (95, auto_accept) · 6209.20 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Accessoire du vêtement pour bébés se présentant sous la forme d’un bavoir de fo…"
- DEBTI52786/23-1 (chapter 61, expected 6113.00): 6203.33 (95, auto_accept) · 6203.33 (95, auto_accept) · 6203.33 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Blouson, sog. PREVENT® Warnschutz-Softshelljacke, Artikel 8060O, Größe M, Foto …"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept) · 6112.41 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (59, review) · 6204.33 (95, auto_accept) · 6204.33 (59, review); correct in the top 3 in 3 of 3 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI23 (chapter 63, expected 6307.90): 6215.90 (95, auto_accept) · 6215.90 (95, auto_accept) · 6215.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Two strips of grosgrain textile material cut to a specified length, then attach…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (90, auto_accept) · 3304.99 (90, auto_accept) · 3304.99 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, auto_accept) · 9503.00 (95, auto_accept) · 9503.00 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.19 (95, auto_accept) · 4602.90 (95, auto_accept) · 4602.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (90, auto_accept) · 4602.19 (90, auto_accept) · 4602.19 (90, auto_accept); correct in the top 3 in 3 of 3 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, auto_accept) · 4602.90 (95, auto_accept) · 4602.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-018 (chapter 63, expected 6307.90): 6306.12 (95, auto_accept) · 6306.12 (95, auto_accept) · 6306.12 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Woven polyester fabric, 100% waterproof. Hemmed all round and can be tightened …"
- XIBTI505066180 (chapter 63, expected 6307.90): 8708.21 (90, auto_accept) · 8708.21 (95, auto_accept) · 8708.21 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, auto_accept) · 6305.90 (95, auto_accept) · 6305.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, auto_accept) · 9503.00 (95, auto_accept) · 9503.00 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI352 (chapter 64, expected 6404.19): 6405.20 (95, auto_accept) · 6405.20 (95, auto_accept) · 6405.20 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept) · 6404.19 (90, auto_accept); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 7310.10 (95, auto_accept) · 7310.10 (95, auto_accept) · 7310.10 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2025-BTI69 (chapter 73, expected 7318.14): 7318.15 (85, ask_shipper) · 7318.15 (85, ask_shipper) · 7318.15 (85, ask_shipper); correct in the top 3 in 3 of 3 runs. "A mild steel, case hardened, hex Flange head screw with self cutting HI-LO thre…"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, auto_accept) · 8415.82 (95, auto_accept) · 8415.82 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.80 (95, auto_accept) · 8481.80 (90, auto_accept) · 8481.80 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, auto_accept) · 8419.89 (95, auto_accept) · 8419.89 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7306.61 (95, auto_accept) · 7306.61 (95, auto_accept) · 7306.61 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3920.10 (95, auto_accept) · 3920.10 (95, auto_accept) · 3920.10 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (90, auto_accept) · 8479.89 (90, auto_accept) · 8413.20 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, auto_accept) · 8536.30 (95, auto_accept) · 8536.30 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2023-BTI579 (chapter 85, expected 8528.52): 8528.72 (95, auto_accept) · 8528.72 (95, auto_accept) · 8528.72 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "14” portable LCD colour monitor. With a screen resolution of 1920 x 1080 pixels…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review) · 8504.31 (59, review) · 8504.31 (59, review); correct in the top 3 in 0 of 3 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.20 (59, review) · 8536.20 (59, review) · 8536.20 (59, review); correct in the top 3 in 2 of 3 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- XIBTI505065379 (chapter 85, expected 8505.19): 9505.90 (95, auto_accept) · 9505.90 (95, auto_accept) · 9505.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Durable, plastic horseshoe-shaped magnets in six different colours. Intended fo…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2025-BTI38 (chapter 95, expected 9503.00): 9618.00 (95, auto_accept) · 9618.00 (95, auto_accept) · 9618.00 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "45CM SOFT TEXTILE COVERED INTERACTIVE ANIMATRONIC PUPPET. THE PRODUCT HAS A PLA…"
- IEBTIIENEN004-2025-BTI460 (chapter 95, expected 9503.00): 9506.62 (95, auto_accept) · 9506.62 (95, auto_accept) · 9506.62 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "INFLATABLE SWIMMING RING, MADE FROM 100% PVC. IT IS INTENDED FOR USE BY CHILDRE…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, auto_accept) · 9609.90 (95, auto_accept) · 9609.90 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (6)

- IEBTIIENEN004-2024-BTI7 (expected 6307.90): 4602.19 (95, auto_accept) · 4602.90 (95, auto_accept) · 4602.90 (95, auto_accept)
- IEBTIIENEN004-2024-BTI354 (expected 6404.19): 6404.19 (95, auto_accept) · 6405.20 (95, auto_accept) · 6405.20 (95, auto_accept)
- IEBTIIENEN004-2024-BTI377 (expected 6404.19): 6404.19 (95, auto_accept) · 6405.20 (95, auto_accept) · 6405.20 (95, auto_accept)
- IEBTIIENEN004-2025-BTI301 (expected 7325.99): 7325.99 (90, auto_accept) · 8421.39 (90, auto_accept) · 8421.39 (90, auto_accept)
- MTBTI2024-002 (expected 8424.89): 8479.89 (90, auto_accept) · 8479.89 (90, auto_accept) · 8413.20 (95, auto_accept)
- SEBTITV-2024-01665 (expected 9401.99): 9401.99 (95, auto_accept) · 6304.92 (95, auto_accept) · 9401.99 (95, auto_accept)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 43 / 48 / 46. In every run: 43 lines, each among the lines wrong in every run above.

- DEBTI7623/25-1 (expected 6202.40): run 2: 6204.33 (95)
- IEBTIIENEN004-2024-BTI354 (expected 6404.19): run 2: 6405.20 (95); run 3: 6405.20 (95)
- IEBTIIENEN004-2024-BTI377 (expected 6404.19): run 2: 6405.20 (95); run 3: 6405.20 (95)
- IEBTIIENEN004-2025-BTI301 (expected 7325.99): run 2: 8421.39 (90); run 3: 8421.39 (90)
- SEBTITV-2024-01665 (expected 9401.99): run 2: 6304.92 (95)

## Iteration 2 (hs6-vote-gate, openai/gpt-4o-mini, 2026-10-26)

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 68/120 | 101/120 | 54 | 59 | 7 | 3 |
| 2 | 69/120 | 101/120 | 53 | 59 | 8 | 2 |
| 3 | 70/120 | 101/120 | 53 | 59 | 8 | 2 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 54 | 41 | 12 | 1 | 0 | 12 | 0 | 51 | 10 |
| 2 | 53 | 43 | 11 | 1 | 0 | 12 | 0 | 51 | 11 |
| 3 | 53 | 42 | 11 | 2 | 0 | 12 | 0 | 51 | 12 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 55 | 14 | 42 | 9 |
| Run 1 | 55 | 13 | 42 | 10 |
| Run 2 | 54 | 15 | 41 | 10 |
| Run 3 | 56 | 14 | 40 | 10 |

On majority results 65 of 120 lines end wrong: 51 from the HS-6 step (the CN-8 step would have failed too on 9 of them), 14 from the CN-8 step alone. End-to-end estimate per run: 55 / 54 / 56 of 120.

Wrong top-1 results (line × run): 153; the correct HS-6 was among the candidates shown to the model in 127 (83.0%).

Leakage guard: each line's own ruling was its nearest ruling in 110 / 111 / 110 of 120 lines (per run), among the 12 the precedent search reads in 120 / 120 / 120; the guard kept it out of the precedents.

### Lines wrong in every run (48)

- XIBTI505068468 (chapter 39, expected 3926.90): 7321.81 (85, ask_shipper) · 7321.81 (85, ask_shipper) · 7321.81 (85, ask_shipper); correct in the top 3 in 0 of 3 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.92 (95, review) · 4202.92 (95, review) · 4202.92 (95, review); correct in the top 3 in 3 of 3 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2025-BTI463 (chapter 39, expected 3926.90): 4008.29 (95, review) · 4008.29 (95, review) · 4008.29 (95, review); correct in the top 3 in 3 of 3 runs. "The product is an orange coloured cushion part used inside a gear shifter, unde…"
- IEBTIIENEN004-2024-BTI141 (chapter 39, expected 3926.90): 9111.80 (95, review) · 9111.80 (95, review) · 9111.80 (95, review); correct in the top 3 in 3 of 3 runs. "The product is a snap on protective case for a smart watch. Its function is to …"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (95, review) · 4202.32 (95, review) · 4202.32 (95, review); correct in the top 3 in 0 of 3 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (95, review) · 4202.22 (95, review) · 4202.22 (95, review); correct in the top 3 in 2 of 3 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, review) · 4202.12 (95, review) · 4202.12 (95, review); correct in the top 3 in 0 of 3 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2024-BTI189 (chapter 42, expected 4202.92): 4202.12 (95, review) · 4202.12 (95, review) · 4202.12 (95, review); correct in the top 3 in 0 of 3 runs. "24L Pack Pack Standard Issue 24-liter backpacks - multiple compartments at diff…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, review) · 4202.22 (95, review) · 4202.22 (95, review); correct in the top 3 in 3 of 3 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (95, review) · 4202.12 (95, review) · 4202.12 (95, review); correct in the top 3 in 0 of 3 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (95, review) · 6112.12 (95, review) · 6112.12 (95, review); correct in the top 3 in 2 of 3 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (95, review) · 6114.30 (95, review) · 6114.30 (95, review); correct in the top 3 in 0 of 3 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, review) · 6104.33 (95, review) · 6104.33 (95, review); correct in the top 3 in 0 of 3 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- FRBTIFR-BTI-2025-08672 (chapter 61, expected 6111.20): 6209.20 (95, review) · 6209.20 (95, review) · 6209.20 (95, review); correct in the top 3 in 3 of 3 runs. "Accessoire du vêtement pour bébés se présentant sous la forme d’un bavoir de fo…"
- DEBTI52786/23-1 (chapter 61, expected 6113.00): 6203.33 (95, review) · 6203.33 (95, review) · 6203.33 (95, review); correct in the top 3 in 0 of 3 runs. "Blouson, sog. PREVENT® Warnschutz-Softshelljacke, Artikel 8060O, Größe M, Foto …"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (59, review) · 6204.33 (59, review) · 6204.33 (95, review); correct in the top 3 in 3 of 3 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI23 (chapter 63, expected 6307.90): 6215.90 (95, review) · 6215.90 (95, review) · 6215.90 (95, review); correct in the top 3 in 3 of 3 runs. "Two strips of grosgrain textile material cut to a specified length, then attach…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (90, review) · 3304.99 (90, review) · 3304.99 (90, review); correct in the top 3 in 0 of 3 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.90 (95, review) · 4602.19 (95, review) · 4602.90 (95, review); correct in the top 3 in 3 of 3 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (90, review) · 4602.19 (90, review) · 4602.19 (90, review); correct in the top 3 in 3 of 3 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, review) · 4602.90 (95, review) · 4602.90 (95, review); correct in the top 3 in 3 of 3 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-018 (chapter 63, expected 6307.90): 6306.12 (95, review) · 6306.12 (95, review) · 6306.12 (95, review); correct in the top 3 in 3 of 3 runs. "Woven polyester fabric, 100% waterproof. Hemmed all round and can be tightened …"
- XIBTI505066180 (chapter 63, expected 6307.90): 8708.21 (95, review) · 8708.21 (95, review) · 8708.21 (90, review); correct in the top 3 in 0 of 3 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, review) · 6305.90 (95, review) · 6305.90 (95, review); correct in the top 3 in 3 of 3 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI352 (chapter 64, expected 6404.19): 6405.20 (95, review) · 6405.20 (95, review) · 6405.20 (95, review); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 7310.10 (95, review) · 7310.10 (95, review) · 7310.10 (95, review); correct in the top 3 in 0 of 3 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2025-BTI69 (chapter 73, expected 7318.14): 7318.15 (85, ask_shipper) · 7318.15 (85, ask_shipper) · 7318.15 (85, ask_shipper); correct in the top 3 in 3 of 3 runs. "A mild steel, case hardened, hex Flange head screw with self cutting HI-LO thre…"
- IEBTIIENEN004-2025-BTI301 (chapter 73, expected 7325.99): 8421.39 (90, review) · 8421.39 (90, review) · 8421.39 (90, review); correct in the top 3 in 3 of 3 runs. "1. Stainless steel X5000 Housing 2. Circular Housing , with 4 Cable entries , U…"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review) · 8415.82 (95, review) · 8415.82 (95, review); correct in the top 3 in 0 of 3 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.80 (95, review) · 8481.80 (95, review) · 8481.80 (95, review); correct in the top 3 in 0 of 3 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review) · 8419.89 (95, review) · 8419.89 (95, review); correct in the top 3 in 3 of 3 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7306.61 (95, review) · 7306.61 (95, review) · 7306.61 (95, review); correct in the top 3 in 0 of 3 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3920.10 (95, review) · 3920.10 (95, review) · 3920.10 (95, review); correct in the top 3 in 0 of 3 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (90, auto_accept) · 8413.20 (95, review) · 8479.89 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review) · 8536.30 (95, review) · 8536.30 (95, review); correct in the top 3 in 3 of 3 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2023-BTI579 (chapter 85, expected 8528.52): 8528.72 (95, review) · 8528.72 (95, review) · 8528.72 (95, review); correct in the top 3 in 3 of 3 runs. "14” portable LCD colour monitor. With a screen resolution of 1920 x 1080 pixels…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review) · 8504.31 (40, ask_shipper) · 8504.31 (59, review); correct in the top 3 in 0 of 3 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.20 (59, review) · 8536.20 (59, review) · 8536.20 (59, review); correct in the top 3 in 2 of 3 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- XIBTI505065379 (chapter 85, expected 8505.19): 9505.90 (95, review) · 9505.90 (95, review) · 9505.90 (95, review); correct in the top 3 in 3 of 3 runs. "Durable, plastic horseshoe-shaped magnets in six different colours. Intended fo…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2025-BTI38 (chapter 95, expected 9503.00): 9618.00 (95, review) · 9618.00 (95, review) · 9618.00 (95, review); correct in the top 3 in 3 of 3 runs. "45CM SOFT TEXTILE COVERED INTERACTIVE ANIMATRONIC PUPPET. THE PRODUCT HAS A PLA…"
- IEBTIIENEN004-2025-BTI460 (chapter 95, expected 9503.00): 9506.62 (95, review) · 9506.62 (95, review) · 9506.62 (95, review); correct in the top 3 in 3 of 3 runs. "INFLATABLE SWIMMING RING, MADE FROM 100% PVC. IT IS INTENDED FOR USE BY CHILDRE…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review) · 9609.90 (95, review) · 9609.90 (40, ask_shipper); correct in the top 3 in 0 of 3 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (8)

- IEBTIIENEN004-2023-BTI572 (expected 3923.10): 9617.00 (95, review) · 3923.10 (95, review) · 3923.10 (90, review)
- IEBTIIENEN004-2024-BTI7 (expected 6307.90): 4602.90 (95, review) · 4602.19 (95, review) · 4602.90 (95, review)
- IEBTIIENEN004-2024-BTI356 (expected 6405.20): 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept) · 6405.20 (95, review)
- IEBTIIENEN004-2024-BTI354 (expected 6404.19): 6404.19 (95, auto_accept) · 6405.20 (95, review) · 6405.20 (95, review)
- MTBTI2024-002 (expected 8424.89): 8479.89 (90, auto_accept) · 8413.20 (95, review) · 8479.89 (90, auto_accept)
- SEBTITV-2024-01665 (expected 9401.99): 9401.99 (95, auto_accept) · 9401.99 (95, auto_accept) · 6304.92 (95, review)
- SEBTITV-2024-01615 (expected 9401.99): 6304.92 (95, review) · 6304.92 (95, review) · 9401.99 (95, auto_accept)
- IEBTIIENEN004-2026-BTI72 (expected 9619.00): 6108.22 (95, review) · 9619.00 (95, auto_accept) · 9619.00 (95, auto_accept)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 3 / 2 / 2. In every run: 1 line, each among the lines wrong in every run above.

- IEBTIIENEN004-2024-BTI356 (expected 6405.20): run 1: 6404.19 (95); run 2: 6404.19 (95)
- MTBTI2024-002 (expected 8424.89): run 1: 8479.89 (90); run 3: 8479.89 (90)

## Iteration 3 (hs6-deepseek-v4-flash, deepseek/deepseek-v4-flash, 2026-10-26)

Invalid answers (retried at most 1 time): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 2: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 3: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 97: 0 / 2 · 95: 72 / 12 · 93: 0 / 1 · 92: 10 / 7 · 90: 104 / 41 · 88: 3 / 4 · 87: 1 / 0 · 85: 28 / 33 · 80: 2 / 2 · 75: 2 / 2 · 70: 10 / 12 · 65: 1 / 4 · 55: 1 / 0 · 50: 1 / 0 · 40: 1 / 4.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 82/120 | 110/120 | 64 | 48 | 8 | 4 |
| 2 | 76/120 | 109/120 | 60 | 53 | 7 | 6 |
| 3 | 78/120 | 107/120 | 61 | 48 | 11 | 6 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 64 | 31 | 12 | 2 | 0 | 11 | 0 | 60 | 13 |
| 2 | 60 | 35 | 9 | 3 | 0 | 13 | 0 | 54 | 12 |
| 3 | 61 | 30 | 9 | 3 | 0 | 17 | 0 | 55 | 12 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 61 | 17 | 36 | 6 |
| Run 1 | 63 | 19 | 34 | 4 |
| Run 2 | 59 | 17 | 36 | 8 |
| Run 3 | 61 | 17 | 35 | 7 |

On majority results 59 of 120 lines end wrong: 42 from the HS-6 step (the CN-8 step would have failed too on 6 of them), 17 from the CN-8 step alone. End-to-end estimate per run: 63 / 59 / 61 of 120.

Wrong top-1 results (line × run): 124; the correct HS-6 was among the candidates shown to the model in 99 (79.8%).

Leakage guard: each line's own ruling was its nearest ruling in 110 / 110 / 110 of 120 lines (per run), among the 12 the precedent search reads in 120 / 120 / 120; the guard kept it out of the precedents.

### Lines wrong in every run (36)

- XIBTI505068468 (chapter 39, expected 3926.90): 7321.81 (70, ask_shipper) · 7322.90 (65, ask_shipper) · 7321.81 (70, ask_shipper); correct in the top 3 in 0 of 3 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.92 (90, review) · 4202.92 (90, review) · 4202.92 (90, review); correct in the top 3 in 3 of 3 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (90, review) · 4202.92 (90, review) · 4202.92 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (85, review) · 4202.12 (85, review) · 4202.12 (70, review); correct in the top 3 in 2 of 3 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (90, review) · 4202.12 (85, review) · 4202.12 (90, review); correct in the top 3 in 2 of 3 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6101.30 (85, review) · 6101.30 (85, review) · 6101.30 (85, review); correct in the top 3 in 3 of 3 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (88, review) · 6114.30 (85, review) · 6114.30 (85, review); correct in the top 3 in 0 of 3 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (85, review) · 6104.33 (90, review) · 6104.33 (93, review); correct in the top 3 in 0 of 3 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- DEBTI23122/26-1 (chapter 61, expected 6116.10): 6116.93 (95, review) · 6116.93 (95, review) · 6116.93 (90, review); correct in the top 3 in 3 of 3 runs. "Handschuhe, Größe 10/XL, Foto siehe Anlage, - laut Antrag: -- paarweise an eine…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (92, review) · 6112.41 (95, review) · 6112.41 (92, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (90, review) · 6112.41 (90, review) · 6112.41 (90, review); correct in the top 3 in 3 of 3 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (85, review) · 6204.33 (90, review) · 6204.33 (90, review); correct in the top 3 in 3 of 3 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (70, review) · 3304.99 (65, review) · 3304.20 (70, review); correct in the top 3 in 2 of 3 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (92, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.90 (92, review) · 4602.90 (59, review) · 4602.90 (59, review); correct in the top 3 in 3 of 3 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (85, review) · 4602.19 (85, review) · 4602.19 (85, review); correct in the top 3 in 3 of 3 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (90, review) · 4602.90 (92, review) · 4602.90 (85, review); correct in the top 3 in 3 of 3 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (90, review) · 6305.90 (90, review) · 6305.90 (85, review); correct in the top 3 in 3 of 3 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (90, review) · 9503.00 (90, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI352 (chapter 64, expected 6404.19): 6405.20 (95, review) · 6405.20 (95, review) · 6405.20 (97, review); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- IEBTIIENEN004-2024-BTI354 (chapter 64, expected 6404.19): 6405.20 (90, review) · 6405.20 (90, review) · 6405.20 (90, review); correct in the top 3 in 3 of 3 runs. "LADIES FUR MULE STYLE SLIPPER WITH OPEN TOE, UPPERS OF TEXTILE, OUTER SOLES OF …"
- IEBTIIENEN004-2024-BTI377 (chapter 64, expected 6404.19): 6405.20 (97, review) · 6405.20 (92, review) · 6405.20 (92, review); correct in the top 3 in 3 of 3 runs. "MEN'S MULE STYLE SLIPPER WITH A CLOSED IN TOE; UPPERS OF TEXTILE, OUTER SOLES O…"
- IEBTIIENEN004-2024-BTI348 (chapter 64, expected 6404.19): 6405.20 (88, review) · 6405.20 (90, review) · 6405.20 (90, review); correct in the top 3 in 3 of 3 runs. "CHILDREN'S MOCCASIN STYLE SLIPPERS WITH UPPERS OF TEXTILE, OUTER SOLES OF PLAST…"
- IEBTIIENEN004-2025-BTI301 (chapter 73, expected 7325.99): 8421.39 (70, review) · 8421.39 (85, review) · 8421.39 (85, review); correct in the top 3 in 3 of 3 runs. "1. Stainless steel X5000 Housing 2. Circular Housing , with 4 Cable entries , U…"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (88, review) · 8415.82 (90, review) · 8415.82 (90, review); correct in the top 3 in 0 of 3 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.90 (85, review) · 8481.90 (75, review) · 8481.90 (85, review); correct in the top 3 in 0 of 3 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (80, review) · 8419.89 (80, review) · 8419.89 (85, review); correct in the top 3 in 3 of 3 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7308.90 (59, review) · 7308.90 (59, review) · 7308.90 (59, review); correct in the top 3 in 0 of 3 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3926.90 (70, auto_accept) · 3926.90 (88, auto_accept) · 3926.90 (85, auto_accept); correct in the top 3 in 0 of 3 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (90, auto_accept) · 8479.89 (95, auto_accept) · 8479.89 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (59, review) · 3925.90 (59, review) · 3925.90 (59, review); correct in the top 3 in 3 of 3 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (40, ask_shipper) · 8504.31 (90, auto_accept) · 8504.31 (40, ask_shipper); correct in the top 3 in 0 of 3 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.30 (85, review) · 8536.30 (85, review) · 8536.30 (85, review); correct in the top 3 in 2 of 3 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (90, auto_accept) · 9405.11 (90, auto_accept) · 9405.11 (90, auto_accept); correct in the top 3 in 3 of 3 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (85, review) · 9609.90 (70, review) · 9609.90 (40, ask_shipper); correct in the top 3 in 3 of 3 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (12)

- IEBTIIENEN004-2025-BTI351 (expected 3925.90): 3925.90 (85, review) · 8538.90 (90, auto_accept) · 8538.90 (90, auto_accept)
- XIBTI505068468 (expected 3926.90): 7321.81 (70, ask_shipper) · 7322.90 (65, ask_shipper) · 7321.81 (70, ask_shipper)
- IEBTIIENEN004-2024-BTI284 (expected 4202.12): 4202.32 (90, review) · 4202.92 (90, review) · 4202.92 (90, auto_accept)
- IEBTIIENEN004-2024-BTI145 (expected 4202.92): 4202.92 (55, review) · 4202.22 (90, review) · 4202.22 (40, ask_shipper)
- IEBTIIENEN004-2025-BTI227 (expected 4202.92): 4202.92 (90, auto_accept) · 4202.22 (90, review) · 4202.22 (90, review)
- IEBTIIENEN004-2026-BTI106 (expected 6212.10): 6112.41 (90, review) · 6112.41 (90, review) · 6212.10 (95, auto_accept)
- IEBTIIENEN004-2026-BTI228 (expected 6307.90): 3304.99 (70, review) · 3304.99 (65, review) · 3304.20 (70, review)
- XIBTI505066180 (expected 6307.90): 8708.21 (85, review) · 8708.21 (70, review) · 6307.90 (70, review)
- DEBTI37155/24-1 (expected 6402.91): 6402.91 (90, auto_accept) · 6402.91 (95, auto_accept) · 6402.99 (85, review)
- XIBTI505060394 (expected 7326.90): 7326.90 (85, auto_accept) · 8303.00 (70, review) · 7310.29 (85, review)
- XIBTI505059567 (expected 8504.40): 8504.40 (70, review) · 8471.80 (85, review) · 8471.80 (85, review)
- XIBTI505065379 (expected 8505.19): 8505.19 (90, auto_accept) · 9505.90 (90, review) · 8505.19 (90, auto_accept)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 4 / 6 / 6. In every run: 4 lines, each among the lines wrong in every run above.

- IEBTIIENEN004-2025-BTI351 (expected 3925.90): run 2: 8538.90 (90); run 3: 8538.90 (90)
- XIBTI505068566 (expected 8504.40): run 2: 8504.31 (90)
- IEBTIIENEN004-2024-BTI284 (expected 4202.12): run 3: 4202.92 (90)

## Iteration 4 (hs6-gemini25-flash, google/gemini-2.5-flash, 2026-10-26)

Invalid answers (retried at most 1 time): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 2: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 3: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 98: 77 / 2 · 95: 168 / 100 · 90: 2 / 7 · 85: 1 / 0 · 80: 0 / 2 · 65: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 82/120 | 107/120 | 64 | 49 | 7 | 5 |
| 2 | 84/120 | 108/120 | 66 | 47 | 7 | 4 |
| 3 | 82/120 | 107/120 | 62 | 51 | 7 | 4 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 64 | 32 | 10 | 3 | 0 | 11 | 0 | 59 | 15 |
| 2 | 66 | 32 | 8 | 3 | 0 | 11 | 0 | 62 | 14 |
| 3 | 62 | 35 | 8 | 4 | 0 | 11 | 0 | 58 | 16 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 67 | 15 | 30 | 8 |
| Run 1 | 67 | 15 | 30 | 8 |
| Run 2 | 68 | 16 | 27 | 9 |
| Run 3 | 67 | 15 | 29 | 9 |

On majority results 53 of 120 lines end wrong: 38 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 15 from the CN-8 step alone. End-to-end estimate per run: 67 / 68 / 67 of 120.

Wrong top-1 results (line × run): 112; the correct HS-6 was among the candidates shown to the model in 84 (75.0%).

Leakage guard: each line's own ruling was its nearest ruling in 111 / 110 / 111 of 120 lines (per run), among the 12 the precedent search reads in 120 / 120 / 120; the guard kept it out of the precedents.

### Lines wrong in every run (34)

- XIBTI505068468 (chapter 39, expected 3926.90): 7322.90 (90, ask_shipper) · 7322.90 (90, ask_shipper) · 7322.90 (90, ask_shipper); correct in the top 3 in 0 of 3 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.92 (95, auto_accept) · 4202.32 (95, review) · 4202.32 (95, review); correct in the top 3 in 3 of 3 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (95, review) · 4202.22 (95, review) · 4202.22 (95, review); correct in the top 3 in 3 of 3 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, review) · 4202.12 (95, review) · 4202.12 (95, review); correct in the top 3 in 1 of 3 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, review) · 4202.22 (95, review) · 4202.22 (95, review); correct in the top 3 in 3 of 3 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (95, review) · 4202.12 (95, review) · 4202.12 (95, review); correct in the top 3 in 3 of 3 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6101.30 (95, review) · 6101.30 (95, review) · 6101.30 (95, review); correct in the top 3 in 3 of 3 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (95, review) · 6114.30 (95, review) · 6114.30 (95, review); correct in the top 3 in 0 of 3 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, review) · 6104.33 (95, review) · 6104.33 (95, review); correct in the top 3 in 0 of 3 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (98, review) · 6112.41 (95, review) · 6112.41 (98, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (95, review) · 6204.33 (95, review) · 6204.33 (95, review); correct in the top 3 in 2 of 3 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (95, review) · 3304.99 (95, review) · 3304.99 (95, review); correct in the top 3 in 0 of 3 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.19 (95, review) · 4602.19 (95, review) · 4602.19 (95, review); correct in the top 3 in 3 of 3 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review) · 4602.19 (95, review) · 4602.19 (95, review); correct in the top 3 in 3 of 3 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- XIBTI505066180 (chapter 63, expected 6307.90): 8708.21 (95, review) · 8708.21 (95, review) · 8708.21 (90, review); correct in the top 3 in 3 of 3 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, review) · 6305.90 (95, review) · 6305.90 (95, review); correct in the top 3 in 3 of 3 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 8303.00 (95, review) · 8303.00 (95, review) · 8303.00 (95, review); correct in the top 3 in 0 of 3 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review) · 8415.82 (95, review) · 8415.82 (95, review); correct in the top 3 in 0 of 3 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.90 (95, review) · 8481.90 (95, review) · 8481.90 (95, review); correct in the top 3 in 0 of 3 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review) · 8419.89 (95, review) · 8419.89 (95, review); correct in the top 3 in 3 of 3 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7308.90 (59, review) · 7308.90 (59, review) · 7308.90 (59, review); correct in the top 3 in 0 of 3 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3926.90 (95, auto_accept) · 3926.90 (95, auto_accept) · 3926.90 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (95, auto_accept) · 8479.89 (95, auto_accept) · 8479.89 (95, auto_accept); correct in the top 3 in 0 of 3 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review) · 8536.30 (95, review) · 8536.30 (95, review); correct in the top 3 in 3 of 3 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (95, review) · 3925.90 (95, review) · 3925.90 (95, review); correct in the top 3 in 3 of 3 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505059567 (chapter 85, expected 8504.40): 8471.80 (95, review) · 8471.80 (95, review) · 8471.80 (95, review); correct in the top 3 in 3 of 3 runs. "Body Worn Camera Docking Station Black docking station with magnetic self-locat…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review) · 8504.31 (59, review) · 8504.31 (59, review); correct in the top 3 in 0 of 3 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review) · 9609.90 (95, review) · 9609.90 (95, review); correct in the top 3 in 3 of 3 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (7)

- IEBTIIENEN004-2024-BTI133 (expected 3926.90): 4202.92 (95, review) · 3926.90 (95, review) · 3926.90 (95, review)
- IEBTIIENEN004-2024-BTI284 (expected 4202.12): 4202.92 (95, auto_accept) · 4202.32 (95, review) · 4202.32 (95, review)
- FRBTIFR-BTI-2025-02100 (expected 4203.29): 6116.10 (95, review) · 4203.29 (95, auto_accept) · 6116.10 (95, review)
- IEBTIIENEN004-2024-BTI8 (expected 6307.90): 6307.90 (95, auto_accept) · 6307.90 (95, auto_accept) · 4602.90 (95, review)
- MTBTI2025-018 (expected 6307.90): 6306.12 (95, review) · 6306.12 (95, review) · 6307.90 (95, review)
- IEBTIIENEN004-2023-BTI561 (expected 8537.10): 8537.10 (95, review) · 8536.30 (95, review) · 8536.30 (95, review)
- IEBTIIENEN004-2026-BTI71 (expected 9619.00): 6108.21 (95, review) · 9619.00 (95, auto_accept) · 6108.21 (95, review)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 5 / 4 / 4. In every run: 4 lines, each among the lines wrong in every run above.

- IEBTIIENEN004-2024-BTI284 (expected 4202.12): run 1: 4202.92 (95)

## Iteration 5 (hs6-gpt41-mini, openai/gpt-4.1-mini, 2026-10-26)

Invalid answers (retried at most 1 time): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 2: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed; run 3: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 95: 174 / 70 · 90: 45 / 56 · 85: 5 / 3 · 70: 2 / 2 · 50: 1 / 1 · 40: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 76/120 | 105/120 | 60 | 52 | 8 | 4 |
| 2 | 75/120 | 104/120 | 61 | 52 | 7 | 5 |
| 3 | 76/120 | 102/120 | 60 | 53 | 7 | 4 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 60 | 33 | 11 | 3 | 0 | 13 | 0 | 56 | 11 |
| 2 | 61 | 33 | 11 | 2 | 0 | 13 | 0 | 56 | 10 |
| 3 | 60 | 33 | 10 | 3 | 0 | 14 | 0 | 56 | 11 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 61 | 15 | 36 | 8 |
| Run 1 | 62 | 14 | 35 | 9 |
| Run 2 | 60 | 15 | 35 | 10 |
| Run 3 | 61 | 15 | 35 | 9 |

On majority results 59 of 120 lines end wrong: 44 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 15 from the CN-8 step alone. End-to-end estimate per run: 62 / 60 / 61 of 120.

Wrong top-1 results (line × run): 133; the correct HS-6 was among the candidates shown to the model in 106 (79.7%).

Leakage guard: each line's own ruling was its nearest ruling in 111 / 110 / 111 of 120 lines (per run), among the 12 the precedent search reads in 120 / 120 / 120; the guard kept it out of the precedents.

### Lines wrong in every run (42)

- IEBTIIENEN004-2025-BTI351 (chapter 39, expected 3925.90): 8538.90 (90, auto_accept) · 8538.90 (95, auto_accept) · 8538.90 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "Internal mounting bracket for infrared sensor The bracket is used to hold the s…"
- XIBTI505068468 (chapter 39, expected 3926.90): 7321.81 (90, ask_shipper) · 7321.81 (90, ask_shipper) · 7321.81 (90, ask_shipper); correct in the top 3 in 0 of 3 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.92 (90, review) · 4202.92 (90, review) · 4202.92 (90, review); correct in the top 3 in 2 of 3 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2025-BTI463 (chapter 39, expected 3926.90): 9606.30 (90, review) · 9606.30 (90, review) · 9606.30 (90, review); correct in the top 3 in 3 of 3 runs. "The product is an orange coloured cushion part used inside a gear shifter, unde…"
- IEBTIIENEN004-2024-BTI141 (chapter 39, expected 3926.90): 9111.80 (90, review) · 9111.80 (90, review) · 9111.80 (50, review); correct in the top 3 in 3 of 3 runs. "The product is a snap on protective case for a smart watch. Its function is to …"
- IEBTIIENEN004-2023-BTI572 (chapter 39, expected 3923.10): 9617.00 (95, review) · 8609.00 (90, review) · 9617.00 (90, review); correct in the top 3 in 2 of 3 runs. "Celsius SSM Shipper It is used to ship Pharmaceutical Drug Substance on an inte…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (90, review) · 4202.32 (90, review) · 4202.32 (90, review); correct in the top 3 in 0 of 3 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (90, review) · 4202.22 (95, review) · 4202.22 (90, review); correct in the top 3 in 3 of 3 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (90, review) · 4202.32 (90, review) · 4202.12 (90, review); correct in the top 3 in 0 of 3 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, review) · 4202.22 (95, review) · 4202.22 (95, review); correct in the top 3 in 3 of 3 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (90, review) · 4202.12 (90, review) · 4202.12 (90, review); correct in the top 3 in 0 of 3 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (90, review) · 6112.12 (90, review) · 6112.12 (90, review); correct in the top 3 in 3 of 3 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (90, review) · 6114.30 (90, review) · 6114.30 (90, review); correct in the top 3 in 0 of 3 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, review) · 6104.33 (95, review) · 6104.33 (95, review); correct in the top 3 in 0 of 3 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- FRBTIFR-BTI-2025-08672 (chapter 61, expected 6111.20): 6209.20 (95, review) · 6111.30 (95, review) · 6111.30 (95, review); correct in the top 3 in 2 of 3 runs. "Accessoire du vêtement pour bébés se présentant sous la forme d’un bavoir de fo…"
- DEBTI52786/23-1 (chapter 61, expected 6113.00): 6203.33 (95, review) · 6203.33 (95, review) · 6203.33 (95, review); correct in the top 3 in 0 of 3 runs. "Blouson, sog. PREVENT® Warnschutz-Softshelljacke, Artikel 8060O, Größe M, Foto …"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (95, review) · 6112.41 (95, review) · 6112.41 (95, review); correct in the top 3 in 3 of 3 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (90, review) · 6204.33 (95, review) · 6204.33 (90, review); correct in the top 3 in 2 of 3 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (90, review) · 3304.99 (90, review) · 3304.99 (90, review); correct in the top 3 in 3 of 3 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.90 (95, review) · 4602.90 (95, review) · 4602.90 (95, review); correct in the top 3 in 3 of 3 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review) · 4602.19 (95, review) · 4602.19 (95, review); correct in the top 3 in 3 of 3 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, review) · 4602.90 (95, review) · 4602.90 (95, review); correct in the top 3 in 3 of 3 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (90, review) · 6305.90 (90, review) · 6305.90 (95, review); correct in the top 3 in 3 of 3 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review) · 9503.00 (95, review) · 9503.00 (95, review); correct in the top 3 in 3 of 3 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI352 (chapter 64, expected 6404.19): 6405.20 (95, review) · 6405.20 (95, review) · 6405.20 (95, review); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept) · 6404.19 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 7310.10 (90, review) · 7310.10 (95, review) · 7310.10 (95, review); correct in the top 3 in 2 of 3 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review) · 8415.82 (95, review) · 8415.82 (95, review); correct in the top 3 in 0 of 3 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.80 (90, review) · 8481.80 (90, review) · 8481.80 (90, review); correct in the top 3 in 0 of 3 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review) · 8419.89 (95, review) · 8419.89 (90, review); correct in the top 3 in 3 of 3 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7306.61 (40, ask_shipper) · 7308.90 (59, review) · 7308.90 (59, review); correct in the top 3 in 0 of 3 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3916.90 (90, review) · 3916.90 (90, review) · 3916.90 (90, review); correct in the top 3 in 0 of 3 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (90, auto_accept) · 8479.89 (90, auto_accept) · 8479.89 (90, auto_accept); correct in the top 3 in 0 of 3 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review) · 8536.30 (95, review) · 8536.30 (95, review); correct in the top 3 in 3 of 3 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (59, review) · 3925.90 (59, review) · 3925.90 (59, review); correct in the top 3 in 3 of 3 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505059567 (chapter 85, expected 8504.40): 8471.80 (90, review) · 8471.80 (95, review) · 8471.80 (90, review); correct in the top 3 in 3 of 3 runs. "Body Worn Camera Docking Station Black docking station with magnetic self-locat…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review) · 8504.31 (59, review) · 8504.31 (59, review); correct in the top 3 in 0 of 3 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept) · 9405.11 (95, auto_accept); correct in the top 3 in 3 of 3 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2025-BTI460 (chapter 95, expected 9503.00): 9506.62 (95, review) · 9506.62 (95, review) · 9506.62 (95, review); correct in the top 3 in 3 of 3 runs. "INFLATABLE SWIMMING RING, MADE FROM 100% PVC. IT IS INTENDED FOR USE BY CHILDRE…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9608.50 (95, review) · 9608.50 (95, review) · 9608.50 (95, review); correct in the top 3 in 0 of 3 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (9)

- IEBTIIENEN004-2023-BTI572 (expected 3923.10): 9617.00 (95, review) · 8609.00 (90, review) · 9617.00 (90, review)
- IEBTIIENEN004-2025-BTI449 (expected 4202.92): 4202.12 (90, review) · 4202.32 (90, review) · 4202.12 (90, review)
- IEBTIIENEN004-2024-BTI315 (expected 4202.32): 4202.32 (90, review) · 4202.32 (90, review) · 3926.90 (90, review)
- FRBTIFR-BTI-2025-08672 (expected 6111.20): 6209.20 (95, review) · 6111.30 (95, review) · 6111.30 (95, review)
- IEBTIIENEN004-2026-BTI107 (expected 6212.10): 6112.41 (95, review) · 6212.10 (95, auto_accept) · 6112.41 (95, review)
- IEBTIIENEN004-2024-BTI128 (expected 6404.19): 6404.19 (95, review) · 6402.99 (90, auto_accept) · 6404.19 (90, review)
- IEBTIIENEN004-2026-BTI124 (expected 8431.49): 7306.61 (40, ask_shipper) · 7308.90 (59, review) · 7308.90 (59, review)
- IEBTIIENEN004-2023-BTI561 (expected 8537.10): 8536.20 (95, review) · 8536.20 (95, review) · 8537.10 (95, review)
- XIBTI505065379 (expected 8505.19): 8505.19 (95, auto_accept) · 9505.90 (95, review) · 8505.19 (95, auto_accept)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 4 / 5 / 4. In every run: 4 lines, each among the lines wrong in every run above.

- IEBTIIENEN004-2024-BTI128 (expected 6404.19): run 2: 6402.99 (90)

## Iteration 6 (hs6-haiku45, anthropic/claude-haiku-4.5, 2026-10-26)

Invalid answers (retried at most 1 time): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 95: 27 / 1 · 92: 47 / 26 · 90: 0 / 1 · 88: 0 / 2 · 87: 0 / 1 · 85: 2 / 2 · 82: 2 / 1 · 78: 3 / 3 · 75: 2 / 0.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 83/120 | 107/120 | 69 | 44 | 7 | 5 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 69 | 29 | 12 | 2 | 0 | 8 | 0 | 64 | 10 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 68 | 15 | 29 | 8 |
| Run 1 | 69 | 14 | 28 | 9 |

On majority results 52 of 120 lines end wrong: 37 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 15 from the CN-8 step alone. End-to-end estimate per run: 69 of 120.

Wrong top-1 results (line × run): 37; the correct HS-6 was among the candidates shown to the model in 27 (73.0%).

Leakage guard: each line's own ruling was its nearest ruling in 110 of 120 lines (per run), among the 12 the precedent search reads in 120; the guard kept it out of the precedents.

### Lines wrong in every run (37)

- IEBTIIENEN004-2025-BTI351 (chapter 39, expected 3925.90): 8538.90 (92, auto_accept); correct in the top 3 in 1 of 1 runs. "Internal mounting bracket for infrared sensor The bracket is used to hold the s…"
- XIBTI505068468 (chapter 39, expected 3926.90): 7321.81 (78, ask_shipper); correct in the top 3 in 0 of 1 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.32 (92, review); correct in the top 3 in 1 of 1 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2024-BTI141 (chapter 39, expected 3926.90): 9111.80 (85, review); correct in the top 3 in 1 of 1 runs. "The product is a snap on protective case for a smart watch. Its function is to …"
- IEBTIIENEN004-2023-BTI572 (chapter 39, expected 3923.10): 9617.00 (92, review); correct in the top 3 in 1 of 1 runs. "Celsius SSM Shipper It is used to ship Pharmaceutical Drug Substance on an inte…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (92, review); correct in the top 3 in 0 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (92, review); correct in the top 3 in 1 of 1 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (88, review); correct in the top 3 in 0 of 1 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2024-BTI315 (chapter 42, expected 4202.32): 4202.92 (88, review); correct in the top 3 in 1 of 1 runs. "Metropolis Protection case for iPhone 11 IT ENCASES THE PHONE BY COVERING THE B…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (92, review); correct in the top 3 in 1 of 1 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (92, review); correct in the top 3 in 0 of 1 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (92, review); correct in the top 3 in 1 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (78, review); correct in the top 3 in 0 of 1 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (92, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- FRBTIFR-BTI-2025-08672 (chapter 61, expected 6111.20): 6111.30 (92, review); correct in the top 3 in 1 of 1 runs. "Accessoire du vêtement pour bébés se présentant sous la forme d’un bavoir de fo…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (92, review); correct in the top 3 in 1 of 1 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI23 (chapter 63, expected 6307.90): 6215.90 (92, review); correct in the top 3 in 1 of 1 runs. "Two strips of grosgrain textile material cut to a specified length, then attach…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (82, review); correct in the top 3 in 1 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (92, review); correct in the top 3 in 1 of 1 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (92, review); correct in the top 3 in 1 of 1 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (92, review); correct in the top 3 in 1 of 1 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (92, review); correct in the top 3 in 1 of 1 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 8303.00 (92, review); correct in the top 3 in 1 of 1 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (87, review); correct in the top 3 in 0 of 1 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.90 (92, review); correct in the top 3 in 0 of 1 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (92, review); correct in the top 3 in 1 of 1 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7326.90 (78, review); correct in the top 3 in 0 of 1 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3920.10 (92, review); correct in the top 3 in 0 of 1 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- IEBTIIENEN004-2025-BTI26 (chapter 84, expected 8471.60): 9608.30 (92, review); correct in the top 3 in 1 of 1 runs. "Wireless Pencil. The device is a touch pen which is designed for use with a cer…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (92, auto_accept); correct in the top 3 in 0 of 1 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (92, review); correct in the top 3 in 1 of 1 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (59, review); correct in the top 3 in 1 of 1 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (92, auto_accept); correct in the top 3 in 0 of 1 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.20 (90, review); correct in the top 3 in 0 of 1 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (92, auto_accept); correct in the top 3 in 1 of 1 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9608.50 (85, review); correct in the top 3 in 1 of 1 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 5. In every run: 5 lines, each among the lines wrong in every run above.

## Iteration 7 (hs6-override, google/gemini-2.5-flash, 2026-10-26)

Invalid answers (retried at most 2 times): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 98: 26 / 1 · 95: 56 / 32 · 90: 0 / 2 · 85: 1 / 1 · 80: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 83/120 | 108/120 | 67 | 53 | 0 | 3 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 67 | 33 | 10 | 4 | 0 | 6 | 0 | 64 | 17 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 12)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 74 | 9 | 29 | 8 |
| Run 1 | 74 | 9 | 28 | 9 |

On majority results 46 of 120 lines end wrong: 37 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 9 from the CN-8 step alone. End-to-end estimate per run: 74 of 120.

Wrong top-1 results (line × run): 37; the correct HS-6 was among the candidates shown to the model in 28 (75.7%).

Leakage guard: each line's own ruling was its nearest ruling in 111 of 120 lines (per run), among the 12 the precedent search reads in 120; the guard kept it out of the precedents.

### Lines wrong in every run (37)

- XIBTI505068468 (chapter 39, expected 3926.90): 7322.90 (95, review); correct in the top 3 in 0 of 1 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (95, review); correct in the top 3 in 0 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (95, review); correct in the top 3 in 1 of 1 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, review); correct in the top 3 in 1 of 1 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- FRBTIFR-BTI-2025-02100 (chapter 42, expected 4203.29): 6116.10 (95, review); correct in the top 3 in 1 of 1 runs. "Accessoire du vêtement, de type gant de protection pour tous métiers, à cinq do…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, review); correct in the top 3 in 1 of 1 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (95, review); correct in the top 3 in 1 of 1 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6101.30 (95, review); correct in the top 3 in 1 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (95, review); correct in the top 3 in 0 of 1 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (98, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (95, review); correct in the top 3 in 1 of 1 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (95, review); correct in the top 3 in 0 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, review); correct in the top 3 in 1 of 1 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- XIBTI505066180 (chapter 63, expected 6307.90): 8708.21 (95, review); correct in the top 3 in 1 of 1 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, review); correct in the top 3 in 1 of 1 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 8303.00 (59, review); correct in the top 3 in 0 of 1 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review); correct in the top 3 in 1 of 1 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.90 (95, review); correct in the top 3 in 0 of 1 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review); correct in the top 3 in 1 of 1 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7308.90 (59, review); correct in the top 3 in 0 of 1 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3926.90 (59, review); correct in the top 3 in 0 of 1 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (95, auto_accept); correct in the top 3 in 0 of 1 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review); correct in the top 3 in 1 of 1 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (95, review); correct in the top 3 in 1 of 1 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505059567 (chapter 85, expected 8504.40): 8471.80 (95, review); correct in the top 3 in 1 of 1 runs. "Body Worn Camera Docking Station Black docking station with magnetic self-locat…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review); correct in the top 3 in 0 of 1 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.30 (95, review); correct in the top 3 in 0 of 1 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review); correct in the top 3 in 1 of 1 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 3. In every run: 3 lines, each among the lines wrong in every run above.

### Precedent override (feature 008)

With the switch on, at least 4 of the nearest rulings at the model's candidate 2 or 3 choose that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the top-1 when no override fired.

| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |
|---|---|---|---|---|---|---|
| 1 | off | 83/120 | 67 | 3 | 64 | 74/120 |
| 1 | on | 92/120 | 81 | 6 | 75 | 82/120 |

Overrides that fired per run: 14, of which chose the right HS-6: 11. The rulings' majority supported the model's candidate 2 or 3 on 27 lines per run; that candidate was the right HS-6 on 16.

- run 1: XIBTI505068468 (expected 3926.90): candidate 2, 7321.81, instead of 7322.90; wrong
- run 1: IEBTIIENEN004-2024-BTI145 (expected 4202.92): candidate 3, 4202.92, instead of 4202.22; right
- run 1: FRBTIFR-BTI-2025-02100 (expected 4203.29): candidate 2, 4203.29, instead of 6116.10; right
- run 1: IEBTIIENEN004-2026-BTI106 (expected 6212.10): candidate 2, 6212.10, instead of 6112.41; right
- run 1: IEBTIIENEN004-2026-BTI108 (expected 6212.10): candidate 2, 6212.10, instead of 6112.41; right
- run 1: IEBTIIENEN004-2026-BTI107 (expected 6212.10): candidate 2, 6212.10, instead of 6112.41; right
- run 1: IEBTIIENEN004-2024-BTI5 (expected 6307.90): candidate 2, 6307.90, instead of 4602.19; right
- run 1: IEBTIIENEN004-2024-BTI8 (expected 6307.90): candidate 2, 6307.90, instead of 4602.90; right
- run 1: MTBTI2025-017 (expected 6307.90): candidate 3, 6307.90, instead of 6305.90; right
- run 1: CZBTI47/152108/2024-580000-04/01 (expected 6307.90): candidate 2, 6307.90, instead of 9503.00; right
- run 1: IEBTIIENEN004-2024-BTI122 (expected 6402.99): candidate 2, 6404.19, instead of 6402.99; wrong
- run 1: IEBTIIENEN004-2024-BTI128 (expected 6404.19): candidate 2, 6402.99, instead of 6404.19; wrong
- run 1: IEBTIIENEN004-2025-BTI336 (expected 8538.90): candidate 2, 8538.90, instead of 3925.90; right
- run 1: IEBTIIENEN004-2026-BTI222 (expected 9609.10): candidate 2, 9609.10, instead of 9609.90; right

## Iteration 8 (hs6-override-min5, google/gemini-2.5-flash, 2026-10-26)

Replay of iteration 7 (hs6-override) at OVERRIDE_MIN 5, from its stored answers: no model call.

Invalid answers (retried at most 2 times): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 98: 26 / 1 · 95: 56 / 32 · 90: 0 / 2 · 85: 1 / 1 · 80: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 83/120 | 108/120 | 67 | 53 | 0 | 3 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 67 | 33 | 10 | 4 | 0 | 6 | 0 | 64 | 17 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 12)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 74 | 9 | 29 | 8 |
| Run 1 | 74 | 9 | 28 | 9 |

On majority results 46 of 120 lines end wrong: 37 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 9 from the CN-8 step alone. End-to-end estimate per run: 74 of 120.

Wrong top-1 results (line × run): 37; the correct HS-6 was among the candidates shown to the model in 28 (75.7%).

Leakage guard: each line's own ruling was its nearest ruling in 111 of 120 lines (per run), among the 12 the precedent search reads in 120; the guard kept it out of the precedents.

### Lines wrong in every run (37)

- XIBTI505068468 (chapter 39, expected 3926.90): 7322.90 (95, review); correct in the top 3 in 0 of 1 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.32 (95, review); correct in the top 3 in 0 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI145 (chapter 42, expected 4202.92): 4202.22 (95, review); correct in the top 3 in 1 of 1 runs. "Travel bag Outer surface is made of polyester, Made from 99.9& Polyester, 0.1% …"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, review); correct in the top 3 in 1 of 1 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- FRBTIFR-BTI-2025-02100 (chapter 42, expected 4203.29): 6116.10 (95, review); correct in the top 3 in 1 of 1 runs. "Accessoire du vêtement, de type gant de protection pour tous métiers, à cinq do…"
- IEBTIIENEN004-2025-BTI227 (chapter 42, expected 4202.92): 4202.22 (95, review); correct in the top 3 in 1 of 1 runs. "BACKPACK, NYLON 840D, DETACHABLE SHOULDER STRAPS, ZIPPERED POCKETS \[Hip PAck Ol…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 4202.12 (95, review); correct in the top 3 in 1 of 1 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6101.30 (95, review); correct in the top 3 in 1 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI208 (chapter 61, expected 6109.90): 6114.30 (95, review); correct in the top 3 in 0 of 1 runs. "T-Shirt Type Garment for Unisex Undergarment for wear by a person who has a spi…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6104.33 (95, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (98, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (95, review); correct in the top 3 in 1 of 1 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (95, review); correct in the top 3 in 0 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI7 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 2 BASKETS; MADE OF 100% PAPER TWISTED INTO PAPER YARN THEN SEWED"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, review); correct in the top 3 in 1 of 1 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- XIBTI505066180 (chapter 63, expected 6307.90): 8708.21 (95, review); correct in the top 3 in 1 of 1 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, review); correct in the top 3 in 1 of 1 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 8303.00 (59, review); correct in the top 3 in 0 of 1 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review); correct in the top 3 in 1 of 1 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2025-BTI293 (chapter 84, expected 8424.90): 8481.90 (95, review); correct in the top 3 in 0 of 1 runs. "Hypotube Tip. This is a stainless-steel component used in a spray nozzle assemb…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review); correct in the top 3 in 1 of 1 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 7308.90 (59, review); correct in the top 3 in 0 of 1 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3926.90 (59, review); correct in the top 3 in 0 of 1 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (95, auto_accept); correct in the top 3 in 0 of 1 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review); correct in the top 3 in 1 of 1 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (95, review); correct in the top 3 in 1 of 1 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505059567 (chapter 85, expected 8504.40): 8471.80 (95, review); correct in the top 3 in 1 of 1 runs. "Body Worn Camera Docking Station Black docking station with magnetic self-locat…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (59, review); correct in the top 3 in 0 of 1 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.30 (95, review); correct in the top 3 in 0 of 1 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- MTBTI2025-011 (chapter 94, expected 9405.42): 9405.11 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "An emergency light fitting with LEDs, having an internal power source in the fo…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review); correct in the top 3 in 1 of 1 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 3. In every run: 3 lines, each among the lines wrong in every run above.

### Precedent override (feature 008)

With the switch on, at least 5 of the nearest rulings at the model's candidate 2 or 3 choose that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the top-1 when no override fired.

| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |
|---|---|---|---|---|---|---|
| 1 | off | 83/120 | 67 | 3 | 64 | 74/120 |
| 1 | on | 87/120 | 71 | 3 | 68 | 77/120 |

Overrides that fired per run: 4, of which chose the right HS-6: 4. The rulings' majority supported the model's candidate 2 or 3 on 27 lines per run; that candidate was the right HS-6 on 16.

- run 1: FRBTIFR-BTI-2025-02100 (expected 4203.29): candidate 2, 4203.29, instead of 6116.10; right
- run 1: IEBTIIENEN004-2024-BTI8 (expected 6307.90): candidate 2, 6307.90, instead of 4602.90; right
- run 1: MTBTI2025-017 (expected 6307.90): candidate 3, 6307.90, instead of 6305.90; right
- run 1: IEBTIIENEN004-2026-BTI222 (expected 9609.10): candidate 2, 9609.10, instead of 9609.90; right

## Iteration 9 (zh-off, google/gemini-2.5-flash, zh, query expansion off, 2026-10-27)

Note: Decision rule fixed before the results: query expansion becomes the default only if, in both languages, it is no worse on wrong auto-accepts and better on top-1 right (zh: zh-on vs zh-off; en: en-on vs hs6-override-min5).

Invalid answers (retried at most 2 times): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 95: 16 / 9 · 90: 1 / 3 · 50: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 17/30 | 26/30 | 9 | 21 | 0 | 0 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 9 | 12 | 5 | 3 | 0 | 1 | 0 | 9 | 8 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 12 | 5 | 10 | 3 |
| Run 1 | 12 | 5 | 10 | 3 |

On majority results 18 of 30 lines end wrong: 13 from the HS-6 step (the CN-8 step would have failed too on 3 of them), 5 from the CN-8 step alone. End-to-end estimate per run: 12 of 30.

Wrong top-1 results (line × run): 13; the correct HS-6 was among the candidates shown to the model in 10 (76.9%).

Leakage guard: each line's own ruling was its nearest ruling in 22 of 30 lines (per run), among the 12 the precedent search reads in 27; the guard kept it out of the precedents.

### Lines wrong in every run (13)

- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.92 (95, review); correct in the top 3 in 0 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6103.39 (90, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6110.30 (95, review); correct in the top 3 in 0 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 9605.00 (90, review); correct in the top 3 in 1 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI122 (chapter 64, expected 6402.99): 6404.19 (95, review); correct in the top 3 in 1 of 1 runs. "Ladies Sandals- PU Weave Strap Mule Sandal The sandal consists of a silicone ru…"
- IEBTIIENEN004-2024-BTI96 (chapter 73, expected 7326.90): 8207.90 (90, review); correct in the top 3 in 1 of 1 runs. "Alloy steel shank used in the production or Rotary Burs. The steel shank is wel…"
- IEBTIIENEN004-2025-BTI301 (chapter 73, expected 7325.99): 8536.69 (50, review); correct in the top 3 in 0 of 1 runs. "1. Stainless steel X5000 Housing 2. Circular Housing , with 4 Cable entries , U…"
- IEBTIIENEN004-2023-BTI579 (chapter 85, expected 8528.52): 8528.59 (95, review); correct in the top 3 in 1 of 1 runs. "14” portable LCD colour monitor. With a screen resolution of 1920 x 1080 pixels…"
- IEBTIIENEN004-2026-BTI71 (chapter 96, expected 9619.00): 6108.22 (95, review); correct in the top 3 in 1 of 1 runs. "Period Pants. They are made of knitted cotton fabric with an additional non-rem…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review); correct in the top 3 in 1 of 1 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 0. In every run: 0 lines, each among the lines wrong in every run above.

### Precedent override (feature 008)

With the switch on, at least 5 of the nearest rulings at the model's candidate 2 or 3 choose that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the top-1 when no override fired.

| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |
|---|---|---|---|---|---|---|
| 1 | off | 17/30 | 9 | 0 | 9 | 12/30 |
| 1 | on | 20/30 | 12 | 0 | 12 | 15/30 |

Overrides that fired per run: 3, of which chose the right HS-6: 3. The rulings' majority supported the model's candidate 2 or 3 on 12 lines per run; that candidate was the right HS-6 on 6.

- run 1: IEBTIIENEN004-2026-BTI106 (expected 6212.10): candidate 3, 6212.10, instead of 6112.41; right
- run 1: IEBTIIENEN004-2026-BTI107 (expected 6212.10): candidate 2, 6212.10, instead of 6112.41; right
- run 1: IEBTIIENEN004-2026-BTI71 (expected 9619.00): candidate 2, 9619.00, instead of 6108.22; right

## Iteration 10 (zh-on, google/gemini-2.5-flash, zh, query expansion on, 2026-10-27)

Note: Decision rule fixed before the results: query expansion becomes the default only if, in both languages, it is no worse on wrong auto-accepts and better on top-1 right (zh: zh-on vs zh-off; en: en-on vs hs6-override-min5).

Invalid answers (retried at most 2 times): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 95: 17 / 10 · 90: 0 / 2 · 50: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 17/30 | 25/30 | 15 | 15 | 0 | 2 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 15 | 11 | 3 | 0 | 0 | 1 | 0 | 13 | 4 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 12 | 5 | 10 | 3 |
| Run 1 | 12 | 5 | 10 | 3 |

On majority results 18 of 30 lines end wrong: 13 from the HS-6 step (the CN-8 step would have failed too on 3 of them), 5 from the CN-8 step alone. End-to-end estimate per run: 12 of 30.

Wrong top-1 results (line × run): 13; the correct HS-6 was among the candidates shown to the model in 9 (69.2%).

Leakage guard: each line's own ruling was its nearest ruling in 24 of 30 lines (per run), among the 12 the precedent search reads in 29; the guard kept it out of the precedents.

### Lines wrong in every run (13)

- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.92 (95, review); correct in the top 3 in 0 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6103.33 (95, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (95, review); correct in the top 3 in 0 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 9616.20 (90, review); correct in the top 3 in 1 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- IEBTIIENEN004-2024-BTI122 (chapter 64, expected 6402.99): 6404.19 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "Ladies Sandals- PU Weave Strap Mule Sandal The sandal consists of a silicone ru…"
- IEBTIIENEN004-2024-BTI96 (chapter 73, expected 7326.90): 7228.40 (90, review); correct in the top 3 in 1 of 1 runs. "Alloy steel shank used in the production or Rotary Burs. The steel shank is wel…"
- IEBTIIENEN004-2025-BTI301 (chapter 73, expected 7325.99): 8538.90 (50, review); correct in the top 3 in 0 of 1 runs. "1. Stainless steel X5000 Housing 2. Circular Housing , with 4 Cable entries , U…"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.30 (95, review); correct in the top 3 in 1 of 1 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- XIBTI505070096 (chapter 94, expected 9403.20): 9404.90 (95, auto_accept); correct in the top 3 in 0 of 1 runs. "This is an Elevated Cot dog bed with sides. A cot or bed for dogs is a speciall…"
- IEBTIIENEN004-2026-BTI71 (chapter 96, expected 9619.00): 6108.22 (95, review); correct in the top 3 in 1 of 1 runs. "Period Pants. They are made of knitted cotton fabric with an additional non-rem…"
- IEBTIIENEN004-2026-BTI222 (chapter 96, expected 9609.10): 9609.90 (95, review); correct in the top 3 in 1 of 1 runs. "Sketching and drawing set consisting of the following: • 44 pencils • 7 charcoa…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 2. In every run: 2 lines, each among the lines wrong in every run above.

### Precedent override (feature 008)

With the switch on, at least 5 of the nearest rulings at the model's candidate 2 or 3 choose that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the top-1 when no override fired.

| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |
|---|---|---|---|---|---|---|
| 1 | off | 17/30 | 15 | 2 | 13 | 12/30 |
| 1 | on | 17/30 | 15 | 2 | 13 | 12/30 |

Overrides that fired per run: 0, of which chose the right HS-6: 0. The rulings' majority supported the model's candidate 2 or 3 on 10 lines per run; that candidate was the right HS-6 on 7.

## Iteration 11 (en-on, google/gemini-2.5-flash, en, query expansion on, 2026-10-27)

Note: Decision rule fixed before the results: query expansion becomes the default only if, in both languages, it is no worse on wrong auto-accepts and better on top-1 right (zh: zh-on vs zh-off; en: en-on vs hs6-override-min5).

Invalid answers (retried at most 2 times): run 1: 0 retried (0 not valid JSON, 0 not the schema), 0 calls still invalid, 0 lines failed.

The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: 98: 11 / 0 · 95: 68 / 33 · 90: 1 / 3 · 85: 1 / 1 · 65: 0 / 1 · 50: 0 / 1.

| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |
|---|---|---|---|---|---|---|
| 1 | 81/120 | 109/120 | 64 | 56 | 0 | 3 |

### Vote gate

Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Lost: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.

| Run | Vote agrees | Vote disagrees | Tie | Share low | No ruling | Not gated | No ruling, to review | Right auto-accepts | Lost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 64 | 32 | 14 | 4 | 0 | 6 | 0 | 61 | 18 |

### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration 11)

The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. Majority: the majority top-1 of each eval; run k: run k of both.

| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | HS-6 wrong, CN-8 wrong |
|---|---|---|---|---|
| Majority | 66 | 15 | 31 | 8 |
| Run 1 | 65 | 16 | 32 | 7 |

On majority results 54 of 120 lines end wrong: 39 from the HS-6 step (the CN-8 step would have failed too on 8 of them), 15 from the CN-8 step alone. End-to-end estimate per run: 65 of 120.

Wrong top-1 results (line × run): 39; the correct HS-6 was among the candidates shown to the model in 28 (71.8%).

Leakage guard: each line's own ruling was its nearest ruling in 110 of 120 lines (per run), among the 12 the precedent search reads in 120; the guard kept it out of the precedents.

### Lines wrong in every run (39)

- XIBTI505068468 (chapter 39, expected 3926.90): 7322.90 (95, review); correct in the top 3 in 0 of 1 runs. "A gas fuelled space heater It’s function is to provide heat by burning gas. Typ…"
- IEBTIIENEN004-2024-BTI133 (chapter 39, expected 3926.90): 4202.92 (95, review); correct in the top 3 in 1 of 1 runs. "This is a protection case for Apple Airpods. Designed to Keep product protected…"
- IEBTIIENEN004-2025-BTI463 (chapter 39, expected 3926.90): 9606.30 (90, review); correct in the top 3 in 1 of 1 runs. "The product is an orange coloured cushion part used inside a gear shifter, unde…"
- IEBTIIENEN004-2024-BTI284 (chapter 42, expected 4202.12): 4202.92 (95, review); correct in the top 3 in 1 of 1 runs. "Slim lightweight structured ipad sleeve with front zippered pocket for accessor…"
- IEBTIIENEN004-2025-BTI449 (chapter 42, expected 4202.92): 4202.12 (95, review); correct in the top 3 in 1 of 1 runs. "Multifunction pencil case with calculator and pencil sharpener. The predominant…"
- IEBTIIENEN004-2024-BTI315 (chapter 42, expected 4202.32): 3926.90 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "Metropolis Protection case for iPhone 11 IT ENCASES THE PHONE BY COVERING THE B…"
- FRBTIFR-BTI-2025-02100 (chapter 42, expected 4203.29): 6116.10 (95, review); correct in the top 3 in 1 of 1 runs. "Accessoire du vêtement, de type gant de protection pour tous métiers, à cinq do…"
- IEBTIIENEN004-2024-BTI261 (chapter 42, expected 4202.92): 3926.90 (95, review); correct in the top 3 in 1 of 1 runs. "PROTECTION CASE FOR MACBOOK PRO 13”. IT’S COMPOSED OF HARD PLASTIC AND COVERS T…"
- IEBTIIENEN004-2024-BTI132 (chapter 61, expected 6102.30): 6112.12 (95, review); correct in the top 3 in 1 of 1 runs. "This garment is a full zip fleece. This is a knitted recycled 100% polyester tw…"
- IEBTIIENEN004-2024-BTI90 (chapter 61, expected 6101.30): 6103.33 (95, review); correct in the top 3 in 0 of 1 runs. "This is a knitted jacket type garment. This is a knitted garment and is made of…"
- DEBTI52786/23-1 (chapter 61, expected 6113.00): 6103.33 (95, review); correct in the top 3 in 0 of 1 runs. "Blouson, sog. PREVENT® Warnschutz-Softshelljacke, Artikel 8060O, Größe M, Foto …"
- IEBTIIENEN004-2026-BTI106 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI108 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "Women's bikini top Consists of two separate fabric lined cups; Two vertical sel…"
- IEBTIIENEN004-2026-BTI107 (chapter 62, expected 6212.10): 6112.41 (95, review); correct in the top 3 in 1 of 1 runs. "A women's bandeau bikini top It consists of two removable foam cups inside whic…"
- DEBTI7623/25-1 (chapter 62, expected 6202.40): 6204.33 (95, review); correct in the top 3 in 0 of 1 runs. "Blouson, sog. Jacke für Frauen, Größe M, Foto siehe Anlage, - aus ca. 0,3 mm di…"
- IEBTIIENEN004-2026-BTI228 (chapter 63, expected 6307.90): 3304.99 (95, review); correct in the top 3 in 1 of 1 runs. "A comprehensive eyelid hygiene kit designed to cleanse, soothe, and support eye…"
- SEBTITV-2026-01096 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Varan är enligt uppgift en konfektionerad hundleksak i form av en gris. Varan ä…"
- IEBTIIENEN004-2024-BTI5 (chapter 63, expected 6307.90): 4602.19 (95, review); correct in the top 3 in 1 of 1 runs. "SET OF 3 PAPER ROPE BASKETS; IT IS MADE OF 100% PAPER TWISTED. MANUFACTURE PROC…"
- IEBTIIENEN004-2024-BTI8 (chapter 63, expected 6307.90): 4602.90 (95, review); correct in the top 3 in 1 of 1 runs. "OPEN WEAVE BASKET; MADE OF 100% PAPER TWISTED PAPER ROPE AND IRON FRAME. IT CON…"
- MTBTI2025-018 (chapter 63, expected 6307.90): 6306.12 (95, review); correct in the top 3 in 1 of 1 runs. "Woven polyester fabric, 100% waterproof. Hemmed all round and can be tightened …"
- XIBTI505066180 (chapter 63, expected 6307.90): 9401.99 (95, review); correct in the top 3 in 0 of 1 runs. "The product is a seat belt pad to be used in conjunction with the car booster s…"
- MTBTI2025-017 (chapter 63, expected 6307.90): 6305.90 (95, review); correct in the top 3 in 1 of 1 runs. "Cylindrical woven finish textile article with a zip fastner or velcro at the to…"
- CZBTI47/152108/2024-580000-04/01 (chapter 63, expected 6307.90): 9503.00 (95, review); correct in the top 3 in 1 of 1 runs. "Dle deklarovaných údajů se jedná o textilní vycpávaný výrobek - hračku pro kočk…"
- IEBTIIENEN004-2024-BTI356 (chapter 64, expected 6405.20): 6404.19 (95, auto_accept); correct in the top 3 in 1 of 1 runs. "LADIES FAUX FUR MULE STYLE SLIPPER WITH A CLOSED IN TOE. UPPERS OF TEXTILE, OUT…"
- XIBTI505060394 (chapter 73, expected 7326.90): 8303.00 (59, review); correct in the top 3 in 1 of 1 runs. "A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is …"
- IEBTIIENEN004-2026-BTI279 (chapter 73, expected 7318.15): 7318.19 (95, review); correct in the top 3 in 1 of 1 runs. "Mild Steel Threaded Bar Zinc Plated CR3 (for increased corrosion resistance). I…"
- IEBTIIENEN004-2026-BTI19 (chapter 84, expected 8415.10): 8415.82 (95, review); correct in the top 3 in 1 of 1 runs. "Railway HVAC Systems. These are self contained systems that regulate the interi…"
- IEBTIIENEN004-2026-BTI68 (chapter 84, expected 8479.89): 8419.89 (95, review); correct in the top 3 in 1 of 1 runs. "A buffer preparation skid assembly. This is a stainless-steel vessel with a hea…"
- IEBTIIENEN004-2026-BTI124 (chapter 84, expected 8431.49): 8431.20 (59, review); correct in the top 3 in 0 of 1 runs. "This is an assembly for use in a Straddle Carrier Product. It consists of a squ…"
- IEBTIIENEN004-2026-BTI105 (chapter 84, expected 8474.90): 3926.90 (59, review); correct in the top 3 in 0 of 1 runs. "Machine Parts. These are Polyethylene Plastic parts that are used as wear strip…"
- MTBTI2024-002 (chapter 84, expected 8424.89): 8479.89 (95, auto_accept); correct in the top 3 in 0 of 1 runs. "A housing container made of plastic or steel which incorporates a simple suctio…"
- IEBTIIENEN004-2026-BTI60 (chapter 85, expected 8538.90): 8536.30 (95, review); correct in the top 3 in 1 of 1 runs. "RESIDUAL CURRENT DETECTION MODULE CONSISTING OF A SENSOR PRINTED CIRCUIT BOARD …"
- IEBTIIENEN004-2025-BTI336 (chapter 85, expected 8538.90): 3925.90 (95, review); correct in the top 3 in 1 of 1 runs. "IT IS MADE OF PLASTIC AND IS USED TO HOLD THE SENSOR ON THE CEILING SO THAT ONL…"
- XIBTI505059567 (chapter 85, expected 8504.40): 8471.80 (95, review); correct in the top 3 in 1 of 1 runs. "Body Worn Camera Docking Station Black docking station with magnetic self-locat…"
- XIBTI505068566 (chapter 85, expected 8504.40): 8504.31 (50, review); correct in the top 3 in 0 of 1 runs. "This product is a transformer Initiates the start up of a pump, regulates flow …"
- IEBTIIENEN004-2023-BTI561 (chapter 85, expected 8537.10): 8536.30 (95, review); correct in the top 3 in 0 of 1 runs. "FUSEBOX WHICH CONTAINS AN RCD (RESIDUAL CURRENT DEVICE) AND 2 MINI CIRCUIT BREA…"
- XIBTI505070096 (chapter 94, expected 9403.20): 9401.49 (90, review); correct in the top 3 in 0 of 1 runs. "This is an Elevated Cot dog bed with sides. A cot or bed for dogs is a speciall…"
- IEBTIIENEN004-2026-BTI72 (chapter 96, expected 9619.00): 6108.22 (95, review); correct in the top 3 in 1 of 1 runs. "Period Pants. They are made of knitted nylon fabric with an additional non-remo…"
- IEBTIIENEN004-2026-BTI71 (chapter 96, expected 9619.00): 6108.21 (95, review); correct in the top 3 in 1 of 1 runs. "Period Pants. They are made of knitted cotton fabric with an additional non-rem…"

### Lines whose top-1 differed between runs (0)

### Wrong but auto-accepted (the HS-6 layer)

Per run: 3. In every run: 3 lines, each among the lines wrong in every run above.

### Precedent override (feature 008)

With the switch on, at least 5 of the nearest rulings at the model's candidate 2 or 3 choose that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the top-1 when no override fired.

| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |
|---|---|---|---|---|---|---|
| 1 | off | 81/120 | 64 | 3 | 61 | 65/120 |
| 1 | on | 83/120 | 66 | 3 | 63 | 67/120 |

Overrides that fired per run: 2, of which chose the right HS-6: 2. The rulings' majority supported the model's candidate 2 or 3 on 26 lines per run; that candidate was the right HS-6 on 14.

- run 1: FRBTIFR-BTI-2025-02100 (expected 4203.29): candidate 2, 4203.29, instead of 6116.10; right
- run 1: IEBTIIENEN004-2026-BTI72 (expected 9619.00): candidate 2, 9619.00, instead of 6108.22; right

Model: google/gemini-2.5-flash. Line-by-line results of the latest run: `tests/eval/hs6_eval.json`; since feature 007 each run also keeps its own, `tests/eval/hs6_eval_<tag>.json`; earlier runs are in the git history of `hs6_eval.json`.
