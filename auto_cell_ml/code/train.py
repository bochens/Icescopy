"""Train a small setup CNN from dense labels on in-memory augmented original views."""
from __future__ import annotations

import argparse
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


class ViewDataset(Dataset):
    def __init__(self, manifest, setup, *, size=256, views=240, seed=0):
        self.path = Path(manifest).resolve()
        self.views = data.TrainingViews(self.path, setup, size=size, count=views, seed=seed)
        self.source, self.setup, self.size = self.views.source, self.views.setup, self.views.size

    def __len__(self):
        return len(self.views)

    def set_epoch(self, epoch):
        self.views.set_epoch(epoch)

    def __getitem__(self, index):
        image, circles, valid = self.views[index]
        target = data.targets(circles, valid, stride=DropletNet.stride)
        return torch.from_numpy(image.transpose(2, 0, 1).copy()).float() / 255, {
            name: torch.from_numpy(array) for name, array in target.items()}


def fit(manifest, output, *, setup, epochs=20, batch_size=8, seed=0, device="cpu", threads=4,
        size=256, views=240, onnx=False):
    if min(epochs, batch_size, threads, views) < 1 or seed < 0 or size < 32 or size % 4:
        raise ValueError("Counts must be positive, seed nonnegative, and size >=32 divisible by 4")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    start = time.perf_counter()
    dataset = ViewDataset(manifest, setup, size=size, views=views, seed=seed)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0,
                        generator=torch.Generator().manual_seed(seed))
    model = DropletNet().to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    output.mkdir(parents=True, exist_ok=False)
    history = []
    for epoch in range(epochs):
        dataset.set_epoch(epoch)
        epoch_start = time.perf_counter()
        sums = {key: 0.0 for key in ("total", "center", "offsets", "radius")}
        valid_cells = positive_cells = 0
        for image, target in loader:
            valid_cells += int(target["valid"].sum())
            positive_cells += int((target["center"] * target["valid"]).sum())
            image = image.to(device)
            target = {key: value.to(device) for key, value in target.items()}
            optimizer.zero_grad(set_to_none=True)
            terms = loss(model(image), target)
            if not torch.isfinite(terms["total"]):
                raise FloatingPointError("Non-finite training loss; no model exported")
            terms["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
            optimizer.step()
            for key, value in terms.items():
                sums[key] += float(value.detach()) * len(image)
        row = {key: value / len(dataset) for key, value in sums.items()}
        row.update(epoch=epoch + 1, epoch_seconds=time.perf_counter() - epoch_start,
                   seconds=time.perf_counter() - start, positive_grid_cells=positive_cells,
                   negative_grid_cells=valid_cells - positive_cells, valid_grid_cells=valid_cells)
        history.append(row)
        (output / "training.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
        print(f"epoch {epoch + 1}/{epochs} loss={row['total']:.4f} center={row['center']:.4f} "
              f"geometry={row['offsets'] + row['radius']:.4f} "
              f"positive={positive_cells} negative={valid_cells - positive_cells} "
              f"elapsed={row['seconds']:.1f}s", flush=True)
    metadata = {"format": FORMAT, "setup": setup, "source": dataset.source,
                "epochs": epochs, "batch_size": batch_size, "seed": seed,
                "crop_size": dataset.size, "stride": model.stride,
                "requested_views": views, "views_per_epoch": len(dataset),
                "coverage_tile_views": dataset.views.tile_count,
                "coverage_circle_views": dataset.views.circle_count,
                "parameters": sum(parameter.numel() for parameter in model.parameters()),
                "training_manifest_sha256": hashlib.sha256(dataset.path.read_bytes()).hexdigest(),
                "pretrained": False, "training_seconds": time.perf_counter() - start,
                "device": device, "threads": threads,
                "optimizer": {"name": "AdamW", "learning_rate": 0.001, "weight_decay": 0.0001},
                "supervision": "Every full valid stride4 block is positive at a marked center or negative; padding is unknown",
                "evaluation_used_for_training": False}
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    model_path = output / "model.pt"
    torch.save({**metadata, "state_dict": state}, model_path)
    metadata["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata["model_bytes"] = model_path.stat().st_size
    if onnx:
        try:
            export_onnx(model, output / "model.onnx", size=dataset.size)
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
    parser.add_argument("--setup", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--views", type=int, default=240)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--onnx", action="store_true", help="Export if the optional onnx package is available")
    try:
        fit(**vars(parser.parse_args()))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
