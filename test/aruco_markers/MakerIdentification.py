import cv2
import numpy as np

# 1. ArUco configuration
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

# 2. Physical parameters of the chessboard (in mm and pixels)
GRID_SIDE_MM = 256.0  # 8 squares of 32 mm
IMG_SIDE_PX = 800     # Warped image resolution (100 px per square)
OFFSET_MM = 2.0       # Offset caused by the 2 mm white border

# Automatic pixel offset calculation (2 mm * 3.125 px/mm = 6.25 px)
px_per_mm = IMG_SIDE_PX / GRID_SIDE_MM
off_px = OFFSET_MM * px_per_mm

# If the black corners are 2 mm OUTSIDE the grid, in the 800x800 image
# they are located at -6.25 px and 806.25 px:
dst_points = np.array([
    [-off_px, -off_px],                           # Marker 0 (a8 - top left)
    [IMG_SIDE_PX + off_px, -off_px],              # Marker 1 (h8 - top right)
    [IMG_SIDE_PX + off_px, IMG_SIDE_PX + off_px], # Marker 2 (h1 - bottom right)
    [-off_px, IMG_SIDE_PX + off_px],              # Marker 3 (a1 - bottom left)
], dtype="float32")

cap = cv2.VideoCapture(0)  # Change 0 to 1 or an IP URL if using an external camera
if not cap.isOpened():
    print("Error: unable to connect to the camera stream!")
    print("Check that the camera index/IP is correct and any browser stream is CLOSED.")
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

        # If all 4 markers (0, 1, 2, 3) are visible
        if all(k in marker_map for k in [0, 1, 2, 3]):
            pt_a8 = marker_map[0][2]  # Bottom-Right of ID 0
            pt_h8 = marker_map[1][3]  # Bottom-Left of ID 1
            pt_h1 = marker_map[2][0]  # Top-Left of ID 2
            pt_a1 = marker_map[3][1]  # Top-Right of ID 3

            src_points = np.array([pt_a8, pt_h8, pt_h1, pt_a1], dtype="float32")

            # Homography and perspective warp
            M = cv2.getPerspectiveTransform(src_points, dst_points)
            warped = cv2.warpPerspective(frame, M, (IMG_SIDE_PX, IMG_SIDE_PX))

            # Draw verification grid (Green = 100x100, Yellow = 60x60 ROI)
            files = "abcdefgh"
            ranks = "87654321"
            pad = 20  # 20 px margin -> 60x60 px center square

            for r in range(8):
                for c in range(8):
                    x1, y1 = c * 100, r * 100
                    x2, y2 = x1 + 100, y1 + 100

                    # 100x100 cell border (Green)
                    cv2.rectangle(warped, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    # 60x60 center ROI (Yellow)
                    cv2.rectangle(warped, (x1 + pad, y1 + pad), (x2 - pad, y2 - pad), (0, 255, 255), 1)
                    # Square name (e.g., a8, e4)
                    cv2.putText(warped, f"{files[c]}{ranks[r]}", (x1 + 5, y1 + 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

            cv2.imshow("Warped Chessboard 800x800", warped)

    cv2.imshow("Original Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
