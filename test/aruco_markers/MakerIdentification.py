import cv2
import numpy as np

# 1. Configurazione ArUco
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

# 2. Parametri fisici della tua scacchiera (in mm e pixel)
LATO_GRIGLIA_MM = 256.0  # 8 caselle da 32 mm
LATO_IMG_PX = 800        # Risoluzione immagine raddrizzata (100 px per casella)
OFFSET_MM = 2.0          # Spostamento dovuto al bordino bianco di 2 mm

# Calcolo automatico dell'offset in pixel (2 mm * 3.125 px/mm = 6.25 px)
px_per_mm = LATO_IMG_PX / LATO_GRIGLIA_MM
off_px = OFFSET_MM * px_per_mm

# Se gli spigoli neri sono 2 mm FUORI dalla griglia, nell'immagine 800x800
# si trovano a -6.25 px e 806.25 px:
punti_destinazione = np.array([
    [-off_px, -off_px],                        # Marker 0 (a8 - alto sx)
    [LATO_IMG_PX + off_px, -off_px],           # Marker 1 (h8 - alto dx)
    [LATO_IMG_PX + off_px, LATO_IMG_PX + off_px], # Marker 2 (h1 - basso dx)
    [-off_px, LATO_IMG_PX + off_px]            # Marker 3 (a1 - basso sx)
], dtype="float32")

cap = cv2.VideoCapture(0) # Cambia 0 con 1 o con l'URL IP se usi una camera esterna
if not cap.isOpened():
    print("Errore: impossibile connettersi allo stream dell'ESP32!")
    print("Controlla che l'IP sia giusto e che la pagina web sul browser sia CHIUSA.")
    exit()
while True:
    ret, frame = cap.read()
    if not ret:
        break

    corners, ids, _ = detector.detectMarkers(frame)
    
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        ids_flat = ids.flatten()
        marker_map = {id_val: corner[0] for corner, id_val in zip(corners, ids_flat)}

        # Se vede tutti e 4 i marker (0, 1, 2, 3)
        if all(k in marker_map for k in [0, 1, 2, 3]):
            pt_a8 = marker_map[0][2] # Basso-Destra di ID 0
            pt_h8 = marker_map[1][3] # Basso-Sinistra di ID 1
            pt_h1 = marker_map[2][0] # Alto-Sinistra di ID 2
            pt_a1 = marker_map[3][1] # Alto-Destra di ID 3

            punti_sorgente = np.array([pt_a8, pt_h8, pt_h1, pt_a1], dtype="float32")

            # Omografia e raddrizzamento
            M = cv2.getPerspectiveTransform(punti_sorgente, punti_destinazione)
            dritta = cv2.warpPerspective(frame, M, (LATO_IMG_PX, LATO_IMG_PX))

            # Disegna la griglia di verifica (Verde = 100x100, Giallo = ROI 60x60)
            colonne = "abcdefgh"
            traverse = "87654321"
            pad = 20 # 20 px di margine -> quadrato centrale 60x60 px

            for r in range(8):
                for c in range(8):
                    x1, y1 = c * 100, r * 100
                    x2, y2 = x1 + 100, y1 + 100
                    
                    # Bordo casella 100x100 (Verde)
                    cv2.rectangle(dritta, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    # Area centrale di lettura 60x60 (Giallo)
                    cv2.rectangle(dritta, (x1 + pad, y1 + pad), (x2 - pad, y2 - pad), (0, 255, 255), 1)
                    # Nome casella (es. a8, e4)
                    cv2.putText(dritta, f"{colonne[c]}{traverse[r]}", (x1 + 5, y1 + 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

            cv2.imshow("Scacchiera Raddrizzata 800x800", dritta)

    cv2.imshow("Telecamera Originale", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()