#! /usr/bin/env python3

#                                                                                      #
# kidapp: Process Kid Application details                                              #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.primitem import PrimeItems


def get_kid_app(element: defusedxml.ElementTree) -> str:
    """
    Get any associated Kid Application info and return it
        :param element: root element to search for <Kid>
        :return: the Kid App info
    """
    blank = "&nbsp;"
    kid_features = kid_plugins = ""
    four_spaces = "&nbsp;&nbsp;&nbsp;&nbsp;"
    kid_element = element.find("Kid")
    if kid_element is None:
        return ""

    kid_package = kid_element.find("pkg").text
    kid_version = kid_element.find("vnme").text
    kid_target = kid_element.find("vTarg").text
    num_feature = num_plugin = 0

    for item in kid_element:  # Get any special features
        if "feat" in item.tag:
            kid_features = f" {kid_features}{num_feature+1}={item.text}, "
            num_feature += 1
        elif "mplug" in item.tag:
            kid_plugins = f" {kid_plugins}{num_plugin+1}={item.text}, "
            num_plugin += 1
    if kid_features:
        kid_features = f"<br>{four_spaces}Features:{kid_features[:len(kid_features)-2]}"
    if kid_plugins:
        kid_plugins = f"<br>{four_spaces}Plugins:{kid_plugins[:len(kid_plugins)-2]}"

    kid_app_info = (
        f"<br>&nbsp;&nbsp;&nbsp;[Kid App Package:{kid_package}, Version"
        f" Name:{kid_version}, Target Android"
        f" Version:{kid_target} {kid_features} {kid_plugins}]"
    )

    if PrimeItems.program_arguments["pretty"]:
        number_of_blanks = kid_app_info.find("Package:") - 4
        kid_app_info = kid_app_info.replace(",", f"<br>{blank*number_of_blanks}")

    return kid_app_info
