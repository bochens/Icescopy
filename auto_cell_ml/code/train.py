"""Developer training: pretrained MobileNet, augmented synthetic fit, then marked recordings."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

if __package__:
    from . import data
    from .model import DropletNet, FORMAT, export_onnx, loss
else:
    import data
    from model import DropletNet, FORMAT, export_onnx, loss


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ViewDataset(Dataset):
    """Balance sources per epoch while retaining every source's coverage views."""
    def __init__(self, view_sets):
        if not view_sets:
            raise ValueError("At least one labeled view source is required")
        self.views = list(view_sets)
        balanced_count = max(len(item) for item in self.views)
        for item in self.views:
            item.count = balanced_count
        self.ends = np.cumsum([len(item) for item in self.views]).tolist()
        self.sources = [{"setup": item.setup, "source": item.source, "views_per_epoch": len(item),
                         "coverage_tile_views": item.tile_count, "coverage_circle_views": item.circle_count}
                        for item in self.views]

    def __len__(self):
        return self.ends[-1]

    def set_epoch(self, epoch):
        for item in self.views:
            item.set_epoch(epoch)

    def __getitem__(self, index):
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        source = bisect_right(self.ends, index)
        local = index - (self.ends[source - 1] if source else 0)
        image, circles, valid, examples, example_mask, example_radii = self.views[source].episode(local)
        target = data.targets(circles, valid, stride=DropletNet.stride)
        return (torch.from_numpy(image.transpose(2, 0, 1).copy()).float() / 255,
                torch.from_numpy(examples.transpose(0, 3, 1, 2).copy()).float() / 255,
                torch.from_numpy(example_mask), torch.from_numpy(example_radii),
                {name: torch.from_numpy(array) for name, array in target.items()})


def _select_setups(manifest, setup, all_setups):
    if bool(setup) == bool(all_setups):
        raise ValueError("Choose explicit setup names or all_setups, not both")
    if all_setups:
        rows = json.loads(Path(manifest).read_text())["setups"]
        names = [row["setup"] for row in rows if row["train"].get("label_status") == "user_marked"]
    else:
        names = [setup] if isinstance(setup, str) else list(setup)
    if not names or len(set(names)) != len(names):
        raise ValueError("Training setup names must be nonempty and unique")
    return names


def fit(manifest, output, *, pretrained, synthetic_manifest, setup=None, all_setups=False,
        synthetic_epochs=3, epochs=20, batch_size=8, seed=0, device="cpu", threads=4,
        size=256, views=240, synthetic_views=64, onnx=False):
    if min(synthetic_epochs, epochs, batch_size, threads, views, synthetic_views) < 1 or seed < 0 or size < 32 or size % 4:
        raise ValueError("Counts must be positive, seed nonnegative, and size >=32 divisible by 4")
    output, manifest = Path(output).resolve(), Path(manifest).resolve()
    pretrained, synthetic_manifest = Path(pretrained).resolve(), Path(synthetic_manifest).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if not pretrained.is_file():
        raise FileNotFoundError(f"Required local pretrained file is missing: {pretrained}")
    selected = _select_setups(manifest, setup, all_setups)
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    start = time.perf_counter()
    synthetic = ViewDataset([data.TrainingViews.from_scene(scene["image"], scene["circles"], scene["source"],
                            setup=scene["source"]["scene_id"], size=size, count=synthetic_views, seed=seed + index)
                            for index, scene in enumerate(data.read_synthetic_fit(synthetic_manifest))])
    real = ViewDataset([data.TrainingViews(manifest, name, size=size, count=views, seed=seed + index)
                        for index, name in enumerate(selected)])
    model = DropletNet(pretrained).to(device).train()
    encoder_ids = {id(parameter) for parameter in model.encoder.parameters()}
    optimizer = torch.optim.AdamW([
        {"params": model.encoder.parameters(), "lr": 0.0002},
        {"params": [parameter for parameter in model.parameters() if id(parameter) not in encoder_ids], "lr": 0.001},
    ], weight_decay=0.0001)
    output.mkdir(parents=True, exist_ok=False)
    history, stages = [], []
    for stage_index, (name, dataset, stage_epochs) in enumerate((("synthetic", synthetic, synthetic_epochs), ("real", real, epochs))):
        stage_start = time.perf_counter()
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0,
                            generator=torch.Generator().manual_seed(seed + stage_index))
        print(f"stage={name} sources={len(dataset.sources)} views={len(dataset)} epochs={stage_epochs}", flush=True)
        for epoch in range(stage_epochs):
            dataset.set_epoch(epoch)
            epoch_start = time.perf_counter()
            sums = {key: 0.0 for key in ("total", "center", "offsets", "radius")}
            valid_cells = positive_cells = 0
            for image, examples, example_mask, example_radii, target in loader:
                valid_cells += int(target["valid"].sum())
                positive_cells += int((target["center"] * target["valid"]).sum())
                image = image.to(device)
                examples, example_mask, example_radii = (value.to(device) for value in (examples, example_mask, example_radii))
                target = {key: value.to(device) for key, value in target.items()}
                optimizer.zero_grad(set_to_none=True)
                terms = loss(model(image, examples, example_mask, example_radii), target)
                if not torch.isfinite(terms["total"]):
                    raise FloatingPointError("Non-finite training loss; no model exported")
                terms["total"].backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
                optimizer.step()
                for key, value in terms.items():
                    sums[key] += float(value.detach()) * len(image)
            row = {key: value / len(dataset) for key, value in sums.items()}
            row.update(stage=name, epoch=epoch + 1, epoch_seconds=time.perf_counter() - epoch_start,
                       seconds=time.perf_counter() - start, positive_grid_cells=positive_cells,
                       negative_grid_cells=valid_cells - positive_cells, valid_grid_cells=valid_cells)
            history.append(row)
            (output / "training.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
            print(f"{name} epoch {epoch + 1}/{stage_epochs} loss={row['total']:.4f} center={row['center']:.4f} "
                  f"geometry={row['offsets'] + row['radius']:.4f} "
                  f"positive={positive_cells} negative={valid_cells - positive_cells} elapsed={row['seconds']:.1f}s", flush=True)
        stages.append({"stage": name, "epochs": stage_epochs, "sources": dataset.sources,
                       "views_per_epoch": len(dataset), "seconds": time.perf_counter() - stage_start})
    metadata = {"format": FORMAT, "architecture": "Shared MobileNetV3-Small blocks0..8, stride4 query/reference interactions, center/geometry heads",
                "setup": "general" if all_setups or len(selected) > 1 else selected[0], "setups": selected,
                "source": real.sources, "stages": stages, "epochs": epochs, "synthetic_epochs": synthetic_epochs,
                "batch_size": batch_size, "seed": seed, "crop_size": size, "stride": model.stride,
                "requested_views_per_setup": views, "requested_views_per_synthetic_scene": synthetic_views,
                "parameters": sum(parameter.numel() for parameter in model.parameters()),
                "training_manifest_sha256": _hash(manifest), "synthetic_manifest_sha256": _hash(synthetic_manifest),
                "pretrained": True, "pretrained_sha256": _hash(pretrained),
                "training_seconds": time.perf_counter() - start, "device": device, "threads": threads,
                "optimizer": {"name": "AdamW", "encoder_learning_rate": 0.0002,
                              "head_learning_rate": 0.001, "weight_decay": 0.0001},
                "stage_continuation": "Same model and optimizer continue from synthetic to real",
                "normalization": "ImageNet RGB mean/std; encoder BatchNorm running statistics stay frozen",
                "conditioning": {"examples": "One or two positive cells from the full same source, masked mean of 64px shared-encoder descriptors",
                                 "fusion": "query*reference, abs(query-reference), cosine similarity, log(mean active pixel radius/16); no query-only head input",
                                 "augmentation": "Query and references share orientation, reflections and lighting; reference radii use query pixel scale",
                                 "runtime_training": False},
                "supervision": "Every full valid stride4 block is positive at a marked center or negative; padding is unknown",
                "evaluation_used_for_training": False}
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    model_path = output / "model.pt"
    torch.save({**metadata, "state_dict": state}, model_path)
    metadata["model_sha256"] = _hash(model_path)
    metadata["model_bytes"] = model_path.stat().st_size
    if onnx:
        try:
            export_onnx(model, output / "model.onnx", size=size)
            metadata["onnx_export"] = "saved model.onnx"
        except RuntimeError as exc:
            metadata["onnx_export"] = str(exc)
            print(str(exc), flush=True)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    print(f"Saved {model_path} ({metadata['parameters']:,} parameters)", flush=True)
    return model_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--setup", action="append", help="Explicit setup; repeat for more than one")
    selection.add_argument("--all-setups", action="store_true")
    parser.add_argument("--pretrained", type=Path, required=True)
    parser.add_argument("--synthetic-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for name, default in (("synthetic-epochs", 3), ("epochs", 20), ("batch-size", 8), ("size", 256),
                          ("views", 240), ("synthetic-views", 64), ("seed", 0), ("threads", 4)):
        parser.add_argument("--" + name, type=int, default=default)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--onnx", action="store_true", help="Export if the optional onnx package is available")
    try:
        fit(**vars(parser.parse_args()))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
