# Synthetic training references

The new neural experiment trains only on computer-rendered images. The network
starts from general ImageNet weights; no laboratory photograph supplies new
training pixels. Real recordings are used only for evaluation. The same boundary
applies to fitting the comparison model, choosing a saved network, and choosing
the detection threshold.

Published photographs and apparatus descriptions guide the renderer's geometry
and lighting. They are not cropped, traced, composited, or otherwise included in
the training images. The simulated appearance is an approximation, not a physical
optics calculation or a validated replica of any instrument.

| Reference | Relevant observations | Renderer choices |
| --- | --- | --- |
| [FINC, Miller et al. (2021), Fig. 1d](https://amt.copernicus.org/articles/14/3131/2021/) | The camera photograph shows dense PCR trays with nested well rims, bright liquid centers, dark frozen centers, and uneven lighting. | Vary rim width, liquid size, small central reflections, interwell boundaries, and illumination across the tray. |
| [DRINCZ, David et al. (2019), Fig. 1 and Sect. 2](https://amt.copernicus.org/articles/12/6865/2019/) | A camera observes transmitted light through a sealed PCR tray. Frozen wells transmit less light. The metal holder blocks light outside the wells. | Include bright centers on a dark holder, darker frozen contents, and reflections from a cover. |
| [BINARY, Budke and Koop (2015), Figs. 1–2](https://amt.copernicus.org/articles/8/689/2015/) | The paper describes a 6 × 6 array of circular compartments. Side lighting makes liquid droplets dark and frozen droplets bright; condensation can form around them. | Separate the droplet from its larger compartment, vary their radius ratio, and add directional reflections and diffuse halos. |
| [NC State cold stage, overview Fig. 1](https://cif-cold-stage.github.io/overview/) | Photographs show droplets in oil and on hydrophobic slides, including irregular arrangements, regular arrays, directional glints, and reflective backgrounds. | Include free droplets, variable spacing, offset highlights, weak rims, and smooth or textured backgrounds. |
| [µL-NIPI, Whale et al. (2015), Sect. 2](https://amt.copernicus.org/articles/8/2437/2015/) | The apparatus places pipetted droplets on a hydrophobic glass slide above a flat cold stage. | Include droplets without enclosing wells and independent slide edges and surface marks. |

FINC, DRINCZ, and NC State photographs were inspected visually. DRINCZ and BINARY also
provide explicit descriptions of the opposite brightness changes under different
lighting. Those descriptions motivate separate lighting modes; brightness alone
must not determine whether a simulated target contains liquid or ice.

## Labels and separation

- Assign filled, empty, and background labels before drawing. A frozen droplet is
  still a filled target. An empty well may have a visible bottom and reflections.
- Store the fluid-region center and radius separately from the holder boundary.
  Apply image geometry changes to the labels as well as the pixels.
- Include empty PCR wells, circular cutouts, scratches, reflections, and small
  background holes as examples that should not be selected.
- Keep different versions of one generated scene in the same data group. Use
  separate groups for fitting, choosing the network, and choosing the threshold.
- Keep the earlier synthetic benchmark separate. The existing real-image set has
  already been inspected during development, so it is an exploratory evaluation,
  not a previously unseen final test.

Varying rendering conditions is motivated by
[Tobin et al. (2017)](https://arxiv.org/abs/1703.06907). It does not establish that
synthetic training will improve this detector. Compare the updated network with
an unchanged network using the same synthetic-only comparison-model fitting and
threshold procedure, then report results on real images separately.
