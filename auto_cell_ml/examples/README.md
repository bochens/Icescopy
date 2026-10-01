# Example images and labels

These files demonstrate training one general detector across five freezing setups. Each training folder contains **one image** and **`labels.icescopy`**, which opens that adjacent image using a relative path. Circle positions and sizes are preserved from Bo Chen's annotations. Shared sessions omit unrelated analysis results, file history, and private paths.

| Setup | Training circles | Independent evaluation image |
| --- | ---: | --- |
| CSU cold stage | 50 | Included |
| CSU IS PCR, filled and empty wells | 160 | Included |
| PKU | 90 | Not available |
| TAMU | 16 | Included |
| NC State/CIF | 105 | Included, Experiment 2 |

There are 421 labeled circles in total. `real/datasets.json` records relative paths, image hashes, and separate recording assignments. `real/evaluation/examples.json` supplies two guidance circles per evaluation image. Those are examples for detection, **not complete evaluation labels**. Do not treat unmarked evaluation objects as negatives or report accuracy from those images without labeling them.

## NC State/CIF source and citation

The NC State cold-stage images are from Markus Petters and Shweta Yadav's public example set. Please cite:

> Petters, M., & Yadav, S. (2023). *CIF-Cold-Stage/DropFreezingDetection.jl: v0.2.0*. Zenodo. https://doi.org/10.5281/zenodo.7765097

The [NC State instrument overview](https://cif-cold-stage.github.io/overview/) describes this setup. The two JPEG files are unmodified copies from the [v0.2.0 source release](https://github.com/CIF-Cold-Stage/DropFreezingDetection.jl/tree/v0.2.0):

- Training: [Experiment 1, `pic_0001_20220426T101339_10.25.jpg`](https://github.com/CIF-Cold-Stage/DropFreezingDetection.jl/blob/v0.2.0/exampledata/level%201/Experiment%201/pic_0001_20220426T101339_10.25.jpg), saved here as `real/train/05-CIF/image.jpg`.
- Evaluation: [Experiment 2, `pic_0001_20220504T145436_9.97.jpg`](https://github.com/CIF-Cold-Stage/DropFreezingDetection.jl/blob/v0.2.0/exampledata/level%201/Experiment%202/pic_0001_20220504T145436_9.97.jpg), saved here as `real/evaluation/05-CIF/image.jpg`.

The upstream repository is distributed under GNU GPL version 3; its license is retained in [licenses/NC-State-GPL-3.0.txt](licenses/NC-State-GPL-3.0.txt). These third-party images retain that license and attribution, independently of Icescopy's code license. The `.icescopy` circles are separate annotations by Bo Chen, not labels provided by Petters or Yadav. Image hashes and upstream Git object identifiers are recorded in the dataset manifest.

The CSU cold-stage, CSU IS, PKU, and TAMU images and their annotations are included with permission from the Icescopy maintainer. Their setup names identify the instruments represented; they do not imply institutional endorsement.

## Synthetic scenes

`synthetic/labels.json` accompanies 40 rendered PNGs: 20 fit scenes, 10 validation scenes, and 10 calibration scenes. The training loader uses only the fit partition. The other partitions remain available for additional checks; the notebook's independent evaluation uses real recordings.

Scenes include droplets, PCR trays, grids and recesses, empty wells, reflections, blur, and color or grayscale lighting. The JSON records droplet targets and negative objects. Any scientific references in its metadata describe rendering inspiration, not the source of the generated pixels.

Additional rotations, crops, reflections, uniform scaling, and lighting changes are applied by the training code. Labels receive the same geometric transform as their image. Synthetic scenes approximate appearances; they are not substitutes for independent real-image evaluation.
