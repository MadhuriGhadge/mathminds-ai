def explain_concept(concept: str) -> dict:
    return {
        "concept": concept,
        "definition": f"{concept} is a fundamental mathematical idea.",
        "key_points": [
            f"Understand what {concept} represents",
            f"Know where {concept} is used"
        ],
        "example": f"Example related to {concept}",
        "common_mistakes": [
            f"Misunderstanding the basics of {concept}"
        ]
    }