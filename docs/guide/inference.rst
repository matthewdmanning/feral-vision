Inference
=========

.. code-block:: python

   from feral_segmentor.inference.predictor import Predictor
   from feral_segmentor.inference.postprocess import PostProcessor

   predictor = Predictor.from_pretrained("feral-segmentor")
   raw = predictor.predict("image.jpg")
   results = PostProcessor().run(raw)
