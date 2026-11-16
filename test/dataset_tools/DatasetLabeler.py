import csv
import os
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
LABELS_CSV = os.path.join(DATASET_DIR, "labels.csv")

KEY_TO_LABEL = {
    ord("w"): "white",
    ord("W"): "white",
    ord("b"): "black",
    ord("B"): "black",
    ord("e"): "empty",
    ord("E"): "empty",
}

DISPLAY_SIZE = 400
BANNER_H = 95


def collect_cell_images(dataset_dir: str) -> list[str]:
    """Collect relative paths of all cell PNGs in dataset_dir (excluding *_full.png)."""
    if not os.path.exists(dataset_dir):
        return []
    cells = []
    for root, _, files in os.walk(dataset_dir):
        for fname in sorted(files):
            if fname.lower().endswith(".png") and not fname.lower().endswith("_full.png"):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, dataset_dir).replace("\\", "/")
                cells.append(rel_path)
    cells.sort()
    return cells


def load_labels(csv_path: str) -> dict[str, str]:
    """Load already-saved labels from labels.csv."""
    labels: dict[str, str] = {}
    if not os.path.exists(csv_path):
        return labels
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel = row.get("rel_path", "").strip()
            lbl = row.get("label", "").strip()
            if rel and lbl:
                labels[rel] = lbl
    return labels


def save_labels(csv_path: str, labels: dict[str, str]) -> None:
    """Save all labels in deterministic order to labels.csv."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rel_path", "label"])
        for rel_path in sorted(labels.keys()):
            writer.writerow([rel_path, labels[rel_path]])


def render_ui(img: np.ndarray, rel_path: str, idx: int, total: int, current_label: str | None) -> np.ndarray:
    """Build the UI window with zoomed cell image and key hints."""
    zoomed = cv2.resize(img, (DISPLAY_SIZE, DISPLAY_SIZE), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((DISPLAY_SIZE + BANNER_H, DISPLAY_SIZE, 3), dtype=np.uint8)
    canvas[:DISPLAY_SIZE, :] = zoomed

    cv2.rectangle(canvas, (0, DISPLAY_SIZE), (DISPLAY_SIZE, DISPLAY_SIZE + BANNER_H), (30, 30, 30), -1)

    progress = f"[{idx + 1}/{total}] {rel_path}"
    cv2.putText(canvas, progress, (10, DISPLAY_SIZE + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    lbl_text = f"Current label: {current_label.upper()}" if current_label else "Unlabeled"
    lbl_color = (0, 255, 180) if current_label else (0, 200, 255)
    cv2.putText(canvas, lbl_text, (10, DISPLAY_SIZE + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, lbl_color, 1, cv2.LINE_AA)

    cv2.putText(canvas, "W: White | B: Black | E: Empty", (10, DISPLAY_SIZE + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Z: Back | S: Skip | X/ESC: Quit", (10, DISPLAY_SIZE + 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)
    return canvas


def main() -> None:
    cells = collect_cell_images(DATASET_DIR)
    if not cells:
        print(f"No cell images found in: {DATASET_DIR}")
        return

    labels = load_labels(LABELS_CSV)
    idx = next((i for i, c in enumerate(cells) if c not in labels), 0)

    print(f"Found {len(cells)} cells in {DATASET_DIR}")
    print(f"Already labeled: {len(labels)} | Remaining: {len(cells) - len(labels)}")
    print("Controls: [W] White  [B] Black  [E] Empty  [Z] Back  [S] Skip  [X/ESC] Quit")

    while 0 <= idx < len(cells):
        rel_path = cells[idx]
        full_path = os.path.join(DATASET_DIR, rel_path)
        img = cv2.imread(full_path)
        if img is None:
            print(f"[WARN] Unable to read {full_path}, skipping.")
            idx += 1
            continue

        ui = render_ui(img, rel_path, idx, len(cells), labels.get(rel_path))
        cv2.imshow("Chessboard Dataset Labeler", ui)

        key = cv2.waitKey(0) & 0xFF
        if key in KEY_TO_LABEL:
            label = KEY_TO_LABEL[key]
            labels[rel_path] = label
            save_labels(LABELS_CSV, labels)
            print(f"[{idx + 1}/{len(cells)}] {rel_path} -> {label}")
            idx += 1
        elif key in (ord("z"), ord("Z"), 8):
            if idx > 0:
                idx -= 1
        elif key in (ord("s"), ord("S")):
            idx += 1
        elif key in (ord("x"), ord("X"), 27):
            break

    cv2.destroyAllWindows()
    print(f"Session finished. Labels saved to: {LABELS_CSV} ({len(labels)}/{len(cells)})")


if __name__ == "__main__":
    main()
