import csv
import glob
import os

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
LABELS_CSV = os.path.join(DATASET_DIR, "labels_pieces.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "best_resnet18_pieces.pth")
OUT_DIR = os.path.join(BASE_DIR, "visualizations")

STAGE_NAMES = ["relu", "layer1", "layer2", "layer3", "layer4"]
STAGE_LABELS = {
    "relu": "Conv1 (112x112)",
    "layer1": "Layer1 (56x56)",
    "layer2": "Layer2 (28x28)",
    "layer3": "Layer3 (14x14)",
    "layer4": "Layer4 (7x7)",
}


def load_model(model_path: str, device: torch.device) -> tuple[nn.Module, list[str]]:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    classes: list[str] = ckpt["classes"]
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    return model, classes


def pick_sample_pieces(csv_path: str, dataset_dir: str, limit: int = 10) -> list[tuple[str, str]]:
    """Select up to `limit` cells with different piece classes from the dataset."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    preferred_order = [
        "white_king",
        "black_king",
        "white_queen",
        "black_queen",
        "white_knight",
        "black_knight",
        "white_rook",
        "black_rook",
        "white_bishop",
        "black_pawn",
    ]
    by_class: dict[str, str] = {}
    fallback: list[tuple[str, str]] = []

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel = row.get("rel_path", "").strip()
            lbl = row.get("label", "").strip()
            if not rel or not lbl or lbl == "empty":
                continue
            full_path = os.path.join(dataset_dir, rel)
            if not os.path.exists(full_path):
                continue
            if lbl not in by_class:
                by_class[lbl] = full_path
            fallback.append((full_path, lbl))

    selected: list[tuple[str, str]] = []
    used_paths: set[str] = set()
    for lbl in preferred_order:
        if lbl in by_class and len(selected) < limit:
            selected.append((by_class[lbl], lbl))
            used_paths.add(by_class[lbl])

    for full_path, lbl in fallback:
        if len(selected) >= limit:
            break
        if full_path not in used_paths:
            selected.append((full_path, lbl))
            used_paths.add(full_path)

    return selected


def to_heatmap_bgr(feature_2d: np.ndarray, size: int) -> np.ndarray:
    f_min, f_max = float(feature_2d.min()), float(feature_2d.max())
    if f_max - f_min > 1e-8:
        norm = (feature_2d - f_min) / (f_max - f_min)
    else:
        norm = np.zeros_like(feature_2d)
    u8 = (norm * 255.0).clip(0, 255).astype(np.uint8)
    resized = cv2.resize(u8, (size, size), interpolation=cv2.INTER_NEAREST if feature_2d.shape[0] <= 14 else cv2.INTER_LINEAR)
    return cv2.applyColorMap(resized, cv2.COLORMAP_INFERNO)


def compute_cam_overlay(
    orig_bgr: np.ndarray,
    layer4_feat: torch.Tensor,
    fc_weights: torch.Tensor,
    pred_idx: int,
    size: int,
) -> np.ndarray:
    """Compute the Class Activation Map (where the network looks) overlaid on the input."""
    weights = fc_weights[pred_idx].detach()
    cam = torch.einsum("c,chw->hw", weights, layer4_feat.squeeze(0))
    cam = torch.relu(cam).cpu().numpy()
    heatmap = to_heatmap_bgr(cam, size)
    base = cv2.resize(orig_bgr, (size, size), interpolation=cv2.INTER_LINEAR)
    return cv2.addWeighted(base, 0.50, heatmap, 0.50, 0)


def extract_activations(
    model: nn.Module,
    img_tensor: torch.Tensor,
) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
    activations: dict[str, torch.Tensor] = {}
    hooks = []

    def make_hook(name: str):
        def hook_fn(_module, _inp, out):
            activations[name] = out.detach()
        return hook_fn

    for name in STAGE_NAMES:
        hooks.append(getattr(model, name).register_forward_hook(make_hook(name)))

    with torch.no_grad():
        logits = model(img_tensor)

    for h in hooks:
        h.remove()
    return activations, logits


def build_detail_image(
    orig_bgr: np.ndarray,
    true_lbl: str,
    pred_lbl: str,
    conf: float,
    activations: dict[str, torch.Tensor],
    fc_weights: torch.Tensor,
    pred_idx: int,
) -> np.ndarray:
    """Build a detailed sheet for a single piece showing the top 4 most active channels per layer."""
    tile = 96
    pad = 10
    top_channels = 4
    cols = 1 + top_channels + 1
    row_h = tile + 32
    header_h = 150

    width = pad + cols * (tile + pad)
    height = header_h + len(STAGE_NAMES) * row_h + pad
    canvas = np.full((height, width, 3), 24, dtype=np.uint8)

    orig_tile = cv2.resize(orig_bgr, (110, 110), interpolation=cv2.INTER_LINEAR)
    cam_tile = compute_cam_overlay(orig_bgr, activations["layer4"], fc_weights, pred_idx, 110)
    canvas[25:135, pad:pad + 110] = orig_tile
    canvas[25:135, pad * 2 + 110:pad * 2 + 220] = cam_tile

    cv2.putText(canvas, "Input", (pad, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    cv2.putText(canvas, "Where it looks (CAM)", (pad * 2 + 110, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 220, 255), 1)

    info_x = pad * 3 + 225
    ok_color = (80, 255, 120) if pred_lbl == true_lbl else (80, 100, 255)
    cv2.putText(canvas, f"Actual: {true_lbl}", (info_x, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    cv2.putText(canvas, f"Pred  : {pred_lbl} ({conf * 100:.1f}%)", (info_x, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.65, ok_color, 2)
    cv2.putText(canvas, "Mean activation + Top 4 most active filters per layer", (info_x, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    for r_idx, stage in enumerate(STAGE_NAMES):
        y0 = header_h + r_idx * row_h
        feat = activations[stage].squeeze(0)
        mean_map = feat.mean(dim=0).cpu().numpy()

        cv2.putText(canvas, STAGE_LABELS[stage], (pad, y0 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 220, 120), 1)

        mean_bgr = to_heatmap_bgr(mean_map, tile)
        canvas[y0 + 24:y0 + 24 + tile, pad:pad + tile] = mean_bgr
        cv2.putText(canvas, "Mean", (pad + 26, y0 + 24 + tile + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        channel_scores = feat.mean(dim=(1, 2))
        top_idxs = torch.topk(channel_scores, k=min(top_channels, feat.shape[0])).indices.tolist()
        for c_pos, ch_idx in enumerate(top_idxs):
            x0 = pad + (c_pos + 1) * (tile + pad)
            ch_bgr = to_heatmap_bgr(feat[ch_idx].cpu().numpy(), tile)
            canvas[y0 + 24:y0 + 24 + tile, x0:x0 + tile] = ch_bgr
            cv2.putText(canvas, f"Ch #{ch_idx}", (x0 + 18, y0 + 24 + tile + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    return canvas


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for old_file in glob.glob(os.path.join(OUT_DIR, "detail_*.png")):
        os.remove(old_file)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Generating CNN visualizations on {device}...")

    model, classes = load_model(MODEL_PATH, device)
    fc_weights = model.fc.weight.data

    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    samples = pick_sample_pieces(LABELS_CSV, DATASET_DIR, limit=10)
    if not samples:
        print("No pieces found in labels_pieces.csv.")
        return

    tile = 120
    pad = 10
    label_col_w = 190
    n_cols = 1 + len(STAGE_NAMES) + 1
    header_h = 44
    row_h = tile + pad

    overview_w = label_col_w + n_cols * (tile + pad) + pad
    overview_h = header_h + len(samples) * row_h + pad
    overview = np.full((overview_h, overview_w, 3), 24, dtype=np.uint8)

    col_titles = ["Input", "Conv1 (112)", "Layer1 (56)", "Layer2 (28)", "Layer3 (14)", "Layer4 (7)", "Where it looks"]
    for c_idx, title in enumerate(col_titles):
        x0 = label_col_w + c_idx * (tile + pad)
        cv2.putText(overview, title, (x0 + 4, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 220, 120), 1)

    for row_idx, (img_path, true_lbl) in enumerate(samples):
        orig_bgr = cv2.imread(img_path)
        if orig_bgr is None:
            continue

        rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
        inp_tensor = tf(Image.fromarray(rgb)).unsqueeze(0).to(device)
        activations, logits = extract_activations(model, inp_tensor)

        probs = torch.softmax(logits, dim=1)[0]
        pred_idx = int(probs.argmax().item())
        pred_lbl = classes[pred_idx]
        conf = float(probs[pred_idx].item())

        y0 = header_h + row_idx * row_h
        ok_color = (80, 255, 120) if pred_lbl == true_lbl else (80, 100, 255)
        cv2.putText(overview, f"{row_idx + 1:02d}. {true_lbl}", (12, y0 + 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(overview, f"-> {pred_lbl}", (12, y0 + 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, ok_color, 1)
        cv2.putText(overview, f"({conf * 100:.1f}%)", (12, y0 + 96),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (190, 190, 190), 1)

        x0 = label_col_w
        overview[y0:y0 + tile, x0:x0 + tile] = cv2.resize(orig_bgr, (tile, tile), interpolation=cv2.INTER_LINEAR)

        for s_idx, stage in enumerate(STAGE_NAMES):
            xs = label_col_w + (s_idx + 1) * (tile + pad)
            mean_map = activations[stage].squeeze(0).mean(dim=0).cpu().numpy()
            overview[y0:y0 + tile, xs:xs + tile] = to_heatmap_bgr(mean_map, tile)

        xc = label_col_w + (len(STAGE_NAMES) + 1) * (tile + pad)
        overview[y0:y0 + tile, xc:xc + tile] = compute_cam_overlay(orig_bgr, activations["layer4"], fc_weights, pred_idx, tile)

        detail_img = build_detail_image(orig_bgr, true_lbl, pred_lbl, conf, activations, fc_weights, pred_idx)
        detail_path = os.path.join(OUT_DIR, f"detail_{row_idx + 1:02d}_{true_lbl}.png")
        cv2.imwrite(detail_path, detail_img)

    overview_path = os.path.join(OUT_DIR, "overview_10_pieces.png")
    cv2.imwrite(overview_path, overview)
    print(f"Done! Images saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
