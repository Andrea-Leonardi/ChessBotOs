import os
import time
import cv2
import numpy as np

# 1. ArUco configuration (identical to MakerIdentification.py)
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, cv2.aruco.DetectorParameters())

# 2. Physical chessboard parameters (in mm and pixels)
GRID_SIDE_MM = 256.0  # 8 squares of 32 mm
IMG_SIDE_PX = 800     # Warped image 800x800 (100 px per square)
CELL_SIZE = IMG_SIDE_PX // 8
OFFSET_MM = 2.0       # 2 mm white border around the grid

px_per_mm = IMG_SIDE_PX / GRID_SIDE_MM
off_px = OFFSET_MM * px_per_mm

DST_POINTS = np.array([
    [-off_px, -off_px],                           # Marker 0 (a8 - top left)
    [IMG_SIDE_PX + off_px, -off_px],              # Marker 1 (h8 - top right)
    [IMG_SIDE_PX + off_px, IMG_SIDE_PX + off_px], # Marker 2 (h1 - bottom right)
    [-off_px, IMG_SIDE_PX + off_px],              # Marker 3 (a1 - bottom left)
], dtype="float32")

FILES = "abcdefgh"
RANKS = "87654321"

# Output directory at project root (ChessBotOs/datasets)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))


def next_capture_index(dataset_dir: str) -> int:
    """Find the next available progressive capture index in dataset_dir."""
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


def save_board_cells(board_img: np.ndarray, dataset_dir: str, capture_idx: int) -> str:
    """Save the full warped board and the 64 cell images (100x100)."""
    capture_name = f"scatto_{capture_idx:04d}"
    capture_dir = os.path.join(dataset_dir, capture_name)
    os.makedirs(capture_dir, exist_ok=True)

    # Save full warped board as reference
    cv2.imwrite(os.path.join(capture_dir, f"{capture_name}_full.png"), board_img)

    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            cell_img = board_img[y1:y2, x1:x2]
            square_name = f"{FILES[c]}{RANKS[r]}"
            cell_path = os.path.join(capture_dir, f"{capture_name}_{square_name}.png")
            cv2.imwrite(cell_path, cell_img)

    return capture_dir


def draw_overlay(board_img: np.ndarray) -> np.ndarray:
    """Return a copy of the board image with verification grid and square labels."""
    vis = board_img.copy()
    pad = 20
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
            cv2.rectangle(vis, (x1 + pad, y1 + pad), (x2 - pad, y2 - pad), (0, 255, 255), 1)
            cv2.putText(vis, f"{FILES[c]}{RANKS[r]}", (x1 + 5, y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    return vis


def main() -> None:
    os.makedirs(DATASET_DIR, exist_ok=True)
    capture_idx = next_capture_index(DATASET_DIR)

    cap = cv2.VideoCapture(0)  # Change 0 to 1 or an IP URL if using an external camera
    if not cap.isOpened():
        print("Error: unable to open camera!")
        return

    print("Controls:")
    print("  [SPACE] -> Capture board and save 64 cells")
    print("  [Q]     -> Quit")

    status_msg = ""
    status_until = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        corners, ids, _ = DETECTOR.detectMarkers(frame)
        board_clean = None

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            marker_map = {id_val: corner[0] for corner, id_val in zip(corners, ids.flatten())}

            if all(k in marker_map for k in (0, 1, 2, 3)):
                src_points = np.array([
                    marker_map[0][2],  # Bottom-Right of ID 0 (a8)
                    marker_map[1][3],  # Bottom-Left of ID 1 (h8)
                    marker_map[2][0],  # Top-Left of ID 2 (h1)
                    marker_map[3][1],  # Top-Right of ID 3 (a1)
                ], dtype="float32")

                M = cv2.getPerspectiveTransform(src_points, DST_POINTS)
                board_clean = cv2.warpPerspective(frame, M, (IMG_SIDE_PX, IMG_SIDE_PX))
                board_vis = draw_overlay(board_clean)

                if time.time() < status_until:
                    cv2.putText(board_vis, status_msg, (15, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)

                cv2.imshow("Warped Chessboard 800x800", board_vis)

        # Show command status on the original camera window
        info_text = "SPACE: Save 64 cells | Q: Quit"
        if time.time() < status_until:
            info_text = status_msg
        color = (0, 255, 0) if board_clean is not None else (0, 165, 255)
        cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imshow("Original Camera", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            if board_clean is not None:
                out_dir = save_board_cells(board_clean, DATASET_DIR, capture_idx)
                status_msg = f"Saved scatto_{capture_idx:04d} (64 cells)"
                status_until = time.time() + 2.0
                print(f"[OK] {status_msg} -> {out_dir}")
                capture_idx += 1
            else:
                status_msg = "Markers 0,1,2,3 not all visible!"
                status_until = time.time() + 2.0
                print(f"[WARN] {status_msg}")
        elif key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
