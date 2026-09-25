from typing import Union

from malcolm.annotypes import Anno, Array
from malcolm.core import Table

with Anno("The Malcolm Resource Identifier for the Block"):
    AMris = Union[Array[str]]
with Anno("A human readable label for the Block"):
    ALabels = Union[Array[str]]


class BlockTable(Table):
    def __init__(self, mri: AMris, label: ALabels) -> None:
        self.mri = mri
        self.label = label
