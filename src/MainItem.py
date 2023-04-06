# ########################################################################################## #
#                                                                                            #
# MainItem: process Tasker items: Project, Profile, Task, Scene                              #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #


class MainItem(object):
    def __init__(self, type):
        self.type = type

    def getname(self, key):
        return self.type

    def process_item(self, process_function):
        process_function()
