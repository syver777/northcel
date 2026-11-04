#!/usr/bin/env python3
"""Compare native PNGs against the Python reference renderer and teachers.

Usage: compare_oracle.py --native DIR --reference DIR --out results.json [--teacher DIR]
Each directory contains fNNNN.png files. Reports grayscale MAE, RGB MAE, the
16x16-block SSIM used by the NorthCel reports, and windowed SSIM when
scikit-image is available.
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image


def block_ssim(a, b, block=16):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    h, w = a.shape
    scores = []
    c1, c2 = 6.5025, 58.5225
    for y in range(0, h - block + 1, block):
        for x in range(0, w - block + 1, block):
            pa = a[y:y + block, x:x + block]
            pb = b[y:y + block, x:x + block]
            ma, mb = pa.mean(), pb.mean()
            va, vb = pa.var(), pb.var()
            cov = ((pa - ma) * (pb - mb)).mean()
            scores.append(((2 * ma * mb + c1) * (2 * cov + c2)) /
                          ((ma * ma + mb * mb + c1) * (va + vb + c2)))
    return float(np.mean(scores))


def gray(img):
    return 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--teacher", default=None)
    args = ap.parse_args()
    try:
        from skimage.metrics import structural_similarity as sk_ssim
    except Exception:
        sk_ssim = None
    rows = []
    for path in sorted(glob.glob(os.path.join(args.native, "*.png"))):
        name = os.path.basename(path)
        ref = os.path.join(args.reference, name)
        if not os.path.exists(ref):
            continue
        a = np.asarray(Image.open(path).convert("RGB")).astype(np.int64)
        b = np.asarray(Image.open(ref).convert("RGB")).astype(np.int64)
        ga, gb = gray(a), gray(b)
        row = {
            "frame": name,
            "gray_mae": float(np.abs(ga - gb).mean()),
            "rgb_mae": float(np.abs(a - b).mean()),
            "max_abs": int(np.abs(a - b).max()),
            "diff_pixels": int((np.abs(a - b).max(axis=2) > 0).sum()),
            "block_ssim": block_ssim(ga, gb),
        }
        if sk_ssim is not None:
            row["window_ssim"] = float(sk_ssim(ga, gb, data_range=255))
        if args.teacher:
            tname = name
            if tname.startswith("tv7_"):
                tname = tname[4:]
            t = os.path.join(args.teacher, tname)
            if not os.path.exists(t):
                t = os.path.join(args.teacher, tname.replace(".png", ".jpg"))
            if os.path.exists(t):
                ta = np.asarray(Image.open(t).convert("RGB")).astype(np.int64)
                tg = gray(ta)
                row["teacher_block_ssim"] = block_ssim(tg, ga)
                row["teacher_gray_mae"] = float(np.abs(tg - ga).mean())
                row["reference_teacher_block_ssim"] = block_ssim(tg, gb)
        rows.append(row)
    json.dump({"frames": rows}, open(args.out, "w"), indent=2)
    for r in rows:
        extra = ""
        if "teacher_block_ssim" in r:
            extra = f' teacherSSIM {r["teacher_block_ssim"]:.6f} teacherMAE {r["teacher_gray_mae"]:.4f} refTeacherSSIM {r["reference_teacher_block_ssim"]:.6f}'
        print(f'{r["frame"]} grayMAE {r["gray_mae"]:.9f} rgbMAE {r["rgb_mae"]:.9f} max {r["max_abs"]} '
              f'blockSSIM {r["block_ssim"]:.9f} diffpx {r["diff_pixels"]}{extra}')


if __name__ == "__main__":
    main()
