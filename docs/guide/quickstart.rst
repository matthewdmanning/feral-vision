Quickstart
==========

Install
-------

.. code-block:: bash

   pip install feral-segmentor

Run inference
-------------

.. code-block:: python

   from feral_segmentor.inference.predictor import Predictor

   predictor = Predictor.from_pretrained("feral-segmentor")
   results = predictor.predict("image.jpg")
