"""Stage 1: domain-adapt a small encoder on transaction sentences (masked LM).

Every paper we read (Flowcast 2305.18430, Trustly 2511.12154, FreeAgent, the SME
FinBERT paper) says the same thing: off-the-shelf English tokenisers and weights
generalise badly to bank narratives (`cd`, `fps`, `ddr`, `pfs`, truncations,
merchant codes). Both MiniLM attempts in this repo skipped this step. This one:

  1. extends the pretrained WordPiece vocabulary with the most frequent
     transaction tokens that the base tokeniser fragments (init: mean of the
     sub-piece embeddings), plus the structured tokens [DEBIT] [CREDIT] [AMT_*];
  2. continues masked-LM pretraining on `outputs/transformer/pretrain_corpus.parquet`
     (whole-word masking, dynamic per batch) on MPS/CUDA/CPU;
  3. writes the adapted encoder + tokeniser to `outputs/distill_models/txn_encoder_mlm/`.

Checkpoints every N steps so a killed run resumes. No gold set is read.

Usage:
    python src/transformer/pretrain_mlm.py [--base distilbert-base-uncased] [--epochs 1]
        [--max-sentences 5000000] [--batch 128] [--max-len 48] [--new-tokens 4000]
    python src/transformer/pretrain_mlm.py --probe    # nearest-neighbour sanity check only
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoModelForMaskedLM, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = ROOT / "outputs" / "transformer" / "pretrain_corpus.parquet"
SAVE_DIR = ROOT / "outputs" / "distill_models" / "txn_encoder_mlm"
CKPT = SAVE_DIR / "ckpt.pt"
LOG = ROOT / "outputs" / "transformer" / "pretrain_mlm.log"

STRUCT_TOKENS = ["[DEBIT]", "[CREDIT]"] + [
    f"[{t}]" for t in ("AMT_0_5", "AMT_5_20", "AMT_20_50", "AMT_50_100", "AMT_100_250",
                       "AMT_250_500", "AMT_500_1K", "AMT_1K_2500", "AMT_2500_PLUS")]

PROBE_WORDS = ["stepchange", "pfs", "klarna", "skybet", "ddr", "fps", "wonga", "tesco",
               "greggs", "hmrc", "bgc", "refund", "returned", "payin3", "pdq"]


def device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def log(msg):
    print(msg, file=sys.stderr, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(msg + "\n")


# ------------------------------------------------------------ tokeniser
def extend_vocab(tokenizer, model, texts, n_new: int):
    """Add the n_new most frequent whitespace tokens that the base tokeniser
    splits into >= 3 word-pieces (i.e. it does not know them)."""
    import re
    noise = re.compile(r"\d{3,}|\d{1,2}[a-z]{3}\d{2}|^[^a-z]*$")  # refs, dates (06sep25), pure symbols
    cnt = collections.Counter()
    for t in texts:
        for w in t.split():
            if w.startswith("[") or len(w) < 3 or noise.search(w):
                continue
            cnt[w] += 1
    cands = []
    for w, c in cnt.most_common(300_000):
        if c < 30:
            break
        pieces = tokenizer.tokenize(w)
        if len(pieces) >= 2:  # base tokeniser fragments it -> teach it as one token
            cands.append((w, c, pieces))
        if len(cands) >= n_new:
            break
    new_words = [w for w, _, _ in cands]
    added = tokenizer.add_tokens(STRUCT_TOKENS + new_words, special_tokens=False)
    old_n = model.get_input_embeddings().weight.shape[0]
    model.resize_token_embeddings(len(tokenizer))
    emb = model.get_input_embeddings().weight.data
    # init: mean of the old sub-piece embeddings (structured tokens: mean of all)
    with torch.no_grad():
        base_mean = emb[:old_n].mean(dim=0)
        for tok in STRUCT_TOKENS:
            emb[tokenizer.convert_tokens_to_ids(tok)] = base_mean
        for w, _, pieces in cands:
            ids = tokenizer.convert_tokens_to_ids(pieces)
            emb[tokenizer.convert_tokens_to_ids(w)] = emb[ids].mean(dim=0)
    log(f"vocab: added {added} tokens ({len(new_words)} domain words + {len(STRUCT_TOKENS)} structured); "
        f"examples: {new_words[:25]}")
    return cands


# ------------------------------------------------------------ masking
_CONT_TABLE = {}


def _continuation_table(tokenizer, dev):
    key = (id(tokenizer), len(tokenizer), str(dev))
    if key not in _CONT_TABLE:
        toks = tokenizer.convert_ids_to_tokens(list(range(len(tokenizer))))
        _CONT_TABLE[key] = torch.tensor([t.startswith("##") for t in toks], device=dev)
    return _CONT_TABLE[key]


def whole_word_mask(input_ids, attention_mask, tokenizer, mlm_prob=0.15):
    """Dynamic whole-word masking: mask all pieces of a chosen word. 80/10/10.
    Vectorised: continuation lookup is a precomputed vocab-sized table."""
    dev = input_ids.device
    labels = input_ids.clone()
    special = torch.tensor(tokenizer.all_special_ids, device=dev)
    is_special = torch.isin(input_ids, special) | (attention_mask == 0)
    is_cont = _continuation_table(tokenizer, dev)[input_ids]
    word_start = ~is_cont & ~is_special
    choose = (torch.rand(input_ids.shape, device=dev) < mlm_prob) & word_start
    # propagate the choice along continuation pieces with a cumulative trick:
    # word id = cumsum(word_start); a piece is masked if its word's start was chosen.
    word_id = torch.cumsum(word_start.long(), dim=1)  # 0 for leading specials
    chosen_word = torch.zeros(input_ids.shape[0], input_ids.shape[1] + 1, dtype=torch.bool, device=dev)
    chosen_word.scatter_(1, word_id * choose.long(), choose)
    chosen_word[:, 0] = False
    masked = chosen_word.gather(1, word_id) & ~is_special
    labels[~masked] = -100
    r = torch.rand(input_ids.shape, device=dev)
    replace = masked & (r < 0.8)
    random = masked & (r >= 0.8) & (r < 0.9)
    out = input_ids.clone()
    out[replace] = tokenizer.mask_token_id
    rand_ids = torch.randint(len(tokenizer), input_ids.shape, device=dev)
    out[random] = rand_ids[random]
    return out, labels


# ------------------------------------------------------------ probe
@torch.no_grad()
def probe(tokenizer, model, dev, words=PROBE_WORDS, k=8):
    emb = model.get_input_embeddings().weight.detach().float()
    emb_n = F.normalize(emb, dim=-1)
    vocab = tokenizer.convert_ids_to_tokens(list(range(len(tokenizer))))
    lines = []
    for w in words:
        ids = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(w))
        if not ids:
            continue
        v = F.normalize(emb[ids].mean(0, keepdim=True), dim=-1)
        sims = (emb_n @ v.T).squeeze(-1)
        top = torch.topk(sims, k + len(ids) + 1).indices.tolist()
        nn = [vocab[i] for i in top if i not in ids and not vocab[i].startswith("[")][:k]
        lines.append(f"  {w:12} -> {', '.join(nn)}")
    log("embedding nearest neighbours:\n" + "\n".join(lines))


# ------------------------------------------------------------ train
def train(args):
    dev = device()
    log(f"device {dev}; base {args.base}")
    df = pd.read_parquet(CORPUS, columns=["text", "provider", "n"])
    if args.max_sentences and len(df) > args.max_sentences:
        df = df.sample(args.max_sentences, random_state=42)
    texts = df["text"].tolist()
    del df
    log(f"corpus: {len(texts):,} sentences")

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForMaskedLM.from_pretrained(args.base)
    extend_vocab(tokenizer, model, texts[:1_000_000], args.new_tokens)
    model.to(dev)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(SAVE_DIR)
    probe(tokenizer, model, dev)

    steps_per_epoch = math.ceil(len(texts) / args.batch)
    total = steps_per_epoch * args.epochs
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.03 * total), total)
    start_step = 0
    if CKPT.exists() and not args.fresh:
        ck = torch.load(CKPT, map_location="cpu")
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        start_step = ck["step"]
        log(f"resumed from step {start_step}")

    rng = np.random.default_rng(42)
    order = rng.permutation(len(texts))
    model.train()
    t0 = time.time()
    run_loss, run_n = 0.0, 0
    step = start_step
    while step < total:
        i = (step % steps_per_epoch) * args.batch
        batch_texts = [texts[j] for j in order[i:i + args.batch]]
        if not batch_texts:
            step += 1
            continue
        enc = tokenizer(batch_texts, truncation=True, max_length=args.max_len,
                        padding="longest", return_tensors="pt")
        input_ids = enc["input_ids"].to(dev)
        attn = enc["attention_mask"].to(dev)
        masked, labels = whole_word_mask(input_ids, attn, tokenizer)
        out = model(input_ids=masked, attention_mask=attn, labels=labels)
        loss = out.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        run_loss += float(loss.detach()); run_n += 1
        if step % 200 == 0:
            el = time.time() - t0
            rate = (step - start_step) * args.batch / max(el, 1e-6)
            eta = (total - step) * args.batch / max(rate, 1e-6) / 60
            log(f"step {step}/{total} loss {run_loss / run_n:.3f} "
                f"{rate:.0f} sent/s eta {eta:.0f} min")
            run_loss, run_n = 0.0, 0
        if step % args.ckpt_every == 0 or step == total:
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                        "sched": sched.state_dict(), "step": step}, CKPT)
            model.save_pretrained(SAVE_DIR)
    model.save_pretrained(SAVE_DIR)
    (SAVE_DIR / "pretrain_meta.json").write_text(json.dumps({
        "base": args.base, "sentences": len(texts), "epochs": args.epochs,
        "batch": args.batch, "max_len": args.max_len, "lr": args.lr,
        "new_tokens": args.new_tokens, "steps": total,
        "wall_s": round(time.time() - t0),
    }, indent=2))
    model.eval()
    probe(tokenizer, model, dev)
    log(f"saved {SAVE_DIR}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--max-sentences", type=int, default=5_000_000)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--new-tokens", type=int, default=4000)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    if args.probe:
        tok = AutoTokenizer.from_pretrained(SAVE_DIR)
        mdl = AutoModelForMaskedLM.from_pretrained(SAVE_DIR)
        probe(tok, mdl, device())
        return
    train(args)


if __name__ == "__main__":
    main()
