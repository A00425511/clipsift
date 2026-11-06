"""Layer 2 stubs. Nothing here works yet; each raises NotImplementedError with instructions.

2a: bigger local models. Implement a class with the same methods as the Layer 1 equivalent.
2b: cloud generative comparison. Never selectable unless cloud.enable_2b is true in config,
    and still a stub. Network use belongs ONLY here.
"""
from .base import Classifier, CountingModel, Detector, register


@register("detector", "layer2a_detector_stub")
class Layer2aDetectorStub(Detector):
    def __init__(self, cfg):
        raise NotImplementedError("Layer 2a detector is a stub. Implement detect(frame, t) with a larger "
                                  "local model in clipsift/stages/layer2.py, then select it in config.")


@register("classifier", "layer2a_classifier_stub")
class Layer2aClassifierStub(Classifier):
    def __init__(self, cfg):
        raise NotImplementedError("Layer 2a classifier is a stub. Implement classify(crop) -> "
                                  "list[SpeciesGuess] with a local species model.")


@register("classifier", "layer2b_cloud_compare_stub", requires_2b=True)
class Layer2bCloudCompareStub(Classifier):
    def __init__(self, cfg):
        raise NotImplementedError("Layer 2b (cloud generative comparison) is a stub and is off by default. "
                                  "It would send crops over the network, so it needs explicit approval "
                                  "from the data owner before anyone implements it.")


@register("counting_model", "point_density_stub")
class PointDensityStub(CountingModel):
    def __init__(self, cfg):
        raise NotImplementedError("Point or density counting is a stub. Implement count_points(frame, t) -> "
                                  "[[x, y, score], ...] (for example a density map model) and register it "
                                  "with @register('counting_model', '<name>'). Training labels can come from "
                                  "the app's point_labels.jsonl and tools/extract_annotations.py.")
