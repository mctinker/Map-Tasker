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

from maptasker.src import actionc
from maptasker.src.actionr import get_action_results
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
