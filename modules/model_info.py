SPEAKERS_370M = [
    "None",
    "david -- English (British)",
    "puck -- English (Gemini)",
    "kore -- English (Gemini)",
    "andrew -- English",
    "jenny -- English (Irish)",
    "simon -- English",
    "katie -- English",
    "seulgi -- Korean",
    "bert -- German",
    "thorsten -- German (Hessisch)",
    "maria -- Spanish",
    "mei -- Chinese (Cantonese)",
    "ming -- Chinese (Shanghai OpenAI)",
    "karim -- Arabic",
    "nur -- Arabic",
]

MODEL_CONFIGS = {
    "kani-tts-370m (Multi-Speaker)": {
        "repo_id": "nineninesix/kani-tts-370m",
        "speakers": SPEAKERS_370M,
    },
    "kani-tts-450m-0.1-pt (Base/Random)": {
        "repo_id": "nineninesix/kani-tts-450m-0.1-pt",
    },
    "kani-tts-450m-0.2-ft (Female)": {
        "repo_id": "nineninesix/kani-tts-450m-0.2-ft",
    },
    "kani-tts-450m-0.1-ft (Male)": {
        "repo_id": "nineninesix/kani-tts-450m-0.1-ft",
    },
}

AVAILABLE_KANI_MODELS = {}