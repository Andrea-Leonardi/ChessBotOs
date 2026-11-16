import csv
import os
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


def next_capture_index(dataset_dir: str) -> int:
    if not os.path.exists(dataset_dir):
        return 1
    existing = [
        d for d in os.listdir(dataset_dir)
        if d.startswith("scatto_") and os.path.isdir(os.path.join(dataset_dir, d))
    ]
    nums = []
    for name in existing:
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


def save_board_cells(board_bgr: np.ndarray, dataset_dir: str, capture_idx: int) -> list[tuple[str, np.ndarray]]:
    capture_name = f"scatto_{capture_idx:04d}"
    capture_dir = os.path.join(dataset_dir, capture_name)
    os.makedirs(capture_dir, exist_ok=True)
    cv2.imwrite(os.path.join(capture_dir, f"{capture_name}_full.png"), board_bgr)

    saved: list[tuple[str, np.ndarray]] = []
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            cell_img = board_bgr[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]
            square_name = f"{FILES[c]}{RANKS[r]}"
            fname = f"{capture_name}_{square_name}.png"
            full_path = os.path.join(capture_dir, fname)
            cv2.imwrite(full_path, cell_img)
            rel_path = f"{capture_name}/{fname}"
            saved.append((rel_path, cell_img))
    return saved


def label_non_empty_cells(
    non_empty: list[tuple[str, np.ndarray, str]],
    labels_3cls: dict[str, str],
    labels_13cls: dict[str, str],
) -> None:
    """Display a quick window to label only cells detected as non-empty."""
    win_name = "Label Detected Pieces"
    display_size = 380
    banner_h = 120
    idx = 0

    while 0 <= idx < len(non_empty):
        rel_path, img, pred_color = non_empty[idx]
        zoomed = cv2.resize(img, (display_size, display_size), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((display_size + banner_h, display_size, 3), dtype=np.uint8)
        canvas[:display_size, :] = zoomed

        col = (0, 220, 0) if pred_color == "white" else (0, 180, 255)
        cv2.putText(canvas, f"[{idx + 1}/{len(non_empty)}] {rel_path}", (10, display_size + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(canvas, f"Detected color: {pred_color.upper()} (W/C to change)", (10, display_size + 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, col, 1)
        cv2.putText(canvas, "R:Rook N:Knight B:Bishop Q:Queen K:King P:Pawn", (10, display_size + 74),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1)
        cv2.putText(canvas, "E:Empty | Z:Back | X/ESC:Done", (10, display_size + 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        cv2.imshow(win_name, canvas)
        key = cv2.waitKey(0) & 0xFF

        if key in KEY_TO_PIECE:
            piece = KEY_TO_PIECE[key]
            labels_3cls[rel_path] = pred_color
            labels_13cls[rel_path] = f"{pred_color}_{piece}"
            save_csv_map(LABELS_3CLS_CSV, labels_3cls)
            save_csv_map(LABELS_13CLS_CSV, labels_13cls)
            idx += 1
        elif key in (ord("e"), ord("E")):
            labels_3cls[rel_path] = "empty"
            labels_13cls[rel_path] = "empty"
            save_csv_map(LABELS_3CLS_CSV, labels_3cls)
            save_csv_map(LABELS_13CLS_CSV, labels_13cls)
            idx += 1
        elif key in (ord("w"), ord("W")):
            non_empty[idx] = (rel_path, img, "white")
        elif key in (ord("c"), ord("C")):
            non_empty[idx] = (rel_path, img, "black")
        elif key in (ord("z"), ord("Z")):
            idx = max(0, idx - 1)
        elif key in (ord("x"), ord("X"), 27):
            break

    cv2.destroyWindow(win_name)


def draw_live_overlay(board_bgr: np.ndarray, preds: list[str], status_msg: str) -> np.ndarray:
    vis = board_bgr.copy()
    for r in range(8):
        for c in range(8):
            pred = preds[r * 8 + c]
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            color = (0, 220, 0) if pred == "white" else ((0, 180, 255) if pred == "black" else (90, 90, 90))
            cv2.rectangle(vis, (x1, y1), (x1 + CELL_SIZE, y1 + CELL_SIZE), color, 2 if pred != "empty" else 1)
            if pred != "empty":
                cv2.putText(vis, pred[0].upper(), (x1 + 8, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    cv2.rectangle(vis, (0, 0), (IMG_SIDE_PX, 32), (0, 0, 0), -1)
    cv2.putText(vis, status_msg, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2)
    return vis


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"SmartPieceCollector on {device}")

    model_3cls, classes_3cls = load_3class_model(MODEL_3CLS_PATH, device)
    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    labels_3cls = load_csv_map(LABELS_3CLS_CSV)
    labels_13cls = load_csv_map(LABELS_13CLS_CSV)
    capture_idx = next_capture_index(DATASET_DIR)

    cap = cv2.VideoCapture(0)  # Change 0 to 1 or an IP URL if using an external camera
    if not cap.isOpened():
        print("Error: unable to open camera!")
        return

    print("Controls:")
    print("  [SPACE] -> Capture, auto-save empty cells, and label only detected pieces")
    print("  [X/ESC] -> Quit")

    status_msg = "SPACE: Capture & Label | X: Quit"
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
                msg = status_msg if time.time() < status_until else f"Detected pieces: {n_pieces} | SPACE: Capture"
                vis = draw_live_overlay(board_clean, preds_3cls, msg)
                cv2.imshow("SmartPieceCollector - Board", vis)

        cv2.imshow("Original Camera", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            if board_clean is not None and preds_3cls is not None:
                saved_cells = save_board_cells(board_clean, DATASET_DIR, capture_idx)
                non_empty = []
                auto_empty = 0

                for (rel_path, cell_img), pred_lbl in zip(saved_cells, preds_3cls):
                    if pred_lbl == "empty":
                        labels_3cls[rel_path] = "empty"
                        labels_13cls[rel_path] = "empty"
                        auto_empty += 1
                    else:
                        non_empty.append((rel_path, cell_img, pred_lbl))

                save_csv_map(LABELS_3CLS_CSV, labels_3cls)
                save_csv_map(LABELS_13CLS_CSV, labels_13cls)
                print(f"[scatto_{capture_idx:04d}] Auto-empty: {auto_empty} | To label: {len(non_empty)}")

                if non_empty:
                    label_non_empty_cells(non_empty, labels_3cls, labels_13cls)

                status_msg = f"Saved scatto_{capture_idx:04d} ({len(non_empty)} pieces)"
                status_until = time.time() + 2.5
                capture_idx += 1
            else:
                status_msg = "Markers 0,1,2,3 not all visible!"
                status_until = time.time() + 2.0
        elif key in (ord("x"), ord("X"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
