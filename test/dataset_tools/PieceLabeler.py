import csv
import os
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
SOURCE_LABELS_CSV = os.path.join(DATASET_DIR, "labels.csv")
PIECES_LABELS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")

KEY_TO_PIECE = {
    ord("r"): "rook",
    ord("R"): "rook",
    ord("n"): "knight",
    ord("N"): "knight",
    ord("b"): "bishop",
    ord("B"): "bishop",
    ord("q"): "queen",
    ord("Q"): "queen",
    ord("k"): "king",
    ord("K"): "king",
    ord("p"): "pawn",
    ord("P"): "pawn",
}

DISPLAY_SIZE = 400
BANNER_H = 115


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


def render_ui(
    img: np.ndarray,
    rel_path: str,
    color_name: str,
    idx: int,
    total: int,
    current_label: str | None,
) -> np.ndarray:
    zoomed = cv2.resize(img, (DISPLAY_SIZE, DISPLAY_SIZE), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((DISPLAY_SIZE + BANNER_H, DISPLAY_SIZE, 3), dtype=np.uint8)
    canvas[:DISPLAY_SIZE, :] = zoomed

    cv2.rectangle(canvas, (0, DISPLAY_SIZE), (DISPLAY_SIZE, DISPLAY_SIZE + BANNER_H), (30, 30, 30), -1)

    cv2.putText(canvas, f"[{idx + 1}/{total}] {rel_path}", (10, DISPLAY_SIZE + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

    col_bgr = (255, 220, 0) if color_name == "white" else (0, 140, 255)
    cv2.putText(canvas, f"Color: {color_name.upper()}", (10, DISPLAY_SIZE + 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, col_bgr, 1, cv2.LINE_AA)

    lbl_text = f"Piece: {current_label}" if current_label else "Piece: UNASSIGNED"
    lbl_col = (0, 255, 180) if current_label else (0, 200, 255)
    cv2.putText(canvas, lbl_text, (185, DISPLAY_SIZE + 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, lbl_col, 1, cv2.LINE_AA)

    cv2.putText(canvas, "R:Rook   N:Knight  B:Bishop", (10, DISPLAY_SIZE + 72),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Q:Queen  K:King    P:Pawn", (10, DISPLAY_SIZE + 92),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Z:Back | S:Skip | X/ESC:Quit", (10, DISPLAY_SIZE + 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)
    return canvas


def main() -> None:
    if not os.path.exists(SOURCE_LABELS_CSV):
        print(f"Error: {SOURCE_LABELS_CSV} not found. Run DatasetLabeler.py first.")
        return

    base_labels = load_csv_map(SOURCE_LABELS_CSV)
    piece_labels = load_csv_map(PIECES_LABELS_CSV)

    # Automatically copy all empty cells without prompting
    added_empty = 0
    for rel, lbl in base_labels.items():
        if lbl == "empty" and rel not in piece_labels:
            piece_labels[rel] = "empty"
            added_empty += 1
    if added_empty > 0:
        save_csv_map(PIECES_LABELS_CSV, piece_labels)

    # Select only images labeled as "white" or "black"
    targets = sorted(
        (rel, lbl) for rel, lbl in base_labels.items() if lbl in ("white", "black")
    )

    if not targets:
        print("No non-empty images found in labels.csv.")
        return

    idx = next((i for i, (rel, _) in enumerate(targets) if rel not in piece_labels), 0)
    done_count = sum(1 for rel, _ in targets if rel in piece_labels)

    print(f"Empty cells auto-copied: {sum(1 for v in piece_labels.values() if v == 'empty')}")
    print(f"Pieces to label: {len(targets)} | Done: {done_count} | Remaining: {len(targets) - done_count}")
    print("Controls: [R] Rook  [N] Knight  [B] Bishop  [Q] Queen  [K] King  [P] Pawn | [Z] Back [X/ESC] Quit")

    while 0 <= idx < len(targets):
        rel_path, color_name = targets[idx]
        full_path = os.path.join(DATASET_DIR, rel_path)
        img = cv2.imread(full_path)
        if img is None:
            print(f"[WARN] Unable to read {full_path}, skipping.")
            idx += 1
            continue

        ui = render_ui(img, rel_path, color_name, idx, len(targets), piece_labels.get(rel_path))
        cv2.imshow("Piece Labeler (13 Classes)", ui)

        key = cv2.waitKey(0) & 0xFF
        if key in KEY_TO_PIECE:
            full_label = f"{color_name}_{KEY_TO_PIECE[key]}"
            piece_labels[rel_path] = full_label
            save_csv_map(PIECES_LABELS_CSV, piece_labels)
            print(f"[{idx + 1}/{len(targets)}] {rel_path} -> {full_label}")
            idx += 1
        elif key in (ord("z"), ord("Z"), 8):
            if idx > 0:
                idx -= 1
        elif key in (ord("s"), ord("S")):
            idx += 1
        elif key in (ord("x"), ord("X"), 27):
            break

    cv2.destroyAllWindows()
    print(f"Saved to: {PIECES_LABELS_CSV} (total rows: {len(piece_labels)})")


if __name__ == "__main__":
    main()
