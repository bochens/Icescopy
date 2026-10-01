"""Train one setup using the PNGs and circle labels saved by data.py."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from torch.utils.data import DataLoader, Dataset

from data import targets
from model import DropletNet, loss


class CropDataset(Dataset):
    def __init__(self, manifest):
        self.path = Path(manifest).resolve()
        self.meta = json.loads(self.path.read_text())
        if self.meta.get("split") != "train" or not self.meta.get("setup"):
            raise ValueError("Expected a training crop manifest for one named setup")
        self.rows = self.meta["samples"]
        if not self.rows:
            raise ValueError("The training crop manifest is empty")
        self.recording_id = self.meta["source"]["recording_id"]
        if any(row["recording_id"] != self.recording_id for row in self.rows):
            raise ValueError("This run must contain only its selected training recording")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        image = np.array(Image.open(self.path.parent / row["image"]).convert("RGB"))
        valid = np.array(Image.open(self.path.parent / row["valid_mask"])) > 0
        labels = json.loads((self.path.parent / row["labels"]).read_text())
        if (labels.get("split") != "train" or labels.get("setup") != self.meta["setup"]
                or labels.get("recording_id") != self.recording_id):
            raise ValueError("Crop labels do not belong to this training recording")
        if image.shape[:2] != valid.shape or image.shape[0] != image.shape[1]:
            raise ValueError("A training crop and its padding mask must have the same square dimensions")
        circles = np.asarray(labels["circles"], dtype=np.float64).reshape(-1, 3)
        expected = targets(circles, valid, stride=DropletNet.stride)
        return torch.from_numpy(image.transpose(2, 0, 1).copy()).float() / 255, {
            name: torch.from_numpy(array) for name, array in expected.items()}


def fit(manifest, output, pretrained, *, epochs=20, batch_size=8, seed=0, device="cpu", threads=4):
    if epochs < 1 or batch_size < 1 or threads < 1:
        raise ValueError("Epochs, batch size, and thread count must be positive")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    dataset = CropDataset(manifest)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0,
                        generator=torch.Generator().manual_seed(seed))
    model = DropletNet(pretrained).to(device).train()
    encoder_ids = {id(p) for p in model.encoder.parameters()}
    optimizer = torch.optim.AdamW([
        {"params": model.encoder.parameters(), "lr": 0.0002},
        {"params": [p for p in model.parameters() if id(p) not in encoder_ids], "lr": 0.001},
    ], weight_decay=0.0001)
    output.mkdir(parents=True)
    start = time.perf_counter()
    history = []
    for epoch in range(epochs):
        sums = {k: 0.0 for k in ("total", "center", "offsets", "radius")}
        for image, target in loader:
            image = image.to(device)
            target = {k: v.to(device) for k, v in target.items()}
            optimizer.zero_grad(set_to_none=True)
            terms = loss(model(image), target)
            if not torch.isfinite(terms["total"]):
                raise FloatingPointError("Non-finite training loss; no model exported")
            terms["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
            optimizer.step()
            for k, value in terms.items():
                sums[k] += float(value.detach()) * len(image)
        row = {k: v / len(dataset) for k, v in sums.items()}
        row.update(epoch=epoch + 1, seconds=time.perf_counter() - start)
        history.append(row)
        (output / "training.json").write_text(json.dumps(history, indent=2) + "\n")
        print(f"epoch {epoch + 1}/{epochs} loss={row['total']:.4f} center={row['center']:.4f} "
              f"geometry={row['offsets'] + row['radius']:.4f} elapsed={row['seconds']:.1f}s", flush=True)
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    metadata = {"format": "icescopy-droplet-net-v1", "state_dict": state,
                "setup": dataset.meta.get("setup"), "epochs": epochs, "batch_size": batch_size,
                "seed": seed, "crop_size": int(image.shape[-1]), "stride": model.stride,
                "parameters": sum(p.numel() for p in model.parameters()),
                "training_manifest_sha256": hashlib.sha256(dataset.path.read_bytes()).hexdigest(),
                "pretrained_sha256": hashlib.sha256(Path(pretrained).read_bytes()).hexdigest(),
                "training_seconds": time.perf_counter() - start,
                "evaluation_used_for_training": False}
    torch.save(metadata, output / "model.pt")
    print(f"Saved {output / 'model.pt'} ({metadata['parameters']:,} parameters)", flush=True)
    return output / "model.pt"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--pretrained", type=Path,
                   default=Path(__file__).resolve().parents[1] / "pretrained/mobilenet_v3_small-047dcff4.pth")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    args = p.parse_args()
    fit(**vars(args))


if __name__ == "__main__":
    main()
