"""Architecture registration manifest.

Importing this package triggers self-registration of all bundled architectures
and weight-source adapters so registries are populated before any call to
``build_model`` or ``load_model``.
"""

from feral_segmentor.models import default as default  # registers Net as "net"
from feral_segmentor.models import sources as sources  # registers all source adapters
