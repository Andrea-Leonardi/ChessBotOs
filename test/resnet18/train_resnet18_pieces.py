import csv
import os
import random
import time
from collections import Counter, defaultdict

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
LABELS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")
MODEL_OUT = os.path.join(BASE_DIR, "models", "best_resnet18_pieces.pth")

CLASSES = [
    "bianco_alfiere",
    "bianco_cavallo",
    "bianco_donna",
    "bianco_pedone",
    "bianco_re",
    "bianco_torre",
    "nero_alfiere",
    "nero_cavallo",
    "nero_donna",
    "nero_pedone",
    "nero_re",
    "nero_torre",
    "vuota",
]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

EPOCHS = 30
BATCH_SIZE = 32
LR = 3e-4
VAL_RATIO = 0.2
SEED = 42


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_samples(csv_path: str, dataset_dir: str) -> list[tuple[str, int]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File non trovato: {csv_path}")

    samples: list[tuple[str, int]] = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel = row["rel_path"].strip()
            lbl = row["label"].strip()
            if lbl not in CLASS_TO_IDX:
                continue
            full_path = os.path.join(dataset_dir, rel)
            if os.path.exists(full_path):
                samples.append((full_path, CLASS_TO_IDX[lbl]))
    return samples


def stratified_split(
    samples: list[tuple[str, int]], val_ratio: float, seed: int
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    rng = random.Random(seed)
    by_class: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for item in samples:
        by_class[item[1]].append(item)

    train_items, val_items = [], []
    for _, items in sorted(by_class.items()):
        rng.shuffle(items)
        n_val = max(1, int(round(len(items) * val_ratio)))
        val_items.extend(items[:n_val])
        train_items.extend(items[n_val:])

    rng.shuffle(train_items)
    rng.shuffle(val_items)
    return train_items, val_items


class CellDataset(Dataset):
    def __init__(self, samples: list[tuple[str, int]], transform: transforms.Compose):
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        path, label = self.samples[idx]
        with Image.open(path) as img:
            img = img.convert("RGB")
            return self.transform(img), label


def build_model(num_classes: int) -> nn.Module:
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, list[list[int]], list[tuple[str, int, int]]]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    num_classes = len(CLASSES)
    conf = [[0] * num_classes for _ in range(num_classes)]
    errors: list[tuple[str, int, int]] = []
    dataset_samples = loader.dataset.samples
    sample_offset = 0

    with torch.no_grad():
        for images, labels in loader:
            batch_n = images.size(0)
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += loss.item() * batch_n

            preds = outputs.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += batch_n

            for i in range(batch_n):
                t = labels[i].item()
                p = preds[i].item()
                conf[t][p] += 1
                if t != p:
                    errors.append((dataset_samples[sample_offset + i][0], t, p))
            sample_offset += batch_n

    return total_loss / max(1, total), correct / max(1, total), conf, errors


def safe_torch_save(obj: dict, path: str, retries: int = 8, delay: float = 0.5) -> None:
    """Salva su file temporaneo e sostituisce in modo atomico (evita lock di OneDrive/Windows)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    for attempt in range(1, retries + 1):
        try:
            torch.save(obj, tmp_path)
            os.replace(tmp_path, path)
            return
        except (PermissionError, RuntimeError, OSError) as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if attempt == retries:
                raise RuntimeError(
                    f"Impossibile salvare {path} (file bloccato da OneDrive o da un altro script aperto): {exc}"
                ) from exc
            time.sleep(delay)


def main() -> None:
    set_seed(SEED)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA non disponibile!")

    device = torch.device("cuda")
    print(f"Device in uso: {device} ({torch.cuda.get_device_name(0)})")

    samples = load_samples(LABELS_CSV, DATASET_DIR)
    print(f"Totale immagini caricate: {len(samples)}")
    counts = Counter(lbl for _, lbl in samples)
    for k in sorted(counts.keys()):
        print(f"  {CLASSES[k]:<15}: {counts[k]}")

    train_samples, val_samples = stratified_split(samples, VAL_RATIO, SEED)
    print(f"\nSplit -> Train: {len(train_samples)} | Validation: {len(val_samples)}\n")

    imagenet_mean = [0.485, 0.456, 0.406]
    imagenet_std = [0.229, 0.224, 0.225]

    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15),
        transforms.ToTensor(),
        transforms.Normalize(imagenet_mean, imagenet_std),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(imagenet_mean, imagenet_std),
    ])

    train_loader = DataLoader(
        CellDataset(train_samples, train_tf),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        CellDataset(val_samples, val_tf),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    train_counts = Counter(lbl for _, lbl in train_samples)
    total_train = len(train_samples)
    class_weights = torch.tensor(
        [total_train / (len(CLASSES) * max(1, train_counts[i])) for i in range(len(CLASSES))],
        dtype=torch.float32,
        device=device,
    )

    model = build_model(len(CLASSES)).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_val_acc = 0.0
    best_errors: list[tuple[str, int, int]] = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        running_loss = 0.0
        running_correct = 0
        seen = 0

        for images, labels in train_loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            n = images.size(0)
            running_loss += loss.item() * n
            running_correct += (outputs.argmax(dim=1) == labels).sum().item()
            seen += n

        scheduler.step()
        train_loss = running_loss / seen
        train_acc = running_correct / seen

        val_loss, val_acc, _, errors = evaluate(model, val_loader, criterion, device)

        marker = ""
        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            best_errors = errors
            safe_torch_save(
                {"model_state": model.state_dict(), "classes": CLASSES, "val_acc": val_acc},
                MODEL_OUT,
            )
            marker = "  <-- BEST"

        print(
            f"Epoch {epoch:02d}/{EPOCHS} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc * 100:6.2f}% | "
            f"Val Loss: {val_loss:.4f} Acc: {val_acc * 100:6.2f}%{marker}"
        )

    print("\n=== RISULTATI FINALI (BEST MODEL - 13 CLASSI) ===")
    print(f"Best Validation Accuracy: {best_val_acc * 100:.2f}%")
    print(f"Modello salvato in: {MODEL_OUT}")

    if best_errors:
        print(f"\nErrori sul validation set ({len(best_errors)}):")
        for path, t, p in best_errors:
            rel = os.path.relpath(path, DATASET_DIR)
            print(f"  {rel}: reale={CLASSES[t]} -> predetto={CLASSES[p]}")
    else:
        print("\nZero errori sul validation set!")


if __name__ == "__main__":
    main()
