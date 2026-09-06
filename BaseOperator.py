import bpy
from bpy.props import *
from .common import *

class FileSelectOptions():
    # File browser filter
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    display_type = EnumProperty(
        items = (
            ('FILE_DEFAULTDISPLAY', 'Default', ''),
            ('FILE_SHORTDISLPAY', 'Short List', ''),
            ('FILE_LONGDISPLAY', 'Long List', ''),
            ('FILE_IMGDISPLAY', 'Thumbnails', '')
        ),
        default = 'FILE_IMGDISPLAY',
        options = {'HIDDEN', 'SKIP_SAVE'}
    )

class BlendMethodOptions():
    blend_method = EnumProperty(
        name = 'Blend Method', 
        description = 'Blend method for transparent material',
        items = (
            ('CLIP', 'Alpha Clip', ''),
            ('HASHED', 'Alpha Hashed', ''),
            ('BLEND', 'Alpha Blend', '')
        ),
        default = 'HASHED'
    )

    shadow_method = EnumProperty(
        name = 'Shadow Method', 
        description = 'Shadow method for transparent material',
        items = (
            ('CLIP', 'Alpha Clip', ''),
            ('HASHED', 'Alpha Hashed', ''),
        ),
        default = 'HASHED'
    )

    surface_render_method = EnumProperty(
        name = 'Surface Render Method', 
        description = 'Surface render method for transparent material',
        items = (
            ('DITHERED', 'Dithered', ''),
            ('BLENDED', 'Blended', ''),
        ),
        default = 'DITHERED'
    )

class OpenImage(FileSelectOptions):

    # File related
    files = CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory = StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    relative = BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    def running_fileselect_modal(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    def get_loaded_images(self):
        import_list, directory = self.generate_paths()
        loaded_images = tuple(load_image(path, directory) for path in import_list)

        return loaded_images

def channel_items_base(self, context):
    from . import lib

    items = []

    node = get_active_ypaint_node()
    if node:
        yp = node.node_tree.yp
        for i, ch in enumerate(yp.channels):
            # Add two spaces to prevent text from being translated
            text_ch_name = ch.name + '  '
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), text_ch_name, '', lib.get_icon(icon_name), i))

    return items

def channel_items(self, context):
    from . import lib

    items = channel_items_base(self, context)
    items.append(('-1', 'All Channels', '', lib.get_icon('channels'), len(items)))

    return items

def is_self_channel_idx_accessible(self):
    # NOTE: Check if self.channel_idx is accessible or not since Blender Debug build always returns invalid pointer
    try:
        channel_idx = int(self.channel_idx)
        return True
    except: pass

    return False

def get_self_channel_idx(self):
    # NOTE: This function is workaround for Blender Debug build since it always returns invalid pointer from self.channel_idx
    try: return int(self.channel_idx)
    except Exception as e:
        ypup = get_user_preferences()
        if ypup.developer_mode: print('EXCEPTIION:', e)

    return 0

def draw_self_channel_idx(self, layout, yp=None):
    if is_self_channel_idx_accessible(self):
        layout.prop(self, 'channel_idx', text='')
    else:
        if yp == None:
            node = get_active_ypaint_node()
            yp = node.node_tree.yp if node else None

        if yp and len(yp.channels) > 0:
            from . import lib

            first_ch = yp.channels[0]
            icon_name = lib.channel_custom_icon_dict[first_ch.type]
            layout.label(text=first_ch.name, icon_value=lib.get_icon(icon_name))

def update_uv_map_name(self, context):
    if not is_udim_supported(): return

    if isinstance(self.id_data, bpy.types.ShaderNodeTree):
        if self.id_data.yp.halt_update:
            return

    if hasattr(self, 'use_udim') and get_user_preferences().enable_auto_udim_detection:

        do_udim_checking = True

        # Only check for udim if the chosen type is image
        if hasattr(self, 'type'):
            prop = self.bl_rna.properties['type']
            for item in prop.enum_items:
                if item.identifier == 'IMAGE' and self.type != 'IMAGE':
                    do_udim_checking = False
                    break

        if do_udim_checking:
            from . import UDIM
            mat = get_active_material()
            objs = get_all_objects_with_same_materials(mat)
            self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_map)

def update_mask_uv_map_name(self, context):
    if not is_udim_supported(): return

    if hasattr(self, 'use_udim_for_mask') and get_user_preferences().enable_auto_udim_detection:

        if hasattr(self, 'mask_type') and self.mask_type != 'IMAGE': 
            self.use_udim_for_mask = False
        else:
            from . import UDIM
            mat = get_active_material()
            objs = get_all_objects_with_same_materials(mat)
            self.use_udim_for_mask = UDIM.is_uvmap_udim(objs, self.mask_uv_name)

def draw_base_image_settings(self, layout, split_val=0.4, show_hdr=True, show_interpolation=True, show_texcoord=True):
    acol = layout.column(align=False)

    row = split_layout(acol, split_val)
    row.label(text='')
    crow = row.row(align=True)
    crow.prop(self, 'use_custom_resolution')

    if not self.use_custom_resolution:
        row = split_layout(acol, split_val)
        right_aligned_label(row, 'Resolution:')
        crow = row.row(align=True)
        crow.prop(self, 'image_resolution', expand= True,)
    else:
        row = split_layout(acol, split_val)
        rcol = row.column(align=True)
        right_aligned_label(rcol, 'Width:')
        right_aligned_label(rcol, 'Height:')

        rcol = row.column(align=True)
        rcol.prop(self, 'width', text='')
        rcol.prop(self, 'height', text='')

    if show_hdr and hasattr(self, 'hdr'):
        row = split_layout(acol, split_val)
        row.label(text='')
        row.prop(self, 'hdr')

    #if is_udim_supported():
    #    row = split_layout(acol, split_val)
    #    row.label(text='')
    #    row.prop(self, 'use_udim')

    #row = split_layout(acol, split_val)
    #row.label(text='')
    #row.prop(self, 'use_image_atlas')

    if show_interpolation and hasattr(self, 'interpolation'):
        row = split_layout(layout, split_val)
        right_aligned_label(row, 'Interpolation:')
        row.prop(self, 'interpolation', text='')

def draw_base_mask_image_settings(parent, layout, split_val=0.4):

    acol = layout.column(align=True)

    row = split_layout(acol, split_val)
    row.label(text='')
    crow = row.row(align=True)
    crow.prop(parent, 'mask_use_custom_resolution')

    if not parent.mask_use_custom_resolution:
        row = split_layout(acol, split_val)
        right_aligned_label(row, 'Resolution:')
        crow = row.row(align=True)
        crow.prop(parent, 'mask_image_resolution', expand= True,)
    else:
        row = split_layout(acol, split_val)
        rcol = row.column(align=True)
        right_aligned_label(rcol, 'Width:')
        right_aligned_label(rcol, 'Height:')

        rcol = row.column(align=True)
        rcol.prop(parent, 'mask_width', text='')
        rcol.prop(parent, 'mask_height', text='')

    row = split_layout(acol, split_val)
    row.label(text='')
    row.prop(parent, 'mask_use_hdr')

    #if hasattr(parent, 'mask_interpolation'):
    #    row = split_layout(layout, split_val)
    #    right_aligned_label(row, 'Interpolation:')
    #    row.prop(parent, 'mask_interpolation', text='')

def draw_base_bake_target_settings(context, layout, btprops, bt=None, show_image_props=True, show_vcol_props=True, show_general_props=True, show_hdr=True, show_udim=True, yp=None):

    #layout = layout.column(align=True)

    any_normal_ch = False
    any_height_ch = False
    any_non_clamped_ch = False
    any_color_channel = False
    if bt:
        channels = get_bake_target_channels(bt)
        any_normal_ch = any([c for c in channels if c.special_type == 'NORMAL'])
        any_height_ch = any([c for c in channels if c.special_type == 'HEIGHT'])
        any_non_clamped_ch = any([c for c in channels if not c.use_clamp and c.special_type not in {'HEIGHT', 'NORMAL'}])
        any_color_channel = any([c for c in channels if c.type == 'RGB' and c.colorspace == 'SRGB' and c.use_clamp])

    show_float_normal_option = False
    show_float_height_option = False
    show_float_vdm_option = False
    if yp:
        for c in yp.channels:
            if c.special_type == 'NORMAL':
                bt = yp.bake_targets.get(c.bake_target_name)
                if bt and bt.bake_settings == 'GLOBAL' and hasattr(btprops, 'use_float_for_normal'):
                    show_float_normal_option = True
                any_normal_ch = True
            if c.special_type == 'HEIGHT':
                bt = yp.bake_targets.get(c.bake_target_name)
                if bt and bt.bake_settings == 'GLOBAL' and hasattr(btprops, 'use_float_for_displacement'):
                    show_float_height_option = True
                any_height_ch = True
            if c.special_type == 'VDISP':
                bt = yp.bake_targets.get(c.bake_target_name)
                if bt and bt.bake_settings == 'GLOBAL' and hasattr(btprops, 'use_float_for_vector_displacement'):
                    show_float_vdm_option = True
            if not c.use_clamp:
                any_non_clamped_ch = True
            if c.colorspace == 'SRGB' and c.type == 'RGB':
                any_color_channel = True

    obj = context.object

    factor = 0.35

    # Image properties
    if show_image_props:

        draw_base_image_settings(btprops, layout, factor, show_hdr=show_hdr, show_interpolation=True)

        row = split_layout(layout, factor)
        right_aligned_label(row, 'UV Map:')
        if obj and obj.type == 'MESH':
            row.prop_search(btprops, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
        else: row.prop(btprops, "uv_map", text='')

        if show_float_normal_option or show_float_height_option or show_float_vdm_option:
            row = split_layout(layout, factor)

            if (
                (show_float_normal_option and not show_float_height_option and not show_float_vdm_option) or
                (show_float_height_option and not show_float_normal_option and not show_float_vdm_option) or
                (show_float_vdm_option and not show_float_height_option and not show_float_normal_option)
            ):
                row.label(text='')
            else:
                right_aligned_label(row, 'Use 32-bit Float:')

            crow = row.row()

            if show_float_normal_option:
                if not show_float_height_option and not show_float_vdm_option:
                    title = 'Use 32-bit float for Normal'
                    crow.prop(btprops, 'use_float_for_normal', text=title)
                else: 
                    title = 'Normal'
                    if show_float_height_option and show_float_vdm_option:
                        rrow = crow.row(align=True)
                        rrow.scale_x = 1.1
                        rrow.prop(btprops, 'use_float_for_normal', text=title)
                    else:
                        crow.prop(btprops, 'use_float_for_normal', text=title)

            if show_float_height_option:
                if not show_float_normal_option and not show_float_vdm_option:
                    title = 'Use 32-bit float for Height'
                    crow.prop(btprops, 'use_float_for_displacement', text=title)
                else:
                    title = 'Height'
                    if show_float_normal_option and show_float_vdm_option:
                        rrow = crow.row(align=True)
                        rrow.scale_x = 1.1
                        rrow.prop(btprops, 'use_float_for_displacement', text=title)
                    else:
                        crow.prop(btprops, 'use_float_for_displacement', text=title)

            if show_float_vdm_option:
                if not show_float_height_option and not show_float_normal_option:
                    title = 'Use 32-bit float for VDM'
                else: title = 'VDM'
                crow.prop(btprops, 'use_float_for_vector_displacement', text=title)

        #layout.separator()

        row = split_layout(layout, factor)
        rcol = row.column(align=True)
        right_aligned_label(rcol, 'Samples:')
        right_aligned_label(rcol, 'AA Level:')

        rcol = row.column(align=True)
        rcol.prop(btprops, 'samples', text='')
        rcol.prop(btprops, 'aa_level', text='')

        row = split_layout(layout, factor)
        right_aligned_label(row, text='Margin:')
        if is_bl_newer_than(3, 1):
            split = split_layout(row, factor, align=True)
            split.prop(btprops, 'margin', text='')
            split.prop(btprops, 'margin_type', text='')
        else:
            row.prop(btprops, 'margin', text='')

        layout.separator()

        if show_udim:
            row = split_layout(layout, factor)
            row.label(text='')
            row.prop(btprops, 'use_udim')

        acol = layout.column(align=True)
        row = split_layout(acol, factor)
        row.label(text='')
        row.prop(btprops, 'fxaa', text='Use FXAA')

        if is_bl_newer_than(2, 81) and (not bt or 
                ((not any_height_ch or bt.height_normalize) and not any_non_clamped_ch)
        ): 
            row = split_layout(acol, factor)
            row.label(text='')
            #row.active = (not any_height_ch or bt.height_normalize) and not any_non_clamped_ch
            row.prop(btprops, 'denoise', text='Use Denoise')

        if not bt or any_color_channel:
            row = split_layout(acol, factor)
            row.label(text='')
            if not btprops.use_dithering:
                row.prop(btprops, 'use_dithering', text='Use Dithering')
            if btprops.use_dithering:
                rrow = split_layout(row, 0.55)
                rrow.prop(btprops, 'use_dithering', text='Use Dithering')
                rrow.prop(btprops, 'dither_intensity', text='')

    # Color attributes properties

    if show_vcol_props and is_bl_newer_than(3, 2):
        row = split_layout(layout, factor)

        rcol = row.column()
        right_aligned_label(rcol, text='Domain:')
        right_aligned_label(rcol, text='Data Type:')

        rcol = row.column()
        crow = rcol.row(align=True)
        crow.prop(btprops, 'vcol_domain', expand=True)
        crow = rcol.row(align=True)
        crow.prop(btprops, 'vcol_data_type', expand=True)

    # General properties
    if show_general_props:
        acol = layout.column(align=True)
        row = split_layout(acol, factor)
        row.label(text='')
        row.prop(btprops, 'force_bake_all_polygons')

        row = split_layout(acol, factor)
        row.label(text='')
        row.prop(btprops, 'bake_disabled_layers')

    if hasattr(btprops, 'bake_device') or hasattr(btprops, 'necessary_only'):
        if show_image_props or (show_vcol_props and is_bl_newer_than(3, 2)) or show_general_props:
            layout.separator()

        if hasattr(btprops, 'necessary_only'):
            row = split_layout(layout, factor)
            row.label(text='')
            row.prop(btprops, 'necessary_only', text='Only Necessary Channels')

        if is_bl_newer_than(2, 80) and hasattr(btprops, 'bake_device'):
            row = split_layout(layout, factor)
            right_aligned_label(row, 'Bake Device:')
            row.prop(btprops, 'bake_device', text='')

        #layout.separator()

class YPropertyGroup(bpy.types.PropertyGroup):
    name = StringProperty(default='')

classes = (
    YPropertyGroup,
)

def register():
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    for cls in classes: bpy.utils.unregister_class(cls)
