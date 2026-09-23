"""Small supervised multi-task baseline with held-out, per-mode promotion gates."""
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .dataset import FEATURE_SIZE, PublicPosition, features, split_for_game, target_vectors
from ..domain.tiles import ALL_TILES, normalize
from ..infrastructure.storage import save_json


def _torch():
    import torch
    return torch


def make_network():
    torch = _torch()
    class MultiTask(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.body = torch.nn.Sequential(torch.nn.Linear(FEATURE_SIZE, 128), torch.nn.ReLU(),
                                            torch.nn.Dropout(.15), torch.nn.Linear(128, 128), torch.nn.ReLU())
            self.tenpai = torch.nn.Linear(128, 1)
            self.waits = torch.nn.Linear(128, 34)
            self.ron = torch.nn.Linear(128, 34)

        def forward(self, x):
            hidden = self.body(x)
            return self.tenpai(hidden).squeeze(-1), self.waits(hidden), self.ron(hidden)
    return MultiTask()


def _arrays(examples):
    x = np.stack([features(example.public) for example in examples]).astype(np.float32)
    labels = [target_vectors(example) for example in examples]
    return x, np.array([label[0] for label in labels], np.float32), \
        np.stack([label[1] for label in labels]), np.stack([label[2] for label in labels]), \
        np.array([label[3] for label in labels], bool), np.array([label[4] for label in labels], bool)


def _fit_temperature(logits, labels):
    if not len(logits):
        return 1.0
    return min(np.linspace(.5, 3, 26), key=lambda t: np.mean((_sigmoid(logits / t) - labels) ** 2)).item()


def _sigmoid(value):
    return 1 / (1 + np.exp(-np.clip(value, -30, 30)))


def _brier(probabilities, labels):
    return float(np.mean((probabilities - labels) ** 2)) if len(labels) else None


def _binary_metrics(probabilities, labels):
    predicted = probabilities >= .5
    tp = int(np.sum(predicted & (labels == 1)))
    fp = int(np.sum(predicted & (labels == 0)))
    fn = int(np.sum(~predicted & (labels == 1)))
    bins = []
    for index in range(10):
        mask = (probabilities >= index / 10) & (probabilities < (index + 1) / 10 if index < 9 else probabilities <= 1)
        if mask.any():
            bins.append({"count": int(mask.sum()), "predicted": float(probabilities[mask].mean()),
                         "observed": float(labels[mask].mean())})
    ece = sum(row["count"] * abs(row["predicted"] - row["observed"]) for row in bins) / len(labels) if len(labels) else None
    return {"brier": _brier(probabilities, labels), "ece": ece, "calibration_bins": bins,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "positives": int(np.sum(labels)), "examples": len(labels)}


def _recall_at_five(probabilities, labels):
    if not len(probabilities):
        return None
    total = found = 0
    for scores, truth in zip(probabilities, labels):
        if truth.sum() == 0:
            continue
        top = np.argsort(-scores, kind="stable")[:5]
        found += int(truth[top].sum())
        total += int(truth.sum())
    return found / total if total else None


def _baseline_tenpai(train, test):
    """Calibrated discard-count buckets matching the existing rule thresholds."""
    def bucket(example):
        if example.public.riichi_confirmed:
            return 3
        count = len(example.public.rivers[example.public.target_seat])
        return 0 if count < 6 else 1 if count < 12 else 2
    prior = (sum(example.tenpai for example in train) + 1) / (len(train) + 2)
    rates = {}
    for index in range(4):
        group = [example for example in train if bucket(example) == index]
        rates[index] = (sum(example.tenpai for example in group) + prior * 2) / (len(group) + 2)
    return np.array([rates[bucket(example)] for example in test])


def train_mode(examples, mode: int, source_counts: dict, output_root: Path, epochs: int = 35) -> dict:
    torch = _torch()
    torch.manual_seed(17)
    np.random.seed(17)
    selected = [example for example in examples if example.public.mode == mode]
    splits = {name: [e for e in selected if split_for_game(e.game_id) == name]
              for name in ("train", "validation", "test")}
    report = {"mode": mode, "sources": source_counts,
              "samples": {name: len(rows) for name, rows in splits.items()},
              "games": {name: len({row.game_id for row in rows}) for name, rows in splits.items()},
              "promoted": False, "reason": ""}
    if any(not rows for rows in splits.values()):
        report["reason"] = "需要按整场牌局划分的训练、验证、测试样本"
        return report
    x_train, y_train, w_train, r_train, wm_train, rm_train = _arrays(splits["train"])
    x_val, y_val, w_val, r_val, wm_val, rm_val = _arrays(splits["validation"])
    x_test, y_test, w_test, r_test, wm_test, rm_test = _arrays(splits["test"])
    if len(set(y_train)) < 2:
        report["reason"] = "训练集缺少听牌或未听牌样本"
        return report
    device = "cuda" if torch.cuda.is_available() else "cpu"
    network = make_network().to(device)
    optimizer = torch.optim.AdamW(network.parameters(), lr=.001, weight_decay=.001)
    def tensors(x, y, w, r, wm, rm):
        return tuple(torch.as_tensor(array, dtype=torch.float32, device=device) for array in (x, y, w, r, wm, rm))
    train_tensors = tensors(x_train, y_train, w_train, r_train, wm_train, rm_train)
    val_tensors = tensors(x_val, y_val, w_val, r_val, wm_val, rm_val)

    def loss(values):
        x, y, waits, ron, wait_mask, ron_mask = values
        tenpai_logits, wait_logits, ron_logits = network(x)
        result = torch.nn.functional.binary_cross_entropy_with_logits(tenpai_logits, y)
        if wait_mask.sum() > 0:
            result = result + torch.nn.functional.binary_cross_entropy_with_logits(
                wait_logits, waits, reduction="none").mean(dim=1).mul(wait_mask).sum() / wait_mask.sum()
        if ron_mask.sum() > 0:
            result = result + torch.nn.functional.binary_cross_entropy_with_logits(
                ron_logits, ron, reduction="none").mean(dim=1).mul(ron_mask).sum() / ron_mask.sum()
        return result

    best, best_state, patience = float("inf"), None, 0
    for _ in range(epochs):
        network.train()
        for indices in torch.randperm(len(x_train), device=device).split(256):
            optimizer.zero_grad()
            value = loss(tuple(array[indices] for array in train_tensors))
            value.backward()
            optimizer.step()
        network.eval()
        with torch.no_grad():
            value = float(loss(val_tensors).item())
        if value < best - 1e-4:
            best, patience = value, 0
            best_state = {name: weight.detach().cpu().clone() for name, weight in network.state_dict().items()}
        else:
            patience += 1
            if patience >= 6:
                break
    network.load_state_dict(best_state)
    network.eval()
    def predict(x):
        with torch.no_grad():
            return tuple(output.cpu().numpy() for output in network(torch.as_tensor(x, device=device)))
    val_logits = predict(x_val)
    test_logits = predict(x_test)
    temperatures = {
        "tenpai": _fit_temperature(val_logits[0], y_val),
        "waits": _fit_temperature(val_logits[1][wm_val].ravel(), w_val[wm_val].ravel()),
        "ron": _fit_temperature(val_logits[2][rm_val].ravel(), r_val[rm_val].ravel()),
    }
    p_tenpai = _sigmoid(test_logits[0] / temperatures["tenpai"])
    p_wait = _sigmoid(test_logits[1] / temperatures["waits"])
    p_ron = _sigmoid(test_logits[2] / temperatures["ron"])
    baseline_tenpai = _baseline_tenpai(splits["train"], splits["test"])
    wait_prior = w_train[wm_train].mean(axis=0) if wm_train.any() else np.zeros(34)
    ron_prior = r_train[rm_train].mean(axis=0) if rm_train.any() else np.zeros(34)
    report["device"] = device
    report["temperatures"] = temperatures
    report["tenpai"] = {"model": _binary_metrics(p_tenpai, y_test),
                        "rule_bucket_baseline": _binary_metrics(baseline_tenpai, y_test)}
    report["waits"] = {"examples": int(wm_test.sum()),
                       "model_recall_at_5": _recall_at_five(p_wait[wm_test], w_test[wm_test]),
                       "prior_recall_at_5": _recall_at_five(np.broadcast_to(wait_prior, w_test[wm_test].shape), w_test[wm_test])}
    report["ron"] = {"examples": int(rm_test.sum()),
                     "model_brier": _brier(p_ron[rm_test].ravel(), r_test[rm_test].ravel()),
                     "prior_brier": _brier(np.broadcast_to(ron_prior, r_test[rm_test].shape).ravel(), r_test[rm_test].ravel())}
    real_sources = set(source_counts) - {"synthetic_demo"}
    checks = (not source_counts.get("synthetic_demo") and bool(real_sources)
              and report["games"]["test"] >= 20
              and report["tenpai"]["model"]["brier"] < report["tenpai"]["rule_bucket_baseline"]["brier"]
              and report["waits"]["model_recall_at_5"] is not None
              and report["waits"]["prior_recall_at_5"] is not None
              and report["waits"]["model_recall_at_5"] > report["waits"]["prior_recall_at_5"]
              and report["ron"]["model_brier"] is not None
              and report["ron"]["prior_brier"] is not None
              and report["ron"]["model_brier"] < report["ron"]["prior_brier"])
    report["promoted"] = bool(checks)
    report["reason"] = "达到独立测试门槛" if checks else "仅供实验：真实独立测试数量或效果未达展示门槛"
    output = output_root / f"{mode}p"
    output.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": best_state, "feature_size": FEATURE_SIZE}, output / "model.pt")
    save_json(output / "report.json", report)
    return report


@dataclass
class Prediction:
    model_version: str
    tenpai_probability: float
    waits: dict[str, float]
    ron: dict[str, float]


class ModelRegistry:
    def __init__(self, root: Path):
        self.root = root
        self._cache = {}

    def predict(self, public: "PublicPosition") -> Prediction | None:
        mode = public.mode
        folder = self.root / f"{mode}p"
        report_path, model_path = folder / "report.json", folder / "model.pt"
        if not report_path.exists() or not model_path.exists():
            return None
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not report.get("promoted"):
            return None
        torch = _torch()
        if mode not in self._cache:
            payload = torch.load(model_path, map_location="cpu", weights_only=True)
            if payload.get("feature_size") != FEATURE_SIZE:
                return None
            network = make_network()
            network.load_state_dict(payload["state_dict"])
            network.eval()
            self._cache[mode] = network
        with torch.no_grad():
            logits = self._cache[mode](torch.as_tensor(features(public)[None, :]))
        values = [_sigmoid(output.cpu().numpy()[0] / report["temperatures"][key])
                  for output, key in zip(logits, ("tenpai", "waits", "ron"))]
        visible = [normalize(tile) for tile in public.own_hand]
        visible += [normalize(tile) for river in public.rivers.values() for tile in river]
        count = {tile: visible.count(tile) for tile in ALL_TILES}
        tenpai_probability = float(values[0])
        if not public.riichi_confirmed and .35 <= tenpai_probability <= .65:
            return None
        waits = {tile: float(values[1][index]) for index, tile in enumerate(ALL_TILES)
                 if (mode == 4 or tile[1] != "m" or tile[0] in "19") and count[tile] < 4}
        if public.riichi_confirmed and (not waits or max(waits.values()) < .20):
            return None
        ron = {tile: float(values[2][index]) for index, tile in enumerate(ALL_TILES)
               if tile in waits and tile not in (public.target_history or public.rivers[public.target_seat])}
        return Prediction("0.3-baseline", tenpai_probability, waits if public.riichi_confirmed else {},
                          ron if public.riichi_confirmed else {})
