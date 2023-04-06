#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# getids: Look for Profile / Task IDs in Project  <pids> <tids> xml elements                 #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.outputl import my_output
from maptasker.src.sysconst import NO_PROFILE
import xml.etree.ElementTree  # Need for type hints


def get_ids(
    doing_project: bool,
    program_args: dict,
    colormap: dict,
    output_list: list,
    project: xml.etree,
    project_name: str,
    projects_without_profiles: list,
) -> list:
    """
    Find either Project 'pids' (Profile IDs) or 'tids' (Task IDs)
    :param doing_project: True if this is searching for Project IDs
    :param program_args: runtime arguments
    :param colormap: output colors to use
    :param output_list: list of all output lines to this point
    :param project: Project xml element
    :param project_name: name of Project
    :param projects_without_profiles: list of elements without ids
    :return:
    """
    # Get Profiles
    project_pids = ""
    if doing_project:
        project_pids = ""
        ids_to_find = 'pids'
        my_output(colormap, program_args, output_list, 1, "")  # Start Profile list
    else:
        ids_to_find = 'tids'
    try:
        # Get a list of the Profiles for this Project
        project_pids = project.find(ids_to_find).text
    except Exception:  # Project has no Profiles
        if project_name not in projects_without_profiles:
            projects_without_profiles.append(project_name)

    return project_pids.split(",") if project_pids != "" else []
