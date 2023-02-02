# ########################################################################################## #
#                                                                                            #
# actarg: process Task "Action" arguments                                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
# ########################################################################################## #
from routines.actiond import process_condition_list
from routines.sysconst import logger
import routines.action as get_action


# ####################################################################################################
# Go through the arguments and parse each one based on its argument 'type'
# ####################################################################################################
def action_args(
    arg_list,
    dict_code,
    lookup_code_entry,
    evaluate_list,
    code_action,
    action_type,
    colormap,
    program_args,
    evaluated_results,
):
    for num, arg in enumerate(arg_list):
        # Find the location for this arg in dictionary key "types' since they can be non-sequential (e.g. '1', '3', '4', '6')
        index = num if arg == "if" else lookup_code_entry[dict_code]["args"].index(arg)
        # Get the arg name and type
        argeval = evaluate_list[num]
        argtype = lookup_code_entry[dict_code]["types"][index]
        evaluated_results["position_arg_type"].append(argtype)
        match argtype:
            case "Str":
                evaluated_results["get_xml_flag"] = True
                evaluated_results["strargs"].append(f"arg{str(arg)}")
                evaluated_results["streval"].append(argeval)
                evaluated_results["returning_something"] = True
            case "Int":
                evaluated_results["get_xml_flag"] = True
                evaluated_results["intargs"].append(f"arg{str(arg)}")
                evaluated_results["inteval"].append(argeval)
                evaluated_results["returning_something"] = True
            case "App":
                evaluated_results["strargs"].append(f"arg{str(arg)}")
                evaluated_results["streval"].append(argeval)
                app_class, app_pkg, app, extra = get_action.get_app_details(
                    code_action, action_type, colormap, program_args
                )
                evaluated_results["result_app"].append(f"{app_class}, {app_pkg}, {app}")
                evaluated_results["returning_something"] = True
            case "ConditionList":
                evaluated_results["strargs"].append(f"arg{str(arg)}")
                evaluated_results["streval"].append(argeval)
                final_conditions = ""
                condition_list, boolean_list = process_condition_list(code_action)
                # Go through all conditions
                for numx, condition in enumerate(condition_list):
                    final_conditions = (
                        f"{final_conditions} {condition[0]}{condition[1]}{condition[2]}"
                    )
                    if boolean_list and len(boolean_list) > numx:
                        final_conditions = f"{final_conditions} {boolean_list[numx]} "
                evaluated_results["result_con"].append(final_conditions)
                evaluated_results["returning_something"] = True
            case "Img":
                image, package = "", ""
                child = code_action.find("Img")
                if child.find("nme") is not None:
                    image = child.find("nme").text
                if child.find("pkg") is not None:
                    package = ", Package:" + child.find("pkg").text
                elif child.find("var") is not None:  # There is a variable name?
                    image = child.find("var").text
                if image:
                    evaluated_results["result_img"].append(argeval + image + package)
                    evaluated_results["returning_something"] = True
                else:
                    evaluated_results["result_img"].append(" ")
            case "Bundle":  # It's a plugin
                child1 = code_action.find("Bundle")
                child2 = child1.find("Vals")
                child3 = child2.find(
                    "com.twofortyfouram.locale.intent.extra.BLURB"
                )  # 2:40 am...funny!
                if child3 is not None and child3.text is not None:
                    # Get rid of extraneous html in Action's label
                    clean_string = child3.text.replace("</font><br><br>", "<br><br>")
                    clean_string = clean_string.replace("&lt;", "<")
                    clean_string = clean_string.replace("&gt;", ">")
                    evaluated_results["result_bun"].append(clean_string)
                    evaluated_results["returning_something"] = True
            case _:
                logger.debug(
                    "get_action_results:" + " unknown argtype:" + argtype + "!!!!!"
                )

    return evaluated_results
