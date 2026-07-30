# Suggested Albumentations Augmentations

Simulates field conditions when applied to high-quality images.

## Low Light & Underexposure

To simulate dynamic range loss, high sensor noise, and poor illumination:

RandomBrightnessContrast(brightness_limit=(-0.3, -0.1), contrast_limit=(-0.3, -0.1), p=0.8)

Why: Hard-shifts the exposure downward and flattens dynamic range to recreate underexposed sensor output.

RandomGamma(gamma_limit=(50, 80), p=0.7)

Why: Gamma values below 100 heavily compress shadow detail and roll off midtones, mimicking low-light tone curves without simply multiplying pixel values linearly.

GaussNoise / ISONoise / ShotNoise

Why: Low-light images suffer from thermal and shot noise when ISO ramps up. ISONoise specifically models camera sensor noise gain patterns.

ColorJitter(brightness=0.2, contrast=0.2, saturation=(-0.5, -0.2), p=0.6)

Why: Low light naturally degrades color saturation, pushing images toward monochromatic palettes.

## Shadows & Partial Occlusion

To simulate canopy shadow, uneven illumination, and dark patches:

RandomShadow(num_shadows_lower=1, num_shadows_upper=3, shadow_dimension=5, p=0.6)

Why: Generates dark polygonal regions over the frame, forcing the model to rely on partial contours rather than global intensity signatures.

PlasmaShadow / CornerIllumination

Why: Creates irregular or organic vignetting/shadow falloff across corners and irregular vegetation edges.

CoarseDropout / Erasing

Why: Simulates heavy occlusion (e.g., foliage or total shadow blocking part of an animal).

## Distant Targets & Low Resolution

To simulate small object scales, spatial frequency loss, and optical distortion:

RandomResizedCrop / Resize + Downscale

Why: Downscale(scale_min=0.25, scale_max=0.5, p=0.5) degrades spatial resolution and introduces interpolation artifacts before upsampling, forcing the network to detect low-frequency feature maps.

GaussianBlur / MotionBlur / AdvancedBlur

Why: Distant objects lack fine detail due to atmospheric haze, slight focus misalignment, or sensor blur.

PadIfNeeded + RandomCrop

Why: Keeps the relative bounding box dimensions small compared to the total field of view, preventing your pipeline from accidentally over-indexing on upscaled targets.

## Possible Starting Point

~~~python
[
    # 1. Geometry & Scale (simulate distance)
    A.RandomResizedCrop(size=(512, 512), scale=(0.08, 0.4), p=0.7),
    A.Downscale(scale_min=0.25, scale_max=0.5, p=0.4),

    # 2. Lighting & Shadows
    A.RandomShadow(num_shadows_lower=1, num_shadows_upper=3, p=0.6),
    A.RandomGamma(gamma_limit=(50, 80), p=0.5),
    A.RandomBrightnessContrast(brightness_limit=(-0.35, -0.1), contrast_limit=(-0.3, 0), p=0.7),

    # 3. Low-Light Noise & Blur
    A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=0.5),
    A.GaussianBlur(blur_limit=(3, 7), p=0.4),
    A.ColorJitter(saturation=(-0.6, -0.2), p=0.5),
]
~~~
