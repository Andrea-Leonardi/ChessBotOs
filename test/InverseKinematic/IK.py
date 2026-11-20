import numpy as np
import pandas as pd

origin_l = (-45,-92.1) 
origin_r = (45,-92.1) 
a = 183
b = 230

cols = ["a","b","c","d","e","f","g","h"]
rows = ["1","2","3","4","5","6","7","8"]
chessPos = {}

for c in cols:
    for r in rows:
        chessPos[c+r] = ((cols.index(c)*32) - 112,(rows.index(r)*32)+51.4)

chessPos["home"] = (0,0)
chessPos["cemetery"] = (176,179.4)

def IK(
        target: tuple,
        origin_l = origin_l, 
        origin_r = origin_r, 
        a = a, 
        b = b) -> tuple[float,float]:

    c_l = np.sqrt(((target[0]-origin_l[0])**2)+((target[1]-origin_l[1])**2))
    c_r = np.sqrt(((target[0]-origin_r[0])**2)+((target[1]-origin_r[1])**2))

    if c_l < abs(a - b) or c_l > a + b:
        raise ValueError(f"Target {target} out of reach for left arm")
    if c_r < abs(a - b) or c_r > a + b:
        raise ValueError(f"Target {target} out of reach for right arm")

    alpha_l = np.degrees(np.arccos((a**2 + c_l**2 - b**2)/(2*a*c_l)))
    alpha_r = np.degrees(np.arccos((a**2 + c_r**2 - b**2)/(2*a*c_r)))


    h = - origin_l[1] + target[1]



    beta_l = np.degrees(np.arccos(h/c_l))
    beta_r = np.degrees(np.arccos(h/c_r))

    pos_rel_l = target[0]-origin_l[0]
    pos_rel_r = target[0]-origin_r[0]

    if pos_rel_l > 0:
        ortogonal_angle_l = -(alpha_l - beta_l)
    else:
        ortogonal_angle_l = -(alpha_l + beta_l)


    if pos_rel_r > 0:
        ortogonal_angle_r = alpha_r + beta_r
    else:
        ortogonal_angle_r = alpha_r - beta_r




    return (ortogonal_angle_l,ortogonal_angle_r)

print(IK(target=chessPos["home"]))



