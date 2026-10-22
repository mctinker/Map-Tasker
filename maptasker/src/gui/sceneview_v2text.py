"""sceneview_v2text: the text of a Version 2 component -- plain, HTML, or linkified.

The tooltip and badges that say what a component is bound to, and the three ways a Text's content is drawn."""

from __future__ import annotations

import html
import re

from nicegui import ui

from maptasker.src.core.maputil2 import tasker_icon_name, translate_string
from maptasker.src.core.sysconst import V2_MATERIAL_PALETTE
from maptasker.src.gui.sceneview import HTML_TAG
from maptasker.src.gui.sceneview_v2base import V2_ALIGNMENT, V2_DEFAULT_TEXT_SIZE, v2_colour, v2_swatch_colour
from maptasker.src.gui.sceneview_v2style import v2_binding_lines, v2_handler_lines, v2_modifier_drawn

# The components named by one of their own properties when they carry no treeLabel, and which
# property -- the same table sceneedit_v2tree.V2_LABEL_FALLBACK holds for the designer's tree,
# written out again rather than imported to keep the renderer from depending on the editor.
# The two change together.
_V2_NAMED_BY_PROPERTY = {"Text": "text", "Button": "text", "IconButton": "icon"}


def v2_bounds_label(node: dict) -> None:
    """The component's name, the way the designer's tree says it -- so a component picked out
    of the picture can be found in the tree, and the other way round.

    Which means the same order of preference sceneedit_v2tree.v2_node_name uses, own property
    included: the two are written out separately rather than shared, to keep the renderer from
    importing the editor, and they have to be changed together.
    """
    own_key = _V2_NAMED_BY_PROPERTY.get(str(node.get("type", "")), "")
    own = str(node.get(own_key, "") or "") if own_key else ""
    if own and v2_is_html(node):
        # Named by what it says rather than by its markup -- "Bold heading", not
        # "<b>Bold</b> heading".
        own = _v2_plain_text(own)
    if own and own_key == "icon":
        # "icon:Close" is called Close; a Symbol's ";weight:600;opsz:24" says how to draw it.
        own = tasker_icon_name(own)
    label = node.get("treeLabel") or own.strip() or node.get("id") or node.get("type", "?")
    ui.label(str(label)).style(
        "position: absolute; left: 0; top: 0; z-index: 5; pointer-events: none;"
        "font: 9px/1.2 monospace; color: rgba(37,99,235,0.95); background: rgba(255,255,255,0.75);"
        "padding: 0 2px; border-radius: 2px; max-width: 100%; overflow: hidden;"
        "text-overflow: ellipsis; white-space: nowrap;",
    )


def v2_condition_badge(node: dict) -> None:
    """What decides whether this component is on screen, and what happens when it is not:
    "Gone" takes its space back, "Invisible" leaves the space behind.  Two different layouts,
    so the mode is shown and not just the condition.
    """
    mode = str(node.get("showWhenMode", "") or "Gone")
    ui.label(f"?{node.get('showWhen', '')} · {mode}").style(
        "position: absolute; right: 0; top: 0; z-index: 5; pointer-events: none;"
        "font: 9px/1.2 monospace; color: #fff; background: rgba(217,119,6,0.92);"
        "padding: 0 3px; border-radius: 2px; max-width: 100%; overflow: hidden;"
        "text-overflow: ellipsis; white-space: nowrap;",
    )


def v2_event_badge(node: dict) -> None:
    """What this component does when it is used -- the V2 answer to the Legacy Task badge."""
    lines = v2_handler_lines(node) + v2_binding_lines(node)
    if not lines:
        return
    with ui.element("div").style(
        "position: absolute; left: 0; right: 0; bottom: 0; z-index: 4; pointer-events: none;"
        "display: flex; flex-wrap: wrap; gap: 2px; justify-content: flex-end;",
    ):
        for line in lines:
            ui.label(line).style(
                "font: 9px/1.3 monospace; color: #fff; background: rgba(37,99,235,0.9);"
                "padding: 0 3px; border-radius: 2px; max-width: 100%;"
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;",
            )


def v2_tooltip(container: ui.element, node: dict) -> None:
    """Everything about this component the drawing cannot carry: its id and type, its
    modifiers in the order they apply, the %variables it depends on, what it does, and where
    it writes to.

    The modifier list is the part that earns its keep.  A modifier this renderer has no CSS
    for -- WindowDrag, or one from a newer Tasker -- is still named here, so "the preview does
    not draw it" never quietly becomes "the Scene does not have it".
    """
    lines = [f"{node.get('type', '?')} '{node.get('id', '')}'".strip()]
    tree_label = node.get("treeLabel")
    if tree_label:
        lines.append(f"{translate_string('Tree label')}: {tree_label}")

    modifiers = [
        str(modifier.get("type", "?"))
        + ("" if v2_modifier_drawn(str(modifier.get("type", ""))) else f" ({translate_string('not drawn')})")
        for modifier in node.get("modifiers") or []
        if isinstance(modifier, dict)
    ]
    if modifiers:
        lines.append(f"{translate_string('Modifiers')}: {' → '.join(modifiers)}")

    variables = sorted({value for value in node.values() if isinstance(value, str) and value.startswith("%")})
    if variables:
        lines.append(f"{translate_string('Variables')}: {', '.join(variables)}")
    if node.get("showWhen"):
        lines.append(f"{translate_string('Show when')}: {node['showWhen']} ({node.get('showWhenMode', 'Gone')})")
    lines.extend(v2_handler_lines(node))
    lines.extend(v2_binding_lines(node))

    with container:
        ui.tooltip("\n".join(lines)).style("white-space: pre-wrap")


def v2_text_style(node: dict, default_colour: str = "") -> str:
    """Size and colour for anything that shows text."""
    size = str(node.get("textSize", "")).strip()
    try:
        size_px = float(size) if size and not size.startswith("%") else V2_DEFAULT_TEXT_SIZE
    except ValueError:
        size_px = V2_DEFAULT_TEXT_SIZE
    colour = v2_colour(node.get("color"), fallback=default_colour or V2_MATERIAL_PALETTE["onSurface"])
    align = V2_ALIGNMENT.get(str(node.get("textAlign", "")), "")
    style = f"font-size: {size_px:g}px; line-height: 1.35;"
    style += f"color: {'rgba(100,116,139,0.95)' if colour.is_variable else colour.css};"
    if align:
        style += f"text-align: {'left' if align == 'flex-start' else 'right' if align == 'flex-end' else 'center'};"
    return style


def v2_text(value: object, style: str) -> None:
    """Draw a run of text, marked when it is a %variable rather than a literal -- the same
    convention the Legacy half uses, so the two previews read the same way.
    """
    text = str(value or "")
    if not text:
        return
    if text.startswith("%"):
        style += "font-style: italic; text-decoration: underline dotted; opacity: 0.85;"
    ui.label(text).style(f"{style} max-width: 100%; overflow: hidden; white-space: pre-wrap;")


# One <a>...</a> and what it reads as on screen.  Nothing else about the markup is parsed:
# this is here to find the *links*, because they are the run drawn in the component's own
# link colour, and everything else is text.
_V2_ANCHOR = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)


# A link nobody wrote a tag around.  Android linkifies these itself -- a bare https://..., a
# www. address or an email address in a text is tappable on the phone and drawn in the link
# colour -- so a preview that only coloured <a> runs would show a Scene whose one link is
# plainly a URL as having no links at all.
_V2_AUTOLINK = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|[\w.+-]+@[\w-]+\.[\w.-]+",
    re.IGNORECASE,
)


# Punctuation that ends the sentence rather than the URL: "see https://x.com." links up to
# the "m".  Matches how Android's own Linkify treats a trailing stop.
_V2_AUTOLINK_TRAILING = ".,;:!?)\"'"


# What Tasker's contentFormat has to say for the text to be markup rather than a sentence.
_V2_HTML_FORMAT = "html"


def v2_is_html(node: dict) -> bool:
    """Whether this component's text is to be read as markup: contentFormat says Html, and
    there is text to read it in.

    Deliberately NOT also "and there is a tag in it".  That extra test looks like the careful
    version and is the wrong one: an Html text whose only link is a bare URL has no tags at
    all, and gating on tags drew exactly that case -- the commonest one there is -- as a plain
    sentence with its link uncoloured.  Whether the text is markup is what contentFormat says;
    what is in it decides only what the drawing has to do.

    A text that is wholly a %variable is still excluded, as it is on the Legacy side (see
    is_inline_html): its markup, and any link in it, arrive on the phone and not here, so it
    keeps the plain label and its variable marking.
    """
    if str(node.get("contentFormat", "")).strip().lower() != _V2_HTML_FORMAT:
        return False
    text = str(node.get("text", "") or "").strip()
    return bool(text) and not text.startswith("%")


def _v2_link_colour(node: dict) -> str:
    """The CSS colour this component's tappable links are drawn in.

    linkColor is an ordinary HTML colour -- a name or a #hex -- which is one more form than
    v2_colour parses (that one knows Material role names, Tasker's #AARRGGBB and CSS's
    shorter hexes), so a name is checked for separately and handed to CSS as itself.

    A %variable can't be resolved from a backup file, so it draws in the same muted grey
    v2_text_style uses for a variable-driven text colour: the preview says "this is decided
    on the phone" rather than inventing a colour to show.  Nothing set at all means Material's
    primary, which is what an unstyled link lands on.
    """
    raw = str(node.get("linkColor", "") or "").strip()
    if raw.startswith("%"):
        return "rgba(100,116,139,0.95)"
    return v2_swatch_colour(raw) or V2_MATERIAL_PALETTE["primary"]


def v2_html_text(node: dict, style: str) -> None:
    """Draw an Html-format text: its links in the component's link colour, the rest as text.

    The markup is taken apart rather than rendered.  A V2 component draws in the page's own
    flow -- it has no geometry to give a frame a size (which is how the Legacy half can afford
    to render markup properly, in the sandboxed iframe at WEB_SANDBOX) -- and putting a
    stranger's markup loose in this page is the one thing that module is careful never to do.

    So what is drawn is the sentence with its tags taken off, the way the Legacy half draws an
    HTML text it isn't rendering, with the tappable runs kept apart and coloured.  That is the
    part of the markup this preview is actually being asked about: which words are tappable,
    and what colour they come out.  Each run goes in as *text* through ui.label, so nothing in
    the Scene can be markup here however it was written.

    Tappable means both kinds of link: the ones written as <a>, and the bare URLs and email
    addresses Android turns into links on its own (see _V2_AUTOLINK).
    """
    raw = str(node.get("text", "") or "")
    link_style = f"color: {_v2_link_colour(node)}; text-decoration: underline;"
    with ui.element("div").style(f"{style} max-width: 100%; overflow: hidden;"):
        position = 0
        for match in _V2_ANCHOR.finditer(raw):
            _v2_linkified_runs(raw[position : match.start()], link_style)
            _v2_run(_v2_plain_text(match.group(1)), link_style)
            position = match.end()
        _v2_linkified_runs(raw[position:], link_style)


def _v2_plain_text(fragment: str) -> str:
    """A run of markup as the words it shows: tags off, entities back (a &amp; is an "&" on
    the phone, not five characters).  What makes the drawn result a sentence rather than a
    listing of its source.
    """
    return html.unescape(HTML_TAG.sub("", fragment))


def _v2_linkified_runs(fragment: str, link_style: str) -> None:
    """Draw a stretch of text that is outside any <a>, giving the link colour to the URLs and
    email addresses in it that Android would make tappable by itself.

    Tags come off first, so a URL that is only there as an href -- inside a tag rather than in
    the words -- is not mistaken for one the reader can see.
    """
    text = _v2_plain_text(fragment)
    position = 0
    for match in _V2_AUTOLINK.finditer(text):
        link = match.group(0).rstrip(_V2_AUTOLINK_TRAILING)
        _v2_run(text[position : match.start()], "")
        _v2_run(link, link_style)
        position = match.start() + len(link)
    _v2_run(text[position:], "")


def _v2_run(text: str, style: str) -> None:
    """One run of an Html-format text, drawn inline so the runs read as one sentence rather
    than as a stack of lines.
    """
    if text:
        ui.label(text).style(f"display: inline; {style}")
