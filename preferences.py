import bpy
from bpy.props import *
from bpy.types import Operator, AddonPreferences
from bpy.app.handlers import persistent
from . import image_ops
from .common import *

class YPaintPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    auto_save : EnumProperty(
            name = 'Auto Save/Pack Images',
            description = 'Auto save/pack images when saving blend',
            items = (('FORCE_ALL', 'Force All Images', ''),
                     ('ONLY_DIRTY', 'Only Dirty Images', ''),
                     ('OFF', 'Off', ''),
                     ),
            default = 'ONLY_DIRTY')

    image_atlas_size : IntProperty(
            name = 'Image Atlas Size',
            description = 'Image Atlas Size',
            default = 4096)

    hdr_image_atlas_size : IntProperty(
            name = 'HDR Image Atlas Size',
            description = 'HDR Image Atlas Size',
            default = 2048)

    unique_image_atlas_per_yp : BoolProperty(
            name = 'Use unique Image Atlas per ' + ADDON_TITLE + ' tree',
            description = 'Try to use different image atlas per ' + ADDON_TITLE + ' tree',
            default = True)

    def draw(self, context):
        self.layout.prop(self, 'auto_save')
        self.layout.prop(self, 'image_atlas_size')
        self.layout.prop(self, 'hdr_image_atlas_size')
        self.layout.prop(self, 'unique_image_atlas_per_yp')

@persistent
def auto_save_images(scene):

    if is_greater_than_280():
        ypup = bpy.context.preferences.addons[__package__].preferences
    else: ypup = bpy.context.user_preferences.addons[__package__].preferences

    for tree in bpy.data.node_groups:
        if tree.yp.is_ypaint_node:
            if ypup.auto_save == 'ONLY_DIRTY':
                image_ops.save_pack_all(tree.yp, only_dirty=True)
            elif ypup.auto_save == 'FORCE_ALL':
                image_ops.save_pack_all(tree.yp, only_dirty=False)

# HACK: For some reason active float image will glitch after auto save
# This hack will fix that
@persistent
def refresh_float_image_hack(scene):
    ypui = bpy.context.window_manager.ypui

    if ypui.refresh_image_hack:
        node = get_active_ypaint_node()
        if node:
            yp = node.node_tree.yp
            if len(yp.layers) > 0:
                layer = yp.layers[yp.active_layer_index]
                source = get_layer_source(layer)
                if source.type == 'TEX_IMAGE' and source.image:
                    # Just reload image to fix glitched float image
                    print("INFO: Just ignore error below if there's any, this is fine..")
                    source.image.reload()
                    print('INFO: ..fine error ended')

        ypui.refresh_image_hack = False

def register():
    bpy.utils.register_class(YPaintPreferences)

    bpy.app.handlers.save_pre.append(auto_save_images)
    bpy.app.handlers.save_post.append(refresh_float_image_hack)

def unregister():
    bpy.utils.unregister_class(YPaintPreferences)

    bpy.app.handlers.save_pre.remove(auto_save_images)
    bpy.app.handlers.save_post.remove(refresh_float_image_hack)
