import bpy
from bpy.props import *
from bpy.types import Operator, AddonPreferences
from bpy.app.handlers import persistent
from . import image_ops
from .common import *

class YTLPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    auto_save = EnumProperty(
            name = 'Auto Save/Pack Images',
            description = 'Auto save/pack images when saving blend',
            items = (('FORCE_ALL', 'Force All Images', ''),
                     ('ONLY_DIRTY', 'Only Dirty Images', ''),
                     ('OFF', 'Off', ''),
                     ),
            default = 'ONLY_DIRTY')

    def draw(self, context):
        self.layout.prop(self, 'auto_save')

@persistent
def auto_save_images(scene):
    tlup = bpy.context.user_preferences.addons[__package__].preferences
    if tlup.auto_save == 'ONLY_DIRTY':
        image_ops.save_pack_all(only_dirty=True)
    elif tlup.auto_save == 'FORCE_ALL':
        image_ops.save_pack_all(only_dirty=False)

def register():
    bpy.app.handlers.save_pre.append(auto_save_images)

def unregister():
    bpy.app.handlers.save_pre.remove(auto_save_images)
