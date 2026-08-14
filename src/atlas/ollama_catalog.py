"""Curated Ollama models for ATLAS. Ollama has no official public library-search API."""

CATALOG = [
    {
        "name": "phi3:latest",
        "title": "Phi-3 Mini",
        "maker": "Microsoft",
        "params": "3.8B",
        "disk": "~2.2 GB",
        "tier": "laptop",
        "fit": "i7 / 8–16 GB RAM, CPU or GPU",
        "why": "ATLAS default. Small, fast, strong at following instructions. Good first model for a work laptop.",
    },
    {
        "name": "phi4-mini",
        "title": "Phi-4 Mini",
        "maker": "Microsoft",
        "params": "3.8B",
        "disk": "~2.5 GB",
        "tier": "laptop",
        "fit": "i7 / 8–16 GB RAM",
        "why": "Newer Phi generation. Best small-model upgrade if Phi-3 feels dated.",
    },
    {
        "name": "llama3.2:3b",
        "title": "Llama 3.2 3B",
        "maker": "Meta",
        "params": "3B",
        "disk": "~2.0 GB",
        "tier": "laptop",
        "fit": "i7 / 8 GB RAM",
        "why": "Slightly smaller than Phi-3. Fast on CPU, decent general chat.",
    },
    {
        "name": "qwen2.5:3b",
        "title": "Qwen2.5 3B",
        "maker": "Alibaba",
        "params": "3B",
        "disk": "~2.0 GB",
        "tier": "laptop",
        "fit": "i7 / 8 GB RAM",
        "why": "Often stronger than Llama 3.2 3B at the same size. Good laptop alternative.",
    },
    {
        "name": "gemma2:2b",
        "title": "Gemma 2 2B",
        "maker": "Google",
        "params": "2B",
        "disk": "~1.6 GB",
        "tier": "tiny",
        "fit": "Low RAM / slow CPU",
        "why": "Google’s small model — not Phi. Use when you need the lightest possible chat model.",
    },
    {
        "name": "llama3.1:8b",
        "title": "Llama 3.1 8B",
        "maker": "Meta",
        "params": "8B",
        "disk": "~4.9 GB",
        "tier": "desktop-gpu",
        "fit": "GPU ~6 GB+ VRAM, or 16 GB+ RAM (slow on CPU)",
        "why": "Better quality than 3B-class models. Heavy on a CPU-only i7. Fine on a 1080 Ti.",
    },
    {
        "name": "mistral:7b",
        "title": "Mistral 7B",
        "maker": "Mistral",
        "params": "7B",
        "disk": "~4.1 GB",
        "tier": "desktop-gpu",
        "fit": "GPU ~5 GB+ or 16 GB RAM",
        "why": "Solid 7B instruct model. Same class as Llama 3.1 8B for ATLAS.",
    },
]


def search_catalog(query: str) -> list[dict]:
    needle = (query or "").strip().lower()
    if not needle:
        return list(CATALOG)
    hits = [
        item
        for item in CATALOG
        if needle in item["name"].lower()
        or needle in item["title"].lower()
        or needle in item["maker"].lower()
        or needle in item["why"].lower()
    ]
    if needle and not any(item["name"].startswith(needle.split(":")[0]) for item in hits):
        hits.append(
            {
                "name": needle if ":" in needle else f"{needle}:latest",
                "title": needle,
                "maker": "Ollama library",
                "params": "?",
                "disk": "unknown until pull",
                "tier": "custom",
                "fit": "Depends on the model",
                "why": "Not in the ATLAS shortlist. If this name exists on ollama.com/library, Pull will download it.",
            }
        )
    return hits
