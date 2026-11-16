import os
import time
import cv2
import numpy as np

# 1. Configurazione ArUco (identica a MakerIdentification.py)
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, cv2.aruco.DetectorParameters())

# 2. Parametri fisici della scacchiera (in mm e pixel)
LATO_GRIGLIA_MM = 256.0  # 8 caselle da 32 mm
LATO_IMG_PX = 800        # Immagine raddrizzata 800x800 (100 px per casella)
CELL_SIZE = LATO_IMG_PX // 8
OFFSET_MM = 2.0          # Bordino bianco di 2 mm attorno alla griglia

px_per_mm = LATO_IMG_PX / LATO_GRIGLIA_MM
off_px = OFFSET_MM * px_per_mm

PUNTI_DESTINAZIONE = np.array([
    [-off_px, -off_px],                           # Marker 0 (a8 - alto sx)
    [LATO_IMG_PX + off_px, -off_px],              # Marker 1 (h8 - alto dx)
    [LATO_IMG_PX + off_px, LATO_IMG_PX + off_px], # Marker 2 (h1 - basso dx)
    [-off_px, LATO_IMG_PX + off_px]               # Marker 3 (a1 - basso sx)
], dtype="float32")

COLONNE = "abcdefgh"
TRAVERSE = "87654321"

# Cartella di output nella root del progetto (ChessBotOs/datasets)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))


def next_capture_index(dataset_dir: str) -> int:
    """Trova il prossimo indice progressivo libero in dataset_dir per non sovrascrivere scatti."""
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
    """Salva l'immagine intera raddrizzata e le 64 mini-immagini (100x100) una per casella."""
    capture_name = f"scatto_{capture_idx:04d}"
    capture_dir = os.path.join(dataset_dir, capture_name)
    os.makedirs(capture_dir, exist_ok=True)

    # Salva la scacchiera raddrizzata completa come riferimento
    cv2.imwrite(os.path.join(capture_dir, f"{capture_name}_full.png"), board_img)

    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            cell_img = board_img[y1:y2, x1:x2]
            square_name = f"{COLONNE[c]}{TRAVERSE[r]}"
            cell_path = os.path.join(capture_dir, f"{capture_name}_{square_name}.png")
            cv2.imwrite(cell_path, cell_img)

    return capture_dir


def draw_overlay(board_img: np.ndarray) -> np.ndarray:
    """Restituisce una copia dell'immagine con griglia ed etichette per la sola anteprima."""
    vis = board_img.copy()
    pad = 20
    for r in range(8):
        for c in range(8):
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
            cv2.rectangle(vis, (x1 + pad, y1 + pad), (x2 - pad, y2 - pad), (0, 255, 255), 1)
            cv2.putText(vis, f"{COLONNE[c]}{TRAVERSE[r]}", (x1 + 5, y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    return vis


def main() -> None:
    os.makedirs(DATASET_DIR, exist_ok=True)
    capture_idx = next_capture_index(DATASET_DIR)

    cap = cv2.VideoCapture(0)  # Cambia 0 con 1 o con l'URL IP se usi una camera esterna
    if not cap.isOpened():
        print("Errore: impossibile aprire la telecamera!")
        return

    print("Comandi:")
    print("  [SPAZIO] -> Acquisisci immagine e salva le 64 celle")
    print("  [Q]      -> Esci")

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
                punti_sorgente = np.array([
                    marker_map[0][2],  # Basso-Destra di ID 0 (a8)
                    marker_map[1][3],  # Basso-Sinistra di ID 1 (h8)
                    marker_map[2][0],  # Alto-Sinistra di ID 2 (h1)
                    marker_map[3][1],  # Alto-Destra di ID 3 (a1)
                ], dtype="float32")

                M = cv2.getPerspectiveTransform(punti_sorgente, PUNTI_DESTINAZIONE)
                board_clean = cv2.warpPerspective(frame, M, (LATO_IMG_PX, LATO_IMG_PX))
                board_vis = draw_overlay(board_clean)

                if time.time() < status_until:
                    cv2.putText(board_vis, status_msg, (15, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)

                cv2.imshow("Scacchiera Raddrizzata 800x800", board_vis)

        # Mostra stato sui comandi nella finestra originale
        info_text = "SPAZIO: Salva 64 celle | Q: Esci"
        if time.time() < status_until:
            info_text = status_msg
        color = (0, 255, 0) if board_clean is not None else (0, 165, 255)
        cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imshow("Telecamera Originale", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            if board_clean is not None:
                out_dir = save_board_cells(board_clean, DATASET_DIR, capture_idx)
                status_msg = f"Salvato scatto_{capture_idx:04d} (64 celle)"
                status_until = time.time() + 2.0
                print(f"[OK] {status_msg} -> {out_dir}")
                capture_idx += 1
            else:
                status_msg = "Marker 0,1,2,3 non tutti visibili!"
                status_until = time.time() + 2.0
                print(f"[WARN] {status_msg}")
        elif key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
