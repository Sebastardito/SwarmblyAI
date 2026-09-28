"""Semantic units: sentences, approximate tokens, interface coupling, delta."""

import re

STOPWORDS = set(
    "the a an and or of to in for with on at by from as is are was were be been "
    "this that these those it its he she they we you i not no but if then than "
    "so such also which who whom whose".split()
)


def split_sentences(text):
    """Sentence segmentation: boundary after .!? followed by whitespace."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\u00bf\u00a1])", text)
    return [p.strip() for p in parts if p.strip()]


def approx_tokens(text):
    """Approximate token count (words x 1.3); consistent across arms so rho
    comparisons are valid. Real tokenizer counts are available per call via
    prompt_eval_count and are recorded alongside."""
    return int(len(re.findall(r"\S+", text)) * 1.3)


def content_words(sentence):
    toks = re.findall(r"[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc0-9]+",
                      sentence.lower())
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]


def coupling(s1, s2):
    """Interface coupling between adjacent sentences: shared content words."""
    w1, w2 = set(content_words(s1)), set(content_words(s2))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / min(len(w1), len(w2))


def entity_chains(sentences, entities):
    """For each canonical entity, the sentence indices where it is mentioned."""
    chains = {}
    for e in entities:
        idx = [i for i, s in enumerate(sentences)
               if re.search(rf"\b{re.escape(e)}\b", s, re.IGNORECASE)]
        if idx:
            chains[e] = idx
    return chains
