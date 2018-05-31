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

# HACK: For some reason active float image will glitch after auto save
# This hack will fix that
@persistent
def refresh_float_image_hack(scene):
    tlui = bpy.context.window_manager.tlui

    if tlui.refresh_image_hack:
        node = get_active_texture_layers_node()
        if node:
            tl = node.node_tree.tl
            if len(tl.textures) > 0:
                tex = tl.textures[tl.active_texture_index]
                source = tex.tree.nodes.get(tex.source)
                if hasattr(source, 'image'):
                    image = source.image
                    # Just reload image to fix glitched float image
                    if image: 
                        print("INFO: Just ignore error below if there's any, this is fine..")
                        image.reload()
                        print('INFO: ..fine error ended')

        tlui.refresh_image_hack = False

def register():
    bpy.app.handlers.save_pre.append(auto_save_images)
    bpy.app.handlers.save_post.append(refresh_float_image_hack)

def unregister():
    bpy.app.handlers.save_pre.remove(auto_save_images)
    bpy.app.handlers.save_post.remove(refresh_float_image_hack)
