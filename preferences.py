import bpy
from bpy.props import *
from bpy.types import AddonPreferences
from bpy.app.handlers import persistent
from . import image_ops
from .common import *
from .lib import *
from .UDIM import *

def update_icons(self, context):
    unload_custom_icons()
    load_custom_icons()

class YImageSizeOption(bpy.types.PropertyGroup):
    name : StringProperty(
        name = 'Image Size Option Name',
        description = 'Image size option name',
        default = '1024'
    )

    width : IntProperty(name='Width', description='Pixel Width', default=1024)
    height : IntProperty(name='Height', description='Pixel Height', default=1024)

    interpolation : EnumProperty(
        name = 'Image Interpolation Type',
        description = 'Image interpolation type',
        items = (
            ('Linear', 'Linear', 'Linear interpolation.'),
            ('Closest', 'Closest', 'No interpolation (sample closest texel).'),
        ),
        default = 'Linear'
    )

class YPaintPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    default_new_image_size : IntProperty(
        name = 'Custom Default Image Size',
        description = 'Default new image size',
        default=1024, min=64, max=16384
    )

    image_atlas_size : IntProperty(
        name = 'Image Atlas Size',
        description = 'Image Atlas Size',
        default=8192, min=2048, max=16384
    )

    hdr_image_atlas_size : IntProperty(
        name = 'HDR Image Atlas Size',
        description = 'HDR Image Atlas Size',
        default=4096, min=1024, max=8192
    )

    unique_image_atlas_per_yp : BoolProperty(
        name = 'Use unique Image Atlas per ' + get_addon_title() + ' tree',
        description = 'Try to use different image atlas per ' + get_addon_title() + ' tree',
        default = True
    )

    developer_mode : BoolProperty(
        name = 'Developer Mode',
        description = 'Developer mode will shows several menu intented for developer only',
        default = False
    )

    show_experimental : BoolProperty(
        name = 'Show Experimental Features',
        description = 'Show unfinished experimental features',
        default = False
    )

    use_image_preview : BoolProperty(
        name = 'Use Image Preview/Thumbnail',
        description = 'Use image preview or thumbnail on the layers list',
        default = False
    )

    skip_property_popups : BoolProperty(
        name = 'Skip Property Popups (Hold Shift to Show)',
        description = 'Don\'t show property popups unless Shift key is pressed. Will use last invokation properties if skipped',
        default = False
    )

    icons : EnumProperty(
        name = 'Icons',
        description = 'Icon set',
        items = (
            ('DEFAULT', 'Default', 'Icon set from the current Blender version'),
            ('LEGACY', 'Legacy', 'Icon set from the old Blender version')
        ),
        default = 'DEFAULT',
        update = update_icons
    )

    make_preview_mode_srgb : BoolProperty(
        name = 'Make Preview Mode use sRGB',
        description = 'Make sure preview mode use sRGB color',
        default = True
    )

    parallax_without_baked : BoolProperty(
        name = 'Parallax Without Use Baked',
        description = 'Make it possible to use parallax without using baked textures (currently VERY SLOW)',
        default = False
    )

    default_bake_device : EnumProperty(
        name = 'Bake Device',
        description = 'Default bake device',
        items = (
            ('DEFAULT', 'Default', 'Use last selected bake device'),
            ('CPU', 'CPU', 'Use CPU by default'),
            ('GPU', 'GPU Compute', 'Use GPU by default')
        ),
        default = 'DEFAULT'
    )

    enable_baked_outside_by_default : BoolProperty(
        name = 'Enable Baked Outside by default',
        description = "Enable baked outside by default when creating new " + get_addon_title() + " node.\n(Useful for creating game assets)",
        default = False
    )

    enable_uniform_uv_scale_by_default : BoolProperty(
        name = 'Enable Uniform UV Scale by default',
        description = "Enable uniform UV scale by default in Layer and Mask UVs. This will make all scale axes have the same value",
        default = False
    )

    enable_auto_udim_detection : BoolProperty(
        name = 'Enable Auto UDIM Detection',
        description = "Enable automatic UDIM detection. This will automatically check 'Use UDIM Tiles' checkboxes when UDIM is detected",
        default = True
    )

    enable_material_view_warning : BoolProperty(
        name = 'Enable "Switch to Material View" warning',
        description = "Enable warning popup when ucupaint parent window is not in a Material render/preview mode",
        default = True
    )

    layer_list_mode : EnumProperty(
        name = 'Layer Lists Mode',
        items = (
            ('DYNAMIC', "Dynamic", 'Dynamic layers list with dropdown support'),
            ('CLASSIC', "Classic", 'Classic layers list'),
            ('BOTH', "Dynamic & Classic (For Debugging)", 'Both Dynamic and Classic layers list for debugging'),
        ),
        default = 'DYNAMIC'
    )
    
    # Addon updater preferences.
    auto_check_update : BoolProperty(
        name = 'Auto-check for Update',
        description = 'If enabled, auto-check for updates using an interval',
        default = True
    )
    
    updater_interval_months : IntProperty(
        name = 'Months',
        description = 'Number of months between checking for updates',
        default=0, min=0
    )
    
    updater_interval_days : IntProperty(
        name = 'Days',
        description = 'Number of days between checking for updates',
        default=1, min=0, max=31
    )
    
    updater_interval_hours : IntProperty(
        name = 'Hours',
        description = 'Number of hours between checking for updates',
        default=0, min=0, max=23
    )
    
    updater_interval_minutes : IntProperty(
        name = 'Minutes',
        description = 'Number of minutes between checking for updates',
        default=1, min=0, max=59
    )

    default_image_resolution : EnumProperty(
        name = 'Default Image Size',
        items = (
            ('DEFAULT', "Default", 'Use the last selected image size'),
            ('512', "512", 'Always use a 512x512 image by default'),
            ('1024', "1024", 'Always use a 1024x1024 image by default'),
            ('2048', "2048", 'Always use a 2048x2048 image by default'),
            ('4096', "4096", 'Always use a 4096x4096 image by default'),
            ('CUSTOM', "Custom Resolution", 'Use a custom resolution by default')
        ),
        default = 'DEFAULT'
    )

    image_size_options : CollectionProperty(type=YImageSizeOption)
    default_image_size_option : IntProperty(default=0)
    ori_default_image_size_option : IntProperty(default=0) # Only set on register

    always_evaluate_frame : BoolProperty(
        name = 'Always Evaluate on Frame Change',
        description = 'Always fo frame change evaluation on '+get_addon_title()+' keyfame data (slow)',
        default = False
    )

    hide_update_notification : BoolProperty(
        name = 'Hide Update Notification',
        description = 'Always hide update notification',
        default = False
    )

    def draw(self, context):
        if is_bl_newer_than(2, 80):
            self.layout.prop(self, 'default_bake_device')
            self.layout.prop(self, 'icons')
        self.layout.prop(self, 'layer_list_mode')

        box = self.layout.box()
        boxcol = box.column(align=True)
        boxcol.label(text='Image Size Options')
        for i, option in enumerate(self.image_size_options):
            row = boxcol.row(align=True)

            rrow = row.row()
            rrow.scale_y = 2.0
            rrow.label(text='Option '+str(i))

            rrow = row.row()
            rrow.scale_y = 2.0
            rrow.prop(option, 'name', text='')

            row.separator()

            col = row.column(align=True)
            col.prop(option, 'width', text='Width')
            col.prop(option, 'height', text='Height')

            row.separator()

            rrow = row.row()
            rrow.scale_y = 2.0
            rrow.scale_x = 0.5
            rrow.prop(option, 'interpolation', expand=True)

            row.separator()

            rrow = row.row()
            rrow.scale_y = 2.0
            if i == self.default_image_size_option:
                rrow.label(text='Set as Default', icon='CHECKBOX_HLT')
            else: rrow.operator('wm.y_set_default_image_option', text='Set as Default', icon='CHECKBOX_DEHLT').index = i

            boxcol.separator()

        boxcol.separator()
        boxcol.prop(self, 'default_image_resolution')
        if self.default_image_resolution == 'CUSTOM':
            boxcol.prop(self, 'default_new_image_size')

        self.layout.prop(self, 'image_atlas_size')
        self.layout.prop(self, 'hdr_image_atlas_size')
        self.layout.prop(self, 'unique_image_atlas_per_yp')
        if is_udim_supported():
            self.layout.prop(self, 'enable_auto_udim_detection')
        self.layout.prop(self, 'enable_material_view_warning')
        self.layout.prop(self, 'make_preview_mode_srgb')
        self.layout.prop(self, 'use_image_preview')
        self.layout.prop(self, 'skip_property_popups')
        self.layout.prop(self, 'enable_baked_outside_by_default')
        self.layout.prop(self, 'always_evaluate_frame')
        if is_bl_newer_than(2, 81):
            self.layout.prop(self, 'enable_uniform_uv_scale_by_default')
        self.layout.prop(self, 'hide_update_notification')
        self.layout.prop(self, 'show_experimental')

        self.layout.prop(self, 'developer_mode')
        #self.layout.prop(self, 'parallax_without_baked')

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

class YSetDefaultImageOption(bpy.types.Operator):
    bl_idname = "wm.y_set_default_image_option"
    bl_label = "Set Default Image Option"
    bl_description = "Set default image option"
    #bl_options = {'REGISTER', 'UNDO'}

    index : IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        ypup = get_user_preferences()

        # Set the preference to file
        write_image_option_index_to_file(self.index)

        # Set the preference
        ypup.default_image_size_option = self.index

        return {'FINISHED'}

@persistent
def auto_save_images(scene):

    ypup = get_user_preferences()

    for tree in bpy.data.node_groups:
        if not hasattr(tree, 'yp'): continue
        if tree.yp.is_ypaint_node:
            image_ops.save_pack_all(tree.yp)

        # NOTE: Version update only happen when loading the blend file or updating the node tree
        # Update version
        #try: tree.yp.version = get_current_version_str()
        #except: print('EXCEPTIION: Cannot save yp version!')
        #try: tree.yp.blender_version = get_current_blender_version_str()
        #except: print('EXCEPTIION: Cannot save blender version!')
        #try: tree.yp.is_unstable = get_alpha_suffix() != ''
        #except: print('EXCEPTIION: Cannot save unstable version flag!')

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
    bpy.utils.register_class(YImageSizeOption)
    bpy.utils.register_class(YPaintPreferences)
    bpy.utils.register_class(YSetDefaultImageOption)

    ypup = get_user_preferences()

    default_index = 1

    if len(ypup.image_size_options) == 0:
        option = ypup.image_size_options.add()
        option.name = '512'
        option.width = 512
        option.height = 512

        option = ypup.image_size_options.add()
        option.name = '1024'
        option.width = 1024
        option.height = 1024

        option = ypup.image_size_options.add()
        option.name = '2048'
        option.width = 2048
        option.height = 2048

        option = ypup.image_size_options.add()
        option.name = '4096'
        option.width = 4096
        option.height = 4096

        ypup.default_image_size_option = default_index
        ypup.ori_default_image_size_option = default_index
        write_image_option_index_to_file(default_index)

    else:
        # Read from file to make sure the settings are in sync
        index = get_image_option_index_from_file()
        if index != None and index < len(ypup.image_size_options):
            ypup.default_image_size_option = index
            ypup.ori_default_image_size_option = index
        elif len(ypup.image_size_options) > default_index:
            ypup.default_image_size_option = default_index
            ypup.ori_default_image_size_option = default_index
            write_image_option_index_to_file(default_index)

    bpy.app.handlers.save_pre.append(auto_save_images)
    bpy.app.handlers.save_post.append(refresh_float_image_hack)

def unregister():
    bpy.utils.unregister_class(YImageSizeOption)
    bpy.utils.unregister_class(YPaintPreferences)
    bpy.utils.unregister_class(YSetDefaultImageOption)

    bpy.app.handlers.save_pre.remove(auto_save_images)
    bpy.app.handlers.save_post.remove(refresh_float_image_hack)
