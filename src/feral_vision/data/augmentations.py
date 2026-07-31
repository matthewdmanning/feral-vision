import difflib
from pathlib import Path
from typing import Any, NoReturn

import albumentations as A
import hydra
import numpy as np
from omegaconf import DictConfig

from feral_vision.config.store import register_configs
from feral_vision.utils import get_logger, to_dtype

log = get_logger(__name__)

register_configs()

# Static registry of every instantiable Albumentations transform.
# Enumerated from the archived release; update only if the library is replaced.
_TRANSFORMS: dict[str, type[A.BasicTransform]] = {
    "AdditiveNoise": A.AdditiveNoise,
    "AdvancedBlur": A.AdvancedBlur,
    "Affine": A.Affine,
    "AtLeastOneBBoxRandomCrop": A.AtLeastOneBBoxRandomCrop,
    "AutoContrast": A.AutoContrast,
    "BBoxSafeRandomCrop": A.BBoxSafeRandomCrop,
    "Blur": A.Blur,
    "CLAHE": A.CLAHE,
    "CenterCrop": A.CenterCrop,
    "CenterCrop3D": A.CenterCrop3D,
    "ChannelDropout": A.ChannelDropout,
    "ChannelShuffle": A.ChannelShuffle,
    "ChromaticAberration": A.ChromaticAberration,
    "CoarseDropout": A.CoarseDropout,
    "CoarseDropout3D": A.CoarseDropout3D,
    "ColorJitter": A.ColorJitter,
    "ConstrainedCoarseDropout": A.ConstrainedCoarseDropout,
    "Crop": A.Crop,
    "CropAndPad": A.CropAndPad,
    "CropNonEmptyMaskIfExists": A.CropNonEmptyMaskIfExists,
    "CubicSymmetry": A.CubicSymmetry,
    "D4": A.D4,
    "Defocus": A.Defocus,
    "Downscale": A.Downscale,
    "ElasticTransform": A.ElasticTransform,
    "Emboss": A.Emboss,
    "Equalize": A.Equalize,
    "Erasing": A.Erasing,
    "FDA": A.FDA,
    "FancyPCA": A.FancyPCA,
    "FrequencyMasking": A.FrequencyMasking,
    "FromFloat": A.FromFloat,
    "GaussNoise": A.GaussNoise,
    "GaussianBlur": A.GaussianBlur,
    "GlassBlur": A.GlassBlur,
    "GridDistortion": A.GridDistortion,
    "GridDropout": A.GridDropout,
    "GridElasticDeform": A.GridElasticDeform,
    "HEStain": A.HEStain,
    "HistogramMatching": A.HistogramMatching,
    "HorizontalFlip": A.HorizontalFlip,
    "HueSaturationValue": A.HueSaturationValue,
    "ISONoise": A.ISONoise,
    "Illumination": A.Illumination,
    "ImageCompression": A.ImageCompression,
    "InvertImg": A.InvertImg,
    "Lambda": A.Lambda,
    "LongestMaxSize": A.LongestMaxSize,
    "MaskDropout": A.MaskDropout,
    "MedianBlur": A.MedianBlur,
    "Morphological": A.Morphological,
    "Mosaic": A.Mosaic,
    "MotionBlur": A.MotionBlur,
    "MultiplicativeNoise": A.MultiplicativeNoise,
    "NoOp": A.NoOp,
    "Normalize": A.Normalize,
    "OpticalDistortion": A.OpticalDistortion,
    "OverlayElements": A.OverlayElements,
    "Pad": A.Pad,
    "Pad3D": A.Pad3D,
    "PadIfNeeded": A.PadIfNeeded,
    "PadIfNeeded3D": A.PadIfNeeded3D,
    "Perspective": A.Perspective,
    "PiecewiseAffine": A.PiecewiseAffine,
    "PixelDistributionAdaptation": A.PixelDistributionAdaptation,
    "PixelDropout": A.PixelDropout,
    "PlanckianJitter": A.PlanckianJitter,
    "PlasmaBrightnessContrast": A.PlasmaBrightnessContrast,
    "PlasmaShadow": A.PlasmaShadow,
    "Posterize": A.Posterize,
    "RGBShift": A.RGBShift,
    "RandomBrightnessContrast": A.RandomBrightnessContrast,
    "RandomCrop": A.RandomCrop,
    "RandomCrop3D": A.RandomCrop3D,
    "RandomCropFromBorders": A.RandomCropFromBorders,
    "RandomCropNearBBox": A.RandomCropNearBBox,
    "RandomFog": A.RandomFog,
    "RandomGamma": A.RandomGamma,
    "RandomGravel": A.RandomGravel,
    "RandomGridShuffle": A.RandomGridShuffle,
    "RandomRain": A.RandomRain,
    "RandomResizedCrop": A.RandomResizedCrop,
    "RandomRotate90": A.RandomRotate90,
    "RandomScale": A.RandomScale,
    "RandomShadow": A.RandomShadow,
    "RandomSizedBBoxSafeCrop": A.RandomSizedBBoxSafeCrop,
    "RandomSizedCrop": A.RandomSizedCrop,
    "RandomSnow": A.RandomSnow,
    "RandomSunFlare": A.RandomSunFlare,
    "RandomToneCurve": A.RandomToneCurve,
    "Resize": A.Resize,
    "RingingOvershoot": A.RingingOvershoot,
    "Rotate": A.Rotate,
    "SafeRotate": A.SafeRotate,
    "SaltAndPepper": A.SaltAndPepper,
    "Sharpen": A.Sharpen,
    "ShiftScaleRotate": A.ShiftScaleRotate,
    "ShotNoise": A.ShotNoise,
    "SmallestMaxSize": A.SmallestMaxSize,
    "Solarize": A.Solarize,
    "Spatter": A.Spatter,
    "SquareSymmetry": A.SquareSymmetry,
    "Superpixels": A.Superpixels,
    "TextImage": A.TextImage,
    "ThinPlateSpline": A.ThinPlateSpline,
    "TimeMasking": A.TimeMasking,
    "TimeReverse": A.TimeReverse,
    "ToFloat": A.ToFloat,
    "ToGray": A.ToGray,
    "ToRGB": A.ToRGB,
    "ToSepia": A.ToSepia,
    "ToTensor3D": A.ToTensor3D,
    "ToTensorV2": A.ToTensorV2,
    "Transpose": A.Transpose,
    "UnsharpMask": A.UnsharpMask,
    "VerticalFlip": A.VerticalFlip,
    "XYMasking": A.XYMasking,
    "ZoomBlur": A.ZoomBlur,
}


def _suggest(name: str) -> list[str]:
    return difflib.get_close_matches(name, _TRANSFORMS.keys(), n=3, cutoff=0.6)


def compose_augmentations(cfg: DictConfig) -> A.Compose:
    """Build an Albumentations Compose pipeline from a Hydra AugmentationConfig.

    Parameters
    ----------
    cfg : DictConfig
        An ``AugmentationConfig``-shaped node with an ``ops`` list. Each entry
        must have a ``name`` key and any kwargs accepted by the corresponding
        Albumentations transform.

    Returns
    -------
    A.Compose
        Ready-to-call pipeline; invoke as ``pipeline(image=img)["image"]``.

    Raises
    ------
    ValueError
        If a transform name is not found in ``_TRANSFORMS``.
    """
    ops = list(cfg.ops) if cfg.ops else []
    transforms = [_instantiate_transform(op) for op in ops]
    return A.Compose(transforms)


def _instantiate_transform(op: Any) -> A.BasicTransform:
    name = op["name"] if hasattr(op, "__getitem__") else op.name
    kwargs = {k: v for k, v in op.items() if k != "name"}
    if name not in _TRANSFORMS:
        _unknown_transform(name)
    return _TRANSFORMS[name](**kwargs)


def _unknown_transform(name: str) -> NoReturn:
    suggestions = _suggest(name)
    msg = f"unknown transform {name!r}"
    if suggestions:
        msg += f"; did you mean: {', '.join(suggestions)}?"
    raise ValueError(msg)


def run_augment_stage(cfg: DictConfig) -> None:
    """Apply the configured augmentation pipeline across data/raw -> data/augmented.

    Parameters
    ----------
    cfg : DictConfig
        Top-level Hydra config; must contain ``cfg.augmentation`` and optionally
        ``cfg.data.root`` (defaults to ``"data"``).

    Notes
    -----
    Images are converted to uint8 via ``to_dtype`` before the Albumentations
    pipeline (its expected input format) and written back as uint8. The stage
    is a no-op when the raw directory is absent so DVC never fails in
    environments where data has not been fetched.
    """
    pipeline = compose_augmentations(cfg.augmentation)
    label = cfg.augmentation.name
    log.info("built augmentation pipeline: %s", label)

    root = Path(getattr(cfg.data, "root", "data")) if "data" in cfg else Path("data")
    raw_dir = root / "raw"
    out_dir = root / "augmented"

    if not raw_dir.exists():
        log.info("raw dir %s absent; nothing to augment", raw_dir)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    import cv2

    suffixes = {".png", ".jpg", ".jpeg", ".bmp"}
    for path in sorted(raw_dir.rglob("*")):
        if path.suffix.lower() not in suffixes:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            log.warning("could not read %s; skipping", path)
            continue
        image_u8 = to_dtype(image, np.uint8) if image.dtype != np.uint8 else image
        augmented = pipeline(image=image_u8)["image"]
        dest = out_dir / f"{path.stem}_{label}{path.suffix}"
        cv2.imwrite(str(dest), augmented)
        log.info("wrote %s", dest)


@hydra.main(version_base=None, config_path="../../../conf", config_name="runs/baseline")
def main(cfg: DictConfig) -> None:
    register_configs()
    run_augment_stage(cfg)


if __name__ == "__main__":
    main()
