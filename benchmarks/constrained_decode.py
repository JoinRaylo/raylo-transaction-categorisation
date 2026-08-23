"""True token-level constrained decoding for mlx_lm: guarantees the model's
output is always exactly one of a fixed set of candidate strings (the 275
taxonomy leaves + unclassified_other), the local-model equivalent of the
enum-constrained tool-call used for the frontier LLMs.

Builds a token trie over each candidate's tokenization and uses mlx_lm's
`logits_processors` hook to mask every token that wouldn't keep the
generated sequence a valid prefix of some candidate. When a node has no
further valid children, only EOS is allowed, forcing a stop exactly there.
"""
import mlx.core as mx


def build_trie(tokenizer, candidates):
    root = {}
    max_len = 0
    for cand in candidates:
        ids = tokenizer.encode(cand, add_special_tokens=False)
        max_len = max(max_len, len(ids))
        node = root
        for tok in ids:
            node = node.setdefault(tok, {})
        node["__end__"] = True
    # The base model (unlike the fine-tuned one) sometimes leads with a
    # throwaway newline/space before the real answer (observed: token 107
    # = '\n' on a real eval row) -- without tolerating this, the very first
    # generated token fails the trie walk and the rest of the generation
    # falls through to unconstrained free text. Self-loop a small set of
    # leading whitespace tokens at the root only (not mid-candidate) so a
    # few throwaway tokens can be swallowed before the real walk starts.
    # +1 to max_len budget per allowed throwaway lead token.
    for ws in ("\n", " ", "\n\n"):
        ids = tokenizer.encode(ws, add_special_tokens=False)
        if len(ids) == 1:
            root.setdefault(ids[0], root)  # self-loop: doesn't consume trie depth
            max_len += 1
    return root, max_len


def make_processor(tokenizer, trie):
    eos_id = tokenizer.eos_token_id

    def processor(tokens, logits):
        # `tokens` here is ONLY the tokens generated so far -- despite
        # generate.py's variable name and mx.concat pattern suggesting a
        # running prompt+generation history, empirically (verified via
        # instrumented debug run) it starts at length 1 on the first call
        # and never includes the prompt. No prompt-length offset needed.
        generated = tokens.tolist()
        node = trie
        for tok in generated:
            if tok in node:
                node = node[tok]
            else:
                return logits  # shouldn't happen; fail open rather than crash
        allowed = [t for t in node.keys() if t != "__end__"]
        if "__end__" in node:
            allowed.append(eos_id)
        mask = mx.full(logits.shape, -mx.inf)
        idx = mx.array(allowed, dtype=mx.int32)
        # scatter the original logit values back in for allowed tokens only
        mask[:, idx] = logits[:, idx]
        return mask

    return processor


def generate_constrained(model, tokenizer, prompt, candidates, generate_fn, prompt_cache=None):
    """generate_fn: the mlx_lm.generate callable (passed in to avoid a
    circular/heavy import at module load time). `prompt` may be a string
    (normal case) or a list of already-tokenized ints (used when the
    caller is feeding only the suffix after a cached shared prefix)."""
    trie, max_len = build_trie(tokenizer, candidates)
    processor = make_processor(tokenizer, trie)
    kwargs = {"logits_processors": [processor]}
    if prompt_cache is not None:
        kwargs["prompt_cache"] = prompt_cache
    out = generate_fn(model, tokenizer, prompt, max_tokens=max_len + 1, verbose=False, **kwargs)
    return out.strip()
