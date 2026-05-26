import bpy
from bpy.props import *
from .common import is_bl_newer_than

updater_preferences = {
    'updater_auto_check_update' : BoolProperty(
        name = 'Auto-check for Update',
        description = 'If enabled, auto-check for updates using an interval',
        default = True
    ),
    
    'updater_interval_months' : IntProperty(
        name = 'Months',
        description = 'Number of months between checking for updates',
        default=0, min=0
    ),
    
    'updater_interval_days' : IntProperty(
        name = 'Days',
        description = 'Number of days between checking for updates',
        default=1, min=0, max=31
    ),
    
    'updater_interval_hours' : IntProperty(
        name = 'Hours',
        description = 'Number of hours between checking for updates',
        default=0, min=0, max=23
    ),
    
    'updater_interval_minutes' : IntProperty(
        name = 'Minutes',
        description = 'Number of minutes between checking for updates',
        default=1, min=0, max=59
    ),

}

def add_preference_props(Preference):
    for prop_name, prop in updater_preferences.items():
        if is_bl_newer_than(2, 80):
            Preference.__annotations__[prop_name] = prop
        else: setattr(Preference, prop_name, prop)

def draw_preferences(self, layout):
    if not self.developer_mode: return
    box = layout.box()

    box.prop(self, "updater_auto_check_update")
    sub_col = box.column()
    if not self.updater_auto_check_update:
        sub_col.enabled = False
    sub_row = sub_col.row()
    sub_row.label(text="Interval between checks")
    sub_row = sub_col.row(align=True)
    check_col = sub_row.column(align=True)
    check_col.prop(self, "updater_interval_days")
    check_col = sub_row.column(align=True)
    check_col.prop(self, "updater_interval_hours")
    check_col = sub_row.column(align=True)
    check_col.prop(self, "updater_interval_minutes")
    check_col = sub_row.column(align=True)
