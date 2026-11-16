import csv
import os
from collections import Counter, defaultdict

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
LABELS_3CLS_CSV = os.path.join(DATASET_DIR, "labels.csv")
LABELS_13CLS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")
MODEL_13CLS_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "resnet18", "models", "best_resnet18_pieces.pth"))

COLONNE = "abcdefgh"
TRAVERSE = "87654321"
PIECE_TYPES = ("torre", "cavallo", "alfiere", "donna", "re", "pedone")

KEY_TO_PIECE = {
    ord("t"): "torre",
    ord("T"): "torre",
    ord("c"): "cavallo",
    ord("C"): "cavallo",
    ord("a"): "alfiere",
    ord("A"): "alfiere",
    ord("d"): "donna",
    ord("D"): "donna",
    ord("r"): "re",
    ord("R"): "re",
    ord("p"): "pedone",
    ord("P"): "pedone",
}


def load_csv_map(csv_path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    if not os.path.exists(csv_path):
        return data
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel = row.get("rel_path", "").strip()
            lbl = row.get("label", "").strip()
            if rel and lbl:
                data[rel] = lbl
    return data


def save_csv_map(csv_path: str, data: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rel_path", "label"])
        for rel_path in sorted(data.keys()):
            writer.writerow([rel_path, data[rel_path]])


def sync_3cls_label(label_13: str) -> str:
    if label_13 == "vuota":
        return "vuota"
    return label_13.split("_", 1)[0]


def find_missing_cells(dataset_dir: str, labels_13cls: dict[str, str]) -> list[tuple[str, str]]:
    """Trova celle esistenti su disco in scatto_XXXX ma assenti da labels_pieces.csv."""
    missing: list[tuple[str, str]] = []
    if not os.path.exists(dataset_dir):
        return missing

    for scatto in sorted(os.listdir(dataset_dir)):
        scatto_dir = os.path.join(dataset_dir, scatto)
        if not scatto.startswith("scatto_") or not os.path.isdir(scatto_dir):
            continue
        for r in range(8):
            for c in range(8):
                fname = f"{scatto}_{COLONNE[c]}{TRAVERSE[r]}.png"
                rel_path = f"{scatto}/{fname}"
                if os.path.exists(os.path.join(scatto_dir, fname)) and rel_path not in labels_13cls:
                    missing.append((rel_path, "Cella mancante dal CSV"))
    return missing


def find_anomalous_shot_cells(labels_13cls: dict[str, str]) -> list[tuple[str, str]]:
    """Individua le celle appartenenti a tipi di pezzo sbilanciati tra bianco e nero per singolo scatto."""
    by_shot: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rel_path, lbl in labels_13cls.items():
        shot = rel_path.split("/")[0]
        by_shot[shot].append((rel_path, lbl))

    flagged: list[tuple[str, str]] = []
    for shot in sorted(by_shot.keys()):
        items = by_shot[shot]
        counts = Counter(lbl for _, lbl in items)
        imbalanced_pieces = [
            p for p in PIECE_TYPES
            if counts.get(f"bianco_{p}", 0) != counts.get(f"nero_{p}", 0)
        ]
        if not imbalanced_pieces and len(items) == 64:
            continue

        suspect_labels = {f"bianco_{p}" for p in imbalanced_pieces} | {f"nero_{p}" for p in imbalanced_pieces}
        reason = f"{shot}: sbilanciato ({', '.join(imbalanced_pieces) or 'conteggio != 64'})"
        for rel_path, lbl in sorted(items):
            if lbl in suspect_labels:
                flagged.append((rel_path, reason))
    return flagged


def find_model_disagreements(
    dataset_dir: str,
    labels_13cls: dict[str, str],
    model_path: str,
    min_conf: float = 0.65,
) -> list[tuple[str, str]]:
    """Esegue inferenza con ResNet18 (13 classi) e segnala i disaccordi ordinati per confidenza."""
    if not os.path.exists(model_path):
        print(f"Modello 13 classi non trovato ({model_path}), salto il controllo disaccordi.")
        return []

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    classes: list[str] = ckpt["classes"]
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()

    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    valid_items: list[tuple[str, str, torch.Tensor]] = []
    for rel_path, human_lbl in sorted(labels_13cls.items()):
        img_path = os.path.join(dataset_dir, rel_path)
        img = cv2.imread(img_path)
        if img is None:
            continue
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        valid_items.append((rel_path, human_lbl, tf(Image.fromarray(rgb))))

    disagreements: list[tuple[float, str, str]] = []
    batch_size = 64
    with torch.no_grad():
        for i in range(0, len(valid_items), batch_size):
            chunk = valid_items[i:i + batch_size]
            batch = torch.stack([t for _, _, t in chunk]).to(device, non_blocking=True)
            probs = torch.softmax(model(batch), dim=1)
            confs, pred_idxs = probs.max(dim=1)
            for (rel_path, human_lbl, _), conf, pidx in zip(chunk, confs, pred_idxs):
                pred_lbl = classes[pidx.item()]
                conf_val = float(conf.item())
                if pred_lbl != human_lbl and conf_val >= min_conf:
                    disagreements.append((conf_val, rel_path, f"Modello: {pred_lbl} ({conf_val * 100:.0f}%)"))

    disagreements.sort(key=lambda x: x[0], reverse=True)
    return [(rel_path, reason) for _, rel_path, reason in disagreements]


def build_review_queue(dataset_dir: str, labels_13cls: dict[str, str], model_path: str) -> list[tuple[str, str]]:
    """Unisce celle mancanti, anomalie per scatto e disaccordi del modello evitando duplicati."""
    merged: dict[str, list[str]] = {}
    for source in (
        find_missing_cells(dataset_dir, labels_13cls),
        find_anomalous_shot_cells(labels_13cls),
        find_model_disagreements(dataset_dir, labels_13cls, model_path),
    ):
        for rel_path, reason in source:
            merged.setdefault(rel_path, [])
            if reason not in merged[rel_path]:
                merged[rel_path].append(reason)

    return [(rel_path, " | ".join(reasons)) for rel_path, reasons in merged.items()]


def review_cells(
    queue: list[tuple[str, str]],
    dataset_dir: str,
    labels_3cls: dict[str, str],
    labels_13cls: dict[str, str],
) -> int:
    win_name = "ReviewLabels - Correzione Rapida"
    display_size = 420
    banner_h = 150
    idx = 0
    changes = 0
    active_color: str | None = None

    while 0 <= idx < len(queue):
        rel_path, reason = queue[idx]
        img = cv2.imread(os.path.join(dataset_dir, rel_path))
        if img is None:
            idx += 1
            continue

        current_lbl = labels_13cls.get(rel_path, "MANCANTE")
        if active_color is None:
            if current_lbl.startswith("bianco_"):
                active_color = "bianco"
            elif current_lbl.startswith("nero_"):
                active_color = "nero"
            else:
                active_color = "bianco"

        zoomed = cv2.resize(img, (display_size, display_size), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((display_size + banner_h, display_size, 3), dtype=np.uint8)
        canvas[:display_size, :] = zoomed

        cv2.putText(canvas, f"[{idx + 1}/{len(queue)}] {rel_path}", (10, display_size + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(canvas, f"Attuale: {current_lbl} | Colore attivo: {active_color.upper()}",
                    (10, display_size + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.putText(canvas, reason[:54], (10, display_size + 82),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 220, 255), 1)
        cv2.putText(canvas, "T/C/A/D/R/P: Pezzo | B/N: Colore | V: Vuota",
                    (10, display_size + 112), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(canvas, "SPAZIO/INVIO: Conferma | Z: Indietro | Q: Salva ed Esci",
                    (10, display_size + 136), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (150, 255, 150), 1)

        cv2.imshow(win_name, canvas)
        key = cv2.waitKey(0) & 0xFF

        if key in (ord("q"), ord("Q"), 27):
            break
        elif key in (ord("z"), ord("Z")):
            idx = max(0, idx - 1)
            active_color = None
        elif key in (32, 13):  # SPAZIO o INVIO: conferma attuale
            idx += 1
            active_color = None
        elif key in (ord("b"), ord("B")):
            active_color = "bianco"
            if "_" in current_lbl:
                new_lbl = f"bianco_{current_lbl.split('_', 1)[1]}"
                labels_13cls[rel_path] = new_lbl
                labels_3cls[rel_path] = "bianco"
                changes += 1
        elif key in (ord("n"), ord("N")):
            active_color = "nero"
            if "_" in current_lbl:
                new_lbl = f"nero_{current_lbl.split('_', 1)[1]}"
                labels_13cls[rel_path] = new_lbl
                labels_3cls[rel_path] = "nero"
                changes += 1
        elif key in (ord("v"), ord("V")):
            if current_lbl != "vuota":
                labels_13cls[rel_path] = "vuota"
                labels_3cls[rel_path] = "vuota"
                changes += 1
            idx += 1
            active_color = None
        elif key in KEY_TO_PIECE:
            new_lbl = f"{active_color}_{KEY_TO_PIECE[key]}"
            if new_lbl != current_lbl:
                labels_13cls[rel_path] = new_lbl
                labels_3cls[rel_path] = sync_3cls_label(new_lbl)
                changes += 1
            idx += 1
            active_color = None

    cv2.destroyAllWindows()
    return changes


def main() -> None:
    labels_3cls = load_csv_map(LABELS_3CLS_CSV)
    labels_13cls = load_csv_map(LABELS_13CLS_CSV)

    queue = build_review_queue(DATASET_DIR, labels_13cls, MODEL_13CLS_PATH)
    if not queue:
        print("Nessuna cella sospetta trovata: il dataset sembra coerente!")
        return

    print(f"Trovate {len(queue)} celle sospette da verificare.")
    changes = review_cells(queue, DATASET_DIR, labels_3cls, labels_13cls)

    if changes > 0:
        save_csv_map(LABELS_13CLS_CSV, labels_13cls)
        save_csv_map(LABELS_3CLS_CSV, labels_3cls)
        print(f"Salvate {changes} modifiche in labels_pieces.csv e labels.csv.")
    else:
        print("Nessuna modifica effettuata.")


if __name__ == "__main__":
    main()
