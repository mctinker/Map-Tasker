#! /usr/bin/env python3

#                                                                                      #
# kidapp: Process Kid Application details                                              #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import pygixml  # Need for type hints

from maptasker.src.maputil2 import get_values_by_tag_prefix
from maptasker.src.primitem import PrimeItems


def get_kid_app(element: pygixml.XMLNode) -> str:
    """
    Get any associated Kid Application info and return it
        :param element: root element to search for <Kid>
        :return: the Kid App info
    """
    blank = "&nbsp;"
    kid_features = kid_plugins = ""
    four_spaces = "&nbsp;&nbsp;&nbsp;&nbsp;"
    if element is None:
        return ""
    kid_element = element.child("Kid")
    if kid_element is None or kid_element.xml == "":
        return ""

    kid_package = kid_element.child("pkg").text()
    kid_version = kid_element.child("vnme").text()
    kid_target = kid_element.child("vTarg").text()

    features = get_values_by_tag_prefix(kid_element, "feat")
    plugins = get_values_by_tag_prefix(kid_element, "mplug")
    for num, feature in enumerate(features):  # Get any special features
        kid_features = f" {kid_features}{num + 1}={feature}, "
    for num, plugin in enumerate(plugins):  # Get any special plugins
        kid_plugins = f" {kid_plugins}{num + 1}={plugin}, "
    if kid_features:
        kid_features = f"<br>{four_spaces}Features:{kid_features[: len(kid_features) - 2]}"
    if kid_plugins:
        kid_plugins = f"<br>{four_spaces}Plugins:{kid_plugins[: len(kid_plugins) - 2]}"

    kid_app_info = (
        f"<br>&nbsp;&nbsp;&nbsp;[Kid App Package:{kid_package}, Version"
        f" Name:{kid_version}, Target Android"
        f" Version:{kid_target} {kid_features} {kid_plugins}]"
    )

    if PrimeItems.program_arguments["pretty"]:
        number_of_blanks = kid_app_info.find("Package:") - 4
        kid_app_info = kid_app_info.replace(",", f"<br>{blank * number_of_blanks}")

    return kid_app_info
