#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# debug: special debug code for MapTasker                                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import sys
import maptasker.src.outputl as build_output

debug_style = '<span style="color:White;font-family:Courier">'


def debug1(colormap: dict, program_args: dict, output_list: list) -> None:
    """
    Output our runtime arguments
        :param colormap: colors to use
        :param program_args: other runtime arguments
        :param output_list: where the output goes
    """
    build_output.my_output(
        colormap,
        program_args,
        output_list,
        4,
        f'{debug_style}sys.argv:{str(sys.argv)}</span>',
    )
    build_output.my_output(
        colormap,
        program_args,
        output_list,
        4,
        '',
    )
    for key, value in program_args.items():
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            4,
            f"{debug_style}{key}: {value}</span>",
        )
    build_output.my_output(
        colormap,
        program_args,
        output_list,
        4,
        '',
    )
    for key, value in colormap.items():
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            4,
            f"{debug_style}colormap for {key} set to {value}</span>",
        )
    build_output.my_output(
        colormap,
        program_args,
        output_list,
        4,
        '',
    )
