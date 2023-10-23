import bpy
from bpy.props import *
from bpy.types import Operator, AddonPreferences
from bpy.app.handlers import persistent
from . import image_ops
from .common import *
from . import addon_updater_ops

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

    default_new_image_size : IntProperty(
            name = 'Default New Image Size',
            description = 'Default new image size',
            default = 1024,
            min=64, max=4096)

    image_atlas_size : IntProperty(
            name = 'Image Atlas Size',
            description = 'Image Atlas Size',
            default = 4096,
            min=2048, max=8192)

    hdr_image_atlas_size : IntProperty(
            name = 'HDR Image Atlas Size',
            description = 'HDR Image Atlas Size',
            default = 2048,
            min=1024, max=4096)

    unique_image_atlas_per_yp : BoolProperty(
            name = 'Use unique Image Atlas per ' + get_addon_title() + ' tree',
            description = 'Try to use different image atlas per ' + get_addon_title() + ' tree',
            default = True)

    developer_mode : BoolProperty(
            name = 'Developer Mode',
            description = 'Developer mode will shows several menu intented for developer only',
            default = False)

    show_experimental : BoolProperty(
            name = 'Show Experimental Features',
            description = 'Show unfinished experimental features',
            default = False)

    use_image_preview : BoolProperty(
            name = 'Use Image Preview/Thumbnail',
            description = 'Use image preview or thumbnail on the layers list',
            default = False)

    make_preview_mode_srgb : BoolProperty(
            name = 'Make Preview Mode use sRGB',
            description = 'Make sure preview mode use sRGB color',
            default = True)

    parallax_without_baked : BoolProperty(
            name = 'Parallax Without Use Baked',
            description = 'Make it possible to use parallax without using baked textures (currently VERY SLOW)',
            default = False)
    
    # Addon updater preferences.
    auto_check_update : BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=True)
    
    updater_interval_months : IntProperty(
        name='Months',
        description="Number of months between checking for updates",
        default=0,
        min=0)
    
    updater_interval_days : IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=1,
        min=0,
        max=31)
    
    updater_interval_hours : IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23)
    
    updater_interval_minutes : IntProperty(
        name='Minutes',
        description="Number of minutes between checking for updates",
        default=1,
        min=0,
        max=59)

    def draw(self, context):
        self.layout.prop(self, 'auto_save')
        self.layout.prop(self, 'default_new_image_size')
        self.layout.prop(self, 'image_atlas_size')
        self.layout.prop(self, 'hdr_image_atlas_size')
        self.layout.prop(self, 'unique_image_atlas_per_yp')
        self.layout.prop(self, 'make_preview_mode_srgb')
        self.layout.prop(self, 'use_image_preview')
        self.layout.prop(self, 'show_experimental')
        self.layout.prop(self, 'developer_mode')
        self.layout.prop(self, 'parallax_without_baked')

        if self.developer_mode:
            box = self.layout.box()

            box.prop(self, "auto_check_update")
            sub_col = box.column()
            if not self.auto_check_update:
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
@persistent
def auto_save_images(scene):

    if is_greater_than_280():
        ypup = bpy.context.preferences.addons[__package__].preferences
    else: ypup = bpy.context.user_preferences.addons[__package__].preferences

    for tree in bpy.data.node_groups:
        if not hasattr(tree, 'yp'): continue
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
