# CN-8 evidence diagnosis: why lines go to the shipper

Data: iteration 8 (tag "evidence-diagnosis"), 3 runs of 120 lines of the fixed EBTI set. Same prompt (prompt-evidence-v2) and settings as iteration 7, run again because iteration 7 did not log the model's raw output. Offline analysis of `tests/eval/cn8_eval.json` by `tests/eval/cn8_evidence_diagnosis.py`; no API call.

## 1. Asks by cause

Every row the CN-8 step sent to the shipper: 36 of 360 (line × run). Each ask goes to the first class that fits, in this order:

1. **model-declined**: the model set attribute_visible false or cn8 null. The code then checks no quote.
2. **source-confusion**: a fragment of the quote that is not words of the description appears, as a phrase, in a CN-8 label path, the HS-6 label or a ruling excerpt sent in the same request.
3. **near-miss**: every such fragment matches the description once case, whitespace, punctuation and line breaks are removed, or at a fuzzy partial ratio of 90 or more.
4. **other**.

Fragments are the quote split at ";". A fragment is words of the description when it passes the code's own evidence check (`agent.routing.evidence_in_line`).

| Class | Asks | Correct CN-8 in the raw output |
|---|---|---|
| a) source-confusion | 24 | 18 |
| b) near-miss | 3 | 3 |
| c) model-declined | 0 | 0 |
| d) other | 9 | 7 |
| All asks | 36 | 28 |

### d) other: quote and description

| Line | Run | Raw CN-8 (expected) | Quote | Description |
|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI264 | 1 | 42029211 (42029291) | Bag for carrying laptop / conveyance of goods or personal effects; intended for the transport of goods | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| DEBTI16524/26-1 | 1 | 64029998 (64029998) | als Frauenschuhe erkennbar; Slipper und andere indoor footwear | Slipper, Größe 37, Foto siehe Anlage,<br>- mit Laufsohlen aus laut Antrag Kunststoff,<br>- mit Oberteil (geschlossenes Blatt) aus Kunststoff (Spinnstoff mit einer mit bloßem Auge<br>  wahrnehmbaren Außenschicht aus Kunststoff, den größten Teil der Außenfläche bildend) und<br>  Spinnstoffen,<br>- über dem Spann mit Strasssteinchen verziert,<br>- nicht den Knöchel bedeckend,<br>- ohne Metallschutz in der Vorderkappe,<br>- mit einer Länge der Innensohle von ca. 24﻿,﻿7 cm,<br>- als Frauenschuhe erkennbar.<br><br>"Schuhe, andere als in der Position 6401 genannte, mit Laufsohlen und Oberteil aus Kunststoff,<br> andere als in den Unterpositionen (KN) 6402 1210 bis 6402 9950 genannte, mit einer Länge der<br> Innensohle von mehr als 24 cm, für Frauen" |
| IEBTIIENEN004-2025-BTI331 | 1 | 73089098 (73089098) | used for agricultural fencing; to be worn when doing sports | A high Tensile Steel Y Shaped Fencing Post<br>The product is used for agricultural fencing. It is driven 2 ft into the ground and wire fence netting is then attached to the Y shaped fencing post<br>1.8m long hot dipped galvanised steel Y shaped post 11 spring loaded clips at various hights<br>High Tensile galvanised steel 2.5m wall thickness<br>Manufactured from high tensile steel coil, that is then rolled and welded, cut and laser welded, punched with a steel punch machine, hot-dipped galvanised. Aluminium Clips are assembled with a stainless steel spring and then riveted on.<br><br>Most defining feature is the Y shape and the spring loaded clip. (A patented spring loaded clip is used) |
| IEBTIIENEN004-2025-BTI26 | 1 | 84716070 (84716070) | designed for use with a certain type of tablet; for bediening van het touchscreen van een tablet of smartphone, om te kunnen tekenen, schrijven en dergelijke | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |
| IEBTIIENEN004-2025-BTI264 | 2 | 42029211 (42029291) | intended for the transport of goods; bag for carrying laptop | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| IEBTIIENEN004-2025-BTI26 | 2 | 84716070 (84716070) | designed for use with a certain type of tablet; for bediening van het touchscreen van een tablet of smartphone, om te kunnen tekenen, schrijven en dergelijke | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |
| IEBTIIENEN004-2025-BTI264 | 3 | 42029291 (42029291) | intended for storing and transporting goods; bag for carrying laptop | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| IEBTIIENEN004-2025-BTI26 | 3 | 84716070 (84716070) | designed for use with a certain type of tablet; for bediening van het touchscreen van een tablet of smartphone, om te kunnen tekenen, schrijven en dergelijke | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |
| IEBTIIENEN004-2026-BTI222 | 3 | 96091090 (96091090) | the set consists of 44 pencils; 7 charcoal sticks; 1 pen; Sketchbook / drawing pad / instructional or practice book; Craft knife; Pencil extender; Erasers; Pencil sharpener | Sketching and drawing set consisting of the following:<br>•	44 pencils<br>•	7 charcoal sticks<br>•	1 pen<br>•	Sketchbook / drawing pad / instructional or practice book<br>•	Craft knife<br>•	Pencil extender<br>•	Erasers<br>•	Pencil sharpener<br><br>All items are stored in a zip up carrying case that contains compartments and elastic holders for the tools. |

1 of these 9 asks quote a phrase of the CN-8 system prompt itself: IEBTIIENEN004-2025-BTI331 (run 1).

## 2. Ruling disagreement

- Lines whose rulings sent span more than one CN-8: 109 of 120 in every run (109 in at least one run).
- Lines wrong in the majority result: 29. The model's own pick (the majority of its raw CN-8 outputs, before the evidence check) was the expected CN-8 on 8, another CN-8 on 21, and none on 0.
- Of the 21 lines picked at another CN-8, 19 had rulings at both the expected and the picked CN-8 among those sent in every run (19 in at least one run).

| Line | Expected | Model's pick | Majority result | Rulings at both, every run | CN-8 lines of the rulings sent |
|---|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI351 | 39259010 | 39259010 | ask | — | 39259010, 39259020, 39259080 |
| IEBTIIENEN004-2024-BTI284 | 42021291 | 42021219 | 42021219 | yes | 42021211, 42021219, 42021250, 42021291, 42021299 |
| IEBTIIENEN004-2024-BTI239 | 42029298 | 42029291 | 42029291 | yes | 42029211, 42029219, 42029291, 42029298 |
| IEBTIIENEN004-2025-BTI264 | 42029291 | 42029211 | ask | yes | 42029211, 42029219, 42029291, 42029298 |
| FRBTIFR-BTI-2025-02100 | 42032910 | 42032910 | ask | — | 42032910, 42032990 |
| IEBTIIENEN004-2025-BTI227 | 42029298 | 42029291 | 42029291 | yes | 42029211, 42029219, 42029291, 42029298 |
| IEBTIIENEN004-2024-BTI208 | 61099020 | 61099090 | 61099090 | no | 61099020 |
| FRBTIFR-BTI-2025-08672 | 61112090 | 61112090 | ask | — | 61112090 |
| IEBTIIENEN004-2026-BTI108 | 62121090 | 62121090 | ask | — | 62121090 |
| IEBTIIENEN004-2026-BTI74 | 62121090 | 62121090 | ask | — | 62121090 |
| SEBTITV-2026-01096 | 63079010 | 63079098 | 63079098 | yes | 63079010, 63079091, 63079093, 63079098 |
| XIBTI505066180 | 63079010 | 63079098 | 63079098 | yes | 63079010, 63079091, 63079093, 63079098 |
| IEBTIIENEN004-2024-BTI122 | 64029939 | 64029931 | 64029931 | yes | 64029931, 64029939, 64029991, 64029993 |
| DEBTI16524/26-1 | 64029998 | 64029950 | 64029950 | no | 64029931, 64029939, 64029993, 64029996, 64029998 |
| IEBTIIENEN004-2025-BTI77 | 73181552 | 73181535 | ask | yes | 73181535, 73181542, 73181548, 73181552, 73181582 |
| IEBTIIENEN004-2025-BTI378 | 73170020 | 73170060 | 73170060 | yes | 73170020, 73170060, 73170080 |
| IEBTIIENEN004-2026-BTI255 | 84213985 | 84213925 | ask | yes | 84213925, 84213985 |
| IEBTIIENEN004-2025-BTI26 | 84716070 | 84716070 | ask | — | 84716060, 84716070 |
| IEBTIIENEN004-2026-BTI60 | 85389099 | 85389091 | 85389091 | yes | 85389091, 85389099 |
| IEBTIIENEN004-2023-BTI579 | 85285210 | 85285210 | ask | — | 85285210, 85285291, 85285299 |
| XIBTI505059567 | 85044060 | 85044083 | 85044083 | yes | 85044060, 85044083, 85044087, 85044095 |
| IEBTIIENEN004-2023-BTI625 | 85285210 | 85285210 | ask | — | 85285210, 85285291, 85285299 |
| XIBTI505070292 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| XIBTI505070488 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| XIBTI505070096 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| IEBTIIENEN004-2025-BTI38 | 95030041 | 95030049 | 95030049 | yes | 95030021, 95030041, 95030049, 95030070, 95030099 |
| IEBTIIENEN004-2026-BTI72 | 96190050 | 96190040 | 96190040 | yes | 96190040, 96190050, 96190071, 96190079, 96190089 |
| DEBTI47340/24-1 | 96039099 | 96039091 | 96039091 | yes | 96039010, 96039091, 96039099 |
| DEBTI59675/24-1 | 96039099 | 96039091 | 96039091 | yes | 96039010, 96039091, 96039099 |

## 3. Confidence of the raw output

Every raw output, by attribute_visible; the visible ones also by the evidence check. The prompt asks for 85-98 when the evidence words state the deciding attribute and 70-84 when the choice is inferred, so a level-b answer (the attribute follows from stated facts) belongs in 70-84.

| Confidence | Visible: all | Visible, evidence passed | Visible, evidence rejected | Visible, cn8 null (not checked) | Not visible |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |
| 1–69 | 0 | 0 | 0 | 0 | 0 |
| 70–84 | 1 | 1 | 0 | 0 | 0 |
| 85–98 | 359 | 323 | 36 | 0 | 0 |
| 99–100 | 0 | 0 | 0 | 0 | 0 |
| All | 360 | 324 | 36 | 0 | 0 |

Exact values, visible: 85 × 320, 95 × 39, 75 × 1.
