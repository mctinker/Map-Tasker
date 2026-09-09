"""piiscan: find the secrets and personal details in a configuration, and redact them."""

#! /usr/bin/env python3

#                                                                                       #
# piiscan: read the loaded configuration for the things in it that are nobody else's    #
#          business -- API keys, tokens, passwords, phone numbers, email addresses     #
#          and home coordinates -- report them in the Health Check, and redact the very #
#          same things out of a standalone export.                                      #
#                                                                                       #
# Same contract as healthck.py, proflint.py, varxref.py and taskflow.py: the scan reads #
# PrimeItems and nothing else -- no GUI, no output_lines, no generated HTML.  It runs   #
# the moment an XML file is loaded (no Map run required) and is testable without        #
# standing up a GUI.                                                                    #
#                                                                                       #
# The dependency runs healthck -> piiscan, never the other way: healthck folds the      #
# findings below into its own report, as it folds in proflint's, taskflow's and         #
# varxref's.  That is why the severity words and the Problem record are spelled out     #
# again here rather than imported from healthck -- importing it back would be a cycle.  #
#                                                                                       #
# ONE detector, TWO callers.  That is the whole point of the module, and the reason the #
# scan and the redactor are not two files:                                              #
#                                                                                       #
#   lint_problems()  walks the configuration and says what it found and where, which is #
#                    what the Health Check prints.                                      #
#   redact_tree()    walks a rendered export and replaces what it found, which is what  #
#                    the "Redact" option on the four standalone exports does.           #
#                                                                                       #
# Both go through find_in_text() and the one _RULES table.  A rule added there is       #
# reported AND redacted; neither half can quietly know about a secret the other does    #
# not.  Anything else would be worse than useless: a report that promises a config is   #
# clean while the export still carries the key, or an export that strips something the  #
# report never warned about.                                                            #
#                                                                                       #
# What this cannot do, said plainly because a redacted file is trusted:                 #
#                                                                                       #
#   * A secret with no shape is invisible.  'hunter2' sitting in a Variable Set is a    #
#     password to the person who wrote it and an ordinary word to a regular expression. #
#     What is caught is what announces itself -- a key with a vendor's prefix, a value  #
#     written next to the word "password", a field Tasker itself calls Password.        #
#   * Names and the references that point at them are never redacted.  A Scene is       #
#     shown by name, a Task performed by name; rewriting either half of that would      #
#     produce a file that imports and then does nothing.  See _REFERENCE_TAGS.          #
#   * A plugin's configuration is an opaque blob only that plugin understands.  The     #
#     text inside it is scanned like any other text, but a key packed into a binary     #
#     bundle is not text and is not found.                                              #
#   * Bank card numbers are deliberately NOT looked for.  Sixteen digits with a valid   #
#     checksum is one in ten of every long number in a file, and a backup is full of    #
#     them -- Tasker stamps every Project, Profile and Task with a millisecond epoch    #
#     date.  A rule that flagged one Profile in ten as holding a credit card would      #
#     teach the user to ignore the whole report, which costs more than it finds.        #
#                                                                                       #
# So the report says "look here", and the redaction is a first pass rather than a       #
# guarantee.  Both say so in as many words -- see healthck._limitations and the note    #
# every redacted export carries at the top of it.                                       #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import (
    PROFILE,
    PROJECT,
    PROPERTIES_PART,
    SCENE,
    TASK,
    TASKERNET_PART,
    VARIABLE,
    Target,
    actions_in_map_order,
)
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Callable

    import defusedxml.ElementTree  # Need for type hints

# Two of healthck's three grading words, spelled out rather than imported (see the
# header).  ERROR is deliberately not among them, and the omission is the point: nothing
# here is broken.  A configuration full of API keys runs perfectly on the device -- it is
# only sharing it that costs anything -- so calling one an error, under a heading that
# reads "these will misbehave on the device", would be a lie about what was found.
#
# WARNING is for what would let somebody else act as you: a key, a token, a password.
# INFO is for what merely identifies you: an email address, a phone number, the
# coordinates of your house.  The split is about consequence, not about certainty.
WARNING = "WARNING"
INFO = "INFO"

# What every finding's detail line ends with.  Said once, here, so the thirty-odd rules
# below do not each re-word it slightly differently.
_ADVICE = "Redact it before sharing this configuration."


@dataclass(frozen=True)
class Rule:
    """One thing worth finding, and everything both callers need to know about it.

    Frozen, and shared by the scan and the redactor: 'tag' and 'what' are what the report
    prints, 'label' is what the export writes in its place, and 'pattern' is the single
    definition of the thing that neither caller may second-guess.

    A rule's pattern may declare a group called 'secret'.  Where it does, that group is
    what gets reported and replaced and the rest of the match is only context -- so
    'api_key=ABC123' redacts to 'api_key=[REDACTED:API-KEY]' rather than losing the name
    of the setting along with its value.  Where it does not, the whole match is the secret.

    'verify' is the second opinion a shape-only rule needs.  Two decimals separated by a
    comma are a coordinate pair or merely two numbers depending on whether they are in
    range, and ten digits are a phone number or a reference depending on what they are made
    of.  A rule with no verify is one whose shape is already conclusive.
    """

    tag: str
    label: str
    severity: str
    pattern: re.Pattern[str]
    what: str
    verify: Callable[[str], bool] | None = None

    @property
    def placeholder(self) -> str:
        """What a redacted export carries in place of the value."""
        return f"[REDACTED:{self.label}]"


@dataclass(frozen=True)
class Finding:
    """One thing found, and where in the string it was."""

    rule: Rule
    start: int
    end: int
    text: str


@dataclass
class Problem:
    """One finding, in the shape healthck folds into its report.

    Deliberately the same four fields proflint.Problem and taskflow.Problem carry, for
    their reason: all three modules exist to be read by healthck.add, and a finding that
    arrived in a different shape would need a fold of its own.

    'where' is a Target wherever there is an object to go and look at, and a plain string
    for the one place there is not -- a Tasker preference, which the Map does not draw.
    """

    severity: str
    tag: str
    where: Target | str
    detail: str


# ##################################################################################
# The rules.  One table, read by the scan and by the redactor alike.
# ##################################################################################
#
# Ordered roughly most-specific first, because overlapping matches are resolved by
# preferring the longer one and then the earlier rule (see find_in_text): a Google API key
# inside a URL should be reported as a Google API key rather than as whatever the generic
# 'key=' rule would have made of it.
#
# Every vendor pattern below is the prefix that vendor documents for its own credentials.
# That is what makes them worth having over the generic rules: a string beginning 'AIza'
# and 39 characters long is a Google API key and cannot readily be anything else, so it
# can be reported with no keyword next to it and no risk of crying wolf.


def _is_coordinate_pair(text: str) -> bool:
    """Whether 'a,b' is a latitude and a longitude rather than two numbers.

    Range-checked because the shape alone is not enough -- '12.3456,78.9012' is a
    coordinate and '99.5000,-200.1' is two numbers that happen to have decimals.  The
    four-decimal minimum in the pattern is the other half of it: a coordinate written to
    four places is precise to about eleven metres, which is a place; one written to two is
    precise to a kilometre, which is a number somebody rounded.
    """
    try:
        latitude, longitude = (float(part) for part in text.split(","))
    except ValueError:
        return False
    return abs(latitude) <= 90 and abs(longitude) <= 180 and (latitude or longitude)


def _is_phone(text: str) -> bool:
    """Whether a formatted number is plausibly a telephone number.

    Rejects the runs of one repeated digit, which are placeholders and test data rather
    than anybody's number ('000-000-0000', '+11111111111').
    """
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 15 and len(set(digits)) > 2


_RULES: tuple[Rule, ...] = (
    # ---- Credentials that name themselves -------------------------------------------
    Rule(
        "SECRET-PRIVATE-KEY",
        "PRIVATE-KEY",
        WARNING,
        re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----.*?-----END[A-Z ]*PRIVATE KEY-----", re.DOTALL),
        "A private key, in full.",
    ),
    Rule(
        "SECRET-API-KEY",
        "API-KEY",
        WARNING,
        re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
        "An AWS access key id.",
    ),
    Rule(
        "SECRET-API-KEY",
        "API-KEY",
        WARNING,
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "A Google API key.",
    ),
    Rule(
        "SECRET-TOKEN",
        "TOKEN",
        WARNING,
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}"),
        "A Slack token.",
    ),
    Rule(
        "SECRET-TOKEN",
        "TOKEN",
        WARNING,
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "A GitHub personal access token.",
    ),
    Rule(
        "SECRET-API-KEY",
        "API-KEY",
        WARNING,
        re.compile(r"\b[sr]k_(?:live|test)_[0-9A-Za-z]{16,}\b"),
        "A Stripe secret key.",
    ),
    Rule(
        "SECRET-API-KEY",
        "API-KEY",
        WARNING,
        re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b"),
        "An OpenAI or Anthropic API key.",
    ),
    # A Telegram bot's token, which is how most Tasker setups send themselves a message.
    # Distinctive enough to match on its own: a run of digits, a colon, and exactly 35
    # characters of the alphabet Telegram uses.
    Rule(
        "SECRET-TOKEN",
        "TOKEN",
        WARNING,
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b"),
        "A Telegram bot token.",
    ),
    Rule(
        "SECRET-TOKEN",
        "TOKEN",
        WARNING,
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "A signed web token (JWT), which usually carries an account with it.",
    ),
    Rule(
        "SECRET-TOKEN",
        "TOKEN",
        WARNING,
        re.compile(r"(?i)\bbearer\s+(?P<secret>[A-Za-z0-9._~+/-]{16,}=*)"),
        "An Authorization header carrying a bearer token.",
    ),
    Rule(
        "SECRET-PASSWORD",
        "PASSWORD",
        WARNING,
        re.compile(r"(?i)\bbasic\s+(?P<secret>[A-Za-z0-9+/]{16,}={0,2})"),
        "An Authorization header carrying a Basic-auth username and password.",
    ),
    Rule(
        "SECRET-PASSWORD",
        "PASSWORD",
        WARNING,
        re.compile(r"://(?P<secret>[^\s:/@]+:[^\s:/@]+)@"),
        "A user name and password written into a URL.",
    ),
    # ---- Credentials found by the word next to them ---------------------------------
    #
    # The generic pair.  Both need a keyword AND a separator AND a value of some length,
    # because the value alone has no shape at all -- that is what makes them generic.  The
    # keyword is left out of the replacement (see Rule.secret) so a redacted export still
    # reads as the setting it is; only the value goes.
    Rule(
        "SECRET-API-KEY",
        "API-KEY",
        WARNING,
        re.compile(
            r"(?i)\b(?:api[_. -]?key|access[_. -]?token|auth[_. -]?token|client[_. -]?secret"
            r"|secret[_. -]?key|app[_. -]?(?:key|secret))\b\s*[:=]\s*[\"']?(?P<secret>[A-Za-z0-9._~+/-]{12,}=*)",
        ),
        "A value written next to the word 'key', 'token' or 'secret'.",
    ),
    Rule(
        "SECRET-PASSWORD",
        "PASSWORD",
        WARNING,
        re.compile(r"(?i)\b(?:password|passwd|passphrase|pwd)\b\s*[:=]\s*[\"']?(?P<secret>[^\s\"'&,;]{4,})"),
        "A value written next to the word 'password'.",
    ),
    # ---- Personal details -----------------------------------------------------------
    Rule(
        "PII-EMAIL",
        "EMAIL",
        INFO,
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
        "An email address.",
    ),
    Rule(
        "PII-PHONE",
        "PHONE-NUMBER",
        INFO,
        re.compile(r"(?<![\w.])(?P<secret>\+[1-9]\d{7,14})(?![\w.])"),
        "A telephone number in international form.",
        verify=_is_phone,
    ),
    Rule(
        "PII-PHONE",
        "PHONE-NUMBER",
        INFO,
        re.compile(r"(?<![\w.])(?P<secret>\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4})(?![\w.])"),
        "A telephone number.",
        verify=_is_phone,
    ),
    Rule(
        "PII-LOCATION",
        "COORDINATES",
        INFO,
        re.compile(r"(?<![\w.])(?P<secret>-?\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,})(?![\w.])"),
        "A latitude and longitude, precise enough to be an address.",
        verify=_is_coordinate_pair,
    ),
)

# Every tag the rules above can raise, plus the two the structural passes raise on their
# own.  healthck reads this to decide whether to print its closing note about them -- the
# same way it reads proflint.TAGS.
TAGS: frozenset[str] = frozenset({rule.tag for rule in _RULES} | {"PII-LOCATION", "SECRET-CREDENTIAL"})

# A '%' followed by a letter is a Tasker variable reference, and a variable reference is
# the OPPOSITE of a leaked secret -- it is the fix.  Somebody who wrote
# 'Authorization: Bearer %Token' has already moved the key out of the action, and telling
# them they have leaked '%Token' would be telling them off for doing the right thing.
_VARIABLE_REFERENCE = re.compile(r"%[A-Za-z]")


def _looks_like_variable(text: str) -> bool:
    """Whether a matched span is really a Tasker variable rather than a value."""
    return bool(_VARIABLE_REFERENCE.search(text))


def find_in_text(value: str) -> list[Finding]:
    """Everything the rules find in one string, in the order it appears.

    THE detector.  Both halves of this feature come through here -- the Health Check to
    say what is in the file, the export to take it out -- so a string that scans clean here
    is one the redactor will leave alone, and vice versa.

    Overlaps are resolved rather than reported twice: the longest match wins, and an
    earlier rule beats a later one of the same length.  That ordering is why the vendor
    patterns are listed above the generic keyword ones -- 'api_key=AIza...' is a Google API
    key, and reporting it twice under two tags would double the count of a single problem.
    """
    if not value:
        return []

    found: list[Finding] = []
    for rule in _RULES:
        for match in rule.pattern.finditer(value):
            group = "secret" if "secret" in rule.pattern.groupindex else 0
            text = match.group(group)
            if not text or _looks_like_variable(text) or (rule.verify and not rule.verify(text)):
                continue
            found.append(Finding(rule, match.start(group), match.end(group), text))

    # Longest first at each position, then by the order the rules are declared in, so the
    # keep-or-drop below is deterministic for a given string.
    found.sort(key=lambda item: (item.start, -(item.end - item.start)))
    kept: list[Finding] = []
    for item in found:
        if not kept or item.start >= kept[-1].end:
            kept.append(item)
    return kept


def redact_in_text(value: str) -> tuple[str, list[Finding]]:
    """The string with every finding replaced by its placeholder, and what was replaced.

    Replaced right-to-left so that each replacement cannot move the offsets of the ones
    not yet made.
    """
    found = find_in_text(value)
    redacted = value
    for item in reversed(found):
        redacted = redacted[: item.start] + item.rule.placeholder + redacted[item.end :]
    return redacted, found


# ##################################################################################
# The things no regular expression finds: fields Tasker itself labels.
# ##################################################################################
#
# A password does not look like anything.  'hunter2' is a word, '1234' is a number, and
# no pattern above will ever call either one a secret -- which would leave the single most
# obvious credential in a configuration unreported and unredacted.
#
# What identifies it is not the value but the box it was typed into.  Tasker names its own
# fields, actionc.py records those names, and an action with a filled-in field called
# "Password" is carrying a password whatever the value looks like.  So these are found
# structurally, by field name, and the table is derived from actionc.py rather than listed
# by hand -- the same derivation healthck._scene_name_args() and varxref's write tables
# use, so a field added in a later Tasker release is covered when that file is regenerated.
_CREDENTIAL_FIELDS: dict[str, tuple[str, str, str, str]] = {
    # field name (lower case): (tag, placeholder label, severity, what the report says)
    "password": ("SECRET-CREDENTIAL", "PASSWORD", WARNING, "Tasker's own 'Password' field, filled in."),
    "client secret": ("SECRET-CREDENTIAL", "API-KEY", WARNING, "Tasker's own 'Client Secret' field, filled in."),
    "override api key": ("SECRET-CREDENTIAL", "API-KEY", WARNING, "Tasker's own API key field, filled in."),
    # Half of a login rather than the whole of one, and graded accordingly -- but it is
    # still the name somebody signs in with, and a shared configuration should not carry it.
    "username": ("SECRET-CREDENTIAL", "USERNAME", INFO, "Tasker's own 'Username' field, filled in."),
}

# The Tasker preference that holds the code protecting Tasker itself (servicec.py names it
# "Lock Code").  A preference is not an action and has no field table, so it is listed --
# there is exactly one of it, and a backup carries it whether or not the user ever set it.
_CREDENTIAL_PREFERENCES: dict[str, tuple[str, str, str, str]] = {
    "lcD": ("SECRET-CREDENTIAL", "PASSWORD", WARNING, "Tasker's own lock code, from the preferences in this backup."),
}

# What a Profile's location condition stores.  Read structurally rather than by pattern
# because the two halves live in separate elements -- neither '-3.1112782' nor
# '-60.0068054' is a coordinate on its own, and the pair rule above only ever sees one
# string at a time.  This is the finding most worth having: a location Profile is somebody's
# home or workplace written down to eleven metres.
_LOCATION_CONDITION = "Loc"
_LATITUDE = "lat"
_LONGITUDE = "long"

# One row of the same shape _CREDENTIAL_FIELDS holds, so the location finding is reported
# and redacted through the same two calls everything else is.
_LOCATION_FINDING = (
    "PII-LOCATION",
    "COORDINATES",
    INFO,
    "The latitude and longitude this Profile watches for, which is a real place.",
)

# What a redacted coordinate becomes.  Zero rather than a placeholder, because Tasker
# reads these as numbers and would refuse a file that had words in them -- the export has
# to remain importable, or redacting it has cost the user the thing they were sharing.
# Zero rather than a rounded-off version of the real place, because rounding still says
# which city; the null island is plainly not where anyone lives, which is the honest way
# for a redacted file to say "this was removed".
_REDACTED_COORDINATE = "0.0"

# Elements this feature never touches, in either direction.
#
# These are names, and the references that point at them.  A Scene is shown by name, a Task
# is performed by name, a Project lists what it owns by id -- rewrite either end of one of
# those pairs and the file still imports and then quietly does nothing, which is a far worse
# outcome than a name that mentions somebody's street.  Not scanned either, rather than
# reported and then left alone: a finding the redactor will not act on reads as a promise
# it cannot keep.  healthck's closing note says this out loud.
_REFERENCE_TAGS: frozenset[str] = frozenset({"nme", "name", "pids", "tids", "scenes", "mid0", "mid1", "id"})

# ...and the action arguments that are likewise a name rather than a value: Perform Task's
# Task, the four Scene lifecycle actions' Scene, and the two widget actions' widget.  Taken
# from the same codes healthck indexes references by; repeated here rather than imported,
# because importing healthck from this module would be the cycle the header rules out.
_NAME_ARGUMENTS: frozenset[tuple[str, str]] = frozenset(
    {("130", "arg0")}  # Perform Task
    | {(code, "arg0") for code in ("46", "47", "48", "49")}  # Create/Show/Hide/Destroy Scene
    | {(code, "arg0") for code in ("152", "155")},  # Set Widget Icon / Set Widget Label
)


def _action_code(action: defusedxml.ElementTree.Element) -> str:
    """An action's Tasker code, or "" if it has none."""
    code = action.find("code")
    return (code.text or "").strip() if code is not None else ""


def _action_entry(code: str) -> object | None:
    """actionc.py's record for a Task action code, following the plugin redirect.

    proflint._action_name's hop, kept because the argument names this module reads live on
    the entry a redirect points at, not on the entry that points.
    """
    entry = action_codes.get(f"{code}t")
    if entry is not None and entry.redirect:
        entry = action_codes.get(entry.redirect, entry)
    return entry


def _argument_names(code: str) -> dict[str, str]:
    """{"argN": the name Tasker gives that field} for one action code."""
    entry = _action_entry(code)
    if entry is None:
        return {}
    return {f"arg{argument.arg_id}": argument.arg_name for argument in entry.args if argument.arg_name}


def _credential_field(code: str, argument: str) -> tuple[str, str, str, str] | None:
    """The credential this action's argument is, or None if it is an ordinary field."""
    return _CREDENTIAL_FIELDS.get(_argument_names(code).get(argument, "").lower())


def _is_empty_or_variable(value: str) -> bool:
    """Whether a field holds nothing worth redacting.

    A field left blank is not a leak, and a field holding '%Password' is the user having
    already moved the secret out of the file -- see _looks_like_variable.
    """
    return not value.strip() or _looks_like_variable(value)


# ##################################################################################
# Walking the configuration: what is in it, and where.
# ##################################################################################
class _Collector:
    """The problems found so far, and the two ways of adding one.

    Findings are aggregated as they arrive, keyed by what was found and the place it was
    found in.  A Task that mails a report at the end of every action would otherwise
    contribute forty identical lines about the same address, and an action whose plugin
    bundle names three recipients would contribute three lines that read word for word the
    same.  Both collapse to one line with a count on it, which is what leaves the report
    skimmable -- the finding a user has not already read is the one worth seeing.
    """

    def __init__(self) -> None:
        # {(where, place, what was found): how many times}, insertion-ordered so the
        # aggregation cannot reshuffle findings that lint_problems then sorts anyway.
        self._counts: dict[tuple[Target | str, str, tuple[str, str, str]], int] = {}

    def _add(self, where: Target | str, place: str, tag: str, severity: str, what: str, count: int = 1) -> None:
        """Add to the tally for one thing found in one place."""
        key = (where, place, (tag, severity, what))
        self._counts[key] = self._counts.get(key, 0) + count

    def note(self, where: Target | str, place: str, credential: tuple[str, str, str, str]) -> None:
        """Record something found structurally rather than by pattern.

        'credential' is a whole row of _CREDENTIAL_FIELDS, passed as one so the scan and the
        redactor read the same table the same way -- the placeholder in it is the
        redactor's half and is not printed here.
        """
        tag, _label, severity, what = credential
        self._add(where, place, tag, severity, what)

    def text(self, where: Target | str, place: str, value: str) -> None:
        """Record everything the rules find in one string."""
        for finding in find_in_text(value):
            rule = finding.rule
            self._add(where, place, rule.tag, rule.severity, rule.what)

    def problems(self) -> list[Problem]:
        """The tally as one Problem per thing found per place."""
        found = []
        for (where, place, (tag, severity, what)), count in self._counts.items():
            times = "" if count == 1 else f" {count} times"
            found.append(Problem(severity, tag, where, f"{what}  Found{times} in {place}.  {_ADVICE}"))
        return found


def _project_owners(kind: str) -> dict[str, str]:
    """{object id: owning Project name} for Profiles (<pids>) or Tasks (<tids>).

    proflint._project_owners, kept for its reason: asking maputils per object walks every
    Project each time, which would make a scan of the whole configuration quadratic, and
    this module promises to read nothing but PrimeItems.
    """
    owners: dict[str, str] = {}
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _scannable(element: defusedxml.ElementTree.Element) -> str:
    """The text of an element the scan is allowed to read, or "".

    "" for a name or a reference (see _REFERENCE_TAGS), which is how the one rule about
    what this feature will not touch is applied in both directions from one place.
    """
    if element.tag in _REFERENCE_TAGS:
        return ""
    return (element.text or "").strip()


def _scan_action(collect: _Collector, where: Target, action: defusedxml.ElementTree.Element) -> None:
    """One Task action: its named settings first, then whatever else it carries."""
    code = _action_code(action)
    names = _argument_names(code)

    arguments = {id(child): child for child in action if str(child.attrib.get("sr", "")).startswith("arg")}
    for child in arguments.values():
        argument = str(child.attrib["sr"])
        if (code, argument) in _NAME_ARGUMENTS:
            continue
        value = child.text or ""
        place = f"the '{names[argument]}' setting" if argument in names else f"argument {argument[3:]}"

        # A field Tasker itself calls Password is reported on the strength of its name, and
        # only then on the strength of what is in it -- the value of a password is exactly
        # the thing no pattern recognizes.
        credential = _credential_field(code, argument)
        if credential and not _is_empty_or_variable(value):
            collect.note(where, place, credential)
        elif value:
            collect.text(where, place, value)

    # Everything below the arguments: a plugin's <Bundle>, the <var> a bound integer holds,
    # a condition attached to the action.  Read as one place rather than named individually,
    # because a plugin's own field names are the plugin's and mean nothing here.
    for element in action.iter():
        if element is action or id(element) in arguments:
            continue
        value = _scannable(element)
        if value:
            collect.text(where, "this action's settings", value)


# Where Tasker keeps what was written about an object when it was published to TaskerNet:
# <Share> holds the description in <d>, and the Map draws it as a block of its own (share.py).
_SHARE = "Share"
_SHARE_DESCRIPTION = "d"


def _scan_tasks(collect: _Collector) -> None:
    """Every action of every Task, and the Task's own properties.

    The properties are not an afterthought.  A Project, Profile or Task can carry
    <ProfileVariable> children -- the values Tasker prompts for when the thing is imported,
    and the place a shared configuration is MEANT to keep its API key.  Which is exactly why
    they are scanned: the prompt has a default, the default is stored, and a backup taken
    after the key was typed in carries it.
    """
    owners = _project_owners("tids")
    for task_id, task in PrimeItems.tasker_root_elements["all_tasks"].items():
        base = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        inside_actions: set[int] = set()
        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            inside_actions.update(id(element) for element in action.iter())
            _scan_action(collect, base.at_action(number), action)
        _scan_properties(collect, base, task["xml"], inside_actions)


def _scan_projects(collect: _Collector) -> None:
    """Every Project's own properties -- see _scan_tasks on why those matter."""
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        _scan_properties(collect, Target(PROJECT, project_name, project_name), project["xml"], set())


def _scan_properties(
    collect: _Collector,
    where: Target,
    element: defusedxml.ElementTree.Element,
    skip: set[int],
) -> None:
    """Everything on an object that is not one of its actions.

    Each finding points at the line of the Map that actually SHOWS what was found, which
    for an object is one of three places:

      its TaskerNet description   drawn as a block of its own (share.py), well below the
                                  object's line.
      its Properties line         the comment, the collision handling and the import-time
                                  variables, written as one line by property.py -- and the
                                  place a shared configuration is meant to keep its API key.
      the object itself           everything else it carries: its name, its member lists,
                                  the icon, the dates.

    The distinction is the whole point.  "Found in this object's own properties" pointing
    at a Project's own line sent the reader to a line with nothing wrong on it, several
    screens above the property that did hold the address -- which reads as the scan being
    wrong rather than the finding being badly aimed.
    """
    description = element.find(f"{_SHARE}/{_SHARE_DESCRIPTION}")
    on_properties = _properties_elements(element)
    for child in element.iter():
        if child is element or id(child) in skip:
            continue
        value = _scannable(child)
        if not value:
            continue
        if child is description:
            collect.text(where.at_part(TASKERNET_PART), "the TaskerNet description", value)
        elif id(child) in on_properties:
            collect.text(where.at_part(PROPERTIES_PART), "this object's own properties", value)
        else:
            collect.text(where, "this object's own properties", value)


def _properties_elements(element: defusedxml.ElementTree.Element) -> set[int]:
    """{id(child)} for everything the object's "...Properties..." line shows.

    Which tags those are is property.PROPERTY_TAGS, read from there rather than restated
    here so that the line a finding points at cannot drift from the line the Map writes --
    the same contract mapjump.scene_element_parts holds for a Scene's elements.

    property is imported inside the function for the reason healthck and varxref import
    sceneedit inside theirs: it is part of the Map-output stack, nothing else here needs
    it, and keeping the dependency in the one place that uses it leaves this module
    importable, and testable, on its own.
    """
    from maptasker.src.property import PROPERTY_TAGS, VARIABLE_TAG  # noqa: PLC0415

    shown: set[int] = set()
    for child in element:
        if child.tag in PROPERTY_TAGS:
            shown.add(id(child))
        elif child.tag == VARIABLE_TAG:
            # The whole subtree: parse_variable displays essentially every child of one.
            shown.update(id(node) for node in child.iter())
    return shown


def _scan_profiles(collect: _Collector) -> None:
    """Every Profile's conditions, the coordinates a location condition holds, and its
    own properties.

    A Profile carries the same "...Properties..." line a Project and a Task do -- its
    comment and its import-time variables -- and it is drawn in the same place, well below
    the Profile's own line.  So a finding about one of those is aimed there rather than at
    the Profile, exactly as _scan_properties aims the other two.
    """
    owners = _project_owners("pids")
    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        where = Target(PROFILE, profile_id, profile["name"], owners.get(profile_id, ""))
        on_properties = _properties_elements(profile["xml"])
        for element in profile["xml"].iter():
            if element.tag == _LOCATION_CONDITION and _has_coordinates(element):
                collect.note(where, "this Profile's location condition", _LOCATION_FINDING)
                continue
            if element.tag in (_LATITUDE, _LONGITUDE):
                continue
            value = _scannable(element)
            if not value:
                continue
            if id(element) in on_properties:
                collect.text(where.at_part(PROPERTIES_PART), "this Profile's own properties", value)
            else:
                collect.text(where, "this Profile's conditions", value)


def _scan_scenes(collect: _Collector) -> None:
    """Every Scene, read whole.

    Not broken down by element: a Scene's layout is deeply nested and its element names are
    the Scene's own business, so a finding says which Scene rather than which button.  The
    Map view is where the user goes to see the rest, and that is what the finding links to.
    """
    for scene_name, scene in PrimeItems.tasker_root_elements["all_scenes"].items():
        where = Target(SCENE, scene_name, scene_name)
        for element in scene["xml"].iter():
            value = _scannable(element)
            if value:
                collect.text(where, f"Scene '{scene_name}'", value)


def _scan_variables(collect: _Collector) -> None:
    """Every global variable's value.

    The likeliest place of all for a key to be sitting: the recommended way to keep a
    secret out of an action is to put it in a variable, and a backup stores what that
    variable held when the backup was taken.  So the advice works right up to the moment
    the configuration is shared, which is exactly what this feature is for.

    Read from PrimeItems.xml_root rather than tasker_root_elements, which has no table of
    them, and from the XML rather than PrimeItems.variables, whose values globalvr has
    already HTML-escaped for display.
    """
    if PrimeItems.xml_root is None:
        return
    for variable in PrimeItems.xml_root.findall("Variable"):
        children = list(variable)
        if len(children) < 2:
            continue
        name = (children[0].text or "").strip()
        value = (children[1].text or "").strip()
        if name and value:
            collect.text(Target(VARIABLE, name, name), f"the value of {name}", value)


def _scan_preferences(collect: _Collector) -> None:
    """The Tasker preferences that hold a credential.

    A full backup carries the whole of Tasker's own settings, and one of them is the code
    that locks Tasker itself.  There is no object to jump to -- the Map does not draw the
    preferences -- so this is the one finding whose location is a sentence rather than a
    Target.
    """
    where = "Tasker preferences in this backup"
    for setting in PrimeItems.tasker_root_elements.get("all_services", []):
        name = (setting.findtext("n") or "").strip()
        value = setting.findtext("v") or ""
        credential = _CREDENTIAL_PREFERENCES.get(name)
        if credential and not _is_empty_or_variable(value):
            collect.note(where, "the Tasker preferences", credential)
            continue
        # And the rest of them by pattern.  Worth doing rather than stopping at the one
        # named credential: Tasker's own preferences include the API key its voice actions
        # use, which is a key like any other and is in every full backup that has one.
        collect.text(where, f"the Tasker preference '{name}'", value)


def _has_coordinates(condition: defusedxml.ElementTree.Element) -> bool:
    """Whether a location condition actually carries a place.

    Both halves, and not both zero: Tasker writes a <Loc> the moment a location condition
    is created, so an unfilled one is a condition somebody started rather than a home
    address.
    """
    latitude = condition.findtext(_LATITUDE) or ""
    longitude = condition.findtext(_LONGITUDE) or ""
    try:
        return bool(float(latitude) or float(longitude))
    except ValueError:
        return False


def lint_problems() -> list[Problem]:
    """Every secret and personal detail in the loaded configuration.

    What healthck folds into its report.  Ordered by tag and then by location so the
    findings arrive grouped -- healthck sorts them again for printing, but a stable order
    here is what makes two runs over the same file produce the same list.

    Safe to call with nothing loaded: every pass iterates lookup tables that are empty, and
    an empty list comes back.
    """
    collect = _Collector()

    _scan_variables(collect)
    _scan_projects(collect)
    _scan_tasks(collect)
    _scan_profiles(collect)
    _scan_scenes(collect)
    _scan_preferences(collect)

    def order(problem: Problem) -> tuple[str, str, int]:
        where = problem.where
        return (
            problem.tag,
            where if isinstance(where, str) else where.label,
            0 if isinstance(where, str) else where.action,
        )

    problems = collect.problems()
    problems.sort(key=order)
    return problems


# ##################################################################################
# The other half: taking the same things back out of an export.
# ##################################################################################
#
# Applied to the tree a standalone export has already built -- every renderer deep-copies
# what it exports, so this rewrites the copy and never the loaded configuration.  The
# renderers call it immediately before serializing, which is the one place all four of them
# pass through and therefore the one place a redaction cannot be forgotten.


@dataclass
class Redaction:
    """What one redaction pass took out, as a count per tag.

    Returned rather than kept, so the caller can tell the user what happened.  "Saved with
    3 things redacted" is worth saying; so, much more so, is "nothing was found", which
    warns the user not to treat the file as cleaned when it may simply hold a secret with
    no shape.
    """

    counts: dict[str, int]

    @property
    def total(self) -> int:
        """How many values were replaced."""
        return sum(self.counts.values())

    def summary(self) -> str:
        """The tags and counts as one line, worst first: 'SECRET-API-KEY x2, PII-EMAIL x1'."""
        return ", ".join(f"{tag} x{count}" for tag, count in sorted(self.counts.items()))


def _redact_text_element(element: defusedxml.ElementTree.Element, counts: dict[str, int]) -> None:
    """Replace whatever the rules find in one element's text."""
    value = _scannable(element)
    if not value:
        return
    redacted, found = redact_in_text(element.text or "")
    if found:
        element.text = redacted
        for finding in found:
            counts[finding.rule.tag] = counts.get(finding.rule.tag, 0) + 1


def _redact_action(action: defusedxml.ElementTree.Element, counts: dict[str, int]) -> None:
    """One exported action: its credential fields wholesale, then everything else by rule."""
    code = _action_code(action)
    arguments = {id(child): child for child in action if str(child.attrib.get("sr", "")).startswith("arg")}

    for child in arguments.values():
        argument = str(child.attrib["sr"])
        if (code, argument) in _NAME_ARGUMENTS:
            continue
        credential = _credential_field(code, argument)
        if credential and not _is_empty_or_variable(child.text or ""):
            tag, label, _severity, _what = credential
            child.text = f"[REDACTED:{label}]"
            counts[tag] = counts.get(tag, 0) + 1
        else:
            _redact_text_element(child, counts)

    for element in action.iter():
        if element is action or id(element) in arguments:
            continue
        _redact_text_element(element, counts)


def _redact_location(condition: defusedxml.ElementTree.Element, counts: dict[str, int]) -> None:
    """Zero out a location condition's coordinates.

    Zeroed rather than replaced with a placeholder, and rounded off to nothing rather than
    to a nearby point: see _REDACTED_COORDINATE.  The <rad> radius and the condition's own
    name are left alone -- neither says where.
    """
    if not _has_coordinates(condition):
        return
    for tag in (_LATITUDE, _LONGITUDE):
        element = condition.find(tag)
        if element is not None:
            element.text = _REDACTED_COORDINATE
    counts[_LOCATION_FINDING[0]] = counts.get(_LOCATION_FINDING[0], 0) + 1


def redact_tree(root: defusedxml.ElementTree.Element) -> Redaction:
    """Take the secrets and personal details out of an already-rendered export, in place.

    The redactor half of the module, and the exact counterpart of lint_problems(): the same
    _RULES table, the same _CREDENTIAL_FIELDS, the same refusal to touch a name or a
    reference.  Whatever the Health Check reports about a Project is what disappears from
    that Project's exported file, which is the property that makes the pair worth having --
    the report is how a user decides to redact, so it has to be describing the same thing.

    Deliberately safe to run on anything: the caller passes the <TaskerData> root of a
    standalone export, but nothing here depends on that shape.  It walks what it is given.

    The result stays a valid, importable Tasker file.  Every replacement lands in a string
    field, coordinates are zeroed rather than worded (Tasker reads those as numbers), and
    nothing that one element uses to find another is rewritten at all.
    """
    counts: dict[str, int] = {}

    actions = set()
    for action in root.iter("Action"):
        actions.add(id(action))
        for element in action.iter():
            actions.add(id(element))
        _redact_action(action, counts)

    for condition in root.iter(_LOCATION_CONDITION):
        _redact_location(condition, counts)

    for setting in root.iter("Setting"):
        credential = _CREDENTIAL_PREFERENCES.get((setting.findtext("n") or "").strip())
        value = setting.find("v")
        if credential and value is not None and not _is_empty_or_variable(value.text or ""):
            tag, label, _severity, _what = credential
            value.text = f"[REDACTED:{label}]"
            counts[tag] = counts.get(tag, 0) + 1

    # Everything else in the file -- a global <Variable>'s value, a Scene element's text, a
    # Project's import-time variables, the rest of the Tasker preferences, a Profile
    # condition that is not a location.
    #
    # Only the actions are held back, and for a reason that is not tidiness: the name a
    # Perform Task calls and the Scene a Show Scene shows are ordinary <Str> arguments, and
    # this pass has no way to tell one of those from a value.  _redact_action does, because
    # it reads the action's code first.  Everything the passes above have already rewritten
    # is left carrying a placeholder, which matches no rule, so a second look at it finds
    # nothing and nothing is counted twice.
    for element in root.iter():
        if id(element) not in actions:
            _redact_text_element(element, counts)

    return Redaction(counts)


def redaction_notice(result: Redaction) -> str:
    """The comment a redacted export carries at the top of it.

    Written into the file rather than only shown in the app, because the file is the thing
    that gets posted to a forum: whoever opens it next has no way of knowing it has been
    edited, and an action reading '[REDACTED:API-KEY]' would otherwise look like a bug in
    the configuration rather than a deliberate blank.

    It also says what redaction does not cover.  Somebody about to import this needs to know
    that the blanks have to be filled in again; somebody about to post it needs to know that
    a secret with no recognizable shape is still in there.
    """
    if result.total:
        removed = f"{result.total} value(s) were replaced with [REDACTED:...] markers ({result.summary()})."
    else:
        removed = "Nothing matching a known secret or personal detail was found to replace."
    return (
        " MapTasker redacted export. "
        f"{removed} "
        "Anything marked [REDACTED:...] has to be filled in again after importing, and any "
        "location condition has had its coordinates zeroed. "
        "This is a first pass, not a guarantee: a password or key that looks like an "
        "ordinary word cannot be recognized, and names are never changed because the file "
        "uses them to refer to itself. Read the file before sharing it. "
    )


def redact_rendered(root: defusedxml.ElementTree.Element) -> str:
    """Redact a rendered export in place, and return the comment to write above it.

    The one call the four standalone exports make, so that "redact this export" is a single
    line in each of them rather than four copies of the same three steps that could drift
    apart.  Called on the tree the renderer has just built and is about to serialize, which
    is a deep copy of the loaded configuration in all four cases -- nothing here can reach
    the file the user has open.

    The comment goes ABOVE <TaskerData> rather than inside it.  A comment in the prolog is
    something every XML parser is required to skip, while one inside the document is a child
    element's worth of surface area on an importer nobody here can test against -- and the
    exports deliberately hand Tasker a file shaped exactly like its own.
    """
    result = redact_tree(root)
    # '--' cannot appear inside an XML comment.  Nothing in the notice contains one today;
    # the guard is here because the notice quotes the tag names, and a tag added later
    # could.
    return f"<!--{redaction_notice(result).replace('--', '-')}-->\n"
