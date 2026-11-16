import argparse
import csv
import os
import shutil
import time

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
MODEL_3CLS_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "resnet18", "models", "best_resnet18.pth"))
LABELS_3CLS_CSV = os.path.join(DATASET_DIR, "labels.csv")
LABELS_13CLS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, cv2.aruco.DetectorParameters())

GRID_SIDE_MM = 256.0
IMG_SIDE_PX = 800
CELL_SIZE = IMG_SIDE_PX // 8
OFFSET_MM = 2.0

px_per_mm = IMG_SIDE_PX / GRID_SIDE_MM
off_px = OFFSET_MM * px_per_mm

DST_POINTS = np.array([
    [-off_px, -off_px],
    [IMG_SIDE_PX + off_px, -off_px],
    [IMG_SIDE_PX + off_px, IMG_SIDE_PX + off_px],
    [-off_px, IMG_SIDE_PX + off_px],
], dtype="float32")

FILES = "abcdefgh"
RANKS = "87654321"

PIECE_ALIASES = {
    "r": "rook",
    "rook": "rook",
    "n": "knight",
    "knight": "knight",
    "b": "bishop",
    "bishop": "bishop",
    "q": "queen",
    "queen": "queen",
    "k": "king",
    "king": "king",
    "p": "pawn",
    "pawn": "pawn",
}

COLOR_ALIASES = {
    "w": "white",
    "white": "white",
    "b": "black",
    "black": "black",
    "auto": "auto",
    "": "auto",
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


def next_targeted_index(dataset_dir: str) -> int:
    if not os.path.exists(dataset_dir):
        return 1
    nums = []
    for name in os.listdir(dataset_dir):
        if name.startswith("mirato_") and os.path.isdir(os.path.join(dataset_dir, name)):
            try:
                nums.append(int(name.split("_")[1]))
            except (IndexError, ValueError):
                pass
    return (max(nums) + 1) if nums else 1


def load_3class_model(model_path: str, device: torch.device) -> tuple[nn.Module, list[str]]:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"3-class model not found: {model_path}")
    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    classes = ckpt["classes"]
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    return model, classes


def classify_cells_3cls(
    board_bgr: np.ndarray,
    model: nn.Module,
    classes: list[str],
    tf: transforms.Compose,
    device: torch.device,
) -> list[str]:
    batch_tensors = []
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            cell_bgr = board_bgr[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]
            cell_rgb = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2RGB)
            batch_tensors.append(tf(Image.fromarray(cell_rgb)))
    batch = torch.stack(batch_tensors).to(device, non_blocking=True)
    with torch.no_grad():
        preds = model(batch).argmax(dim=1)
    return [classes[p.item()] for p in preds]


def prompt_target_piece() -> tuple[str, str]:
    print("\n=== Set target piece to capture ===")
    while True:
        raw_piece = input("Piece [R=rook, N=knight, B=bishop, Q=queen, K=king, P=pawn]: ").strip().lower()
        if raw_piece in PIECE_ALIASES:
            piece = PIECE_ALIASES[raw_piece]
            break
        print("Invalid value. Use R, N, B, Q, K, P (or full piece name).")

    while True:
        raw_color = input("Color [W=white, B=black, ENTER/AUTO=use model predicted color]: ").strip().lower()
        if raw_color in COLOR_ALIASES:
            color_mode = COLOR_ALIASES[raw_color]
            break
        print("Invalid value. Use W, B, or press ENTER for AUTO.")

    print(f"--> Active target: piece={piece}, color={color_mode.upper()}\n")
    return piece, color_mode


def save_non_empty_cells(
    board_bgr: np.ndarray,
    preds_3cls: list[str],
    dataset_dir: str,
    shot_idx: int,
    target_piece: str,
    color_mode: str,
) -> list[tuple[str, str, str]]:
    """Save ONLY non-empty cells and return [(rel_path, label_3cls, label_13cls), ...]."""
    shot_name = f"mirato_{shot_idx:04d}"
    shot_dir = os.path.join(dataset_dir, shot_name)
    saved: list[tuple[str, str, str]] = []

    for idx, pred_3cls in enumerate(preds_3cls):
        if pred_3cls == "empty":
            continue

        r, c = divmod(idx, 8)
        x1, y1 = c * CELL_SIZE, r * CELL_SIZE
        cell_img = board_bgr[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]

        os.makedirs(shot_dir, exist_ok=True)
        square_name = f"{FILES[c]}{RANKS[r]}"
        fname = f"{shot_name}_{square_name}.png"
        cv2.imwrite(os.path.join(shot_dir, fname), cell_img)

        resolved_color = pred_3cls if color_mode == "auto" else color_mode
        rel_path = f"{shot_name}/{fname}"
        saved.append((rel_path, resolved_color, f"{resolved_color}_{target_piece}"))

    return saved


def draw_live_overlay(
    board_bgr: np.ndarray,
    preds: list[str],
    target_piece: str,
    color_mode: str,
    status_msg: str,
) -> np.ndarray:
    vis = board_bgr.copy()
    for r in range(8):
        for c in range(8):
            pred = preds[r * 8 + c]
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            cv2.rectangle(vis, (x1, y1), (x1 + CELL_SIZE, y1 + CELL_SIZE), (70, 70, 70), 1)
            if pred != "empty":
                resolved_color = pred if color_mode == "auto" else color_mode
                box_color = (0, 220, 0) if resolved_color == "white" else (0, 200, 255)
                cv2.rectangle(vis, (x1 + 2, y1 + 2), (x1 + CELL_SIZE - 2, y1 + CELL_SIZE - 2), box_color, 2)
                tag = f"{resolved_color[0].upper()}-{target_piece[:3].upper()}"
                cv2.putText(vis, tag, (x1 + 8, y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)

    cv2.rectangle(vis, (0, 0), (IMG_SIDE_PX, 34), (0, 0, 0), -1)
    cv2.putText(vis, status_msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return vis


def main() -> None:
    parser = argparse.ArgumentParser(description="Targeted piece acquisition without saving empty cells.")
    parser.add_argument("--piece", type=str, default="", help="Target piece (rook, knight, bishop, queen, king, pawn)")
    parser.add_argument("--color", type=str, default="", help="Target color (white, black, auto)")
    args = parser.parse_args()

    if args.piece.strip().lower() in PIECE_ALIASES:
        target_piece = PIECE_ALIASES[args.piece.strip().lower()]
        raw_col = args.color.strip().lower()
        color_mode = COLOR_ALIASES.get(raw_col, "auto")
    else:
        target_piece, color_mode = prompt_target_piece()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"TargetedPieceCollector on {device}")

    model_3cls, classes_3cls = load_3class_model(MODEL_3CLS_PATH, device)
    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    labels_3cls = load_csv_map(LABELS_3CLS_CSV)
    labels_13cls = load_csv_map(LABELS_13CLS_CSV)
    shot_idx = next_targeted_index(DATASET_DIR)
    history: list[tuple[int, list[str]]] = []

    cap = cv2.VideoCapture(0)  # Change 0 to 1 or an IP URL if using an external camera
    if not cap.isOpened():
        print("Error: unable to open camera!")
        return

    print("Window controls:")
    print("  [SPACE] -> Capture: discard empty cells and save/label only detected pieces")
    print("  [U]     -> Undo last targeted capture")
    print("  [M]     -> Change target piece/color from terminal")
    print("  [X/ESC] -> Quit")

    status_msg = f"Target: {target_piece} ({color_mode}) | SPACE: Capture"
    status_until = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        corners, ids, _ = DETECTOR.detectMarkers(frame)
        board_clean = None
        preds_3cls = None

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            marker_map = {id_val: corner[0] for corner, id_val in zip(corners, ids.flatten())}

            if all(k in marker_map for k in (0, 1, 2, 3)):
                src_points = np.array([
                    marker_map[0][2],
                    marker_map[1][3],
                    marker_map[2][0],
                    marker_map[3][1],
                ], dtype="float32")

                M = cv2.getPerspectiveTransform(src_points, DST_POINTS)
                board_clean = cv2.warpPerspective(frame, M, (IMG_SIDE_PX, IMG_SIDE_PX))
                preds_3cls = classify_cells_3cls(board_clean, model_3cls, classes_3cls, tf, device)

                n_pieces = sum(1 for p in preds_3cls if p != "empty")
                default_msg = f"Target: {target_piece} ({color_mode}) | Detected: {n_pieces} | SPACE: Capture"
                msg = status_msg if time.time() < status_until else default_msg
                vis = draw_live_overlay(board_clean, preds_3cls, target_piece, color_mode, msg)
                cv2.imshow("TargetedPieceCollector - Board", vis)

        cv2.imshow("Original Camera", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            if board_clean is not None and preds_3cls is not None:
                saved = save_non_empty_cells(board_clean, preds_3cls, DATASET_DIR, shot_idx, target_piece, color_mode)
                if not saved:
                    status_msg = "No pieces detected: nothing saved!"
                    status_until = time.time() + 2.0
                    continue

                added_paths = []
                for rel_path, lbl3, lbl13 in saved:
                    labels_3cls[rel_path] = lbl3
                    labels_13cls[rel_path] = lbl13
                    added_paths.append(rel_path)

                save_csv_map(LABELS_3CLS_CSV, labels_3cls)
                save_csv_map(LABELS_13CLS_CSV, labels_13cls)
                history.append((shot_idx, added_paths))

                summary = ", ".join(f"{os.path.basename(rp)}->{l13}" for rp, _, l13 in saved)
                print(f"[mirato_{shot_idx:04d}] Saved {len(saved)} pieces (empty discarded): {summary}")
                status_msg = f"mirato_{shot_idx:04d}: saved {len(saved)} pieces!"
                status_until = time.time() + 2.0
                shot_idx += 1
            else:
                status_msg = "Markers 0,1,2,3 not all visible!"
                status_until = time.time() + 2.0
        elif key in (ord("u"), ord("U")):
            if history:
                last_idx, last_paths = history.pop()
                for rp in last_paths:
                    labels_3cls.pop(rp, None)
                    labels_13cls.pop(rp, None)
                save_csv_map(LABELS_3CLS_CSV, labels_3cls)
                save_csv_map(LABELS_13CLS_CSV, labels_13cls)
                shutil.rmtree(os.path.join(DATASET_DIR, f"mirato_{last_idx:04d}"), ignore_errors=True)
                print(f"Undid mirato_{last_idx:04d} ({len(last_paths)} pieces removed).")
                status_msg = f"Undid mirato_{last_idx:04d}"
                status_until = time.time() + 2.0
        elif key in (ord("m"), ord("M")):
            target_piece, color_mode = prompt_target_piece()
            status_msg = f"New target: {target_piece} ({color_mode})"
            status_until = time.time() + 2.0
        elif key in (ord("x"), ord("X"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
