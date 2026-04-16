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
