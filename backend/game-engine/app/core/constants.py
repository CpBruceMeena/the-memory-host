"""Application constants for The Memory Host — Game Engine Service."""

WORD_POOL: list[str] = [
    "eagle", "jaguar", "tiger", "zebra", "koala", "dolphin", "elephant",
    "kangaroo", "dragon", "butterfly", "firefly", "falcon", "panther",
    "raven", "coyote", "osprey", "beaver", "otter", "badger", "cougar",
    "apple", "banana", "cherry", "lemon", "orange", "pepper", "ginger",
    "olive", "pancake", "chocolate", "nectar", "honey", "mango", "peach",
    "plum", "grape", "melon", "walnut", "basil", "sage",
    "forest", "garden", "harbor", "island", "mountain", "river", "sunset",
    "ocean", "iceberg", "thunder", "rainbow", "winter", "autumn", "horizon",
    "meadow", "canyon", "glacier", "volcano", "desert", "tundra",
    "castle", "lantern", "marble", "rocket", "piano", "violin", "guitar",
    "jewel", "diamond", "amber", "sapphire", "quartz", "knight", "umbrella",
    "feather", "copper", "violet", "nebula", "crystal", "mirror",
    "night", "whisper", "melody", "yellow", "silver", "velvet", "crimson",
    "emerald", "golden", "shadow", "spirit", "summer", "spring", "dream",
    "echo", "bloom", "dawn", "frost", "breeze", "storm",
]

assert len(WORD_POOL) == len(set(WORD_POOL)), "Word pool contains duplicates!"
assert len(WORD_POOL) >= 100, f"Word pool has {len(WORD_POOL)} words, need at least 100"
