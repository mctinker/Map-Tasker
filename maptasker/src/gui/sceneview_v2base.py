"""sceneview_v2base: what the Version 2 preview needs before it draws anything.

The device screens a layout can be previewed in, the arrangement and alignment words as flexbox's, and the
resolution of colours and icons (Material roles, symbols, app icons) to something a browser can show."""

from __future__ import annotations

import re

from maptasker.src.core.maputil2 import is_html_colour, tasker_icon_name
from maptasker.src.core.sysconst import V2_MATERIAL_PALETTE
from maptasker.src.gui.sceneview import Colour, tasker_colour

# ======================================================================================
# VERSION 2
#
# A V2 layout is a tree of components that lay themselves out -- there are no coordinates to
# honour, so this half is a translation of Compose's layout model onto CSS flexbox rather
# than the placement exercise the Legacy half is.  The translation is close to exact for the
# things Scenes actually use: a Column is a flex column, its horizontalAlignment is
# align-items, its verticalArrangement is justify-content, and SpaceBetween/SpaceAround/
# SpaceEvenly are the CSS keywords of the same names.
#
# Sizes are in dp and drawn 1dp = 1px inside a frame of the chosen device size, then scaled
# to fit by the same transform the Legacy canvas uses.  There is no density control here and
# should not be: dp is already the density-independent unit, so 1:1 is the honest mapping and
# the only open question is how big a screen the layout is being laid out in -- which is what
# the frame size is for.
# ======================================================================================

# The screens the preview offers to lay a layout out in, in dp.  A V2 Scene has no size of
# its own, so this is the one thing the user has to be able to change to judge a layout:
# the same tree wraps differently at 360dp and at 800dp, and that difference is the whole
# reason FlowRow and showWhen (%sv2_render_width) exist.
V2_SCREENS: tuple[tuple[str, int, int], ...] = (
    ("Phone", 412, 892),
    ("Small phone", 360, 780),
    ("Large phone", 448, 998),
    ("Tablet", 800, 1280),
)


V2_DEFAULT_SCREEN = V2_SCREENS[0][0]


# V2_MATERIAL_PALETTE (Material 3's baseline scheme) lives in sysconst: sceneedit checks
# colour names against it too, and a core module cannot import this one.

# Compose's arrangements and alignments, in the spellings sceneedit's schema offers, mapped
# onto the flexbox keywords that mean the same thing.
V2_ARRANGEMENT: dict[str, str] = {
    "Start": "flex-start",
    "Center": "center",
    "End": "flex-end",
    "SpaceBetween": "space-between",
    "SpaceAround": "space-around",
    "SpaceEvenly": "space-evenly",
    "Top": "flex-start",
    "Bottom": "flex-end",
}


V2_ALIGNMENT: dict[str, str] = {
    "Start": "flex-start",
    "Center": "center",
    "End": "flex-end",
    "Top": "flex-start",
    "Bottom": "flex-end",
}


# A component's default text size in dp when it does not say.  Material's body default.
V2_DEFAULT_TEXT_SIZE = 16


# How deep to follow the tree.  Nothing in a real Scene comes close; this is a stop against a
# layout that somehow refers to itself, not a limit anyone should meet.
V2_MAX_DEPTH = 40


# Icons arrive as "icon:Close" / "icon:ArrowBack" -- Material's own icon names, which is what
# the browser's Material font is keyed by once they are snake_cased.  So these draw as the
# real icon rather than as a placeholder, unlike a Legacy <Img>.
_V2_ICON_PREFIX = "icon:"


_V2_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


# The second way a Scene names a glyph: Material Symbols, Google's newer set.  Quasar reaches
# it by prefixing the name -- sym_o_ for the Outlined face, which is the one Tasker's own
# picker shows -- and NiceGUI 3.15 ships all three Symbols faces with itself (see its
# static/fonts.css), so drawing one fetches nothing from the network.
#
# The names in this set are already snake_case, and the ";weight:600;opsz:24" tail on them
# says how to draw the glyph rather than which glyph it is (maputil2.tasker_icon_name).
_V2_SYMBOL_PREFIX = "symbol:"


_V2_QUASAR_SYMBOL_PREFIX = "sym_o_"


# The third way: an installed app's own icon, served by Tasker's icon provider on the device.
# "content://net.dinglisch.android.taskerm.iconprovider//app/com.android.vending" is a
# reference to something on the phone -- the icon belongs to the app, not to the backup -- so
# there is no glyph here to draw and the package name is what can honestly be shown for it.
_V2_APP_ICON_SCHEME = "content://"


_V2_APP_ICON_MARKER = "iconprovider"


def v2_colour(raw: object, fallback: str = "") -> Colour:
    """A V2 colour value: a Material role name, a plain hex colour, or a %variable.

    Not the same parse as the Legacy tasker_colour, and the difference is the point.  A V2
    layout writes ordinary #RRGGBB ("#64B5F6", "#f43356") and Material role names ("outline",
    "onSecondaryContainer"); a Legacy Scene writes #AARRGGBB with the alpha FIRST.  Handing a
    Legacy colour to this function would change both its hue and its transparency, so the two
    parsers are kept apart rather than merged into one clever one.

    THE EIGHT-DIGIT CASE IS AN INFERENCE, and is flagged as one because no V2 layout in any
    sample here carries a colour of that length -- there is no evidence to read.  It is
    treated as Tasker's own #AARRGGBB rather than as CSS's #RRGGBBAA, because AARRGGBB is the
    only colour convention this app has ever observed Tasker writing in a Scene of either
    kind, and the two orders are not a near miss: reading "#FF64B5F6" the CSS way turns a
    blue into a red.  If a real V2 Scene ever turns up carrying one, this is the line to check
    it against.
    """
    value = str(raw or "").strip()
    if not value:
        return Colour(fallback or "transparent", known=False)
    if value.startswith("%"):
        return Colour(fallback or "transparent", variable=value, known=False)
    if value in V2_MATERIAL_PALETTE:
        return Colour(V2_MATERIAL_PALETTE[value])
    if value.startswith("#") and len(value) == 9:
        return tasker_colour(value, fallback or "transparent")
    if value.startswith("#") and len(value) in (4, 7):
        return Colour(value)
    return Colour(fallback or "transparent", known=False)


def v2_swatch_colour(raw: object) -> str:
    """The CSS this V2 colour value actually draws as, for showing a swatch of it -- a
    Material role name resolved through the palette, a #hex as itself, an HTML colour name as
    itself.

    "" for anything that names no colour this app can resolve: an empty property, a
    %variable, a spelling from a newer Tasker.  The caller decides what to show for those --
    a blank swatch says "nothing to show you" where a made-up colour would be a claim.
    """
    value = str(raw or "").strip()
    if not value or value.startswith("%"):
        return ""
    colour = v2_colour(value, fallback="")
    if colour.known:
        return colour.css
    return value.lower() if is_html_colour(value) else ""


def v2_icon(raw: object) -> str:
    """The name Quasar draws this icon by: "icon:ArrowBack" -> "arrow_back",
    "symbol:cloud_upload;opsz:24" -> "sym_o_cloud_upload".

    Both sets are drawn from fonts NiceGUI ships, so neither goes to the network.  The two
    differ in how the name is spelled as well as which font it is in: Material Icons names are
    camel case in a Scene and snake case in the font, while Symbols names are snake case
    already -- which is why only the first is converted.

    "" for anything that is not a font glyph at all: an app icon from the device's own icon
    provider (see v2_app_icon), a URL, a %variable, an empty property.
    """
    value = str(raw or "").strip()
    if value.startswith(_V2_SYMBOL_PREFIX):
        name = tasker_icon_name(value)
        return f"{_V2_QUASAR_SYMBOL_PREFIX}{name}" if name else ""
    if value.startswith(_V2_ICON_PREFIX):
        name = tasker_icon_name(value)
        return _V2_CAMEL_BOUNDARY.sub("_", name).lower() if name else ""
    return ""


def v2_app_icon(raw: object) -> str:
    """The package whose own icon this reference names -- "com.android.vending" out of a
    "content://...iconprovider//app/com.android.vending".  "" for anything else.

    The icon itself is installed with the app on the phone and is not in the backup, so this
    is the most that can be said about it here.  The callers draw a stand-in glyph and name
    the package rather than leaving the component empty, which is what a preview that cannot
    show something owes the person reading it.
    """
    value = str(raw or "").strip()
    if not value.startswith(_V2_APP_ICON_SCHEME) or _V2_APP_ICON_MARKER not in value:
        return ""
    return tasker_icon_name(value)
