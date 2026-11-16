import cv2
import numpy as np

# 1. Physical settings (300 DPI on A4 sheet: 210 x 297 mm)
DPI = 300
mm_to_px = DPI / 25.4  # ~11.811 pixels per millimeter

a4_width = int(round(210 * mm_to_px))   # 2480 px
a4_height = int(round(297 * mm_to_px))  # 3508 px

# Create a blank white A4 sheet
a4_sheet = np.ones((a4_height, a4_width), dtype=np.uint8) * 255

# 2. Physical dimensions of the marker on the 22 mm frame
black_side_mm = 15.0    # The black ArUco square will be exactly 15x15 mm
white_border_mm = 2.0   # 2 mm white margin around it (19x19 mm total)

side_px = int(round(black_side_mm * mm_to_px))      # 177 pixels
border_px = int(round(white_border_mm * mm_to_px))  # 24 pixels

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# 3. Place the 4 markers in a row at the top of the A4 sheet
for marker_id in range(4):
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, side_px)

    x_start = 200 + marker_id * (side_px + 2 * border_px + 150)
    y_start = 200

    # Paste the black square onto the A4 sheet
    a4_sheet[y_start : y_start + side_px, x_start : x_start + side_px] = marker

    # Draw a thin gray outer border as a cutting guide
    cv2.rectangle(
        a4_sheet,
        (x_start - border_px, y_start - border_px),
        (x_start + side_px + border_px, y_start + side_px + border_px),
        180, 1,
    )
    # Write the ID below the box so markers are easy to distinguish
    cv2.putText(a4_sheet, f"ID {marker_id}", (x_start, y_start + side_px + border_px + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)

cv2.imwrite("stampa_A4_markers_15mm.png", a4_sheet)
print("Created stampa_A4_markers_15mm.png!")
