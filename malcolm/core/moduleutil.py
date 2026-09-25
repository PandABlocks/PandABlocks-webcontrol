from typing import Any, Union


def submodule_all(
    globals_d, only_classes: Union[dict[str, Any], bool] = True
) -> list[str]:
    # Return all the classes
    return sorted(
        k for k, v in globals_d.items() if not only_classes or isinstance(v, type)
    )
