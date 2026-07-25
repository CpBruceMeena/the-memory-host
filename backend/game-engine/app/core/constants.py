"""Application constants for The Memory Host — Game Engine Service.

Word pool uses simple, common English words that are easy to pronounce.
Avoids words with complex consonant clusters, unusual spellings, or
ambiguous pronunciations.
"""

WORD_POOL: list[str] = [
    # Animals (easy)
    "cat", "dog", "bird", "fish", "frog", "duck", "bear", "deer",
    "lion", "wolf", "fox", "hen", "pig", "cow", "sheep", "goat",
    "mouse", "rabbit", "horse", "turtle",
    # Food & Fruits (everyday)
    "apple", "banana", "bread", "cake", "rice", "soup", "milk",
    "egg", "butter", "cheese", "grape", "peach", "mango", "lemon",
    "melon", "pear", "plum", "corn", "bean", "pepper",
    # Body & People (familiar)
    "hand", "foot", "head", "nose", "eye", "ear", "arm", "leg",
    "baby", "child", "mother", "father", "sister", "brother",
    # Nature & Weather (common)
    "rain", "snow", "wind", "sun", "moon", "star", "tree", "leaf",
    "flower", "grass", "rock", "sand", "water", "fire", "cloud",
    "hill", "lake", "river", "ocean", "desert",
    # Home & Objects (everyday)
    "door", "window", "table", "chair", "bed", "lamp", "clock",
    "book", "pen", "paper", "cup", "plate", "bowl", "knife",
    "spoon", "fork", "bag", "box", "ball", "hat",
    # Actions & Colors (simple)
    "red", "blue", "green", "white", "black", "brown", "pink",
    "walk", "run", "jump", "sing", "dance", "read", "write",
    "cook", "clean", "draw", "play", "sleep", "swim",
    # Places & Things (basic)
    "school", "house", "shop", "park", "bank", "farm", "store",
    "ship", "train", "car", "bus", "bike", "boat", "plane",
]

assert len(WORD_POOL) == len(set(WORD_POOL)), "Word pool contains duplicates!"
assert len(WORD_POOL) >= 100, f"Word pool has {len(WORD_POOL)} words, need at least 100"
