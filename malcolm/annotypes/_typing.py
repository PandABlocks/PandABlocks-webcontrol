import sys
from abc import ABCMeta as GenericMeta
from collections.abc import Mapping, Sequence
from collections.abc import Mapping as MappingOrigin
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
    overload,
)

NEW_TYPING = True
