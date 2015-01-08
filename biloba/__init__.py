from .service import *
from .service import __all__ as service_all
from .config import parse_address
from .util import waitany

from . import _meta


__version__ = _meta.version
__version_info__ = _meta.version_info


__all__ = [
    'parse_address',
    'waitany',
]

__all__.extend(service_all)

del service_all
