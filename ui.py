import bpy, re, time, os, sys, json
import requests, threading
from bpy.props import *
from bpy.app.handlers import persistent
from bpy.app.translations import pgettext_iface
from . import lib, Modifier, MaskModifier, UDIM, ListItem, Decal, modifier_common, BaseOperator
from .common import *

USE_CACHE_DELTA_MS = 250

RGBA_CHANNEL_PREFIX = {
    'Color' : '',
    'Alpha' : 'alpha_',
    'R' : 'r_',
    'G' : 'g_',
    'B' : 'b_',
}

def get_material_ui(mat):
    if not mat: return None
    ypui = bpy.context.window_manager.ypui

    mui = ypui.materials.get(mat.name)
    if not mui:
        mui = ypui.materials.add()
        mui.name = mat.name
        mui.material = mat

    return mui

def update_yp_ui():

    # Get active yp node
    node = get_active_ypaint_node()
    if not node or node.type != 'GROUP': return
    tree = node.node_tree
    yp = tree.yp
    ypui = bpy.context.window_manager.ypui

    # Check layer channel ui consistency
    if len(yp.layers) > 0:
        if len(ypui.layer_ui.channels) != len(yp.channels):
            ypui.need_update = True

    # Update UI
    if (ypui.tree_name != tree.name or 
        ypui.layer_idx != yp.active_layer_index or 
        ypui.channel_idx != yp.active_channel_index or 
        ypui.bake_target_idx != yp.active_bake_target_index or 
        ypui.need_update
        ):

        ypui.tree_name = tree.name
        ypui.layer_idx = yp.active_layer_index
        ypui.channel_idx = yp.active_channel_index
        ypui.bake_target_idx = yp.active_bake_target_index
        ypui.need_update = False
        ypui.halt_prop_update = True
        ypui.channels.clear()

        if len(yp.bake_targets) > 0:
            try: bt = yp.bake_targets[yp.active_bake_target_index]
            except: bt = None
            if bt:
                ypui.bake_target_ui.expand_content = bt.expand_content
                ypui.bake_target_ui.expand_bake_settings = bt.expand_bake_settings
                ypui.bake_target_ui.expand_r = bt.expand_r
                ypui.bake_target_ui.expand_g = bt.expand_g
                ypui.bake_target_ui.expand_b = bt.expand_b
                ypui.bake_target_ui.expand_a = bt.expand_a

        if len(yp.channels) > 0 and yp.active_channel_index < len(yp.channels) and yp.active_channel_index > 0:

            # Get channel
            channel = yp.channels[yp.active_channel_index]
            ypui.channel_ui.expand_content = channel.expand_content
            ypui.channel_ui.expand_base_vector = channel.expand_base_vector
            ypui.channel_ui.expand_subdiv_settings = channel.expand_subdiv_settings
            ypui.channel_ui.expand_parallax_settings = channel.expand_parallax_settings
            ypui.channel_ui.expand_alpha_settings = channel.expand_alpha_settings
            ypui.channel_ui.expand_bake_to_vcol_settings = channel.expand_bake_to_vcol_settings
            ypui.channel_ui.expand_input_bump_settings = channel.expand_input_bump_settings
            ypui.channel_ui.expand_smooth_bump_settings = channel.expand_smooth_bump_settings
            ypui.channel_ui.modifiers.clear()

            # Construct noncontextual channel UI objects
            for i, ch in enumerate(yp.channels):
                c = ypui.channels.add()
                c.expand_baked_data = ch.expand_baked_data

            # Construct channel UI objects
            for i, mod in enumerate(channel.modifiers):
                m = ypui.channel_ui.modifiers.add()
                m.expand_content = mod.expand_content

        if len(yp.layers) > 0:

            # Layer list item
            #ypui.layer_items.clear()
            #for i, layer in enumerate(yp.layers):
            #    li = ypui.layer_items.add()
            #    li.expand_subitems = layer.expand_subitems

            # Get layer
            layer = yp.layers[yp.active_layer_index]
            ypui.layer_ui.expand_content = layer.expand_content
            ypui.layer_ui.expand_vector = layer.expand_vector
            ypui.layer_ui.expand_source = layer.expand_source
            ypui.layer_ui.expand_masks = layer.expand_masks
            ypui.layer_ui.expand_channels = layer.expand_channels
            ypui.layer_ui.channels.clear()
            ypui.layer_ui.masks.clear()
            ypui.layer_ui.modifiers.clear()

            # Construct layer modifier UI objects
            for mod in layer.modifiers:
                m = ypui.layer_ui.modifiers.add()
                m.expand_content = mod.expand_content
            
            # Construct layer channel UI objects
            for i, ch in enumerate(layer.channels):
                c = ypui.layer_ui.channels.add()
                c.expand_bump_settings = ch.expand_bump_settings
                c.expand_intensity_settings = ch.expand_intensity_settings
                c.expand_transition_bump_settings = ch.expand_transition_bump_settings
                c.expand_transition_ramp_settings = ch.expand_transition_ramp_settings
                c.expand_transition_ao_settings = ch.expand_transition_ao_settings
                c.expand_input_settings = ch.expand_input_settings
                c.expand_blend_settings = ch.expand_blend_settings
                c.expand_source = ch.expand_source
                c.expand_source_1 = ch.expand_source_1
                c.expand_content = ch.expand_content

                for mod in ch.modifiers:
                    m = c.modifiers.add()
                    m.expand_content = mod.expand_content

                for mod in ch.modifiers_1:
                    m = c.modifiers_1.add()
                    m.expand_content = mod.expand_content

            # Construct layer masks UI objects
            for i, mask in enumerate(layer.masks):
                m = ypui.layer_ui.masks.add()
                m.expand_content = mask.expand_content
                m.expand_channels = mask.expand_channels
                m.expand_source = mask.expand_source
                m.expand_vector = mask.expand_vector

                for mch in mask.channels:
                    mc = m.channels.add()
                    mc.expand_content = mch.expand_content

                for mod in mask.modifiers:
                    mm = m.modifiers.add()
                    mm.expand_content = mod.expand_content

        ypui.halt_prop_update = False

def get_collapse_arrow_icon(collapse=False):
    if not is_bl_newer_than(2, 80):
        return 'TRIA_DOWN' if collapse else 'TRIA_RIGHT'

    return 'DOWNARROW_HLT' if collapse else 'RIGHTARROW'

def inbox_dropdown_button(row, item, prop, text, scale_override=0.0, icon_value=None):
    icon = get_collapse_arrow_icon(getattr(item, prop))

    if is_bl_newer_than(2, 80):

        row.alignment = 'LEFT'
        if is_bl_newer_than(2, 92):
            row.scale_x = 0.9 if scale_override == 0.0 else scale_override
        elif is_bl_newer_than(2, 83):
            row.scale_x = 0.95 #if scale_override == 0.0 else scale_override

        if icon_value != None:
            row.prop(item, prop, emboss=False, text=text, icon_value=icon_value)
        else: row.prop(item, prop, emboss=False, text=text, icon=icon)

    else:
        if icon_value != None:
            row.prop(item, prop, emboss=False, text='', icon_value=icon_value)
        else: row.prop(item, prop, emboss=False, text='', icon=icon)
        row.label(text=text)

def draw_bake_info(bake_info, layout, entity):

    yp = entity.id_data.yp
    bi = bake_info

    if bi.bake_type.startswith('OTHER_OBJECT_'):

        if is_bl_newer_than(2, 79):
            num_oos = len([oo for oo in bi.other_objects if oo.object])
        else: num_oos = len(bi.other_objects)

        layout.label(text='List of Objects:')
        box = layout.box()
        bcol = box.column()
        bcol.context_pointer_set('bake_info', bi)

        if num_oos > 0:
            for oo in bi.other_objects:
                if is_bl_newer_than(2,79) and not oo.object: continue
                brow = bcol.row()
                brow.context_pointer_set('other_object', oo)
                if is_bl_newer_than(2, 79):
                    brow.label(text=oo.object.name, icon_value=lib.get_icon('object_index'))
                else: brow.label(text=oo.object_name, icon_value=lib.get_icon('object_index'))
                brow.operator('wm.y_remove_bake_info_other_object', text='', icon_value=lib.get_icon('close'))

            if is_bl_newer_than(2, 79):
                bbcol = bcol.column(align=True)
                bbcol.operator('wm.y_select_all_other_objects', text='Select All', icon='RESTRICT_SELECT_OFF')
                bbcol.operator('wm.y_toggle_other_objects_visibility', text='Toggle Hide', icon='RESTRICT_VIEW_OFF')
        else:
            brow = bcol.row()
            brow.label(text='No source objects found!', icon='ERROR')

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m3:
        layer = yp.layers[int(m3.group(1))]
        layout.context_pointer_set('entity', layer)
    else: layout.context_pointer_set('entity', entity)

    layout.context_pointer_set('bake_info', bi)
    if bi.bake_type == 'SELECTED_VERTICES':
        c = layout.operator("wm.y_try_to_select_baked_vertex", text='Try to Reselect Vertices', icon='GROUP_VERTEX')
    c = layout.operator("wm.y_bake_to_layer", text='Rebake ' + bake_type_labels[bi.bake_type], icon_value=lib.get_icon('bake'))
    c.type = bi.bake_type
    if m1 or m3: c.target_type = 'LAYER'
    else: c.target_type = 'MASK'
    c.overwrite_current = True

class NODE_MT_copy_image_path_menu(bpy.types.Menu):
    bl_label = "Copy Image Path Options"
    bl_idname = "NODE_MT_copy_image_path_menu"
    bl_description = get_addon_title() + " Options for copying the image path or opening the containing folder"

    def draw(self, context):
        layout = self.layout
        image = context.image

        full_path = os.path.normpath(image.filepath or "")
        op = layout.operator("wm.copy_image_path_to_clipboard", text="Copy Image Filepath", icon="COPYDOWN")
        op.clipboard_text = full_path
        
        # Add more branches below for different operating systems
        if sys.platform in {'win32', 'darwin', 'linux'}: 

            if sys.platform == 'win32':
                browser_name = 'Explorer'
            elif sys.platform == 'darwin':
                browser_name = 'Finder'
            else: browser_name = 'File Manager'

            op = layout.operator("wm.open_containing_image_folder", text="Open Image in "+browser_name, icon="FILE_FOLDER")
            op.file_path = image.filepath
        else:
            folder_path = os.path.normpath(os.path.dirname(full_path)) if full_path else ""
            op = layout.operator("wm.copy_image_path_to_clipboard", text="Copy Containing Folder Path")
            op.clipboard_text = folder_path

def draw_image_props(context, source, layout, entity=None, show_flip_y=False, show_datablock=True, show_source_input=False):

    image = source.image

    col = layout.column()

    # NOTE: Assuming show source input always used in mask ui
    if entity and show_source_input:
        draw_mask_source_input(col, entity, split_factor=0.4)

    unlink_op = 'wm.y_remove_layer'
    if entity:
        yp = entity.id_data.yp
        m1 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())
        if m1: 
            layer = yp.layers[int(m1.group(1))]
            col.context_pointer_set('layer', layer)
            col.context_pointer_set('mask', entity)
            unlink_op = 'wm.y_remove_layer_mask'
        elif m2: 
            layer = yp.layers[int(m2.group(1))]
            col.context_pointer_set('layer', layer)
            col.context_pointer_set('channel', entity)
            if show_flip_y:
                unlink_op = 'wm.y_remove_channel_override_1_source'
            else: unlink_op = 'wm.y_remove_channel_override_source'

    bi = image.y_bake_info
    if (bi.is_baked and not bi.is_baked_channel and 
        (not bi.is_baked_entity or bi.baked_entity_type in {'EDGE_DETECT', 'AO'}) # NOTE: Some baked type can come from entity
    ):
        #if image.yia.is_image_atlas or image.yua.is_udim_atlas:
        #    col.label(text=image.name + ' (Baked)', icon_value=lib.get_icon('image'))
        #elif show_datablock: col.template_ID(source, "image", unlink=unlink_op)
        #col.label(text='Type: ' + bake_type_labels[bi.bake_type], icon_value=lib.get_icon('bake'))

        draw_bake_info(bi, col, entity)
        return

    if image.yia.is_image_atlas or image.yua.is_udim_atlas:

        if image.yia.is_image_atlas:
            segment = image.yia.segments.get(entity.segment_name)
        else: segment = image.yua.segments.get(entity.segment_name)

        #if segment and segment.bake_info.is_baked:
        #    bi = segment.bake_info
        #    col.label(text=image.name + ' (Baked)', icon_value=lib.get_icon('image'))
        #    col.label(text='Type: ' + bake_type_labels[bi.bake_type], icon_value=lib.get_icon('bake'))
        #else: col.label(text=image.name, icon_value=lib.get_icon('image'))
        if segment:
            if image.yia.is_image_atlas:
                row = col.row()
                row.label(text='Atlas Tile X: ' + str(segment.tile_x))
                row.label(text='Atlas Tile Y: ' + str(segment.tile_y))
                row = col.row()
                row.label(text='Width: ' + str(segment.width))
                row.label(text='Height: ' + str(segment.height))
            else:
                split = split_layout(col, 0.4)
                split.label(text='Atlas Tiles: ')
                row = split.row(align=True)
                segment_tilenums = UDIM.get_udim_segment_tilenums(segment)
                for tilenum in segment_tilenums:
                    row.label(text=str(tilenum))

            if segment.bake_info.is_baked:
                draw_bake_info(segment.bake_info, col, entity)

        split = split_layout(col, 0.4)
        scol = split.column()
        scol.label(text='Interpolation:')
        scol = split.column()
        scol.prop(source, 'interpolation', text='')

        return

    if show_datablock: col.template_ID(source, "image", unlink=unlink_op)
    if image.source == 'GENERATED':
        col.label(text='Generated image settings:')
        row = col.row()

        col1 = row.column(align=True)
        col1.prop(image, 'generated_width', text='X')
        col1.prop(image, 'generated_height', text='Y')

        col1.prop(image, 'use_generated_float', text='Float Buffer')
        col2 = row.column(align=True)
        col2.prop(image, 'generated_type', expand=True)

        row = col.row()
        row.label(text='Color:')
        row.prop(image, 'generated_color', text='')

    elif image.source == 'FILE':
        if not image.filepath:
            col.label(text='Image Path: -')
        else:
            # Create a row with two parts: one label and one dropdown button.
            row = col.row(align=True)
            row.label(text="Path: " + os.path.normpath(image.filepath))
            row.context_pointer_set('image', image)
            row.menu("NODE_MT_copy_image_path_menu", text="", icon='DOWNARROW_HLT')

        image_format = 'RGBA'
        image_bit = int(image.depth / 4)
        if image.depth in {24, 48, 96}:
            image_format = 'RGB'
            image_bit = int(image.depth / 3)

        col.label(
            text='Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                ' ' + image_format + ' ' + str(image_bit) + '-bit'
        )

    split = split_layout(col, 0.4)

    scol = split.column()
    scol.label(text='Color Space:')
    if hasattr(image, 'use_alpha'):
        scol.label(text='Use Alpha:')
    scol.label(text='Alpha Mode:')

    scol.label(text='Interpolation:')

    scol.label(text='Extension:')
    #scol.label(text='Projection:')
    #if source.projection == 'BOX':
    #    scol.label(text='Blend:')

    scol = split.column()

    if not image.is_dirty:
        scol.prop(image.colorspace_settings, "name", text='') 
        if hasattr(image, 'use_alpha'):
            scol.prop(image, 'use_alpha', text='')
        scol.prop(image, 'alpha_mode', text='')
    else:
        scol.label(text=image.colorspace_settings.name)
        if hasattr(image, 'use_alpha'):
            scol.label(text='True' if image.use_alpha else 'False')
        scol.label(text=alpha_mode_labels[image.alpha_mode])

    scol.prop(source, 'interpolation', text='')

    scol.prop(source, 'extension', text='')
    #scol.prop(source, 'projection', text='')
    #if source.projection == 'BOX':
    #    scol.prop(entity, 'projection_blend', text='')

    if entity and hasattr(entity, 'image_flip_y') and show_flip_y:
        row = col.row(align=True)
        row.label(text='Flip G:')
        row.prop(entity, 'image_flip_y', text='')

def draw_object_index_props(entity, layout):
    col = layout.column()
    row = split_layout(col, 0.6)
    row.label(text='Object Index:')
    row.prop(entity, 'object_index', text='')

def draw_hemi_props(entity, source, layout):
    col = layout.column()
    col.prop(entity, 'hemi_space', text='Space')
    col.label(text='Light Direction:')

    # Get light direction
    norm = source.node_tree.nodes.get('Normal')

    col.prop(norm.outputs[0], 'default_value', text='')
    col.prop(entity, 'hemi_use_prev_normal', text='Use Previous Normal')
    col.prop(entity, 'hemi_camera_ray_mask', text='Camera Ray Mask')

def draw_mask_source_input(layout, mask, split_factor=0.5):
    layout.context_pointer_set('mask', mask)
    split = split_layout(layout, split_factor)
    split.label(text='Input:')

    outp = get_mask_input_socket(mask)

    label = ''
    if mask.type not in {'IMAGE', 'VCOL'}:
        label = mask_type_labels[mask.type] + ' '
    if outp: label += outp.name
    split.menu("NODE_MT_y_layer_mask_input_menu", text=label)

    # Swizzle options
    if outp.type in {'RGBA', 'RGB', 'VECTOR'}:

        split = split_layout(layout, split_factor)
        split.label(text='Swizzle:')

        split.prop(mask, "swizzle_input_mode", text='')

def draw_vcol_props(layout, vcol=None, entity=None, show_divide_rgb_alpha=True, show_source_input=False):
    if show_divide_rgb_alpha and hasattr(entity, 'divide_rgb_by_alpha'):
        row = layout.row(align=True)
        row.label(text='Divide RGB by Alpha:')
        row.prop(entity, 'divide_rgb_by_alpha', text='')

    # NOTE: Assuming show source input always used in mask ui
    if entity and show_source_input:
        draw_mask_source_input(layout, entity, split_factor=0.4)

def is_input_skipped(inp):
    if is_bl_newer_than(2, 81):
        return inp.name == 'Vector' or not inp.enabled

    return inp.name == 'Vector'

def draw_tex_props(source, layout, entity=None, show_source_input=False):

    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(text=title + ' Properties:')
    #col.separator()

    # NOTE: Assuming show source input always used in mask ui
    if show_source_input:
        draw_mask_source_input(col, entity)

    if title == 'Brick':

        separator_needed  = {'Mortar'}

        row = col.row()
        col = row.column(align=True)
        col.label(text='Offset:')
        col.label(text='Frequency:')
        col.separator()

        col.label(text='Squash:')
        col.label(text='Frequency:')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')
            if inp.name in separator_needed:
                col.separator()

        col = row.column(align=True)
        col.prop(source, 'offset', text='')
        col.prop(source, 'offset_frequency', text='')
        col.separator()

        col.prop(source, 'squash', text='')
        col.prop(source, 'squash_frequency', text='')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')
            if inp.name in separator_needed:
                col.separator()

    elif title == 'Checker':

        separator_needed  = {'Color2'}

        row = col.row()

        col = row.column(align=True)
        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')
            if inp.name in separator_needed:
                col.separator()

        col = row.column(align=True)
        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')
            if inp.name in separator_needed:
                col.separator()

    elif title == 'Gradient':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Type:')
        col = row.column(align=True)
        col.prop(source, 'gradient_type', text='')

    elif title == 'Magic':

        row = col.row()

        col = row.column(align=True)
        col.label(text='Depth:')
        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

    elif title == 'Musgrave':

        row = col.row()
        col = row.column(align=True)
        if is_bl_newer_than(2, 81):
            col.label(text='Dimensions:')
        col.label(text='Type:')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)
        if is_bl_newer_than(2, 81):
            col.prop(source, 'musgrave_dimensions', text='')
        col.prop(source, 'musgrave_type', text='')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

    elif title == 'Noise':

        row = col.row()
        col = row.column(align=True)
        if is_bl_newer_than(2, 81):
            col.label(text='Dimensions:')
            if hasattr(source, 'noise_type'):
                col.label(text='Type:')
            if is_bl_newer_than(4):
                col.label(text='Normalize:')
            else:
                col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)
        if is_bl_newer_than(2, 81):
            col.prop(source, 'noise_dimensions', text='')

            if hasattr(source, 'noise_type'):
                col.prop(source, 'noise_type', text='')
            if is_bl_newer_than(4):
                col.prop(source, 'normalize', text='')
            else:
                col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

    elif title == 'Gabor':
        row = col.row()
        col = row.column(align=True)
        col.label(text='Gabor Type:')

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)
        col.prop(source, 'gabor_type', text='')

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

    elif title == 'Voronoi':

        row = col.row()

        col = row.column(align=True)
        if is_bl_newer_than(2, 81):
            col.label(text='Dimensions:')
        else: col.label(text='Coloring:')

        if is_bl_newer_than(2, 80):
            col.label(text='Feature:')
            if source.feature not in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'}:
                col.label(text='Distance:')

        if is_bl_newer_than(4) and source.feature != 'N_SPHERE_RADIUS':
            col.label(text='Normalize:')
        else:
            col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)

        if is_bl_newer_than(2, 81):
            col.prop(source, 'voronoi_dimensions', text='')
        else: col.prop(source, 'coloring', text='')

        if is_bl_newer_than(2, 80):
            if entity and is_bl_newer_than(2, 81):
                col.prop(entity, 'voronoi_feature', text='')
            else: col.prop(source, 'feature', text='')
            if source.feature not in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'}:
                col.prop(source, 'distance', text='')

        if is_bl_newer_than(4) and source.feature not in {'N_SPHERE_RADIUS'}:
            col.prop(source, 'normalize', text='')
        else:
            col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

    elif title == 'Wave':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Type:')
        if hasattr(source, 'bands_direction'):
            col.label(text='Band Direction:')
        col.label(text='Profile:')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.label(text=inp.name + ':')

        col = row.column(align=True)
        col.prop(source, 'wave_type', text='')
        if hasattr(source, 'bands_direction'):
            col.prop(source, 'bands_direction', text='')
        if hasattr(source, 'wave_profile'):
            col.prop(source, 'wave_profile', text='')
        col.separator()

        for inp in source.inputs:
            if is_input_skipped(inp): continue
            col.prop(inp, 'default_value', text='')

def draw_input_bundle_props(entity, source, layout):
    col = layout.column()
    row = col.row()
    row.operator('wm.y_sync_bundle_input_layer', text='Sync Inputs')

def draw_colorid_props(entity, source, layout, layer=None):
    col = layout.column()
    row = col.row()
    row.label(text='Color ID:')
    draw_input_prop(row, entity, 'color_id', layer=layer)

def draw_solid_color_props(entity, source, layout):
    col = layout.column()
    row = col.row()
    row.label(text='Color:')
    row.prop(source.outputs[0], 'default_value', text='')

def draw_edge_detect_props(entity, source, layout, layer=None):
    col = layout.column()
    row = col.row()
    row.label(text='Radius:')
    draw_input_prop(row, entity, 'edge_detect_radius', layer=layer)

    row = col.row()
    row.label(text='Cycles Method:')
    row.prop(entity, 'edge_detect_method', text='')

    row = col.row()
    row.label(text='Use Previous Normal:')
    row.prop(entity, 'hemi_use_prev_normal', text='')

def draw_ao_props(entity, source, layout, layer=None):
    col = layout.column()

    row = col.row()
    row.label(text='Distance:')
    draw_input_prop(row, entity, 'ao_distance', layer=layer)

    # NOTE: AO samples is a bit irrelevant
    #row = col.row()
    #row.label(text='Samples:')
    #row.prop(source, 'samples', text='')

    row = col.row()
    row.label(text='Inside:')
    row.prop(source, 'inside', text='')

    row = col.row()
    row.label(text='Only Local (Cycles Only):')
    row.prop(source, 'only_local', text='')

    row = col.row()
    row.label(text='Use Previous Normal:')
    row.prop(entity, 'hemi_use_prev_normal', text='')

def draw_inbetween_modifier_mask_props(layer, source, layout):
    col = layout.column()
    if layer.modifier_type == 'CURVE':
        source.draw_buttons_ext(bpy.context, col)
    elif layer.modifier_type == 'RAMP':
        col.template_color_ramp(source, "color_ramp", expand=True)

def draw_input_prop(layout, entity, prop_name, emboss=None, text='', layer=None):
    inp = get_entity_prop_input(entity, prop_name, layer=layer)
    if emboss != None:
        if inp: layout.prop(inp, 'default_value', text=text, emboss=emboss)
        else: layout.prop(entity, prop_name, text=text, emboss=emboss)
    else:
        if inp: layout.prop(inp, 'default_value', text=text)
        else: layout.prop(entity, prop_name, text=text) 

def draw_mask_modifier_stack(layer, mask, layout, ui, layer_tree):
    ypui = bpy.context.window_manager.ypui
    tree = get_mask_tree(mask, layer_tree)

    for i, m in enumerate(mask.modifiers):

        try: modui = ui.modifiers[i]
        except: 
            ypui.need_update = True
            return

        can_be_expanded = m.type in MaskModifier.can_be_expanded

        row = layout.row(align=True)

        rrow = row.row(align=True)

        if can_be_expanded:
            if modui.expand_content:
                icon_value = lib.get_icon('uncollapsed_modifier')
            else: icon_value = lib.get_icon('collapsed_modifier')
            inbox_dropdown_button(rrow, modui, 'expand_content', m.name, icon_value=icon_value)
        else:
            rrow.label(text='', icon_value=lib.get_icon('modifier'))
            rrow.label(text=m.name)

        if is_bl_newer_than(2, 80): rrow = row.row(align=True) # To make sure the next row align right

        row.context_pointer_set('layer', layer)
        row.context_pointer_set('mask', mask)
        row.context_pointer_set('modifier', m)
        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.menu("NODE_MT_y_mask_modifier_menu", text='', icon=icon)

        row.prop(m, 'enable', text='')

        if modui.expand_content and can_be_expanded:
            row = layout.row(align=True)
            row.label(text='', icon='BLANK1')
            box = row.box()
            box.active = m.enable
            MaskModifier.draw_modifier_properties(tree, m, box)

def draw_modifier_stack(context, parent, channel_type, layout, ui, layer=None, extra_blank=False, use_modifier_1=False, layout_active=True, is_root_ch=False):

    ypui = context.window_manager.ypui

    modifiers = parent.modifiers
    if use_modifier_1:
        modifiers = parent.modifiers_1

    # Check if parent is layer channel
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
    if match:
        yp = parent.id_data.yp
        layer = yp.layers[int(match.group(1))]
        root_ch = yp.channels[int(match.group(2))]
        ch = layer.channels[int(match.group(2))]

    for i, m in enumerate(modifiers):

        try: 
            if use_modifier_1:
                modui = ui.modifiers_1[i]
            else: modui = ui.modifiers[i]
        except: 
            ypui.need_update = True
            return

        mod_tree = get_mod_tree(m)
        can_be_expanded = m.type in Modifier.can_be_expanded
        
        row = layout.row(align=True)
        row.active = layout_active

        label = m.name

        rrow = row.row(align=True)

        if can_be_expanded:
            if modui.expand_content:
                icon_value = lib.get_icon('uncollapsed_modifier')
            else: icon_value = lib.get_icon('collapsed_modifier')
            #row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            inbox_dropdown_button(rrow, modui, 'expand_content', label, scale_override=0.95, icon_value=icon_value)
        else:
            rrow.label(text='', icon_value=lib.get_icon('modifier'))
            rrow.label(text=label)

        if is_bl_newer_than(2, 80): rrow = row.row(align=True) # To make sure the next row align right
        
        if not modui.expand_content:

            if m.type == 'RGB_TO_INTENSITY':
                row.prop(m, 'rgb2i_col', text='', icon='COLOR')
                row.separator()

            #if m.type == 'INVERT':
            #    if channel_type == 'VALUE':
            #        row.prop(m, 'invert_r_enable', text='Value', toggle=True)
            #        row.prop(m, 'invert_a_enable', text='Alpha', toggle=True)
            #    else:
            #        row.prop(m, 'invert_r_enable', text='R', toggle=True)
            #        row.prop(m, 'invert_g_enable', text='G', toggle=True)
            #        row.prop(m, 'invert_b_enable', text='B', toggle=True)
            #        row.prop(m, 'invert_a_enable', text='A', toggle=True)
            #    row.separator()

            #if m.type == 'MATH':
            #    row.prop(m, 'math_r_val', text='')
            #    if channel_type != 'VALUE':
            #        row.prop(m, 'math_g_val', text='')
            #        row.prop(m, 'math_b_val', text='')
            #    if m.affect_alpha :
            #        row.prop(m, 'math_a_val', text='')
            #    row.separator()

            if m.type == 'OVERRIDE_COLOR': # and not m.oc_use_normal_base:
                if channel_type == 'VALUE':
                    row.prop(m, 'oc_val', text='')
                else: 
                    row.prop(m, 'oc_col', text='', icon='COLOR')
                    row.separator()

        row.context_pointer_set('layer', layer)
        row.context_pointer_set('parent', parent)
        row.context_pointer_set('modifier', m)
        if use_modifier_1:
            icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            row.menu("NODE_MT_y_modifier1_menu", text='', icon=icon)
        else:
            icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            row.menu("NODE_MT_y_modifier_menu", text='', icon=icon)
        row.prop(m, 'enable', text='')

        if modui.expand_content and can_be_expanded:
            row = layout.row(align=True)
            row.active = layout_active
            #row.label(text='', icon='BLANK1')
            row.label(text='', icon='BLANK1')
            box = row.box()
            box.active = m.enable
            Modifier.draw_modifier_properties(bpy.context, channel_type, mod_tree.nodes, m, parent, box, is_root_ch=is_root_ch)

            #row.label(text='', icon='BLANK1')

def draw_bake_target_channel(context, layout, bt, letter='r'):
    yp = bt.id_data.yp
    ypui = context.window_manager.ypui
    btui = ypui.bake_target_ui

    btc = getattr(bt, letter)
    ch = yp.channels.get(btc.channel_name) if btc.channel_name != '' else None

    row = layout.row(align=True)
    if ch:
        icon_name = letter
        #if getattr(btui, 'expand_' + letter):
        #    icon_name = 'uncollapsed_' + icon_name
        #else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon(icon_name)
        icon = get_collapse_arrow_icon(getattr(btui, 'expand_' + letter))
        row.prop(btui, 'expand_' + letter, text='', emboss=False, icon=icon)
        if is_bl_newer_than(2, 80):
            row.prop(btui, 'expand_' + letter, text='', emboss=False, icon_value=icon_value)
        else: row.label(text='', icon_value=icon_value)

    else:
        row.label(text='', icon='BLANK1')
        row.label(text='', icon_value=lib.get_icon(letter))

    if btc.channel_name == '':
        split = split_layout(row, 0.65, align=True)
        split.prop_search(btc, "channel_name", yp, "channels", text='')
        split.prop(btc, 'default_value', text='')
    else:
        if ch and ch.type in {'RGB', 'VECTOR'}:
            split = split_layout(row, 0.75, align=True)
            split.prop_search(btc, "channel_name", yp, "channels", text='')
            split.prop(btc, 'subchannel_index', text='')
        else:
            row.prop_search(btc, "channel_name", yp, "channels", text='')

    if ch and getattr(btui, 'expand_' + letter):

        row = layout.row(align=True)
        row.label(text='', icon='BLANK1')
        box = row.box()
        bcol = box.column()

        brow = bcol.row(align=True)
        brow.label(text='Invert Value:')
        brow.prop(btc, 'invert_value', text='')

def draw_preview_mode_ui(context, layout, node):
    yp = node.node_tree.yp
    ypup = get_user_preferences()
    wm = context.window_manager
    ypui = wm.ypui

    col = layout.column(align=True)

    row = col.row(align=True)

    use_popover = is_bl_newer_than(2, 80) #and False
    show_settings = True #not yp.use_baked
    if not use_popover:
        show_settings &= yp.preview_mode

    if show_settings and use_popover:
        row = split_layout(row, 0.6, align=True)

    scale_y = 1.0
    row.alert = yp.preview_mode
    title = 'Preview Mode'
    row.prop(yp, 'preview_mode', text=title, icon='HIDE_OFF')

    try: root_ch = yp.channels[yp.preview_mode_channel_index]
    except: root_ch = None

    if show_settings:
        if use_popover:
            rrow = row.row(align=True)
            rrow.scale_y = scale_y
            rrow.active = yp.preview_mode

            title = root_ch.name if root_ch else 'Settings'
            if root_ch and not yp.use_baked:
                if yp.preview_mode_type == 'CHANNEL':
                    title += ' (Final)'
                elif yp.preview_mode_type == 'LAYER':
                    title += ' (Layer)'
                elif yp.preview_mode_type == 'ALPHA':
                    title += ' (Alpha)'
                elif yp.preview_mode_type == 'SPECIFIC_MASK':
                    extra_title = ''

                    try: layer = yp.layers[yp.active_layer_index]
                    except: layer = None
                    if layer:
                        for mask in layer.masks:
                            if mask.active_edit:
                                extra_title = ' (Mask)'
                                break

                    if extra_title == '':
                        extra_title = ' (Data)'
                    title += extra_title

            setting_icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            icon_name = lib.channel_custom_icon_dict[root_ch.type] if root_ch else setting_icon
            icon_value = lib.get_icon(icon_name)
            if yp.use_baked:
                rrow.popover("NODE_PT_ypaint_preview_mode_channel_settings_popover", text=title, icon_value=icon_value)
            else: rrow.popover("NODE_PT_ypaint_preview_mode_settings_popover", text=title, icon_value=icon_value)
        else:
            draw_preview_mode_settings(context, col, node)

def draw_preview_mode_popover_settings(context, layout, node, show_types=True):
    yp = node.node_tree.yp

    #layout.active = yp.preview_mode

    layout.label(text='Preview Mode Settings')

    try: root_ch = yp.channels[yp.preview_mode_channel_index]
    except:
        layout.label(text='No channel to preview', icon='ERROR')
        return

    if show_types:
        row = split_layout(layout, 0.4)

        col = row.column()

        if not yp.use_baked:
            ccol = col.column(align=True)
            ccol.label(text='Type')
            #ccol.prop(yp, "preview_mode_type", expand=True)

            if yp.preview_mode and yp.preview_mode_type == 'CHANNEL': ccol.alert = True
            ccol.operator('wm.y_toggle_preview_mode', text='Final Channel').type = 'CHANNEL'
            ccol.alert = False

            if yp.preview_mode and yp.preview_mode_type == 'LAYER': ccol.alert = True
            ccol.operator('wm.y_toggle_preview_mode', text='Layer').type = 'LAYER'
            ccol.alert = False

            if yp.preview_mode and yp.preview_mode_type == 'ALPHA': ccol.alert = True
            ccol.operator('wm.y_toggle_preview_mode', text='Layer Alpha').type = 'ALPHA'
            ccol.alert = False

            if yp.preview_mode and yp.preview_mode_type == 'SPECIFIC_MASK': ccol.alert = True
            ccol.operator('wm.y_toggle_preview_mode', text='Active Mask/Data').type = 'SPECIFIC_MASK'
            ccol.alert = False
    else:
        row = layout

    col = row.column()
    col.active = yp.preview_mode

    ccol = col.column(align=True)
    ccol.label(text='Channel')
    ccol.template_list("NODE_UL_YPaint_simple_channels", "", yp,
            "channels", yp, "preview_mode_channel_index", rows=len(yp.channels), maxrows=5)  

    if root_ch.special_type == 'NORMAL':
        ccol = col.column(align=True)
        ccol.label(text='Normal Space')
        ccol.prop(yp, 'preview_mode_normal_space', text='')

    color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)
    if (yp.preview_mode_type == 'CHANNEL' or yp.use_baked) and alpha_ch != None:
        row = col.row()
            
        row.active = root_ch != alpha_ch
        row.prop(yp, 'preview_mode_use_alpha', text='Use Alpha')

def draw_preview_mode_settings(context, layout, node):
    yp = node.node_tree.yp

    layout.active = yp.preview_mode

    split_val = 0.3
    cbox = layout.box()
    bcol = cbox.column(align=True)
    
    try: root_ch = yp.channels[yp.preview_mode_channel_index]
    except:
        bcol.label(text='No channel to preview', icon='ERROR')
        return

    if not yp.use_baked:
        row = split_layout(bcol, split_val)
        row.label(text='Type:')
        row.prop(yp, "preview_mode_type", text='')

    row = split_layout(bcol, split_val)
    row.label(text='Channel:')
    icon_value = lib.get_icon(lib.channel_custom_icon_dict[root_ch.type])
    rrow = row.row(align=True)
    rrow.menu("NODE_MT_y_preview_mode_channel_menu", text=root_ch.name, icon_value=icon_value)
    if root_ch.special_type == 'NORMAL': rrow.prop(yp, 'preview_mode_normal_space', text='')

    color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)
    if is_channel_preview_mode_enabled(yp) and alpha_ch != None:
        row = split_layout(bcol, split_val)
        #row.label(text='Use Alpha:')
        row.label(text='')
            
        row.active = root_ch != alpha_ch
        row.prop(yp, 'preview_mode_use_alpha', text='Use Alpha')

def is_baked_node_found(yp):
    nodes = yp.id_data.nodes

    # Check for baked node
    for bt in yp.bake_targets:
        baked_node = nodes.get(bt.baked_node)
        if baked_node: 
            return True

    return False

def draw_main_ui(context, layout):
    wm = context.window_manager
    area = context.area
    scene = context.scene
    node = get_active_ypaint_node()
    obj = context.object
    mat = obj.active_material if obj else None
    ypui = wm.ypui
    ypup = get_user_preferences()

    ypui.expanded_main_ui = True

    # NOTE: Blender 4.2+ can detect if user is currently in a modal operation
    # [HACK] Cache is necessary to improve performace since blender always update the UI in modal operation and when using the sliders
    use_cache = ypui.use_cache or (is_bl_newer_than(4, 2) and len(bpy.context.window.modal_operators) > 0)

    # Timer
    #if wm.yptimer.time != '':
    #    print('INFO: Scene is updated in', '{:0.2f}'.format((time.time() - float(wm.yptimer.time)) * 1000), 'ms!')
    #    wm.yptimer.time = ''

    ## NOTE: [HACK] Disable cache if delta time already pass the limit
    #if ypui.use_cache:
    #    delta = get_node_slider_delta_ms()
    #    if delta > USE_CACHE_DELTA_MS:
    #        ypui.use_cache = False

    ## Update ui props first
    #update_yp_ui()

    addon_updater_ops = get_package_module('.addon_updater_ops')
    if addon_updater_ops:
        need_restart = addon_updater_ops.draw_top_ui_panel(context, layout)
        if need_restart: return

    # Extension platform update notification
    if is_online() and not ypup.hide_update_notification and ypui.extension_update_state == 'AVAILABLE':
        col = layout.column()
        row_alert = col.row(align=True)
        row_alert.alert = True
        row_alert.operator("extensions.userpref_show_for_update", icon='ERROR', text='New version is available!') # + ypui.latest_version)
        row_alert.alert = False
        row_alert.operator("ext.y_pending_update", icon='PANEL_CLOSE', text='')

    # Check if Mio3 UV checker found
    if obj and any([m for m in obj.modifiers if m.type == 'NODES' and m.node_group and m.node_group.name == 'Mio3MaterialOverride' and (m.show_viewport or m.show_render)]):
        row = layout.row(align=True)
        row.alert = True
        op = row.operator("wm.y_remove_mio3_uv_checker", icon='ERROR')
        row.alert = False
        return

    # Check if uv is found
    is_a_mesh = True if obj and obj.type == 'MESH' else False
    uv_layers = get_uv_layers(obj)

    uv_found = False
    if is_a_mesh and len(uv_layers) > 0: 
        uv_found = True

    if is_a_mesh and not uv_found:
        row = layout.row(align=True)
        row.alert = True
        row.operator("wm.y_add_simple_uvs", icon='ERROR')
        row.alert = False
        return

    if not node:
        #layout.label(text="No active " + get_addon_title() + " node!", icon='ERROR')
        layout.operator("wm.y_quick_ypaint_node_setup", icon_value=lib.get_icon('nodetree'))

        return

    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp

    if version_tuple(yp.version) < version_tuple(get_current_version_str()):
        col = layout.column()
        col.alert = True
        col.label(text=group_tree.name + ' (' + yp.version + ')', icon_value=lib.get_icon('nodetree'))
        col.operator("wm.y_update_yp_trees", text='Update node to version ' + get_current_version_str(), icon='ERROR')
        return

    # Message will appear when opening file with newer node version
    if version_tuple(yp.version) > version_tuple(get_current_version_str()):
        col = layout.column()
        col.alert = True
        col.label(text='This node uses newer version!', icon='ERROR')
        if is_installed_through_extension_platform():
            # Extension platform releases link
            col.operator('wm.url_open', text='Update '+get_addon_title(), icon='ERROR').url = 'https://extensions.blender.org/add-ons/ucupaint/'
        else: 
            if is_online():
                # Blender with online access already has the update button
                col.label(text='Please update the addon!', icon='BLANK1')
            else:
                # Github releases link
                col.operator('wm.url_open', text='Update '+get_addon_title(), icon='ERROR').url = 'https://github.com/ucupumar/ucupaint/releases'

    # Message will appear when legacy alpha toggle is enabled by accident
    legacy_alpha_found = False
    if not ypup.developer_mode:
        for ch in yp.channels:
            if ch.enable_alpha:
                legacy_alpha_found = True
                break

        if legacy_alpha_found:
            col = layout.column()
            col.alert = True
            col.label(text='Legacy alpha accidentally enabled!', icon='ERROR')
            col.operator("wm.y_disable_legacy_channel_alpha", text='Disable Legacy Alpha')

    if ypup.developer_mode and is_bl_newer_than(2, 78):
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch and height_root_ch.enable_smooth_bump:
            col = layout.column()
            col.alert = True
            col.label(text='Smooth(er) bump is no longer supported!', icon='ERROR')
            col.operator("wm.y_update_remove_smooth_bump", text='Remove Smooth Bump')
            #return

    ##layout.label(text='Active: ' + node.node_tree.name, icon_value=lib.get_icon('nodetree'))
    #row = layout.row(align=True)
    #row.label(text='', icon_value=lib.get_icon('nodetree'))
    ##row.label(text='Active: ' + node.node_tree.name)
    #row.label(text=node.node_tree.name)
    ##row.prop(node.node_tree, 'name', text='')

    #icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
    #row.menu("NODE_MT_ypaint_special_menu", text='', icon=icon)

    # Check duplicated yp node (indicated by more than one users)
    if group_tree.users > 1:
        row = layout.row(align=True)
        row.alert = True
        op = row.operator("wm.y_duplicate_yp_nodes", text='Fix Multi-User ' + get_addon_title() + ' Node', icon='ERROR')
        op.duplicate_node = True
        op.duplicate_material = False
        op.only_active = True
        row.alert = False
        #layout.prop(ypui, 'make_image_single_user')
        return

    # Check if layer and yp has different numbers of channels
    channel_mismatch = False
    num_channels = len(yp.channels)
    for layer in yp.layers:
        if len(layer.channels) != num_channels:
            channel_mismatch = True
            break
            
        for mask in layer.masks:
            if len(mask.channels) != num_channels:
                channel_mismatch = True
                break

        if channel_mismatch:
            break

    if channel_mismatch:
        row = layout.row(align=True)
        row.alert = True
        row.operator("wm.y_fix_channel_missmatch", text='Fix Missmatched Channels!', icon='ERROR')
        row.alert = False
        return

    # If error happens, halt_update and halt_reconnect can stuck on, add button to disable it
    if yp.halt_update:
        row = layout.row(align=True)
        row.alert = True
        row.prop(yp, 'halt_update', text='Disable Halt Update', icon='ERROR')
        row.alert = False
    if yp.halt_reconnect:
        row = layout.row(align=True)
        row.alert = True
        row.prop(yp, 'halt_reconnect', text='Disable Halt Reconnect', icon='ERROR')
        row.alert = False

    # NOTE: Avoid checking missing data, linear colors, and AO problems when in modal operation to avoid performance loss
    if use_cache:
        missing_data = ypui.cache_missing_data
        linear_problem = ypui.cache_linear_problem
        ao_problem = ypui.cache_ao_problem
        missing_combine_bundle = ypui.cache_missing_combine_bundle
    else:
        vcols = get_vertex_colors(obj)
        linear_problem, ao_problem, missing_data, missing_combine_bundle = any_yp_problems(node, vcols)
        ypui.cache_linear_problem = linear_problem
        ypui.cache_ao_problem = ao_problem
        ypui.cache_missing_data = missing_data
        ypui.cache_missing_combine_bundle = missing_combine_bundle
    
    # Show missing data button
    if missing_data:
        row = layout.row(align=True)
        row.alert = True
        row.operator("wm.y_fix_missing_data", icon='ERROR')
        row.alert = False
        return

    if missing_combine_bundle:
        row = layout.row(align=True)
        row.alert = True
        row.operator("wm.y_fix_missing_combine_bundle_node", icon='ERROR')
        row.alert = False

    if linear_problem:
        row = layout.row(align=True)
        row.alert = True
        row.operator('wm.y_use_linear_color_space', text='Fix Linear Colorspace Problem', icon='ERROR')
        row.alert = False

    if ao_problem:
        row = layout.row(align=True)
        row.alert = True
        row.operator('wm.y_fix_edge_detect_ao', text='Fix EEVEE Edge Detect AO', icon='ERROR')
        row.alert = False

    # Refresh tangent sign
    if (is_tangent_sign_hacks_needed(yp) and area.type == 'VIEW_3D' and 
        area.spaces[0].shading.type == 'RENDERED' and scene.render.engine == 'CYCLES'):
        row = layout.row(align=True)
        row.operator('wm.y_refresh_tangent_sign_vcol', icon='FILE_REFRESH', text='Tangent')

    if yp.sculpt_mode:
        # Sculpt mode

        layer = yp.layers[yp.active_layer_index]
        source = get_layer_source(layer)

        box = layout.box()

        if source and source.image:
            row = box.row()
            row.label(text='Sculpting: ' + source.image.name, icon_value=lib.get_icon('image'))

        row = box.row()
        row.alert = True
        row.operator('sculpt.y_apply_sculpt_to_image', icon='SCULPTMODE_HLT', text='Apply Sculpt to Image')
        row = box.row(align=True)
        row.operator('sculpt.y_cancel_sculpt_to_image', icon='X', text='Cancel Sculpt')
    else:

        # Check for baked node
        baked_found = is_baked_node_found(yp)

        if (baked_found or yp.use_baked) and not group_tree.users > 1:
            rrow = layout.row(align=True)
            rrow.operator('wm.y_bake_all_targets', text='Rebake', icon_value=lib.get_icon('bake')).with_prompt = True
            rrow.separator()
            rrow.prop(yp, 'use_baked', toggle=True, text='Use Baked')
            rrrow = rrow.row(align=True)
            rrrow.active = yp.use_baked
            rrrow.prop(yp, 'enable_baked_outside', toggle=True, text='Outside', icon='NODETREE')

            #rrow.separator()

            #icon = 'TRASH' if is_bl_newer_than(2, 80) else 'CANCEL'
            #rrow.operator('wm.y_delete_baked_channel_images', text='', icon=icon)

        # Preview mode
        draw_preview_mode_ui(context, layout, node)

        if yp.use_baked:
            draw_baked_ui(context, layout, node)
        else: draw_layers_ui(context, layout, node)

def draw_stats_ui(context, layout, node, show_header=False):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui

    images = []
    vcols = []
    num_ramps = 0
    num_curves = 0
    num_gen_texs = 0

    for root_ch in yp.channels:
        for mod in root_ch.modifiers:
            if not mod.enable: continue
            if mod.type == 'COLOR_RAMP':
                num_ramps += 1
            elif mod.type == 'RGB_CURVE':
                num_curves += 1

    for layer in yp.layers:
        if not layer.enable: continue
        layer_tree = get_tree(layer)
        if layer.type == 'IMAGE':
            src = get_layer_source(layer, layer_tree)
            if src.image and src.image not in images:
                images.append(src.image)
        elif layer.type == 'VCOL':
            src = get_layer_source(layer, layer_tree)
            vcol_name = get_source_vcol_name(src)
            if vcol_name != '' and vcol_name not in vcols:
                vcols.append(vcol_name)
        elif layer.type in {'BRICK', 'CHECKER', 'GRADIENT', 'MAGIC', 'MUSGRAVE', 'NOISE', 'GABOR', 'VORONOI', 'WAVE'}:
            num_gen_texs += 1

        for ch in layer.channels:
            if ch.enable:
                if ch.override:
                    if ch.override_type == 'IMAGE':
                        src = get_channel_source(ch, layer)
                        if src.image and src.image not in images:
                            images.append(src.image)
                    elif ch.override_type == 'VCOL':
                        src = get_channel_source(ch, layer)
                        vcol_name = get_source_vcol_name(src)
                        if vcol_name != '' and vcol_name not in vcols:
                            vcols.append(vcol_name)
                    elif ch.override_type not in {'DEFAULT'}:
                        num_gen_texs += 1
                if ch.override_1:
                    if ch.override_1_type == 'IMAGE':
                        src = layer_tree.nodes.get(ch.source_1)
                        if src.image and src.image not in images:
                            images.append(src.image)

                for mod in ch.modifiers:
                    if not mod.enable: continue
                    if mod.type == 'COLOR_RAMP':
                        num_ramps += 1
                    elif mod.type == 'RGB_CURVE':
                        num_curves += 1

                if ch.enable_transition_ramp:
                    num_ramps += 1

                if ch.enable_transition_bump and ch.transition_bump_falloff and ch.transition_bump_falloff_type == 'CURVE':
                    num_curves += 1

        for mod in layer.modifiers:
            if not mod.enable: continue
            if mod.type == 'COLOR_RAMP':
                num_ramps += 1
            elif mod.type == 'RGB_CURVE':
                num_curves += 1

        if not layer.enable_masks: continue

        for mask in layer.masks:
            if not mask.enable: continue
            mask_tree = get_mask_tree(mask, layer_tree)
            if mask.use_baked:
                src = mask_tree.nodes.get(mask.baked_source)
                if src.image and src.image not in images:
                    images.append(src.image)
            elif mask.type == 'IMAGE':
                src = mask_tree.nodes.get(mask.source)
                if src.image and src.image not in images:
                    images.append(src.image)
            elif mask.type == 'VCOL':
                src = mask_tree.nodes.get(mask.source)
                vcol_name = get_source_vcol_name(src)
                if vcol_name != '' and vcol_name not in vcols:
                    vcols.append(vcol_name)
            elif mask.type in {'BRICK', 'CHECKER', 'GRADIENT', 'MAGIC', 'MUSGRAVE', 'NOISE', 'GABOR', 'VORONOI', 'WAVE'}:
                num_gen_texs += 1

            if mask.type == 'MODIFIER':
                if mask.modifier_type == 'RAMP':
                    num_ramps += 1
                elif mask.modifier_type == 'CURVE':
                    num_curves += 1

            for mod in mask.modifiers:
                if not mod.enable: continue
                if mod.type == 'RAMP':
                    num_ramps += 1
                elif mod.type == 'CURVE':
                    num_curves += 1

    #box = layout.box()
    box = layout
    col = box.column()

    if show_header:
        col.label(text='Stats:')

    col.label(text=pgettext_iface('Number of Images: ') + str(len(images)), icon_value=lib.get_icon('image'))
    col.label(text=pgettext_iface('Number of '+get_vertex_color_label()+': ') + str(len(vcols)), icon_value=lib.get_icon('vertex_color'))
    col.label(text=pgettext_iface('Number of Generated Textures: ') + str(num_gen_texs), icon_value=lib.get_icon('texture'))
    col.label(text=pgettext_iface('Number of Color Ramps: ') + str(num_ramps), icon_value=lib.get_icon('modifier'))
    col.label(text=pgettext_iface('Number of RGB Curves: ') + str(num_curves), icon_value=lib.get_icon('modifier'))

    #col.operator('wm.y_new_image_atlas_segment_test', icon_value=lib.get_icon('image'))
    #col.operator('wm.y_new_udim_atlas_segment_test', icon_value=lib.get_icon('image'))
    #col.operator('wm.y_uv_transform_test', icon_value=lib.get_icon('uv'))

def draw_bake_targets_ui(context, layout, node, show_header=False, rows=4):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp

    ypui = context.window_manager.ypui
    btui = ypui.bake_target_ui

    #box = layout.box()
    box = layout
    col = box.column()

    #if show_header:
    #    #col.operator('wm.y_bake_all_targets', text='Bake '+get_addon_title()+' Node', icon_value=lib.get_icon('bake')).with_prompt = True
    #    col.label(text='Bake Target Settings')

    row = col.row(align=True)

    col.operator('wm.y_bake_all_targets', text='Bake '+get_addon_title()+' Node', icon_value=lib.get_icon('bake')).with_prompt = True

    if show_header:
        col.label(text='Bake Target Settings')

    row = col.row()

    rcol = row.column(align=False)

    rows = rows if rows >= 4 else 4
    rcol.template_list(
        "NODE_UL_YPaint_bake_targets", "", yp, "bake_targets", yp,
        "active_bake_target_index", rows=rows, maxrows=5
    )

    rcol = row.column(align=True)

    try: bt = yp.bake_targets[yp.active_bake_target_index]
    except: bt = None


    if bt: rcol.context_pointer_set('bake_target', bt)

    if is_bl_newer_than(2, 80):
        rcol.operator("wm.y_new_bake_target", icon='ADD', text='')
        rcol.operator("wm.y_remove_bake_target", icon='REMOVE', text='')
    else: 
        rcol.operator("wm.y_new_bake_target", icon='ZOOMIN', text='')
        rcol.operator("wm.y_remove_bake_target", icon='ZOOMOUT', text='')

    rcol.operator("wm.y_move_bake_target", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("wm.y_move_bake_target", text='', icon='TRIA_DOWN').direction = 'DOWN'
    rcol.menu("NODE_MT_y_bake_list_special_menu", text='', icon='DOWNARROW_HLT')

    if bt and len(yp.bake_targets) > 0:
        baked_node = nodes.get(bt.baked_node)
        image = None
        vcol_name = ''

        if bt.data_type == 'IMAGE':
            image = baked_node.image if baked_node and baked_node.type == 'TEX_IMAGE' and baked_node.image else None
        else: vcol_name = baked_node.attribute_name if baked_node and baked_node.type == 'ATTRIBUTE' else ''

        row = col.row(align=True)
        row.label(text='', icon='BLANK1')

        info_col = row.column()
        row_image = info_col.row(align=True)

        empty_label = '- (not baked yet)'
        if bt.data_type == 'VCOL':
            vcol_name = empty_label if vcol_name == '' else vcol_name
            row_image.label(text=get_vertex_color_label()+': ' + vcol_name, icon_value=lib.get_icon('vertex_color'))
        elif bt.data_type == 'IMAGE':
            image_name = image.name if image else empty_label
            row_image.label(text='Image: ' + image_name, icon_value=lib.get_icon('image'))

        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        if bt.data_type == 'IMAGE': row_image.context_pointer_set('image', image)
        row_image.context_pointer_set('bt', bt)
        row_image.menu("NODE_MT_y_bake_target_menu", text='', icon=icon)

        #if not image:
        #    row = col.row(align=True)
        #    row.label(text='', icon='BLANK1')
        #    row.label(text=f"Do 'Bake {bt.name}' to get the image!", icon='ERROR')

        icon_name = 'bake'
        #if btui.expand_content:
        #    icon_name = 'uncollapsed_' + icon_name
        #else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon('channels')

        row = col.row(align=True)

        icon = get_collapse_arrow_icon(btui.expand_content)

        if is_bl_newer_than(2, 80):
            row.alignment = 'LEFT'
            row.scale_x = 0.95

        row.prop(btui, 'expand_content', text='', emboss=False, icon=icon)

        bt_label = 'Channel'

        has_height_channel = False
        has_normal_channel = False

        channels = get_bake_target_channels(bt)
        if len(channels) > 1:
            bt_label += 's'

        if not btui.expand_content:
            bt_label += ': '
            if len(channels) > 0:
                for i, ch in enumerate(channels):
                    if i > 0:
                        bt_label += ', '
                    bt_label += ch.name

            else:
                bt_label += '-'

        if is_bl_newer_than(2, 80):
            row.prop(btui, 'expand_content', text=bt_label, emboss=False, icon_value=icon_value)
        else: row.label(text=bt_label, icon_value=icon_value)

        if btui.expand_content:
            row = col.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            for letter in rgba_letters:
                draw_bake_target_channel(context, bcol, bt, letter)

        # Vertex color specific settings
        if bt.data_type == 'VCOL' and is_bl_newer_than(3, 2):
            crow = col.row(align=True)
            crow.label(text='', icon='BLANK1')
            crow.label(text='Domain:')
            crow.prop(bt, 'vcol_domain', expand=True)

            crow = col.row(align=True)
            crow.label(text='', icon='BLANK1')
            crow.label(text='Data Type:')
            crow.prop(bt, 'vcol_data_type', expand=True)

        # Channel specific settings
        for ch in channels:
            if ch.special_type == 'HEIGHT':
                has_height_channel = True
            if ch.special_type == 'NORMAL':
                has_normal_channel = True

        if has_height_channel:
            crow = col.row(align=True)
            crow.label(text='', icon='BLANK1')
            crow.label(text='Normalize Height:')
            crow.prop(bt, 'height_normalize', text='')

        if has_normal_channel:
            crow = col.row(align=True)
            crow.label(text='', icon='BLANK1')
            crow.label(text='Normal includes Height:')
            crow.prop(bt, 'normal_includes_height', text='')

        # Bake settings
        crow = col.row(align=True)

        icon = get_collapse_arrow_icon(btui.expand_bake_settings)

        label_setting = "Bake Settings:"
        if bt.bake_settings != 'GLOBAL':
            drow = crow.row(align=True)
            if is_bl_newer_than(2, 80):
                drow.alignment = 'LEFT'
                drow.scale_x = 0.85

            drow.prop(btui, 'expand_bake_settings', text='', emboss=False, icon=icon)
            if is_bl_newer_than(2, 80):
                drow.prop(btui, 'expand_bake_settings', text=label_setting, emboss=False)
            else: 
                drow.label(text=label_setting)
        else:
            crow.label(text='', icon='BLANK1')
            crow.label(text=label_setting)

        #if bt.data_type != 'VCOL':
        srow = crow.row(align=True)
        srow.alignment = 'RIGHT'
        srow.prop(bt, 'bake_settings', text='')

        if btui.expand_bake_settings and bt.bake_settings != 'GLOBAL':

            crow = col.row(align=True)
            crow.label(text='', icon='BLANK1')

            info_col = crow.column()
            if bt.data_type == 'VCOL':
                bbox = info_col.box()
                bcol = bbox.column()

                crow = bcol.row(align=True)
                crow.label(text='Force Bake All Polygons:')
                crow.prop(bt, 'force_bake_all_polygons', text='')

                crow = bcol.row(align=True)
                crow.label(text='Bake Disabled Layers:')
                crow.prop(bt, 'bake_disabled_layers', text='')
            else:
                draw_bake_target_settings(context, info_col, bt)

def draw_bake_target_settings(context, layout, bt):

    box = layout.box()
    bcol = box.column()

    BaseOperator.draw_base_bake_target_settings(context, bcol, bt, bt, 
        show_image_props = bt.data_type == 'IMAGE',
        show_vcol_props = bt.data_type == 'VCOL',
        show_udim = is_udim_supported()
    )

def draw_channel_bake_target_dropdown(context, channel, layout, draw_blank=True):
    yp = channel.id_data.yp

    bt = yp.bake_targets.get(channel.bake_target_name)
    bt_label = get_bake_target_label(bt)

    chbts = get_channel_bake_target_dict(yp)

    text = 'Active Bake Target:'
    icon_value = lib.get_icon('bake')
    expand_content = False
    if is_bl_newer_than(4, 1):
        header, panel = layout.panel("MAT_YP_ChannelActiveBakeTargetPanel", default_closed=True)
        split = split_layout(header, 0.45, align=False)
        split.label(text=text) #, icon_value=icon_value)
        if channel.name in chbts:
            split.menu("NODE_MT_y_channel_active_bake_target_menu", text=bt_label, icon_value=icon_value)
        else: split.operator('wm.y_new_channel_bake_target', text='Add New Bake Target', icon='ADD')

        if panel:
            expand_content = True
            bcol = panel.column(align=True)
    else:
        row = layout.row(align=True)
        rrow = row.row(align=True)
        rrow.alignment = 'LEFT'
        rrow.scale_x = 0.95

        icon = get_collapse_arrow_icon(ypui.expand_channel_bake_target_settings)
        rrow.prop(ypui, 'expand_channel_bake_target_settings', text='', emboss=False, icon=icon)

        expand_content = ypui.expand_channel_bake_target_settings

        if is_bl_newer_than(2, 80):
            rrow.prop(ypui, 'expand_channel_bake_target_settings', text=text, emboss=False) #, icon_value=icon_value)
        else: rrow.label(text=text) #, icon_value=icon_value)

        if channel.name in chbts:
            rrow = row.row(align=True)
            rrow.alignment = 'RIGHT'
            rrow.scale_x = 1.2
            rrow.menu("NODE_MT_y_channel_active_bake_target_menu", icon_value=icon_value, text=bt_label)

        else:
            rrow = row.row(align=True)
            rrow.alignment = 'RIGHT'
            rrow.scale_x = 1.2
            rrow.operator('wm.y_new_channel_bake_target', text='Add New Bake Target', icon='ADD')

        if expand_content:
            bcol = layout
            draw_blank = True
    
    if expand_content and bt:
        brow = bcol.row(align=True)
        if draw_blank: brow.label(text='', icon='BLANK1')
        draw_bake_target_settings(context, brow, bt)

        brow = bcol.row(align=True)
        if draw_blank: brow.label(text='', icon='BLANK1')
        op = brow.operator('wm.y_bake_single_target', text='Bake '+bt_label, icon_value=lib.get_icon('bake'))
        op.bake_target_index = get_bake_target_index(bt)

def draw_root_channels_ui(context, layout, node, show_header=False, rows=3):
    scene = bpy.context.scene
    obj = bpy.context.object
    engine = scene.render.engine
    mat = get_active_material()
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()

    channel = yp.channels[yp.active_channel_index] if len(yp.channels) > 0 and yp.active_channel_index < len(yp.channels) else None 

    #box = layout.box()
    box = layout
    col = box.column()

    if show_header:
        col.label(text='Channel Settings')

    row = col.row()

    rcol = row.column()

    rows = rows if rows >= 3 else 3
    rcol.template_list("NODE_UL_YPaint_channels", "", yp,
            "channels", yp, "active_channel_index", rows=rows, maxrows=5)  

    rcol = row.column(align=True)
    #rcol.context_pointer_set('node', node)

    if is_bl_newer_than(2, 80):
        rcol.menu("NODE_MT_y_new_channel_menu", text='', icon='ADD')
        #rcol.operator_menu_enum("wm.y_add_new_ypaint_channel", 'type', icon='ADD', text='')
        rcol.operator("wm.y_remove_ypaint_channel", icon='REMOVE', text='')
    else: 
        rcol.menu("NODE_MT_y_new_channel_menu", text='', icon='ZOOMIN')
        #rcol.operator_menu_enum("wm.y_add_new_ypaint_channel", 'type', icon='ZOOMIN', text='')
        rcol.operator("wm.y_remove_ypaint_channel", icon='ZOOMOUT', text='')

    rcol.operator("wm.y_move_ypaint_channel", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("wm.y_move_ypaint_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

    if len(yp.channels) > 0 and channel:

        mcol = col.column(align=False)

        mcol.context_pointer_set('channel', channel)

        chui = ypui.channel_ui

        # Check if channel output is connected or not
        inputs = node.inputs
        outputs = node.outputs
        output_index = get_output_index(channel)

        if group_tree.users == 1:

            # Optimize normal process button if normal input is disconnected
            root_height_ch = get_root_height_channel(yp)
            if root_height_ch:
                if is_height_input_unconnected_but_has_start_process(node, root_height_ch):
                    row = mcol.row(align=True)
                    row.alert = True
                    row.operator('wm.y_optimize_normal_process', icon='ERROR', text='Fix Height Process')
                elif is_height_input_connected_but_has_no_start_process(node, root_height_ch):
                    row = mcol.row(align=True)
                    row.alert = True
                    row.operator('wm.y_optimize_normal_process', icon='ERROR', text='Fix Height Input')

            if is_output_unconnected(node, channel) and not channel.disable_unconnected_warning:
                row = mcol.row(align=True)
                row.alert = True
                row.operator('wm.y_connect_ypaint_channel', icon='ERROR', text='Fix Unconnected Channel Output')

        icon_name = lib.channel_custom_icon_dict[channel.type]
        ch_icon_value = lib.get_icon(icon_name)
        text=channel.name + ' ' + pgettext_iface('Channel') + ' Settings'

        expand_content = False
        draw_blank = True

        if is_bl_newer_than(4, 1):
            header, panel = mcol.panel("MAT_YP_ActiveChannelSettingsPanel", default_closed=False)
            header.label(text=text, icon_value=ch_icon_value)

            if ypup.show_experimental:
                header.context_pointer_set('parent', channel)
                header.context_pointer_set('channel_ui', chui)
                header.menu("NODE_MT_y_channel_experimental_menu", icon='PREFERENCES', text='')

            if panel:
                expand_content = True
                bcol = panel.column(align=False)
        else:
            row = mcol.row(align=True)
            rrow = row.row(align=True)
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95

            icon = get_collapse_arrow_icon(ypui.expand_channel_settings)
            rrow.prop(ypui, 'expand_channel_settings', text='', emboss=False, icon=icon)

            if is_bl_newer_than(2, 80):
                rrow.prop(ypui, 'expand_channel_settings', text=text, emboss=False, icon_value=ch_icon_value)
            else: rrow.label(text=text, icon_value=ch_icon_value)

            if ypup.show_experimental:
                rrow = row.row(align=True)
                rrow.alignment = 'RIGHT'
                rrow.context_pointer_set('parent', channel)
                rrow.context_pointer_set('channel_ui', ypui)
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                rrow.menu("NODE_MT_y_channel_experimental_menu", icon=icon, text='')

            expand_content = ypui.expand_channel_settings
            if expand_content:
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')
                box = row.box()
                bcol = box.column()
                draw_blank = False

        if expand_content:

            is_alpha_channel = channel.type == 'VALUE' and channel.special_type == 'ALPHA'

            # Modifier stack ui will only active when use_baked is off
            baked = nodes.get(channel.baked)
            layout_active = not yp.use_baked or not baked

            draw_modifier_stack(context, channel, channel.type, bcol, chui, layout_active=layout_active, is_root_ch=True)

            inp = node.inputs.get(channel.name)

            special_type_available = True
            if channel.type == 'VALUE':
                height_ch_exists = any([c for c in yp.channels if c.special_type == 'HEIGHT' and c != channel])
                alpha_ch_exists = any([c for c in yp.channels if c.special_type == 'ALPHA' and c != channel])
                special_type_available = not height_ch_exists or ((channel.name == 'Alpha' or channel.special_type == 'ALPHA') and not alpha_ch_exists)
            elif channel.type == 'VECTOR':
                normal_ch_exists = any([c for c in yp.channels if c.special_type == 'NORMAL' and c != channel])
                # NOTE: Do not show vector displacement option for channel called normal to avoid confusion
                vdisp_ch_exists = any([c for c in yp.channels if c.special_type == 'VDISP' and c != channel]) if channel.name != 'Normal' else False
                special_type_available = not normal_ch_exists or not vdisp_ch_exists
            else:
                vdisp_ch_exists = any([c for c in yp.channels if c.special_type == 'VDISP' and c != channel])
                special_type_available = not vdisp_ch_exists

            # NOTE: Replaced by base layer
            #if ypup.layer_list_mode == 'CLASSIC' and channel.type in {'RGB', 'VALUE'}:
            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)

                #brow.label(text='', icon_value=lib.get_icon('input'))
                if draw_blank: brow.label(text='', icon='BLANK1')

                if channel.type == 'RGB':
                    brow.label(text='Background:')
                elif channel.type == 'VALUE':
                    brow.label(text='Base Value:')

                if not yp.use_baked or (channel.no_layer_using and len(inp.links) == 0):
                    brow.prop(inp,'default_value', text='')

                if yp.use_baked and not channel.no_layer_using:
                    brow.label(text='', icon_value=lib.get_icon('texture'))
                elif len(inp.links) > 0:
                    brow.label(text='', icon='LINKED')

                #if len(channel.modifiers) > 0:
                #    brow.label(text='', icon='BLANK1')

            # Special channel for other than main color channel
            if special_type_available and channel.name not in {'Color', 'Base Color', 'Albedo'}:
                brow = bcol.row(align=True)
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Special Type:')

                rna_property = channel.bl_rna.properties['special_type']
                enum_item = rna_property.enum_items[channel.special_type]
                label = enum_item.name
                brow.menu("NODE_MT_y_channel_special_type_menu", text=label)

            # Alpha is no longer available to access without developer mode 
            if ypup.developer_mode or channel.enable_alpha:
                brow = bcol.row() #align=True)

                rrow = brow.row(align=True)
                if channel.enable_alpha and not chui.expand_alpha_settings:
                    inp_alpha = node.inputs.get(channel.name + io_suffix['ALPHA'])
                    inbox_dropdown_button(rrow, chui, 'expand_alpha_settings', 'Base Alpha:')

                    if is_bl_newer_than(2, 80):
                        rrow = brow.row(align=True) # To make sure next row is aligned right
                        rrow.alignment = 'RIGHT'

                    if len(inp_alpha.links) == 0:
                        if not yp.use_baked:
                            brow.prop(inp_alpha, 'default_value', text='')
                    else: brow.label(text='', icon='LINKED')
                else: 
                    inbox_dropdown_button(rrow, chui, 'expand_alpha_settings', 'Alpha:')

                    if is_bl_newer_than(2, 80):
                        rrow = brow.row(align=True) # To make sure next row is aligned right
                        rrow.alignment = 'RIGHT'

                if not yp.use_baked:
                    brow.prop(channel, 'enable_alpha', text='')
                else: brow.label(text='', icon_value=lib.get_icon('texture'))

                if chui.expand_alpha_settings:
                    brow = bcol.row(align=True)
                    if draw_blank: brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)
                    bbcol.active = channel.enable_alpha

                    if channel.enable_alpha:
                        inp_alpha = node.inputs.get(channel.name + io_suffix['ALPHA'])
                        brow = bbcol.row(align=True)
                        brow.label(text='Base Alpha:')
                        if len(inp_alpha.links)==0:
                            if not yp.use_baked:
                                brow.prop(inp_alpha, 'default_value', text='')
                        else: brow.label(text='', icon='LINKED')

                    if is_bl_newer_than(2, 80) and engine != 'HYDRA_STORM':

                        if is_bl_newer_than(4, 2):
                            brow = bbcol.row(align=True)
                            brow.label(text='Transparent Shadows:')
                            brow.prop(mat, 'use_transparent_shadow', text='')
                            brow = bbcol.row(align=True)
                            brow.label(text='Jittered Shadows (Global):')
                            brow.prop(scene.eevee, 'use_shadow_jitter_viewport', text='')
                            brow = bbcol.row(align=True)
                            brow.label(text='Render Method:')
                            brow.prop(mat, 'surface_render_method', text='')
                        else:
                            brow = bbcol.row(align=True)
                            brow.label(text='Blend Mode:')
                            brow.prop(channel, 'alpha_blend_mode', text='')

                            brow = bbcol.row(align=True)
                            brow.label(text='Shadow Mode:')
                            brow.prop(channel, 'alpha_shadow_mode', text='')

                        if channel.alpha_blend_mode == 'CLIP' or channel.alpha_shadow_mode == 'CLIP':
                            brow = bbcol.row(align=True)
                            brow.label(text='Clip Threshold:')
                            brow.prop(mat, 'alpha_threshold', text='')

                    brow = bbcol.row(align=True)
                    brow.active = not (yp.use_baked and yp.enable_baked_outside)
                    brow.label(text='Backface Mode:')
                    brow.prop(channel, 'backface_mode', text='')

                    #bbcol.separator()

            if channel.special_type == 'HEIGHT':
                # Check for normal channel
                normal_ch = get_root_normal_channel(yp)

                if ypup.developer_mode:
                    brow = bcol.row(align=True)
                    brow.active = normal_ch != None
                    if draw_blank: brow.label(text='', icon='BLANK1')
                    brow.label(text='Use as Bump Only:')
                    brow.prop(channel, 'use_height_as_bump', text='')

                brow = bcol.row(align=True)
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Normalize Input Output:')
                if yp.use_baked and not channel.no_layer_using:
                    brow.label(text='', icon_value=lib.get_icon('texture'))
                else: brow.prop(channel, 'use_height_normalize', text='')

            if channel.special_type in {'HEIGHT', 'VDISP'}:
                brow = bcol.row(align=True)
                #brow.active = normal_ch != None
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Displacement Setup:')
                bbrow = brow.row(align=True)
                bbrow.alignment = 'RIGHT'

                # Displacement enabled label
                displacement_enabled = get_displacement_method() != 'BUMP'
                if channel.special_type == 'HEIGHT':
                    displacement_enabled = displacement_enabled and not channel.use_height_as_bump
                label = 'Enabled' if displacement_enabled else 'Disabled'
                bbrow.label(text=label)

                brow = bcol.row(align=True)
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.operator("wm.y_quick_displacement_setup", text='Quick Displacement Setup', icon='MOD_SUBSURF')
                brow.operator("wm.y_remove_displacement_setup", text='', icon='CANCEL')

            if is_alpha_channel:
                brow = bcol.row(align=True)
                brow.active = not yp.use_baked or channel.no_layer_using
                #brow.label(text='', icon_value=lib.get_icon('input'))
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Channel Pair:')
                brow.prop_search(channel, "alpha_pair_name", yp, "channels", text='')

                brow = bcol.row(align=True)
                brow.active = not (yp.use_baked and yp.enable_baked_outside)
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Backface Mode:')
                brow.prop(channel, 'backface_mode', text='')

                # NOTE: Combine to baked color is replaced with bake target settings
                #brow = bcol.row(align=True)
                #brow.active = not yp.use_baked
                #if draw_blank: brow.label(text='', icon='BLANK1')
                #brow.label(text='Combine to Baked Color:')
                #if yp.use_baked:
                #    brow.label(text='', icon_value=lib.get_icon('texture'))
                #else: brow.prop(channel, 'alpha_combine_to_baked_color', text='')

            if channel.type in {'RGB', 'VALUE'} and channel.special_type == 'NONE':
                brow = bcol.row(align=True)
                brow.active = not yp.use_baked or channel.no_layer_using
                #brow.label(text='', icon_value=lib.get_icon('input'))
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.label(text='Use Clamp:')
                brow.prop(channel, 'use_clamp', text='')

            #if len(channel.modifiers) > 0:
            #    brow.label(text='', icon='BLANK1')

            if channel.special_type == 'NORMAL':
                brow = bcol.row(align=True)
                #brow.active = not (yp.use_baked and yp.enable_baked_outside)

                if draw_blank: brow.label(text='', icon='BLANK1')
                #brow.label(text='Normal channel has no settings!', icon='INFO')
                brow.label(text='Main UV:')
                brow.prop_search(channel, "main_uv", context.object.data, "uv_layers", text='', icon='GROUP_UVS')

            if channel.type in {'RGB', 'VALUE'} and not is_alpha_channel:

                if channel.special_type == 'NONE':
                    brow = bcol.row(align=True)
                    #brow.label(text='', icon_value=lib.get_icon('input'))
                    if draw_blank: brow.label(text='', icon='BLANK1')

                    split = split_layout(brow, 0.375, align=True)

                    split.label(text='Space:')
                    split.prop(channel, 'colorspace', text='')

            if channel.special_type == 'VDISP' and is_bl_newer_than(3, 2):
                #bcol.separator()
                brow = bcol.row(align=True)
                if draw_blank: brow.label(text='', icon='BLANK1')
                brow.operator('object.y_remove_vdm_and_add_multires', text="Apply VDM layers to Multires", icon='SCULPTMODE_HLT')

            bt = yp.bake_targets.get(channel.bake_target_name)
            bt_label = get_bake_target_label(bt)
            icon_value = lib.get_icon('bake')

            chbts = get_channel_bake_target_dict(yp)
            valid_bts_exist = channel.name in chbts and len(chbts[channel.name]) > 0

            brow = bcol.row(align=True)
            if draw_blank: brow.label(text='', icon='BLANK1')
            split = split_layout(brow, 0.375, align=False)
            label = 'Bake Target:'
            #if not bt or not valid_bts_exist:
            #    label += ' -'
            split.label(text=label)

            if bt and valid_bts_exist:
                icon_value = lib.get_icon('image') if bt.data_type == 'IMAGE' else lib.get_icon('vertex_color')
                srow = split.row(align=True)
                srow.menu("NODE_MT_y_channel_active_bake_target_menu", icon_value=icon_value, text=bt_label)
            else:

                if valid_bts_exist:
                    split.menu("NODE_MT_y_channel_active_bake_target_menu", icon_value=icon_value, text=bt_label)
                else: 
                    split.alert = True
                    split.operator('wm.y_new_channel_bake_target', text='Add New Bake Target', icon='ADD')

        #draw_channel_bake_target_dropdown(context, channel, mcol, draw_blank)

def draw_base_layer_ui(context, layout, yp, node):
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()

    row = layout.row(align=True)
    rrow = row.row(align=True)
    rrow.alignment = 'LEFT'
    rrow.scale_x = 0.95
    label = 'Channel Base Values'
    icon_value = lib.get_icon('channels')

    icon = get_collapse_arrow_icon(ypui.expand_channel_base_values)
    rrow.prop(ypui, 'expand_channel_base_values', text='', emboss=False, icon=icon)
    if is_bl_newer_than(2, 80):
        rrow.prop(ypui, 'expand_channel_base_values', text=label, emboss=False, icon_value=icon_value)
    else: rrow.label(text=label, icon_value=icon_value)

    if ypui.expand_channel_base_values:
        rrow = layout.row(align=True)
        rrow.label(text='', icon='BLANK1')
        rcol = rrow.column(align=True)

        inputs = node.inputs
        outputs = node.outputs
        ypup = get_user_preferences()
        tree = node.node_tree

        for root_ch in yp.channels:

            input_index = root_ch.io_index

            rcrow = rcol.row()

            icon_value = lib.get_icon(lib.channel_custom_icon_dict[root_ch.type])
            rcrow.label(text=root_ch.name, icon_value=icon_value)

            if root_ch.type == 'RGB':
                rcrow = rcrow.row(align=True)

            if len(inputs[input_index].links) > 0:
                rcrow.label(text='', icon='LINKED')

            # NOTE: Always show the base values because it will affect the bake result
            if root_ch.type == 'VALUE':
                rcrow.prop(inputs[input_index], 'default_value', text='') #, emboss=False)
            elif root_ch.type == 'RGB':
                rcrow.prop(inputs[input_index], 'default_value', text='', icon='COLOR')

            #output_index = get_output_index(root_ch)
            #if is_output_unconnected(node, output_index, root_ch):
            #    rcrow.label(text='', icon='ERROR')

            if ypup.developer_mode and root_ch.type=='RGB' and root_ch.enable_alpha:
                if len(inputs[input_index + 1].links) == 0:
                    rcrow.prop(inputs[input_index + 1], 'default_value', text='')
                else: row.label(text='', icon='LINKED')

def draw_layer_source(context, layout, layer, layer_tree, source, image, vcol, is_a_mesh):
    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    scene = context.scene
    ypup = get_user_preferences()

    row = layout.row(align=True)
    rrow = row.row(align=True)
    rrow.alignment = 'LEFT'
    rrow.scale_x = 0.95
    label = ''
    #label += pgettext_iface('Layer') + ': '
    if image:
        icon_value = lib.get_icon('image')
        if image.yia.is_image_atlas or image.yua.is_udim_atlas:
            label += layer.name
        else: label += image.name
    elif vcol:
        icon_value = lib.get_icon('vertex_color')
        label += vcol.name
    elif layer.type == 'BACKGROUND':
        icon_value = lib.get_icon('background')
        label += layer.name
    elif layer.type == 'COLOR':
        icon_value = lib.get_icon('color')
        label += layer.name
    elif layer.type == 'GROUP':
        icon_value = lib.get_icon('group')
        label += layer.name
    elif layer.type == 'HEMI':
        icon_value = lib.get_icon('hemi')
        label += layer.name
    elif layer.type in {'EDGE_DETECT', 'AO'}:
        icon_value = lib.get_icon('edge_detect')
        label += layer.name
    elif layer.type == 'PREV_LAYERS':
        icon_value = lib.get_icon('COLLAPSEMENU')
        label += layer.name
    elif layer.type == 'INPUT_BUNDLE':
        icon_value = lib.get_icon('NODE_SOCKET_BUNDLE')
        label += layer.name
    else:
        icon_value = lib.get_icon('texture')
        label += layer.name

    icon = get_collapse_arrow_icon(lui.expand_content)
    rrow.prop(lui, 'expand_content', text='', emboss=False, icon=icon)
    if is_bl_newer_than(2, 80):
        rrow.prop(lui, 'expand_content', text=label, emboss=False, icon_value=icon_value)
    else: rrow.label(text=label, icon_value=icon_value)

    row.context_pointer_set('parent', layer)
    row.context_pointer_set('layer', layer)
    row.context_pointer_set('layer_ui', lui)

    if layer.type not in {'GROUP', 'PREFERENCES'}:
        #icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        icon = 'MODIFIER_ON' if is_bl_newer_than(2, 80) else 'MODIFIER'
        rrow = row.row()
        rrow.alignment = 'RIGHT'
        rrow.menu("NODE_MT_y_layer_special_menu", icon=icon, text='')

    #if layer.type == 'GROUP': return
    #if layer.type in {'VCOL', 'BACKGROUND'} and len(layer.modifiers) == 0: return
    #if layer.type in {'BACKGROUND'} and len(layer.modifiers) == 0: return
    if not lui.expand_content: return

    rrow = layout.row(align=True)
    rrow.label(text='', icon='BLANK1')
    rbox = rrow.box()
    rcol = rbox.column(align=False)

    modcol = rcol.column()
    modcol.active = layer.type not in {'BACKGROUND', 'GROUP'}
    draw_modifier_stack(context, layer, 'RGB', modcol, lui, layer)

    #if layer.type not in {'VCOL', 'BACKGROUND'}:
    #if layer.type not in {'BACKGROUND'}:
    row = rcol.row(align=True)

    if layer.type == 'IMAGE':
        suffix = 'image'
    elif layer.type == 'COLOR':
        suffix = 'color'
    elif layer.type == 'HEMI':
        suffix = 'hemi'
    elif layer.type in {'EDGE_DETECT', 'AO'}:
        suffix = 'edge_detect'
    elif layer.type == 'VCOL':
        suffix = 'vertex_color'
    else: suffix = 'texture'

    split = split_layout(row, 0.45, align=False)
    label_text = pgettext_iface('Layer') + ' Source:'

    rrow = split.row(align=True)
    if layer.type in {'BACKGROUND', 'GROUP', 'PREV_LAYERS'}:
        rrow.label(text='', icon='BLANK1')
        rrow.label(text=label_text)
    else:
        inbox_dropdown_button(rrow, lui, 'expand_source', label_text)

    menu_label = ''
    if image:
        image_name = image.name
        if image.y_bake_info.is_baked:
            image_name += ' (Baked)'
        menu_label = image_name
        icon_value = lib.get_icon('image')
    elif vcol:
        menu_label = vcol.name
        icon_value = lib.get_icon('vertex_color')
    else: 
        menu_label = layer_type_labels[layer.type]
        if layer.type == 'COLOR':
            icon_value = lib.get_icon('color')
        elif layer.type == 'BACKGROUND':
            icon_value = lib.get_icon('background')
        elif layer.type == 'GROUP':
            icon_value = lib.get_icon('group')
        elif layer.type == 'HEMI':
            icon_value = lib.get_icon('hemi')
        elif layer.type in {'EDGE_DETECT', 'AO'}:
            icon_value = lib.get_icon('edge_detect')
        elif layer.type == 'PREV_LAYERS':
            menu_label = 'Adjustment (Previous Layers)'
            icon_value = lib.get_icon('COLLAPSEMENU')
        elif layer.type == 'INPUT_BUNDLE':
            icon_value = lib.get_icon('NODE_SOCKET_BUNDLE')
        else: icon_value = lib.get_icon('texture')

    #if layer.type == 'COLOR' and not lui.expand_source:
    #    ssplit = split_layout(split, 0.6, align=True)
    #    ssplit.menu("NODE_MT_y_layer_type_menu", text=menu_label, icon_value=icon_value)
    #    ssplit.prop(source.outputs[0], 'default_value', text='')
    #else:
    split.menu("NODE_MT_y_layer_type_menu", text=menu_label, icon_value=icon_value)

    if lui.expand_source and layer.type not in {'BACKGROUND', 'GROUP', 'PREV_LAYERS'}:
        row = rcol.row(align=True)
        row.label(text='', icon='BLANK1')
        #bbox = row.box()
        rrcol = row.column()

        ccol = rrcol.column()
        ccol.active = not layer.use_baked

        if image:
            draw_image_props(context, source, ccol, layer, show_flip_y=True, show_datablock=False)

            # NOTE: Divide rgb by alpha is mostly useless for image layer, 
            # so it's hidden under experimental feature unless the user ever enabled it before
            if hasattr(layer, 'divide_rgb_by_alpha') and (layer.divide_rgb_by_alpha or ypup.show_experimental):
                rrrow = ccol.row(align=True)
                rrrow.label(text='Divide RGB by Alpha:')
                rrrow.prop(layer, 'divide_rgb_by_alpha', text='')

        elif layer.type == 'COLOR':
            draw_solid_color_props(layer, source, ccol)
        elif layer.type == 'VCOL':
            draw_vcol_props(ccol, vcol, layer)
        elif layer.type == 'HEMI':
            draw_hemi_props(layer, source, ccol)
        elif layer.type == 'EDGE_DETECT':
            draw_edge_detect_props(layer, source, ccol, layer=layer)
        elif layer.type == 'AO':
            draw_ao_props(layer, source, ccol, layer=layer)
        elif layer.type == 'INPUT_BUNDLE':
            draw_input_bundle_props(layer, source, ccol)
        else: draw_tex_props(source, ccol, entity=layer)

        if layer.baked_source == '' and layer.type in {'EDGE_DETECT', 'HEMI', 'AO'}:
            rrrow = rrcol.row(align=True)
            rrrow.operator("wm.y_bake_entity_to_image", text='Bake '+mask_type_labels[layer.type]+' as Image', icon_value=lib.get_icon('bake'))

        elif layer.baked_source != '':

            stree = get_source_tree(layer)
            baked_source = stree.nodes.get(layer.baked_source)
            if baked_source and baked_source.image:
                brow = rrcol.row(align=True)
                brow.active = layer.use_baked
                brow.label(text='Baked: ')
                crow = brow.row(align=True)
                crow.alignment = 'RIGHT'
                crow.label(text=baked_source.image.name, icon='IMAGE_DATA')

            rrcol.context_pointer_set('entity', layer)
            rrcol.context_pointer_set('layer', layer)
            brow = rrcol.row(align=True)
            brow.operator("wm.y_bake_entity_to_image", text='Rebake', icon_value=lib.get_icon('bake'))
            brow.prop(layer, 'use_baked', text='Use Baked', toggle=True)

            icon = 'TRASH' if is_bl_newer_than(2, 80) else 'X'
            brow.operator("wm.y_remove_baked_entity", text='', icon=icon)

    layout.separator()

def draw_layer_vector(context, layout, layer, layer_tree, source, image, vcol, is_a_mesh):

    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    scene = context.scene

    # Vector
    if is_layer_using_vector(layer, exclude_baked=True):

        col = layout.column()
        col.active = not layer.use_baked

        row = col.row(align=False)

        icon_value = lib.get_icon('uv')
        rrow = row.row(align=True)
        icon = get_collapse_arrow_icon(lui.expand_vector)
        label = 'Mapping'
        if not lui.expand_vector: label += ':'
        rrow.prop(lui, 'expand_vector', text='', emboss=False, icon=icon)
        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(lui, 'expand_vector', text=label, emboss=False, icon_value=icon_value)
        else: rrow.label(text=label, icon_value=icon_value)

        texcoord = layer_tree.nodes.get(layer.texcoord)

        rrow = row.row(align=True)
        rrow.alignment = 'RIGHT'
        if not lui.expand_vector:
            if is_a_mesh and layer.texcoord_type == 'UV':
                rrow.scale_x = 0.5
                split = split_layout(rrow, 0.33, align=True)
                split.prop(layer, 'texcoord_type', text='')
                split.prop_search(layer, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            elif layer.type == 'IMAGE' and layer.texcoord_type in {'Generated', 'Object'} and not lui.expand_vector:
                rrow.scale_x = 0.5
                split = split_layout(rrow, 0.5, align=True)
                split.prop(layer, 'texcoord_type', text='')
                split.prop(layer, 'projection_blend', text='')
            elif layer.texcoord_type == 'Decal' and not lui.expand_vector:
                if texcoord:
                    rrow.scale_x = 0.5
                    split = split_layout(rrow, 0.4, align=True)
                    split.prop(layer, 'texcoord_type', text='')
                    split.prop(texcoord, 'object', text='')
            else:
                rrow.prop(layer, 'texcoord_type', text='')

        #if layer.texcoord_type == 'UV':
        #    icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        #    rrow.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')

        if lui.expand_vector:
            row = col.row(align=True)
            row.label(text='', icon='BLANK1')
            bbox = row.box()
            boxcol = bbox.column()

            rrow = boxcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            rrow.label(text='Coordinate:')
            rrow.prop(layer, 'texcoord_type', text='')

            is_using_image_atlas = image and (image.yia.is_image_atlas or image.yua.is_udim_atlas)

            if is_a_mesh and layer.texcoord_type == 'UV':
                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rrow.label(text='UV Map:')
                rrrow = rrow.row(align=True)
                rrrow.scale_x = 1.2
                rrrow.prop_search(layer, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                rrow.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')

            if layer.type == 'IMAGE' and layer.texcoord_type in {'Generated', 'Object'}:
                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                splits = split_layout(rrow, 0.5, align=True)
                splits.label(text='Projection Blend:')
                splits.prop(layer, 'projection_blend', text='')

            if layer.texcoord_type == 'Decal':

                if texcoord:
                    rrow = boxcol.row(align=True)
                    rrow.label(text='', icon='BLANK1')
                    splits = split_layout(rrow, 0.45, align=True)
                    splits.label(text='Decal Object:')
                    splits.prop(texcoord, 'object', text='')

                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                splits = split_layout(rrow, 0.5, align=True)
                splits.label(text='Decal Distance:')
                draw_input_prop(splits, layer, 'decal_distance_value', layer=layer)

                if texcoord and texcoord.object:

                    rrow = boxcol.row(align=True)
                    rrow.label(text='', icon='BLANK1')
                    rrrow = rrow.row()
                    rrrow.label(text='Decal Constraint:')
                    draw_input_prop(rrrow, texcoord.object.yp_decal, 'enable_shrinkwrap')

                    # NOTE: Show constraint target when there's more than one material users
                    decal_const = Decal.get_decal_shrinkwrap_constraint(texcoord.object)
                    if decal_const:
                        mat = get_active_material()
                        if mat.users > 1 or decal_const.target == None:
                            rrow = boxcol.row(align=True)
                            rrow.label(text='', icon='BLANK1')
                            rrrow = rrow.row()
                            rrrow.label(text='Constraint Target:')
                            draw_input_prop(rrrow, decal_const, 'target')

                boxcol.context_pointer_set('entity', layer)
                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                if is_bl_newer_than(2, 80):
                    rrow.operator('wm.y_select_decal_object', icon='EMPTY_SINGLE_ARROW')
                else: rrow.operator('wm.y_select_decal_object', icon='EMPTY_DATA')

                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rrow.operator('wm.y_set_decal_object_position_to_sursor', text='Set Position to Cursor', icon='CURSOR')
                
            if layer.texcoord_type != 'Decal' and not is_using_image_atlas:
                mapping = get_layer_mapping(layer)

                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rrow.label(text='Transform:')
                rrow.prop(mapping, 'vector_type', text='')

                rrow = boxcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rrow = rrow.row()
                if is_bl_newer_than(2, 81):
                    mcol = rrow.column()
                    mcol.prop(mapping.inputs[1], 'default_value', text='Offset')
                    mcol = rrow.column()
                    mcol.prop(mapping.inputs[2], 'default_value', text='Rotation')
                    if layer.enable_uniform_scale:
                        mcol = rrow.column(align=True)
                        mrow = mcol.row()
                        mrow.label(text='Scale:')
                        mrow.prop(layer, 'enable_uniform_scale', text='', icon='LOCKED')
                        draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'X', layer=layer)
                        draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'Y', layer=layer)
                        draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'Z', layer=layer)
                    else:
                        mcol = rrow.column(align=True)
                        mrow = mcol.row()
                        mrow.label(text='Scale:')
                        mrow.prop(layer, 'enable_uniform_scale', text='', icon='UNLOCKED')
                        mcol.prop(mapping.inputs[3], 'default_value', text='')
                else:
                    mcol = rrow.column()
                    mcol.prop(mapping, 'translation')
                    mcol = rrow.column()
                    mcol.prop(mapping, 'rotation')
                    mcol = rrow.column()
                    mcol.prop(mapping, 'scale')
            
                if yp.need_temp_uv_refresh:
                    rrow = boxcol.row(align=True)
                    rrow.label(text='', icon='BLANK1')
                    rrow.alert = True
                    rrow.operator('wm.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

            # Blur row
            rrow = boxcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            splits = split_layout(rrow, 0.5)
            splits.label(text='Blur:')
            if layer.enable_blur_vector:
                draw_input_prop(splits, layer, 'blur_vector_factor', layer=layer)
            rrow.prop(layer, 'enable_blur_vector', text='')

            layout.separator()

def get_layer_channel_input_label(layer, ch, source=None, secondary_input=False):
    yp = layer.id_data.yp

    color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)
    override = ch.override if not secondary_input else ch.override_1
    override_type = ch.override_type if not secondary_input else ch.override_1_type

    if override:
        if not source: source = get_channel_source(ch, layer)
        label = 'Custom'
        if override_type == 'IMAGE' and source and source.image:
            label = source.image.name
        elif override_type == 'VCOL' and source:
            label = source.attribute_name
        elif override_type != 'DEFAULT':
            label = channel_override_labels[override_type]
    elif layer.type in {'GROUP', 'PREV_LAYERS'}:
        root_ch = yp.channels[get_layer_channel_index(layer, ch)]
        label = 'Group ' if layer.type == 'GROUP' else 'Previous '
        label += root_ch.name
    else:
        label = 'Layer'

        if ch == alpha_ch and color_ch.enable and not color_ch.unpair_alpha:
            if not color_ch.override and color_ch.socket_input_name == 'Alpha':
                label = 'Solid Value (1.0)'
            else: label += ' Alpha'
        else: label += ' ' + get_channel_input_socket_name(layer, ch, secondary_input=secondary_input)

    return label

def draw_layer_channels(context, layout, layer, layer_tree, image, specific_ch):
    #T = time.time()

    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()
    lui = ypui.layer_ui
    
    # Get channel pairs
    color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)
    normal_ch, height_ch = get_layer_normal_height_ch_pairs(layer)

    enabled_channels = [c for c in layer.channels if c.enable or (c == alpha_ch and color_ch.enable)]

    root_ch = None
    ch = None

    if not specific_ch:

        label = pgettext_iface('Channel')
        if len(enabled_channels) == 0:
            #label += ' (0)'
            pass
        elif color_ch and color_ch.enable and len(enabled_channels) == 2:
            if lui.expand_channels:
                label = pgettext_iface('Channels') + ' (2)'
            else:
                ch = color_ch
                ch_idx = get_layer_channel_index(layer, ch)
                root_ch = yp.channels[ch_idx]
                if is_bl_newer_than(2, 80):
                    label += ' (' + root_ch.name + ')'
                else: label = root_ch.name + ' ' + pgettext_iface('Channel')   
        elif len(enabled_channels) == 1:
            if lui.expand_channels:
                label += ' (1)'
            else:
                ch = enabled_channels[0]
                ch_idx = get_layer_channel_index(layer, ch)
                root_ch = yp.channels[ch_idx]
                #label = root_ch.name
                if root_ch.special_type == 'VDISP' and layer.type != 'GROUP':
                    if is_bl_newer_than(2, 80):
                        label += ' (VDM)'
                    else: label = 'VDM'
                else:
                    if is_bl_newer_than(2, 80):
                        label += ' (' + root_ch.name + ')'
                    else: label = root_ch.name + ' ' + pgettext_iface('Channel')   

        else:
            label = pgettext_iface('Channels') + ' (' + str(len(enabled_channels)) + ')'

        if not lui.expand_channels and len(enabled_channels) == 1:
            label += ':'
        
        row = layout.row(align=False)
        rrow = row.row(align=True)
        icon_value = lib.get_icon('channels')
        icon = get_collapse_arrow_icon(lui.expand_channels)
        rrow.prop(lui, 'expand_channels', text='', emboss=False, icon=icon)
        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(lui, 'expand_channels', text=label, emboss=False, icon_value=icon_value)
        else: rrow.label(text=label, icon_value=icon_value)

        if ch and root_ch:
            rrow = row.row(align=True)
            rrow.alignment = 'RIGHT'
            if ch == height_ch and height_ch.use_height_as_normal:
                splits = split_layout(rrow, 0.5, align=True)
                splits.prop(normal_ch, 'normal_blend_type', text='')
                draw_input_prop(splits, ch, 'bump_distance', layer=layer)
            elif root_ch.special_type == 'NORMAL' and layer.type != 'GROUP':
                splits = split_layout(rrow, 0.5, align=True)
                splits.prop(ch, 'normal_blend_type', text='')
                draw_input_prop(splits, ch, 'normal_strength', layer=layer)
            elif root_ch.special_type == 'HEIGHT' and layer.type != 'GROUP':
                splits = split_layout(rrow, 0.5, align=True)
                splits.prop(ch, 'height_blend_type', text='')
                draw_input_prop(splits, ch, 'bump_distance', layer=layer)
            elif root_ch.special_type == 'VDISP':
                splits = split_layout(rrow, 0.5, align=True)
                splits.prop(ch, 'blend_type', text='')
                draw_input_prop(splits, ch, 'vdisp_strength', layer=layer)
            else: 
                rrow.scale_x = 1.25
                rrow.prop(ch, 'blend_type', text='')

        if not lui.expand_channels:
            return

        rrow = row.row(align=True)
        rrow.alignment = 'RIGHT'
        rrow.prop(ypui, 'expand_channels', text='', emboss=True, icon_value = lib.get_icon('checkbox'))

    rrow = layout.row(align=True)
    if not specific_ch:
        rrow.label(text='', icon='BLANK1')
    rcol = rrow.column(align=False)

    if len(layer.channels) == 0:
        rcol.label(text='No channel found!', icon='ERROR')

    # Check if theres any mask bump
    bump_ch_found = True if get_transition_bump_channel(layer) else False
    showed_bump_ch_found = True if get_showed_transition_bump_channel(layer) else False

    ch_count = 0
    extra_separator = False
    for i, ch in enumerate(layer.channels):

        ch_enabled = ch.enable or (alpha_ch == ch and color_ch.enable)

        if not ypui.expand_channels and not ch_enabled:
            continue

        if specific_ch and ch != specific_ch:
            continue

        # Hide normal channel if 'Use height as normal' is enabled
        if ch == normal_ch and height_ch.enable and height_ch.use_height_as_normal:
            continue

        root_ch = yp.channels[i]
        ch_count += 1

        try: chui = ypui.layer_ui.channels[i]
        except: 
            ypui.need_update = True
            return

        ccol = rcol.column()
        ccol.active = ch.enable or (alpha_ch == ch and color_ch.enable)
        ccol.context_pointer_set('channel', ch)

        row = ccol.row(align=True)

        if layer.type in {'GROUP', 'PREV_LAYERS'}:
            row.active = get_channel_enabled(ch, layer, root_ch)

        if not chui.expand_content: # and ch.enable:
            split = split_layout(row, 0.35)
            rrow = split.row(align=True)
        else: rrow = row.row(align=True)

        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95

        label = ''
        alt_ch_for_icon = None
        if ch == height_ch and height_ch.use_height_as_normal:
            root_normal_ch, root_height_ch = get_normal_height_ch_pairs(yp)
            alt_ch_for_icon = root_normal_ch
            label = root_normal_ch.name+' from '+root_height_ch.name
        else: label += yp.channels[i].name
        intensity_value = get_entity_prop_value(ch, 'intensity_value', layer=layer, 
            path='.channels['+str(i)+'].intensity_value') # NOTE: Manual path passing is for optimization
        if intensity_value != 1.0 and layer.type != 'GROUP':
            label += ' (%.1f)' % intensity_value
        if not chui.expand_content:
            label += ':'

        if alt_ch_for_icon != None:
            icon_name = lib.channel_custom_icon_dict[alt_ch_for_icon.type]
        else: icon_name = lib.channel_custom_icon_dict[root_ch.type]
        channel_icon_value = lib.get_icon(icon_name)

        icon = get_collapse_arrow_icon(chui.expand_content)
        rrow.prop(chui, 'expand_content', text='', emboss=False, icon=icon)

        if is_bl_newer_than(2, 80):
            rrow.prop(chui, 'expand_content', text=label, emboss=False, icon_value=channel_icon_value, translate=False)
        else: rrow.label(text=label, icon_value=channel_icon_value, translate=False)

        # Alpha channel with color channel enabled will not show blend and opacity options
        show_blend_opacity = alpha_ch != ch or (alpha_ch == ch and (not get_channel_enabled(color_ch) or color_ch.unpair_alpha))

        #if layer.type != 'BACKGROUND':
        if not chui.expand_content: # and ch.enable:
            rrow = split.row(align=True)
            rrow.context_pointer_set('parent', ch)

            if show_blend_opacity:

                ssplit = split_layout(rrow, 0.4, align=True)
                
                if ch == height_ch and height_ch.use_height_as_normal:
                    label = normal_blend_labels[normal_ch.normal_blend_type] + ' ' + '%.1f' % intensity_value
                    ssplit.prop(normal_ch, 'normal_blend_type', text='')
                elif root_ch.special_type == 'NORMAL':
                    label = normal_blend_labels[ch.normal_blend_type] + ' ' + '%.1f' % intensity_value
                    ssplit.prop(ch, 'normal_blend_type', text='')
                elif root_ch.special_type == 'HEIGHT':
                    label = blend_type_labels[ch.height_blend_type] + ' ' + '%.1f' % intensity_value
                    ssplit.prop(ch, 'height_blend_type', text='')
                elif layer.type != 'BACKGROUND': 
                    label = blend_type_labels[ch.blend_type] + ' ' + '%.1f' % intensity_value
                    ssplit.prop(ch, 'blend_type', text='')
                else:
                    draw_input_prop(ssplit, ch, 'intensity_value', layer=layer)
            else:
                ssplit = rrow.row(align=True)

            if layer.type in {'GROUP', 'PREV_LAYERS'}:
                rrrow = ssplit.row(align=True)
                draw_input_prop(rrrow, ch, 'intensity_value', layer=layer)

            elif root_ch.special_type == 'HEIGHT':
                rrrow = ssplit.row(align=True)

                draw_input_prop(rrrow, ch, 'bump_distance', layer=layer)

                if ch.override and ch.override_type == 'DEFAULT':
                    draw_input_prop(rrrow, ch, 'override_value', layer=layer)

                rrrow.menu("NODE_MT_y_layer_channel_input_menu", text='', icon='DOWNARROW_HLT')

                if ch.enable and ch.override:
                    if ch.override_type == 'IMAGE':
                        rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('image'))
                    elif ch.override_type == 'VCOL':
                        rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color'))
                    elif ch.override_type != 'DEFAULT':
                        rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('texture'))

            elif root_ch.special_type == 'VDISP':
                rrrow = ssplit.row(align=True)
                draw_input_prop(rrrow, ch, 'vdisp_strength', layer=layer)

            elif ch.override:
                rrrow = ssplit.row(align=True)

                if ch.override_type == 'DEFAULT':
                    if root_ch.type == 'VALUE':
                        draw_input_prop(rrrow, ch, 'override_value', layer=layer)
                    else: draw_input_prop(rrrow, ch, 'override_color', layer=layer)
                    rrrow.menu("NODE_MT_y_layer_channel_input_menu", text='', icon='DOWNARROW_HLT')
                else:
                    label = get_layer_channel_input_label(layer, ch)
                    rrrow.menu("NODE_MT_y_layer_channel_input_menu", text=label)

                    #if ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
                    if ch.enable or ch == alpha_ch and color_ch.enable:
                        if ch.override_type == 'IMAGE':
                            rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('image'))
                        elif ch.override_type == 'VCOL':
                            rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color'))
                        elif ch.override_type != 'DEFAULT':
                            rrrow.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('texture'))
            else:
                label = get_layer_channel_input_label(layer, ch)
                ssplit.menu("NODE_MT_y_layer_channel_input_menu", text=label)

        else:
            rrow = row.row(align=True)
            rrow.alignment = 'RIGHT'

        rrow.context_pointer_set('parent', ch)
        rrow.context_pointer_set('layer', layer)
        rrow.context_pointer_set('channel_ui', chui)

        icon = 'MODIFIER_ON' if is_bl_newer_than(2, 80) else 'MODIFIER'
        rrow.menu("NODE_MT_y_layer_channel_special_menu", icon=icon, text='')

        if ypui.expand_channels:
            color_ch_enabled = False
            if ch == alpha_ch:
                color_ch_enabled = get_channel_enabled(color_ch, layer) if layer.type == 'GROUP' else color_ch.enable

            if ch == alpha_ch and color_ch_enabled:
                row.label(text='', icon='BLANK1')
            else: row.prop(ch, 'enable', text='')

        if not chui.expand_content: continue

        mrow = ccol.row(align=True)
        mrow.label(text='', icon='BLANK1')
        mbox = mrow.box()
        mcol = mbox.column() #align=True)
        #mcol = mrow.column(align=True)
        #mcol.use_property_split = True

        if layer.type in {'GROUP', 'PREV_LAYERS'}:
            channel_enabled = get_channel_enabled(ch, layer, root_ch)

            if ch.enable and not channel_enabled:
                if layer.type == 'GROUP':
                    label ='No children is using \''+root_ch.name+'\' channel!'
                else: label ='No previous layer is using \''+root_ch.name+'\' channel!'
                mbox.label(text=label, icon='ERROR')

            mcol.active = channel_enabled

        if show_blend_opacity:

            # Blend type
            row = mcol.row(align=True)
            #if ch == height_ch: row.active = not ch.use_height_as_normal
            split = split_layout(row, 0.375)

            rrow = split.row(align=True)
            inbox_dropdown_button(rrow, chui, 'expand_blend_settings', 'Blend:')

            rrow = split.row(align=True)

            if height_ch == ch and height_ch.use_height_as_normal:
                rrow.prop(normal_ch, 'normal_blend_type', text='')
            elif root_ch.special_type == 'NORMAL':
                rrow.prop(ch, 'normal_blend_type', text='')
            elif root_ch.special_type == 'HEIGHT':
                rrow.prop(ch, 'height_blend_type', text='')
            else: rrow.prop(ch, 'blend_type', text='')

            if not chui.expand_blend_settings:
                draw_input_prop(rrow, ch, 'intensity_value', layer=layer)

            else:

                # Layer channel opacity
                row = mcol.row(align=True)
                #if ch == height_ch: row.active = not ch.use_height_as_normal
                row.label(text='', icon='BLANK1')
                row.label(text='Opacity:')
                draw_input_prop(row, ch, 'intensity_value', layer=layer)

                # Use Clamp
                if root_ch.type != 'VECTOR' and root_ch.special_type not in {'HEIGHT', 'NORMAL'}:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='Use Clamp:')
                    row.prop(ch, 'use_clamp', text='')
                
                if ch == color_ch:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='Unpair Alpha:')
                    row.prop(ch, 'unpair_alpha', text='')

        elif layer.type == 'GROUP' and ch == alpha_ch:
            # Layer channel opacity
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            row.label(text='Opacity:')
            draw_input_prop(row, ch, 'intensity_value', layer=layer)

        if root_ch.special_type == 'HEIGHT':

            if layer.type != 'GROUP':
                # Height
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')
                row.active = layer.type != 'COLOR' or not ch.enable_transition_bump
                row.label(text='Scale:') #, icon_value=lib.get_icon('input'))
                row.active == is_bump_distance_relevant(layer, ch)
                draw_input_prop(row, ch, 'bump_distance', layer=layer)

                # Midlevel
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')
                row.active = layer.type != 'COLOR' or not ch.enable_transition_bump
                row.label(text='Midlevel:') 
                draw_input_prop(row, ch, 'bump_midlevel', layer=layer)

                if root_ch.enable_smooth_bump:
                    # Smooth multiplier
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='Smooth Multiplier:') 
                    draw_input_prop(row, ch, 'bump_smooth_multiplier', layer=layer)

            # Write Height
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            row.label(text='Use as Normal Only:')
            row.prop(ch, 'use_height_as_normal', text='')

            if ch.use_height_as_normal:
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')
                row.label(text='Height Blend:')
                row.prop(ch, 'height_blend_type', text='')

            if ch.show_transition_bump or ch.enable_transition_bump:

                brow = mcol.row(align=True)

                rrow = brow.row(align=True)
                inbox_dropdown_button(rrow, chui, 'expand_transition_bump_settings', 'Transition Bump:', scale_override=0.915)

                if is_bl_newer_than(2, 80): rrow = brow.row(align=True) # To make sure the next row align right
                brow.separator()

                if ch.enable_transition_bump and not chui.expand_transition_bump_settings:
                    draw_input_prop(brow, ch, 'transition_bump_distance', layer=layer)

                brow.context_pointer_set('parent', ch)
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                brow.menu("NODE_MT_y_transition_bump_menu", text='', icon=icon)

                brow.prop(ch, 'enable_transition_bump', text='')

                if chui.expand_transition_bump_settings:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')

                    bbox = row.box()
                    bbox.active = ch.enable_transition_bump
                    cccol = bbox.column(align=True)

                    #crow = cccol.row(align=True)
                    #crow.label(text='Type:') #, icon_value=lib.get_icon('input'))
                    #crow.prop(ch, 'transition_bump_type', text='')

                    #crow = cccol.row(align=True)
                    #crow.label(text='Type:') #, icon_value=lib.get_icon('input'))
                    #crow.prop(ch, 'transition_bump_type', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Max Height:') #, icon_value=lib.get_icon('input'))
                    draw_input_prop(crow, ch, 'transition_bump_distance', layer=layer)

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 1:') #, icon_value=lib.get_icon('input'))
                    draw_input_prop(crow, ch, 'transition_bump_value', layer=layer)

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 2:') #, icon_value=lib.get_icon('input'))
                    draw_input_prop(crow, ch, 'transition_bump_second_edge_value', layer=layer)

                    crow = cccol.row(align=True)
                    crow.label(text='Affected Masks:') #, icon_value=lib.get_icon('input'))
                    crow.prop(ch, 'transition_bump_chain', text='')

                    #if ch.transition_bump_type == 'CURVED_BUMP_MAP':
                    #    crow = cccol.row(align=True)
                    #    crow.label(text='Offset:') #, icon_value=lib.get_icon('input'))
                    #    crow.prop(ch, 'transition_bump_curved_offset', text='')

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND'
                    crow.label(text='Flip:') #, icon_value=lib.get_icon('input'))
                    crow.prop(ch, 'transition_bump_flip', text='')

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                    crow.active = not ch.transition_bump_flip
                    crow.label(text='Crease:') #, icon_value=lib.get_icon('input'))
                    crow.prop(ch, 'transition_bump_crease', text='')

                    if ch.transition_bump_crease:
                        crow = cccol.row(align=True)
                        crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                        crow.label(text='Crease Factor:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(crow, ch, 'transition_bump_crease_factor', layer=layer)

                        crow = cccol.row(align=True)
                        crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                        crow.label(text='Crease Power:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(crow, ch, 'transition_bump_crease_power', layer=layer)

                        cccol.separator()

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND'
                    crow.label(text='Falloff:') #, icon_value=lib.get_icon('input'))
                    crow.prop(ch, 'transition_bump_falloff', text='')

                    if ch.transition_bump_falloff:

                        crow = cccol.row(align=True)
                        crow.label(text='Falloff Type :') #, icon_value=lib.get_icon('input'))
                        crow.prop(ch, 'transition_bump_falloff_type', text='')

                        if ch.transition_bump_falloff_type == 'EMULATED_CURVE':

                            crow = cccol.row(align=True)
                            crow.label(text='Falloff Factor:') #, icon_value=lib.get_icon('input'))
                            draw_input_prop(crow, ch, 'transition_bump_falloff_emulated_curve_fac', layer=layer)
                        
                        elif ch.transition_bump_falloff_type == 'CURVE' and ch.enable_transition_bump and ch.enable:
                            cccol.separator()
                            tbf = layer_tree.nodes.get(ch.tb_falloff)
                            if root_ch.enable_smooth_bump:
                                tbf = tbf.node_tree.nodes.get('_original')
                            curve = tbf.node_tree.nodes.get('_curve')
                            curve.draw_buttons_ext(context, cccol)

                    #row.label(text='', icon='BLANK1')

        if root_ch.special_type == 'NORMAL' and layer.type != 'GROUP':

            #height_as_normal_disabled = ch == normal_ch and (height_ch == None or not height_ch.enable or not height_ch.use_height_as_normal)

            # Normal Strength
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            #row.active = height_as_normal_disabled
            label = 'Normal Strength:' if ch.normal_map_type == 'BUMP_NORMAL_MAP' else 'Strength:'
            row.label(text=label)
            if ch.normal_map_type == 'NORMAL_MAP':
                row = row.row(align=True)
                row.scale_x = 1.4
            draw_input_prop(row, ch, 'normal_strength', layer=layer)

            # Normal Space
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            #row.active = height_as_normal_disabled
            label = 'Normal Space:' if ch.normal_map_type == 'BUMP_NORMAL_MAP' else 'Space:'
            row.label(text=label)
            if ch.normal_map_type == 'NORMAL_MAP':
                row = row.row(align=True)
                row.scale_x = 1.4
            row.prop(ch, 'normal_space', text='')

        if root_ch.special_type == 'VDISP' and layer.type != 'GROUP':

            # Vector Displacement Strength
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            row.label(text='Strength:') #, icon_value=lib.get_icon('input'))
            draw_input_prop(row, ch, 'vdisp_strength', layer=layer)

            # Vector Displacement Flip Y/Z
            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            row.label(text='Flip Y/Z:') #, icon_value=lib.get_icon('input'))
            draw_input_prop(row, ch, 'vdisp_enable_flip_yz', layer=layer)

        if root_ch.type in {'RGB', 'VALUE'}:

            if ch.show_transition_ramp or ch.enable_transition_ramp:

                # Transition Ramp
                row = mcol.row(align=True)

                tr_ramp = layer_tree.nodes.get(ch.tr_ramp)
                rrow = row.row(align=True)

                label_text = 'Transition Ramp:'
                if not tr_ramp:
                    rrow.label(text='', icon='BLANK1')
                    rrow.label(text=label_text)
                else:
                    inbox_dropdown_button(rrow, chui, 'expand_transition_ramp_settings', label_text, scale_override=0.915)

                if is_bl_newer_than(2, 80): rrow = row.row(align=True) # To make sure the next row align right
                row.separator()

                if ch.enable_transition_ramp and not chui.expand_transition_ramp_settings:
                    draw_input_prop(row, ch, 'transition_ramp_intensity_value', layer=layer)

                row.context_pointer_set('parent', ch)
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                row.menu("NODE_MT_y_transition_ramp_menu", text='', icon=icon)

                row.prop(ch, 'enable_transition_ramp', text='')

                if tr_ramp and chui.expand_transition_ramp_settings:
                    row = mcol.row(align=True)
                    row.active = ch.enable_transition_ramp
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    bcol = box.column(align=False)

                    brow = bcol.row(align=True)
                    brow.label(text='Intensity:')
                    draw_input_prop(brow, ch, 'transition_ramp_intensity_value', layer=layer)

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ramp_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.active = bump_ch_found
                    brow.label(text='Transition Factor:')
                    draw_input_prop(brow, ch, 'transition_bump_second_fac', layer=layer)

                    if tr_ramp.type == 'GROUP':
                        ramp = tr_ramp.node_tree.nodes.get('_RAMP')

                        #brow.prop(ch, 'ramp_intensity_value', text='')
                        bcol.template_color_ramp(ramp, "color_ramp", expand=True)
                        #row.label(text='', icon='BLANK1')

            if ch.show_transition_ao or ch.enable_transition_ao:

                # Transition AO
                row = mcol.row(align=True)
                row.active = bump_ch_found #and layer.type != 'BACKGROUND'

                rrow = row.row(align=True)

                inbox_dropdown_button(rrow, chui, 'expand_transition_ao_settings', 'Transition AO:', scale_override=0.915)

                if is_bl_newer_than(2, 80): rrow = row.row(align=True) # To make sure the next row align right
                row.separator()

                if ch.enable_transition_ao and not chui.expand_transition_ao_settings:
                    draw_input_prop(row, ch, 'transition_ao_intensity', layer=layer)

                row.context_pointer_set('layer', layer)
                row.context_pointer_set('parent', ch)
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                row.menu("NODE_MT_y_transition_ao_menu", text='', icon=icon)

                row.prop(ch, 'enable_transition_ao', text='')

                if chui.expand_transition_ao_settings:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    box.active = bump_ch_found #and layer.type != 'BACKGROUND'
                    bcol = box.column(align=False)

                    brow = bcol.row(align=True)
                    brow.label(text='Intensity:')
                    draw_input_prop(brow, ch, 'transition_ao_intensity', layer=layer)

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ao_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Power:')
                    draw_input_prop(brow, ch, 'transition_ao_power', layer=layer)

                    brow = bcol.row(align=True)
                    brow.label(text='Color:')
                    draw_input_prop(brow, ch, 'transition_ao_color', layer=layer)

                    brow = bcol.row(align=True)
                    brow.label(text='Inside:')
                    draw_input_prop(brow, ch, 'transition_ao_inside_intensity', layer=layer)

            # Transition Bump Intensity
            if showed_bump_ch_found:
                row = mcol.row(align=True)
                row.active = bump_ch_found
                row.label(text='', icon='BLANK1')
                row.label(text='Transition Factor:')
                draw_input_prop(row, ch, 'transition_bump_fac', layer=layer)

            extra_separator = True

        # Get sources
        source = get_channel_source(ch, layer)
        source_1 = layer_tree.nodes.get(ch.source_1)
        cache_1 = layer_tree.nodes.get(ch.cache_1_image)

        split_factor = 0.375

        # Override settings

        modcol = mcol.column()
        modcol.active = layer.type != 'BACKGROUND'
        draw_modifier_stack(context, ch, root_ch.type, modcol, 
                ypui.layer_ui.channels[i], layer)

        #mcol.separator()

        # NOTE: Swizzle currently only works with non custom layer channel source
        # Only expose swizzle to developer for now
        soc = get_channel_input_socket(layer, ch, source)
        swizzleable = (ypup.developer_mode or ch.swizzle_input_mode != 'RGB') and soc.type in {'RGBA', 'RGB', 'VECTOR'} and not ch.override
        socket_input_name = get_channel_input_socket_name(layer, ch, source)

        input_settings_available = has_layer_input_options(layer) and (socket_input_name != 'Alpha' 
                and root_ch.colorspace == 'SRGB')

        #row = mcol.row(align=True)
        srow = split_layout(mcol, split_factor, align=False)
        row = srow.row(align=True)

        label = ''
        label += 'Source:'

        if ch == color_ch and ch.enable:
            label = root_ch.name + ':'

        dropdown_available = (ch.override and ch.override_type != 'VCOL') or input_settings_available or swizzleable

        if dropdown_available:
            inbox_dropdown_button(row, chui, 'expand_source', label)
        else:
            row.label(text='', icon='BLANK1')
            row.label(text=label)

        row = srow.row(align=True)
        label = get_layer_channel_input_label(layer, ch, source)
        row.context_pointer_set('parent', ch)
        if ch.override and ch.override_type == 'DEFAULT' and not ch.expand_source:
            split = split_layout(row, 0.55, align=True)
            split.menu("NODE_MT_y_layer_channel_input_menu", text=label)
            if root_ch.type == 'VALUE':
                draw_input_prop(split, ch, 'override_value', layer=layer)
            else: draw_input_prop(split, ch, 'override_color', layer=layer)
        else:
            swizzle_shortcut = swizzleable and not ch.expand_source
            if swizzle_shortcut:
                rrow = split_layout(row, 0.55, align=True)
            else: 
                rrow = row.row(align=True)
                rrow.scale_x = 1.4 if ch.normal_map_type != 'BUMP_NORMAL_MAP' else 1.1

            rrow.menu("NODE_MT_y_layer_channel_input_menu", text=label)

            if swizzle_shortcut:
                rrow.prop(ch, "swizzle_input_mode", text='')

        #if ch.enable and ch.override: #and ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
        if (ch.enable or (ch == alpha_ch and color_ch.enable)) and ch.override:
            if ch.override_type == 'IMAGE':
                row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('image'))
            elif ch.override_type == 'VCOL':
                row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color'))
            elif ch.override_type != 'DEFAULT':
                row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('texture'))

        ch_source = None
        if ch.override:
            ch_source = get_channel_source(ch, layer)

        if ch.expand_source and dropdown_available: # and ch.override_type != 'DEFAULT':

            rrow = mcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            #rrcol = rrow.box()
            rrcol = rrow.column()

            if swizzleable:
                srow = split_layout(rrcol, 0.5, align=False)
                srow.label(text='Swizzle:')
                srow.prop(ch, "swizzle_input_mode", text='')

            if ch.override:
                if ch.override_type == 'DEFAULT':
                    row = rrcol.row()
                    if root_ch.type == 'VALUE':
                        row.label(text='Custom Value:')
                        draw_input_prop(row, ch, 'override_value', layer=layer)
                    else: 
                        row.label(text='Custom Color:')
                        draw_input_prop(row, ch, 'override_color', layer=layer)

                if ch_source:
                    if ch.override_type == 'IMAGE':
                        draw_image_props(context, ch_source, rrcol, ch, show_datablock=False)
                    elif ch.override_type == 'VCOL':
                        draw_vcol_props(rrcol)
                    else:
                        draw_tex_props(ch_source, rrcol, entity=ch)

            elif input_settings_available:
                row = rrcol.row(align=True)
                row.label(text='Gamma Space:')
                row.prop(ch, 'gamma_space', text='')

        if ypui.expand_channels:
            mrow.label(text='', icon='BLANK1')

        if not specific_ch and extra_separator and i < len(layer.channels)-1:
            ccol.separator()

    if not ypui.expand_channels and ch_count == 0:
        rcol.label(text='No active channel!')

    if not specific_ch:
        layout.separator()

    #print(get_addon_title()+': Layer channels UI is drawn in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def draw_layer_masks(context, layout, layer, specific_mask=None):
    #T = time.time()

    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()
    lui = ypui.layer_ui

    layer_tree = get_tree(layer)

    col = layout.column()
    col.active = layer.enable_masks

    layer_color_ch, layer_alpha_ch = get_layer_color_alpha_ch_pairs(layer)

    if not specific_mask:
        #label = 'Masks'

        num_masks = len(layer.masks)
        num_enabled_masks = len([m for m in layer.masks if m.enable])

        text_mask = pgettext_iface('Mask')
        if num_masks == 0:
            #label += ' (0)'
            label = text_mask # (0)'
        elif num_enabled_masks == 0:
            label = text_mask + ' (0)'
        elif num_enabled_masks == 1:
            label = text_mask + ' (1)'
        else:
            label = pgettext_iface('Masks') + ' ('
            label += str(num_enabled_masks) + ')'

        #if lui.expand_masks and len(layer.masks) > 0:
        #    label += ':'

        row = col.row(align=True)
        rrow = row.row(align=True)
        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95

        icon_value = lib.get_icon('mask')
        if len(layer.masks) > 0:
            icon = get_collapse_arrow_icon(lui.expand_masks)
            rrow.prop(lui, 'expand_masks', text='', emboss=False, icon=icon)
        else: 
            rrow.label(text='', icon='BLANK1')
        
        if is_bl_newer_than(2, 80):
            rrow.prop(lui, 'expand_masks', text=label, emboss=False, icon_value=icon_value)
        else: rrow.label(text=label, icon_value=icon_value)

        rrow = row.row()
        rrow.alignment = 'RIGHT'

        if is_bl_newer_than(4) and not ypup.ui_legacy_add_layer_menu:
            rrow.operator("wm.call_menu", text='', icon='ADD').name = "NODE_MT_y_add_layer_mask_menu"
        elif is_bl_newer_than(2, 80):
            rrow.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='ADD')
        else: rrow.menu('NODE_MT_y_add_layer_mask_menu', text='', icon='ZOOMIN')

        if not lui.expand_masks or len(layer.masks) == 0: return

    #row = col.row(align=True)
    #row.label(text='', icon='BLANK1')
    #rcol = row.column(align=False)

    for i, mask in enumerate(layer.masks):

        try: maskui = ypui.layer_ui.masks[i]
        except: 
            ypui.need_update = True
            return

        if specific_mask and specific_mask != mask: continue

        mask_image = None
        mask_tree = get_mask_tree(mask, layer_tree)
        mask_source = mask_tree.nodes.get(mask.source)
        mask_vcol_name = ''
        socket_input_name = get_mask_input_socket_name(mask, mask_source) if mask_source else ''

        if mask.type == 'IMAGE':
            mask_image = mask_source.image
            if mask_image.yia.is_image_atlas or mask_image.yua.is_udim_atlas:
                label_text = mask.name
            else: label_text = mask_image.name
        elif mask.type == 'VCOL':
            label_text = mask_vcol_name = mask_source.attribute_name
        else: label_text = mask.name

        if mask.type in {'IMAGE', 'VCOL'} and socket_input_name == 'Alpha':
            label_text += ' (Alpha)'

        mrow = col.row(align=True)
        if not specific_mask:
            mrow.label(text='', icon='BLANK1')
        mrow.active = mask.enable

        if not maskui.expand_content: # and ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
            srow = split_layout(mrow, 0.35, align=True)
        else: 
            srow = mrow

        rrow = srow.row(align=True)
        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
        icon = get_collapse_arrow_icon(maskui.expand_content)
        rrow.prop(maskui, 'expand_content', text='', emboss=False, icon=icon)

        icon_value = lib.get_icon('mask')
        if is_bl_newer_than(2, 80):
            rrow.prop(maskui, 'expand_content', text=label_text, emboss=False, icon_value=icon_value)
        else: rrow.label(text=label_text, icon_value=icon_value)

        if maskui.expand_content:
            srow.separator()

        rrow = srow.row(align=True)
        if maskui.expand_content:
            rrow.alignment = 'RIGHT'

        #if mask.baked_source != '':
        #    rrow.prop(mask, 'use_baked', text='Use Baked', toggle=True)

        if not maskui.expand_content: # and ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
            rrow.prop(mask, 'blend_type', text='')
            draw_input_prop(rrow, mask, 'intensity_value', layer=layer)

        mask_icon = ''
        if mask.enable:
            if mask.type == 'IMAGE':
                #if socket_input_name in {'Alpha', 'R', 'G', 'B'}:
                if socket_input_name == 'Alpha':
                    mask_icon = RGBA_CHANNEL_PREFIX[socket_input_name] + 'image'
                elif mask.swizzle_input_mode in {'R', 'G', 'B'}:
                    mask_icon = RGBA_CHANNEL_PREFIX[mask.swizzle_input_mode] + 'image'
                else: 
                    mask_icon = 'image'
            elif mask.type == 'VCOL':
                #if socket_input_name in {'Alpha', 'R', 'G', 'B'}:
                if socket_input_name == 'Alpha':
                    mask_icon = RGBA_CHANNEL_PREFIX[socket_input_name] + 'vertex_color'
                elif mask.swizzle_input_mode in {'R', 'G', 'B'}:
                    mask_icon = RGBA_CHANNEL_PREFIX[mask.swizzle_input_mode] + 'vertex_color'
                else: 
                    mask_icon = 'vertex_color'
            elif mask.type == 'HEMI':
                mask_icon = 'hemi'
            elif mask.type == 'OBJECT_INDEX':
                mask_icon = 'object_index'
            elif mask.type in {'EDGE_DETECT', 'AO'}:
                mask_icon = 'edge_detect'
            elif mask.type == 'COLOR_ID':
                mask_icon = 'color'
            elif mask.type == 'BACKFACE':
                mask_icon = 'backface'
            elif mask.type == 'MODIFIER':
                mask_icon = 'modifier'
            else:
                mask_icon = 'texture'

        if mask_icon != '' and not maskui.expand_content: # and ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
            rrow.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon(mask_icon))

        rrow.context_pointer_set('mask', mask)

        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        rrow.menu("NODE_MT_y_layer_mask_menu", text='', icon=icon)

        mrow.prop(mask, 'enable', text='')

        if not maskui.expand_content: continue

        row = col.row(align=True)
        row.active = mask.enable
        if not specific_mask:
            row.label(text='', icon='BLANK1')
        row.label(text='', icon='BLANK1')
        box = row.box()
        rrcol = box.column()
        row.label(text='', icon='BLANK1')

        # Blend row
        srow = split_layout(rrcol, 0.35, align=False)
        rrow = srow.row(align=True)
        inbox_dropdown_button(rrow, maskui, 'expand_channels', 'Blend:')

        rrow = srow.row(align=True)
        rrow.prop(mask, 'blend_type', text='')
        if not maskui.expand_channels:
            draw_input_prop(rrow, mask, 'intensity_value', layer=layer)

        # Mask Channels row
        if maskui.expand_channels:

            # Channels row
            #rbox = rrow.box()
            bcol = rrcol.column() #align=True)

            rrow = bcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            rrow.label(text='Opacity:')
            draw_input_prop(rrow, mask, 'intensity_value', layer=layer)

            for k, c in enumerate(mask.channels):

                #if k%2 == 0:
                erow = bcol.row(align=True)
                erow.label(text='', icon='BLANK1')

                rrow = erow.row(align=True)
                lc = layer.channels[k]
                rrow.active = lc.enable if lc != layer_alpha_ch else layer_color_ch.enable or lc.enable
                root_ch = yp.channels[k]
                #rrow.label(text='', 
                #        icon_value=lib.get_icon(lib.channel_custom_icon_dict[root_ch.type]))
                rrow.label(text=root_ch.name + ':', translate=False)
                rrow.label(text='', icon_value=lib.get_icon(lib.channel_custom_icon_dict[root_ch.type]))
                rrow.prop(c, 'enable', 
                    text = '',
                    #text=root_ch.name,
                    #toggle = True,
                    #icon_value=lib.get_icon(lib.channel_custom_icon_dict[root_ch.type])
                )

            rrcol.separator()

        draw_mask_modifier_stack(layer, mask, rrcol, maskui, layer_tree)

        # Source row
        srow = split_layout(rrcol, 0.35, align=False)
        rrow = srow.row(align=True)

        text_source = pgettext_iface('Source: ')
        if mask.type not in {'BACKFACE', 'MODIFIER'} or (mask.type == 'MODIFIER' and mask.modifier_type in {'CURVE', 'RAMP'}):
            inbox_dropdown_button(rrow, maskui, 'expand_source', text_source)
        else:
            rrow.label(text='', icon='BLANK1')
            rrow.label(text=text_source)

        rrow = srow.row(align=True)

        #rrrow = rrow.row(align=True)
        #splits.alignment = 'RIGHT'
        if mask_image:
            label = mask_image.name
        elif mask_vcol_name != '':
            label = mask_vcol_name
        elif mask.type == 'MODIFIER':
            if mask.modifier_type == 'INVERT': 
                label = 'Invert'
            elif mask.modifier_type == 'RAMP': 
                label = 'Ramp'
            elif mask.modifier_type == 'CURVE': 
                label = 'Curve'
        else: 
            label = mask_type_labels[mask.type]

        rrrow = rrow.row(align=True)
        rrrow.context_pointer_set('mask', mask)
        #rrrow.label(text=label)
        rrrow.menu("NODE_MT_y_mask_type_menu", text=label) #, icon_value=icon_value)
        
        if mask_icon != '': # and ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
            rrrow.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon(mask_icon))

        if maskui.expand_source and (mask.type not in {'BACKFACE', 'MODIFIER'} or 
                                     (mask.type == 'MODIFIER' and mask.modifier_type in {'CURVE', 'RAMP'})):
            rrow = rrcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            #rbox = rrow.box()
            #rbcol = rbox.column()
            rbcol = rrow.column()
            rbcol.active = not mask.use_baked
            if mask_image:
                draw_image_props(context, mask_source, rbcol, mask, show_datablock=False, show_source_input=True)
            elif mask.type == 'HEMI':
                draw_hemi_props(mask, mask_source, rbcol)
            elif mask.type == 'OBJECT_INDEX':
                draw_object_index_props(mask, rbcol)
            elif mask.type == 'COLOR_ID':
                draw_colorid_props(mask, mask_source, rbcol, layer=layer)
            elif mask.type == 'EDGE_DETECT':
                draw_edge_detect_props(mask, mask_source, rbcol, layer=layer)
            elif mask.type == 'AO':
                draw_ao_props(mask, mask_source, rbcol, layer=layer)
            elif mask.type == 'MODIFIER':
                draw_inbetween_modifier_mask_props(mask, mask_source, rbcol)
            elif mask.type == 'VCOL':
                draw_vcol_props(rbcol, entity=mask, show_divide_rgb_alpha=False, show_source_input=True)
            else: draw_tex_props(mask_source, rbcol, entity=mask, show_source_input=True)

            rrcol.context_pointer_set('entity', mask)
            if mask.baked_source == '' and mask.type in {'EDGE_DETECT', 'HEMI', 'AO'}:
                rrrow = rrcol.row(align=True)
                rrrow.label(text='', icon='BLANK1')
                rrrow.operator("wm.y_bake_entity_to_image", text='Bake '+mask_type_labels[mask.type]+' as Image', icon_value=lib.get_icon('bake'))

            elif mask.baked_source != '':

                baked_source = mask_tree.nodes.get(mask.baked_source)
                if baked_source and baked_source.image:
                    brow = rrcol.row(align=True)
                    brow.active = mask.use_baked
                    brow.label(text='', icon='BLANK1')

                    crow = brow.row(align=True)
                    drow = crow.row(align=True)
                    drow.label(text='Baked: ')
                    drow = crow.row(align=True)
                    drow.alignment = 'RIGHT'
                    drow.label(text=baked_source.image.name, icon='IMAGE_DATA')

                brow = rrcol.row(align=True)
                brow.label(text='', icon='BLANK1')
                brow.operator("wm.y_bake_entity_to_image", text='Rebake', icon_value=lib.get_icon('bake'))
                brow.prop(mask, 'use_baked', text='Use Baked', toggle=True)
                icon = 'TRASH' if is_bl_newer_than(2, 80) else 'X'
                brow.operator("wm.y_remove_baked_entity", text='', icon=icon)

            if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER', 'AO'}:
                rrcol.separator()

        # Vector row
        if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER', 'AO'}:

            srow = split_layout(rrcol, 0.35, align=False)
            srow.active = not mask.use_baked
            rrow = srow.row(align=True)

            label_text = 'Mapping:'
            if mask.texcoord_type != 'Layer':
                inbox_dropdown_button(rrow, maskui, 'expand_vector', label_text)
            else: 
                rrow.label(text='', icon='BLANK1')
                rrow.label(text=label_text)

            texcoord = layer_tree.nodes.get(mask.texcoord)

            rrow = srow.row(align=True)
            if mask.texcoord_type == 'UV' and not maskui.expand_vector:

                if obj.type == 'MESH':
                    rrrow = split_layout(rrow, 0.35, align=True)
                    rrrow.prop(mask, 'texcoord_type', text='')
                    rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                else:
                    rrow.prop(mask, 'texcoord_type', text='')

                #rrow.context_pointer_set('mask', mask)
                #icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                #rrow.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')
            elif mask.type == 'IMAGE' and mask.texcoord_type in {'Generated', 'Object'} and not maskui.expand_vector:
                mask_src = get_mask_source(mask)

                rrrow = split_layout(rrow, 0.5, align=True)

                rrrow.prop(mask, 'texcoord_type', text='')
                rrrow.prop(mask_src, 'projection_blend', text='')
            elif mask.texcoord_type == 'Decal' and not maskui.expand_vector:
                ssplit = split_layout(rrow, 0.4, align=True)
                if texcoord:
                    ssplit.prop(mask, 'texcoord_type', text='')
                    ssplit.prop(texcoord, 'object', text='')
            else:
                rrow.prop(mask, 'texcoord_type', text='')

            if maskui.expand_vector and mask.texcoord_type != 'Layer':
                rrow = rrcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                #rbox = rrow.box()
                #boxcol = rbox.column()
                boxcol = rrow.column()
                boxcol.active = not mask.use_baked

                is_using_image_atlas = mask_image and (mask_image.yia.is_image_atlas or mask_image.yua.is_udim_atlas)

                if mask.type == 'IMAGE' and mask.texcoord_type in {'Generated', 'Object'}:
                    mask_src = get_mask_source(mask)

                    splits = split_layout(boxcol, 0.5, align=True)
                    splits.label(text='Projection Blend:')
                    splits.prop(mask_src, 'projection_blend', text='')

                if mask.texcoord_type == 'UV' and obj.type == 'MESH':
                    rrow = boxcol.row(align=True)
                    rrow.label(text='UV Map:')
                    rrrow = rrow.row(align=True)
                    rrrow.scale_x = 1.2
                    rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

                    icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                    rrow.context_pointer_set('entity', mask)
                    rrow.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')

                if mask.texcoord_type == 'Decal':
                    if texcoord:
                        splits = split_layout(boxcol, 0.45, align=True)
                        splits.label(text='Decal Object:')
                        splits.prop(texcoord, 'object', text='')

                    splits = split_layout(boxcol, 0.5, align=True)
                    splits.label(text='Decal Distance:')
                    draw_input_prop(splits, mask, 'decal_distance_value', layer=layer)

                    if texcoord and texcoord.object:
                        rrow = boxcol.row(align=True)
                        rrow.label(text='Decal Constraint:')
                        draw_input_prop(rrow, texcoord.object.yp_decal, 'enable_shrinkwrap')

                        # NOTE: Show constraint target when there's more than one material users
                        decal_const = Decal.get_decal_shrinkwrap_constraint(texcoord.object)
                        if decal_const:
                            mat = get_active_material()
                            if mat.users > 1 or decal_const.target == None:
                                rrow = boxcol.row(align=True)
                                rrow.label(text='Constraint Target:')
                                draw_input_prop(rrow, decal_const, 'target')

                    boxcol.context_pointer_set('entity', mask)
                    if is_bl_newer_than(2, 80):
                        boxcol.operator('wm.y_select_decal_object', icon='COLLAPSEMENU')
                    else: boxcol.operator('wm.y_select_decal_object', icon='EMPTY_DATA')
                    boxcol.operator('wm.y_set_decal_object_position_to_sursor', text='Set Position to Cursor', icon='CURSOR')

                if mask.texcoord_type != 'Decal' and not is_using_image_atlas:
                    mapping = get_mask_mapping(mask)

                    rrow = boxcol.row()
                    rrow.label(text='Transform:')
                    rrow.prop(mapping, 'vector_type', text='')

                    rrow = boxcol.row()
                    if is_bl_newer_than(2, 81):
                        mcol = rrow.column()
                        mcol.prop(mapping.inputs[1], 'default_value', text='Offset')
                        mcol = rrow.column()
                        mcol.prop(mapping.inputs[2], 'default_value', text='Rotation')
                        if mask.enable_uniform_scale:
                            mcol = rrow.column(align=True)
                            mrow = mcol.row()
                            mrow.label(text='Scale:')
                            mrow.prop(mask, 'enable_uniform_scale', text='', icon='LOCKED')
                            draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'X', layer=layer)
                            draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'Y', layer=layer)
                            draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'Z', layer=layer)
                        else:
                            mcol = rrow.column(align=True)
                            mrow = mcol.row()
                            mrow.label(text='Scale:')
                            mrow.prop(mask, 'enable_uniform_scale', text='', icon='UNLOCKED')
                            mcol.prop(mapping.inputs[3], 'default_value', text='')
                    else:
                        mcol = rrow.column()
                        mcol.prop(mapping, 'translation')
                        mcol = rrow.column()
                        mcol.prop(mapping, 'rotation')
                        mcol = rrow.column()
                        mcol.prop(mapping, 'scale')
                
                    if mask.type == 'IMAGE' and mask.active_edit and (
                            yp.need_temp_uv_refresh
                            ):
                        rrow = boxcol.row(align=True)
                        rrow.alert = True
                        rrow.operator('wm.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')
            
                # Blur row
                if mask.texcoord_type != 'Layer':
                    rrow = boxcol.row(align=True)
                    splits = split_layout(rrow, 0.5)
                    splits.label(text='Blur:')
                    if mask.enable_blur_vector:
                        draw_input_prop(splits, mask, 'blur_vector_factor', layer=layer)
                    rrow.prop(mask, 'enable_blur_vector', text='')

        if not specific_mask and i < len(layer.masks)-1:
            col.separator()

    #print(get_addon_title()+': Layer masks are drawn in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def is_gamma_incorrect(gamma, linear_node):
    return (
        (gamma == 1.0 and linear_node) or
        (gamma != 1.0 and (not linear_node or not isclose(linear_node.inputs[1].default_value, gamma, rel_tol=1e-5)))
    )

def any_yp_problems(node, vcols=[]):
    yp = node.node_tree.yp
    #T = time.time()

    scene = bpy.context.scene
    obj = bpy.context.object

    linear_problem = False
    ao_problem = False
    missing_data = False
    missing_combine_bundle = False

    gtao_not_used = is_bl_newer_than(2, 93) and not is_bl_newer_than(4, 2) and not scene.eevee.use_gtao

    for layer in yp.layers:
        layer_tree = None
        layer_source = None
        layer_enabled = get_layer_enabled(layer)

        # Check for combine bundle node
        if layer.type == 'INPUT_BUNDLE':
            inp = node.inputs.get(layer.name)
            if inp and (len(inp.links) == 0 or inp.links[0].from_node.type != 'NodeCombineBundle'):
                missing_combine_bundle = True

        # Check for missing data
        if not missing_data:
            if layer.type in {'IMAGE' , 'VCOL'}:
                if layer_tree == None: layer_tree = get_tree(layer) # Optimization
                if layer_source == None: layer_source = get_layer_source(layer, layer_tree) # Optimization

                if (
                        not layer_source or
                        (layer.type == 'IMAGE' and not layer_source.image) or 
                        (layer.type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, layer_source))
                    ):
                    missing_data = True

        # Channels loop
        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]
            
            channel_source_tree = None
            channel_source = None

            # Check for missing channel source data
            if not missing_data:
                if ch.override and ch.override_type in {'IMAGE', 'VCOL'}:
                    if channel_source == None: 
                        if channel_source_tree == None: channel_source_tree = get_channel_source_tree(ch, layer) # Optimization
                        channel_source = get_channel_source(ch, layer, channel_source_tree)
                    if (
                            not channel_source or
                            (ch.override_type == 'IMAGE' and not channel_source.image) or 
                            (ch.override_type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, channel_source))
                        ):
                        missing_data = True

            # No need to check linear problem if channel is disabled or there's missing data
            if missing_data or not layer_enabled or not get_channel_enabled(ch, layer, root_ch): continue

            # Check for linear problem on channel source
            if not linear_problem:
                if channel_source_tree == None: channel_source_tree = get_channel_source_tree(ch, layer) # Optimization
                if channel_source == None: channel_source = get_channel_source(ch, layer, channel_source_tree) # Optimization
                if layer_source == None: layer_source = get_layer_source(layer, layer_tree) # Optimization

                gamma = get_layer_channel_gamma_value(ch, layer, root_ch, channel_source=channel_source, layer_source=layer_source, channel_enabled=True)
                linear = channel_source_tree.nodes.get(ch.linear)

                if is_gamma_incorrect(gamma, linear):
                    linear_problem = True

        # Masks loop
        for mask in layer.masks:

            mask_tree = None
            mask_source = None

            # Check for missing mask source data
            if not missing_data:
                if mask.type in {'IMAGE' , 'VCOL'}:
                    if layer_tree == None: layer_tree = get_tree(layer) # Optimization
                    if mask_tree == None: mask_tree = get_mask_tree(mask, layer_tree) # Optimization
                    if mask_source == None: mask_source = mask_tree.nodes.get(mask.source)

                    if (
                            not mask_source or
                            (mask.type == 'IMAGE' and mask_source and not mask_source.image) or 
                            (mask.type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, mask_source))
                        ):
                        missing_data = True

                elif mask.type == 'COLOR_ID':
                    if obj.type == 'MESH' and COLOR_ID_VCOL_NAME not in vcols:
                        missing_data = True

            # No need to check linear problem if mask is disabled or there's missing data
            if missing_data or not layer_enabled or not get_mask_enabled(mask, layer): continue

            # Check for AO problem
            if gtao_not_used and not ao_problem and mask.type in {'EDGE_DETECT', 'AO'}:
                ao_problem = True

            # Check for linear problem on mask
            if not linear_problem:
                if layer_tree == None: layer_tree = get_tree(layer) # Optimization
                if mask_tree == None: mask_tree = get_mask_tree(mask, layer_tree) # Optimization
                if mask_source == None: mask_source = mask_tree.nodes.get(mask.source) # Optimization

                gamma = get_layer_mask_gamma_value(mask, mask_tree=mask_tree, mask_source=mask_source, mask_enabled=True)
                linear = mask_tree.nodes.get(mask.linear)
                if is_gamma_incorrect(gamma, linear):
                    linear_problem = True

        # No need to check linear problem if layer is disabled or there's missing data
        if missing_data or not layer_enabled: continue

        # Check for AO problem
        if gtao_not_used and not ao_problem and layer.type in {'EDGE_DETECT', 'AO'}:
            ao_problem = True

        # Check for linear problem on legacy blender source node
        if not linear_problem:

            # Blender 2.7x has color space option on the node 
            if not is_bl_newer_than(2, 80) and layer.type == 'IMAGE':
                if layer_tree == None: layer_tree = get_tree(layer) # Optimization
                if layer_source == None: layer_source = get_layer_source(layer, layer_tree) # Optimization

                if layer_source:
                    if layer_source.color_space == 'NONE' and yp.use_linear_blending:
                        linear_problem = True
                    if layer_source.color_space == 'COLOR' and not yp.use_linear_blending:
                        linear_problem = True

        # Check for linear problem on layer source
        if not linear_problem:
            if layer_tree == None: layer_tree = get_tree(layer) # Optimization
            if layer_source == None: layer_source = get_layer_source(layer, layer_tree) # Optimization

            gamma = get_layer_gamma_value(layer, layer_source, layer_enabled=True)
            source_tree = get_source_tree(layer, layer_tree)
            linear = source_tree.nodes.get(layer.linear)

            if is_gamma_incorrect(gamma, linear):
                linear_problem = True

    #print(get_addon_title()+': YP problems are calculated in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

    return linear_problem, ao_problem, missing_data, missing_combine_bundle

def draw_baked_ui(context, layout, node):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()

    col = layout.column(align=False)

    if is_not_in_material_view() and ypup.enable_material_view_warning:
        bbox = col.box()
        row = bbox.row(align=True)
        row.alert = True
        row.operator('wm.y_switch_to_material_view', icon='MATERIAL_DATA')
        row.alert = False

    # Get paired channels
    root_color_ch, root_alpha_ch = get_color_alpha_ch_pairs(yp)
    root_normal_ch, root_height_ch = get_normal_height_ch_pairs(yp)

    # Get channel bake target dictionary
    chbts = get_channel_bake_target_dict(yp)

    for i, root_ch in enumerate(yp.channels):

        try: nchui = ypui.channels[i]
        except: 
            ypui.need_update = True
            return

        baked_image = get_active_baked_channel_image(root_ch)

        icon_name = lib.channel_custom_icon_dict[root_ch.type]
        icon_value = lib.get_icon(icon_name)

        # Check if channel has any baked node
        any_baked_node = False
        if root_ch.name in chbts:
            for bt in chbts[root_ch.name]:
                baked_node = nodes.get(bt.baked_node)
                if baked_node:
                    any_baked_node = True
                    break

        no_baked_data = root_ch.name not in chbts or len(chbts[root_ch.name]) == 0 or not any_baked_node
        bake_disabled = root_ch.disable_global_baked and not yp.enable_baked_outside

        row = col.row(align=True)
        row.context_pointer_set('root_ch', root_ch)
        if baked_image: row.context_pointer_set('image', baked_image)
        else: row.context_pointer_set('image', None)

        rrow = row.row(align=True)
        icon = get_collapse_arrow_icon(getattr(nchui, 'expand_baked_data'))
        rrow.prop(nchui, 'expand_baked_data', text='', emboss=False, icon=icon)
        rrow = row.row(align=True)
        rrow.active = not (bake_disabled or no_baked_data)
        title = 'Baked ' + root_ch.name
        if bake_disabled:
            title += ' (Disabled)'
        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(nchui, 'expand_baked_data', text=title, icon_value=icon_value, emboss=False)
        else:
            rrow.label(text=title, icon_value=icon_value)

        if baked_image:
            icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            rrow = row.row(align=True)
            if is_bl_newer_than(2, 80):
                rrow.alignment = 'RIGHT'
            rrow.menu("NODE_MT_y_baked_image_menu", text='', icon=icon)

        if not nchui.expand_baked_data: continue

        row = col.row(align=True)
        row.label(text='', icon='BLANK1')
        bbox = row.box()
        bcol = bbox.column(align=True)

        if no_baked_data:
            bcol.label(text=root_ch.name + " channel hasn't been baked yet!", icon='ERROR')
            continue

        # Show list of bake targets of the channel
        if root_ch.name in chbts:

            # Check if bake target is chosen not by choice
            forced_bt = None
            if root_height_ch and not root_height_ch.use_height_as_bump and root_ch == root_normal_ch:
                forced_bt = get_normal_bake_target_without_height(yp, root_normal_ch)

            has_multiple_bts = len(chbts[root_ch.name]) > 1

            for bt in chbts[root_ch.name]:
                baked_node = nodes.get(bt.baked_node)

                if baked_node:

                    row = bcol.row(align=True)
                    row.active = (not bake_disabled or yp.enable_baked_outside) and bt.name == root_ch.bake_target_name

                    # Get bake target name and icons
                    packed = False
                    if baked_node.type == 'TEX_IMAGE' and baked_node.image:
                        title = baked_node.image.name
                        if baked_node.image.is_dirty: title += ' *'

                        icon_value = lib.get_icon('image')

                        if baked_node.image.packed_file: packed = True

                    elif baked_node.type == 'ATTRIBUTE':
                        title = bt.name
                        icon_value = lib.get_icon('vertex_color')

                    is_active_bt = bt.name == root_ch.bake_target_name and (not root_ch.disable_global_baked or yp.enable_baked_outside)

                    # Extra '(Active)' label
                    #if not bake_disabled and has_multiple_bts and (
                    #    bt == forced_bt or (not forced_bt and bt.name == root_ch.bake_target_name)
                    #):
                    #    title += ' (Active)'
                    if yp.preview_mode and is_active_bt:
                        ch_idx = get_channel_index(root_ch)
                        if ch_idx == yp.preview_mode_channel_index:
                            title += ' (Active)'

                    # Bake target entry
                    #row.label(text=title, icon_value=icon_value)
                    rrow = row.row(align=True)
                    rrow.context_pointer_set('channel', root_ch)
                    rrow.alignment = 'LEFT'
                    #rrow.scale_x = 0.95

                    # Bake target selection
                    #if forced_bt == None and has_multiple_bts:
                    #rrow.context_pointer_set('channel', root_ch)
                    icon = 'RADIOBUT_ON' if is_active_bt else 'RADIOBUT_OFF'
                    op = rrow.operator('wm.y_set_channel_active_bake_target', text='', emboss=False, icon=icon)
                    op.bake_target_name = bt.name
                    #else:
                    #    rrow.label(text='', icon='BLANK1')

                    op = rrow.operator('wm.y_set_channel_active_bake_target', text=title, emboss=False, icon_value=icon_value)
                    op.bake_target_name = bt.name

                    rrow = row.row(align=True)
                    rrow = row.row(align=True)
                    rrow.alignment = 'RIGHT'

                    # Packed icon
                    if packed: rrow.label(text='', icon='PACKAGE')

            # Disable baked
            if not yp.enable_baked_outside:
                row = bcol.row(align=True)
                #row.active = not yp.enable_baked_outside
                row.active = root_ch.disable_global_baked
                rrow = row.row(align=True)
                rrow.alignment = 'LEFT'
                is_active = root_ch.disable_global_baked and not yp.enable_baked_outside
                icon = 'RADIOBUT_ON' if is_active else 'RADIOBUT_OFF'
                rrow.label(text='', icon=icon)
                #title = 'Disable Baked '+root_ch.name
                title = 'Use Layer Stack'
                if yp.preview_mode and is_active:
                    ch_idx = get_channel_index(root_ch)
                    if ch_idx == yp.preview_mode_channel_index:
                        title += ' (Active)'
                if yp.enable_baked_outside:
                    rrow.label(text=title, icon='COLLAPSEMENU')
                else:
                    rrow.context_pointer_set('channel', root_ch)
                    rrow.operator('wm.y_toggle_channel_use_baked', text=title, icon='COLLAPSEMENU', emboss=False)
                rrow = row.row(align=True)

    # Save buttons
    row = layout.row(align=True)
    icon = 'FILE_TICK'
    row.operator('wm.y_save_all_baked_images', text='Save As All...', icon=icon).copy = False
    row.operator('wm.y_save_all_baked_images', text='Save Copies All...', icon=icon).copy = True

    # Remove baked data button
    icon = 'TRASH' if is_bl_newer_than(2, 80) else 'CANCEL'
    row.operator('wm.y_delete_baked_channel_images', text='', icon=icon)

    return

def draw_layers_ui(context, layout, node):
    #T = time.time()
    scene = context.scene
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()
    obj = context.object
    vcols = get_vertex_colors(obj)
    is_a_mesh = True if obj and obj.type == 'MESH' else False
    uv_layers = get_uv_layers(obj)

    # Check if uv is found
    #box = layout.box()
    box = layout

    # Check if parallax is enabled
    height_root_ch = get_root_height_channel(yp)
    enable_parallax = is_parallax_enabled(height_root_ch)

    # Check if any uv is missing
    uv_missings = []
    if is_a_mesh:

        # Check baked images
        if yp.baked_uv_name != '':
            uv_layer = uv_layers.get(yp.baked_uv_name)
            if not uv_layer and yp.baked_uv_name not in uv_missings:
                uv_missings.append(yp.baked_uv_name)

        # Check main uv of height channel
        height_ch = get_root_height_channel(yp)
        if height_ch and height_ch.enable_smooth_bump and height_ch.main_uv != '':
            uv_layer = uv_layers.get(height_ch.main_uv)
            if not uv_layer and height_ch.main_uv not in uv_missings:
                uv_missings.append(height_ch.main_uv)

        # Check layer and mask uv
        for layer in yp.layers:
            if layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'COLOR', 'BACKGROUND', 'EDGE_DETECT', 'MODIFIER', 'AO', 'PREV_LAYERS'} and layer.uv_name != '':
                uv_layer = uv_layers.get(layer.uv_name)
                if not uv_layer and layer.uv_name not in uv_missings:
                    uv_missings.append(layer.uv_name)
                    #entities.append(layer.name)

            for mask in layer.masks:
                if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER', 'AO'} and mask.uv_name != '':
                    uv_layer = uv_layers.get(mask.uv_name)
                    if not uv_layer and mask.uv_name not in uv_missings:
                        uv_missings.append(mask.uv_name)
                        #entities.append(mask.name)

    # Show missing UV buttons
    for uv_name in uv_missings:
        row = box.row(align=True)
        row.alert = True
        title = 'UV ' + uv_name + ' is missing or renamed!'
        row.operator("wm.y_fix_missing_uv", text=title, icon='ERROR').source_uv_name = uv_name
        #print(entities)
        row.alert = False

    # Check if tangent refresh is needed
    need_tangent_refresh = False
    if height_root_ch and is_tangent_sign_hacks_needed(yp):
        for uv in yp.uvs:
            if uv.name not in uv_layers: continue
            if TANGENT_SIGN_PREFIX + uv.name not in vcols:
                need_tangent_refresh = True
                break

    if need_tangent_refresh:
        row = box.row(align=True)
        row.alert = True
        row.operator('wm.y_refresh_tangent_sign_vcol', icon='FILE_REFRESH', text='Tangent Sign Hacks is missing!')
        row.alert = False

    # Get active item entity
    item_entity = ListItem.get_active_item_entity(yp)

    # Get layer, image and set context pointer
    layer = None
    source = None
    image = None
    vcol = None
    mask_image = None
    mask_vcol = None
    mask = None
    mask_idx = 0
    override_image = None
    override_vcol = None
    colorid_vcol = None
    colorid_col = None
    entity = None
    missing_source = False

    is_base_layer_selected = ypup.layer_list_mode in {'DYNAMIC', 'BOTH'} and yp.active_item_index == len(yp.list_items)-1

    if len(yp.layers) > 0 and not is_base_layer_selected:
        layer = yp.layers[yp.active_layer_index]
        layer = entity = yp.layers[yp.active_layer_index]

        if layer:
            layer_tree = get_tree(layer)
            # Check for active override channel
            for i, c in enumerate(layer.channels):
                if c.override and c.override_type != 'DEFAULT' and c.active_edit:
                    source = get_channel_source(c, layer)
                    if c.override_type == 'IMAGE':
                        override_image = source.image
                    elif c.override_type == 'VCOL':
                        override_vcol = get_vcol_from_source(obj, source)
                elif c.override_1 and c.override_1_type == 'IMAGE' and c.active_edit_1:
                    source = get_channel_source_1(c, layer)
                    if source and source.image:
                        override_image = source.image

            # Check for active mask
            for i, m in enumerate(layer.masks):
                if m.active_edit:
                    #mask = m
                    mask = entity = m
                    mask_idx = i
                    if m.use_baked:
                        mask_tree = get_mask_tree(m, layer_tree)
                        baked_source = mask_tree.nodes.get(m.baked_source)
                        if baked_source:
                            mask_image = baked_source.image
                    elif m.type == 'IMAGE':
                        source = get_mask_source(m)
                        mask_image = source.image
                    elif m.type == 'VCOL' and is_a_mesh:
                        source = get_mask_source(m)
                        mask_vcol = get_vcol_from_source(obj, source)
                    elif m.type == 'COLOR_ID' and is_a_mesh:
                        colorid_vcol = vcols.get(COLOR_ID_VCOL_NAME)
                        colorid_col = get_mask_color_id_color(mask)

            # Use layer image if there is no mask image
            #if not mask:
            source = get_layer_source(layer, layer_tree)
            if not source: missing_source = True
            if layer.type == 'IMAGE':
                image = source.image
            elif layer.type == 'VCOL' and is_a_mesh:
                vcol = get_vcol_from_source(obj, source)

    # Check if there's any expandable layer
    ypui.any_expandable_layers = any_expandable_layer(yp)

    # Set pointer for active layer and image
    if layer: box.context_pointer_set('layer', layer)
    if mask_image: box.context_pointer_set('image', mask_image)
    elif override_image: box.context_pointer_set('image', override_image)
    elif image: box.context_pointer_set('image', image)
    if entity: box.context_pointer_set('entity', entity)

    col = box.column()

    row = col.row()
    rcol = row.column()

    if ypup.layer_list_mode in {'CLASSIC', 'BOTH'}:
        rcol.template_list("NODE_UL_YPaint_layers", "", yp,
                "layers", yp, "active_layer_index", rows=6, maxrows=6)  

    if ypup.layer_list_mode in {'DYNAMIC', 'BOTH'}:
        if ypup.layer_list_mode == 'BOTH':
            rcol.operator('wm.y_refresh_list_items', icon='FILE_REFRESH', text='Refresh Items')
        rcol.template_list("NODE_UL_YPaint_list_items", "", yp,
                "list_items", yp, "active_item_index", rows=6, maxrows=6)  

    rcol = row.column(align=True)
    if is_bl_newer_than(4) and not ypup.ui_legacy_add_layer_menu:
        rcol.operator("wm.call_menu", text='', icon='ADD').name = "NODE_MT_y_new_layer_menu"
    elif is_bl_newer_than(2, 80):
        rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ADD')
    else: rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ZOOMIN')

    if layer:

        if has_children(layer): # or (image and not image.packed_file):

            if is_bl_newer_than(2, 80):
                rcol.operator("wm.y_remove_layer_menu", icon='REMOVE', text='')
            else: rcol.operator("wm.y_remove_layer_menu", icon='ZOOMOUT', text='')

        else: 
            if is_bl_newer_than(2, 80):
                c = rcol.operator("wm.y_remove_layer", icon='REMOVE', text='')
            else: c = rcol.operator("wm.y_remove_layer", icon='ZOOMOUT', text='')

            c.remove_children = False

        if is_top_member(layer):
            c = rcol.operator("wm.y_move_in_out_layer_group_menu", text='', icon='TRIA_UP')
            c.direction = 'UP'
            c.move_out = True
        else:
            upper_idx, upper_layer = get_upper_neighbor(layer)

            if upper_layer and (upper_layer.type == 'GROUP' or upper_layer.parent_idx != layer.parent_idx):
                c = rcol.operator("wm.y_move_in_out_layer_group_menu", text='', icon='TRIA_UP')
                c.direction = 'UP'
                c.move_out = False
            else: 
                c = rcol.operator("wm.y_move_layer", text='', icon='TRIA_UP')
                c.direction = 'UP'

        if is_bottom_member(layer):
            c = rcol.operator("wm.y_move_in_out_layer_group_menu", text='', icon='TRIA_DOWN')
            c.direction = 'DOWN'
            c.move_out = True
        else:
            lower_idx, lower_layer = get_lower_neighbor(layer)

            if lower_layer and (lower_layer.type == 'GROUP' and lower_layer.parent_idx == layer.parent_idx):
                c = rcol.operator("wm.y_move_in_out_layer_group_menu", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'
                c.move_out = False
            else: 
                c = rcol.operator("wm.y_move_layer", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'

    else:

        if is_bl_newer_than(2, 80):
            rcol.operator("wm.y_remove_layer", icon='REMOVE', text='')
        else: rcol.operator("wm.y_remove_layer", icon='ZOOMOUT', text='')

        rcol.operator("wm.y_move_layer", text='', icon='TRIA_UP').direction = 'UP'
        rcol.operator("wm.y_move_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'

    rcol.menu("NODE_MT_y_layer_list_special_menu", text='', icon='DOWNARROW_HLT')

    if any_subitem_exists(yp) and ypup.layer_list_mode != 'CLASSIC' :
        rcol.separator()
        if is_bl_newer_than(2, 80):
            rcol.popover("NODE_PT_y_list_item_option_popover", text='', icon='OUTLINER')
        else: rcol.menu("NODE_PT_y_list_item_option_menu", text='', icon='OOPS')

    if layer:
        layer_tree = get_tree(layer)
        source_tree = get_source_tree(layer)

        col = box.column()
        col.active = layer.enable and not is_parent_hidden(layer)

        # Get active vcol
        if mask_vcol: active_vcol = mask_vcol
        elif override_vcol: active_vcol = override_vcol
        elif colorid_vcol: active_vcol = colorid_vcol
        elif vcol: active_vcol = vcol
        else: active_vcol = None

        if missing_source:
            bbox = col.box()
            row = bbox.row(align=True)
            row.alert = True
            row.operator('wm.y_fix_missing_layer_source', text='Fix Missing Source', icon='ERROR')
            row.alert = False
            return

        mask_socket_input_name = ''
        if mask and source:
            mask_socket_input_name = get_mask_input_socket_name(mask, source)

        if colorid_vcol and colorid_vcol == get_active_vertex_color(obj) and obj.type == 'MESH' and obj.mode == 'EDIT':

            bbox = col.box()
            ccol = bbox.column()
            row = ccol.row(align=True)
            row.label(text='', icon_value=lib.get_icon('color'))
            row.label(text='Fill Color ID:')
            row = ccol.row(align=True)
            color = (colorid_col[0], colorid_col[1], colorid_col[2], 1.0)
            row.context_pointer_set('mask', mask)
            row.operator('mesh.y_vcol_fill_face_custom', text='Fill').color = color
            row.operator('mesh.y_vcol_fill_face_custom', text='Erase').color = (0.0, 0.0, 0.0, 1.0)
            #row = ccol.row(align=True)
            op = row.operator('mesh.y_select_faces_by_vcol', text='Select')
            op.color = color
            #op.deselect = False
            #op = row.operator('mesh.y_select_faces_by_vcol', text='Deselect')
            #op.color = color
            #op.deselect = True

        if obj.type == 'MESH' and active_vcol: # and layer.enable:

            if active_vcol != get_active_vertex_color(obj):
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('mesh.y_set_active_vcol', text='Fix Active '+get_vertex_color_label()+' Missmatch!', icon='ERROR').vcol_name = active_vcol.name
                row.alert = False

            elif obj.mode == 'EDIT' and active_vcol != colorid_vcol:
                ve = scene.ve_edit

                bbox = col.box()
                ccol = bbox.column()
                row = ccol.row(align=True)
                #row.label(text='', icon='GROUP_VCOL')
                row.label(text='', icon_value=lib.get_icon('vertex_color'))
                row.label(text=pgettext_iface('Fill ') + get_active_vertex_color(obj).name + ':')
                row = ccol.row(align=True)
                #row.prop(ve, 'fill_mode', text='') #, expand=True)
                #row.separator()
                row.operator('mesh.y_vcol_fill', text='White').color_option = 'WHITE'
                row.operator('mesh.y_vcol_fill', text='Black').color_option = 'BLACK'
                #if is_bl_newer_than(2, 80):
                #    row.operator("mesh.y_vcol_fill", text='Transparent').color_option = 'TRANSPARENT'
                row.separator()
                row.operator('mesh.y_vcol_fill', text='Color').color_option = 'CUSTOM'

                row.prop(ve, "color", text="", icon='COLOR')

            elif obj.mode == 'VERTEX_PAINT' and is_bl_newer_than(2, 92) and ((layer.type == 'VCOL' and not mask_vcol) or (mask_vcol and mask_socket_input_name == 'Alpha')) and not override_vcol:
                bbox = col.box()
                row = bbox.row(align=True)
                brush = context.tool_settings.vertex_paint.brush
                label = 'Toggle Eraser'
                if brush.name == eraser_names['VERTEX_PAINT']:
                    row.alert = True
                    label = 'Disable Eraser'
                row.operator('paint.y_toggle_eraser', text=label)

            elif obj.mode == 'SCULPT' and is_bl_newer_than(3, 2) and ((layer.type == 'VCOL' and not mask_vcol) or (mask_vcol and mask_socket_input_name == 'Alpha')) and not override_vcol:

                bbox = col.box()
                row = bbox.row(align=True)
                brush = context.tool_settings.sculpt.brush
                label = 'Toggle Eraser'
                if brush.name == eraser_names['SCULPT']:
                    row.alert = True
                    label = 'Disable Eraser'
                row.operator('paint.y_toggle_eraser', text=label)

        # Only works with experimental sculpt texture paint is turned on
        in_sculpt_texture_paint_mode = obj.mode == 'SCULPT' and ((
            hasattr(context.preferences.experimental, 'use_sculpt_texture_paint') and 
            context.preferences.experimental.use_sculpt_texture_paint
            ) or (
            # NOTE: Blender 5.2 likely will/already have custom build that can paint texture in sculpt mode
            is_bl_newer_than(5, 2) 
            ))

        in_texture_paint_mode = obj.mode == 'TEXTURE_PAINT'

        if obj.type == 'MESH' and ((layer.type == 'IMAGE' and not mask_image) or (mask_image and mask_socket_input_name == 'Alpha')) and not override_image:

            if is_bl_newer_than(4, 3) and in_texture_paint_mode:
                brush = context.tool_settings.image_paint.brush
                if brush and get_brush_image_tool(brush) != 'MASK':
                    bbox = col.box()
                    row = bbox.row(align=True)
                    label = 'Toggle Eraser'
                    if brush.name in tex_eraser_asset_names or (brush not in tex_default_brushes and brush.blend == 'ERASE_ALPHA'):
                        row.alert = True
                        label = 'Disable Eraser'
                    row.operator('paint.y_toggle_eraser', text=label)

            elif in_texture_paint_mode or in_sculpt_texture_paint_mode:
                bbox = col.box()
                row = bbox.row(align=True)
                if in_texture_paint_mode:
                    brush = context.tool_settings.image_paint.brush
                    label = 'Toggle Eraser'
                    if brush.name == eraser_names['TEXTURE_PAINT']:
                        row.alert = True
                        label = 'Disable Eraser'
                elif in_sculpt_texture_paint_mode:
                    brush = context.tool_settings.sculpt.brush
                    label = 'Toggle Eraser'
                    if brush.name == eraser_names['SCULPT']:
                        row.alert = True
                        label = 'Disable Eraser'
                row.operator('paint.y_toggle_eraser', text=label)

        ve = scene.ve_edit
        if is_bl_newer_than(4, 3) and in_texture_paint_mode:
            brush = context.tool_settings.image_paint.brush
            if brush and ((mask_image and mask_socket_input_name == 'Color') or override_image) and (brush.name in tex_eraser_asset_names or brush.blend == 'ERASE_ALPHA'):
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        elif in_texture_paint_mode or in_sculpt_texture_paint_mode:
            brush = context.tool_settings.image_paint.brush if in_texture_paint_mode else context.tool_settings.sculpt.brush
            if brush and ((mask_image and mask_socket_input_name == 'Color') or override_image) and brush.name == eraser_names[obj.mode]:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        elif obj.mode == 'VERTEX_PAINT' and is_bl_newer_than(2, 80): 
            brush = context.tool_settings.vertex_paint.brush
            if brush and mask_vcol and mask_socket_input_name == 'Color' and brush.name == eraser_names[obj.mode]:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        elif obj.mode == 'SCULPT' and is_bl_newer_than(3, 2): 
            brush = context.tool_settings.sculpt.brush
            if brush and mask_vcol and mask_socket_input_name == 'Color' and brush.name == eraser_names[obj.mode]:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        if obj.mode == 'EDIT':
            if obj.type == 'MESH' and obj.data.uv_layers.active:
                if layer.type != 'IMAGE' and is_layer_using_vector(layer) and obj.data.uv_layers.active.name != layer.uv_name:
                    bbox = col.box()
                    row = bbox.row(align=True)
                    row.alert = True
                    row.operator('wm.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')
                elif obj.data.uv_layers.active.name == TEMP_UV:
                    bbox = col.box()
                    row = bbox.row(align=True)
                    row.alert = True
                    row.operator('wm.y_back_to_original_uv', icon='EDITMODE_HLT', text='Edit Original UV')
        else:
            if yp.need_temp_uv_refresh or is_active_uv_map_missmatch_active_entity(obj, layer):
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('wm.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

        if layer.type == 'IMAGE' and is_a_mesh and is_bl_newer_than(3, 2):
            vdisp_layer_ch = get_vdisp_channel(layer)
            if vdisp_layer_ch and vdisp_layer_ch.enable:
                bbox = col.box()
                cbox = bbox.column()
                row = cbox.row(align=True)
                row.alert = obj.mode == 'SCULPT'
                row.operator('sculpt.y_sculpt_image', icon='SCULPTMODE_HLT', text='Sculpt Image')

        if is_a_mesh and is_layer_vdm(layer):
            active_uv_name = get_active_render_uv(obj)
            if active_uv_name != layer.uv_name:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('object.y_fix_vdm_missmatch_uv')
                row.alert = False

        if is_not_in_material_view() and ypup.enable_material_view_warning:
            bbox = col.box()
            row = bbox.row(align=True)
            row.alert = True
            row.operator('wm.y_switch_to_material_view', icon='MATERIAL_DATA')
            row.alert = False

        # Check if list items are empty
        if len(yp.list_items) == 0 and len(yp.layers) > 0:
            bbox = col.box()
            cbox = bbox.column()
            row = cbox.row(align=True)
            row.alert = True
            row.operator('wm.y_refresh_list_items', icon='FILE_REFRESH', text='Refresh Layer List')
            row.alert = False

        specific_ch = None
        specific_mask = None

        # NOTE: Individual Channel/Mask UI need more experiments and testing
        if False and ypup.layer_list_mode in {'DYNAMIC', 'BOTH'}:

            # Get active channel item
            for ch in layer.channels:
                if ch == item_entity:
                    specific_ch = ch
                    break

            # Get active mask item
            if not specific_ch:
                for mask in layer.masks:
                    if mask == item_entity:
                        specific_mask = mask
                        break

        # Source
        if not specific_mask and not specific_ch:
            draw_layer_source(context, col, layer, layer_tree, source, image, vcol, is_a_mesh)

            # Vector
            draw_layer_vector(context, col, layer, layer_tree, source, image, vcol, is_a_mesh)

        if not specific_mask:
            # Channels
            draw_layer_channels(context, col, layer, layer_tree, image, specific_ch)

        if not specific_ch:
            # Masks
            draw_layer_masks(context, col, layer, specific_mask)

    elif is_base_layer_selected:
        col = box.column()
        draw_base_layer_ui(context, col, yp, node)

    #print(get_addon_title()+': Layers UI is drawn in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def draw_test_ui(context, layout):
    ypup = get_user_preferences()
    if not ypup.developer_mode : return
    Test = get_package_module('.Test')
    if not Test: return
    Test.draw_test_ui(context, layout)

def draw_about_preset_ui(self, context):
    #return
    ypui = context.window_manager.ypui

    layout = self.layout
    row = layout.row(align=True)

    area_type = 'VIEW_3D' if context.area.type == 'VIEW_3D' else 'NODE_EDITOR'
    if context.area.type == area_type:
        if not getattr(ypui, 'expanded_about_ui_'+area_type):
            row.label(text='Help', icon='HELP')

        setattr(ypui, 'expanded_about_ui_'+area_type, False)

def draw_about_ui(self, context):
    ypui = context.window_manager.ypui
    area_type = 'VIEW_3D' if context.area.type == 'VIEW_3D' else 'NODE_EDITOR'
    setattr(ypui, 'expanded_about_ui_'+area_type, True)

    layout = self.layout

    col = layout.column()

    credits_ui = get_package_module('.credits_ui')

    if is_bl_newer_than(2, 80) and credits_ui:
        row = col.row(align=True)
        row.popover("NODE_PT_ypaint_about_popover", text='Credits', icon='HELP')
        if is_package_module_exists('.credits_ui'):
            row.popover('VIEW3D_PT_ypaint_support_ui', text='Support Us!', icon='FUND')
        #col.separator()

    # NOTE: Blender don't like if the addon creator get small money through UI :(((
    elif not is_installed_through_extension_platform():
        icon = 'FUND' if is_bl_newer_than(2, 80) else 'POSE_DATA'
        label = "Get "+get_addon_title()+" Plus!" if is_bl_newer_than(2, 80) else "Become a Sponsor!"
        col.operator('wm.url_open', text=label, icon=icon).url = "https://github.com/sponsors/ucupumar"
        #col.separator()

    ccol = col.column(align=True)
    ccol.operator('wm.url_open', text=get_addon_title()+' Wiki', icon='TEXT').url = 'https://ucupumar.github.io/ucupaint-wiki/'
    ccol.operator('wm.url_open', text=get_addon_title()+' GitHub', icon='SCRIPT').url = 'https://github.com/ucupumar/ucupaint'
    icon = 'COMMUNITY' if is_bl_newer_than(2, 80) else 'SEQ_SEQUENCER'
    ccol.operator('wm.url_open', text=get_addon_title()+' Discord Server', icon=icon).url = 'https://discord.gg/BdNfGGzQHh'

    addon_updater_ops = get_package_module('.addon_updater_ops')
    if addon_updater_ops:
        #col.separator()
        addon_updater_ops.draw_updater_options(context, col)

class NODE_PT_YPaint_legacy_about_ui(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = get_addon_title() + get_extra_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'TOOLS'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        draw_about_ui(self, context)

class NODE_PT_YPaint_about_ui(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = get_addon_title() + get_extra_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw_header_preset(self, context):
        draw_about_preset_ui(self, context)

    def draw(self, context):
        draw_about_ui(self, context)

class VIEW3D_PT_YPaint_legacy_about_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = get_addon_title() + get_extra_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        draw_about_ui(self, context)

class VIEW3D_PT_YPaint_about_ui(bpy.types.Panel):
    bl_label = get_addon_title() + get_extra_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header_preset(self, context):
        draw_about_preset_ui(self, context)

    def draw(self, context):
        draw_about_ui(self, context)

def update_ui_and_timer(context):
    wm = context.window_manager
    ypui = wm.ypui

    # Timer
    if wm.yptimer.time != '':
        print('INFO: Scene is updated in', '{:0.2f}'.format((time.time() - float(wm.yptimer.time)) * 1000), 'ms!')
        wm.yptimer.time = ''

    # NOTE: [HACK] Disable cache if delta time already pass the limit
    if ypui.use_cache:
        delta = get_node_slider_delta_ms()
        if delta > USE_CACHE_DELTA_MS:
            ypui.use_cache = False

    # Update ui props first
    update_yp_ui()

class BaseMainUI():
    def base_draw_header(self, context):
        wm = context.window_manager
        ypui = wm.ypui
        layout = self.layout
        node = get_active_ypaint_node()

        ypui.expanded_main_ui = False

        if not node:
            layout.label(text="No active " + get_addon_title() + " node!", icon='ERROR')
        else: layout.label(text=node.node_tree.name, icon='NODETREE')

        # Update timer and UI here
        update_ui_and_timer(context)

        # HACK: Create split layout to load all icons (Only for Blender 3.2+)
        if is_bl_newer_than(3, 2) and not wm.ypprops.all_icons_loaded:
            split = split_layout(layout, 1.0)
            row = split.row(align=True)
        else:
            row = layout.row(align=True)

        # HACK: Load all icons earlier so no missing icons possible (Only for Blender 3.2+)
        if is_bl_newer_than(3, 2) and not wm.ypprops.all_icons_loaded:
            wm.ypprops.all_icons_loaded = True
            layout.label(text='', icon='BLANK1')
            folder = lib.get_icon_folder()
            # Add extra splits so the actual icons aren't actually visible
            s1 = split_layout(split, 1.0)
            s1.label(text='', icon='BLANK1')
            s2 = split_layout(s1, 1.0)
            s2.label(text='', icon='BLANK1')
            invisible_row = s2.row(align=False)
            # Load all icons on invisible area of the screen
            for i, f in enumerate(os.listdir(folder)):
                if f.endswith('.png'):
                    icon_name = f.replace('_icon.png', '')
                    invisible_row.label(text='', icon_value=lib.get_icon(icon_name))

    def base_draw_header_preset(self, context):
        ypui = context.window_manager.ypui
        ypup = get_user_preferences()
        node = get_active_ypaint_node()
        if not node: return
        yp = node.node_tree.yp

        layout = self.layout

        row = layout.row(align=True)

        if ypui.expanded_main_ui and not yp.sculpt_mode:

            if not ypup.ui_non_popup_settings:

                connection_warning = False
                for ch in yp.channels:
                    if is_output_unconnected(node, ch) and not ch.disable_unconnected_warning:
                        connection_warning = True
                        break

                icon_value = lib.get_icon('ERROR') if connection_warning else lib.get_icon('channels')
                row.popover("NODE_PT_ypaint_channel_popover", text='', icon_value=icon_value)

                # NOTE: HACK: Switch between alternative popovers so the popover always closed after baking
                gloset = yp.bake_target_global_settings
                if gloset.baked_counters % 2 == 1:
                    row.popover("NODE_PT_ypaint_bake_target_alt_popover", text='', icon_value=lib.get_icon('bake'))
                else: row.popover("NODE_PT_ypaint_bake_target_popover", text='', icon_value=lib.get_icon('bake'))

            icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            row.menu("NODE_MT_ypaint_special_menu", text='', icon=icon)

    def base_draw(self, context):
        draw_main_ui(context, self.layout)

class VIEW3D_PT_YPaint_main_ui(bpy.types.Panel, BaseMainUI):
    bl_label = ' '
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    #bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_main_ui(bpy.types.Panel, BaseMainUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = ' '
    bl_region_type = 'UI'
    bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_legacy_main_ui(bpy.types.Panel, BaseMainUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = ' '
    bl_region_type = 'TOOLS'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class VIEW3D_PT_YPaint_legacy_main_tools(bpy.types.Panel, BaseMainUI):
    bl_space_type = 'VIEW_3D'
    bl_label = ' '
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class BaseObjectMaterialSettingsUI():
    def base_draw(self, context):

        obj = context.object
        mat = obj.active_material

        layout = self.layout

        ### Object settings

        #icon = 'TRIA_DOWN' if ypui.show_object else 'TRIA_RIGHT'
        #row = layout.row(align=True)
        #rrow = row.row(align=True)
        text_object = pgettext_iface('Object: ')
        if obj: text_object += obj.name
        else: text_object += '-'

        #if is_bl_newer_than(2, 80):
        #    rrow.alignment = 'LEFT'
        #    rrow.scale_x = 0.95
        #    rrow.prop(ypui, 'show_object', emboss=False, text=text_object, icon=icon)
        #else:
        #    rrow.prop(ypui, 'show_object', emboss=False, text='', icon=icon)
        #    rrow.label(text=text_object)

        #rrow = row.row(align=True)
        #rrow.alignment = 'RIGHT'
        #if not is_bl_newer_than(2, 80):
        #    rrow.menu("NODE_MT_ypaint_about_menu", text='', icon='INFO')
        #else: 
        #    row.popover("NODE_PT_ypaint_about_popover", text='', icon='HELP')
        #    if is_package_module_exists('.credits_ui'):
        #        row.popover('VIEW3D_PT_ypaint_support_ui', text='', icon='FUND')

        #header, panel = self.layout.panel("MAT_YP_ObjectSettingsPanel", default_closed=True)
        #header.label(text=text_object, icon_value=lib.get_icon('object_data'))
        #if panel:
        box = layout
        #box = layout.box()
        #box = panel
        col = box.column()
        row = split_layout(col, 0.6)
        row.label(text='Object Index ('+obj.name+'):')
        row.prop(obj, 'pass_index', text='')

        ### Material settings

        #icon = 'TRIA_DOWN' if ypui.show_materials else 'TRIA_RIGHT'
        #rrow = row.row(align=True)
        text_material = pgettext_iface('Material: ')
        if mat: text_material += mat.name
        else: text_material += '-'

        #if is_bl_newer_than(2, 80):
        #    rrow.alignment = 'LEFT'
        #    rrow.scale_x = 0.95
        #    rrow.prop(ypui, 'show_materials', emboss=False, text=text_material, icon=icon)
        #else:
        #    rrow.prop(ypui, 'show_materials', emboss=False, text='', icon=icon)
        #    rrow.label(text=text_material)

        #header, panel = self.layout.panel("MAT_YP_MaterialSettingsPanel", default_closed=True)
        #header.label(text=text_material, icon_value=lib.get_icon('material'))

        ##if ypui.show_materials:
        #if panel:
        is_sortable = len(obj.material_slots) > 1
        rows = 2
        if (is_sortable):
            rows = 4
        box = layout
        #box = layout.box()
        #box = panel
        row = box.row()
        row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index", rows=rows)
        col = row.column(align=True)
        if is_bl_newer_than(2, 80):
            col.operator("object.material_slot_add", icon='ADD', text="")
            col.operator("object.material_slot_remove", icon='REMOVE', text="")
        else:
            col.operator("object.material_slot_add", icon='ZOOMIN', text="")
            col.operator("object.material_slot_remove", icon='ZOOMOUT', text="")

        col.menu("MATERIAL_MT_y_special_menu", icon='DOWNARROW_HLT', text="")

        if is_sortable:
            col.separator()

            col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
            col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

        if obj.mode == 'EDIT':
            row = box.row(align=True)
            row.operator("object.material_slot_assign", text="Assign")
            row.operator("object.material_slot_select", text="Select")
            row.operator("object.material_slot_deselect", text="Deselect")

        row = box.row(align=True)
        mat = get_active_material()
        mui = get_material_ui(mat)
        if mui:
            icon = 'DOWNARROW_HLT' if mui.expand_content else 'RIGHTARROW'
            row.prop(mui, 'expand_content', emboss=False, text='', icon=icon)
        row.template_ID(obj, "active_material", new="material.new")

        if mui and mui.expand_content:
            row = box.row(align=True)
            row.label(text='', icon='BLANK1')
            col = row.column(align=False)

            if not is_bl_newer_than(2, 80):
                rrow = col.row(align=True)
                rrow.label(text='Alpha Blend:')
                rrow.prop(mat.game_settings, 'alpha_blend', text='')

            elif not is_bl_newer_than(4, 2):

                rrow = col.row(align=True)
                rrow.label(text='Blend Mode:')
                rrow.prop(mat, 'blend_method', text='')

                rrow = col.row(align=True)
                rrow.label(text='Shadow Mode:')
                rrow.prop(mat, 'shadow_method', text='')
            else:

                # NOTE: Displacement setup probably need to be rethinked again before showing this option
                #rrow = col.row(align=True)
                #rrow.label(text='Displacement:')
                #rrow.prop(mat, 'displacement_method', text='')

                rrow = col.row(align=True)
                rrow.label(text='Render Method:')
                rrow.prop(mat, 'surface_render_method', text='')

                rrow = col.row(align=True)
                rrow.label(text='Transparent Shadows:')
                rrow.prop(mat, 'use_transparent_shadow', text='')

        #node = get_active_ypaint_node()
        #if not node: return

        #### Channel Settings

        #header, panel = self.layout.panel("MAT_YP_ChannelSettingsPanel", default_closed=True)
        #header.label(text="Channels", icon_value=lib.get_icon('channels'))
        #if panel:
        #    draw_root_channels_ui(context, panel, node)

        #### Bake Target Settings

        #header, panel = self.layout.panel("MAT_YP_ChannelBakeTargetsPanel", default_closed=True)
        #header.label(text="Bake Targets", icon_value=lib.get_icon('bake'))
        #if panel:
        #    draw_bake_targets_ui(context, panel, node)

class VIEW3D_PT_YPaint_legacy_obj_mat_settings_tools(bpy.types.Panel, BaseObjectMaterialSettingsUI):
    bl_space_type = 'VIEW_3D'
    bl_label = get_addon_title() + get_extra_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        self.base_draw(context)

class VIEW3D_PT_YPaint_obj_mat_settings_ui(bpy.types.Panel, BaseObjectMaterialSettingsUI):
    bl_label = 'Object & Material'
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        self.base_draw(context)

class BaseChannelSettingsUI():
    def base_draw_header(self, context):
        ypui = bpy.context.window_manager.ypui
        ypui.expanded_settings_ui = False

    def base_draw_header_preset(self, context):
        ypui = bpy.context.window_manager.ypui

    def base_draw(self, context):
        node = get_active_ypaint_node()
        ypui = bpy.context.window_manager.ypui
        ypui.expanded_settings_ui = True

        layout = self.layout

        draw_root_channels_ui(context, layout, node)

class VIEW3D_PT_YPaint_channel_settings_ui(bpy.types.Panel, BaseChannelSettingsUI):
    bl_label = 'Channel Settings'
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_channel_settings_ui(bpy.types.Panel, BaseChannelSettingsUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = 'Channel Settings'
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_legacy_channel_settings_ui(bpy.types.Panel, BaseChannelSettingsUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = 'Channel Settings'
    bl_region_type = 'TOOLS'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class VIEW3D_PT_YPaint_legacy_channel_settings_tools(bpy.types.Panel, BaseChannelSettingsUI):
    bl_space_type = 'VIEW_3D'
    bl_label = 'Channel Settings'
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        self.base_draw(context)

class BaseBakeTargetSettingsUI():
    def base_draw_header(self, context):
        ypui = bpy.context.window_manager.ypui
        ypui.expanded_settings_ui = False

    def base_draw_header_preset(self, context):
        ypui = bpy.context.window_manager.ypui

    def base_draw(self, context):
        node = get_active_ypaint_node()
        ypui = bpy.context.window_manager.ypui
        ypui.expanded_settings_ui = True

        layout = self.layout

        draw_bake_targets_ui(context, layout, node)

class VIEW3D_PT_YPaint_bake_target_settings_ui(bpy.types.Panel, BaseBakeTargetSettingsUI):
    bl_label = 'Bake Target Settings'
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_bake_target_settings_ui(bpy.types.Panel, BaseBakeTargetSettingsUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = 'Bake Target Settings'
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class NODE_PT_YPaint_legacy_bake_target_settings_ui(bpy.types.Panel, BaseBakeTargetSettingsUI):
    bl_space_type = 'NODE_EDITOR'
    bl_label = 'Bake Target Settings'
    bl_region_type = 'TOOLS'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw_header(self, context):
        self.base_draw_header(context)

    def draw_header_preset(self, context):
        self.base_draw_header_preset(context)

    def draw(self, context):
        self.base_draw(context)

class VIEW3D_PT_YPaint_legacy_bake_target_settings_tools(bpy.types.Panel, BaseBakeTargetSettingsUI):
    bl_space_type = 'VIEW_3D'
    bl_label = 'Bake Target Settings'
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        if not ypup.ui_non_popup_settings: return False
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        sculpt_mode = yp.sculpt_mode if yp else False
        return yp and not use_baked and not sculpt_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        self.base_draw(context)

class VIEW3D_PT_YPaint_stats_ui(bpy.types.Panel):
    bl_label = 'Stats'
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp if node else None
        use_baked = yp.use_baked if yp else False
        return yp and not use_baked and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        draw_stats_ui(context, self.layout, get_active_ypaint_node())

class VIEW3D_PT_YPaint_test_ui(bpy.types.Panel):
    bl_label = 'Test'
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        ypup = get_user_preferences()
        return ypup.developer_mode and context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        draw_test_ui(context, self.layout)

def is_output_unconnected(node, root_ch):
    yp = node.node_tree.yp
    outp = node.outputs.get(root_ch.name)
    if not outp: return False
    unconnected = len(outp.links) == 0 and not (yp.use_baked and yp.enable_baked_outside)
    return unconnected

def is_height_input_connected_but_has_no_start_process(node, root_ch):
    yp = node.node_tree.yp
    if root_ch.special_type != 'HEIGHT': return False
    socket = node.inputs.get(root_ch.name + io_suffix['HEIGHT'])
    connected = len(socket.links) > 0 if socket else False
    start_bump_process = node.node_tree.nodes.get(root_ch.start_bump_process)
    if connected and not start_bump_process:
        return True
    return False

def is_height_input_unconnected_but_has_start_process(node, root_ch):
    yp = node.node_tree.yp
    if root_ch.special_type != 'HEIGHT': return False
    socket = node.inputs.get(root_ch.name + io_suffix['HEIGHT'])
    unconnected = len(socket.links) == 0 if socket else True
    start_bump_process = node.node_tree.nodes.get(root_ch.start_bump_process)
    if unconnected and start_bump_process:
        return True
    return False

class NODE_UL_YPaint_bake_targets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        tree = item.id_data
        baked_node = tree.nodes.get(item.baked_node)
        image = baked_node.image if baked_node and baked_node.type == 'TEX_IMAGE' else None

        row = layout.row()

        icon_value = lib.get_icon('bake')
        if item.data_type == 'IMAGE':
            if image:
                icon_value = lib.get_icon('image')
        elif item.data_type == 'VCOL':
            obj = context.object
            if obj:
                vcols = get_vertex_colors(obj)
                if item.name in vcols:
                    icon_value = lib.get_icon('vertex_color')

        if image:
            row.prop(image, 'name', text='', emboss=False, icon_value=icon_value)

            # Asterisk icon to indicate dirty image
            if image.is_dirty:
                row.label(text='', icon_value=lib.get_icon('asterisk'))

            # Indicate packed image
            if image.packed_file:
                row.label(text='', icon='PACKAGE')
            
        else: 
            row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)

class NODE_UL_YPaint_simple_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        icon_value = lib.get_icon(lib.channel_custom_icon_dict[item.type])
        row.label(text=item.name, icon_value=icon_value)

class NODE_UL_YPaint_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_ypaint_node()
        inputs = group_node.inputs
        outputs = group_node.outputs
        yp = group_node.node_tree.yp
        ypup = get_user_preferences()

        inp = inputs.get(item.name)

        row = layout.row()

        icon_value = lib.get_icon(lib.channel_custom_icon_dict[item.type])
        row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)

        # NOTE: Option for background only available for classic layer list mode
        #if ypup.layer_list_mode != 'CLASSIC': return

        if not yp.use_baked or (item.no_layer_using and not (yp.use_baked and yp.enable_baked_outside)):
            if item.type == 'RGB':
                row = row.row(align=True)

            if len(inp.links) == 0:
                if item.type == 'VALUE':
                    rrow = row.row(align=True)
                    if is_bl_newer_than(2, 80): rrow.scale_x = 0.8
                    rrow.prop(inp, 'default_value', text='') #, emboss=False)
                elif item.type == 'RGB':
                    row.prop(inp, 'default_value', text='', icon='COLOR')
            else:
                row.label(text='', icon='LINKED')

            if is_output_unconnected(group_node, item) and not item.disable_unconnected_warning:
                row.label(text='', icon='ERROR')

            if ypup.developer_mode and item.type=='RGB' and item.enable_alpha:
                inp_alpha = inputs.get(item.name + io_suffix['ALPHA'])
                if len(inp_alpha.links) == 0:
                    row.prop(inp_alpha, 'default_value', text='')
                else: row.label(text='', icon='LINKED')

def any_subitem_in_layer(layer):
    yp = layer.id_data.yp

    for mask in layer.masks:
        if mask.enable:
            return True

    color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)

    for i, ch in enumerate(layer.channels):
        ch_enabled = ch.enable or (ch == alpha_ch and color_ch.enable)
        if not ch_enabled: continue

        root_ch = yp.channels[i]

        if ch.override and ch.override_type != 'DEFAULT':
            return True

    return False

def is_layer_expandable(layer):
    yp = layer.id_data.yp

    if yp.enable_expandable_subitems:
        if any_subitem_in_layer(layer):
            return True

    children = get_list_of_direct_children(layer)
    if len(children) > 0:
        return True

    return False

def any_expandable_layer(yp):
    for layer in yp.layers:
        if is_layer_expandable(layer):
            return True

    return False

def any_subitem_exists(yp):
    for layer in yp.layers:
        if any_subitem_in_layer(layer):
            return True

    return False

def get_eye_icon(visible=True):
    if not is_bl_newer_than(2, 80):
        return 'RESTRICT_VIEW_OFF' if visible else 'RESTRICT_VIEW_OFF'

    return 'HIDE_OFF' if visible else 'HIDE_ON'

def get_ch_type_icon_prefix(layer, ch):
    if get_layer_channel_type(layer, ch) == 'RGB': return 'rgb_'
    if get_layer_channel_type(layer, ch) == 'VALUE': return 'value_'
    if get_layer_channel_type(layer, ch) == 'VECTOR': return 'vector_'
    return ''

def get_ch_override_label(layer, ch):
    yp = ch.id_data.yp

    label = channel_override_labels[ch.override_type]

    root_ch = yp.channels[get_layer_channel_index(layer, ch)]
    channel_label = root_ch.name

    label += ' ('+channel_label+')'

    return label

def layer_listing(layout, layer, show_expand=False):
    yp = layer.id_data.yp
    layer_tree = get_tree(layer)
    obj = bpy.context.object
    ypup = get_user_preferences()
    ypui = bpy.context.window_manager.ypui

    color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)

    is_active = not is_parent_hidden(layer) and layer.enable

    # Layer who doesn't use the active preview channel will be inactive
    if yp.preview_mode: # and yp.preview_mode_type != 'SPECIFIC_MASK':
        try: preview_ch = yp.channels[yp.preview_mode_channel_index]
        except: preview_ch = None

        if preview_ch:
            ch_idx = get_channel_index(preview_ch)
            try: ch = layer.channels[ch_idx]
            except: ch = None

            # Height layer that used for normal bump will be active when previewing final normal channel
            # TODO: Previewing layer height channel as normal preview
            root_normal_ch, root_height_ch = get_normal_height_ch_pairs(yp)
            normal_ch, height_ch = get_layer_normal_height_ch_pairs(layer)
            if yp.preview_mode_type == 'CHANNEL' and normal_ch and ch == normal_ch and root_height_ch.use_height_as_bump:
                ch = height_ch
                preview_ch = root_height_ch

            # Color layer will also be active when previewing alpha channel
            root_color_ch, root_alpha_ch = get_color_alpha_ch_pairs(yp)
            if alpha_ch and ch == alpha_ch and not ch.enable:
                ch = color_ch
                preview_ch = root_color_ch

            if ch:
                is_active = get_channel_enabled(ch, layer, preview_ch)

    master = layout.row(align=True)

    if layer.parent_idx != -1:
        depth = get_layer_depth(layer)
        for i in range(depth):
            master.label(text='', icon='BLANK1')

    if show_expand:
        if is_layer_expandable(layer):
            icon = 'DOWNARROW_HLT' if layer.expand_subitems else 'RIGHTARROW'
            master.prop(layer, 'expand_subitems', icon=icon, text='', emboss=False)
        elif ypui.any_expandable_layers:
            master.label(text='', icon='BLANK1')

    # Try to get image
    image = None
    if layer.type == 'IMAGE':
        source = get_layer_source(layer, layer_tree)
        image = source.image

    # Try to get vertex color
    #vcol = None
    #if layer.type == 'VCOL':
    #    source = get_layer_source(layer, layer_tree)
    #    vcol = get_vcol_from_source(obj, source)

    show_inline_subitems = (
        not show_expand or 
        (yp.enable_inline_subitems and not (layer.expand_subitems and yp.enable_expandable_subitems)) or 
        (not yp.enable_inline_subitems and not yp.enable_expandable_subitems)
        )

    all_overrides = []
    selectable_overrides = []
    active_override = None
    override_idx = 0
    if show_inline_subitems:
        for i, c in enumerate(layer.channels):
            root_ch = yp.channels[i]
            #if not c.enable: continue
            if (c.override and c.override_type != 'DEFAULT') or (c.override_1 and c.override_1_type != 'DEFAULT'):
                if c.enable or (c == alpha_ch and color_ch.enable): 
                    selectable_overrides.append(c)
                all_overrides.append(c)
                if c.active_edit or c.active_edit_1:
                    active_override = c
                if c.active_edit_1:
                    override_idx = 1

    # Try to get image masks
    all_masks = []
    selectable_masks = []
    active_mask = None
    if show_inline_subitems:
        for m in layer.masks:
            #if m.type in {'IMAGE', 'VCOL'}:
            if m.enable: selectable_masks.append(m)
            all_masks.append(m)
            if m.active_edit:
                active_mask = m
                active_override = m

    row = master.row(align=True)

    # Image icon
    if len(selectable_masks) == 0 and len(selectable_overrides) == 0:
        row = master.row(align=True)
        row.active = is_active
        if image and (image.yia.is_image_atlas or image.yua.is_udim_atlas): 
            if ypup.use_image_preview and image.preview: 
                #if not image.preview: image.preview_ensure()
                row.prop(layer, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            else: row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('image'))
        elif image: 
            if ypup.use_image_preview and image.preview: 
                #if not image.preview: image.preview_ensure()
                row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            else: row.prop(image, 'name', text='', emboss=False, icon_value=lib.get_icon('image'))
        elif layer.type == 'VCOL': 
            row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
        elif layer.type == 'HEMI': 
            row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('hemi'))
        elif layer.type in {'EDGE_DETECT', 'AO'}:
            row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('edge_detect'))
        elif layer.type == 'COLOR': 
            row.prop(layer, 'name', text='', emboss=False, icon='COLOR')
        elif layer.type == 'PREV_LAYERS': 
            icon_name = 'modifier' if len(layer.modifiers) > 0 else 'COLLAPSEMENU'
            row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon(icon_name))
        elif layer.type == 'BACKGROUND': row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('background'))
        elif layer.type == 'GROUP': row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('group'))
        elif layer.type == 'INPUT_BUNDLE': row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('NODE_SOCKET_BUNDLE'))
        else: 
            row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('texture'))
    else:
        if active_override:
            ae_prop = 'active_edit'
            if override_idx == 1 and hasattr(active_override, 'active_edit_1'):
                ae_prop = 'active_edit_1'
            row.active = False
            if image: 
                if ypup.use_image_preview and image.preview:
                    #if not image.preview: image.preview_ensure()
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=image.preview.icon_id)
                else: 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('image'))
            elif layer.type == 'VCOL': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
            elif layer.type == 'COLOR': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon='COLOR')
            elif layer.type == 'PREV_LAYERS': 
                icon_name = 'modifier' if len(layer.modifiers) > 0 else 'COLLAPSEMENU'
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon(icon_name))
            elif layer.type == 'HEMI': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('hemi'))
            elif layer.type in {'EDGE_DETECT', 'AO'}:
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('edge_detect'))
            elif layer.type == 'BACKGROUND': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('background'))
            elif layer.type == 'GROUP': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('group'))
            elif layer.type == 'INPUT_BUNDLE': 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('NODE_SOCKET_BUNDLE'))
            else: 
                row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('texture'))
        else:
            if image: 
                if ypup.use_image_preview and image.preview: 
                    #if not image.preview: image.preview_ensure()
                    row.label(text='', icon_value=image.preview.icon_id)
                else: row.label(text='', icon_value=lib.get_icon('image'))
            elif layer.type == 'VCOL': 
                row.label(text='', icon_value=lib.get_icon('vertex_color'))
            elif layer.type == 'COLOR': 
                row.label(text='', icon='COLOR')
            elif layer.type == 'PREV_LAYERS': 
                icon_name = 'modifier' if len(layer.modifiers) > 0 else 'COLLAPSEMENU'
                row.label(text='', icon_value=lib.get_icon(icon_name))
            elif layer.type == 'HEMI': 
                row.label(text='', icon_value=lib.get_icon('hemi'))
            elif layer.type in {'EDGE_DETECT', 'AO'}:
                row.label(text='', icon_value=lib.get_icon('edge_detect'))
            elif layer.type == 'BACKGROUND': 
                row.label(text='', icon_value=lib.get_icon('background'))
            elif layer.type == 'GROUP': 
                row.label(text='', icon_value=lib.get_icon('group'))
            elif layer.type == 'INPUT_BUNDLE': 
                row.label(text='', icon_value=lib.get_icon('NODE_SOCKET_BUNDLE'))
            else: 
                row.label(text='', icon_value=lib.get_icon('texture'))

    # Override icons
    active_override_image = None
    #active_override_vcol = None
    override_ch = None
    for c in selectable_overrides:
        if c.override and c.override_type != 'DEFAULT' and c.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
            row = master.row(align=True)
            row.active = c.active_edit
            if c.active_edit:
                src = get_channel_source(c, layer)
                override_ch = c
                if src and c.override_type == 'IMAGE':
                    active_override_image = src.image
                    if ypup.use_image_preview and src.image.preview: 
                        #if not src.image.preview: src.image.preview_ensure()
                        row.label(text='', icon_value=src.image.preview.icon_id)
                    else: 
                        icon_name = get_ch_type_icon_prefix(layer, c) + 'image'
                        row.label(text='', icon_value=lib.get_icon(icon_name))
                elif c.override_type == 'VCOL':
                    #active_override_vcol = c
                    icon_name = get_ch_type_icon_prefix(layer, c) + 'vertex_color'
                    row.label(text='', icon_value=lib.get_icon(icon_name))
                else:
                    icon_name = get_ch_type_icon_prefix(layer, c) + 'texture'
                    row.label(text='', icon_value=lib.get_icon(icon_name))
            else:
                if c.override_type == 'IMAGE':
                    src = get_channel_source(c, layer)
                    if src: 
                        if ypup.use_image_preview and src.image.preview: 
                            #if not src.image.preview: src.image.preview_ensure()
                            row.prop(c, 'active_edit', text='', emboss=False, icon_value=src.image.preview.icon_id)
                        else: 
                            icon_name = get_ch_type_icon_prefix(layer, c) + 'image'
                            row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(icon_name))
                elif c.override_type == 'VCOL':
                    icon_name = get_ch_type_icon_prefix(layer, c) + 'vertex_color'
                    row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(icon_name))
                else:
                    icon_name = get_ch_type_icon_prefix(layer, c) + 'texture'
                    row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(icon_name))

        if c.override_1 and c.override_1_type != 'DEFAULT' and c.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
            row = master.row(align=True)
            row.active = c.active_edit_1
            if c.active_edit_1:
                src = get_channel_source_1(c, layer)
                override_ch = c
                if src and c.override_1_type == 'IMAGE':
                    active_override_image = src.image
                    if ypup.use_image_preview and src.image.preview: 
                        #if not src.image.preview: src.image.preview_ensure()
                        row.label(text='', icon_value=src.image.preview.icon_id)
                    else: 
                        row.label(text='', icon_value=lib.get_icon('vector_image'))
            else:
                if c.override_1_type == 'IMAGE':
                    src = get_channel_source_1(c, layer)
                    if src: 
                        if ypup.use_image_preview and src.image.preview: 
                            #if not src.image.preview: src.image.preview_ensure()
                            row.prop(c, 'active_edit_1', text='', emboss=False, icon_value=src.image.preview.icon_id)
                        else: row.prop(c, 'active_edit_1', text='', emboss=False, icon_value=lib.get_icon('vector_image'))

    # Mask icons
    active_mask_image = None
    active_vcol_mask = None
    mask = None
    for m in selectable_masks:
        mask_tree = get_mask_tree(m, layer_tree)
        row = master.row(align=True)
        row.active = m.active_edit
        if m.active_edit:
            mask = m
            src = mask_tree.nodes.get(m.source)
            if m.type == 'IMAGE':
                active_mask_image = src.image
                if ypup.use_image_preview and src.image.preview: 
                    #if not src.image.preview: src.image.preview_ensure()
                    row.label(text='', icon_value=src.image.preview.icon_id)
                else: 
                    socket_input_name = get_mask_input_socket_name(m, src) if src else ''
                    if socket_input_name == 'Alpha':
                        row.label(text='', icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[socket_input_name]+'image'))
                    elif m.swizzle_input_mode in {'R', 'G', 'B'}:
                        row.label(text='', icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[m.swizzle_input_mode]+'image'))
                    else: row.label(text='', icon_value=lib.get_icon('image'))
            elif m.type == 'VCOL':
                active_vcol_mask = m
                socket_input_name = get_mask_input_socket_name(m, src) if src else ''
                if socket_input_name == 'Alpha':
                    row.label(text='', icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[socket_input_name]+'vertex_color'))
                elif m.swizzle_input_mode in {'R', 'G', 'B'}:
                    row.label(text='', icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[m.swizzle_input_mode]+'vertex_color'))
                else: row.label(text='', icon_value=lib.get_icon('vertex_color'))
            elif m.type == 'HEMI':
                row.label(text='', icon_value=lib.get_icon('hemi'))
            elif m.type == 'OBJECT_INDEX':
                row.label(text='', icon_value=lib.get_icon('object_index'))
            elif m.type in {'EDGE_DETECT', 'AO'}:
                row.label(text='', icon_value=lib.get_icon('edge_detect'))
            elif m.type == 'COLOR_ID':
                row.label(text='', icon_value=lib.get_icon('color'))
            elif m.type == 'BACKFACE':
                row.label(text='', icon_value=lib.get_icon('backface'))
            elif m.type == 'MODIFIER':
                row.label(text='', icon_value=lib.get_icon('modifier'))
            else:
                row.label(text='', icon_value=lib.get_icon('texture'))
        else:
            if m.type == 'IMAGE':
                src = mask_tree.nodes.get(m.source)
                if ypup.use_image_preview and src.image.preview: 
                    #if not src.image.preview: src.image.preview_ensure()
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=src.image.preview.icon_id)
                else: 
                    socket_input_name = get_mask_input_socket_name(m, src)
                    if socket_input_name == 'Alpha':
                        row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[socket_input_name]+'image'))
                    elif m.swizzle_input_mode in {'R', 'G', 'B'}:
                        row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[m.swizzle_input_mode]+'image'))
                    else: row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('image'))
            elif m.type == 'VCOL':
                src = mask_tree.nodes.get(m.source)
                socket_input_name = get_mask_input_socket_name(m, src)
                if socket_input_name == 'Alpha':
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[socket_input_name]+'vertex_color'))
                elif m.swizzle_input_mode in {'R', 'G', 'B'}:
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[m.swizzle_input_mode]+'vertex_color'))
                else: row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
            elif m.type == 'HEMI':
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('hemi'))
            elif m.type == 'OBJECT_INDEX':
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('object_index'))
            elif m.type in {'EDGE_DETECT', 'AO'}:
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('edge_detect'))
            elif m.type == 'COLOR_ID':
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('color'))
            elif m.type == 'BACKFACE':
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('backface'))
            elif m.type == 'MODIFIER':
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('modifier'))
            else:
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('texture'))

    # Debug parent
    #row.label(text=str(index) + ' (' + str(layer.parent_idx) + ')')

    # Active image/layer label
    if len(selectable_masks) > 0 or len(selectable_overrides) > 0:
        row = master.row(align=True)
        row.active = is_active
        if override_ch:
            if active_override_image:
                if active_override_image.yia.is_image_atlas or active_override_image.yua.is_udim_atlas:
                    #row.label(text='Image Atlas Override')
                    row.label(text=active_override_image.name)
                else: row.prop(active_override_image, 'name', text='', emboss=False)
            elif override_ch.override_type == 'VCOL':
                row.prop(override_ch, 'override_vcol_name', text='', emboss=False)
            else:
                row.label(text=get_ch_override_label(layer, override_ch))
        elif active_mask_image:
            if active_mask_image.yia.is_image_atlas or active_mask_image.yua.is_udim_atlas:
                row.prop(mask, 'name', text='', emboss=False)
            else: row.prop(active_mask_image, 'name', text='', emboss=False)
        elif active_vcol_mask:
            row.prop(active_vcol_mask, 'name', text='', emboss=False)
        elif active_mask:
            row.prop(active_mask, 'name', text='', emboss=False)
        else: 
            if image and not image.yia.is_image_atlas and not image.yua.is_udim_atlas: 
                row.prop(image, 'name', text='', emboss=False)
            else: row.prop(layer, 'name', text='', emboss=False)

    row = master.row(align=True)
    row.active = is_active

    # Active image
    if active_mask_image: active_image = active_mask_image
    elif active_override_image: active_image = active_override_image
    elif image: active_image = image
    else: active_image = None

    if active_image:
        # Asterisk icon to indicate dirty image
        if active_image.is_dirty:
            row.label(text='', icon_value=lib.get_icon('asterisk'))

        # Indicate packed image
        if active_image.packed_file:
            row.label(text='', icon='PACKAGE')

    # Modifier shortcut
    shortcut_found = False

    if layer.type == 'COLOR':
        src = get_layer_source(layer, layer_tree)
        if src is not None: 
            rrow = row.row()
            rrow.prop(src.outputs[0], 'default_value', text='', icon='COLOR')
            shortcut_found = True

    if not shortcut_found:

        for mod in layer.modifiers:
            if mod.shortcut and mod.enable:
                if mod.type == 'RGB_TO_INTENSITY':
                    rrow = row.row()
                    mod_tree = get_mod_tree(mod)
                    rrow.prop(mod, 'rgb2i_col', text='', icon='COLOR')
                    shortcut_found = True
                    break

                elif mod.type == 'OVERRIDE_COLOR': # and not mod.oc_use_normal_base:
                    rrow = row.row()
                    mod_tree = get_mod_tree(mod)
                    rrow.prop(mod, 'oc_col', text='', icon='COLOR')
                    shortcut_found = True
                    break

    if not shortcut_found:

        for ch in layer.channels:
            for mod in ch.modifiers:
                if mod.shortcut and mod.enable:

                    if mod.type == 'RGB_TO_INTENSITY':
                        rrow = row.row()
                        mod_tree = get_mod_tree(mod)
                        rrow.prop(mod, 'rgb2i_col', text='', icon='COLOR')
                        shortcut_found = True
                        break

                    elif mod.type == 'OVERRIDE_COLOR': # and not mod.oc_use_normal_base:
                        rrow = row.row()
                        mod_tree = get_mod_tree(mod)
                        rrow.prop(mod, 'oc_col', text='', icon='COLOR')
                        shortcut_found = True
                        break

            if shortcut_found:
                break

    # Mask visibility
    if len([m for m in layer.masks if m.enable]) > 0:
        row = master.row()
        row.active = is_active
        mask_icon = 'mask' if layer.enable_masks else 'mask_off'
        row.prop(layer, 'enable_masks', emboss=False, text='', icon_value=lib.get_icon(mask_icon))

    # Layer intensity
    row = master.row()
    row.active = is_active
    row.scale_x = 0.4
    if is_bl_newer_than(3):
        row.emboss = 'NONE_OR_STATUS'
    elif is_bl_newer_than(2, 92):
        row.emboss = 'UI_EMBOSS_NONE_OR_STATUS'
    elif is_bl_newer_than(2, 80): row.emboss = 'NONE'

    if is_bl_newer_than(2, 80):
        draw_input_prop(row, layer, 'intensity_value', layer=layer)
    else: draw_input_prop(row, layer, 'intensity_value', emboss=False, layer=layer)

    # Layer visibility
    row = master.row()
    row.active = is_active
    if not is_bl_newer_than(2, 80):
        if layer.enable: eye_icon = 'RESTRICT_VIEW_OFF'
        else: eye_icon = 'RESTRICT_VIEW_ON'
    else:
        if layer.enable: eye_icon = 'HIDE_OFF'
        else: eye_icon = 'HIDE_ON'
    row.prop(layer, 'enable', emboss=False, text='', icon=eye_icon)

class NODE_UL_YPaint_list_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        ypup = get_user_preferences()
        group_tree = item.id_data
        yp = group_tree.yp
        ypui = context.window_manager.ypui

        # Base Layer
        if item.type == 'BASE':
            row = layout.row(align=True)
            if ypui.any_expandable_layers:
                row.label(text='', icon='BLANK1')
            #row.label(text=item.name, icon_value=lib.get_icon('NODE_MATERIAL'))
            row.label(text=item.name, icon_value=lib.get_icon('channels'))

            # Get first channel
            node = get_active_ypaint_node()
            if node and len(yp.channels) > 0 and yp.channels[0].type == 'RGB':
                root_ch = yp.channels[0]
                root_color_ch, root_alpha_ch = get_color_alpha_ch_pairs(yp)

                # Alpha input
                if root_alpha_ch and root_ch == root_color_ch:
                    inp = node.inputs[root_alpha_ch.io_index]

                    if len(inp.links) > 0:
                        row.label(text='', icon='LINKED')

                    if len(inp.links) == 0: # or baked:
                        arow = row.row(align=True)
                        arow.scale_x = 0.4
                        if is_bl_newer_than(3):
                            arow.emboss = 'NONE_OR_STATUS'
                        elif is_bl_newer_than(2, 92):
                            arow.emboss = 'UI_EMBOSS_NONE_OR_STATUS'
                        elif is_bl_newer_than(2, 80): arow.emboss = 'NONE'
                        arow.prop(inp, 'default_value', text='', emboss=False)

                row.separator()

                # Color input
                if root_ch.io_index < len(node.inputs):
                    inp = node.inputs[root_ch.io_index]
                    baked = group_tree.nodes.get(root_ch.baked)
                    if len(inp.links) > 0:
                        row.label(text='', icon='LINKED')

                    if len(inp.links) == 0: # or baked:
                        row.prop(inp, 'default_value', text='', icon='COLOR')

        # Layer
        if item.type == 'LAYER' and item.index < len(yp.layers):
            layer = yp.layers[item.index]
            layer_listing(layout, layer, show_expand=True)

        # Overrides
        if item.type == 'CHANNEL_OVERRIDE' and item.parent_index != -1 and item.parent_index < len(yp.layers):
            master = layout.row(align=True)
            layer = yp.layers[item.parent_index]

            if layer.parent_idx != -1:
                depth = get_layer_depth(layer)
                for i in range(depth):
                    master.label(text='', icon='BLANK1')

            if item.index < len(layer.channels):

                ch = layer.channels[item.index]
                root_ch = yp.channels[item.index]
                color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)

                is_active = not is_parent_hidden(layer) and layer.enable and (ch.enable or (ch == alpha_ch and color_ch.enable))

                row = master.row(align=True)
                row.active = is_active

                row.label(text='', icon='BLANK1')
                row.label(text='', icon='BLANK1')

                ch_source = None
                override_type = ''
                if ch.override:
                    ch_source = get_channel_source(ch, layer)
                    override_type = ch.override_type

                ch_image = None
                if override_type == 'IMAGE' and ch_source and ch_source.image:
                    ch_image = ch_source.image
                    if ypup.use_image_preview and ch_image.preview: 
                        #if not ch_image.preview: ch_image.preview_ensure()
                        row.prop(ch_image, 'name', text='', emboss=False, icon_value=ch_image.preview.icon_id)
                    else: 
                        icon_name = get_ch_type_icon_prefix(layer, ch) + 'image'
                        row.prop(ch_image, 'name', text='', emboss=False, icon_value=lib.get_icon(icon_name))
                elif override_type == 'VCOL' and ch_source and ch_source.attribute_name:
                    icon_name = get_ch_type_icon_prefix(layer, ch) + 'vertex_color'
                    row.prop(ch, 'override_vcol_name', text='', emboss=False, icon_value=lib.get_icon(icon_name))
                else: 
                    icon_name = get_ch_type_icon_prefix(layer, ch) + 'texture'
                    row.label(text=get_ch_override_label(layer, ch), icon_value=lib.get_icon(icon_name))

                if ch_image:
                    # Asterisk icon to indicate dirty image
                    if ch_image.is_dirty:
                        row.label(text='', icon_value=lib.get_icon('asterisk'))

                    # Indicate packed image
                    if ch_image.packed_file:
                        row.label(text='', icon='PACKAGE')

                row.label(text='', icon='BLANK1')

        # Masks
        if item.type == 'MASK' and item.parent_index != -1 and item.parent_index < len(yp.layers):
            master = layout.row(align=True)
            layer = yp.layers[item.parent_index]

            if layer.parent_idx != -1:
                depth = get_layer_depth(layer)
                for i in range(depth):
                    master.label(text='', icon='BLANK1')

            if item.index < len(layer.masks):

                mask = layer.masks[item.index]

                is_active = not is_parent_hidden(layer) and layer.enable and layer.enable_masks and mask.enable

                row = master.row(align=True)
                row.active = is_active

                row.label(text='', icon='BLANK1')
                row.label(text='', icon='BLANK1')

                mask_image = None
                if mask.type == 'IMAGE':
                    mask_tree = get_mask_tree(mask)
                    source = mask_tree.nodes.get(mask.source)
                    if source and source.image:
                        mask_image = source.image
                        if mask_image:
                            if (mask_image.yia.is_image_atlas or mask_image.yua.is_udim_atlas): 
                                if ypup.use_image_preview and mask_image.preview: 
                                    #if not mask_image.preview: mask_image.preview_ensure()
                                    row.prop(mask, 'name', text='', emboss=False, icon_value=mask_image.preview.icon_id)
                                else: row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('image'))
                            else:
                                if ypup.use_image_preview and mask_image.preview: 
                                    #if not mask_image.preview: mask_image.preview_ensure()
                                    row.prop(mask_image, 'name', text='', emboss=False, icon_value=mask_image.preview.icon_id)
                                else: row.prop(mask_image, 'name', text='', emboss=False, icon_value=lib.get_icon('image'))
                    else: row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('mask'))
                elif mask.type == 'VCOL':
                    mask_tree = get_mask_tree(mask)
                    source = mask_tree.nodes.get(mask.source)
                    socket_input_name = get_mask_input_socket_name(mask, source)
                    if socket_input_name == 'Alpha':
                        row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[socket_input_name]+'vertex_color'))
                    elif mask.swizzle_input_mode in {'R', 'G', 'B'}:
                        row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon(RGBA_CHANNEL_PREFIX[mask.swizzle_input_mode]+'vertex_color'))
                    else: row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
                elif mask.type == 'HEMI':
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('hemi'))
                elif mask.type == 'OBJECT_INDEX':
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('object_index'))
                elif mask.type in {'EDGE_DETECT', 'AO'}:
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('edge_detect'))
                elif mask.type == 'COLOR_ID':
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('color'))
                elif mask.type == 'BACKFACE':
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('backface'))
                elif mask.type == 'MODIFIER':
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('modifier'))
                else:
                    row.prop(mask, 'name', text='', emboss=False, icon_value=lib.get_icon('texture'))

                if mask_image:
                    # Asterisk icon to indicate dirty image
                    if mask_image.is_dirty:
                        row.label(text='', icon_value=lib.get_icon('asterisk'))

                    # Indicate packed image
                    if mask_image.packed_file:
                        row.label(text='', icon='PACKAGE')

                # Mask blend type
                #row = master.row(align=True)
                #row.scale_x = 0.55
                #row.active = is_active
                #row.prop(mask, 'blend_type', text='', emboss=False)

                # Mask visibility
                #row = master.row(align=True)
                #row.active = is_active
                #mask_icon = 'mask' if mask.enable else 'mask_off'
                #row.prop(mask, 'enable', emboss=False, text='', icon_value=lib.get_icon(mask_icon))
                ##row.prop(mask, 'enable', emboss=False, text='', icon=get_eye_icon(mask.enable))

                # Mask intensity
                #row = master.row(align=True)
                #row.scale_x = 0.4
                #row.active = is_active
                #if is_bl_newer_than(3):
                #    row.emboss = 'NONE_OR_STATUS'
                #elif is_bl_newer_than(2, 92):
                #    row.emboss = 'UI_EMBOSS_NONE_OR_STATUS'
                #elif is_bl_newer_than(2, 80): row.emboss = 'NONE'

                #if is_bl_newer_than(2, 80):
                #    draw_input_prop(row, mask, 'intensity_value', layer=layer)
                #else: draw_input_prop(row, mask, 'intensity_value', emboss=False, layer=layer)

                row = master.row(align=True)
                row.label(text='', icon='BLANK1')
        
class NODE_UL_YPaint_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layer = item
        layer_listing(layout, layer)

class YPAssetBrowserMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_asset_browser_menu"
    bl_label = get_addon_title() + " Asset Browser Menu"
    bl_description = get_addon_title() + " asset browser menu"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        obj = context.object

        active_mat = get_active_material()

        mat_asset = getattr(context, 'mat_asset', None)
        mat_name = mat_asset.name if mat_asset else ''
        asset_library_path = mat_asset.full_library_path if mat_asset else ''

        op = self.layout.operator("wm.y_open_images_from_material_to_single_layer", icon_value=lib.get_icon('image'), text='Open Material Images to Layer')
        op.mat_name = mat_name
        op.asset_library_path = asset_library_path
        op.fail_self_load = active_mat != None and active_mat.asset_data != None and mat_name == active_mat.name and asset_library_path == ''

        if obj.type == 'MESH':
            op.texcoord_type = 'UV'
            active_uv_name = get_active_render_uv(obj)
            op.uv_map = active_uv_name
        else:
            op.texcoord_type = 'Generated'

        op = self.layout.operator("wm.y_open_layers_from_material", icon='PASTEDOWN')
        op.mat_name = mat_name
        op.asset_library_path = asset_library_path

def draw_yp_asset_browser_menu(self, context):

    assets = context.selected_assets if is_bl_newer_than(4) else context.selected_asset_files

    mat_asset = None
    for asset in assets:
        if asset.id_type == 'MATERIAL':
            mat_asset = asset
            break

    obj = context.object

    if mat_asset and obj:
        self.layout.separator()
        self.layout.context_pointer_set('mat_asset', mat_asset)
        self.layout.menu("NODE_MT_ypaint_asset_browser_menu", text=get_addon_title(), icon_value=lib.get_icon('nodetree'))

class YPFileBrowserMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_file_browser_menu"
    bl_label = get_addon_title() + " File Browser Menu"
    bl_description = get_addon_title() + " file browser menu"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        if not node:
            self.layout.label(text="You need to select object that uses "+get_addon_title()+" node!", icon='ERROR')
        else:
            params = context.params
            filename = params.filename
            directory = params.directory.decode('utf-8')

            filepath = os.path.join(directory, filename)

            self.layout.label(text='Image: ' + filename)

            op = self.layout.operator("wm.y_open_image_to_layer", icon_value=lib.get_icon('image'), text="Open Image as Layer")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'UV'

            op = self.layout.operator("wm.y_open_image_as_mask", icon_value=lib.get_icon('image'), text="Open Image as Mask")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'UV'

            op = self.layout.operator("wm.y_new_layer", icon_value=lib.get_icon('image'), text="Open Image as Mask for New Layer")
            op.type = 'COLOR'
            op.add_mask = True
            op.mask_type = 'IMAGE'
            op.mask_image_filepath = filepath
            op.mask_texcoord_type = 'UV'

            self.layout.separator()

            op = self.layout.operator("wm.y_open_image_to_layer", icon_value=lib.get_icon('image'), text="Open Image as Decal Layer")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'Decal'

            op = self.layout.operator("wm.y_open_image_as_mask", icon_value=lib.get_icon('image'), text="Open Image as Decal Mask")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'Decal'

            op = self.layout.operator("wm.y_new_layer", icon_value=lib.get_icon('image'), text="Open Image as Decal Mask for New Layer")
            op.type = 'COLOR'
            op.add_mask = True
            op.mask_type = 'IMAGE'
            op.mask_image_filepath = filepath
            op.mask_texcoord_type = 'Decal'

def draw_yp_file_browser_menu(self, context):
    params = context.space_data.params
    extension = os.path.splitext(params.filename)[1]
    if extension in valid_image_extensions:

        filename = params.filename
        directory = params.directory.decode('utf-8')
        filepath = os.path.join(directory, filename)

        if os.path.isfile(filepath):
            self.layout.separator()
            self.layout.context_pointer_set('params', params)
            self.layout.menu("NODE_MT_ypaint_file_browser_menu", text=get_addon_title(), icon_value=lib.get_icon('nodetree'))

def draw_ypaint_about(self, context):
    col = self.layout.column(align=True)

    #any_ui_drawn = False

    credits_ui = get_package_module('.credits_ui')
    #credits_ui_loaded = False
    if credits_ui:
        credits_ui_loaded = credits_ui.draw_contributors(context, col)
        #if credits_ui_loaded: any_ui_drawn = True

    #if not credits_ui_loaded:
    #    # NOTE: Blender don't like if the addon creator get small money through UI :(((
    #    if not is_installed_through_extension_platform() and (not is_bl_newer_than(2, 80) or not credits_ui):
    #        col.label(text='Support '+get_addon_title() + '!')
    #        icon = 'FUND' if is_bl_newer_than(2, 80) else 'POSE_DATA'
    #        label = "Get "+get_addon_title()+" Plus!" if is_bl_newer_than(2, 80) else "Become a Sponsor!"
    #        col.operator('wm.url_open', text=label, icon=icon).url = "https://github.com/sponsors/ucupumar"
    #        any_ui_drawn = True

    #    if credits_ui: credits_ui.draw_contributor_status(context, col, add_separator=any_ui_drawn)    

    #if any_ui_drawn: col.separator()

    #col.label(text='Links:')
    #col.operator('wm.url_open', text=get_addon_title()+' Wiki', icon='TEXT').url = 'https://ucupumar.github.io/ucupaint-wiki/'
    #col.operator('wm.url_open', text=get_addon_title()+' GitHub', icon='SCRIPT').url = 'https://github.com/ucupumar/ucupaint'
    #icon = 'COMMUNITY' if is_bl_newer_than(2, 80) else 'SEQ_SEQUENCER'
    #col.operator('wm.url_open', text=get_addon_title()+' Discord Server', icon=icon).url = 'https://discord.gg/BdNfGGzQHh'

    #addon_updater_ops = get_package_module('.addon_updater_ops')
    #if addon_updater_ops:
    #    col.separator()
    #    addon_updater_ops.draw_updater_options(context, col)

class YPaintBakeTargetPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_bake_target_popover"
    bl_label = get_addon_title() + " Bake Targets"
    bl_description = get_addon_title() + " Bake Targets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        draw_bake_targets_ui(context, self.layout, node, show_header=True, rows=len(yp.bake_targets))

class YPaintBakeTargetAltPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_bake_target_alt_popover"
    bl_label = get_addon_title() + " Bake Targets (Alt)"
    bl_description = get_addon_title() + " Bake Targets (alt)"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        draw_bake_targets_ui(context, self.layout, node, show_header=True, rows=len(yp.bake_targets))

class YPaintPreviewModeSettingsPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_preview_mode_settings_popover"
    bl_label = get_addon_title() + " Preview Mode Settings"
    bl_description = get_addon_title() + " Preview Mode settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_preview_mode_popover_settings(context, self.layout, get_active_ypaint_node())

class YPaintPreviewModeChannelSettingsPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_preview_mode_channel_settings_popover"
    bl_label = get_addon_title() + " Preview Mode Channel Settings"
    bl_description = get_addon_title() + " Preview Mode channel settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 9

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_preview_mode_popover_settings(context, self.layout, get_active_ypaint_node(), show_types=False)

class YPaintChannelPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_channel_popover"
    bl_label = get_addon_title() + " Channels"
    bl_description = get_addon_title() + " Channels"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 14

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        draw_root_channels_ui(context, self.layout, get_active_ypaint_node(), show_header=True, rows=len(yp.channels))

class YPaintAboutPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ypaint_about_popover"
    bl_label = get_addon_title() + " About"
    bl_description = get_addon_title() + " About"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        draw_ypaint_about(self, context)

class YPaintAboutMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_about_menu"
    bl_label = get_addon_title() + " About"
    bl_description = get_addon_title() + " About"
    
    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        draw_ypaint_about(self, context)

class YPaintSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_special_menu"
    bl_label = get_addon_title() + " Special Menu"
    bl_description = get_addon_title() + " Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()
        mat = get_active_material()
        yp = node.node_tree.yp
        ypui = context.window_manager.ypui

        row = self.layout.row()

        col = row.column()

        col.operator('wm.y_bake_all_targets', text='Bake '+get_addon_title()+' Node', icon_value=lib.get_icon('bake')).with_prompt = True
        col.operator('wm.y_rename_ypaint_tree', text='Rename '+get_addon_title()+' Node Tree', icon_value=lib.get_icon('rename'))

        col.separator()

        col.operator('wm.y_remove_yp_node', icon_value=lib.get_icon('close'))

        col.separator()

        col.operator('wm.y_clean_yp_caches', icon_value=lib.get_icon('clean'))

        col.separator()

        op = col.operator('wm.y_duplicate_yp_nodes', text='Duplicate Material and ' + get_addon_title() + ' Nodes', icon='COPY_ID')
        op.duplicate_material = True

        col.separator()

        col.label(text='Active Node Tree:', icon_value=lib.get_icon('nodetree'))
        for n in get_list_of_ypaint_nodes(mat):
            if n.name == node.name:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            #row = col.row()
            col.operator('wm.y_change_active_ypaint_node', text=n.node_tree.name, icon=icon).name = n.name

        col.separator()
        col.label(text='Option:')
        col.prop(yp, 'use_linear_blending')

        if is_bl_newer_than(2, 80) and not is_bl_newer_than(3):
            col.prop(yp, 'enable_tangent_sign_hacks')

        #col.prop(yp, 'enable_backface_always_up')

        #col.separator()
        #col.label(text='Performance Options:')
        #col.prop(ypui, 'disable_auto_temp_uv_update')
        #col.prop(yp, 'disable_quick_toggle')

        if not yp.use_baked:
            col.separator()
            draw_stats_ui(context, col, node, show_header=True)

class YBakeListSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_bake_list_special_menu"
    bl_label = "Bake Special Menu"
    bl_description = "Bake Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()

        row = self.layout.row()
        col = row.column()

        col.operator('wm.y_copy_bake_target', icon='COPYDOWN')
        col.operator('wm.y_paste_bake_target', icon='PASTEDOWN').paste_as_new = True
        col.operator('wm.y_paste_bake_target', text="Paste Bake Target Values", icon='PASTEDOWN').paste_as_new = False

class YBakeTargetMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_bake_target_menu"
    bl_description = 'Bake Target Menu'
    bl_label = "Bake Target Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):

        col = self.layout.column()

        bt = context.bt
        op = col.operator('wm.y_bake_single_target', text='Bake '+bt.name, icon_value=lib.get_icon('bake'))
        op.bake_target_index = get_bake_target_index(bt)

        if bt.data_type == 'IMAGE':
            col.separator()
            col.operator('wm.y_pack_image', icon='PACKAGE')
            col.operator('wm.y_save_image', icon='FILE_TICK')

            if context.image:
                if context.image.packed_file:
                    col.operator('wm.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').copy = False
                else: col.operator('wm.y_save_as_image', text='Save As Image').copy = False
                col.operator('wm.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

class YChannelSpecialTypeMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_channel_special_type_menu"
    bl_description = 'Channel special type menu'
    bl_label = 'Channel Special Type Menu'

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        channel = context.channel
        yp = channel.id_data.yp
        col = self.layout.column()

        icon = 'RADIOBUT_ON' if channel.special_type == 'NONE' else 'RADIOBUT_OFF'
        col.operator('wm.y_set_channel_special_type', text='None', icon=icon).type = 'NONE'

        if channel.type == 'VALUE' and (channel.name == 'Alpha' or channel.special_type == 'ALPHA'):
            alpha_ch_exists = any([c for c in yp.channels if c.special_type == 'ALPHA' and c != channel])
            if not alpha_ch_exists:
                icon = 'RADIOBUT_ON' if channel.special_type == 'ALPHA' else 'RADIOBUT_OFF'
                col.operator('wm.y_set_channel_special_type', text='Alpha', icon=icon).type = 'ALPHA'

        if channel.type == 'VECTOR':
            icon = 'RADIOBUT_ON' if channel.special_type == 'NORMAL' else 'RADIOBUT_OFF'
            col.operator('wm.y_set_channel_special_type', text='Normal', icon=icon).type = 'NORMAL'

        if channel.type == 'VALUE':
            height_ch_exists = any([c for c in yp.channels if c.special_type == 'HEIGHT' and c != channel])
            if not height_ch_exists:
                icon = 'RADIOBUT_ON' if channel.special_type == 'HEIGHT' else 'RADIOBUT_OFF'
                col.operator('wm.y_set_channel_special_type', text='Height', icon=icon).type = 'HEIGHT'

        # NOTE: Do not show vector displacement option for channel called normal to avoid confusion
        if channel.type in {'RGB', 'VECTOR'} and channel.name not in {'Normal'}:
            icon = 'RADIOBUT_ON' if channel.special_type == 'VDISP' else 'RADIOBUT_OFF'
            col.operator('wm.y_set_channel_special_type', text='Vector Displacement', icon=icon).type = 'VDISP'

class YChannelActiveBakeTargetMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_channel_active_bake_target_menu"
    bl_description = 'Channel active bake target menu'
    bl_label = 'Channel Active Bake Target Menu'

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        channel = context.channel
        yp = channel.id_data.yp

        chbts = get_channel_bake_target_dict(yp)

        #show_remove = channel.name in chbts and len(chbts[channel.name]) > 1
        show_remove = False

        if show_remove:
            row = self.layout.row()
            col = row.column()
        else:
            col = self.layout.column()

        if channel.name in chbts:

            for bt in chbts[channel.name]:
                bt_label = get_bake_target_label(bt)
                icon = 'RADIOBUT_ON' if channel.bake_target_name == bt.name else 'RADIOBUT_OFF'
                col.operator('wm.y_set_channel_active_bake_target', text=bt_label, icon=icon).bake_target_name = bt.name

            #col.separator()

        #col.operator('wm.y_new_channel_bake_target', text='Add New Bake Target', icon='ADD')

        if show_remove:
            col = row.column()

            icon = 'TRASH' if is_bl_newer_than(2, 80) else 'CANCEL'
            for bt in chbts[channel.name]:
                col.context_pointer_set('bake_target', bt)
                col.operator('wm.y_remove_bake_target', text='Remove', icon=icon)

class YNewChannelMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_channel_menu"
    bl_description = 'Add New Channel'
    bl_label = "New Channel Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()
        col.label(text='Add New Channel')

        col.operator("wm.y_add_new_ypaint_channel", icon='RADIOBUT_OFF', text='Custom')

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['VALUE'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Alpha').mode = 'ALPHA'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['RGB'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Ambient Occlusion').mode = 'AO'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['RGB'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Emission').mode = 'EMISSION'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['VALUE'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Height').mode = 'HEIGHT'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['VECTOR'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Normal').mode = 'NORMAL'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['RGB'])
        col.operator("wm.y_auto_setup_new_ypaint_channel", icon_value=icon_value, text='Vector Displacement').mode = 'VDISP'

def draw_new_image_layer_menu(layout, show_vdm=True):
    layout.operator("wm.y_new_layer", text='New Image', icon_value=lib.get_icon('image')).type = 'IMAGE'

    op = layout.operator("wm.y_open_image_to_layer", text='Open Image...')
    op.texcoord_type = 'UV'
    op.file_browser_filepath = ''
    layout.operator("wm.y_open_existing_data_to_layer", text='Open Existing Image').type = 'IMAGE'

    layout.operator("wm.y_open_images_to_single_layer", text='Open Images to Single Layer...')
    layout.operator("wm.y_open_images_from_material_to_single_layer", text='Open Images from Material').asset_library_path = ''

    # NOTE: Dedicated menu for opening images to single layer is kinda hard to see, so it's probably better be hidden for now
    #layout.menu("NODE_MT_y_open_images_to_single_layer_menu", text='Open Images to Single Layer')

    if is_bl_newer_than(3, 2) and show_vdm:
        layout.separator()
        layout.operator("wm.y_new_vdm_layer", text='Vector Displacement Image', icon='SCULPTMODE_HLT')

def draw_new_vcol_layer_menu(layout):
    layout.operator("wm.y_new_layer", icon_value=lib.get_icon('vertex_color'), text='New '+get_vertex_color_label()).type = 'VCOL'
    layout.operator("wm.y_open_existing_data_to_layer", text='Open Existing '+get_vertex_color_label()).type = 'VCOL'

def draw_new_color_layer_menu(layout):
    icon_value = lib.get_icon("color")
    c = layout.operator("wm.y_new_layer", icon_value=icon_value, text='Solid Color')
    c.type = 'COLOR'
    c.add_mask = False

    c = layout.operator("wm.y_new_layer", text='Solid Color w/ Image Mask')
    c.type = 'COLOR'
    c.add_mask = True
    c.mask_type = 'IMAGE'

    c = layout.operator("wm.y_new_layer", text='Solid Color w/ '+get_vertex_color_label()+' Mask')
    c.type = 'COLOR'
    c.add_mask = True
    c.mask_type = 'VCOL'

    c = layout.operator("wm.y_new_layer", text='Solid Color w/ Color ID Mask')
    c.type = 'COLOR'
    c.add_mask = True
    c.mask_type = 'COLOR_ID'

    if is_bl_newer_than(2, 93):
        c = layout.operator("wm.y_new_layer", text='Solid Color w/ Edge Detect Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'EDGE_DETECT'

def draw_new_texture_layer_menu(layout):
    layout.operator("wm.y_new_layer", icon_value=lib.get_icon('texture'), text='Brick').type = 'BRICK'
    layout.operator("wm.y_new_layer", text='Checker').type = 'CHECKER'
    layout.operator("wm.y_new_layer", text='Gradient').type = 'GRADIENT'
    layout.operator("wm.y_new_layer", text='Magic').type = 'MAGIC'
    if not is_bl_newer_than(4, 1): layout.operator("wm.y_new_layer", text='Musgrave').type = 'MUSGRAVE'
    layout.operator("wm.y_new_layer", text='Noise').type = 'NOISE'
    if is_bl_newer_than(4, 3): layout.operator("wm.y_new_layer", text='Gabor').type = 'GABOR'
    layout.operator("wm.y_new_layer", text='Voronoi').type = 'VORONOI'
    layout.operator("wm.y_new_layer", text='Wave').type = 'WAVE'

def draw_new_input_layer_menu(layout):
    if is_bl_newer_than(5):
        c = layout.operator("wm.y_new_layer", text='Bundle Input', icon='NODE_SOCKET_BUNDLE')
        c.type = 'INPUT_BUNDLE'

def draw_new_generated_layer_menu(layout):
    if is_bl_newer_than(2, 93):
        layout.operator("wm.y_new_layer", icon_value=lib.get_icon('edge_detect'), text='Ambient Occlusion').type = 'AO'
        layout.operator("wm.y_new_layer", text='Edge Detect').type = 'EDGE_DETECT'
        layout.separator()
    layout.operator("wm.y_new_layer", icon_value=lib.get_icon('hemi'), text='Fake Lighting').type = 'HEMI'

def draw_new_adjustment_layer_menu(layout):
    op = layout.operator("wm.y_new_layer", icon_value=lib.get_icon('modifier'), text='RGB Curve')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'RGB_CURVE'

    op = layout.operator("wm.y_new_layer", text='Color Ramp')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'COLOR_RAMP'

    op = layout.operator("wm.y_new_layer", text='Hue Saturation')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'HUE_SATURATION'

    op = layout.operator("wm.y_new_layer", text='Brightness Contrast')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'BRIGHT_CONTRAST'

    op = layout.operator("wm.y_new_layer", text='Math')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'MATH'

    op = layout.operator("wm.y_new_layer", text='Invert')
    op.type = 'PREV_LAYERS'
    op.modifier_type = 'INVERT'

def draw_new_bake_as_layer_menu(layout):
    c = layout.operator("wm.y_bake_to_layer", icon_value=lib.get_icon('bake'), text='Ambient Occlusion')
    c.type = 'AO'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    c = layout.operator("wm.y_bake_to_layer", text='Pointiness')
    c.type = 'POINTINESS'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    c = layout.operator("wm.y_bake_to_layer", text='Cavity')
    c.type = 'CAVITY'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    c = layout.operator("wm.y_bake_to_layer", text='Dust')
    c.type = 'DUST'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    c = layout.operator("wm.y_bake_to_layer", text='Paint Base')
    c.type = 'PAINT_BASE'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    c = layout.operator("wm.y_bake_to_layer", text='Wireframe')
    c.type = 'WIREFRAME'
    c.target_type = 'LAYER'
    c.overwrite_current = False
        
    if is_bl_newer_than(2, 80):
        c = layout.operator("wm.y_bake_to_layer", text='Thickness')
        c.type = 'THICKNESS'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Curvature')
        c.type = 'CURVATURE'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Bevel Normal')
        c.type = 'BEVEL_NORMAL'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Bevel Grayscale')
        c.type = 'BEVEL_MASK'
        c.target_type = 'LAYER'
        c.overwrite_current = False

    # NOTE: Blender 2.76 does not bake to object space normal correctly
    if is_bl_newer_than(2, 77):
        c = layout.operator("wm.y_bake_to_layer", text='Object Space Normal')
        c.type = 'OBJECT_SPACE_NORMAL'
        c.target_type = 'LAYER'
        c.overwrite_current = False

    if is_bl_newer_than(2, 80):
        layout.separator()

        c = layout.operator("wm.y_bake_to_layer", text='Multires Normal')
        c.type = 'MULTIRES_NORMAL'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Multires Displacement')
        c.type = 'MULTIRES_DISPLACEMENT'
        c.target_type = 'LAYER'
        c.overwrite_current = False

    # NOTE: Blender 2.76 currently cant bake from other objects since it has a different setup
    if is_bl_newer_than(2, 77):
        layout.separator()

        c = layout.operator("wm.y_bake_to_layer", text='Other Objects Color')
        c.type = 'OTHER_OBJECT_EMISSION'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Other Objects Normal')
        c.type = 'OTHER_OBJECT_NORMAL'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = layout.operator("wm.y_bake_to_layer", text='Other Objects Channels')
        c.type = 'OTHER_OBJECT_CHANNELS'
        c.target_type = 'LAYER'
        c.overwrite_current = False

    layout.separator()

    c = layout.operator("wm.y_bake_to_layer", text='Selected Vertices')
    c.type = 'SELECTED_VERTICES'
    c.target_type = 'LAYER'
    c.overwrite_current = False

    ypup = get_user_preferences()
    if ypup.show_experimental:
        layout.separator()

        c = layout.operator("wm.y_bake_to_layer", text='Flow')
        c.type = 'FLOW'
        c.target_type = 'LAYER'
        c.overwrite_current = False

class YNewImageLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_image_layer_menu"
    bl_description = 'Add New Image Layer'
    bl_label = "New Image Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_image_layer_menu(self.layout)

class YNewVcolLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_vcol_layer_menu"
    bl_description = 'Add New Attributes Layer'
    bl_label = "New Attributes Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_vcol_layer_menu(self.layout)

class YNewColorLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_color_layer_menu"
    bl_description = 'Add New Solid Color Layer'
    bl_label = "New Solid Color Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_color_layer_menu(self.layout)

class YNewTextureLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_texture_layer_menu"
    bl_description = 'Add New Texture Layer'
    bl_label = "New Texture Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_texture_layer_menu(self.layout)

class YNewInputLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_input_layer_menu"
    bl_description = 'Add New Input Layer'
    bl_label = "New Texture Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_input_layer_menu(self.layout)

class YNewGeneratedLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_generated_layer_menu"
    bl_description = 'Add New Generated Layer'
    bl_label = "New Generated Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_generated_layer_menu(self.layout)

class YNewAdjustmentLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_adjustment_layer_menu"
    bl_description = 'Add New Adjustment Layer'
    bl_label = "New Adjustment Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_adjustment_layer_menu(self.layout)

class YNewBakeAsLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_bake_as_layer_menu"
    bl_description = 'Add New Bake as Layer'
    bl_label = "New Bake as Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_bake_as_layer_menu(self.layout)

class YNewLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_layer_menu"
    bl_description = 'Add New Layer'
    bl_label = "Add Layer"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        ypup = get_user_preferences()

        if is_bl_newer_than(4) and not ypup.ui_legacy_add_layer_menu:
            col = self.layout

            if self.layout.operator_context == 'EXEC_REGION_WIN':
                self.layout.operator_context = 'INVOKE_REGION_WIN'
                col.operator(
                    "WM_OT_search_single_menu",
                    text="Search...",
                    icon='VIEWZOOM',
                ).menu_idname = "NODE_MT_y_new_layer_menu"
                col.separator()

            self.layout.operator_context = 'INVOKE_REGION_WIN'

            col.menu("NODE_MT_y_new_image_layer_menu", text='Image', icon_value=lib.get_icon('image'))
            col.menu("NODE_MT_y_new_vcol_layer_menu", text=get_vertex_color_label(), icon_value=lib.get_icon('vertex_color'))
            col.menu("NODE_MT_y_new_color_layer_menu", text='Solid Color', icon_value=lib.get_icon('color'))
            col.menu("NODE_MT_y_new_texture_layer_menu", text='Texture', icon_value=lib.get_icon('texture'))
            col.separator()
            col.menu("NODE_MT_y_new_generated_layer_menu", text='Geometry', icon_value=lib.get_icon('edge_detect'))
            col.menu("NODE_MT_y_new_bake_as_layer_menu", text='Bake as Layer', icon_value=lib.get_icon('bake'))
            col.menu("NODE_MT_y_new_adjustment_layer_menu", text='Adjustment', icon_value=lib.get_icon('modifier'))
            col.separator()
            col.menu("NODE_MT_y_new_input_layer_menu", text='Node Input', icon_value=lib.get_icon('RADIOBUT_ON'))
            col.separator()
            col.operator("wm.y_new_layer", icon_value=lib.get_icon('group'), text='Layer Group').type = 'GROUP'
        else:
            row = self.layout.row()
            col = row.column()

            col.label(text='New Layer:')

            draw_new_image_layer_menu(col, show_vdm=False)
            col.separator()

            col.operator("wm.y_new_layer", icon_value=lib.get_icon('group'), text='Layer Group').type = 'GROUP'
            col.separator()

            draw_new_vcol_layer_menu(col)
            col.separator()

            draw_new_color_layer_menu(col)

            col.separator()
            draw_new_input_layer_menu(col)

            if is_bl_newer_than(3, 2):
                col.separator()
                col.operator("wm.y_new_vdm_layer", text='Vector Displacement Image', icon='SCULPTMODE_HLT')

            col = row.column()
            col.label(text='New Generated Layer:')
            draw_new_texture_layer_menu(col)

            col.separator()
            draw_new_generated_layer_menu(col)

            col.separator()
            col.label(text='New Adjustment Layer:')
            draw_new_adjustment_layer_menu(col)

            col = row.column()
            col.label(text='Bake as Layer:')
            draw_new_bake_as_layer_menu(col)

class YBakedImageMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_baked_image_menu"
    bl_label = "Baked Image Menu"
    bl_description = "Baked Image Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        root_ch = context.root_ch

        #row = col.row()
        #row.active = not yp.enable_baked_outside
        #label = 'Disable Baked ' + root_ch.name
        #row.prop(context.root_ch, 'disable_global_baked', text=label, icon='RESTRICT_RENDER_ON')


        if context.image:
            col.label(text='Active Image: '+context.image.name, icon='IMAGE_DATA')

            col.separator()

            col.operator('wm.y_pack_image', icon='PACKAGE')
            col.operator('wm.y_save_image', icon='FILE_TICK')

            if context.image.packed_file:
                col.operator('wm.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').copy = False
            else: col.operator('wm.y_save_as_image', text='Save As Image').copy = False
            col.operator('wm.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

class YLayerChannelNormalBlendMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_channel_normal_blend_menu"
    bl_label = "Layer Channel Normal Blend"
    bl_description = "Layer channel normal blend"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column() #align=True)
        for key, val in normal_blend_labels.items():
            col.operator('wm.y_set_layer_channel_normal_blend_type', text=val).normal_blend_type = key

class YLayerChannelBlendMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_channel_blend_menu"
    bl_label = "Layer Channel Blend"
    bl_description = "Layer channel blend"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column() #align=True)
        for key, val in blend_type_labels.items():
            col.operator('wm.y_set_layer_channel_blend_type', text=val).blend_type = key

def draw_expandable_list_options(layout):
    col = layout.column()
    yp = get_active_ypaint_node().node_tree.yp

    col.label(text='Layer List Options (Experimental)')
    col.separator()
    
    col.prop(yp, 'enable_expandable_subitems')
    row = col.row()
    row.active =  yp.enable_expandable_subitems
    row.prop(yp, 'enable_inline_subitems')

class YListItemOptionPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_y_list_item_option_popover"
    bl_label = "List Item Popover"
    bl_description = "List item popover"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 10

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_expandable_list_options(self.layout)

class YListItemOptionMenu(bpy.types.Menu):
    bl_idname = "NODE_PT_y_list_item_option_menu"
    bl_label = "List Item Menu"
    bl_description = "List item menu"
    
    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_expandable_list_options(self.layout)

def has_layer_input_options(layer):
    return (layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'MUSGRAVE', 'EDGE_DETECT', 'AO'} and not 
        (is_bl_newer_than(2, 81) and layer.type == 'VORONOI' and layer.voronoi_feature in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'}))

class YLayerChannelInputMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_channel_input_menu"
    bl_label = "Layer Channel Source"
    bl_description = "Replace layer channel source"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        ch = context.channel
        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\].*', ch.path_from_id())
        if m: 
            layer = yp.layers[int(m.group(1))]
            root_ch = yp.channels[int(m.group(2))]
            tree = get_tree(layer)
        else: return

        color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)
        
        col = self.layout.column()

        #col.label(text='Layer '+root_ch.name+' Source')
        col.label(text=root_ch.name+' Source')

        col.separator()

        # Layer input based on source output sockets
        col.separator()
        if color_ch and color_ch.enable and not color_ch.unpair_alpha and alpha_ch == ch:
            icon = 'RADIOBUT_ON' if not ch.override else 'RADIOBUT_OFF'

            if color_ch.socket_input_name == 'Alpha' and not color_ch.override and layer.type != 'GROUP':
                label = ' Solid Value (1.0)'
            else:
                label = 'Layer' if layer.type != 'GROUP' else 'Group'
                label += ' Alpha'

                source = get_layer_source(layer)
                if layer.type == 'IMAGE' and source and source.image:
                    label += ' ('+source.image.name+')'
                elif layer.type == 'VCOL' and source:
                    label += ' ('+source.attribute_name+')'

            op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
            op.socket_name = get_channel_input_socket_name(layer, ch)
            op.set_normal_input = False
        else:
            if layer.type in {'GROUP', 'PREV_LAYERS'}:
                label = 'Group ' if layer.type == 'GROUP' else 'Previous '
                label += root_ch.name
                icon = 'RADIOBUT_ON' if not ch.override else 'RADIOBUT_OFF'
                op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
                op.socket_name = ch.socket_input_name
                op.set_normal_input = False
            else:
                source = get_layer_source(layer)
                for outp in get_available_source_outputs(source, layer.type):
                    if not outp.enabled: continue
                    icon = 'RADIOBUT_ON' if get_channel_input_socket_name(layer, ch) == outp.name and not ch.override else 'RADIOBUT_OFF'
                    label = 'Layer ' + outp.name

                    if layer.type == 'IMAGE' and source and source.image:
                        label += ' ('+source.image.name+')'
                    elif layer.type == 'VCOL' and source:
                        label += ' ('+source.attribute_name+')'
                    if layer.type not in {'IMAGE', 'VCOL'}:
                        label += ' ('+layer_type_labels[layer.type]+')'

                    op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
                    op.socket_name = outp.name
                    op.set_normal_input = False

        col.separator()

        # Custom/Override Default
        label = 'Custom'
        if root_ch.type == 'VALUE':
            label += ' Value'
        else: label += ' Color'

        icon = 'RADIOBUT_ON' if ch.override and ch.override_type == 'DEFAULT' else 'RADIOBUT_OFF'
        op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
        op.socket_name = ''
        op.set_normal_input = False

        # Custom Data
        label = 'Custom '
        source = get_channel_source(ch, layer)
        if source:
            if ch.override_type == 'IMAGE':
                label += 'Image (' + source.image.name + ')'
            elif ch.override_type == 'VCOL':
                label += get_vertex_color_label()+' (' + source.attribute_name + ')'
            else:
                label += 'Data (' + channel_override_labels[ch.override_type] +')'
        else:
            label += 'Data'

        icon = 'RADIOBUT_ON' if ch.override and ch.override_type != 'DEFAULT' else 'RADIOBUT_OFF'
        col.menu("NODE_MT_y_replace_channel_override_menu", text=label, icon=icon)

class YLayerChannelInput1Menu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_channel_input_1_menu"
    bl_label = "Layer Normal Channel Source"
    bl_description = "Replace layer normal channel source"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        ch = context.channel
        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\].*', ch.path_from_id())
        if m: 
            layer = yp.layers[int(m.group(1))]
            root_ch = yp.channels[int(m.group(2))]
            tree = get_tree(layer)
        else: return
        
        col = self.layout.column()
        col.label(text='Normal Source')
        col.separator()

        # Layer input based on source output sockets

        if layer.type in {'GROUP', 'PREV_LAYERS'}:
            label = 'Group ' if layer.type == 'GROUP' else 'Previous '
            label += root_ch.name
            icon = 'RADIOBUT_ON' if not ch.override_1 else 'RADIOBUT_OFF'
            op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
            op.socket_name = ch.socket_input_1_name
            op.set_normal_input = True
        else:
            source = get_layer_source(layer)
            for outp in get_available_source_outputs(source, layer.type):
                if not outp.enabled: continue
                icon = 'RADIOBUT_ON' if get_channel_input_socket_name(layer, ch, secondary_input=True) == outp.name and not ch.override_1 else 'RADIOBUT_OFF'
                label = 'Layer ' + outp.name

                if layer.type not in {'IMAGE', 'VCOL'}:
                    label += ' ('+layer_type_labels[layer.type]+')'

                op = col.operator('wm.y_set_layer_channel_input', text=label, icon=icon)
                op.socket_name = outp.name
                op.set_normal_input = True

        col.separator()

        # Custom/Override Default
        icon = 'RADIOBUT_ON' if ch.override_1 and ch.override_1_type == 'DEFAULT' else 'RADIOBUT_OFF'
        op = col.operator('wm.y_set_layer_channel_input', text='Custom Color', icon=icon)
        #op.type = 'CUSTOM'
        op.socket_name = ''
        op.set_normal_input = True

        # Custom Data
        label = 'Custom Image'
        source = get_channel_source_1(ch, layer)
        if source:
            if ch.override_1_type == 'IMAGE':
                label += ' (' + source.image.name + ')'

        icon = 'RADIOBUT_ON' if ch.override_1 and ch.override_1_type != 'DEFAULT' else 'RADIOBUT_OFF'
        col.menu("NODE_MT_y_replace_channel_override_1_menu", text=label, icon=icon)

class YLayerMaskInputMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_mask_input_menu"
    bl_label = "Layer Mask Input"
    bl_description = "Layer Mask Input"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        mask = context.mask

        col = self.layout.column()

        source = get_mask_source(mask)
        for outp in get_available_source_outputs(source, mask.type):
            if not outp.enabled: continue
            icon = 'RADIOBUT_ON' if get_mask_input_socket_name(mask) == outp.name else 'RADIOBUT_OFF'

            label = ''
            if mask.type not in {'IMAGE', 'VCOL'}:
                label = mask_type_labels[mask.type] + ' '
            label += outp.name

            op = col.operator('wm.y_set_mask_input', text=label, icon=icon)
            op.socket_name = outp.name

class YLayerListSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_list_special_menu"
    bl_label = "Layer Special Menu"
    bl_description = "Layer Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()
        wm = context.window_manager
        wmp = wm.ypprops

        row = self.layout.row()
        col = row.column()
        
        col.operator('wm.y_merge_layer', text='Merge Layer Up', icon='TRIA_UP').direction = 'UP'
        col.operator('wm.y_merge_layer', text='Merge Layer Down', icon='TRIA_DOWN').direction = 'DOWN'

        col.separator()

        c = col.operator("wm.y_duplicate_layer", icon='COPY_ID', text='Duplicate Layer').duplicate_blank = False
        c = col.operator("wm.y_duplicate_layer", icon='COPY_ID', text='Duplicate Blank Layer').duplicate_blank = True

        col.separator()

        col.operator('wm.y_copy_layer', text='Copy Layer', icon='COPYDOWN').all_layers = False
        col.operator('wm.y_copy_layer', text='Copy All Layers', icon='COPYDOWN').all_layers = True
        col.operator('wm.y_paste_layer', text='Paste Layer(s)', icon='PASTEDOWN').paste_blank = False
        col.operator('wm.y_paste_layer', text='Paste Blank Layer(s)', icon='PASTEDOWN').paste_blank = True

        col.separator()
        col.operator('wm.y_rebake_baked_images', text='Rebake All Baked Images', icon_value=lib.get_icon('bake'))

        if is_udim_supported():
            col.operator('wm.y_refill_udim_tiles', text='Refill UDIM Tiles', icon_value=lib.get_icon('uv'))

        col = row.column()

        #col.context_pointer_set('space_data', context.screen.areas[6].spaces[0])
        #col.operator('image.save_as', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image:
            col.label(text=pgettext_iface('Active Image: ') + context.image.name, icon_value=lib.get_icon('image'))
        else:
            col.label(text='No active image')

        #col.separator()
        #col.operator('wm.y_transfer_layer_uv', text='Transfer Active Layer UV', icon_value=lib.get_icon('uv'))
        #col.operator('wm.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon_value=lib.get_icon('uv'))
        
        #if hasattr(context, 'image') and context.image:
        col.separator()
        op = col.operator('wm.y_resize_image', text='Resize Image', icon='FULLSCREEN_ENTER')
        if hasattr(context, 'layer'):
            op.layer_name = context.layer.name
        if hasattr(context, 'image'):
            op.image_name = context.image.name
        col.operator("wm.y_invert_image", icon='IMAGE_ALPHA')

        col.separator()
        col.operator('wm.y_pack_image', icon='PACKAGE')
        col.operator('wm.y_save_image', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image.packed_file:
            col.operator('wm.y_save_as_image', text='Unpack As Image...', icon='UGLYPACKAGE').copy = False
        else:
            if is_bl_newer_than(2, 80):
                col.operator('wm.y_save_as_image', text='Save As Image...').copy = False
            else: col.operator('wm.y_save_as_image', text='Save As Image...', icon='SAVE_AS').copy = False
        col.operator('wm.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

        col.separator()
        col.operator("wm.y_reload_image", icon='FILE_REFRESH')

        col.separator()

        if hasattr(context, 'image'):
            col.menu("NODE_MT_y_image_convert_menu", text='Convert Image')

        if is_bl_newer_than(2, 80): col.operator('wm.y_save_pack_all', text='Save/Pack All Images')
        else: col.operator('wm.y_save_pack_all', text='Save/Pack All Images', icon='FILE_TICK')

        if is_bl_newer_than(2, 80):
            col.separator()
            col.operator('wm.y_export_layers', text='Export Layers as PSD', icon='EXPORT')

class YOpenImagesToSingleLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_open_images_to_single_layer_menu"
    bl_label = "Open Images to Single Layer Menu"
    bl_description = "Open Images to Single Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        col.operator("wm.y_open_images_to_single_layer", icon='FILE_FOLDER', text='From Directory')
        col.operator("wm.y_open_images_from_material_to_single_layer", icon='MATERIAL_DATA', text='From Material').asset_library_path = ''

class YImageConvertToMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_image_convert_menu"
    bl_label = "Convert Image to Menu"
    bl_description = "Convert Image to Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        text = 'Convert to ' + ('Byte ' if context.image.is_float else 'Float ') + 'Image'
        col.operator("image.y_convert_image_bit_depth", icon='IMAGE_DATA', text=text)

        if is_udim_supported():
            #col.separator()
            text = 'Convert to ' + ('Non UDIM ' if context.image.source == 'TILED' else 'UDIM ') + 'Image'
            col.operator("image.y_convert_image_tiled", icon='IMAGE_DATA', text=text)

        col.separator()
        if context.image.yia.is_image_atlas or context.image.yua.is_udim_atlas:
            col.operator("wm.y_convert_to_standard_image", icon='IMAGE_DATA', text='Convert to standard Image').all_images = False
            col.operator("wm.y_convert_to_standard_image", icon='IMAGE_DATA', text='Convert All Image Atlas to standard Images').all_images = True
        else:
            col.operator("wm.y_convert_to_image_atlas", icon='IMAGE_DATA', text='Convert to Image Atlas').all_images = False
            col.operator("wm.y_convert_to_image_atlas", icon='IMAGE_DATA', text='Convert All Images to Image Atlas').all_images = True

class YUVSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_uv_special_menu"
    bl_label = "UV Special Menu"
    bl_description = "UV Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        col.operator('wm.y_transfer_layer_uv', text='Transfer UV', icon_value=lib.get_icon('uv'))
        col.operator('wm.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon_value=lib.get_icon('uv'))

class YModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_modifier_menu"
    bl_label = "Modifier Menu"
    bl_description = "Modifier Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'modifier') and hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        if not hasattr(context, 'parent') or not hasattr(context, 'modifier'):
            col.label(text='ERROR: Context has no parent or modifier!', icon='ERROR')
            return

        op = col.operator('wm.y_move_ypaint_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('wm.y_move_ypaint_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if is_bl_newer_than(2, 80):
            op = col.operator('wm.y_remove_ypaint_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('wm.y_remove_ypaint_modifier', icon='ZOOMOUT', text='Remove Modifier')

        #if hasattr(context, 'layer') and context.modifier.type in {'RGB_TO_INTENSITY', 'OVERRIDE_COLOR'}:
        #    col.separator()
        #    col.prop(context.modifier, 'shortcut', text='Shortcut on layer list')

class YModifier1Menu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_modifier1_menu"
    bl_label = "Modifier Menu"
    bl_description = "Modifier Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'modifier') and hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        if not hasattr(context, 'parent') or not hasattr(context, 'modifier'):
            col.label(text='ERROR: Context has no parent or modifier!', icon='ERROR')
            return

        op = col.operator('wm.y_move_normalmap_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('wm.y_move_normalmap_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if is_bl_newer_than(2, 80):
            op = col.operator('wm.y_remove_normalmap_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('wm.y_remove_normalmap_modifier', icon='ZOOMOUT', text='Remove Modifier')

class YMaskModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_mask_modifier_menu"
    bl_label = "Mask Modifier Menu"
    bl_description = "Mask Modifier Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'modifier') and hasattr(context, 'mask') and hasattr(context, 'layer')
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        if not hasattr(context, 'mask') or not hasattr(context, 'modifier') or not hasattr(context, 'layer'):
            col.label(text='ERROR: Context has no mask, modifier, or layer!', icon='ERROR')
            return

        op = col.operator('wm.y_move_mask_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('wm.y_move_mask_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()

        if is_bl_newer_than(2, 80):
            op = col.operator('wm.y_remove_mask_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('wm.y_remove_mask_modifier', icon='ZOOMOUT', text='Remove Modifier')

class YTransitionBumpMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_bump_menu"
    bl_label = "Transition Bump Menu"
    bl_description = "Transition Bump Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        #col.label(text=context.parent.path_from_id())
        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        if is_bl_newer_than(2, 80):
            col.operator('wm.y_hide_transition_effect', text='Remove Transition Bump', icon='REMOVE').type = 'BUMP'
        else: col.operator('wm.y_hide_transition_effect', text='Remove Transition Bump', icon='ZOOMOUT').type = 'BUMP'

class YTransitionRampMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ramp_menu"
    bl_label = "Transition Ramp Menu"
    bl_description = "Transition Ramp Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        col.prop(context.parent, 'transition_ramp_intensity_unlink', text='Unlink Ramp with Channel Intensity')

        col.separator()

        if is_bl_newer_than(2, 80):
            col.operator('wm.y_hide_transition_effect', text='Remove Transition Ramp', icon='REMOVE').type = 'RAMP'
        else: col.operator('wm.y_hide_transition_effect', text='Remove Transition Ramp', icon='ZOOMOUT').type = 'RAMP'

class YTransitionAOMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ao_menu"
    bl_label = "Transition AO Menu"
    bl_description = "Transition AO Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        #return hasattr(context, 'parent') and hasattr(context, 'layer')
        return get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout

        trans_bump = get_transition_bump_channel(context.layer)
        trans_bump_flip = (trans_bump and trans_bump.transition_bump_flip) or context.layer.type == 'BACKGROUND'

        col = layout.column()

        if not hasattr(context, 'parent') or not hasattr(context, 'layer'):
            col.label(text='ERROR: Context has no parent or layer!', icon='ERROR')
            return

        col.active = not trans_bump_flip
        col.prop(context.parent, 'transition_ao_intensity_unlink', text='Unlink AO with Channel Intensity')

        col.separator()

        col = layout.column()
        if is_bl_newer_than(2, 80):
            col.operator('wm.y_hide_transition_effect', text='Remove Transition AO', icon='REMOVE').type = 'AO'
        else: col.operator('wm.y_hide_transition_effect', text='Remove Transition AO', icon='ZOOMOUT').type = 'AO'

def new_mask_button(layout, operator, text, lib_icon='', otype='', target_type='', modifier_type='', overwrite_current=None):
    if lib_icon:
        op = layout.operator(operator, icon_value=lib.get_icon(lib_icon), text=text)
    else: op = layout.operator(operator, text=text)

    if otype != '': op.type = otype
    if target_type != '': op.target_type = target_type
    if overwrite_current != None: op.overwrite_current = overwrite_current
    if modifier_type != '': op.modifier_type = modifier_type

    return op

def draw_new_image_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_new_layer_mask', 'New Image Mask', lib_icon='image', otype='IMAGE')
    op = new_mask_button(layout, 'wm.y_open_image_as_mask', 'Open Image as Mask...') #, lib_icon='open_image')
    op.texcoord_type = 'UV'
    op.file_browser_filepath = ''
    new_mask_button(layout, 'wm.y_open_existing_data_as_mask', 'Open Existing Image as Mask', otype='IMAGE') #, lib_icon='open_image')

def draw_new_vcol_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_new_layer_mask', 'New '+get_vertex_color_label()+' Mask', lib_icon='vertex_color', otype='VCOL')
    new_mask_button(layout, 'wm.y_open_existing_data_as_mask', 'Open Existing '+get_vertex_color_label()+' as Mask', otype='VCOL') # lib_icon='vertex_color')

    new_mask_button(layout, 'wm.y_new_layer_mask', 'Color ID', lib_icon='color', otype='COLOR_ID')

def draw_new_adjustment_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Invert', otype='MODIFIER', modifier_type='INVERT', lib_icon='modifier')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Ramp', otype='MODIFIER', modifier_type='RAMP') #, lib_icon='modifier')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Curve', otype='MODIFIER', modifier_type='CURVE') #, lib_icon='modifier')

def draw_new_texture_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Brick', otype='BRICK', lib_icon='texture')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Checker', otype='CHECKER')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Gradient', otype='GRADIENT')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Magic', otype='MAGIC')
    if not is_bl_newer_than(4, 1): new_mask_button(layout, 'wm.y_new_layer_mask', 'Musgrave', otype='MUSGRAVE')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Noise', otype='NOISE')
    if is_bl_newer_than(4, 3): new_mask_button(layout, 'wm.y_new_layer_mask', 'Gabor', otype='GABOR')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Voronoi', otype='VORONOI')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Wave', otype='WAVE')

def draw_new_generated_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Object Index', otype='OBJECT_INDEX', lib_icon='object_index')
    new_mask_button(layout, 'wm.y_new_layer_mask', 'Backface', otype='BACKFACE', lib_icon='backface')
    layout.separator()

    if is_bl_newer_than(2, 93):
        new_mask_button(layout, 'wm.y_new_layer_mask', 'Ambient Occlusion', otype='AO', lib_icon='edge_detect')
        new_mask_button(layout, 'wm.y_new_layer_mask', 'Edge Detect', otype='EDGE_DETECT')
        layout.separator()

    new_mask_button(layout, 'wm.y_new_layer_mask', 'Fake Lighting', lib_icon='hemi', otype='HEMI')

def draw_new_bake_as_layer_mask_menu(layout):
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Ambient Occlusion', lib_icon='bake', otype='AO', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Pointiness', otype='POINTINESS', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Cavity', otype='CAVITY', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Dust', otype='DUST', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Paint Base', otype='PAINT_BASE', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Thickness', otype='THICKNESS', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Wireframe', otype='WIREFRAME', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Curvature', otype='CURVATURE', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Bevel Grayscale', otype='BEVEL_MASK', target_type='MASK', overwrite_current=False)
    new_mask_button(layout, 'wm.y_bake_to_layer', 'Selected Vertices', otype='SELECTED_VERTICES', target_type='MASK', overwrite_current=False)
    if is_bl_newer_than(2, 77):
        layout.separator()
        new_mask_button(layout, 'wm.y_bake_to_layer', 'Other Objects Color', otype='OTHER_OBJECT_EMISSION', target_type='MASK', overwrite_current=False)

class YAddImageLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_image_layer_mask_menu"
    bl_description = 'Add Image Layer Mask'
    bl_label = "Add Image Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_image_layer_mask_menu(self.layout)

class YAddVColLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_vcol_layer_mask_menu"
    bl_description = 'Add Attributes Layer Mask'
    bl_label = "Add Attributes Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_vcol_layer_mask_menu(self.layout)

class YAddAdjustmentLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_adjustment_layer_mask_menu"
    bl_description = 'Add Adjustment Layer Mask'
    bl_label = "Add Adjustment Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_adjustment_layer_mask_menu(self.layout)

class YAddTextureLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_texture_layer_mask_menu"
    bl_description = 'Add Texture Layer Mask'
    bl_label = "Add Texture Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_texture_layer_mask_menu(self.layout)

class YAddGeneratedLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_generated_layer_mask_menu"
    bl_description = 'Add Generated Layer Mask'
    bl_label = "Add Generated Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_generated_layer_mask_menu(self.layout)

class YAddBakeAsLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_bake_as_layer_mask_menu"
    bl_description = 'Add Bake as Layer Mask'
    bl_label = "Add Bake as Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        draw_new_bake_as_layer_mask_menu(self.layout)

class YAddLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_layer_mask_menu"
    bl_description = 'Add Layer Mask'
    bl_label = "Add Layer Mask"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        ypup = get_user_preferences()

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = yp.layers[yp.active_layer_index] if yp.active_layer_index >= 0 and yp.active_layer_index <= len(yp.layers) else None

        layout = self.layout
        row = layout.row()
        col = row.column(align=True)

        if not layer:
            col.label(text='ERROR: Context has no layer!', icon='ERROR')
            return

        col.context_pointer_set('layer', layer)

        if is_bl_newer_than(4) and not ypup.ui_legacy_add_layer_menu:
            if self.layout.operator_context == 'EXEC_REGION_WIN':
                self.layout.operator_context = 'INVOKE_REGION_WIN'
                col.operator(
                    "WM_OT_search_single_menu",
                    text="Search...",
                    icon='VIEWZOOM',
                ).menu_idname = "NODE_MT_y_add_layer_mask_menu"
                col.separator()

            self.layout.operator_context = 'INVOKE_REGION_WIN'

            col.menu("NODE_MT_y_add_image_layer_mask_menu", text='Image', icon_value=lib.get_icon('image'))
            col.menu("NODE_MT_y_add_vcol_layer_mask_menu", text=get_vertex_color_label(), icon_value=lib.get_icon('vertex_color'))
            col.menu("NODE_MT_y_add_texture_layer_mask_menu", text='Texture', icon_value=lib.get_icon('texture'))
            col.separator()
            col.menu("NODE_MT_y_add_generated_layer_mask_menu", text='Geometry', icon_value=lib.get_icon('edge_detect'))
            col.menu("NODE_MT_y_add_bake_as_layer_mask_menu", text='Bake as Mask', icon_value=lib.get_icon('bake'))
            col.menu("NODE_MT_y_add_adjustment_layer_mask_menu", text='Adjustment', icon_value=lib.get_icon('modifier'))
        else:
            col.label(text='Image Mask:')
            draw_new_image_layer_mask_menu(col)
            col.separator()

            col.label(text=get_vertex_color_label()+' Mask:')
            draw_new_vcol_layer_mask_menu(col)
            col.separator()

            col.label(text='Adjustment Mask:')
            draw_new_adjustment_layer_mask_menu(col)

            col = row.column(align=True)
            col.label(text='Generated Mask:')
            draw_new_texture_layer_mask_menu(col)

            col.separator()
            draw_new_generated_layer_mask_menu(col)

            col = row.column(align=True)
            col.label(text='Bake as Mask:')
            draw_new_bake_as_layer_mask_menu(col)

class YLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_mask_menu"
    bl_description = 'Layer Mask Menu'
    bl_label = "Layer Mask Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'mask') and hasattr(context, 'layer')
        return get_active_ypaint_node()

    def draw(self, context):
        #print(context.mask)
        mask = context.mask
        layer = context.layer
        layer_tree = get_tree(layer)
        layout = self.layout

        row = layout.row()
        col = row.column(align=True)

        if not hasattr(context, 'layer') or not hasattr(context, 'mask'):
            col.label(text='ERROR: Context has no layer or mask!', icon='ERROR')
            return

        if mask.type == 'IMAGE':
            mask_tree = get_mask_tree(mask, layer_tree)
            source = mask_tree.nodes.get(mask.source)
            col.context_pointer_set('image', source.image)
            col.operator('wm.y_invert_image', text='Invert Image', icon='IMAGE_ALPHA')

        col.separator()

        op = col.operator('wm.y_move_layer_mask', icon='TRIA_UP', text='Move Mask Up')
        op.direction = 'UP'
        op = col.operator('wm.y_move_layer_mask', icon='TRIA_DOWN', text='Move Mask Down')
        op.direction = 'DOWN'

        col.separator()

        op = col.operator('wm.y_merge_mask', icon='TRIA_UP', text='Merge Mask Up')
        op.direction = 'UP'
        op = col.operator('wm.y_merge_mask', icon='TRIA_DOWN', text='Merge Mask Down')
        op.direction = 'DOWN'

        col.separator()

        col.context_pointer_set('entity', mask)
        col.operator('wm.y_bake_entity_to_image', icon_value=lib.get_icon('bake'), text='Bake as Image')

        col.separator()

        #op = col.operator('wm.y_transfer_layer_uv', icon_value=lib.get_icon('uv'), text='Transfer UV')

        #col.separator()

        if is_bl_newer_than(2, 80):
            col.operator('wm.y_remove_layer_mask', text='Remove Mask', icon='REMOVE')
        else: col.operator('wm.y_remove_layer_mask', text='Remove Mask', icon='ZOOMOUT')

        col = row.column(align=True)
        col.label(text='Add Modifier')

        col.operator('wm.y_new_mask_modifier', text='Invert', icon_value=lib.get_icon('modifier')).type = 'INVERT'
        col.operator('wm.y_new_mask_modifier', text='Ramp', icon_value=lib.get_icon('modifier')).type = 'RAMP'
        col.operator('wm.y_new_mask_modifier', text='Curve', icon_value=lib.get_icon('modifier')).type = 'CURVE'

        #if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
        #    col.separator()
        #    col.prop(mask, 'enable_blur_vector', text='Blur Vector')

class YMaterialSpecialMenu(bpy.types.Menu):
    bl_idname = "MATERIAL_MT_y_special_menu"
    bl_label = "Material Special Menu"
    bl_description = 'Material Special Menu'

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        col = self.layout.column()
        col.operator('wm.y_select_all_material_polygons', icon='FACESEL')
        col.operator('wm.y_rename_uv_using_the_same_material', icon='GROUP_UVS')

class YReplaceChannelOverrideMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_replace_channel_override_menu"
    bl_label = "Replace Channel Override Menu"
    bl_description = 'Replace Channel Override'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        #row = self.layout.row()
        #col = row.column()
        col = self.layout.column()

        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if m:
            ch = context.parent
            yp = ch.id_data.yp
            layer = yp.layers[int(m.group(1))]
            root_ch = yp.channels[int(m.group(2))]
            tree = get_tree(layer)
        else:
            return

        #col.label(text='Override Type:')
        col.label(text='Custom Data Type')

        #icon = 'RADIOBUT_ON' if ch.override_type == 'DEFAULT' else 'RADIOBUT_OFF'
        #if root_ch.type == 'VALUE':
        #    col.operator('wm.y_replace_layer_channel_override', text='Value', icon=icon).type = 'DEFAULT'
        #else: col.operator('wm.y_replace_layer_channel_override', text='Color', icon=icon).type = 'DEFAULT'

        col.separator()

        label = 'Image'
        cache_image = tree.nodes.get(ch.cache_image)
        #source = tree.nodes.get(ch.source)
        source = get_channel_source(ch, layer)
        if cache_image:
            label += ': ' + cache_image.image.name
        elif (ch.override_type == 'IMAGE' and source):
            label += ': ' + source.image.name

        icon = 'RADIOBUT_ON' if ch.override and ch.override_type == 'IMAGE' else 'RADIOBUT_OFF'
        if cache_image and (ch.override_type != 'IMAGE' or not ch.override):
            col.operator('wm.y_replace_layer_channel_override', text=label, icon=icon).type = 'IMAGE'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)

        ccol = row.column(align=True)
        ccol.operator('wm.y_open_image_to_override_layer_channel', text='Open Image...', icon_value=lib.get_icon('open_image'))
        ccol.operator('wm.y_open_existing_data_to_override_channel', text='Open Existing Image', icon_value=lib.get_icon('open_image')).type = 'IMAGE'
        
        col.separator()

        label = get_vertex_color_label()
        cache_vcol = tree.nodes.get(ch.cache_vcol)
        #source = tree.nodes.get(ch.source)
        if cache_vcol:
            label += ': ' + get_source_vcol_name(cache_vcol)
        elif (ch.override_type == 'VCOL' and source):
            label += ': ' + get_source_vcol_name(source)

        icon = 'RADIOBUT_ON' if ch.override and ch.override_type == 'VCOL' else 'RADIOBUT_OFF'
        if cache_vcol and (ch.override_type != 'VCOL' or not ch.override):
            col.operator('wm.y_replace_layer_channel_override', text=label, icon=icon).type = 'VCOL'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)

        ccol = row.column(align=True)
        ccol.operator('wm.y_new_vcol_to_override_channel', text='New '+get_vertex_color_label(), icon_value=lib.get_icon('vertex_color'))
        ccol.operator('wm.y_open_existing_data_to_override_channel', text='Use Existing '+get_vertex_color_label(), icon_value=lib.get_icon('vertex_color')).type = 'VCOL'

        col.separator()

        for item in channel_override_type_items:
            if item[0] == 'MUSGRAVE' and is_bl_newer_than(4, 1): continue
            if item[0] == 'GABOR' and not is_bl_newer_than(4, 3): continue

            if ch.override and item[0] == ch.override_type:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            if item[0] in {'DEFAULT', 'IMAGE', 'VCOL'}: continue

            col.operator('wm.y_replace_layer_channel_override', text=item[1], icon=icon).type = item[0]

class YReplaceChannelOverride1Menu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_replace_channel_override_1_menu"
    bl_label = "Replace Channel Override Menu"
    bl_description = 'Replace Channel Override'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        #row = self.layout.row()
        #col = row.column()
        col = self.layout.column()

        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if m:
            ch = context.parent
            yp = ch.id_data.yp
            layer = yp.layers[int(m.group(1))]
            root_ch = yp.channels[int(m.group(2))]
            tree = get_tree(layer)
        else:
            return

        col.label(text='Custom Image:')

        #icon = 'RADIOBUT_ON' if ch.override_1_type == 'DEFAULT' else 'RADIOBUT_OFF'
        ##if root_ch.type == 'VALUE':
        ##    col.operator('wm.y_replace_layer_channel_override_1', text='Value', icon=icon).type = 'DEFAULT'
        ##else: 
        #col.operator('wm.y_replace_layer_channel_override_1', text='Color', icon=icon).type = 'DEFAULT'

        #col.separator()

        label = 'Image'
        cache_1_image = tree.nodes.get(ch.cache_1_image)
        #source = tree.nodes.get(ch.source)
        source = get_channel_source_1(ch, layer)
        if cache_1_image:
            label += ': ' + cache_1_image.image.name
        elif (ch.override_1_type == 'IMAGE' and source):
            label += ': ' + source.image.name

        icon = 'RADIOBUT_ON' if ch.override_1 and ch.override_1_type == 'IMAGE' else 'RADIOBUT_OFF'
        if cache_1_image and (ch.override_1_type != 'IMAGE' or not ch.override_1):
            col.operator('wm.y_replace_layer_channel_override_1', text=label, icon=icon).type = 'IMAGE'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)
        #ccol = row.column(align=True)
        #ccol.label(text='', icon='BLANK1')

        ccol = row.column(align=True)
        ccol.operator('wm.y_open_image_to_override_1_layer_channel', text='Open Image...', icon_value=lib.get_icon('open_image'))
        ccol.operator('wm.y_open_existing_data_to_override_1_channel', text='Open Existing Image', icon_value=lib.get_icon('open_image'))

class YChannelSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_channel_experimental_menu"
    bl_label = "Channel Special Menu"
    bl_description = 'Bake channel or add channel modifiers'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        col.label(text='Experimental')
        col.operator('wm.y_bake_channel_to_vcol', text='Bake Channel to '+get_vertex_color_label(), icon_value=lib.get_icon('vertex_color')).all_materials = False
        col.operator('wm.y_bake_channel_to_vcol', text='Bake Channel to '+get_vertex_color_label()+' (Batch All Materials)', icon_value=lib.get_icon('vertex_color')).all_materials = True
        
class YLayerChannelSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_channel_special_menu"
    bl_label = "Layer Channel Special Menu"
    bl_description = 'Add modifiers or effects to layer channel'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        row = self.layout.row()

        col = row.column()

        if not hasattr(context, 'parent'):
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        yp = context.parent.id_data.yp
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]

        is_group_layer = layer.type in {'GROUP', 'PREV_LAYERS'}

        col.separator()

        col.label(text='Add Modifier')

        #if root_ch.special_type == 'NORMAL':
        #    col.operator('wm.y_new_normalmap_modifier', text='Invert', icon_value=lib.get_icon('modifier')).type = 'INVERT'
        #    col.operator('wm.y_new_normalmap_modifier', text='Math', icon_value=lib.get_icon('modifier')).type = 'MATH'
        #else:

        # List the items
        for mt in modifier_common.modifier_type_items:
            # Override color and multiplier modifier are deprecated
            if mt[0] == 'OVERRIDE_COLOR': continue
            if mt[0] == 'MULTIPLIER': continue
            col.operator('wm.y_new_ypaint_modifier', text=mt[1], icon_value=lib.get_icon('modifier')).type = mt[0]

        if root_ch.special_type not in {'NORMAL', 'VDISP'}:
            col = row.column()
            col.label(text='Transition Effects')
            if root_ch.special_type == 'HEIGHT':
                col.operator('wm.y_show_transition_bump', text='Transition Bump', icon_value=lib.get_icon('background'))
            else:
                col.operator('wm.y_show_transition_ramp', text='Transition Ramp', icon_value=lib.get_icon('background'))
                col.operator('wm.y_show_transition_ao', text='Transition AO', icon_value=lib.get_icon('background'))

class YPreviewModeChannelMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_preview_mode_channel_menu"
    bl_label = "Preview Mode Channel Menu"
    bl_description = 'Preview Mode channel'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        col = self.layout.column()

        for i, ch in enumerate(yp.channels):
            if i == yp.preview_mode_channel_index:
                col.label(text=ch.name, icon='RADIOBUT_ON')
            else: col.operator('wm.y_select_preview_mode_channel', text=ch.name, icon='RADIOBUT_OFF').channel_idx = i

class YLayerTypeMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_type_menu"
    bl_label = "Layer Type Menu"
    bl_description = 'Replace layer source'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        layer = context.layer
        tree = get_tree(layer)
        ypup = get_user_preferences()
        
        col = self.layout.column()
        col.label(text='Layer Source')
        col.separator()

        folder_emoji = '🗁  ' if is_bl_newer_than(3, 4) else '>  '

        cache_image = tree.nodes.get(layer.cache_image)
        if layer.type != 'IMAGE' and cache_image and cache_image.image:
            op = col.operator('wm.y_replace_layer_type', text='Image: ' + cache_image.image.name, icon='RADIOBUT_OFF')
            op.type = 'IMAGE'
            op.load_item = False
            op.item_name = ''
        else:
            source = get_layer_source(layer)
            suffix = ''
            if layer.type == 'IMAGE' and source and source.image:
                suffix += ': ' + source.image.name
            icon = 'RADIOBUT_ON' if layer.type == 'IMAGE' else 'RADIOBUT_OFF'
            col.label(text='Image' + suffix, icon=icon)

        label = 'Open Image' if layer.type != 'IMAGE' else 'Replace Image'
        op = col.operator('wm.y_open_image_to_replace_layer', text=folder_emoji+label)

        label = 'Open Existing Image' if layer.type != 'IMAGE' else 'Replace with Existing Image'
        #label = 'Open Existing Image'
        op = col.operator('wm.y_replace_layer_type', text=folder_emoji+label)
        op.type = 'IMAGE'
        op.load_item = True

        col.separator()

        cache_vcol = tree.nodes.get(layer.cache_vcol)
        if layer.type != 'VCOL' and cache_vcol and cache_vcol.attribute_name != '':
            op = col.operator('wm.y_replace_layer_type', text=get_vertex_color_label()+': ' + cache_vcol.attribute_name, icon='RADIOBUT_OFF')
            op.type = 'VCOL'
            op.load_item = False
            op.item_name = ''
        else:
            source = get_layer_source(layer)
            suffix = ''
            if layer.type == 'VCOL' and source and source.attribute_name != '':
                suffix += ': ' + source.attribute_name
            icon = 'RADIOBUT_ON' if layer.type == 'VCOL' else 'RADIOBUT_OFF'
            col.label(text=get_vertex_color_label() + suffix, icon=icon)

        label = 'Open Existing '+get_vertex_color_label() if layer.type != 'VCOL' else 'Replace '+get_vertex_color_label()
        op = col.operator('wm.y_replace_layer_type', text=folder_emoji+label) #, icon_value=lib.get_icon('vertex_color'))
        op.type = 'VCOL'
        op.load_item = True

        col.separator()

        icon = 'RADIOBUT_ON' if layer.type == 'COLOR' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Solid Color', icon=icon).type = 'COLOR'

        if ypup.developer_mode or layer.type == 'BACKGROUND':
            icon = 'RADIOBUT_ON' if layer.type == 'BACKGROUND' else 'RADIOBUT_OFF'
            col.operator('wm.y_replace_layer_type', text='Background', icon=icon).type = 'BACKGROUND'

        icon = 'RADIOBUT_ON' if layer.type == 'GROUP' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Group', icon=icon).type = 'GROUP'

        icon = 'RADIOBUT_ON' if layer.type == 'PREV_LAYERS' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_layer_type", icon=icon, text='Adjustment (Previous Layers)').type = 'PREV_LAYERS'

        col.separator()

        icon = 'RADIOBUT_ON' if layer.type == 'BRICK' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Brick', icon=icon).type = 'BRICK'

        icon = 'RADIOBUT_ON' if layer.type == 'CHECKER' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Checker', icon=icon).type = 'CHECKER'

        icon = 'RADIOBUT_ON' if layer.type == 'GRADIENT' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Gradient', icon=icon).type = 'GRADIENT'

        icon = 'RADIOBUT_ON' if layer.type == 'MAGIC' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Magic', icon=icon).type = 'MAGIC'

        if not is_bl_newer_than(4, 1): 
            icon = 'RADIOBUT_ON' if layer.type == 'MUSGRAVE' else 'RADIOBUT_OFF'
            col.operator('wm.y_replace_layer_type', text='Musgrave', icon=icon).type = 'MUSGRAVE'

        icon = 'RADIOBUT_ON' if layer.type == 'NOISE' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Noise', icon=icon).type = 'NOISE'

        if is_bl_newer_than(4, 3): 
            icon = 'RADIOBUT_ON' if layer.type == 'GABOR' else 'RADIOBUT_OFF'
            col.operator('wm.y_replace_layer_type', text='Gabor', icon=icon).type = 'GABOR'

        icon = 'RADIOBUT_ON' if layer.type == 'VORONOI' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Voronoi', icon=icon).type = 'VORONOI'

        icon = 'RADIOBUT_ON' if layer.type == 'WAVE' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Wave', icon=icon).type = 'WAVE'

        col.separator()
        icon = 'RADIOBUT_ON' if layer.type == 'HEMI' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_layer_type", icon=icon, text='Fake Lighting').type = 'HEMI'

        icon = 'RADIOBUT_ON' if layer.type == 'AO' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_layer_type", icon=icon, text='Ambient Occlusion').type = 'AO'

        icon = 'RADIOBUT_ON' if layer.type == 'EDGE_DETECT' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_layer_type", icon=icon, text='Edge Detect').type = 'EDGE_DETECT'

        col.separator()

        icon = 'RADIOBUT_ON' if layer.type == 'INPUT_BUNDLE' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_layer_type', text='Input Bundle', icon=icon).type = 'INPUT_BUNDLE'

class YMaskTypeMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_mask_type_menu"
    bl_label = "Mask Type Menu"
    bl_description = 'Replace mask source'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        mask = context.mask
        layer = context.layer
        tree = get_tree(layer)
        
        col = self.layout.column()
        col.label(text='Mask Source')
        col.separator()

        folder_emoji = '🗁  ' if is_bl_newer_than(3, 4) else '>  '

        cache_image = tree.nodes.get(mask.cache_image)
        if mask.type != 'IMAGE' and cache_image and cache_image.image:
            op = col.operator('wm.y_replace_mask_type', text='Image: ' + cache_image.image.name, icon='RADIOBUT_OFF')
            op.type = 'IMAGE'
            op.load_item = False
            op.item_name = ''
        else:
            source = get_mask_source(mask)
            suffix = ''
            if mask.type == 'IMAGE' and source and source.image:
                suffix += ': ' + source.image.name
            icon = 'RADIOBUT_ON' if mask.type == 'IMAGE' else 'RADIOBUT_OFF'
            col.label(text='Image' + suffix, icon=icon)

        label = 'Open Image' if mask.type != 'IMAGE' else 'Replace Image'
        op = col.operator('wm.y_open_image_to_replace_mask', text=folder_emoji+label)

        label = 'Open Existing Image' if mask.type != 'IMAGE' else 'Replace with Existing Image'
        op = col.operator('wm.y_replace_mask_type', text=folder_emoji+label)
        op.type = 'IMAGE'
        op.load_item = True

        col.separator()

        cache_vcol = tree.nodes.get(mask.cache_vcol)
        if mask.type != 'VCOL' and cache_vcol and cache_vcol.attribute_name != '':
            op = col.operator('wm.y_replace_mask_type', text=get_vertex_color_label()+': ' + cache_vcol.attribute_name, icon='RADIOBUT_OFF')
            op.type = 'VCOL'
            op.load_item = False
            op.item_name = ''
        else:
            source = get_mask_source(mask)
            suffix = ''
            if mask.type == 'VCOL' and source and source.attribute_name != '':
                suffix += ': ' + source.attribute_name
            icon = 'RADIOBUT_ON' if mask.type == 'VCOL' else 'RADIOBUT_OFF'
            col.label(text=get_vertex_color_label() + suffix, icon=icon)

        label = 'Open Existing '+get_vertex_color_label() if mask.type != 'VCOL' else 'Replace '+get_vertex_color_label()
        op = col.operator('wm.y_replace_mask_type', text=folder_emoji+label) #, icon_value=lib.get_icon('vertex_color'))
        op.type = 'VCOL'
        op.load_item = True

        col.separator()

        #icon = 'RADIOBUT_ON' if mask.type == 'COLOR' else 'RADIOBUT_OFF'
        #col.operator('wm.y_replace_mask_type', text='Solid Color', icon=icon).type = 'COLOR'

        #icon = 'RADIOBUT_ON' if mask.type == 'BACKGROUND' else 'RADIOBUT_OFF'
        #col.operator('wm.y_replace_mask_type', text='Background', icon=icon).type = 'BACKGROUND'

        #icon = 'RADIOBUT_ON' if mask.type == 'GROUP' else 'RADIOBUT_OFF'
        #col.operator('wm.y_replace_mask_type', text='Group', icon=icon).type = 'GROUP'

        #col.separator()

        icon = 'RADIOBUT_ON' if mask.type == 'BRICK' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Brick', icon=icon).type = 'BRICK'

        icon = 'RADIOBUT_ON' if mask.type == 'CHECKER' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Checker', icon=icon).type = 'CHECKER'

        icon = 'RADIOBUT_ON' if mask.type == 'GRADIENT' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Gradient', icon=icon).type = 'GRADIENT'

        icon = 'RADIOBUT_ON' if mask.type == 'MAGIC' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Magic', icon=icon).type = 'MAGIC'

        if not is_bl_newer_than(4, 1): 
            icon = 'RADIOBUT_ON' if mask.type == 'MUSGRAVE' else 'RADIOBUT_OFF'
            col.operator('wm.y_replace_mask_type', text='Musgrave', icon=icon).type = 'MUSGRAVE'

        icon = 'RADIOBUT_ON' if mask.type == 'NOISE' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Noise', icon=icon).type = 'NOISE'

        if is_bl_newer_than(4, 3): 
            icon = 'RADIOBUT_ON' if mask.type == 'GABOR' else 'RADIOBUT_OFF'
            col.operator('wm.y_replace_mask_type', text='Gabor', icon=icon).type = 'GABOR'

        icon = 'RADIOBUT_ON' if mask.type == 'VORONOI' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Voronoi', icon=icon).type = 'VORONOI'

        icon = 'RADIOBUT_ON' if mask.type == 'WAVE' else 'RADIOBUT_OFF'
        col.operator('wm.y_replace_mask_type', text='Wave', icon=icon).type = 'WAVE'

        col.separator()
        icon = 'RADIOBUT_ON' if mask.type == 'HEMI' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Fake Lighting').type = 'HEMI'

        col.separator()

        icon = 'RADIOBUT_ON' if mask.type == 'COLOR_ID' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Color ID').type = 'COLOR_ID'

        icon = 'RADIOBUT_ON' if mask.type == 'OBJECT_INDEX' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Object Index').type = 'OBJECT_INDEX'

        icon = 'RADIOBUT_ON' if mask.type == 'BACKFACE' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Backface').type = 'BACKFACE'

        icon = 'RADIOBUT_ON' if mask.type == 'AO' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Ambient Occlusion').type = 'AO'

        icon = 'RADIOBUT_ON' if mask.type == 'EDGE_DETECT' else 'RADIOBUT_OFF'
        col.operator("wm.y_replace_mask_type", icon=icon, text='Edge Detect').type = 'EDGE_DETECT'

        col.separator()

        icon = 'RADIOBUT_ON' if mask.type == 'MODIFIER' and mask.modifier_type == 'INVERT' else 'RADIOBUT_OFF'
        op = col.operator("wm.y_replace_mask_type", icon=icon, text='Invert Modifier')
        op.type = 'MODIFIER'
        op.modifier_type = 'INVERT'

        icon = 'RADIOBUT_ON' if mask.type == 'MODIFIER' and mask.modifier_type == 'RAMP' else 'RADIOBUT_OFF'
        op = col.operator("wm.y_replace_mask_type", icon=icon, text='Ramp Modifier')
        op.type = 'MODIFIER'
        op.modifier_type = 'RAMP'

        icon = 'RADIOBUT_ON' if mask.type == 'MODIFIER' and mask.modifier_type == 'CURVE' else 'RADIOBUT_OFF'
        op = col.operator("wm.y_replace_mask_type", icon=icon, text='Curve Modifier')
        op.type = 'MODIFIER'
        op.modifier_type = 'CURVE'

class YLayerSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_special_menu"
    bl_label = "Layer Special Menu"
    bl_description = 'Layer Special Menu'

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return get_active_ypaint_node()

    def draw(self, context):
        yp = context.parent.id_data.yp
        ypui = context.window_manager.ypui
        ypup = get_user_preferences()

        row = self.layout.row()

        if not hasattr(context, 'parent'):
            col = row.column()
            col.label(text='ERROR: Context has no parent!', icon='ERROR')
            return

        if context.parent.type not in {'GROUP'}:
            col = row.column()
            col.label(text='Add Modifier')
            ## List the modifiers
            for mt in modifier_common.modifier_type_items:
                # Override color modifier is deprecated
                if mt[0] == 'OVERRIDE_COLOR': continue
                if mt[0] == 'MULTIPLIER': continue
                col.operator('wm.y_new_ypaint_modifier', text=mt[1], icon_value=lib.get_icon('modifier')).type = mt[0]

        if ypup.developer_mode:
            col = row.column()
            col.label(text='Advanced')

            col.context_pointer_set('entity', context.parent)
            col.context_pointer_set('layer', context.parent)
            col.operator('wm.y_bake_entity_to_image', icon_value=lib.get_icon('bake'), text='Bake Layer as Image')

        #col = row.column()
        #col.label(text='Options:')
        #col.prop(ypui, 'disable_auto_temp_uv_update')
        #col.prop(yp, 'disable_quick_toggle')

def update_modifier_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp

    match1 = re.match(r'ypui\.layer_ui\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'ypui\.layer_ui\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'ypui\.channel_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match4 = re.match(r'ypui\.layer_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match5 = re.match(r'ypui\.layer_ui\.masks\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        mod = yp.layers[yp.active_layer_index].channels[int(match1.group(1))].modifiers[int(match1.group(2))]
    elif match2:
        mod = yp.layers[yp.active_layer_index].channels[int(match2.group(1))].modifiers_1[int(match2.group(2))]
    elif match3:
        mod = yp.channels[yp.active_channel_index].modifiers[int(match3.group(1))]
    elif match4:
        mod = yp.layers[yp.active_layer_index].modifiers[int(match4.group(1))]
    elif match5:
        mod = yp.layers[yp.active_layer_index].masks[int(match5.group(1))].modifiers[int(match5.group(2))]
    #else: return #yolo

    mod.expand_content = self.expand_content

def update_layer_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp
    if len(yp.layers) == 0: return

    layer = yp.layers[yp.active_layer_index]
    layer.expand_content = self.expand_content
    layer.expand_vector = self.expand_vector
    layer.expand_masks = self.expand_masks
    layer.expand_source = self.expand_source
    layer.expand_channels = self.expand_channels

#def update_layer_ui_item(self, context):
#    ypui = context.window_manager.ypui
#    if ypui.halt_prop_update: return
#
#    group_node =  get_active_ypaint_node()
#    if not group_node: return
#    yp = group_node.node_tree.yp
#    if len(yp.layers) == 0: return
#
#    match = re.match(r'ypui\.layer_items\[(\d+)\]', self.path_from_id())
#    if match:
#        layer = yp.layers[int(match.group(1))]
#        layer.expand_subitems = self.expand_subitems
#
#        ListItem.refresh_list_items(yp)

def update_noncontextual_channel_ui(self, context):
    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp
    if len(yp.channels) == 0: return

    m = re.match(r'ypui\.channels\[(\d+)\]', self.path_from_id())

    if m: ch = yp.channels[int(m.group(1))]
    else: return

    if hasattr(ch, 'expand_baked_data'):
        ch.expand_baked_data = self.expand_baked_data

def update_channel_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp
    if len(yp.channels) == 0: return

    match1 = re.match(r'ypui\.layer_ui\.channels\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'ypui\.channel_ui', self.path_from_id())

    if match1:
        ch = yp.layers[yp.active_layer_index].channels[int(match1.group(1))]
    elif match2:
        ch = yp.channels[yp.active_channel_index]
    #else: return #yolo

    ch.expand_content = self.expand_content
    if hasattr(ch, 'expand_bump_settings'):
        ch.expand_bump_settings = self.expand_bump_settings
    if hasattr(ch, 'expand_base_vector'):
        ch.expand_base_vector = self.expand_base_vector
    if hasattr(ch, 'expand_subdiv_settings'):
        ch.expand_subdiv_settings = self.expand_subdiv_settings
    if hasattr(ch, 'expand_parallax_settings'):
        ch.expand_parallax_settings = self.expand_parallax_settings
    if hasattr(ch, 'expand_alpha_settings'):
        ch.expand_alpha_settings = self.expand_alpha_settings
    if hasattr(ch, 'expand_bake_to_vcol_settings'):
        ch.expand_bake_to_vcol_settings = self.expand_bake_to_vcol_settings
    if hasattr(ch, 'expand_input_bump_settings'):
        ch.expand_input_bump_settings = self.expand_input_bump_settings
    if hasattr(ch, 'expand_smooth_bump_settings'):
        ch.expand_smooth_bump_settings = self.expand_smooth_bump_settings
    if hasattr(ch, 'expand_intensity_settings'):
        ch.expand_intensity_settings = self.expand_intensity_settings
    if hasattr(ch, 'expand_transition_bump_settings'):
        ch.expand_transition_bump_settings = self.expand_transition_bump_settings
    if hasattr(ch, 'expand_transition_ramp_settings'):
        ch.expand_transition_ramp_settings = self.expand_transition_ramp_settings
    if hasattr(ch, 'expand_transition_ao_settings'):
        ch.expand_transition_ao_settings = self.expand_transition_ao_settings
    if hasattr(ch, 'expand_input_settings'):
        ch.expand_input_settings = self.expand_input_settings
    if hasattr(ch, 'expand_blend_settings'):
        ch.expand_blend_settings = self.expand_blend_settings
    if hasattr(ch, 'expand_source'):
        ch.expand_source = self.expand_source
    if hasattr(ch, 'expand_source_1'):
        ch.expand_source_1 = self.expand_source_1

def update_mask_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp
    #if len(yp.channels) == 0: return

    match = re.match(r'ypui\.layer_ui\.masks\[(\d+)\]', self.path_from_id())
    mask = yp.layers[yp.active_layer_index].masks[int(match.group(1))]

    mask.expand_content = self.expand_content
    mask.expand_channels = self.expand_channels
    mask.expand_source = self.expand_source
    mask.expand_vector = self.expand_vector

def update_bake_target_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp

    try: bt = yp.bake_targets[yp.active_bake_target_index]
    except: return

    bt.expand_content = self.expand_content
    bt.expand_r = self.expand_r
    bt.expand_g = self.expand_g
    bt.expand_b = self.expand_b
    bt.expand_a = self.expand_a
    bt.expand_bake_settings = self.expand_bake_settings

def update_mask_channel_ui(self, context):
    ypui = context.window_manager.ypui
    if ypui.halt_prop_update: return

    group_node =  get_active_ypaint_node()
    if not group_node: return
    yp = group_node.node_tree.yp
    #if len(yp.channels) == 0: return

    match = re.match(r'ypui\.layer_ui\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    mask = yp.layers[yp.active_layer_index].masks[int(match.group(1))]
    mask_ch = mask.channels[int(match.group(2))]

    mask_ch.expand_content = self.expand_content

def update_ui_use_cache(self, context):
    #print(get_addon_title(), 'UI Use Cache:', self.use_cache)
    pass

class YBakeTargetUI(bpy.types.PropertyGroup):
    expand_content : BoolProperty(
        name = 'Bake Target Options',
        description = 'Expand bake target options',
        default = True,
        update = update_bake_target_ui
    )

    expand_r : BoolProperty(
        name = 'R Channel',
        description = 'Expand bake target R channel options',
        default = False,
        update = update_bake_target_ui
    )

    expand_g : BoolProperty(
        name = 'G Channel',
        description = 'Expand bake target R channel options',
        default = False,
        update = update_bake_target_ui
    )

    expand_b : BoolProperty(
        name = 'B Channel',
        description = 'Expand bake target B channel options',
        default = False,
        update = update_bake_target_ui
    )

    expand_a : BoolProperty(
        name = 'A Channel',
        description = 'Expand bake target A channel options',
        default = False,
        update = update_bake_target_ui
    )

    expand_bake_settings : BoolProperty(
        name = 'Bake Settings',
        description = 'Expand bake target settings',
        default=False,
        update = update_bake_target_ui
    )

class YModifierUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(default=True, update=update_modifier_ui)

class YChannelUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(
        name = 'Channel Options',
        description = 'Expand channel options',
        default = False,
        update = update_channel_ui
    )

    expand_bump_settings : BoolProperty(
        name = 'Bump',
        description = 'Expand bump settings',
        default = False,
        update = update_channel_ui
    )

    expand_intensity_settings : BoolProperty(
        name = 'Intensity',
        description = 'Expand intensity settings',
        default = False,
        update = update_channel_ui
    )

    expand_base_vector : BoolProperty(
        name = 'Base Vector',
        description = 'Expand base vector options',
        default = True,
        update = update_channel_ui
    )

    expand_transition_bump_settings : BoolProperty(
        name = 'Transition Bump',
        description = 'Expand transition bump settings',
        default = True,
        update = update_channel_ui
    )

    expand_transition_ramp_settings : BoolProperty(
        name = 'Transition Ramp',
        description = 'Expand transition ramp settings',
        default = True, update = update_channel_ui
    )

    expand_transition_ao_settings : BoolProperty(
        name = 'Transition AO',
        description = 'Expand transition AO settings',
        default = True,
        update = update_channel_ui
    )

    expand_subdiv_settings : BoolProperty(
        name = 'Displacement Subdivision',
        description = 'Expand displacement subdivision settings',
        default = False,
        update = update_channel_ui
    )

    expand_parallax_settings : BoolProperty(
        name = 'Parallax',
        description = 'Expand parallax settings',
        default = False,
        update = update_channel_ui
    )

    expand_alpha_settings : BoolProperty(
        name = 'Channel Alpha',
        description = 'Expand alpha settings',
        default = False,
        update = update_channel_ui
    )

    expand_bake_to_vcol_settings : BoolProperty(
        name = 'Bake to '+get_vertex_color_label(),
        description = 'Expand bake to '+get_vertex_color_label(00)+' settings',
        default = False,
        update = update_channel_ui
    )

    expand_input_bump_settings : BoolProperty(
        name = 'Input Bump',
        description = 'Expand input bump settings',
        default = False,
        update = update_channel_ui
    )

    expand_smooth_bump_settings : BoolProperty(
        name = 'Smooth Bump',
        description = 'Expand smooth bump settings',
        default = False,
        update = update_channel_ui
    )

    expand_input_settings : BoolProperty(
        name = 'Input',
        description = 'Expand input settings',
        default = True,
        update = update_channel_ui
    )

    expand_blend_settings : BoolProperty(
            name='Blend',
            description='Expand blend settings',
            default=False, update=update_channel_ui)

    expand_source : BoolProperty(
        name = 'Channel Source',
        description = 'Expand channel source settings',
        default = True,
        update = update_channel_ui
    )

    expand_source_1 : BoolProperty(
        name = 'Channel Normal Source',
        description = 'Expand channel normal source settings',
        default = True,
        update = update_channel_ui
    )

    expand_baked_data : BoolProperty(
        name = 'Baked Channel Data',
        description = 'Expand baked channel data',
        default = False,
        update = update_noncontextual_channel_ui
    )

    modifiers : CollectionProperty(type=YModifierUI)
    modifiers_1 : CollectionProperty(type=YModifierUI)

class YMaskChannelUI(bpy.types.PropertyGroup):
    expand_content : BoolProperty(
        name = 'Mask Channel Options',
        description = 'Expand mask channel options',
        default = False,
        update = update_mask_channel_ui
    )

class YMaskUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(
        name = 'Mask Options',
        description = 'Expand mask options',
        default = True,
        update = update_mask_ui
    )

    expand_channels : BoolProperty(
        name = 'Mask Channel',
        description = 'Expand mask channels',
        default = True,
        update = update_mask_ui
    )

    expand_source : BoolProperty(
        name = 'Mask Source',
        description = 'Expand mask source options',
        default = True,
        update = update_mask_ui
    )

    expand_vector : BoolProperty(
        name = 'Mask Vector',
        description = 'Expand mask vector options',
        default = True,
        update = update_mask_ui
    )

    channels : CollectionProperty(type=YMaskChannelUI)
    modifiers : CollectionProperty(type=YModifierUI)

class YLayerUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')

    expand_content : BoolProperty(
        name = 'Layer Options',
        description = 'Expand layer options',
        default = False,
        update = update_layer_ui
    )

    expand_vector : BoolProperty(
        name = 'Layer Vector',
        description = 'Expand layer vector options',
        default = False,
        update = update_layer_ui
    )

    expand_masks : BoolProperty(
        name = 'Masks',
        description = 'Expand all masks',
        default = False,
        update = update_layer_ui
    )

    expand_source : BoolProperty(
        name = 'Layer Source',
        description = 'Expand layer source options',
        default = False,
        update = update_layer_ui
    )

    expand_channels : BoolProperty(
        name = 'Layer Channels',
        description = 'Expand layer channels',
        default = True,
        update = update_layer_ui
    )

    channels : CollectionProperty(type=YChannelUI)
    masks : CollectionProperty(type=YMaskUI)
    modifiers : CollectionProperty(type=YModifierUI)

#def update_mat_active_yp_node(self, context):
#    print('Update:', self.active_ypaint_node)

class YMaterialUI(bpy.types.PropertyGroup):
    name : StringProperty(default='')
    active_ypaint_node : StringProperty(default='') #, update=update_mat_active_yp_node)

    expand_content : BoolProperty(default=False)

if is_bl_newer_than(2, 83):
    tab_items = (
       ('LAYERS', 'Layers', 'Layers', 'COLLAPSEMENU', 0),
       ('CHANNELS', 'Channels', 'Channel Settings', 'OUTLINER_OB_POINTCLOUD', 1),
       ('BAKE_TARGETS', 'Bake Targets', 'Bake Target Settings', 'OUTPUT', 2),
    )

    setting_items = (
       ('CHANNELS', 'Channels', 'Channel Settings', 'OUTLINER_OB_POINTCLOUD', 0),
       ('BAKE_TARGETS', 'Bake Targets', 'Bake Target Settings', 'OUTPUT', 1),
    )
else:
    tab_items = (
       ('LAYERS', 'Layers', 'Layers'),
       ('CHANNELS', 'Channels', 'Channel Settings'),
       ('BAKE_TARGETS', 'Bake Targets', 'Bake Target Settings'),
    )

    setting_items = (
       ('CHANNELS', 'Channels', 'Channel Settings'),
       ('BAKE_TARGETS', 'Bake Targets', 'Bake Target Settings'),
    )

class YPaintUI(bpy.types.PropertyGroup):

    show_object : BoolProperty(
        name = 'Active Object',
        description = 'Show active object options',
        default = False
    )

    show_materials : BoolProperty(
        name = 'Materials',
        description = 'Show material lists',
        default = False
    )

    show_channels : BoolProperty(
        name = 'Channels',
        description = 'Show channel lists',
        default = False
    )

    show_bake_targets : BoolProperty(
        name = 'Custom Bake Targets',
        description = 'Show custom bake target lists',
        default = False
    )

    show_stats : BoolProperty(
        name = 'Stats',
        description = 'Show node stats',
        default = False
    )

    show_test : BoolProperty(
        name = 'Tests',
        description = 'Show test sections',
        default = False
    )

    show_support : BoolProperty(
        name = 'Support',
        description = 'Show support',
        default = False
    )

    expand_channels : BoolProperty(
        name = 'Show Channel Toggle',
        description = "Show layer channels toggle",
        default = False
    )

    expand_mask_channels : BoolProperty(
        name = 'Expand all mask channels',
        description = 'Expand all mask channels',
        default = False
    )

    expand_channel_base_values : BoolProperty(
        name = 'Expand channel base values',
        description = 'Expand channel base values',
        default = True
    )

    expand_channel_settings : BoolProperty(
        name = 'Expand Channel Settings',
        description = 'Expand channel settings',
        default = True
    )

    expand_channel_bake_target_settings : BoolProperty(
        name = 'Expand Channel Bake Target Settings',
        description = 'Expand channel bake target settings',
        default = False
    )

    # To store active node and tree
    tree_name : StringProperty(default='')
    
    # Layer related UI
    layer_idx : IntProperty(default=0)
    layer_ui : PointerProperty(type=YLayerUI)

    #disable_auto_temp_uv_update : BoolProperty(
    #        name = 'Disable Transformed UV Auto Update',
    #        description = "UV won't be created automatically if layer with custom offset/rotation/scale is selected.\n(This can make selecting layer faster)",
    #        default=False)

    #mask_ui : PointerProperty(type=YMaskUI)

    # Group channel related UI
    channel_idx : IntProperty(default=0)
    channel_ui : PointerProperty(type=YChannelUI)
    channels : CollectionProperty(type=YChannelUI)
    modifiers : CollectionProperty(type=YModifierUI)

    # Bake target related UI
    bake_target_idx : IntProperty(default=0)
    bake_target_ui : PointerProperty(type=YBakeTargetUI)

    # Update related
    need_update : BoolProperty(default=False)
    halt_prop_update : BoolProperty(default=False)

    # Duplicated layer related
    #make_image_single_user : BoolProperty(
    #        name = 'Make Images Single User',
    #        description = 'Make duplicated image layers single user',
    #        default=True)

    # HACK: For some reason active float image will glitch after auto save
    # This prop will notify if float image is active after saving
    refresh_image_hack : BoolProperty(default=False)

    materials : CollectionProperty(type=YMaterialUI)
    #active_obj : StringProperty(default='')
    active_mat : StringProperty(default='')
    active_ypaint_node : StringProperty(default='')

    hide_update : BoolProperty(default=False)
    #random_prop : BoolProperty(default=False)

    # Cache timer
    use_cache : BoolProperty(default=False, update=update_ui_use_cache)
    hit_node_slider_timestamp : StringProperty(default='0.0')

    # Cache variables
    cache_linear_problem : BoolProperty(default=False)
    cache_ao_problem : BoolProperty(default=False)
    cache_missing_data : BoolProperty(default=False)
    cache_missing_combine_bundle : BoolProperty(default=False)

    any_expandable_layers : BoolProperty(default=False)

    extension_update_state : EnumProperty(
        name = 'Update State',
        description = 'Extension update state',
        items = (
            ('UNAVAILABLE', 'Unavailable', ''),
            ('AVAILABLE', 'Available', ''),
            ('PENDING', 'Pending', '')
        ),
        default = 'UNAVAILABLE'
    )

    latest_version : StringProperty(
        default= ''
    )

    expanded_about_ui_VIEW_3D : BoolProperty(default=False)
    expanded_about_ui_NODE_EDITOR : BoolProperty(default=False)
    expanded_main_ui : BoolProperty(default=True)
    expanded_settings_ui : BoolProperty(default=False)

def add_new_ypaint_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine not in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}: return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('wm.y_add_new_ypaint_node', text=get_addon_title(), icon_value=lib.get_icon('nodetree'))

def copy_ui_settings(source, dest):
    for attr in dir(source):
        if attr.startswith(('show_', 'expand_')) or attr.endswith('_name'):
            try: setattr(dest, attr, getattr(source, attr))
            except Exception as e: 
                print('EXCEPTIION: Cannot set UI settings!')

def save_mat_ui_settings():
    ypui = bpy.context.window_manager.ypui
    for mui in ypui.materials:
        mat = bpy.data.materials.get(mui.name)
        if mat: 
            try: mat.yp.active_ypaint_node = mui.active_ypaint_node
            except Exception as e: print(e)
            try: mat.yp.expand_content = mui.expand_content
            except Exception as e: print(e)

def load_mat_ui_settings():
    ypui = bpy.context.window_manager.ypui
    for mat in bpy.data.materials:
        mui = get_material_ui(mat)
        if mat.yp.active_ypaint_node != '':
            mui.active_ypaint_node = mat.yp.active_ypaint_node
        mui.expand_content = mat.yp.expand_content

ui_bus_owner = object()

def get_node_slider_delta_ms():
    ypui = bpy.context.window_manager.ypui
    return (time.time() - float(ypui.hit_node_slider_timestamp)) * 1000

def node_slider_callback(*args):
    ypui = bpy.context.window_manager.ypui
    ypui.hit_node_slider_timestamp = str(time.time())
    # Enable the UI cache to improve performace until the time limit
    if not ypui.use_cache:
        ypui.use_cache = True

@persistent
def yp_load_ui_msgbus_subscription(dummy):
    # Clear owner first
    bpy.msgbus.clear_by_owner(ui_bus_owner) 

    # Subscribe to all socket types
    keys = (
        (bpy.types.NodeSocketFloat, "default_value"),
        (bpy.types.NodeSocketFloatFactor, "default_value"),
        (bpy.types.NodeSocketColor, "default_value"),
    )

    # Subscribe to node slider update
    for key in keys:
        bpy.msgbus.subscribe_rna(key=key, owner=ui_bus_owner, args=(), notify=node_slider_callback)                
    
@persistent
def yp_save_ui_settings(scene):
    save_mat_ui_settings()
    wmui = bpy.context.window_manager.ypui
    scui = bpy.context.scene.ypui
    copy_ui_settings(wmui, scui)

@persistent
def yp_load_ui_settings(scene):
    load_mat_ui_settings()
    wmui = bpy.context.window_manager.ypui
    scui = bpy.context.scene.ypui
    copy_ui_settings(scui, wmui)

    # Update UI
    wmui.need_update = True

def get_new_extension_version_available():
    addon_id = 'ucupaint'
    from bl_pkg import bl_extension_ops as ext_op
    from bl_pkg import bl_extension_utils

    repos_all = ext_op.extension_repos_read(use_active_only=True)
    repo_cache_store = ext_op.repo_cache_store_ensure()

    repo_directory_supset = [repo_entry.directory for repo_entry in repos_all]

    if not repos_all:
        return None

    for repo_item in repos_all:
        if repo_item.use_cache:
            continue
        bl_extension_utils.pkg_repo_cache_clear(repo_item.directory)

    pkg_manifest_local_all = list(repo_cache_store.pkg_manifest_from_local_ensure(
        error_fn=None,
        directory_subset=repo_directory_supset,
    ))

    for repo_index, pkg_manifest_remote in enumerate(repo_cache_store.pkg_manifest_from_remote_ensure(
        error_fn=None,
        directory_subset=repo_directory_supset,
    )):
        if pkg_manifest_remote is None:
            continue

        pkg_manifest_local = pkg_manifest_local_all[repo_index]
        if pkg_manifest_local is None:
            continue

        repo_item = repos_all[repo_index]
        for pkg_id, item_remote in pkg_manifest_remote.items():
            item_local = pkg_manifest_local.get(pkg_id)
            if item_local is None:
                # Not installed.
                continue
            if item_remote.block:
                # Blocked, don't touch.
                continue

            if pkg_id == addon_id and item_remote.version != item_local.version:
                # print("available=", item_remote.version)
                return item_remote.version
            
    return None

def check_latest_extension_version():
    # Only for extension platform installation
    if not is_online() or not is_installed_through_extension_platform(): return
    ypui = bpy.context.window_manager.ypui

    try: new_ver = get_new_extension_version_available()
    except Exception as e:
        new_ver = None
        print(get_addon_title()+" (Error extension version getter):",e)

    if new_ver:
        ypui.extension_update_state = 'AVAILABLE'
        ypui.latest_version = new_ver
    else:
        ypui.extension_update_state = 'UNAVAILABLE'

class YPendingUpdate(bpy.types.Operator):
    bl_idname = "ext.y_pending_update"
    bl_label = "Pending Update"
    bl_description = "Pending update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ypui = bpy.context.window_manager.ypui
        ypui.extension_update_state = 'PENDING'

        return {'FINISHED'}

classes = []
if not is_bl_newer_than(2, 80):
    classes.extend([
        YPaintAboutMenu,
        YListItemOptionMenu,
    ])
else: 
    classes.extend([
        YPaintAboutPopover,
        YListItemOptionPopover,

        YPaintBakeTargetPopover,
        YPaintBakeTargetAltPopover,
        YPaintChannelPopover,
        YPaintPreviewModeSettingsPopover,
        YPaintPreviewModeChannelSettingsPopover,
    ])
classes.extend([
    YPaintSpecialMenu,
    YChannelSpecialTypeMenu,
    YChannelActiveBakeTargetMenu,
    YNewChannelMenu,
    YNewImageLayerMenu,
    YNewVcolLayerMenu,
    YNewColorLayerMenu,
    YNewTextureLayerMenu,
    YNewInputLayerMenu,
    YNewGeneratedLayerMenu,
    YNewAdjustmentLayerMenu,
    YNewBakeAsLayerMenu,
    YBakeTargetMenu,
    YBakeListSpecialMenu,
    YBakedImageMenu,
    YLayerListSpecialMenu,
    YLayerChannelBlendMenu,
    YLayerChannelNormalBlendMenu,
    YLayerChannelInputMenu,
    YLayerChannelInput1Menu,
    YLayerMaskInputMenu,
    YImageConvertToMenu,
    YOpenImagesToSingleLayerMenu,
    YUVSpecialMenu,
    YModifierMenu,
    YModifier1Menu,
    YMaskModifierMenu,
    YTransitionBumpMenu,
    YTransitionRampMenu,
    YTransitionAOMenu,
    YAddImageLayerMaskMenu,
    YAddVColLayerMaskMenu,
    YAddAdjustmentLayerMaskMenu,
    YAddTextureLayerMaskMenu,
    YAddGeneratedLayerMaskMenu,
    YAddBakeAsLayerMaskMenu,
    YLayerMaskMenu,
    YMaterialSpecialMenu,
    YChannelSpecialMenu,
    YLayerChannelSpecialMenu,
    YReplaceChannelOverrideMenu,
    YReplaceChannelOverride1Menu,
    YPreviewModeChannelMenu,
    YLayerSpecialMenu,
    YLayerTypeMenu,
    YMaskTypeMenu,
    YModifierUI,
    YBakeTargetUI,
    YChannelUI,
    YMaskChannelUI,
    YMaskUI,
    YLayerUI,
    YMaterialUI,
    NODE_UL_YPaint_bake_targets,
    NODE_UL_YPaint_channels,
    NODE_UL_YPaint_simple_channels,
    NODE_UL_YPaint_layers,
    NODE_UL_YPaint_list_items,
    YPAssetBrowserMenu,
    YPFileBrowserMenu,
    NODE_MT_copy_image_path_menu,
    YPendingUpdate,
    YPaintUI,
])

new_entity_menus = (
    YNewLayerMenu,
    YAddLayerMaskMenu,
)

def register_new_entity_menus():
    ypup = get_user_preferences()

    for menu in new_entity_menus:
        if hasattr(bpy.types, menu.bl_idname):
            bpy.utils.unregister_class(menu)

        if is_bl_newer_than(4):
            # Enable search on keypress if legacy menu is not used
            if not ypup.ui_legacy_add_layer_menu:
                menu.bl_options = {'SEARCH_ON_KEY_PRESS'}
            else: menu.bl_options = set()

        bpy.utils.register_class(menu)

def unregister_new_entity_menus():
    for menu in new_entity_menus: bpy.utils.unregister_class(menu)

panels = [
    VIEW3D_PT_YPaint_about_ui,
    VIEW3D_PT_YPaint_obj_mat_settings_ui,
    VIEW3D_PT_YPaint_main_ui,
    VIEW3D_PT_YPaint_channel_settings_ui,
    VIEW3D_PT_YPaint_bake_target_settings_ui,
    #VIEW3D_PT_YPaint_stats_ui,
    VIEW3D_PT_YPaint_test_ui,
]
if not is_bl_newer_than(2, 80):
    panels.extend([
        NODE_PT_YPaint_legacy_about_ui,
        NODE_PT_YPaint_legacy_main_ui,
        NODE_PT_YPaint_legacy_channel_settings_ui,
        NODE_PT_YPaint_legacy_bake_target_settings_ui,

        VIEW3D_PT_YPaint_legacy_about_tools,
        VIEW3D_PT_YPaint_legacy_obj_mat_settings_tools,
        VIEW3D_PT_YPaint_legacy_main_tools,
        VIEW3D_PT_YPaint_legacy_channel_settings_tools,
        VIEW3D_PT_YPaint_legacy_bake_target_settings_tools,
    ])
else: 
    panels.extend([
        NODE_PT_YPaint_about_ui,
        NODE_PT_YPaint_main_ui,
        NODE_PT_YPaint_channel_settings_ui,
        NODE_PT_YPaint_bake_target_settings_ui,
    ])

def register_panels():
    # Set up icon value and register panels
    icon_value = lib.get_icon('ucupaint')
    for panel in panels:
        if hasattr(bpy.types, panel.__name__):
            bpy.utils.unregister_class(panel)
        if is_bl_newer_than(5, 2):
            panel.bl_icon_value = icon_value
        bpy.utils.register_class(panel)

def unregister_panels():
    for panel in panels: bpy.utils.unregister_class(panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    register_new_entity_menus()
    register_panels()

    bpy.types.Scene.ypui = PointerProperty(type=YPaintUI)
    bpy.types.WindowManager.ypui = PointerProperty(type=YPaintUI)

    # Add yPaint node ui
    bpy.types.NODE_MT_add.append(add_new_ypaint_node_menu)

    if is_bl_newer_than(4):
        bpy.types.ASSETBROWSER_MT_context_menu.append(draw_yp_asset_browser_menu)

    if is_bl_newer_than(2, 81):
        bpy.types.FILEBROWSER_MT_context_menu.append(draw_yp_file_browser_menu)

    # Handlers
    bpy.app.handlers.load_post.append(yp_load_ui_settings)
    bpy.app.handlers.save_pre.append(yp_save_ui_settings)

    check_latest_extension_version()

    if is_bl_newer_than(2, 80):
        # Msgbus Subscription
        yp_load_ui_msgbus_subscription(None)
        bpy.app.handlers.load_post.append(yp_load_ui_msgbus_subscription)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    unregister_new_entity_menus()
    unregister_panels()

    # Remove add yPaint node ui
    bpy.types.NODE_MT_add.remove(add_new_ypaint_node_menu)

    if is_bl_newer_than(4):
        bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_yp_asset_browser_menu)

    if is_bl_newer_than(2, 81):
        bpy.types.FILEBROWSER_MT_context_menu.remove(draw_yp_file_browser_menu)

    # Remove Handlers
    bpy.app.handlers.load_post.remove(yp_load_ui_settings)
    bpy.app.handlers.save_pre.remove(yp_save_ui_settings)

    if is_bl_newer_than(2, 80):
        # Remove msgbus subscription
        bpy.msgbus.clear_by_owner(ui_bus_owner) 
        bpy.app.handlers.load_post.remove(yp_load_ui_msgbus_subscription)
