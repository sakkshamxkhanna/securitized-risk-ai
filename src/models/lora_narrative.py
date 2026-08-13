"""LoRA-adapted narrative generation for surveillance commentary.

Fine-tunes low-rank adapters on top of a frozen GPT-2 using a corpus of
surveillance-commentary sentences in desk register, so the model learns
the domain's phrasing ("subordinate write-down", "WAL extension",
"credit enhancement erosion") rather than generic prose.

Deliberately small: rank-8 adapters over GPT-2 (124M) trains on CPU in
a couple of minutes. The point is demonstrating parameter-efficient
fine-tuning end-to-end, not model scale.

Numeric facts are always injected from the pipeline's computed metrics —
the LM controls phrasing only, never the figures.
"""
from __future__ import annotations

import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ADAPTER_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "lora_adapter"

CORPUS = [
    "Pool performance remained within expectations this period, with prepayment speeds tracking modestly above the base case projection.",
    "Credit enhancement to the senior tranche increased as sequential principal amortisation reduced the outstanding senior balance.",
    "The subordinate tranche absorbed realised collateral losses in full, leaving mezzanine principal unimpaired over the projection horizon.",
    "Faster prepayment speeds shortened weighted average life on the senior bonds, reducing spread duration but accelerating reinvestment risk.",
    "Delinquency migration was concentrated in higher loan-to-value cohorts, consistent with the modelled sensitivity to house price declines.",
    "Under the adverse scenario, cumulative collateral losses eroded a material portion of available credit enhancement at the subordinate level.",
    "Geographic concentration remains the dominant driver of tail loss, with regional employment shocks propagating across cohorts sharing an originator.",
    "Weighted average coupon on the pool declined marginally as higher-rate borrowers prepaid at elevated speeds.",
    "Risk weighted assets increased period on period, driven by the subordinate tranche retaining a larger share of outstanding exposure.",
    "The desk should monitor originator level performance dispersion, as correlated underwriting weakness is not captured by loan level scoring alone.",
    "Expected loss on the mezzanine tranche remains contained under base assumptions but is highly convex to unemployment stress.",
    "Collateral seasoning continued to build, moving the pool further up the prepayment ramp and stabilising projected cashflow timing.",
    "Servicer advancing behaviour supports near term cashflow stability, though recovery timelines extend under the stressed scenarios.",
    "Available funds shortfalls did not occur in any generated scenario, with interest collections covering the full tranche accrual.",
    "Loss severity assumptions remain the single largest sensitivity in the subordinate write-down projection.",
    "Portfolio surveillance identified no covenant breaches this period; all trigger tests remain in compliance.",
    "Prepayment speeds accelerated across seasoned cohorts, consistent with the modelled rate incentive response.",
    "Realised losses remained below the base case projection, supporting stable credit enhancement across the capital structure.",
    "The senior tranche retains substantial subordination, and no principal impairment is projected under any generated scenario.",
    "Mezzanine spread duration extended modestly as slower prepayment reduced projected principal return velocity.",
    "Loan level delinquency transitions were stable, with early stage roll rates unchanged from the prior surveillance period.",
    "Cohorts sharing a common originator exhibited correlated deterioration, supporting the case for graph based risk aggregation.",
    "Weighted average life on the senior class shortened under the rate rally scenario as prepayment speeds rose sharply.",
    "House price declines drive default severity directly, and the subordinate tranche bears the resulting loss allocation first.",
    "Credit enhancement erosion at the subordinate level is the primary early warning indicator for mezzanine risk transfer.",
    "Interest collections comfortably covered tranche accruals in all periods, with no available funds cap event triggered.",
    "The pool exhibits moderate geographic concentration, and regional stress testing remains a core surveillance requirement.",
    "Elevated debt to income cohorts showed greater sensitivity to unemployment stress in the scenario analysis.",
    "Projected cashflow timing remained stable, with scheduled amortisation dominating principal return in base conditions.",
    "Recovery assumptions materially influence subordinate write-down magnitude and warrant periodic revalidation.",
    "Portfolio exposure declined period on period as scheduled and unscheduled principal reduced outstanding balances.",
    "Risk weighted asset intensity rose as the remaining exposure concentrated in lower rated tranches.",
    "Servicer reporting was received on time and reconciled to trustee remittance without exception.",
    "No trigger events were breached, and the transaction continues to pay sequentially as structured.",
    "Stress testing indicates the mezzanine tranche remains insulated across the sampled macro scenario distribution.",
    "Loss timing is back loaded in the credit stress scenarios, delaying subordinate write-down relative to the base case.",
    "Originator level dispersion in default performance justifies cohort level rather than pool level risk monitoring.",
    "Collateral quality metrics remained stable, with weighted average FICO and loan to value broadly unchanged.",
    "The transaction's sequential pay structure continues to build credit enhancement for the senior class over time.",
]


def train_adapter(epochs: int = 12, verbose: bool = True):
    """Trains rank-8 LoRA adapters on the surveillance corpus. Returns
    (model, tokenizer) or None if transformers/peft are unavailable."""
    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import GPT2LMHeadModel, GPT2Tokenizer
    except ImportError:
        if verbose:
            print("  [lora] transformers/peft not installed — skipping adapter training")
        return None

    tok = GPT2Tokenizer.from_pretrained("gpt2")
    tok.pad_token = tok.eos_token
    base = GPT2LMHeadModel.from_pretrained("gpt2")

    cfg = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05,
        target_modules=["c_attn"], bias="none", task_type="CAUSAL_LM",
    )
    model = get_peft_model(base, cfg)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    if verbose:
        print(f"  [lora] trainable params {trainable:,} / {total:,} "
              f"({100*trainable/total:.2f}% — rank-8 adapters on c_attn)")

    enc = tok(CORPUS, return_tensors="pt", padding=True, truncation=True, max_length=64)
    input_ids, attn = enc["input_ids"], enc["attention_mask"]
    labels = input_ids.clone()
    labels[attn == 0] = -100

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-4)
    model.train()
    for ep in range(epochs):
        opt.zero_grad()
        out = model(input_ids=input_ids, attention_mask=attn, labels=labels)
        out.loss.backward()
        opt.step()
        if verbose and (ep % 4 == 0 or ep == epochs - 1):
            print(f"  [lora] epoch {ep:2d}  loss={out.loss.item():.4f}")
    model.eval()

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    if verbose:
        print(f"  [lora] adapter saved -> {ADAPTER_DIR}")
    return model, tok


def generate_commentary(model_and_tok, prompt: str, max_new_tokens: int = 45) -> str | None:
    if model_and_tok is None:
        return None
    import torch
    model, tok = model_and_tok
    ids = tok(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            **ids, max_new_tokens=max_new_tokens, do_sample=True,
            top_p=0.92, temperature=0.8, pad_token_id=tok.eos_token_id,
            repetition_penalty=1.15,
        )
    text = tok.decode(out[0], skip_special_tokens=True)
    body = text[len(prompt):].strip()
    # keep only the first complete sentence
    if "." in body:
        body = body[: body.index(".") + 1]
    return body or None
