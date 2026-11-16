import cv2
import numpy as np

# 1. Impostazioni fisiche (300 DPI su foglio A4: 210 x 297 mm)
DPI = 300
mm_to_px = DPI / 25.4  # ~11.811 pixel per millimetro

larghezza_a4 = int(round(210 * mm_to_px))  # 2480 px
altezza_a4 = int(round(297 * mm_to_px))    # 3508 px

# Crea un foglio A4 tutto bianco
foglio_a4 = np.ones((altezza_a4, larghezza_a4), dtype=np.uint8) * 255

# 2. Dimensioni reali del marker sulla tua cornice da 22 mm
lato_nero_mm = 15.0    # Il quadrato nero ArUco sarà 15x15 mm esatti
bordo_bianco_mm = 2.0  # 2 mm di margine bianco intorno (totale 19x19 mm)

lato_px = int(round(lato_nero_mm * mm_to_px))      # 177 pixel
bordo_px = int(round(bordo_bianco_mm * mm_to_px))  # 24 pixel

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# 3. Posiziona i 4 marker in fila in alto sul foglio A4
for marker_id in range(4):
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, lato_px)
    
    x_start = 200 + marker_id * (lato_px + 2 * bordo_px + 150)
    y_start = 200
    
    # Incolla il quadrato nero sul foglio A4
    foglio_a4[y_start : y_start + lato_px, x_start : x_start + lato_px] = marker
    
    # Disegna un sottile tratteggio grigio esterno per sapere dove tagliare con le forbici
    cv2.rectangle(
        foglio_a4, 
        (x_start - bordo_px, y_start - bordo_px), 
        (x_start + lato_px + bordo_px, y_start + lato_px + bordo_px), 
        180, 1
    )
    # Scrive l'ID sotto al riquadro per non confonderli
    cv2.putText(foglio_a4, f"ID {marker_id}", (x_start, y_start + lato_px + bordo_px + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)

cv2.imwrite("stampa_A4_markers_15mm.png", foglio_a4)
print("File stampa_A4_markers_15mm.png creato!")