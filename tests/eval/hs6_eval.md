# HS-6 evaluation report (feature 006)

- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's 120 EBTI rulings (built 2026-10-23); a line's correct HS-6 is the first six digits of its ruling's CN-8.
- **Method**: each ruling's goods description, as given, is a new line through the app's path: the description check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold 85, ask floor 50). A line's own ruling is never a precedent (leave-one-out); ruling validity on the set's build date. `python tests/eval/hs6_eval.py --repeat 3`.
- **Top-1** is the first candidate; a line without one (a stop word, a failure) is a miss. **In top 3**: the correct HS-6 among the candidates the clerk picks from on review. **Majority**: the most frequent top-1 over the runs (a tie goes to the earliest run). **Wrong, auto-accepted**: routed to auto-accept with a wrong top-1; the CN-8 step then runs on the wrong HS-6.

| Iteration | Run on | Tag | Runs | Top-1 per run | Majority top-1 | In top 3 per run | Same top-1 | Same route | Wrong, auto-accepted per run | End to end per run | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-25 | hs6-baseline | 3 | 72 / 68 / 69 of 120 | 69/120 | 103 / 103 / 101 of 120 | 114/120 | 119/120 | 43 / 48 / 46 | 59 / 54 / 56 of 120 | $0.1932 (€0.1778), 350 s |

## Iteration 1 (hs6-baseline, 2026-10-25)

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

Model: openai/gpt-4o-mini. Line-by-line results of the latest run: `tests/eval/hs6_eval.json`; earlier runs are in the git history of that file.
