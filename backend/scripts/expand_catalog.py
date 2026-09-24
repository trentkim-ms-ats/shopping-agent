"""Build a reproducible 240-product synthetic catalog, preserving the original 24."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_COUNTS = {"J": 12, "M": 4, "P": 4, "A": 4}
BASE_IDS = {f"{prefix}{i:02d}" for prefix, count in BASE_COUNTS.items() for i in range(1, count + 1)}
COLLECTIONS = [
    ("Juniper", "woodland paths", "An internal hanging loop."),
    ("Granite", "rocky trail approaches", "A contrast pull tab."),
    ("Harbor", "coastal paths", "A plain stitched label."),
    ("Aspen", "forest clearings", "A small exterior patch pocket."),
    ("Canyon", "dry valley routes", "A contrasting edge trim."),
    ("Willow", "riverside paths", "A folded fabric tab."),
    ("Orchard", "countryside lanes", "A simple stitched panel."),
    ("Cedar", "parkland routes", "A tonal decorative seam."),
    ("Highland", "hill country paths", "A compact zip pocket."),
]
PALETTES = [
    ("Black", "Slate"), ("Stone", "Moss"), ("Navy", "Sand"), ("Rust", "Black"),
    ("Olive", "Stone"), ("Plum", "Slate"), ("Red", "Navy"), ("Teal", "Sand"),
]
# Benefits are independently authored evaluation labels, not copied from search results.
RECIPES = {
    "jacket": [
        ("Drizzle Anorak", ("Lightweight jacket for autumn day hikes. Helps shed light drizzle. "
         "Packs into its own pocket."), 129, {"lightweight", "light rain protection"}, True),
        ("Ridge Shell", "Jacket for fall hiking. Helps shed light drizzle. Adjustable cuffs.",
         139, {"light rain protection"}, True),
        ("Camp Parka", "Warm jacket for winter camping. Hood and two front pockets.", 169, {"warmth"}, False),
        ("Sunrise Windlayer", "Lightweight jacket for summer hiking. Full zip and stand collar.",
         89, {"lightweight"}, False),
        ("Spring Trail Jacket", "Jacket for spring hikes. Helps shed light drizzle. Zip chest pocket.",
         109, {"light rain protection"}, False),
        ("Commuter Overshirt", "Jacket for spring commuting. Button front and two patch pockets.",
         99, set(), False),
        ("Winter Hood Jacket", "Warm jacket for winter walking. Soft lining and adjustable hood.",
         189, {"warmth"}, False),
        ("Travel Pack Shell", "Lightweight shell for autumn travel. Packs into its own pocket.",
         119, {"lightweight"}, False),
        ("Cycle Layer", "Lightweight jacket for summer cycling. Zip front and rear pocket.",
         109, {"lightweight"}, False),
        ("Summit Soft Jacket", "Warm jacket for autumn hiking. Soft lining and two hand pockets.",
         159, {"warmth"}, True),
        ("Rain Cape", "Jacket for fall walks. Helps shed light drizzle. Snap front and adjustable hood.",
         149, {"light rain protection"}, False),
        ("Town Field Jacket", "Jacket for autumn city visits. Button front and four patch pockets.",
         129, set(), False),
    ],
    "midlayer": [
        ("Trail Zip Fleece", "Warm midlayer for autumn hiking. Zip front and two hand pockets.",
         59, {"warmth"}, True),
        ("Summer Crew Layer", "Lightweight midlayer for summer hikes. Crew neck and chest pocket.",
         49, {"lightweight"}, False),
        ("Camp Half Zip", "Warm midlayer for winter camping. Half zip and stand collar.",
         69, {"warmth"}, False),
        ("Travel Cardigan", "Midlayer for spring travel. Button front and two patch pockets.",
         55, set(), False),
    ],
    "pants": [
        ("Trail Pocket Pants", "Pants for autumn hiking. Two hand pockets and one zip pocket.",
         79, set(), True),
        ("Summer Drawcord Pants", "Lightweight pants for summer hikes. Drawcord waist and side pockets.",
         59, {"lightweight"}, False),
        ("Camp Lined Pants", "Warm pants for winter campsite evenings. Soft lining and two pockets.",
         89, {"warmth"}, False),
        ("Travel Straight Pants", "Pants for spring travel. Straight leg and two rear pockets.",
         65, set(), False),
    ],
    "accessory": [
        ("Trail Visor Cap", "Lightweight visor cap for autumn hiking. Adjustable back strap.",
         25, {"lightweight"}, True),
        ("Camp Beanie", "Warm beanie for winter camping. Folded edge and plain design.",
         29, {"warmth"}, False),
        ("Travel Pouch", "Small pouch for spring travel. Zip closure and an adjustable strap.",
         32, set(), False),
        ("Walking Scarf", "Warm scarf for autumn walks. Plain design with fringed ends.",
         35, {"warmth"}, False),
    ],
}
PREFIXES = dict(zip(RECIPES, BASE_COUNTS, strict=True))


def read(path):
    return json.loads((ROOT / path).read_text())


def write(path, data):
    (ROOT / path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def expanded_catalog():
    raw = [p for p in read("data/seed/raw_products.json") if p["product_id"] in BASE_IDS]
    commerce = [p for p in read("data/seed/commerce.json") if p["product_id"] in BASE_IDS]
    if {p["product_id"] for p in raw} != BASE_IDS or {p["product_id"] for p in commerce} != BASE_IDS:
        raise ValueError("The original 24 source and commerce records must be present")
    annotations = {}
    for category, recipes in RECIPES.items():
        prefix = PREFIXES[category]
        for collection_index, (collection, setting, detail) in enumerate(COLLECTIONS):
            for recipe_index, (name, description, price, benefits, fall_hiking) in enumerate(recipes):
                number = BASE_COUNTS[prefix] + collection_index * len(recipes) + recipe_index + 1
                pid = f"{prefix}{number:02d}"
                colors = PALETTES[(collection_index + recipe_index) % len(PALETTES)]
                sizes = ["One Size"] if category == "accessory" else \
                    ["XS", "S"] if number % 11 == 0 else \
                    ["M", "L", "XL"] if number % 3 == 0 else ["S", "M", "L"]
                style = ("outdoor style", "minimal style", "urban style")[
                    (collection_index + recipe_index) % 3]
                raw.append({
                    "product_id": pid, "category": category, "name": f"{collection} {name}",
                    "colors": list(colors), "sizes": sizes,
                    "description": f"{description} {detail} Designed for {setting}. Simple {style}.",
                })
                variants = []
                for color_index, color in enumerate(colors):
                    for size_index, size in enumerate(sizes):
                        stock = 0 if number % 13 == 0 or (number + color_index + size_index) % 7 == 0 \
                            else 1 + (number * 3 + color_index * 5 + size_index) % 18
                        variants.append({
                            "variant_id": f"{pid}-{color}-{size.replace(' ', '-')}",
                            "color": color, "size": size, "stock": stock,
                        })
                commerce.append({
                    "product_id": pid, "currency": "USD",
                    "price_cents": (price + collection_index * (7 if category != "accessory" else 3)) * 100,
                    "variants": variants, "popularity_30d": 12 + (number * 37 + collection_index * 19) % 780,
                    "snapshot_at": "2026-09-21T00:00:00Z",
                })
                annotations[pid] = {"benefits": benefits, "fall_hiking": fall_hiking}
    counts = Counter(p["category"] for p in raw)
    if counts != {"jacket": 120, "midlayer": 40, "pants": 40, "accessory": 40}:
        raise ValueError(f"Unexpected catalog counts: {counts}")
    for field in ("name", "description"):
        duplicates = [value for value, count in Counter(p[field] for p in raw).items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate synthetic {field}: {duplicates}")
    return raw, commerce, annotations


def expanded_cases(raw, commerce, annotations):
    cases = read("evals/cases.json")
    products = {p["product_id"]: p for p in raw}
    facts = {p["product_id"]: p for p in commerce}
    profiles = {p["profile_id"]: p for p in read("data/seed/profiles.json")}
    for case in cases:
        case["eligible"] = [pid for pid in case["eligible"] if pid in BASE_IDS]
        case["relevant"] = [pid for pid in case["relevant"] if pid in BASE_IDS]
        has_relevance_labels = bool(case["relevant"])
        profile = profiles[case["profile"]]
        intent = {"category": "jacket", "size": profile["preferred_size"],
                  "max_price_cents": profile["budget_cents"], "required_benefits": [], **case["intent"]}
        for pid, labels in annotations.items():
            product, fact = products[pid], facts[pid]
            if product["category"] != intent["category"] or fact["price_cents"] > intent["max_price_cents"]:
                continue
            if not any(v["size"] == intent["size"] and v["stock"] > 0 for v in fact["variants"]):
                continue
            if not set(intent["required_benefits"]) <= labels["benefits"]:
                continue
            case["eligible"].append(pid)
            desired = {"light_rain": "light rain protection", "warmth": "warmth",
                       "lightweight": "lightweight"}.get(intent.get("priority"))
            if has_relevance_labels and labels["fall_hiking"] and (not desired or desired in labels["benefits"]):
                case["relevant"].append(pid)
    return cases


def main():
    raw, commerce, annotations = expanded_catalog()
    cases = expanded_cases(raw, commerce, annotations)
    write("data/seed/raw_products.json", raw)
    write("data/seed/commerce.json", commerce)
    write("evals/cases.json", cases)
    print(json.dumps({"products": len(raw), "categories": dict(Counter(p["category"] for p in raw)),
                      "variants": sum(len(p["variants"]) for p in commerce), "evaluation_cases": len(cases)}))


if __name__ == "__main__":
    main()
