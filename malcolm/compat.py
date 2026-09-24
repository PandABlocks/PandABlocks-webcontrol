from xml.etree import cElementTree as ET

try:
    # ruamel exists, use this OrderedDict as it is faster
    from ruamel.ordereddict import ordereddict as OrderedDict
except ImportError:
    # Fallback to slower collections one
    from collections import OrderedDict  # noqa


def et_to_string(element: ET.Element) -> str:
    xml = '<?xml version="1.0" ?>'
    try:
        xml += ET.tostring(element, encoding="unicode")
    except LookupError:
        xml += ET.tostring(element).decode()
    return xml
