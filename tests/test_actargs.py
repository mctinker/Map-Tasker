"""MapTasker Action argument mapping (actargs) Unit Tests -- Icon arguments

An Icon argument is an <Img> element, and Tasker writes one in six shapes.  Only two of
them carry an <nme>, which is what the old reader keyed off: 'Set Tasker Icon' (138) names
an installed app's icon with a bare <pkg>, so it mapped as nothing at all -- the action
displayed with no argument whatsoever, which is not an error anybody sees in a log.  Each
shape is named here for that reason: the failure is a silently missing argument.

The label is asserted alongside the value because action_args hands extract_image the
argument's *name* ("Icon"), not its arg_eval ("Icon="), and gluing the two together
produced "Iconmw_navigation_apps" for every icon that did map.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest

from maptasker.src import actargs, actionc
from maptasker.src.actionr import get_action_results
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems

SET_TASKER_ICON = "138t"  # Icon(<Img>)=arg0
NOTIFY = "523t"  # Icon(<Img>)=arg2, with Str/Int arguments around it


def _map_icon(img_xml: str, code: str = "138", action_code: str = SET_TASKER_ICON) -> str:
    """The mapped line for one action carrying the given <Img>."""
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Action sr="act0" ve="7"><code>{code}</code>{img_xml}</Action>',
    )
    return get_action_results(action_code, actionc.action_codes, action, False)


@pytest.fixture(autouse=True)
def _specs() -> None:
    """The argument-type table proginit loads, which is what says arg_type '4' is an Icon."""
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"  # proginit appends these two; see its own note.
    specs[str(len(specs))] = "Img"
    for key, value in specs.items():
        if value == "String":
            specs[key] = "Str"
            break
    PrimeItems.tasker_arg_specs = specs
    PrimeItems.program_arguments = {"display_detail_level": 3, "pretty": False, "debug": False}
    PrimeItems.output_lines = LineOut()


def test_app_icon_maps() -> None:
    """A bare <pkg> is an installed app's own icon -- the shape 'Set Tasker Icon' writes."""
    result = _map_icon('<Img sr="arg0" ve="2"><pkg>android.autoinstalls.config.samsung</pkg></Img>')
    assert "Icon=Package:android.autoinstalls.config.samsung" in result


def test_app_icon_keeps_its_class() -> None:
    """The <cls> beside the package names the activity the icon is taken from."""
    result = _map_icon(
        '<Img sr="arg0" ve="2"><pkg>com.google.android.apps.docs</pkg>'
        "<cls>com.google.android.apps.docs.app.NewMainProxyActivity</cls></Img>",
    )
    assert "Icon=Package:com.google.android.apps.docs" in result
    assert "Class:com.google.android.apps.docs.app.NewMainProxyActivity" in result


def test_builtin_icon_maps() -> None:
    """<nme> alone is one of Tasker's own icons.  <tint> is not part of the reference."""
    result = _map_icon('<Img sr="arg0" ve="2"><nme>mw_navigation_apps</nme><tint>-1</tint></Img>')
    assert "Icon=mw_navigation_apps" in result
    assert "-1" not in result


def test_icon_pack_icon_maps() -> None:
    """<nme> plus <pkg> is a name inside an installed icon pack: both halves are needed."""
    result = _map_icon(
        '<Img sr="arg0" ve="2"><nme>spreadsheet</nme><pkg>net.dinglisch.android.ipack.crystalhd</pkg></Img>',
    )
    assert "Icon=spreadsheet, Package:net.dinglisch.android.ipack.crystalhd" in result


def test_variable_icon_wins_over_the_rest() -> None:
    """A <var> is resolved on the phone, whatever else was left in the element beside it."""
    result = _map_icon('<Img sr="arg0" ve="2"><var>%image_path</var><nme>stale_name</nme></Img>')
    assert "Icon=%image_path" in result
    assert "stale_name" not in result


def test_file_icon_maps() -> None:
    """<fle> names an image file on the device."""
    result = _map_icon('<Img sr="arg0" ve="2"><fle>/storage/emulated/0/Reminder_HD_Icon.png</fle></Img>')
    assert "Icon=/storage/emulated/0/Reminder_HD_Icon.png" in result


def test_symbol_icon_maps() -> None:
    """<sym> names a Material symbol."""
    result = _map_icon('<Img sr="arg0" ve="2"><sym>ac_unit</sym></Img>')
    assert "Icon=ac_unit" in result


def test_unset_icon_maps_to_nothing() -> None:
    """Tasker writes the empty element for an icon that was never set, and a missing one is
    the same thing: neither is an icon, and neither may invent a label.
    """
    for img_xml in ('<Img sr="arg0" ve="2"/>', ""):
        result = _map_icon(img_xml)
        assert "Icon" not in result.replace("Set Tasker Icon", "")


def test_icon_is_paired_with_its_own_argument() -> None:
    """Notify's icon is arg2, sitting among Str and Int arguments: the <Img> is matched by
    its sr= and lands in argument order, not first or last.
    """
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Action sr="act0" ve="7"><code>523</code>'
        '<Str sr="arg0" ve="3">Title here</Str><Str sr="arg1" ve="3">Text here</Str>'
        '<Img sr="arg2" ve="2"><nme>mw_navigation_apps</nme></Img>'
        '<Int sr="arg5" val="5"/></Action>',
    )
    result = get_action_results(NOTIFY, actionc.action_codes, action, False)
    assert "Text=Text here, Icon=mw_navigation_apps, Priority=5" in result


# An argument Tasker happens to name "Label" is an ordinary <Str sr="argn">, and has nothing
# to do with the action's own <label> element -- the free-text note the user types on any
# action, which the map already prints beside it.  Reading the element in the argument's
# place silently swallowed the argument: 'Goto' showed its Type and Number but no label at
# all, and it does that for every action naming an argument this way, not just Goto.
GOTO = "135t"  # Type=arg0, Number=arg1, Label=arg2
SET_WIDGET_LABEL = "155t"  # Name=arg0, Label=arg1


def test_goto_label_argument_maps() -> None:
    """Goto's label is arg2, and is displayed alongside its Type and Number."""
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Action sr="act12" ve="7"><code>135</code>'
        '<Int sr="arg0" val="1"/><Int sr="arg1" val="1"/>'
        '<Str sr="arg2" ve="3">Log Profile Names</Str></Action>',
    )
    result = get_action_results(GOTO, actionc.action_codes, action, False)
    assert "Label=Log Profile Names" in result


def test_label_argument_is_not_the_actions_own_label() -> None:
    """The action's <label> is its own note and never stands in for the argument."""
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Action sr="act12" ve="7"><code>135</code>'
        "<label>Jump back to the top</label>"
        '<Int sr="arg0" val="1"/><Int sr="arg1" val="1"/>'
        '<Str sr="arg2" ve="3">Log Profile Names</Str></Action>',
    )
    result = get_action_results(GOTO, actionc.action_codes, action, False)
    assert "Label=Log Profile Names" in result
    assert "Label=Jump back to the top" not in result


def test_set_widget_label_maps_its_label() -> None:
    """Goto is not alone: every action naming an argument "Label" lost it the same way."""
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Action sr="act2" ve="7"><code>155</code>'
        '<Str sr="arg0" ve="3">Allow Macro Toggle</Str>'
        '<Str sr="arg1" ve="3">Macros Off</Str></Action>',
    )
    result = get_action_results(SET_WIDGET_LABEL, actionc.action_codes, action, False)
    assert "Name=Allow Macro Toggle" in result
    assert "Label=Macros Off" in result


# ##################################################################################
# Plugin configuration -- the <Bundle> a plugin action carries
# ##################################################################################
#
# A plugin action stores its whole configuration in a <Bundle>, not in numbered <argN>
# elements like every other action, so none of the argument mapping above applies to it.
# What the user configured is a single blob written by the plugin itself, under one of
# two tag names depending on which plugin wrote it -- and an action whose bundle is not
# read displays as a bare plugin name with no settings at all, which reads as a plugin
# that was never configured.


def _bundle_result(inner: str, arg: str = "0") -> dict:
    """get_bundle's result for one action carrying the given bundle XML."""
    action = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Action sr="act0" ve="7"><code>1</code>{inner}</Action>',
    )
    return actargs.get_bundle(action, {"returning_something": True}, arg)


def test_a_plugin_blurb_is_read_as_its_configuration() -> None:
    """The BLURB tag is the Locale plugin convention -- the human-readable summary the
    plugin writes of whatever the user set up in it.
    """
    result = _bundle_result(
        "<Bundle><Vals><com.twofortyfouram.locale.intent.extra.BLURB>a=1\nb=2"
        "</com.twofortyfouram.locale.intent.extra.BLURB></Vals></Bundle>",
    )
    assert result["arg0"]["value"] == "Configuration Parameter(s):\na=1\nb=2\n"


def test_a_plugin_config_command_is_read_the_same_way() -> None:
    """Plugins that predate the BLURB convention write <Configcommand> instead.  Both
    reach the same line, and a reader has no way to tell which plugin used which.
    """
    result = _bundle_result("<Bundle><Vals><Configcommand>do thing</Configcommand></Vals></Bundle>")
    assert result["arg0"]["value"] == "Configuration Parameter(s):\ndo thing\n"


def test_plugin_output_variables_are_named_alongside_the_configuration() -> None:
    """<pref> is the variable the plugin writes its result into -- the half of the
    plugin's contract that the rest of the Task depends on.
    """
    result = _bundle_result("<Bundle><pref>%out</pref><Vals><Configcommand>x</Configcommand></Vals></Bundle>")
    assert "Output Variables=%out" in result["arg0"]["value"]


def test_an_action_with_no_bundle_returns_nothing_to_show() -> None:
    """Not every action reaching here is a plugin.  "returning_something" False is what
    tells the caller to leave the argument off the line entirely rather than print an
    empty "Configuration Parameter(s):" heading.
    """
    result = _bundle_result("")
    assert result["arg0"]["value"] == ""
    assert result["returning_something"] is False


def test_a_bundle_with_no_values_returns_nothing_to_show() -> None:
    """A plugin that was added but never configured writes the <Bundle> and nothing in it."""
    result = _bundle_result("<Bundle><pref>p</pref></Bundle>")
    assert result["arg0"]["value"] == ""
    assert result["returning_something"] is False


def test_an_unmapped_action_code_is_reported_rather_than_guessed() -> None:
    """Tasker adds actions faster than the code table here is updated.  An unmapped code
    has to say so in the output: silently showing the action with no arguments is
    indistinguishable from an action that genuinely takes none.
    """
    assert actargs.handle_missing_code("999t", 2) == ""
    assert "not mapped" in "".join(PrimeItems.output_lines.output_lines)
