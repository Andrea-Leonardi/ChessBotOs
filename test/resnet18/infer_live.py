import os
import time

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "best_resnet18.pth")

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, cv2.aruco.DetectorParameters())

LATO_GRIGLIA_MM = 256.0
LATO_IMG_PX = 800
CELL_SIZE = LATO_IMG_PX // 8
OFFSET_MM = 2.0

px_per_mm = LATO_IMG_PX / LATO_GRIGLIA_MM
off_px = OFFSET_MM * px_per_mm

PUNTI_DESTINAZIONE = np.array([
    [-off_px, -off_px],
    [LATO_IMG_PX + off_px, -off_px],
    [LATO_IMG_PX + off_px, LATO_IMG_PX + off_px],
    [-off_px, LATO_IMG_PX + off_px],
], dtype="float32")


def load_model(model_path: str, device: torch.device) -> tuple[nn.Module, list[str]]:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modello non trovato: {model_path}. Esegui prima train_resnet18.py.")

    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    classes = ckpt["classes"]

    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    return model, classes


def draw_board_predictions(
    board_img: np.ndarray,
    preds: list[tuple[str, float]],
    fps: float,
) -> np.ndarray:
    vis = board_img.copy()
    colors = {
        "bianco": (0, 220, 0),
        "nero": (0, 180, 255),
        "vuota": (140, 140, 140),
    }

    for r in range(8):
        for c in range(8):
            label, conf = preds[r * 8 + c]
            x1, y1 = c * CELL_SIZE, r * CELL_SIZE
            x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
            color = colors.get(label, (255, 255, 255))

            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2 if label != "vuota" else 1)
            if label != "vuota":
                tag = f"{label[0].upper()} {conf * 100:.0f}%"
                cv2.putText(vis, tag, (x1 + 8, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    cv2.rectangle(vis, (0, 0), (LATO_IMG_PX, 32), (0, 0, 0), -1)
    cv2.putText(vis, f"ResNet18 (3 classi) | FPS: {fps:.1f} | Q: Esci", (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return vis


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Inferenza live su: {device}")

    model, classes = load_model(MODEL_PATH, device)
    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Errore: impossibile aprire la telecamera!")
        return

    prev_t = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        corners, ids, _ = DETECTOR.detectMarkers(frame)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            marker_map = {id_val: corner[0] for corner, id_val in zip(corners, ids.flatten())}

            if all(k in marker_map for k in (0, 1, 2, 3)):
                punti_sorgente = np.array([
                    marker_map[0][2],
                    marker_map[1][3],
                    marker_map[2][0],
                    marker_map[3][1],
                ], dtype="float32")

                M = cv2.getPerspectiveTransform(punti_sorgente, PUNTI_DESTINAZIONE)
                board_clean = cv2.warpPerspective(frame, M, (LATO_IMG_PX, LATO_IMG_PX))

                batch_tensors = []
                for r in range(8):
                    for c in range(8):
                        x1, y1 = c * CELL_SIZE, r * CELL_SIZE
                        cell_bgr = board_clean[y1:y1 + CELL_SIZE, x1:x1 + CELL_SIZE]
                        cell_rgb = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2RGB)
                        batch_tensors.append(tf(Image.fromarray(cell_rgb)))

                batch = torch.stack(batch_tensors).to(device, non_blocking=True)
                with torch.no_grad():
                    probs = torch.softmax(model(batch), dim=1)
                    confs, pred_idxs = probs.max(dim=1)

                preds = [(classes[i.item()], float(c.item())) for i, c in zip(pred_idxs, confs)]
                now = time.time()
                fps = 1.0 / max(1e-6, now - prev_t)
                prev_t = now

                cv2.imshow("Scacchiera ResNet18 (3 classi)", draw_board_predictions(board_clean, preds, fps))

        cv2.imshow("Telecamera Originale", frame)
        if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
