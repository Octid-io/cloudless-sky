"""
EML Symbolic Regression via Master Formula (PyTorch)

Implements the Odrzywołek (2026) approach: each EML node's inputs are
softmax-weighted selections from {1, x, child_result}. Training with
Adam optimizer + hardening phase + snapping produces exact symbolic
compositions.

Requires: torch (pip install torch)

Patent pending | License: Apache 2.0
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
from typing import Callable


def eml_torch(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """EML operator in PyTorch with complex support."""
    # Use complex to handle negative y in log
    xc = x.to(torch.complex128) if not x.is_complex() else x
    yc = y.to(torch.complex128) if not y.is_complex() else y
    return torch.exp(xc) - torch.log(yc)


class EMLMasterFormula(nn.Module):
    """Master formula for EML symbolic regression.

    Structure: a full binary tree of depth `depth` where:
    - Each leaf selects between {1, x} via 2-way softmax
    - Each internal node's two inputs select between {1, x, child_result}
      via 3-way softmax
    - The root outputs the final function value

    Training: Adam on softmax logits → hardening (temperature increase)
    → snap to discrete {0, 1} values → exact symbolic composition.
    """

    def __init__(self, depth: int):
        super().__init__()
        self.depth = depth

        # Count nodes: 2^(depth+1) - 1 total, 2^depth leaves, 2^depth - 1 internal
        self.n_leaves = 2 ** depth
        self.n_internal = 2 ** depth - 1

        # Leaf logits: each leaf has 2 logits (select between 1 and x)
        self.leaf_logits = nn.Parameter(torch.randn(self.n_leaves, 2, dtype=torch.float64))

        # Internal node logits: each internal node has 2 inputs,
        # each input has 3 logits (select between 1, x, child_result)
        # Shape: [n_internal, 2 inputs, 3 options]
        self.internal_logits = nn.Parameter(
            torch.randn(self.n_internal, 2, 3, dtype=torch.float64)
        )

        self.temperature = 1.0  # for softmax sharpening during hardening

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Evaluate the master formula at x (batched).

        x: tensor of shape [N] (float64 or complex128)
        Returns: tensor of shape [N] (complex128)
        """
        N = x.shape[0] if x.dim() > 0 else 1
        xc = x.to(torch.complex128).reshape(N)
        one = torch.ones(N, dtype=torch.complex128)

        # Bottom-up evaluation — fully vectorized across batch
        # Level 0: leaves produce softmax-weighted combination of {1, x}
        leaf_weights = torch.softmax(self.leaf_logits / self.temperature, dim=-1)
        # leaf_weights: [n_leaves, 2]
        # Expand to batch: [n_leaves, N]
        leaf_values = (leaf_weights[:, 0:1].to(torch.complex128) * one.unsqueeze(0) +
                       leaf_weights[:, 1:2].to(torch.complex128) * xc.unsqueeze(0))
        # leaf_values: [n_leaves, N]

        current_level = leaf_values  # [n_nodes_at_level, N]
        internal_idx = self.n_internal - 1

        for level in range(self.depth):
            n_nodes = current_level.shape[0] // 2
            left_children = current_level[0::2][:n_nodes]   # [n_nodes, N]
            right_children = current_level[1::2][:n_nodes]   # [n_nodes, N]

            # Gather this level's internal node logits
            start_idx = internal_idx - n_nodes + 1
            level_logits = self.internal_logits[start_idx:start_idx + n_nodes]
            # level_logits: [n_nodes, 2 inputs, 3 options]

            # Left inputs: softmax over {1, x, left_child}
            lw = torch.softmax(level_logits[:, 0, :] / self.temperature, dim=-1)
            # lw: [n_nodes, 3]
            left_input = (lw[:, 0:1].to(torch.complex128) * one.unsqueeze(0) +
                          lw[:, 1:2].to(torch.complex128) * xc.unsqueeze(0) +
                          lw[:, 2:3].to(torch.complex128) * left_children)

            # Right inputs: softmax over {1, x, right_child}
            rw = torch.softmax(level_logits[:, 1, :] / self.temperature, dim=-1)
            right_input = (rw[:, 0:1].to(torch.complex128) * one.unsqueeze(0) +
                           rw[:, 1:2].to(torch.complex128) * xc.unsqueeze(0) +
                           rw[:, 2:3].to(torch.complex128) * right_children)

            # Apply eml: [n_nodes, N]
            current_level = torch.exp(left_input) - torch.log(right_input)
            internal_idx -= n_nodes

        return current_level[0]  # [N]

    def snap(self) -> dict:
        """Snap softmax weights to discrete {0, 1} and return the symbolic structure.

        Returns a dict describing the exact composition tree.
        """
        result = {"depth": self.depth, "leaves": [], "nodes": []}

        # Snap leaves
        with torch.no_grad():
            leaf_weights = torch.softmax(self.leaf_logits / self.temperature, dim=-1)
            for i in range(self.n_leaves):
                idx = torch.argmax(leaf_weights[i]).item()
                result["leaves"].append("1" if idx == 0 else "x")

            # Snap internal nodes
            for i in range(self.n_internal):
                node_info = {"left": {}, "right": {}}
                for inp_idx, inp_name in enumerate(["left", "right"]):
                    weights = torch.softmax(
                        self.internal_logits[i, inp_idx] / self.temperature, dim=-1
                    )
                    idx = torch.argmax(weights).item()
                    node_info[inp_name] = ["1", "x", "f"][idx]
                result["nodes"].append(node_info)

        return result


def train_eml(
    target_fn: Callable[[float], float],
    depth: int = 2,
    x_range: tuple[float, float] = (0.1, 5.0),
    n_samples: int = 100,
    lr: float = 0.01,
    epochs: int = 5000,
    harden_start: float = 0.6,  # fraction of epochs where hardening begins
    harden_end_temp: float = 0.01,  # final temperature (sharp softmax)
    restarts: int = 5,
    verbose: bool = False,
) -> tuple[EMLMasterFormula, dict]:
    """Train an EML master formula to fit a target function.

    Returns (best_model, info_dict).
    """
    # Sample points
    xs_np = [x_range[0] + (x_range[1] - x_range[0]) * i / (n_samples - 1)
             for i in range(n_samples)]
    targets_np = [target_fn(x) for x in xs_np]

    xs = [torch.tensor(x, dtype=torch.complex128) for x in xs_np]
    targets = torch.tensor(targets_np, dtype=torch.float64)

    # Batch tensors
    xs_tensor = torch.tensor(xs_np, dtype=torch.float64)
    targets_tensor = torch.tensor(targets_np, dtype=torch.float64)

    best_model = None
    best_loss = float('inf')
    best_info = {}

    for restart in range(restarts):
        torch.manual_seed(42 + restart * 13)
        model = EMLMasterFormula(depth)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

        harden_epoch = int(epochs * harden_start)

        for epoch in range(epochs):
            # Temperature schedule
            if epoch >= harden_epoch:
                progress = (epoch - harden_epoch) / (epochs - harden_epoch)
                model.temperature = 1.0 - progress * (1.0 - harden_end_temp)
            else:
                model.temperature = 1.0

            optimizer.zero_grad()

            try:
                preds = model(xs_tensor)  # [N] complex128
                preds_real = preds.real.to(torch.float64)

                # Mask out non-finite predictions
                finite_mask = torch.isfinite(preds_real)
                if finite_mask.sum() == 0:
                    break

                loss = ((preds_real[finite_mask] - targets_tensor[finite_mask]) ** 2).mean()

                if torch.isnan(loss) or torch.isinf(loss):
                    break

                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()

            except Exception:
                break

            if verbose and epoch % 500 == 0:
                print(f"  restart {restart} epoch {epoch}: loss={loss.item():.8f} temp={model.temperature:.4f}")

            if loss.item() < best_loss:
                best_loss = loss.item()
                # Deep copy the model state
                import copy
                best_model = copy.deepcopy(model)
                best_info = {
                    "restart": restart,
                    "epoch": epoch,
                    "loss": loss.item(),
                    "temperature": model.temperature,
                }

            if loss.item() < 1e-20:
                break

        if verbose:
            print(f"  restart {restart} done, best_loss so far: {best_loss:.2e}")

    # Snap the best model
    if best_model is not None:
        best_model.temperature = harden_end_temp
        structure = best_model.snap()
        best_info["structure"] = structure

        # Evaluate final accuracy
        max_err = 0.0
        for x_val, target_val in zip(xs_np, targets_np):
            try:
                with torch.no_grad():
                    pred = best_model(torch.tensor(x_val, dtype=torch.complex128))
                err = abs(pred.real.item() - target_val)
                if math.isfinite(err):
                    max_err = max(max_err, err)
            except Exception:
                max_err = float('inf')
        best_info["max_error"] = max_err

    return best_model, best_info


# ── Sequential Master Formula (paper's actual approach) ─────────────────────
#
# The tree variant above works for depth 2 but scales poorly because every
# node has an independent softmax selection — loss surface is brutal at depth
# 3+. The paper (Odrzywołek 2026) instead uses a sequential *chain*:
#
#     f_1 = eml(α_1·1 + β_1·x,  α_2·1 + β_2·x)
#     f_n = eml(α_1·1 + β_1·x + γ_1·f_{n-1},
#               α_2·1 + β_2·x + γ_2·f_{n-1})      for n ≥ 2
#
# (α,β[,γ]) are softmax-normalised logits summing to 1. Each level adds one
# eml op and lets the next level reuse the previous result. This is the
# bootstrappable structure — level n can be warm-started from level n-1's
# converged weights plus a near-identity γ, which is what gets >99% recovery
# at depth 5-6 in the paper.


class EMLChain(nn.Module):
    """Sequential master-formula chain of depth n_levels.

    Params per level:
      - Level 1: 2 inputs × 2 logits (softmax over {1, x}) = 4
      - Level k>1: 2 inputs × 3 logits (softmax over {1, x, f_{k-1}}) = 6

    Total params = 4 + 6·(n_levels - 1) = 6·n_levels - 2.
    """

    def __init__(self, n_levels: int):
        super().__init__()
        assert n_levels >= 1
        self.n_levels = n_levels
        # Level 1: [2 inputs, 2 options: (1, x)]
        self.l1_logits = nn.Parameter(torch.randn(2, 2, dtype=torch.float64))
        # Levels 2..n: each [2 inputs, 3 options: (1, x, f_prev)]
        self.ln_logits = nn.ParameterList([
            nn.Parameter(torch.randn(2, 3, dtype=torch.float64))
            for _ in range(n_levels - 1)
        ])
        self.temperature = 1.0

    @staticmethod
    def _safe_exp(z: torch.Tensor, clamp: float = 50.0) -> torch.Tensor:
        """Complex exp with real-part clamped to avoid overflow.
        Differentiable; clamp has zero gradient outside [-clamp, clamp]."""
        real = torch.clamp(z.real, min=-clamp, max=clamp)
        return torch.exp(torch.complex(real, z.imag))

    @staticmethod
    def _safe_log(z: torch.Tensor, eps: float = 1e-30) -> torch.Tensor:
        """Complex log with magnitude floor to avoid log(0) → -inf."""
        mag = z.abs()
        # Shift tiny-magnitude values up to eps to keep log finite
        safe = torch.where(mag < eps,
                            torch.complex(torch.full_like(mag, eps),
                                          torch.zeros_like(mag)),
                            z)
        return torch.log(safe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [N] real/complex. Returns complex128 [N]."""
        if x.dim() == 0:
            x = x.unsqueeze(0)
        N = x.shape[0]
        xc = x.to(torch.complex128)
        one = torch.ones(N, dtype=torch.complex128)

        # Level 1 — no f yet
        w1 = torch.softmax(self.l1_logits / self.temperature, dim=-1)  # [2, 2]
        inp_l = w1[0, 0].to(torch.complex128) * one + w1[0, 1].to(torch.complex128) * xc
        inp_r = w1[1, 0].to(torch.complex128) * one + w1[1, 1].to(torch.complex128) * xc
        f = self._safe_exp(inp_l) - self._safe_log(inp_r)

        # Levels 2..n
        for logits in self.ln_logits:
            w = torch.softmax(logits / self.temperature, dim=-1)  # [2, 3]
            inp_l = (w[0, 0].to(torch.complex128) * one
                     + w[0, 1].to(torch.complex128) * xc
                     + w[0, 2].to(torch.complex128) * f)
            inp_r = (w[1, 0].to(torch.complex128) * one
                     + w[1, 1].to(torch.complex128) * xc
                     + w[1, 2].to(torch.complex128) * f)
            f = self._safe_exp(inp_l) - self._safe_log(inp_r)

        return f

    def snap(self) -> dict:
        """Snap softmax weights to discrete selections and describe the chain."""
        levels = []
        with torch.no_grad():
            w1 = torch.softmax(self.l1_logits / self.temperature, dim=-1)
            levels.append({
                "left":  ["1", "x"][int(torch.argmax(w1[0]).item())],
                "right": ["1", "x"][int(torch.argmax(w1[1]).item())],
            })
            for logits in self.ln_logits:
                w = torch.softmax(logits / self.temperature, dim=-1)
                levels.append({
                    "left":  ["1", "x", "f"][int(torch.argmax(w[0]).item())],
                    "right": ["1", "x", "f"][int(torch.argmax(w[1]).item())],
                })
        return {"n_levels": self.n_levels, "levels": levels}

    @torch.no_grad()
    def forward_discrete(self, x: torch.Tensor) -> torch.Tensor:
        """Evaluate the HARD-argmax tree (discrete wire form) at x.

        This is what would actually ship on the wire and evaluate on-device.
        No softmax — at each level each input is exactly one of {1, x, f_prev}.
        """
        if x.dim() == 0:
            x = x.unsqueeze(0)
        N = x.shape[0]
        xc = x.to(torch.complex128)
        one = torch.ones(N, dtype=torch.complex128)

        # Level 1
        l1_idx = torch.argmax(self.l1_logits, dim=-1)  # [2]
        opts_l1 = [one, xc]
        inp_l = opts_l1[int(l1_idx[0].item())]
        inp_r = opts_l1[int(l1_idx[1].item())]
        f = self._safe_exp(inp_l) - self._safe_log(inp_r)

        # Levels 2..n
        for logits in self.ln_logits:
            idx = torch.argmax(logits, dim=-1)  # [2]
            opts = [one, xc, f]
            inp_l = opts[int(idx[0].item())]
            inp_r = opts[int(idx[1].item())]
            f = self._safe_exp(inp_l) - self._safe_log(inp_r)

        return f

    @torch.no_grad()
    def softmax_diagnostics(self) -> dict:
        """Report how peaked each softmax is — confidence in discretization.
        Returns per-level {max_weight, entropy}. Clean snap = all max_weight ≈ 1.0."""
        out = []
        w1 = torch.softmax(self.l1_logits / self.temperature, dim=-1)
        for i in range(2):
            p = w1[i]
            ent = float(-(p * torch.log(p + 1e-40)).sum().item())
            out.append({"level": 1, "input": ["L", "R"][i],
                         "max_weight": float(p.max().item()),
                         "entropy": ent,
                         "n_options": 2})
        for li, logits in enumerate(self.ln_logits, start=2):
            w = torch.softmax(logits / self.temperature, dim=-1)
            for i in range(2):
                p = w[i]
                ent = float(-(p * torch.log(p + 1e-40)).sum().item())
                out.append({"level": li, "input": ["L", "R"][i],
                             "max_weight": float(p.max().item()),
                             "entropy": ent,
                             "n_options": 3})
        return {"per_input": out,
                "min_max_weight": min(r["max_weight"] for r in out)}

    @torch.no_grad()
    def warm_start_from(self, prior: "EMLChain", pass_through: float = 1.0) -> None:
        """Bootstrap: copy prior chain's weights, initialise new tail levels
        with a strong γ (f-reference) so the new level starts near f_prev.

        This is the paper's "perturb from correct" trick — 100% recovery at
        depths where random init gives <1%.
        """
        assert prior.n_levels <= self.n_levels
        # Copy level-1
        self.l1_logits.data.copy_(prior.l1_logits.data)
        # Copy matching later levels
        for i, prior_logit in enumerate(prior.ln_logits):
            self.ln_logits[i].data.copy_(prior_logit.data)
        # Initialise any extra levels to (1·f_prev + small noise) on both inputs
        for j in range(len(prior.ln_logits), len(self.ln_logits)):
            init = torch.zeros(2, 3, dtype=torch.float64)
            init[:, 2] = pass_through  # bias softmax toward γ (f_prev)
            init += 0.05 * torch.randn_like(init)
            self.ln_logits[j].data.copy_(init)


class EMLChainWide(nn.Module):
    """Chain variant where each level's inputs can reference ANY prior f_k,
    not just f_{n-1}. At level n, softmax is over {1, x, f_1, ..., f_{n-1}}
    (size n+1). Parameter count: sum over levels of 2·(n+1) = n²+3n.

    Strictly more expressive than EMLChain. Identity x = eml(ln(x), 1) now
    reachable at L=4, 1/x and x² likely at L=5.
    """

    def __init__(self, n_levels: int):
        super().__init__()
        assert n_levels >= 1
        self.n_levels = n_levels
        # Level k has (k+1) input options: {1, x, f_1, ..., f_{k-1}}
        # For k=1: {1, x} = 2 options
        self.logits_per_level = nn.ParameterList([
            nn.Parameter(torch.randn(2, k + 1, dtype=torch.float64))
            for k in range(1, n_levels + 1)
        ])
        self.temperature = 1.0

    @staticmethod
    def _safe_exp(z: torch.Tensor, clamp: float = 50.0) -> torch.Tensor:
        real = torch.clamp(z.real, min=-clamp, max=clamp)
        return torch.exp(torch.complex(real, z.imag))

    @staticmethod
    def _safe_log(z: torch.Tensor, eps: float = 1e-30) -> torch.Tensor:
        mag = z.abs()
        safe = torch.where(mag < eps,
                            torch.complex(torch.full_like(mag, eps),
                                          torch.zeros_like(mag)),
                            z)
        return torch.log(safe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 0:
            x = x.unsqueeze(0)
        N = x.shape[0]
        xc = x.to(torch.complex128)
        one = torch.ones(N, dtype=torch.complex128)

        # Build up f_list; at each level, softmax over [1, x, f_1..f_{k-1}]
        f_list: list[torch.Tensor] = []
        for k, logits in enumerate(self.logits_per_level, start=1):
            w = torch.softmax(logits / self.temperature, dim=-1)  # [2, k+1]
            # Options: index 0 = 1, index 1 = x, indices 2..k = f_1..f_{k-1}
            options = [one, xc] + f_list  # len = k+1
            stacked = torch.stack(options, dim=0)  # [k+1, N]
            # w[i] is [k+1]; combine options by weighted sum
            inp_l = (w[0].unsqueeze(1).to(torch.complex128) * stacked).sum(dim=0)
            inp_r = (w[1].unsqueeze(1).to(torch.complex128) * stacked).sum(dim=0)
            f = self._safe_exp(inp_l) - self._safe_log(inp_r)
            f_list.append(f)

        return f_list[-1]

    def snap(self) -> dict:
        levels = []
        with torch.no_grad():
            for k, logits in enumerate(self.logits_per_level, start=1):
                w = torch.softmax(logits / self.temperature, dim=-1)
                options_names = ["1", "x"] + [f"f{j}" for j in range(1, k)]
                left_idx = int(torch.argmax(w[0]).item())
                right_idx = int(torch.argmax(w[1]).item())
                levels.append({
                    "left": options_names[left_idx],
                    "right": options_names[right_idx],
                })
        return {"n_levels": self.n_levels, "levels": levels, "variant": "wide"}

    @torch.no_grad()
    def forward_discrete(self, x: torch.Tensor) -> torch.Tensor:
        """Hard-argmax evaluation — the actual discrete tree that ships on wire."""
        if x.dim() == 0:
            x = x.unsqueeze(0)
        N = x.shape[0]
        xc = x.to(torch.complex128)
        one = torch.ones(N, dtype=torch.complex128)

        f_list: list[torch.Tensor] = []
        for k, logits in enumerate(self.logits_per_level, start=1):
            idx = torch.argmax(logits, dim=-1)  # [2]
            options = [one, xc] + f_list  # len = k+1
            inp_l = options[int(idx[0].item())]
            inp_r = options[int(idx[1].item())]
            f = self._safe_exp(inp_l) - self._safe_log(inp_r)
            f_list.append(f)
        return f_list[-1]

    @torch.no_grad()
    def softmax_diagnostics(self) -> dict:
        out = []
        for k, logits in enumerate(self.logits_per_level, start=1):
            w = torch.softmax(logits / self.temperature, dim=-1)
            for i in range(2):
                p = w[i]
                ent = float(-(p * torch.log(p + 1e-40)).sum().item())
                out.append({"level": k, "input": ["L", "R"][i],
                             "max_weight": float(p.max().item()),
                             "entropy": ent,
                             "n_options": k + 1})
        return {"per_input": out,
                "min_max_weight": min(r["max_weight"] for r in out)}


def train_chain_wide(
    target_fn: Callable[[float], float],
    n_levels: int = 4,
    x_range: tuple[float, float] = (0.5, 5.0),
    n_samples: int = 60,
    lr: float = 0.02,
    epochs: int = 3000,
    harden_start: float = 0.5,
    harden_end_temp: float = 0.02,
    restarts: int = 5,
    seed_base: int = 42,
    verbose: bool = False,
) -> tuple[EMLChainWide, dict]:
    """Fit a wide-reference EML chain. Same training loop as train_chain."""
    import copy
    xs_np = [x_range[0] + (x_range[1] - x_range[0]) * i / (n_samples - 1)
             for i in range(n_samples)]
    targets_np = [target_fn(x) for x in xs_np]
    xs_tensor = torch.tensor(xs_np, dtype=torch.float64)
    targets_tensor = torch.tensor(targets_np, dtype=torch.float64)

    best_model: EMLChainWide | None = None
    best_loss = float("inf")
    best_info: dict = {"loss": float("inf"), "max_error": float("inf"),
                        "restart": -1, "epoch": -1, "temperature": 1.0,
                        "structure": None}

    for restart in range(restarts):
        torch.manual_seed(seed_base + restart * 13)
        model = EMLChainWide(n_levels)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        harden_epoch = int(epochs * harden_start)

        for epoch in range(epochs):
            if epoch >= harden_epoch:
                progress = (epoch - harden_epoch) / max(1, epochs - harden_epoch)
                model.temperature = max(harden_end_temp,
                                         1.0 - progress * (1.0 - harden_end_temp))
            else:
                model.temperature = 1.0

            optimizer.zero_grad()
            try:
                preds = model(xs_tensor).real.to(torch.float64)
                finite = torch.isfinite(preds)
                if finite.sum() < len(xs_np) // 2:
                    break
                loss = ((preds[finite] - targets_tensor[finite]) ** 2).mean()
                if torch.isnan(loss) or torch.isinf(loss):
                    break
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
            except Exception:
                break

            if loss.item() < best_loss:
                best_loss = loss.item()
                best_model = copy.deepcopy(model)
                best_info = {
                    "restart": restart, "epoch": epoch,
                    "loss": loss.item(), "temperature": model.temperature,
                }
            if loss.item() < 1e-20:
                break

    if best_model is not None:
        best_model.temperature = harden_end_temp
        best_info["structure"] = best_model.snap()
        max_err = 0.0
        with torch.no_grad():
            preds = best_model(xs_tensor).real
            for p, t in zip(preds.tolist(), targets_np):
                if math.isfinite(p):
                    max_err = max(max_err, abs(p - t))
                else:
                    max_err = float("inf")
        best_info["max_error"] = max_err
    return best_model, best_info


def demo_sweep_wide():
    """Sweep the WIDE chain variant — allow cross-level references —
    against the functions that failed the restricted chain.
    """
    import math as m
    import time

    print("EML WIDE Chain Sweep — cross-level references unlocked")
    print("=" * 64)

    targets = [
        ("x (identity)", lambda x: x,            (0.5, 5.0), 4),
        ("1/x",          lambda x: 1.0/x,        (0.5, 5.0), 5),
        ("x^2",          lambda x: x*x,          (0.5, 3.0), 5),
        ("sqrt(x)",      m.sqrt,                 (0.5, 5.0), 5),
    ]

    results = []
    for name, fn, xr, nlev in targets:
        t0 = time.time()
        mdl, info = train_chain_wide(
            fn, n_levels=nlev, x_range=xr,
            n_samples=50, epochs=3000, restarts=6, verbose=False,
        )
        elapsed = time.time() - t0
        err = info.get("max_error", float("inf"))
        loss = info.get("loss", float("inf"))
        verdict = ("EXACT    " if err < 1e-6
                   else "APPROX   " if err < 0.05
                   else "LOOSE    " if err < 1.0
                   else "FAIL     ")
        results.append((name, nlev, err, loss, elapsed, verdict,
                        info.get("structure")))
        print(f"  {verdict} {name:14s} L={nlev}  "
              f"err={err:.2e}  loss={loss:.2e}  ({elapsed:.0f}s)", flush=True)

    print("\n" + "=" * 64)
    print("Structures of EXACT and APPROX finds:")
    for name, nlev, err, loss, _, verdict, struct in results:
        if verdict.strip() in ("EXACT", "APPROX") and struct:
            print(f"\n  {name} ({verdict.strip()}, err={err:.2e}):")
            for i, lvl in enumerate(struct["levels"], start=1):
                print(f"    L{i}: eml({lvl['left']}, {lvl['right']})")


def train_chain(
    target_fn: Callable[[float], float],
    n_levels: int = 2,
    x_range: tuple[float, float] = (0.1, 5.0),
    n_samples: int = 80,
    lr: float = 0.02,
    epochs: int = 4000,
    harden_start: float = 0.5,
    harden_end_temp: float = 0.02,
    restarts: int = 3,
    warm_from: EMLChain | None = None,
    verbose: bool = False,
) -> tuple[EMLChain, dict]:
    """Fit a sequential EML chain to target_fn. Supports bootstrap via warm_from."""
    import copy
    xs_np = [x_range[0] + (x_range[1] - x_range[0]) * i / (n_samples - 1)
             for i in range(n_samples)]
    targets_np = [target_fn(x) for x in xs_np]
    xs_tensor = torch.tensor(xs_np, dtype=torch.float64)
    targets_tensor = torch.tensor(targets_np, dtype=torch.float64)

    best_model: EMLChain | None = None
    best_loss = float("inf")
    best_info: dict = {"loss": float("inf"), "max_error": float("inf"),
                       "restart": -1, "epoch": -1, "temperature": 1.0,
                       "structure": None}

    n_restarts = 1 if warm_from is not None else restarts
    for restart in range(n_restarts):
        torch.manual_seed(42 + restart * 13)
        model = EMLChain(n_levels)
        if warm_from is not None:
            model.warm_start_from(warm_from)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        harden_epoch = int(epochs * harden_start)

        for epoch in range(epochs):
            if epoch >= harden_epoch:
                progress = (epoch - harden_epoch) / max(1, epochs - harden_epoch)
                model.temperature = max(harden_end_temp,
                                         1.0 - progress * (1.0 - harden_end_temp))
            else:
                model.temperature = 1.0

            optimizer.zero_grad()
            try:
                preds = model(xs_tensor).real.to(torch.float64)
                finite = torch.isfinite(preds)
                if finite.sum() < len(xs_np) // 2:
                    break
                loss = ((preds[finite] - targets_tensor[finite]) ** 2).mean()
                if torch.isnan(loss) or torch.isinf(loss):
                    break
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
            except Exception:
                break

            if verbose and epoch % 500 == 0:
                print(f"  r{restart} e{epoch}: loss={loss.item():.3e} T={model.temperature:.3f}")

            if loss.item() < best_loss:
                best_loss = loss.item()
                best_model = copy.deepcopy(model)
                best_info = {
                    "restart": restart, "epoch": epoch,
                    "loss": loss.item(), "temperature": model.temperature,
                }
            if loss.item() < 1e-20:
                break

    if best_model is not None:
        best_model.temperature = harden_end_temp
        best_info["structure"] = best_model.snap()
        max_err = 0.0
        with torch.no_grad():
            preds = best_model(xs_tensor).real
            for p, t in zip(preds.tolist(), targets_np):
                if math.isfinite(p):
                    max_err = max(max_err, abs(p - t))
                else:
                    max_err = float("inf")
        best_info["max_error"] = max_err
    return best_model, best_info


def demo_chain():
    """Bootstrap the chain through the derivation ladder."""
    import math as m

    print("EML Sequential Chain — Bootstrap Derivation Ladder")
    print("=" * 60)

    # Step 1: exp(x) at depth 1. Expect eml(x, 1) = exp(x).
    print("\n[1] exp(x) @ depth 1")
    m_exp, info_exp = train_chain(m.exp, n_levels=1, x_range=(0.0, 3.0),
                                   n_samples=60, epochs=1500, restarts=3,
                                   verbose=False)
    print(f"   loss={info_exp['loss']:.2e} max_err={info_exp['max_error']:.2e}")
    print(f"   structure: {info_exp['structure']}")

    # Step 2: ln(x) at depth 2, bootstrapped from exp(x). Expect eml(0, exp(x)) = 0 - x = ... wait,
    # Actually ln(x) is more subtle — let's not warm-start, just train fresh.
    print("\n[2] ln(x) @ depth 2 (cold)")
    m_ln, info_ln = train_chain(m.log, n_levels=2, x_range=(0.5, 5.0),
                                 n_samples=60, epochs=3000, restarts=3,
                                 verbose=False)
    print(f"   loss={info_ln['loss']:.2e} max_err={info_ln['max_error']:.2e}")
    print(f"   structure: {info_ln['structure']}")


def demo_bootstrap():
    """Validate the bootstrap hypothesis: warm-starting from a converged
    parent chain unlocks depth-3+ functions that fail cold-init.
    """
    import math as m
    import time

    print("EML Bootstrap Test — does warm-start unlock deeper functions?")
    print("=" * 64)

    # Phase 1: converge exp(x) at depth 1
    print("\n[phase 1] exp(x) @ depth 1 (cold)")
    t0 = time.time()
    m_exp, info_exp = train_chain(m.exp, n_levels=1, x_range=(0.3, 3.0),
                                   n_samples=60, epochs=1500, restarts=3,
                                   verbose=False)
    print(f"   loss={info_exp['loss']:.2e} max_err={info_exp['max_error']:.2e} "
          f"({time.time()-t0:.1f}s)")
    print(f"   structure: {info_exp['structure']}")

    # Phase 2: ln(x) @ depth 3 — cold, many restarts
    print("\n[phase 2] ln(x) @ depth 3 (COLD, 5 restarts)")
    t0 = time.time()
    m_ln_cold, info_ln_cold = train_chain(
        m.log, n_levels=3, x_range=(0.5, 5.0),
        n_samples=60, epochs=3000, restarts=5, verbose=False,
    )
    print(f"   loss={info_ln_cold['loss']:.2e} "
          f"max_err={info_ln_cold['max_error']:.2e} "
          f"({time.time()-t0:.1f}s)")
    print(f"   structure: {info_ln_cold['structure']}")

    # Phase 3: ln(x) @ depth 3 — warm from exp chain (gentle pass-through)
    print("\n[phase 3] ln(x) @ depth 3 (WARM from exp, pass_through=1.0)")
    t0 = time.time()
    m_ln_warm, info_ln_warm = train_chain(
        m.log, n_levels=3, x_range=(0.5, 5.0),
        n_samples=60, epochs=3000, restarts=1, verbose=False,
        warm_from=m_exp,
    )
    print(f"   loss={info_ln_warm['loss']:.2e} "
          f"max_err={info_ln_warm['max_error']:.2e} "
          f"({time.time()-t0:.1f}s)")
    print(f"   structure: {info_ln_warm['structure']}")

    # Phase 4: ln(x) @ depth 4 — wider cold, stronger search
    print("\n[phase 4] ln(x) @ depth 4 (COLD, 5 restarts — wider search)")
    t0 = time.time()
    m_ln_d4, info_ln_d4 = train_chain(
        m.log, n_levels=4, x_range=(0.5, 5.0),
        n_samples=60, epochs=3000, restarts=5, verbose=False,
    )
    print(f"   loss={info_ln_d4['loss']:.2e} "
          f"max_err={info_ln_d4['max_error']:.2e} "
          f"({time.time()-t0:.1f}s)")
    print(f"   structure: {info_ln_d4['structure']}")

    # Verdict
    print("\n" + "=" * 64)
    print(f"cold @3:  max_err = {info_ln_cold['max_error']:.2e}")
    print(f"warm @3:  max_err = {info_ln_warm['max_error']:.2e}")
    print(f"cold @4:  max_err = {info_ln_d4['max_error']:.2e}")
    best = min(info_ln_cold['max_error'], info_ln_warm['max_error'],
               info_ln_d4['max_error'])
    print(f"best:     max_err = {best:.2e}  "
          f"({'EXACT' if best < 1e-6 else 'approximate' if best < 0.1 else 'poor'})")


def demo_sweep_depth4():
    """Sweep depth-4 chain against a range of target functions to map
    what's reachable from cold random init with clamped eml.
    """
    import math as m
    import time

    print("EML Depth-4 Chain Sweep — what can cold random init reach?")
    print("=" * 64)

    # (name, fn, x_range, n_levels)
    targets = [
        ("exp(x)",   m.exp,                  (0.0, 3.0), 1),
        ("ln(x)",    m.log,                  (0.5, 5.0), 3),
        ("1/x",      lambda x: 1.0/x,        (0.5, 5.0), 4),
        ("x^2",      lambda x: x*x,          (0.5, 3.0), 4),
        ("sqrt(x)",  m.sqrt,                 (0.5, 5.0), 4),
        ("x",        lambda x: x,            (0.5, 5.0), 3),
        ("sin(x)",   m.sin,                  (0.1, 3.0), 4),
        ("cos(x)",   m.cos,                  (0.1, 3.0), 4),
    ]

    results = []
    for name, fn, xr, nlev in targets:
        t0 = time.time()
        mdl, info = train_chain(
            fn, n_levels=nlev, x_range=xr,
            n_samples=60, epochs=3000, restarts=5, verbose=False,
        )
        elapsed = time.time() - t0
        err = info.get("max_error", float("inf"))
        loss = info.get("loss", float("inf"))
        verdict = ("EXACT    " if err < 1e-6
                   else "APPROX   " if err < 0.05
                   else "LOOSE    " if err < 1.0
                   else "FAIL     ")
        results.append((name, nlev, err, loss, elapsed, verdict,
                        info.get("structure")))
        print(f"  {verdict} {name:9s} L={nlev}  "
              f"err={err:.2e}  loss={loss:.2e}  ({elapsed:.0f}s)")

    print("\n" + "=" * 64)
    print("Structures of EXACT and APPROX finds:")
    for name, nlev, err, loss, _, verdict, struct in results:
        if verdict.strip() in ("EXACT", "APPROX"):
            print(f"\n  {name} ({verdict.strip()}, err={err:.2e}):")
            if struct and struct.get("levels"):
                for i, lvl in enumerate(struct["levels"], start=1):
                    print(f"    L{i}: eml({lvl['left']}, {lvl['right']})")


def demo_overnight_search(log_path: str | None = None) -> None:
    """High-restart search for functions that failed the quick sweep.
    Logs every restart's best loss to see the recovery-rate distribution.

    Targets: identity (L=4 wide), 1/x (L=5 wide), sqrt (L=5 wide).
    All theoretically reachable; paper reports <25% cold-init success at
    depth >=3 so restart count matters.
    """
    import math as m
    import time
    import json
    import io

    log_lines: list[str] = []

    def log(line: str) -> None:
        print(line, flush=True)
        log_lines.append(line)

    log("EML Overnight Search — 40 restarts per function, L=4/5 wide")
    log("=" * 70)

    targets = [
        ("identity", lambda x: x,       (0.5, 5.0), 4),
        ("1/x",      lambda x: 1.0/x,   (0.5, 5.0), 5),
        ("sqrt",     m.sqrt,            (0.5, 5.0), 5),
    ]

    n_restarts = 40
    epochs = 5000
    harden_end = 0.01

    for name, fn, xr, nlev in targets:
        log(f"\n[{name} @ L={nlev} wide — {n_restarts} restarts, "
            f"epochs={epochs}, harden_end_T={harden_end}]")
        t_func_start = time.time()

        per_restart = []
        best_overall_loss = float("inf")
        best_model: EMLChainWide | None = None
        best_info: dict = {}

        for r in range(n_restarts):
            t_r = time.time()
            mdl, info = train_chain_wide(
                fn, n_levels=nlev, x_range=xr,
                n_samples=50, epochs=epochs, restarts=1,
                harden_end_temp=harden_end,
                seed_base=13 + r * 97,  # wide seed variance
                verbose=False,
            )
            rl = info.get("loss", float("inf"))
            re = info.get("max_error", float("inf"))
            per_restart.append({"restart": r, "loss": rl, "max_error": re,
                                 "time_s": round(time.time() - t_r, 1)})
            if rl < best_overall_loss:
                best_overall_loss = rl
                best_model = mdl
                best_info = info
            if rl < 1e-18:
                log(f"  r{r:2d}: loss={rl:.2e} max_err={re:.2e} CONVERGED")
                break
            if r % 5 == 0 or r == n_restarts - 1:
                log(f"  r{r:2d}: loss={rl:.2e} max_err={re:.2e} "
                    f"(best so far {best_overall_loss:.2e})")

        elapsed = time.time() - t_func_start
        log(f"  -> {n_restarts} restarts in {elapsed:.0f}s. "
            f"Best loss={best_overall_loss:.2e}")

        if best_model is not None:
            # Discrete verification
            xs_np = [xr[0] + (xr[1] - xr[0]) * i / 49 for i in range(50)]
            targets_np = [fn(x) for x in xs_np]
            xs_t = torch.tensor(xs_np, dtype=torch.float64)
            with torch.no_grad():
                disc = best_model.forward_discrete(xs_t).real.tolist()
            disc_err = max(abs(p - t) for p, t in zip(disc, targets_np))
            diag = best_model.softmax_diagnostics()
            log(f"  discrete max_err: {disc_err:.3e}")
            log(f"  min_max_weight: {diag['min_max_weight']:.6f}")
            if best_info.get("structure"):
                log(f"  structure: {best_info['structure']['levels']}")
            if disc_err < 1e-6:
                log(f"  VERDICT: EXACT — discrete tree verified")
            elif disc_err < 0.05:
                log(f"  VERDICT: APPROX (disc err {disc_err:.2e})")
            else:
                log(f"  VERDICT: no converged restart")

        # Recovery-rate histogram
        bucketed = {"exact (<1e-10)": 0, "near (<1e-4)": 0,
                    "loose (<1.0)": 0, "fail": 0}
        for r in per_restart:
            if r["loss"] < 1e-10:
                bucketed["exact (<1e-10)"] += 1
            elif r["loss"] < 1e-4:
                bucketed["near (<1e-4)"] += 1
            elif r["loss"] < 1.0:
                bucketed["loose (<1.0)"] += 1
            else:
                bucketed["fail"] += 1
        log(f"  recovery histogram: {bucketed}")

    log("\n" + "=" * 70)
    log("Overnight search complete.")

    if log_path:
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except Exception:
            pass


def demo_discretization_gap():
    """IP-critical verification: does hard-argmax give the same error as
    the trained softmax mixture? If yes, the discrete tree is the wire form.
    If no, we only have a soft approximation and the bit-count story is fake.
    """
    import math as m
    import time

    print("EML Discretization Gap Verification")
    print("=" * 64)
    print("For each converged function, compare:")
    print("  (a) softmax-continuous evaluation (training form)")
    print("  (b) hard-argmax discrete evaluation (wire form)")
    print("=" * 64)

    # Re-train the two known-converged cases and verify
    cases = [
        ("exp(x)", m.exp, (0.3, 3.0), 1),
        ("ln(x)",  m.log, (0.5, 5.0), 3),
    ]

    for name, fn, xr, nlev in cases:
        print(f"\n[{name} @ L={nlev}]")
        t0 = time.time()
        model, info = train_chain(
            fn, n_levels=nlev, x_range=xr,
            n_samples=60, epochs=3000, restarts=5, verbose=False,
        )
        elapsed = time.time() - t0

        if model is None:
            print(f"  train failed ({elapsed:.0f}s)")
            continue

        # Continuous error (as before)
        cont_err = info["max_error"]

        # Softmax diagnostics
        diag = model.softmax_diagnostics()
        min_max_w = diag["min_max_weight"]
        max_ent = max(r["entropy"] for r in diag["per_input"])

        # Discrete evaluation
        xs_np = [xr[0] + (xr[1] - xr[0]) * i / 59 for i in range(60)]
        targets = [fn(x) for x in xs_np]
        xs_t = torch.tensor(xs_np, dtype=torch.float64)
        disc_preds = model.forward_discrete(xs_t).real.tolist()
        disc_err = max(abs(p - t) for p, t in zip(disc_preds, targets))

        # Verdict
        ratio = disc_err / cont_err if cont_err > 0 else float("inf")
        print(f"  continuous max_err : {cont_err:.3e}")
        print(f"  discrete   max_err : {disc_err:.3e}")
        print(f"  softmax confidence : min_max_weight={min_max_w:.6f}, max_entropy={max_ent:.3e}")
        print(f"  train time         : {elapsed:.0f}s")
        if disc_err < 1e-6 and cont_err < 1e-6:
            print(f"  VERDICT: CLEAN SNAP — discrete tree evaluates to machine precision.")
        elif abs(disc_err - cont_err) / max(cont_err, 1e-30) < 0.01:
            print(f"  VERDICT: MATCH — discrete ≈ continuous (ratio {ratio:.3f})")
        else:
            print(f"  VERDICT: GAP — discrete diverges from continuous by {ratio:.2e}x")
            print(f"           (softmax didn't fully snap; hardening insufficient)")

    print("\n" + "=" * 64)
    print("If all verdicts are CLEAN SNAP or MATCH, the discrete tree IS")
    print("the wire form and the encoding bit-count claim holds.")


def demo():
    """Quick demo of the master formula approach."""
    import math as m

    functions = [
        ("exp(x)", m.exp, (0.0, 3.0), 2),
        ("ln(x)", m.log, (0.1, 5.0), 2),
        ("x^2", lambda x: x**2, (0.1, 4.0), 3),
        ("1/x", lambda x: 1/x, (0.1, 5.0), 3),
        ("sqrt(x)", m.sqrt, (0.1, 5.0), 3),
        ("sin(x)", m.sin, (0.1, 6.0), 4),
    ]

    print("EML Master Formula — Symbolic Regression Demo")
    print("=" * 60)

    for name, fn, xr, depth in functions:
        print(f"\n{name} (depth={depth}):")
        model, info = train_eml(
            fn, depth=depth, x_range=xr,
            n_samples=50, epochs=3000, restarts=3,
            verbose=False
        )
        if model is not None:
            loss = info.get("loss", float('inf'))
            max_err = info.get("max_error", float('inf'))
            structure = info.get("structure", {})
            print(f"  loss={loss:.2e}  max_err={max_err:.6f}")
            print(f"  leaves: {structure.get('leaves', [])}")
            print(f"  nodes: {structure.get('nodes', [])}")

            # Sample evaluation
            for x_val in [0.5, 1.0, 2.0]:
                if xr[0] <= x_val <= xr[1]:
                    with torch.no_grad():
                        pred = model(torch.tensor(x_val, dtype=torch.complex128))
                    expected = fn(x_val)
                    print(f"  f({x_val}) = {pred.real.item():.6f} (expect {expected:.6f})")
        else:
            print("  FAILED to converge")


if __name__ == "__main__":
    demo()
