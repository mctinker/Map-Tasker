#! /usr/bin/env python3
"""Tasker codes that are deprecated, keyed the way action_codes is keyed"""

#                                                                                      #
# deprecate: the Task actions, Events and States Tasker has deprecated                 #
#                                                                                      #
# Keys carry the type suffix, exactly as in action_codes: 't' Task action, 'e' Event,  #
# 's' State.  They used to be bare numbers, which is type-blind -- and a number means   #
# entirely different things depending on the type.  Every entry below is an action      #
# except where marked, so the bare-number form was also marking, wrongly:               #
#                                                                                      #
#   10s  'Power'          12s  'HDMI Plugged'          411e  'Device Boot'              #
#                                                                                      #
# all three of which are current.  Nothing showed it while the deprecation notice was   #
# itself broken and never appeared; it surfaced the moment that was fixed.              #
#                                                                                      #
# The test for a Task action is whether Tasker still publishes it in                    #
# task_all_actions.json, which is exported from a running Tasker: it does not list       #
# actions it has removed.  Everything below is absent from that file, so none of them    #
# is ever actually looked up -- check_for_deprecation only marks a code action_codes     #
# also holds.  They are kept because a configuration old enough to still contain one is  #
# exactly when this is worth saying.                                                     #
#                                                                                       #
# 115t 'Test', 116t 'HTTP Post', 117t 'HTTP Head' and 118t 'HTTP Get' were listed here   #
# on the assumption that 'HTTP Request' had superseded them.  Tasker publishes all four, #
# in live categories, so they are current and were removed from this table.              #
# tests/test_deprecation.py enforces that rule rather than restating the list.           #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

depricated = {
    "10t": "Deprecated",
    "11t": "Deprecated",
    "12t": "Deprecated",
    "151t": "Deprecated",
    "411t": "Deprecated",
    "500t": "Deprecated",
    "510t": "Deprecated",
    "520t": "Deprecated",
    "530t": "Deprecated",
    "540t": "Deprecated",
    "557t": "Deprecated",
    "560t": "Deprecated",
    "565t": "Deprecated",
    "594t": "Deprecated",
    "696t": "Deprecated",
    "777t": "Deprecated",
    "876t": "Deprecated",
    "2087e": "Deprecated",  # Event 'Fingerprint Gesture'
}
