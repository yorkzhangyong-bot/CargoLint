# CN-8 evidence diagnosis: why lines go to the shipper

Data: iteration 9 (tag "evidence-source-v1"), 3 runs of 120 lines of the fixed EBTI set; evidence-source-v1: goods description in its own <goods> block; the prompt allows quotes only from it, with new level-b examples (knife, hose, desk lamp); the evidence check normalises accents and line breaks and accepts a fragment found as a phrase or a run of words at 90 %; 3 runs, the row shows run 1. Offline analysis of `tests/eval/cn8_eval.json` by `tests/eval/cn8_evidence_diagnosis.py`; no API call.

## 1. Asks by cause

Every row the CN-8 step sent to the shipper: 26 of 360 (line × run). Each ask goes to the first class that fits, in this order:

1. **model-declined**: the model set attribute_visible false or cn8 null. The code then checks no quote.
2. **source-confusion**: a fragment of the quote that is not words of the description appears, as a phrase, in a CN-8 label path, the HS-6 label or a ruling excerpt sent in the same request.
3. **near-miss**: every such fragment matches the description once case, whitespace, punctuation and line breaks are removed, or at a fuzzy partial ratio of 90 or more.
4. **other**.

Fragments are the quote split at ";". A fragment is words of the description when it passes the code's own evidence check (`agent.routing.evidence_in_line`).

| Class | Asks | Correct CN-8 in the raw output |
|---|---|---|
| a) source-confusion | 12 | 10 |
| b) near-miss | 1 | 1 |
| c) model-declined | 0 | 0 |
| d) other | 13 | 10 |
| All asks | 26 | 21 |

### d) other: quote and description

| Line | Run | Raw CN-8 (expected) | Quote | Description |
|---|---|---|---|---|
| IEBTIIENEN004-2023-BTI572 | 1 | 39231090 (39231090) | used to ship Pharmaceutical Drug Substance; transport and packaging | Celsius SSM Shipper<br>It is used to ship Pharmaceutical Drug Substance on an international level<br>Aluminum Pallet Base, LLDPE exterior, Fiberglass interior,Polyurethane Insulation |
| IEBTIIENEN004-2025-BTI264 | 1 | 42029211 (42029291) | Bag for carrying laptop; conveyance of goods or personal effects; intended for the transport of goods | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| XIBTI505060394 | 1 | 73269098 (73269098) | designed for the purpose of securely storing tools and equipment; made of steel | A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is approximately 60KG, colour is black and grey with the company logo on the front and sides<br>It is designed for the purpose of securely storing tools and equipment.<br>Construction is of steel – 2-5mm made by rolling, bending, cutting and welding.<br>It features 2 5-lever locks to secure the lid closed. The lid has gas struts to hold it open. On the bottom of the box are mounting points to enable the box to be bolted to the floor of a vehicle. |
| IEBTIIENEN004-2025-BTI26 | 1 | 84716070 (84716070) | designed for use with a certain type of tablet; for use with a tablet | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |
| IEBTIIENEN004-2025-BTI351 | 2 | 39259010 (39259010) | Internal mounting bracket for infrared sensor; hold the sensor on the ceiling; intended to be fixed | Internal mounting bracket for infrared sensor<br>The bracket is used to hold the sensor on the ceiling so that only the bracket and not the sensor is visible. The sensor can be used without the bracket.<br>The product is made of ABS Plastic |
| IEBTIIENEN004-2025-BTI264 | 2 | 42029211 (42029291) | Bag for carrying laptop; intended for the conveyance of goods or personal effects | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| IEBTIIENEN004-2025-BTI26 | 2 | 84716070 (84716070) | designed for use with a certain type of tablet; for drawing, writing and similar activities | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |
| IEBTIIENEN004-2025-BTI351 | 3 | 39259010 (39259010) | mounting bracket for infrared sensor; hold the sensor on the ceiling; intended to be fixed | Internal mounting bracket for infrared sensor<br>The bracket is used to hold the sensor on the ceiling so that only the bracket and not the sensor is visible. The sensor can be used without the bracket.<br>The product is made of ABS Plastic |
| IEBTIIENEN004-2023-BTI572 | 3 | 39231090 (39231090) | used to ship Pharmaceutical Drug Substance; transport and packaging | Celsius SSM Shipper<br>It is used to ship Pharmaceutical Drug Substance on an international level<br>Aluminum Pallet Base, LLDPE exterior, Fiberglass interior,Polyurethane Insulation |
| IEBTIIENEN004-2025-BTI264 | 3 | 42029211 (42029291) | Bag for carrying laptop; conveyance of goods or personal effects; intended for the storage and transport of goods | Back-pack / Rucksack<br>Bag for carrying laptop / conveyance of goods or personal effects<br>Black in colour, 5 separate zipped compartments in different sizes, each bag is packaged in clear transparent.  One comparted at the rear of the bag has section within to secure a laptop.  Black netting pocket on both side of the bag.  Handle on top of bag, adjustable straps to allow the bag to be carried on a person's back & adjustable luggage strap with quick release buckle (nylon & pvc).    Size approx. Width: 35CM / Depth: 16CM / Height: 40cm<br>Plastic / Synthetic Textile material<br>100% 600D (denier) Polyester. |
| IEBTIIENEN004-2024-BTI128 | 3 | 64041990 (64041990) | Women’s Sandals; glass beaded sandal; outdoor footwear | Women’s Sandals  – The upper material is textile fully covered with glass beads, the underlying material between the beads is not visible.<br>The outer sole is made of rubber/plastic.<br>The glass beaded sandal is made of 100% TPR for outsole; 100% glass beads with textile lining for uppers. The glass beads fully covered the textile material |
| XIBTI505060394 | 3 | 73269098 (73269098) | designed for the purpose of securely storing tools and equipment; made of steel | A metal box with a hinged lid measuring 625(D) x 1210(W) x 645mm(H). Weight is approximately 60KG, colour is black and grey with the company logo on the front and sides<br>It is designed for the purpose of securely storing tools and equipment.<br>Construction is of steel – 2-5mm made by rolling, bending, cutting and welding.<br>It features 2 5-lever locks to secure the lid closed. The lid has gas struts to hold it open. On the bottom of the box are mounting points to enable the box to be bolted to the floor of a vehicle. |
| IEBTIIENEN004-2025-BTI26 | 3 | 84716070 (84716070) | designed for use with a certain type of tablet; for drawing, writing and similar activities | Wireless Pencil.<br><br>The device is a touch pen which is designed for use with a certain type of tablet. It contains a plastic housing, rechargeable battery and replaceable plastic tips. It connects to the tablet via a Bluetooth connection and also charges inductively through the tablet.<br>It includes a touch surface that supports double-tapping, it has palm rejection and pressure & tilt sensitivity. It measures 166 mm (6.53 inches) in length, 0.35 inch (8.9 mm) in diameter and it weighs 19.15 grams (0.68 ounces). |

0 of these 13 asks quote a phrase of the CN-8 system prompt itself.

## 2. Ruling disagreement

- Lines whose rulings sent span more than one CN-8: 109 of 120 in every run (109 in at least one run).
- Lines wrong in the majority result: 26. The model's own pick (the majority of its raw CN-8 outputs, before the evidence check) was the expected CN-8 on 6, another CN-8 on 20, and none on 0.
- Of the 20 lines picked at another CN-8, 18 had rulings at both the expected and the picked CN-8 among those sent in every run (18 in at least one run).

| Line | Expected | Model's pick | Majority result | Rulings at both, every run | CN-8 lines of the rulings sent |
|---|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI351 | 39259010 | 39259010 | ask | — | 39259010, 39259020, 39259080 |
| IEBTIIENEN004-2023-BTI572 | 39231090 | 39231090 | ask | — | 39231010, 39231090 |
| IEBTIIENEN004-2024-BTI284 | 42021291 | 42021219 | 42021219 | yes | 42021211, 42021219, 42021250, 42021291, 42021299 |
| IEBTIIENEN004-2024-BTI239 | 42029298 | 42029291 | 42029291 | yes | 42029211, 42029219, 42029291, 42029298 |
| IEBTIIENEN004-2025-BTI264 | 42029291 | 42029211 | ask | yes | 42029211, 42029219, 42029291, 42029298 |
| IEBTIIENEN004-2025-BTI227 | 42029298 | 42029291 | 42029291 | yes | 42029211, 42029219, 42029291, 42029298 |
| IEBTIIENEN004-2024-BTI208 | 61099020 | 61099090 | 61099090 | no | 61099020 |
| FRBTIFR-BTI-2025-08672 | 61112090 | 61112090 | ask | — | 61112090 |
| SEBTITV-2026-01096 | 63079010 | 63079098 | 63079098 | yes | 63079010, 63079091, 63079093, 63079098 |
| XIBTI505066180 | 63079010 | 63079098 | 63079098 | yes | 63079010, 63079091, 63079093, 63079098 |
| IEBTIIENEN004-2024-BTI122 | 64029939 | 64029931 | ask | yes | 64029931, 64029939, 64029991, 64029993 |
| DEBTI16524/26-1 | 64029998 | 64029950 | 64029950 | no | 64029931, 64029939, 64029993, 64029996, 64029998 |
| XIBTI505060394 | 73269098 | 73269098 | ask | — | 73269040, 73269094, 73269096, 73269098 |
| IEBTIIENEN004-2025-BTI77 | 73181552 | 73181535 | 73181535 | yes | 73181535, 73181542, 73181548, 73181552, 73181582 |
| IEBTIIENEN004-2026-BTI255 | 84213985 | 84213925 | 84213925 | yes | 84213925, 84213985 |
| IEBTIIENEN004-2025-BTI26 | 84716070 | 84716070 | ask | — | 84716060, 84716070 |
| IEBTIIENEN004-2026-BTI60 | 85389099 | 85389091 | 85389091 | yes | 85389091, 85389099 |
| IEBTIIENEN004-2023-BTI579 | 85285210 | 85285291 | 85285291 | yes | 85285210, 85285291, 85285299 |
| XIBTI505059567 | 85044060 | 85044083 | 85044083 | yes | 85044060, 85044083, 85044087, 85044095 |
| IEBTIIENEN004-2023-BTI625 | 85285210 | 85285210 | ask | — | 85285210, 85285291, 85285299 |
| XIBTI505070292 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| XIBTI505070488 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| XIBTI505070096 | 94032080 | 94032020 | 94032020 | yes | 94032020, 94032080 |
| IEBTIIENEN004-2025-BTI38 | 95030041 | 95030049 | 95030049 | yes | 95030021, 95030041, 95030049, 95030070, 95030099 |
| IEBTIIENEN004-2026-BTI72 | 96190050 | 96190040 | 96190040 | yes | 96190040, 96190050, 96190071, 96190079, 96190089 |
| DEBTI59675/24-1 | 96039099 | 96039091 | 96039091 | yes | 96039010, 96039091, 96039099 |

## 3. Confidence of the raw output

Every raw output, by attribute_visible; the visible ones also by the evidence check. The prompt asks for 85-98 when the evidence words state the deciding attribute and 70-84 when the choice is inferred, so a level-b answer (the attribute follows from stated facts) belongs in 70-84.

| Confidence | Visible: all | Visible, evidence passed | Visible, evidence rejected | Visible, cn8 null (not checked) | Not visible |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |
| 1–69 | 0 | 0 | 0 | 0 | 0 |
| 70–84 | 0 | 0 | 0 | 0 | 0 |
| 85–98 | 360 | 334 | 26 | 0 | 0 |
| 99–100 | 0 | 0 | 0 | 0 | 0 |
| All | 360 | 334 | 26 | 0 | 0 |

Exact values, visible: 85 × 329, 95 × 31.
