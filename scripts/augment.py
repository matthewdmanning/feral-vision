"""Augment images+masks from a source directory and write to an output directory."""

import argparse
from pathlib import Path

import cv2
import numpy as np

from feral_segmentor.data.augmentations import (
    BrightnessShift,
    GammaAdjust,
    HorizontalFlip,
    Identity,
    MotionBlur,
    RandomRotate90,
)

CHAINS = {
    "original": Identity(),
    "hflip": HorizontalFlip(),
    "rot90": RandomRotate90(),
    "brightness": BrightnessShift(shift=0.1),
    "gamma_dark": GammaAdjust(gamma=2.0),
    "gamma_bright": GammaAdjust(gamma=0.5),
    "hflip_brightness": BrightnessShift(inner=HorizontalFlip()),
    "hflip_gamma": GammaAdjust(gamma=2.0, inner=HorizontalFlip()),
    "motion_blur": MotionBlur(),
}


def run(
    src: Path,
    dst: Path,
    ops: list[str],
    brightness_shift: float,
    gamma: float,
    motion_blur_kernel: int = 15,
) -> None:
    out_images = dst / "images"
    # out_masks  = dst / "masks"
    out_images.mkdir(parents=True, exist_ok=True)
    # out_masks.mkdir(parents=True, exist_ok=True)

    chains = {
        "original": Identity(),
        "hflip": HorizontalFlip(),
        "rot90": RandomRotate90(),
        "brightness": BrightnessShift(shift=brightness_shift),
        "gamma_dark": GammaAdjust(gamma=gamma),
        "gamma_bright": GammaAdjust(gamma=1.0 / gamma),
        "hflip_brightness": BrightnessShift(
            shift=brightness_shift, inner=HorizontalFlip()
        ),
        "hflip_gamma": GammaAdjust(gamma=gamma, inner=HorizontalFlip()),
        "motion_blur": MotionBlur(kernel_size=motion_blur_kernel),
    }
    selected = {k: v for k, v in chains.items() if k in ops}

    # mask_by_stem = {p.stem: p for p in sorted((src / "masks").iterdir())}
    written = 0

    for img_path in sorted((src / "images").iterdir()):
        stem = img_path.stem
        # mask_path = mask_by_stem.get(stem)
        # if mask_path is None:
        #     print(f"WARNING: no mask for {stem}, skipping")
        #     continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        if bgr is None:
            print(img_path, flush=True)
            continue
        # mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        norm_img = bgr.astype(np.float64) / 255.0
        # norm_mask = mask.astype(np.float64)

        for tag, chain in selected.items():
            aug_img = chain.augment(norm_img)
            # aug_mask = chain.augment(norm_mask)

            cv2.imwrite(
                str(out_images / f"{stem}_{tag}.jpg"),
                np.clip(aug_img * 255.0, 0, 255).astype(np.uint8),
            )
            # cv2.imwrite(str(out_masks / f"{stem}_{tag}.png"),
            #            np.clip(aug_mask, 0, 1).astype(np.uint8))
            written += 1

    print(f"wrote {written} pairs → {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment image/mask pairs.")
    parser.add_argument(
        "--src", required=True, help="Source dir with images/ and masks/ subdirs"
    )
    parser.add_argument(
        "--dst", required=True, help="Output dir (images/ and masks/ created inside)"
    )
    parser.add_argument(
        "--ops",
        nargs="+",
        default=list(CHAINS.keys()),
        choices=list(CHAINS.keys()),
        help="Augmentation variants to apply",
    )
    parser.add_argument(
        "--brightness-shift",
        type=float,
        default=0.1,
        help="Additive brightness offset (default: 0.1)",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=2.0,
        help="Gamma exponent for gamma_dark; gamma_bright uses 1/gamma (default: 2.0)",
    )
    parser.add_argument(
        "--motion-blur-kernel",
        type=int,
        default=15,
        help="Motion blur kernel size, must be odd (default: 15)",
    )
    args = parser.parse_args()

    run(
        src=Path(args.src),
        dst=Path(args.dst),
        ops=args.ops,
        brightness_shift=args.brightness_shift,
        gamma=args.gamma,
        motion_blur_kernel=args.motion_blur_kernel,
    )


if __name__ == "__main__":
    main()
