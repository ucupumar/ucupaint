import bpy, re, time, os
from bpy.props import *
from bpy.app.handlers import persistent
from bpy.app.translations import pgettext_iface
from . import lib, Modifier, MaskModifier, NormalMapModifier, Root, UDIM
from .common import *

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

        if len(yp.bake_targets) > 0:
            bt = yp.bake_targets[yp.active_bake_target_index]
            ypui.bake_target_ui.expand_content = bt.expand_content
            ypui.bake_target_ui.expand_r = bt.expand_r
            ypui.bake_target_ui.expand_g = bt.expand_g
            ypui.bake_target_ui.expand_b = bt.expand_b
            ypui.bake_target_ui.expand_a = bt.expand_a

        if len(yp.channels) > 0:

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

            # Construct channel UI objects
            for i, mod in enumerate(channel.modifiers):
                m = ypui.channel_ui.modifiers.add()
                m.expand_content = mod.expand_content

        if len(yp.layers) > 0:

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

def draw_bake_info(bake_info, layout, entity):

    yp = entity.id_data.yp
    bi = bake_info

    if len(bi.other_objects) > 0:
        layout.label(text='List of Objects:')
        box = layout.box()
        bcol = box.column()
        for oo in bi.other_objects:
            brow = bcol.row()
            brow.context_pointer_set('other_object', oo)
            brow.context_pointer_set('bake_info', bi)
            if is_bl_newer_than(2, 79):
                brow.label(text=oo.object.name, icon_value=lib.get_icon('object_index'))
            else: brow.label(text=oo.object_name, icon_value=lib.get_icon('object_index'))
            brow.operator('node.y_remove_bake_info_other_object', text='', icon_value=lib.get_icon('close'))

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m3:
        layer = yp.layers[int(m3.group(1))]
        layout.context_pointer_set('entity', layer)
    else: layout.context_pointer_set('entity', entity)

    layout.context_pointer_set('bake_info', bi)
    if bi.bake_type == 'SELECTED_VERTICES':
        c = layout.operator("node.y_try_to_select_baked_vertex", text='Try to Reselect Vertices', icon='GROUP_VERTEX')
    c = layout.operator("node.y_bake_to_layer", text='Rebake', icon_value=lib.get_icon('bake'))
    c.type = bi.bake_type
    if m1 or m3: c.target_type = 'LAYER'
    else: c.target_type = 'MASK'
    c.overwrite_current = True

def draw_image_props(context, source, layout, entity=None, show_flip_y=False):

    image = source.image

    col = layout.column()

    unlink_op = 'node.y_remove_layer'
    if entity:
        yp = entity.id_data.yp
        m1 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())
        if m1: 
            layer = yp.layers[int(m1.group(1))]
            col.context_pointer_set('layer', layer)
            col.context_pointer_set('mask', entity)
            unlink_op = 'node.y_remove_layer_mask'
        elif m2: 
            layer = yp.layers[int(m2.group(1))]
            col.context_pointer_set('layer', layer)
            col.context_pointer_set('channel', entity)
            if show_flip_y:
                unlink_op = 'node.y_remove_channel_override_1_source'
            else: unlink_op = 'node.y_remove_channel_override_source'

    if image.y_bake_info.is_baked and not image.y_bake_info.is_baked_channel:
        bi = image.y_bake_info
        if image.yia.is_image_atlas or image.yua.is_udim_atlas:
            col.label(text=image.name + ' (Baked)', icon_value=lib.get_icon('image'))
        else: col.template_ID(source, "image", unlink=unlink_op)
        col.label(text='Type: ' + bake_type_labels[bi.bake_type], icon_value=lib.get_icon('bake'))

        draw_bake_info(bi, col, entity)
        return

    if image.yia.is_image_atlas or image.yua.is_udim_atlas:

        if image.yia.is_image_atlas:
            segment = image.yia.segments.get(entity.segment_name)
        else: segment = image.yua.segments.get(entity.segment_name)

        if segment and segment.bake_info.is_baked:
            bi = segment.bake_info
            col.label(text=image.name + ' (Baked)', icon_value=lib.get_icon('image'))
            col.label(text='Type: ' + bake_type_labels[bi.bake_type], icon_value=lib.get_icon('bake'))
        else: col.label(text=image.name, icon_value=lib.get_icon('image'))
        if segment:
            if image.yia.is_image_atlas:
                row = col.row()
                row.label(text='Tile X: ' + str(segment.tile_x))
                row.label(text='Tile Y: ' + str(segment.tile_y))
                row = col.row()
                row.label(text='Width: ' + str(segment.width))
                row.label(text='Height: ' + str(segment.height))
            else:
                split = split_layout(col, 0.4)
                split.label(text='Tile Numbers: ')
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

    col.template_ID(source, "image", unlink=unlink_op)
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
            col.label(text='Path: ' + image.filepath)

        image_format = 'RGBA'
        image_bit = int(image.depth/4)
        if image.depth in {24, 48, 96}:
            image_format = 'RGB'
            image_bit = int(image.depth/3)

        col.label(text='Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                ' ' + image_format + ' ' + str(image_bit) + '-bit')

    split = split_layout(col, 0.4)

    scol = split.column()
    if not image.is_dirty:
        scol.label(text='Color Space:')
        if hasattr(image, 'use_alpha'):
            scol.label(text='Use Alpha:')
        scol.label(text='Alpha Mode:')

    if entity and hasattr(entity, 'image_flip_y') and show_flip_y:
        scol.label(text='Flip Y:')

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

    if entity and hasattr(entity, 'image_flip_y') and show_flip_y:
        scol.prop(entity, 'image_flip_y', text='')

    scol.prop(source, 'interpolation', text='')

    scol.prop(source, 'extension', text='')
    #scol.prop(source, 'projection', text='')
    #if source.projection == 'BOX':
    #    scol.prop(entity, 'projection_blend', text='')

def draw_object_index_props(entity, layout):
    col = layout.column()
    col.prop(entity, 'object_index')

def draw_hemi_props(entity, source, layout):
    col = layout.column()
    col.prop(entity, 'hemi_space', text='Space')
    col.label(text='Light Direction:')

    # Get light direction
    norm = source.node_tree.nodes.get('Normal')

    col.prop(norm.outputs[0], 'default_value', text='')
    col.prop(entity, 'hemi_use_prev_normal', text='Use Previous Normal')
    col.prop(entity, 'hemi_camera_ray_mask', text='Camera Ray Mask')

def draw_vcol_props(layout, vcol=None, entity=None):
    if hasattr(entity, 'divide_rgb_by_alpha'):
        layout.prop(entity, 'divide_rgb_by_alpha')
    else:
        layout.label(text='You can also edit vertex color in edit mode')

def is_input_skipped(inp):
    if is_bl_newer_than(2, 81):
        return inp.name == 'Vector' or not inp.enabled

    return inp.name == 'Vector'

def draw_tex_props(source, layout, entity=None):

    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(text=title + ' Properties:')
    #col.separator()

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

def draw_colorid_props(layer, source, layout):
    col = layout.column()
    row = col.row()
    row.label(text='Color ID:')
    #row.prop(source.inputs[0], 'default_value', text='')

    #row.prop(layer, 'color_id', text='')
    draw_input_prop(row, layer, 'color_id')
    #row = col.row()
    #row.label(text='Shortcut on list:')
    #row.prop(layer, 'color_shortcut', text='')

def draw_solid_color_props(layer, source, layout):
    col = layout.column()
    #col.label(text='Ewsom')
    row = col.row()
    row.label(text='Color:')
    row.prop(source.outputs[0], 'default_value', text='')
    row = col.row()
    row.label(text='Shortcut on list:')
    row.prop(layer, 'color_shortcut', text='')

def draw_edge_detect_props(layer, source, layout):
    col = layout.column()
    row = col.row()
    row.label(text='Radius:')
    draw_input_prop(row, layer, 'edge_detect_radius')

def draw_inbetween_modifier_mask_props(layer, source, layout):
    col = layout.column()
    if layer.modifier_type == 'CURVE':
        source.draw_buttons_ext(bpy.context, col)
    elif layer.modifier_type == 'RAMP':
        col.template_color_ramp(source, "color_ramp", expand=True)

def draw_input_prop(layout, entity, prop_name, emboss=None, text=''):
    inp = get_entity_prop_input(entity, prop_name)
    if emboss != None:
        if inp: layout.prop(inp, 'default_value', text=text, emboss=emboss)
        else: layout.prop(entity, prop_name, text=text, emboss=emboss)
    else:
        if inp: layout.prop(inp, 'default_value', text=text)
        else: layout.prop(entity, prop_name, text=text) 

def draw_mask_modifier_stack(layer, mask, layout, ui):
    ypui = bpy.context.window_manager.ypui
    tree = get_mask_tree(mask)

    for i, m in enumerate(mask.modifiers):

        try: modui = ui.modifiers[i]
        except: 
            ypui.need_update = True
            return

        can_be_expanded = m.type in MaskModifier.can_be_expanded

        row = layout.row(align=True)

        if can_be_expanded:
            if modui.expand_content:
                icon_value = lib.get_icon('uncollapsed_modifier')
            else: icon_value = lib.get_icon('collapsed_modifier')
            row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.label(text='', icon_value=lib.get_icon('modifier'))

        row.label(text=m.name)

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

def draw_modifier_stack(context, parent, channel_type, layout, ui, layer=None, extra_blank=False, use_modifier_1=False, layout_active=True):

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

        if can_be_expanded:
            if modui.expand_content:
                icon_value = lib.get_icon('uncollapsed_modifier')
            else: icon_value = lib.get_icon('collapsed_modifier')
            row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.label(text='', icon_value=lib.get_icon('modifier'))
        
        label = m.name

        # If parent is layer channel
        if match:
            if root_ch.type == 'NORMAL' and ch.normal_map_type == 'BUMP_NORMAL_MAP':
                if use_modifier_1:
                    label += ' (Normal)'
                else: label += ' (Bump)'

        #if m.type == 'MATH' and not modui.expand_content:
        #    method_name = [mt[1] for mt in math_method_items if mt[0] == m.math_meth][0]
        #    label += ' (' + method_name + ')'

        row.label(text=label)

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
            Modifier.draw_modifier_properties(bpy.context, channel_type, mod_tree.nodes, m, box, False)

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
        if getattr(btui, 'expand_' + letter):
            icon_name = 'uncollapsed_' + icon_name
        else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon(icon_name)
        row.prop(btui, 'expand_' + letter, text='', emboss=False, icon_value=icon_value)
    else:
        row.label(text='', icon_value=lib.get_icon(letter))

    if btc.channel_name == '':
        split = split_layout(row, 0.65, align=True)
        split.prop_search(btc, "channel_name", yp, "channels", text='')
        split.prop(btc, 'default_value', text='')
    else:
        if ch and (ch.type == 'RGB' or (ch.type == 'NORMAL' and btc.normal_type != 'DISPLACEMENT')):
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

        if ch.type == 'NORMAL':
            brow = split_layout(bcol, 0.3, align=True)
            brow.label(text='Source:')
            brow.prop(btc, 'normal_type', text='')

        brow = bcol.row(align=True)
        brow.label(text='Invert Value:')
        brow.prop(btc, 'invert_value', text='')

def draw_bake_targets_ui(context, layout, node):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp

    ypui = context.window_manager.ypui
    btui = ypui.bake_target_ui

    box = layout.box()
    col = box.column()
    row = col.row()

    rcol = row.column()
    rcol.template_list("NODE_UL_YPaint_bake_targets", "", yp,
            "bake_targets", yp, "active_bake_target_index", rows=2, maxrows=5)

    rcol = row.column(align=True)
    #rcol.context_pointer_set('node', node)

    if is_bl_newer_than(2, 80):
        rcol.operator("node.y_new_bake_target", icon='ADD', text='')
        rcol.operator("node.y_remove_bake_target", icon='REMOVE', text='')
    else: 
        rcol.operator("node.y_new_bake_target", icon='ZOOMIN', text='')
        rcol.operator("node.y_remove_bake_target", icon='ZOOMOUT', text='')

    if len(yp.bake_targets) > 0:
        bt = yp.bake_targets[yp.active_bake_target_index]
        image_node = nodes.get(bt.image_node)
        image = image_node.image if image_node and image_node.image else None

        icon_name = 'bake'
        if btui.expand_content:
            icon_name = 'uncollapsed_' + icon_name
        else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon(icon_name)

        row = col.row(align=True)

        row.prop(btui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        if image: 
            bt_label = image.name
            if image.is_float: bt_label += ' (Float)'
        else: 
            bt_label = bt.name
            if bt.use_float: bt_label += ' (Float)'

        row.label(text=bt_label)

        if btui.expand_content:
            row = col.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            for letter in rgba_letters:
                draw_bake_target_channel(context, bcol, bt, letter)

        row = col.row(align=True)
        image_name = image.name if image else '-'

        row.label(text='Image: ' + image_name, icon_value=lib.get_icon('image'))

        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.context_pointer_set('image', image)
        row.menu("NODE_MT_y_bake_target_menu", text='', icon=icon)
        
        if not image:
            row = col.row(align=True)
            row.label(text="Do 'Bake All Channels' to get the image!", icon='ERROR')

def draw_root_channels_ui(context, layout, node):
    scene = bpy.context.scene
    obj = bpy.context.object
    engine = scene.render.engine
    mat = get_active_material()
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    ypup = get_user_preferences()

    box = layout.box()
    col = box.column()
    row = col.row()

    rcol = row.column()
    if len(yp.channels) > 0:
        pcol = rcol.column()
        if yp.preview_mode: pcol.alert = True
        if not is_bl_newer_than(2, 80):
            pcol.prop(yp, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')
        else: pcol.prop(yp, 'preview_mode', text='Preview Mode', icon='HIDE_OFF')

    rcol.template_list("NODE_UL_YPaint_channels", "", yp,
            "channels", yp, "active_channel_index", rows=3, maxrows=5)  

    rcol = row.column(align=True)
    #rcol.context_pointer_set('node', node)

    if is_bl_newer_than(2, 80):
        rcol.menu("NODE_MT_y_new_channel_menu", text='', icon='ADD')
        #rcol.operator_menu_enum("node.y_add_new_ypaint_channel", 'type', icon='ADD', text='')
        rcol.operator("node.y_remove_ypaint_channel", icon='REMOVE', text='')
    else: 
        rcol.menu("NODE_MT_y_new_channel_menu", text='', icon='ZOOMIN')
        #rcol.operator_menu_enum("node.y_add_new_ypaint_channel", 'type', icon='ZOOMIN', text='')
        rcol.operator("node.y_remove_ypaint_channel", icon='ZOOMOUT', text='')

    rcol.operator("node.y_move_ypaint_channel", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("node.y_move_ypaint_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

    if len(yp.channels) > 0:

        mcol = col.column(align=False)

        channel = yp.channels[yp.active_channel_index]
        mcol.context_pointer_set('channel', channel)

        chui = ypui.channel_ui

        # Check if channel output is connected or not
        inputs = node.inputs
        outputs = node.outputs
        output_index = get_output_index(channel)

        if group_tree.users == 1:

            # Optimize normal process button if normal input is disconnected
            root_normal_ch = get_root_height_channel(yp)
            if root_normal_ch:
                if is_height_input_unconnected_but_has_start_process(node, root_normal_ch):
                    row = mcol.row(align=True)
                    row.alert = True
                    row.operator('node.y_optimize_normal_process', icon='ERROR', text='Fix Height Process')
                elif is_height_input_connected_but_has_no_start_process(node, root_normal_ch):
                    row = mcol.row(align=True)
                    row.alert = True
                    row.operator('node.y_optimize_normal_process', icon='ERROR', text='Fix Height Input')

            if is_output_unconnected(node, output_index, channel):
                row = mcol.row(align=True)
                row.alert = True
                row.operator('node.y_connect_ypaint_channel', icon='ERROR', text='Fix Unconnected Channel Output')

            # Fix for alpha channel missing connection
            elif channel.type=='RGB' and channel.enable_alpha and is_output_unconnected(node, output_index+1, channel):
                row = mcol.row(align=True)
                row.alert = True
                row.operator('node.y_connect_ypaint_channel_alpha', icon='ERROR', text='Fix Unconnected Alpha Output')

        row = mcol.row(align=True)

        icon_name = lib.channel_custom_icon_dict[channel.type]
        if chui.expand_content:
            icon_name = 'uncollapsed_' + icon_name
        else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon(icon_name)
        row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        #else:
        #    row.prop(chui, 'expand_content', text='', emboss=True, icon=lib.channel_icon_dict[channel.type])

        row.label(text=channel.name + ' ' + pgettext_iface('Channel'))

        #if channel.type != 'NORMAL':
        row.context_pointer_set('parent', channel)
        row.context_pointer_set('channel_ui', chui)
        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.menu("NODE_MT_y_channel_special_menu", icon=icon, text='')

        if chui.expand_content:

            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            # Modifier stack ui will only active when use_baked is off
            baked = nodes.get(channel.baked)
            layout_active = not yp.use_baked or not baked

            draw_modifier_stack(context, channel, channel.type, bcol, chui, layout_active=layout_active)

            inp = node.inputs[channel.io_index]

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)

                brow.label(text='', icon_value=lib.get_icon('input'))

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

            # Alpha settings will only visible on color channel without developer mode
            # Alpha will also not visible if other channel already enable the alpha
            if ((channel.type == 'RGB' and not any([c for c in yp.channels if c.enable_alpha and c != channel]))
                or ypup.developer_mode or channel.enable_alpha):
                brow = bcol.row(align=True)
                #brow.label(text='', icon_value=lib.get_icon('input'))
                if chui.expand_alpha_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                brow.prop(chui, 'expand_alpha_settings', text='', emboss=False, icon_value=icon_value)
                if channel.enable_alpha:
                    inp_alpha = node.inputs[channel.io_index+1]
                    brow.label(text='Base Alpha:')
                    if len(node.inputs[channel.io_index+1].links)==0:
                        if not yp.use_baked:
                            brow.prop(inp_alpha, 'default_value', text='')
                    else: brow.label(text='', icon='LINKED')
                else: brow.label(text='Alpha:')
                if not yp.use_baked:
                    brow.prop(channel, 'enable_alpha', text='')
                else:
                    brow.label(text='', icon_value=lib.get_icon('texture'))

                if chui.expand_alpha_settings:
                    brow = bcol.row(align=True)
                    brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)
                    bbcol.active = channel.enable_alpha

                    if is_bl_newer_than(2, 80):

                        if is_bl_newer_than(4, 2) and engine == 'BLENDER_EEVEE_NEXT':
                            brow = bbcol.row(align=True)
                            brow.label(text='Transparent Shadows:')
                            brow.prop(mat, 'use_transparent_shadow', text='')
                            brow = bbcol.row(align=True)
                            brow.label(text='Jittered Shadows (Global):')
                            brow.prop(scene.eevee, 'use_shadow_jitter_viewport', text='')
                            brow = bbcol.row(align=True)
                            brow.label(text='Render Method:')
                            brow.prop(mat, 'surface_render_method', text='')
                        elif engine != 'HYDRA_STORM':
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

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.active = not yp.use_baked or channel.no_layer_using
                brow.label(text='', icon_value=lib.get_icon('input'))
                brow.label(text='Use Clamp:')
                brow.prop(channel, 'use_clamp', text='')

            #if len(channel.modifiers) > 0:
            #    brow.label(text='', icon='BLANK1')

            if channel.type == 'NORMAL':
                brow = bcol.row(align=True)
                #if channel.enable_smooth_bump:
                if chui.expand_smooth_bump_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                brow.prop(chui, 'expand_smooth_bump_settings', text='', emboss=False, icon_value=icon_value)
                #else:
                #    brow.label(text='', icon_value=lib.get_icon('input'))
                if is_bl_newer_than(2, 80):
                    brow.label(text='Smoother Bump:')
                else: brow.label(text='Smooth Bump:')

                if not yp.use_baked:
                    brow.prop(channel, 'enable_smooth_bump', text='')
                else:
                    brow.label(text='', icon_value=lib.get_icon('texture'))

                if chui.expand_smooth_bump_settings: # and channel.enable_smooth_bump:
                    brow = bcol.row(align=True)
                    brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)

                    if channel.enable_smooth_bump:
                        brow = bbcol.row(align=True)
                        brow.label(text='Main UV:')
                        #brow.label(text=channel.main_uv)
                        #brow.prop(channel, 'main_uv', text='')
                        brow.prop_search(channel, "main_uv", context.object.data, "uv_layers", text='', icon='GROUP_UVS')

                    brow = bbcol.row(align=True)
                    brow.label(text='Backface Normal Up:')
                    brow.prop(yp, 'enable_backface_always_up', text='')

                if channel.enable_smooth_bump:
                    brow = bcol.row(align=True)
                    brow.label(text='', icon_value=lib.get_icon('input'))
                    brow.label(text='Normal Tweak:')

                    if not yp.use_baked:
                        if channel.enable_smooth_normal_tweak:
                            end_linear = nodes.get(channel.end_linear)
                            if end_linear:
                                brow.prop(end_linear.inputs['Normal Tweak'], 'default_value', text='')
                            else: brow.prop(channel, 'smooth_normal_tweak', text='')

                        brow.prop(channel, 'enable_smooth_normal_tweak', text='')
                    else:
                        brow.label(text='', icon_value=lib.get_icon('texture'))

                brow = bcol.row(align=True)

                brow.label(text='', icon_value=lib.get_icon('input'))
                brow.label(text='Height Tweak:')

                if not yp.use_baked:
                    if channel.enable_height_tweak:
                        end_max_height_tweak = nodes.get(channel.end_max_height_tweak)
                        if end_max_height_tweak:
                            brow.prop(end_max_height_tweak.inputs['Height Tweak'], 'default_value', text='')
                        else: brow.prop(channel, 'height_tweak', text='')

                    brow.prop(channel, 'enable_height_tweak', text='')
                else:
                    brow.label(text='', icon_value=lib.get_icon('texture'))

                # Put parallax settings to experimental since it's very imprescise
                if ypup.show_experimental or channel.enable_parallax:
                    brow = bcol.row(align=True)
                    brow.active = yp.use_baked and not channel.enable_subdiv_setup and not yp.enable_baked_outside

                    if chui.expand_parallax_settings:
                        icon_value = lib.get_icon('uncollapsed_input')
                    else: icon_value = lib.get_icon('collapsed_input')
                    brow.prop(chui, 'expand_parallax_settings', text='', emboss=False, icon_value=icon_value)

                    brow.label(text='Parallax:')
                    if not chui.expand_parallax_settings and channel.enable_parallax:
                        brow.prop(channel, 'baked_parallax_num_of_layers', text='')
                    brow.prop(channel, 'enable_parallax', text='')

                    if chui.expand_parallax_settings:

                        brow = bcol.row(align=True)
                        brow.label(text='', icon='BLANK1')
                        bbox = brow.box()
                        bbcol = bbox.column() #align=True)
                        bbcol.active = is_parallax_enabled(channel) and (
                                not yp.use_baked or not channel.enable_subdiv_setup or channel.subdiv_adaptive)

                        brow = bbcol.row(align=True)
                        brow.label(text='Steps:')
                        brow.prop(channel, 'baked_parallax_num_of_layers', text='')

                        brow = bbcol.row(align=True)
                        #brow.label(text='', icon_value=lib.get_icon('input'))
                        brow.label(text='Rim Hack:')
                        if channel.parallax_rim_hack:
                            brow.prop(channel, 'parallax_rim_hack_hardness', text='')
                        brow.prop(channel, 'parallax_rim_hack', text='')

                        brow = bbcol.row(align=True)
                        brow.label(text='Height Tweak:')
                        brow.prop(channel, 'parallax_height_tweak', text='')

                        brow = bbcol.row(align=True)
                        brow.label(text='Main UV: ' + channel.main_uv)

                brow = bcol.row(align=True)

                if chui.expand_subdiv_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                brow.prop(chui, 'expand_subdiv_settings', text='', emboss=False, icon_value=icon_value)

                brow.label(text='Displacement Setup:')
                brow.prop(channel, 'enable_subdiv_setup', text='')

                if chui.expand_subdiv_settings:

                    brow = bcol.row(align=True)
                    brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)
                    bbcol.active = channel.enable_subdiv_setup

                    height_input = node.inputs.get(channel.name + io_suffix['HEIGHT'])
                    if height_input and len(height_input.links)>0:

                        brow = bbcol.row(align=True)
                        brow.label(text='Input Max Height:')
                        brow.prop(node.inputs[channel.io_index+2], 'default_value', text='')

                        brow = bbcol.row(align=True)
                        brow.label(text='Input Bump Midlevel:')

                        start_bump_process = nodes.get(channel.start_bump_process)
                        if start_bump_process and 'Midlevel' in start_bump_process.inputs:
                            brow.prop(start_bump_process.inputs['Midlevel'], 'default_value', text='')

                    brow = bbcol.row(align=True)
                    brow.label(text='Max Polygons:')
                    brow.prop(channel, 'subdiv_on_max_polys', text='')

                    if is_bl_newer_than(2, 78):
                        brow = bbcol.row(align=True)
                        brow.label(text='Adaptive (Cycles Only):')
                        brow.prop(channel, 'subdiv_adaptive', text='')

                        if channel.subdiv_adaptive:
                            brow = bbcol.row(align=True)
                            brow.label(text='Global Dicing:')
                            brow.prop(channel, 'subdiv_global_dicing', text='')

                    # Only show subsurf only option when object has multires
                    multires = get_multires_modifier(obj, include_hidden=True)
                    if multires or channel.subdiv_subsurf_only:
                        brow = bbcol.row(align=True)
                        brow.active = not channel.subdiv_adaptive
                        brow.label(text='Subsurf Only:')
                        brow.prop(channel, 'subdiv_subsurf_only', text='')

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.label(text='', icon_value=lib.get_icon('input'))

                split = split_layout(brow, 0.375, align=True)

                split.label(text='Space:')
                split.prop(channel, 'colorspace', text='')

                # Bake to vertex color settings
                if is_bl_newer_than(2, 92):
                    brow = bcol.row(align=True)
                    if chui.expand_bake_to_vcol_settings:
                        ch_icon = lib.get_icon('uncollapsed_input')
                    else: ch_icon = lib.get_icon('collapsed_input')
                    brow.prop(chui, 'expand_bake_to_vcol_settings', text='', emboss=False, icon_value=ch_icon)
                    vcols = get_vertex_colors(context.object)
                    if yp.use_baked and channel.bake_to_vcol_name in vcols:
                        brow.label(text='Use Baked Vertex Color:')
                    else: brow.label(text='Bake To Vertex Color:')
                    brow.prop(channel, 'enable_bake_to_vcol', text='')

                    if chui.expand_bake_to_vcol_settings:
                        brow = bcol.row(align=True)
                        brow.label(text='', icon='BLANK1')
                        bbox = brow.box()
                        bbcol = bbox.column() #align=True)
                        bbcol.active = channel.enable_bake_to_vcol
                        brow = bbcol.row(align=True)
                        if channel.type == 'VALUE':
                            brow.label(text='Bake to Alpha Only:')
                            brow.prop(channel, 'bake_to_vcol_alpha', text='')

                        brow = bbcol.row(align=True)
                        brow.label(text='Target Vertex Color:')
                        brow.prop(channel, 'bake_to_vcol_name', text='')

def draw_layer_source(context, layout, layer, layer_tree, source, image, vcol, is_a_mesh):
    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    scene = context.scene

    row = layout.row(align=True)
    if image:
        if lui.expand_content:
            icon_value = lib.get_icon('uncollapsed_image')
        else: icon_value = lib.get_icon('collapsed_image')
        row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        if image.yia.is_image_atlas or image.yua.is_udim_atlas:
            row.label(text=layer.name)
        else: row.label(text=image.name)
    elif vcol:
        #if len(layer.modifiers) > 0:
        if lui.expand_content:
            icon_value = lib.get_icon('uncollapsed_vertex_color')
        else: icon_value = lib.get_icon('collapsed_vertex_color')
        row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        #else:
        #    row.label(text='', icon_value=lib.get_icon('vertex_color'))
        row.label(text=vcol.name)
    elif layer.type == 'BACKGROUND':
        if len(layer.modifiers) > 0:
            if lui.expand_content:
                icon_value = lib.get_icon('uncollapsed_background')
            else: icon_value = lib.get_icon('collapsed_background')
            row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.label(text='', icon_value=lib.get_icon('background'))
        row.label(text=layer.name)
    elif layer.type == 'COLOR':
        if lui.expand_content:
            icon_value = lib.get_icon('uncollapsed_color')
        else: icon_value = lib.get_icon('collapsed_color')
        row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        row.label(text=layer.name)
    elif layer.type == 'GROUP':
        row.label(text='', icon_value=lib.get_icon('group'))
        row.label(text=layer.name)
    elif layer.type == 'HEMI':
        if lui.expand_content:
            icon_value = lib.get_icon('uncollapsed_hemi')
        else: icon_value = lib.get_icon('collapsed_hemi')
        row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        row.label(text=layer.name)
    else:
        title = source.bl_idname.replace('ShaderNodeTex', '')
        if lui.expand_content:
            icon_value = lib.get_icon('uncollapsed_texture')
        else: icon_value = lib.get_icon('collapsed_texture')
        row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        row.label(text=title)

    row.context_pointer_set('parent', layer)
    row.context_pointer_set('layer', layer)
    row.context_pointer_set('layer_ui', lui)

    if layer.use_temp_bake:
        row = row.row(align=True)
        row.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')

    #if layer.type != 'GROUP':
    icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
    row.menu("NODE_MT_y_layer_special_menu", icon=icon, text='')

    if layer.type == 'GROUP': return
    #if layer.type in {'VCOL', 'BACKGROUND'} and len(layer.modifiers) == 0: return
    if layer.type in {'BACKGROUND'} and len(layer.modifiers) == 0: return
    if not lui.expand_content: return

    rrow = layout.row(align=True)
    rrow.label(text='', icon='BLANK1')
    rcol = rrow.column(align=False)

    modcol = rcol.column()
    modcol.active = layer.type not in {'BACKGROUND', 'GROUP'}
    draw_modifier_stack(context, layer, 'RGB', modcol, 
            lui, layer)

    #if layer.type not in {'VCOL', 'BACKGROUND'}:
    if layer.type not in {'BACKGROUND'}:
        row = rcol.row(align=True)

        if layer.type == 'IMAGE':
            suffix = 'image'
        elif layer.type == 'COLOR':
            suffix = 'color'
        elif layer.type == 'HEMI':
            suffix = 'hemi'
        elif layer.type == 'VCOL':
            suffix = 'vertex_color'
        else: suffix = 'texture'

        if lui.expand_source:
            icon_value = lib.get_icon('uncollapsed_' + suffix)
        else: icon_value = lib.get_icon('collapsed_' + suffix)
        row.prop(lui, 'expand_source', text='', emboss=False, icon_value=icon_value)
        #else:
        #    if layer.type == 'IMAGE':
        #        icon = 'IMAGE_DATA'
        #    #elif layer.type == 'VCOL':
        #    #    icon = 'GROUP_VCOL'
        #    else:
        #        icon = 'TEXTURE'
        #    #icon = 'IMAGE_DATA' if layer.type == 'IMAGE' else 'TEXTURE'
        #    row.prop(lui, 'expand_source', text='', emboss=True, icon=icon)
        text_source = pgettext_iface('Source: ')
        if image:
            image_name = image.name
            if image.y_bake_info.is_baked:
                image_name += ' (Baked)'
            row.label(text=text_source + image_name)
        elif vcol:
            row.label(text=text_source + vcol.name)
        else: row.label(text=text_source + layer.name)

        if lui.expand_source:
            row = rcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bbox = row.box()

            if layer.use_temp_bake:
                bbox.context_pointer_set('parent', layer)
                bbox.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')
            elif image:
                draw_image_props(context, source, bbox, layer, show_flip_y=True)
                if hasattr(layer, 'divide_rgb_by_alpha'):
                    bbox.prop(layer, 'divide_rgb_by_alpha', text='Spread Fix')
            elif layer.type == 'COLOR':
                draw_solid_color_props(layer, source, bbox)
            elif layer.type == 'VCOL':
                draw_vcol_props(bbox, vcol, layer)
            elif layer.type == 'HEMI':
                draw_hemi_props(layer, source, bbox)
            else: draw_tex_props(source, bbox, entity=layer)

        # Vector
        #if layer.type not in {'VCOL', 'COLOR', 'HEMI', 'OBJECT_INDEX'}:
        if is_layer_using_vector(layer):
            row = rcol.row(align=True)

            if lui.expand_vector:
                icon_value = lib.get_icon('uncollapsed_uv')
            else: icon_value = lib.get_icon('collapsed_uv')
            row.prop(lui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
            #else:
            #    row.prop(lui, 'expand_vector', text='', emboss=True, icon_value=lib.get_icon('uv'))

            texcoord = layer_tree.nodes.get(layer.texcoord)

            split = split_layout(row, 0.275, align=True)

            split.label(text='Vector:')
            if is_a_mesh and layer.texcoord_type == 'UV':

                ssplit = split_layout(split, 0.33, align=True)

                ssplit.prop(layer, 'texcoord_type', text='')
                ssplit.prop_search(layer, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            elif layer.type == 'IMAGE' and layer.texcoord_type in {'Generated', 'Object'} and not lui.expand_vector:
                ssplit = split_layout(split, 0.5, align=True)

                ssplit.prop(layer, 'texcoord_type', text='')
                ssplit.prop(layer, 'projection_blend', text='')
            elif layer.texcoord_type == 'Decal' and not lui.expand_vector:
                ssplit = split_layout(split, 0.4, align=True)
                if texcoord:
                    ssplit.prop(layer, 'texcoord_type', text='')
                    ssplit.prop(texcoord, 'object', text='')
            else:
                split.prop(layer, 'texcoord_type', text='')

            if layer.texcoord_type == 'UV':
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                row.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')

            if lui.expand_vector:
                row = rcol.row(align=True)
                row.label(text='', icon='BLANK1')
                bbox = row.box()
                boxcol = bbox.column()
                if image and (image.yia.is_image_atlas or image.yua.is_udim_atlas):
                    #boxcol.label(text="Transform vector with image atlas is not possible!")
                    pass
                else:
                    if layer.type == 'IMAGE' and layer.texcoord_type in {'Generated', 'Object'}:
                        splits = split_layout(boxcol, 0.5, align=True)
                        splits.label(text='Projection Blend:')
                        splits.prop(layer, 'projection_blend', text='')

                    if layer.texcoord_type == 'Decal':

                        if texcoord:
                            splits = split_layout(boxcol, 0.45, align=True)
                            splits.label(text='Decal Object:')
                            splits.prop(texcoord, 'object', text='')

                        splits = split_layout(boxcol, 0.5, align=True)
                        splits.label(text='Decal Distance:')
                        draw_input_prop(splits, layer, 'decal_distance_value')

                        boxcol.context_pointer_set('entity', layer)
                        if is_bl_newer_than(2, 80):
                            boxcol.operator('node.y_select_decal_object', icon='EMPTY_SINGLE_ARROW')
                        else: boxcol.operator('node.y_select_decal_object', icon='EMPTY_DATA')
                        boxcol.operator('node.y_set_decal_object_position_to_sursor', text='Set Position to Cursor', icon='CURSOR')

                    if layer.texcoord_type != 'Decal':
                        mapping = get_layer_mapping(layer)

                        rrow = boxcol.row()
                        rrow.label(text='Transform:')
                        rrow.prop(mapping, 'vector_type', text='')

                        rrow = boxcol.row()
                        if is_bl_newer_than(2, 81):
                            mcol = rrow.column()
                            mcol.prop(mapping.inputs[1], 'default_value', text='Offset')
                            mcol = rrow.column()
                            mcol.prop(mapping.inputs[2], 'default_value', text='Rotation')
                            if layer.enable_uniform_scale:
                                mcol = rrow.column(align=True)
                                mcol.label(text='Scale:')
                                draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'X')
                                draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'Y')
                                draw_input_prop(mcol, layer, 'uniform_scale_value', None, 'Z')
                            else:
                                mcol = rrow.column()
                                mcol.prop(mapping.inputs[3], 'default_value', text='Scale')
                        else:
                            mcol = rrow.column()
                            mcol.prop(mapping, 'translation')
                            mcol = rrow.column()
                            mcol.prop(mapping, 'rotation')
                            mcol = rrow.column()
                            mcol.prop(mapping, 'scale')
                    
                        # Uniform scale
                        if is_bl_newer_than(2, 81):
                            rrow = boxcol.row(align=True)
                            splits = split_layout(rrow, 0.5)
                            splits.label(text='Uniform Scale:')
                            rrow.prop(layer, 'enable_uniform_scale', text='')

                        if yp.need_temp_uv_refresh:
                            rrow = boxcol.row(align=True)
                            rrow.alert = True
                            rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

                # Blur row
                rrow = boxcol.row(align=True)
                splits = split_layout(rrow, 0.5)
                splits.label(text='Blur:')
                if layer.enable_blur_vector:
                    draw_input_prop(splits, layer, 'blur_vector_factor')
                rrow.prop(layer, 'enable_blur_vector', text='')

    layout.separator()

def draw_layer_channels(context, layout, layer, layer_tree, image):

    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    
    enabled_channels = [c for c in layer.channels if c.enable]
    root_ch = None
    ch = None

    label = pgettext_iface('Channel')
    if len(enabled_channels) == 0:
        #label += ' (0)'
        pass
    elif len(enabled_channels) == 1:
        if lui.expand_channels:
            label += ' (1)'
        else:
            ch = enabled_channels[0]
            ch_idx = get_layer_channel_index(layer, ch)
            root_ch = yp.channels[ch_idx]
            #label = root_ch.name
            if root_ch.type == 'NORMAL' and ch.normal_map_type != 'NORMAL_MAP':
                if ch.normal_map_type == 'BUMP_MAP':
                    label += ' (Bump)'
                    #label = 'Bump'
                elif ch.normal_map_type == 'BUMP_NORMAL_MAP':
                    label += ' (Bump + Normal)'
                    #label = 'Bump + Normal'
                elif ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                    label += ' (VDM)'
                    #label = 'VDM'
                #label += ' (' + root_ch.name + ')'
            else:
                label += ' (' + root_ch.name + ')'
                #label = root_ch.name
            label += ':'

    else:
        label = pgettext_iface('Channels') + ' (' + str(len(enabled_channels)) + ')'

    if lui.expand_channels:
        label += ':'
    
    row = layout.row(align=True)
    if lui.expand_channels:
        icon_value = lib.get_icon('uncollapsed_channels')
    else: icon_value = lib.get_icon('collapsed_channels')
    row.prop(lui, 'expand_channels', text='', emboss=False, icon_value=icon_value)

    row.label(text=label)

    if ch and root_ch:
        if root_ch.type == 'NORMAL':
            rrow = row.row(align=True)
            rrow.scale_x = 0.75
            rrow.prop(ch, 'normal_blend_type', text='')
            #rrow.prop(ch, 'normal_map_type', text='')
            rrow = row.row(align=True)
            rrow.scale_x = 0.75
            if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                draw_input_prop(rrow, ch, 'bump_distance')
            elif ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                draw_input_prop(rrow, ch, 'vdisp_strength')
            else: draw_input_prop(rrow, ch, 'normal_strength')
        else: 
            rrow = row.row(align=True)
            rrow.scale_x = 0.9
            rrow.prop(ch, 'blend_type', text='')

    if not lui.expand_channels:
        return

    row.prop(ypui, 'expand_channels', text='', emboss=True, icon_value = lib.get_icon('channels'))

    rrow = layout.row(align=True)
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

        if not ypui.expand_channels and not ch.enable:
            continue

        root_ch = yp.channels[i]
        ch_count += 1

        try: chui = ypui.layer_ui.channels[i]
        except: 
            ypui.need_update = True
            return

        ccol = rcol.column()
        ccol.active = ch.enable
        ccol.context_pointer_set('channel', ch)

        row = ccol.row(align=True)

        expandable = True
        #expandable = (
        #        len(ch.modifiers) > 0 or 
        #        layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'MUSGRAVE'} or 
        #        root_ch.type == 'NORMAL' or
        #        ch.show_transition_ramp or
        #        ch.show_transition_ao or
        #        showed_bump_ch_found
        #        )

        icon_name = lib.channel_custom_icon_dict[root_ch.type]
        if expandable:
            if chui.expand_content:
                icon_name = 'uncollapsed_' + icon_name
            else: icon_name = 'collapsed_' + icon_name
        icon_value = lib.get_icon(icon_name)
        if expandable:
            row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else: row.label(text='', icon_value=icon_value)

        row.label(text=yp.channels[i].name + ':', translate=False)

        #if layer.type != 'BACKGROUND':
        if root_ch.type == 'NORMAL':
            row.prop(ch, 'normal_blend_type', text='')
        elif layer.type != 'BACKGROUND':
            row.prop(ch, 'blend_type', text='')

        draw_input_prop(row, ch, 'intensity_value')

        row.context_pointer_set('parent', ch)
        row.context_pointer_set('layer', layer)
        row.context_pointer_set('channel_ui', chui)

        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.menu("NODE_MT_y_layer_channel_special_menu", icon=icon, text='')

        if ypui.expand_channels:
            row.prop(ch, 'enable', text='')

        if not expandable or not chui.expand_content: continue

        mrow = ccol.row(align=True)
        mrow.label(text='', icon='BLANK1')
        mcol = mrow.column()

        if root_ch.type == 'NORMAL':

            if root_ch.enable_smooth_bump and image:

                uv_neighbor = layer_tree.nodes.get(layer.uv_neighbor)
                if uv_neighbor:
                    cur_x = uv_neighbor.inputs[1].default_value 
                    cur_y = uv_neighbor.inputs[2].default_value 

                    correct_x, correct_y = get_correct_uv_neighbor_resolution(ch, image)

                    if round(cur_x, 2) != round(correct_x, 2) or round(cur_y, 2) != round(correct_y, 2):
                        brow = mcol.row(align=True)
                        brow.alert = True
                        brow.context_pointer_set('channel', ch)
                        brow.context_pointer_set('image', image)
                        brow.operator('node.y_refresh_neighbor_uv', icon='ERROR')

            if ch.show_transition_bump or ch.enable_transition_bump:

                brow = mcol.row(align=True)
                if chui.expand_transition_bump_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                brow.prop(chui, 'expand_transition_bump_settings', text='', emboss=False, icon_value=icon_value)
                #else:
                #    brow.prop(chui, 'expand_transition_bump_settings', text='', emboss=True, icon='MOD_MASK')
                brow.label(text='Transition Bump:')

                if ch.enable_transition_bump and not chui.expand_transition_bump_settings:
                    draw_input_prop(brow, ch, 'transition_bump_distance')

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
                    draw_input_prop(crow, ch, 'transition_bump_distance')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 1:') #, icon_value=lib.get_icon('input'))
                    draw_input_prop(crow, ch, 'transition_bump_value')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 2:') #, icon_value=lib.get_icon('input'))
                    draw_input_prop(crow, ch, 'transition_bump_second_edge_value')

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
                        draw_input_prop(crow, ch, 'transition_bump_crease_factor')

                        crow = cccol.row(align=True)
                        crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                        crow.label(text='Crease Power:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(crow, ch, 'transition_bump_crease_power')

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
                            draw_input_prop(crow, ch, 'transition_bump_falloff_emulated_curve_fac')
                        
                        elif ch.transition_bump_falloff_type == 'CURVE' and ch.enable_transition_bump and ch.enable:
                            cccol.separator()
                            tbf = layer_tree.nodes.get(ch.tb_falloff)
                            if root_ch.enable_smooth_bump:
                                tbf = tbf.node_tree.nodes.get('_original')
                            curve = tbf.node_tree.nodes.get('_curve')
                            curve.draw_buttons_ext(context, cccol)

                    #row.label(text='', icon='BLANK1')

            row = mcol.row(align=True)
            #row.active = layer.type != 'COLOR'
            #row.active = not is_valid_to_remove_bump_nodes(layer, ch)

            if chui.expand_bump_settings:
                icon_value = lib.get_icon('uncollapsed_input')
            else: icon_value = lib.get_icon('collapsed_input')
            row.prop(chui, 'expand_bump_settings', text='', emboss=False, icon_value=icon_value)

            if layer.type == 'GROUP':
                if chui.expand_bump_settings:
                    row.label(text='Group Normal Settings:')
                else: row.label(text='Group Normal Settings')
            else:
                split = split_layout(row, 0.275)
                split.label(text='Type:')
                srow = split.row(align=True)
                srow.prop(ch, 'normal_map_type', text='')
                if not chui.expand_bump_settings:
                    if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                        # Solid color with transition bump always have bump distance value of 0
                        ssrow = srow.row(align=True)
                        ssrow.active = is_bump_distance_relevant(layer, ch)
                        draw_input_prop(ssrow, ch, 'bump_distance')
                    elif ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                        draw_input_prop(srow, ch, 'vdisp_strength')
                    else:
                        draw_input_prop(srow, ch, 'normal_strength')

            #row.label(text='', icon='BLANK1')

            #if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'} and chui.expand_bump_settings:
            if chui.expand_bump_settings:
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')

                bbox = row.box()
                #bbox.active = layer.type != 'COLOR'
                #bbox.active = not is_valid_to_remove_bump_nodes(layer, ch)
                cccol = bbox.column(align=True)

                #if ch.normal_map_type != 'BUMP_NORMAL_MAP':
                if ch.normal_map_type not in {'NORMAL_MAP', 'VECTOR_DISPLACEMENT_MAP'} or ch.enable_transition_bump:
                    brow = cccol.row(align=True)
                    brow.label(text='Write Height:') #, icon_value=lib.get_icon('input'))
                    brow.prop(ch, 'write_height', text='')

                #if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:

                if layer.type != 'GROUP':
                    #brow = cccol.row(align=True)
                    #brow.active = not ch.enable_transition_bump or ch.normal_map_type != 'NORMAL_MAP'
                    if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                        brow = cccol.row(align=True)
                        brow.active = layer.type != 'COLOR' or not ch.enable_transition_bump
                        brow.label(text='Height:') #, icon_value=lib.get_icon('input'))
                        brow.active == is_bump_distance_relevant(layer, ch)
                        draw_input_prop(brow, ch, 'bump_distance')
                        brow = cccol.row(align=True)
                        brow.label(text='Midlevel:') 
                        draw_input_prop(brow, ch, 'bump_midlevel')
                        if root_ch.enable_smooth_bump:
                            brow = cccol.row(align=True)
                            brow.label(text='Smooth Multiplier:') 
                            draw_input_prop(brow, ch, 'bump_smooth_multiplier')

                    if ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}: 
                        brow = cccol.row(align=True)
                        brow.label(text='Normal Strength:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(brow, ch, 'normal_strength')
                    elif ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                        brow = cccol.row(align=True)
                        brow.label(text='Strength:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(brow, ch, 'vdisp_strength')

                        brow = cccol.row(align=True)
                        brow.label(text='Flip Y/Z:') #, icon_value=lib.get_icon('input'))
                        draw_input_prop(brow, ch, 'vdisp_enable_flip_yz')

                #brow = cccol.row(align=True)
                #brow.label(text='Invert Backface Normal')
                #brow.prop(ch, 'invert_backface_normal', text='')

                #row.label(text='', icon='BLANK1')

            extra_separator = True

        if root_ch.type in {'RGB', 'VALUE'}:

            if ch.show_transition_ramp or ch.enable_transition_ramp:

                # Transition Ramp
                row = mcol.row(align=True)

                tr_ramp = layer_tree.nodes.get(ch.tr_ramp)
                if not tr_ramp:
                    row.label(text='', icon_value=lib.get_icon('input'))
                else:
                    if chui.expand_transition_ramp_settings:
                        icon_value = lib.get_icon('uncollapsed_input')
                    else: icon_value = lib.get_icon('collapsed_input')
                    row.prop(chui, 'expand_transition_ramp_settings', text='', emboss=False, icon_value=icon_value)
                row.label(text='Transition Ramp:')
                if ch.enable_transition_ramp and not chui.expand_transition_ramp_settings:
                    draw_input_prop(row, ch, 'transition_ramp_intensity_value')

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
                    draw_input_prop(brow, ch, 'transition_ramp_intensity_value')

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ramp_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.active = bump_ch_found
                    brow.label(text='Transition Factor:')
                    draw_input_prop(brow, ch, 'transition_bump_second_fac')

                    if tr_ramp.type == 'GROUP':
                        ramp = tr_ramp.node_tree.nodes.get('_RAMP')

                        #brow.prop(ch, 'ramp_intensity_value', text='')
                        bcol.template_color_ramp(ramp, "color_ramp", expand=True)
                        #row.label(text='', icon='BLANK1')

            if ch.show_transition_ao or ch.enable_transition_ao:

                # Transition AO
                row = mcol.row(align=True)
                row.active = bump_ch_found #and layer.type != 'BACKGROUND'
                if chui.expand_transition_ao_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                row.prop(chui, 'expand_transition_ao_settings', text='', emboss=False, icon_value=icon_value)
                row.label(text='Transition AO:')
                if ch.enable_transition_ao and not chui.expand_transition_ao_settings:
                    draw_input_prop(row, ch, 'transition_ao_intensity')

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
                    draw_input_prop(brow, ch, 'transition_ao_intensity')

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ao_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Power:')
                    draw_input_prop(brow, ch, 'transition_ao_power')

                    brow = bcol.row(align=True)
                    brow.label(text='Color:')
                    draw_input_prop(brow, ch, 'transition_ao_color')

                    brow = bcol.row(align=True)
                    brow.label(text='Inside:')
                    draw_input_prop(brow, ch, 'transition_ao_inside_intensity')

            # Transition Bump Intensity
            if showed_bump_ch_found:
                row = mcol.row(align=True)
                row.active = bump_ch_found
                row.label(text='', icon_value=lib.get_icon('input'))
                row.label(text='Transition Factor')
                draw_input_prop(row, ch, 'transition_bump_fac')

            extra_separator = True

        # Get sources
        source = get_channel_source(ch, layer)
        source_1 = layer_tree.nodes.get(ch.source_1)
        cache_1 = layer_tree.nodes.get(ch.cache_1_image)

        # Override settings
        if root_ch.type != 'NORMAL' or ch.normal_map_type != 'NORMAL_MAP': # or (not source_1 and not cache_1):

            modcol = mcol.column()
            modcol.active = layer.type != 'BACKGROUND'
            draw_modifier_stack(context, ch, root_ch.type, modcol, 
                    ypui.layer_ui.channels[i], layer)

            if root_ch.type != 'NORMAL' or ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP' or ch.override:
                row = mcol.row(align=True)
                if ch.override_type == 'DEFAULT':
                    row.label(text='', icon_value=lib.get_icon('input'))
                else:
                    if chui.expand_source:
                        icon_value = lib.get_icon('uncollapsed_input')
                    else: icon_value = lib.get_icon('collapsed_input')
                    row.prop(chui, 'expand_source', text='', emboss=False, icon_value=icon_value)

                label_str = 'Override'
                if root_ch.type == 'NORMAL' and ch.normal_map_type == 'BUMP_NORMAL_MAP':
                    label_str += ' Bump'
                if ch.override_type == 'IMAGE':
                    if source: label_str += ' (' + source.image.name + ')'
                elif ch.override_type == 'VCOL':
                    if source: label_str += ' (' + get_source_vcol_name(source) + ')'
                elif ch.override_type != 'DEFAULT':
                    label_str += ' (' + channel_override_labels[ch.override_type] + ')'
                label_str += ':'
                row.label(text=label_str)

                if ch.enable:
                    if ch.override_type == 'IMAGE':
                        row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('image'))
                    elif ch.override_type == 'VCOL':
                        row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color'))
                    elif ch.override_type != 'DEFAULT':
                        row.prop(ch, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('texture'))

                row.context_pointer_set('parent', ch)
                if ch.override and ch.override_type == 'DEFAULT':
                    if root_ch.type == 'VALUE':
                        draw_input_prop(row, ch, 'override_value')
                    else: draw_input_prop(row, ch, 'override_color')
                row.prop(ch, 'override', text='')

                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                row.menu("NODE_MT_y_replace_channel_override_menu", icon=icon, text='')

                ch_source = None
                if ch.override:
                    #ch_source = layer_tree.nodes.get(ch.source)
                    ch_source = get_channel_source(ch, layer)
                elif ch.override_type not in {'DEFAULT'}:
                    ch_source = layer_tree.nodes.get(getattr(ch, 'cache_' + ch.override_type.lower()))

                if ch.expand_source and ch.override_type != 'DEFAULT'  and ch_source:
                    rrow = mcol.row(align=True)
                    rrow.label(text='', icon='BLANK1')
                    rbox = rrow.box()
                    rbox.active = ch.override
                    if ch.override_type == 'IMAGE':
                        draw_image_props(context, ch_source, rbox, ch)
                    elif ch.override_type == 'VCOL':
                        draw_vcol_props(rbox)
                    else:
                        draw_tex_props(ch_source, rbox, entity=ch)

        # Override 1
        if root_ch.type == 'NORMAL' and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}: # and (source_1 or cache_1))):

            modcol = mcol.column()
            modcol.active = layer.type != 'BACKGROUND'
            draw_modifier_stack(context, ch, root_ch.type, modcol, 
                    ypui.layer_ui.channels[i], layer, use_modifier_1=True)

            row = mcol.row(align=True)
            if ch.override_1_type == 'DEFAULT':
                row.label(text='', icon_value=lib.get_icon('input'))
            else:
                if chui.expand_source_1:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                row.prop(chui, 'expand_source_1', text='', emboss=False, icon_value=icon_value)

            label_str = 'Override Normal'
            if ch.override_1_type == 'IMAGE':
                if source_1: label_str += ' (' + source_1.image.name + ')'
            elif ch.override_1_type == 'VCOL':
                if source_1: label_str += ' (' + get_source_vcol_name(source_1) + ')'
            elif ch.override_1_type != 'DEFAULT':
                label_str += ' (' + channel_override_labels[ch.override_1_type] + ')'
            label_str += ':'
            row.label(text=label_str)

            row.context_pointer_set('parent', ch)
            if ch.override_1 and ch.override_1_type == 'DEFAULT':
                #if root_ch.type == 'VALUE':
                #    row.prop(ch, 'override_value', text='')
                #else: 
                draw_input_prop(row, ch, 'override_1_color')

            if ch.enable and ch.override_1_type == 'IMAGE':
                row.prop(ch, 'active_edit_1', text='', toggle=True, icon_value=lib.get_icon('image'))

            row.prop(ch, 'override_1', text='')

            icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
            row.menu("NODE_MT_y_replace_channel_override_1_menu", icon=icon, text='')

            ch_source_1 = None
            if ch.override_1:
                ch_source_1 = layer_tree.nodes.get(ch.source_1)
            elif ch.override_1_type not in {'DEFAULT'}:
                #ch_source_1 = layer_tree.nodes.get(getattr(ch, 'cache_' + ch.override_1_type.lower()))
                ch_source_1 = layer_tree.nodes.get(getattr(ch, 'cache_1_image'))

            if ch.expand_source_1 and ch.override_1_type == 'IMAGE' and ch_source_1:
                rrow = mcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                rbox.active = ch.override_1
                draw_image_props(context, ch_source_1, rbox, entity=ch, show_flip_y=True)

        # Layer input
        if (layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'MUSGRAVE'} and not 
            (is_bl_newer_than(2, 81) and layer.type == 'VORONOI' and layer.voronoi_feature in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'})
            ):
            row = mcol.row(align=True)

            input_settings_available = (ch.layer_input != 'ALPHA' 
                    and root_ch.colorspace == 'SRGB' and root_ch.type != 'NORMAL' )

            if input_settings_available:
                if chui.expand_input_settings:
                    icon_value = lib.get_icon('uncollapsed_input')
                else: icon_value = lib.get_icon('collapsed_input')
                row.prop(chui, 'expand_input_settings', text='', emboss=False, icon_value=icon_value)
            else:
                row.label(text='', icon_value=lib.get_icon('input'))

            split = split_layout(row, 0.275)

            split.label(text='Input:')
            srow = split.row(align=True)
            srow.prop(ch, 'layer_input', text='')

            if chui.expand_input_settings and input_settings_available:
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')
                box = row.box()
                bcol = box.column(align=False)

                brow = bcol.row(align=True)
                brow.label(text='Gamma Space:')
                brow.prop(ch, 'gamma_space', text='')

            #row.label(text='', icon='BLANK1')

            extra_separator = True

        if ypui.expand_channels:
            mrow.label(text='', icon='BLANK1')

        if extra_separator and i < len(layer.channels)-1:
            ccol.separator()

    if not ypui.expand_channels and ch_count == 0:
        rcol.label(text='No active channel!')

    layout.separator()

def draw_layer_masks(context, layout, layer):
    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui

    layer_tree = get_tree(layer)

    col = layout.column()
    col.active = layer.enable_masks

    row = col.row(align=True)
    if len(layer.masks) > 0:
        if lui.expand_masks:
            icon_value = lib.get_icon('uncollapsed_mask')
        else: icon_value = lib.get_icon('collapsed_mask')
        row.prop(lui, 'expand_masks', text='', emboss=False, icon_value=icon_value)
    else: 
        icon_value = lib.get_icon('mask')
        row.label(text='', icon_value=icon_value)
        #row.label(text='', icon='MOD_MASK')

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

    if lui.expand_masks:
        label += ':'

    row.label(text=label)

    if is_bl_newer_than(2, 80):
        row.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='ADD')
    else: row.menu('NODE_MT_y_add_layer_mask_menu', text='', icon='ZOOMIN')

    if not lui.expand_masks or len(layer.masks) == 0: return

    row = col.row(align=True)
    row.label(text='', icon='BLANK1')
    rcol = row.column(align=False)

    for i, mask in enumerate(layer.masks):

        try: maskui = ypui.layer_ui.masks[i]
        except: 
            ypui.need_update = True
            return

        row = rcol.row(align=True)
        row.active = mask.enable

        if maskui.expand_content:
            icon_value = lib.get_icon('uncollapsed_mask')
        else: icon_value = lib.get_icon('collapsed_mask')
        row.prop(maskui, 'expand_content', text='', emboss=False, icon_value=icon_value)

        mask_image = None
        mask_tree = get_mask_tree(mask)
        mask_source = mask_tree.nodes.get(mask.source)
        if mask.type == 'IMAGE':
            mask_image = mask_source.image
            if mask_image.yia.is_image_atlas or mask_image.yua.is_udim_atlas:
                label_text = mask.name
            else: label_text = mask_image.name
        else: label_text = mask.name

        if mask.type in {'IMAGE', 'VCOL'} and mask.source_input == 'ALPHA':
            label_text += ' (Alpha)'

        row.label(text=label_text)

        if mask.baked_source != '':
            row.prop(mask, 'use_baked', text='Use Baked', toggle=True)

        if not maskui.expand_content:
            rrow = row.row(align=True)
            rrow.scale_x = 0.8
            rrow.prop(mask, 'blend_type', text='')
            rrow = row.row(align=True)
            rrow.scale_x = 0.8
            draw_input_prop(rrow, mask, 'intensity_value')

        if mask.enable:
            if mask.type == 'IMAGE':
                if mask.source_input == 'ALPHA':
                    row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('alpha_image'))
                else: row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('image'))
            elif mask.type == 'VCOL':
                if mask.source_input == 'ALPHA':
                    row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color_alpha'))
                else: row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('vertex_color'))
            elif mask.type == 'HEMI':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('hemi'))
            elif mask.type == 'OBJECT_INDEX':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('object_index'))
            elif mask.type == 'EDGE_DETECT':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('edge_detect'))
            elif mask.type == 'COLOR_ID':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('color'))
            elif mask.type == 'BACKFACE':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('backface'))
            elif mask.type == 'MODIFIER':
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('modifier'))
            else:
                row.prop(mask, 'active_edit', text='', toggle=True, icon_value=lib.get_icon('texture'))

        row.context_pointer_set('mask', mask)

        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.menu("NODE_MT_y_layer_mask_menu", text='', icon=icon)

        row = row.row(align=True)
        row.prop(mask, 'enable', text='')

        if not maskui.expand_content: continue

        row = rcol.row(align=True)
        row.active = mask.enable
        row.label(text='', icon='BLANK1')
        rrcol = row.column()
        row.label(text='', icon='BLANK1')

        # Source row
        rrow = rrcol.row(align=True)

        if mask.type == 'VCOL':
            rrow.label(text='', icon_value=lib.get_icon('vertex_color'))
        elif mask.type == 'BACKFACE':
            rrow.label(text='', icon_value=lib.get_icon('backface'))
        elif mask.type == 'MODIFIER' and mask.modifier_type == 'INVERT':
            rrow.label(text='', icon_value=lib.get_icon('modifier'))
        else:
            if mask.type == 'IMAGE':
                suffix = 'image' 
            elif mask.type == 'HEMI':
                suffix = 'hemi' 
            elif mask.type == 'OBJECT_INDEX':
                suffix = 'object_index' 
            elif mask.type == 'EDGE_DETECT':
                suffix = 'edge_detect' 
            elif mask.type == 'COLOR_ID':
                suffix = 'color' 
            elif mask.type == 'BACKFACE':
                suffix = 'backface' 
            elif mask.type == 'MODIFIER':
                suffix = 'modifier' 
            else:
                suffix = 'texture' 
            if maskui.expand_source:
                icon_value = lib.get_icon('uncollapsed_' + suffix)
            else: icon_value = lib.get_icon('collapsed_' + suffix)
            rrow.prop(maskui, 'expand_source', text='', emboss=False, icon_value=icon_value)

        text_source = pgettext_iface('Source: ')
        if mask_image:
            rrow.label(text=text_source + mask_image.name)
        else: rrow.label(text=text_source + mask.name)

        if maskui.expand_source and (mask.type not in {'VCOL', 'BACKFACE', 'MODIFIER'} or 
                                     (mask.type == 'MODIFIER' and mask.modifier_type in {'CURVE', 'RAMP'})):
            rrow = rrcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            rbox = rrow.box()
            rbcol = rbox.column()
            rbcol.active = not mask.use_baked
            if mask.use_temp_bake:
                rbcol.context_pointer_set('parent', mask)
                rbcol.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')
            elif mask_image:
                draw_image_props(context, mask_source, rbcol, mask)
            elif mask.type == 'HEMI':
                draw_hemi_props(mask, mask_source, rbcol)
            elif mask.type == 'OBJECT_INDEX':
                draw_object_index_props(mask, rbcol)
            elif mask.type == 'COLOR_ID':
                draw_colorid_props(mask, mask_source, rbcol)
            elif mask.type == 'EDGE_DETECT':
                draw_edge_detect_props(mask, mask_source, rbcol)
            elif mask.type == 'MODIFIER':
                draw_inbetween_modifier_mask_props(mask, mask_source, rbcol)
            else: draw_tex_props(mask_source, rbcol, entity=mask)

            if mask.baked_source != '':
                rbox.context_pointer_set('entity', mask)
                rbox.operator("node.y_bake_entity_to_image", text='Rebake', icon_value=lib.get_icon('bake'))

        # Input row
        if (mask.type not in {'COLOR_ID', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER'} and (is_bl_newer_than(2, 92) or mask.type != 'VCOL') and
            not (is_bl_newer_than(2, 81) and mask.type == 'VORONOI' and mask.voronoi_feature in {'DISTANCE_TO_EDGE', 'N_SPHERE_RADIUS'})
            ):
            rrow = rrcol.row(align=True)
            rrow.label(text='', icon_value=lib.get_icon('input'))
            splits = split_layout(rrow, 0.3)
            splits.active = not mask.use_baked
            splits.label(text='Input:')
            splits.prop(mask, 'source_input', text='')

        # Vector row
        if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER'}:
            rrow = rrcol.row(align=True)

            if maskui.expand_vector:
                icon_value = lib.get_icon('uncollapsed_uv')
            else: icon_value = lib.get_icon('collapsed_uv')
            rrow.prop(maskui, 'expand_vector', text='', emboss=False, icon_value=icon_value)

            splits = split_layout(rrow, 0.3)
            splits.active = not mask.use_baked

            mask_src = get_mask_source(mask)
            texcoord = layer_tree.nodes.get(mask.texcoord)

            splits.label(text='Vector:')
            if mask.texcoord_type == 'UV':

                rrrow = split_layout(splits, 0.35, align=True)
                rrrow.prop(mask, 'texcoord_type', text='')
                rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

                rrow.context_pointer_set('mask', mask)
                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                rrow.menu("NODE_MT_y_uv_special_menu", icon=icon, text='')
            elif mask.type == 'IMAGE' and mask.texcoord_type in {'Generated', 'Object'} and not maskui.expand_vector:
                rrrow = split_layout(splits, 0.5, align=True)

                rrrow.prop(mask, 'texcoord_type', text='')
                rrrow.prop(mask_src, 'projection_blend', text='')
            elif mask.texcoord_type == 'Decal' and not maskui.expand_vector:
                ssplit = split_layout(splits, 0.4, align=True)
                if texcoord:
                    ssplit.prop(mask, 'texcoord_type', text='')
                    ssplit.prop(texcoord, 'object', text='')
            else:
                splits.prop(mask, 'texcoord_type', text='')

            if maskui.expand_vector:
                rrow = rrcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                rbox.active = not mask.use_baked
                boxcol = rbox.column()
                if mask.texcoord_type == 'Layer':
                    boxcol.label(text="Mask is using layer vector", icon='INFO')
                elif mask_image and (mask_image.yia.is_image_atlas or mask_image.yua.is_udim_atlas):
                    #boxcol.label(text="Transform vector with image atlas is not possible!")
                    pass
                else:
                    if mask.type == 'IMAGE' and mask.texcoord_type in {'Generated', 'Object'}:
                        splits = split_layout(boxcol, 0.5, align=True)
                        splits.label(text='Projection Blend:')
                        splits.prop(mask_src, 'projection_blend', text='')

                    if mask.texcoord_type == 'Decal':
                        if texcoord:
                            splits = split_layout(boxcol, 0.45, align=True)
                            splits.label(text='Decal Object:')
                            splits.prop(texcoord, 'object', text='')

                        splits = split_layout(boxcol, 0.5, align=True)
                        splits.label(text='Decal Distance:')
                        draw_input_prop(splits, mask, 'decal_distance_value')

                        boxcol.context_pointer_set('entity', mask)
                        if is_bl_newer_than(2, 80):
                            boxcol.operator('node.y_select_decal_object', icon='EMPTY_SINGLE_ARROW')
                        else: boxcol.operator('node.y_select_decal_object', icon='EMPTY_DATA')
                        boxcol.operator('node.y_set_decal_object_position_to_sursor', text='Set Position to Cursor', icon='CURSOR')

                    if mask.texcoord_type != 'Decal':
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
                                mcol.label(text='Scale:')
                                draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'X')
                                draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'Y')
                                draw_input_prop(mcol, mask, 'uniform_scale_value', None, 'Z')
                            else:
                                mcol = rrow.column()
                                mcol.prop(mapping.inputs[3], 'default_value', text='Scale')
                        else:
                            mcol = rrow.column()
                            mcol.prop(mapping, 'translation')
                            mcol = rrow.column()
                            mcol.prop(mapping, 'rotation')
                            mcol = rrow.column()
                            mcol.prop(mapping, 'scale')
                    
                        # Uniform scale
                        if is_bl_newer_than(2, 81):
                            rrow = boxcol.row(align=True)
                            splits = split_layout(rrow, 0.5)
                            splits.label(text='Uniform Scale:')
                            rrow.prop(mask, 'enable_uniform_scale', text='')

                        if mask.type == 'IMAGE' and mask.active_edit and (
                                yp.need_temp_uv_refresh
                                ):
                            rrow = boxcol.row(align=True)
                            rrow.alert = True
                            rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')
            
                # Blur row
                if mask.texcoord_type != 'Layer':
                    rrow = boxcol.row(align=True)
                    splits = split_layout(rrow, 0.5)
                    splits.label(text='Blur:')
                    if mask.enable_blur_vector:
                        draw_input_prop(splits, mask, 'blur_vector_factor')
                    rrow.prop(mask, 'enable_blur_vector', text='')

        draw_mask_modifier_stack(layer, mask, rrcol, maskui)

        rrow = rrcol.row(align=True)
        rrow.label(text='', icon_value=lib.get_icon('blend'))
        rrow.label(text='Blend:')
        rrow.prop(mask, 'blend_type', text='')
        draw_input_prop(rrow, mask, 'intensity_value')

        # Mask Channels row
        rrow = rrcol.row(align=True)
        if maskui.expand_channels:
            icon_value = lib.get_icon('uncollapsed_channels')
        else: icon_value = lib.get_icon('collapsed_channels')
        rrow.prop(maskui, 'expand_channels', text='', emboss=False, icon_value=icon_value)
        rrow.label(text='Channels')

        if maskui.expand_channels:

            rrow = rrcol.row()
            rrow.label(text='', icon='BLANK1')
            rbox = rrow.box()
            bcol = rbox.column(align=True)

            # Channels row
            for k, c in enumerate(mask.channels):
                rrow = bcol.row(align=True)
                rrow.active = layer.channels[k].enable
                root_ch = yp.channels[k]
                rrow.label(text='', 
                        icon_value=lib.get_icon(lib.channel_custom_icon_dict[root_ch.type]))
                rrow.label(text=root_ch.name, translate=False)
                rrow.prop(c, 'enable', text='')

        if i < len(layer.masks)-1:
            rcol.separator()

def draw_layers_ui(context, layout, node):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    obj = context.object
    vcols = get_vertex_colors(obj)
    is_a_mesh = True if obj and obj.type == 'MESH' else False

    uv_layers = get_uv_layers(obj)

    # Check if uv is found
    uv_found = False
    if is_a_mesh and len(uv_layers) > 0: 
        uv_found = True

    box = layout.box()

    # Check duplicated yp node (indicated by more than one users)
    if group_tree.users > 1:
        row = box.row(align=True)
        row.alert = True
        op = row.operator("node.y_duplicate_yp_nodes", text='Fix Multi-User ' + get_addon_title() + ' Node', icon='ERROR')
        op.duplicate_node = True
        op.duplicate_material = False
        op.only_active = True
        row.alert = False
        #box.prop(ypui, 'make_image_single_user')
        return

    if yp.use_baked:
        col = box.column(align=False)

        if len(yp.channels) > 0:
            root_ch = yp.channels[yp.active_channel_index]

            baked = nodes.get(root_ch.baked)
            baked_vcol_node = nodes.get(root_ch.baked_vcol)

            icon_name = lib.channel_custom_icon_dict[root_ch.type]
            icon_value = lib.get_icon(icon_name)

            if not baked or not baked.image or root_ch.no_layer_using:
                col.label(text=root_ch.name + " channel hasn't been baked yet!", icon_value=icon_value)
            else:
                row = col.row(align=True)
                title = 'Baked ' + root_ch.name + ':'
                row.label(text=title, icon_value=icon_value)

                row.context_pointer_set('root_ch', root_ch)
                row.context_pointer_set('image', baked.image)

                icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
                row.menu("NODE_MT_y_baked_image_menu", text='', icon=icon)

                row = col.row(align=True)
                row.active = not root_ch.disable_global_baked or yp.enable_baked_outside
                row.label(text='', icon='BLANK1')
                if baked.image.is_dirty:
                    title = baked.image.name + ' *'
                else: title = baked.image.name
                if root_ch.disable_global_baked and not yp.enable_baked_outside:
                    title += ' (Disabled)'
                elif not root_ch.enable_bake_to_vcol and baked_vcol_node:
                    title += pgettext_iface(' (Active)')
                row.label(text=title, icon_value=lib.get_icon('image'))

                if baked.image.packed_file:
                    row.label(text='', icon='PACKAGE')

                # If enabled or a baked vertex color is found
                if root_ch.enable_bake_to_vcol or baked_vcol_node:
                    obj = context.object
                    vcols = get_vertex_colors(obj)
                    vcol_name = root_ch.bake_to_vcol_name
                    vcol = vcols.get(vcol_name)

                    row = col.row(align=True)
                    row.label(text='', icon='BLANK1')

                    row.active = not root_ch.disable_global_baked or yp.enable_baked_outside
                    title = ''
                    if root_ch.disable_global_baked and not yp.enable_baked_outside:
                        title += pgettext_iface(' (Disabled)')
                    elif root_ch.enable_bake_to_vcol and baked_vcol_node:
                        title += pgettext_iface(' (Active)')

                    if baked_vcol_node and vcol:
                        row.label(text=vcol_name + title, icon_value=lib.get_icon('vertex_color'))
                    else:
                        row.label(text='Baked vertex color is missing!' + title, icon='ERROR')

            if root_ch.type == 'NORMAL':

                baked_normal_overlay = nodes.get(root_ch.baked_normal_overlay)
                if baked_normal_overlay and baked_normal_overlay.image:
                    row = col.row(align=True)
                    row.active = not root_ch.disable_global_baked
                    row.label(text='', icon='BLANK1')
                    if baked_normal_overlay.image.is_dirty:
                        title = baked_normal_overlay.image.name + ' *'
                    else: title = baked_normal_overlay.image.name
                    if root_ch.disable_global_baked:
                        title += ' (Disabled)'
                    row.label(text=title, icon_value=lib.get_icon('image'))

                    if baked_normal_overlay.image.packed_file:
                        row.label(text='', icon='PACKAGE')

                baked_disp = nodes.get(root_ch.baked_disp)
                if baked_disp and baked_disp.image:
                    row = col.row(align=True)
                    row.active = not root_ch.disable_global_baked
                    row.label(text='', icon='BLANK1')
                    if baked_disp.image.is_dirty:
                        title = baked_disp.image.name + ' *'
                    else: title = baked_disp.image.name
                    if root_ch.disable_global_baked:
                        title += ' (Disabled)'
                    row.label(text=title, icon_value=lib.get_icon('image'))

                    if baked_disp.image.packed_file:
                        row.label(text='', icon='PACKAGE')

            btimages = []
            for bt in yp.bake_targets:
                for i, letter in enumerate(rgba_letters):
                    btc = getattr(bt, letter)
                    if getattr(btc, 'channel_name') == root_ch.name:
                        bt_node = nodes.get(bt.image_node)
                        btimg = bt_node.image if bt_node and bt_node.image else None
                        if btimg and btimg not in btimages:

                            title = btimg.name
                            if btimg.is_dirty:
                                title += ' *'

                            row = col.row(align=True)
                            row.label(text='', icon='BLANK1')
                            row.label(text=title, icon_value=lib.get_icon('image'))

                            if btimg.packed_file:
                                row.label(text='', icon='PACKAGE')

                            btimages.append(btimg)


        return

    if is_a_mesh and not uv_found:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_add_simple_uvs", icon='ERROR')
        row.alert = False
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
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_fix_channel_missmatch", text='Fix Missmatched Channels!', icon='ERROR')
        row.alert = False
        return

    # If error happens, halt_update and halt_reconnect can stuck on, add button to disable it
    if yp.halt_update:
        row = box.row(align=True)
        row.alert = True
        row.prop(yp, 'halt_update', text='Disable Halt Update', icon='ERROR')
        row.alert = False
    if yp.halt_reconnect:
        row = box.row(align=True)
        row.alert = True
        row.prop(yp, 'halt_reconnect', text='Disable Halt Reconnect', icon='ERROR')
        row.alert = False

    # Check if parallax is enabled
    height_root_ch = get_root_height_channel(yp)
    enable_parallax = is_parallax_enabled(height_root_ch)

    # Check duplicated layers (indicated by more than one users)
    #elif len(yp.layers) > 0:
    #    last_layer = yp.layers[-1]
    #    ltree = get_tree(last_layer)
    #    if ltree and (
    #        (not enable_parallax and ltree.users > 1) or
    #        (enable_parallax and ltree.users > 2)
    #        ):
    #        row = box.row(align=True)
    #        row.alert = True
    #        row.operator("node.y_fix_duplicated_yp_nodes", text='Fix Duplicated Layers', icon='ERROR')
    #        row.alert = False
    #        #box.prop(ypui, 'make_image_single_user')
    #        return

    # Check source for missing data
    missing_data = False
    for layer in yp.layers:
        if layer.type in {'IMAGE' , 'VCOL'}:
            src = get_layer_source(layer)

            if ( not src or
                (layer.type == 'IMAGE' and not src.image) or 
                (layer.type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, src))
                ):
                missing_data = True
                break

        # Also check mask source
        for mask in layer.masks:
            if mask.type in {'IMAGE' , 'VCOL'}:
                mask_src = get_mask_source(mask)

                if ( not mask_src or
                    (mask.type == 'IMAGE' and mask_src and not mask_src.image) or 
                    (mask.type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, mask_src))
                    ):
                    missing_data = True
                    break

            if mask.type == 'COLOR_ID':
                if obj.type == 'MESH' and COLOR_ID_VCOL_NAME not in vcols:
                    missing_data = True
                    break

        for ch in layer.channels:
            if ch.override and ch.override_type in {'IMAGE', 'VCOL'}:
                src = get_channel_source(ch, layer)
                if (
                    not src or
                    (ch.override_type == 'IMAGE' and not src.image) or 
                    (ch.override_type == 'VCOL' and obj.type == 'MESH' and not get_vcol_from_source(obj, src))
                    ):
                    missing_data = True
                    break

            if ch.override_1 and ch.override_1_type == 'IMAGE':
                src = get_channel_source_1(ch, layer)
                if not src or not src.image:
                    missing_data = True
                    break

        if missing_data:
            break
    
    # Show missing data button
    if missing_data:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_fix_missing_data", icon='ERROR')
        row.alert = False
        return

    # Check if any uv is missing
    if is_a_mesh:

        # Get missing uvs
        uv_missings = []

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
            if layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'COLOR', 'BACKGROUND', 'EDGE_DETECT', 'MODIFIER'}:
                uv_layer = uv_layers.get(layer.uv_name)
                if not uv_layer and layer.uv_name not in uv_missings:
                    uv_missings.append(layer.uv_name)
                    #entities.append(layer.name)

            for mask in layer.masks:
                if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER'}:
                    uv_layer = uv_layers.get(mask.uv_name)
                    if not uv_layer and mask.uv_name not in uv_missings:
                        uv_missings.append(mask.uv_name)
                        #entities.append(mask.name)

        for uv_name in uv_missings:
            row = box.row(align=True)
            row.alert = True
            title = 'UV ' + uv_name + ' is missing or renamed!'
            row.operator("node.y_fix_missing_uv", text=title, icon='ERROR').source_uv_name = uv_name
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
        row.operator('node.y_refresh_tangent_sign_vcol', icon='FILE_REFRESH', text='Tangent Sign Hacks is missing!')
        row.alert = False

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

    if len(yp.layers) > 0:
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
                    source = get_mask_source(m)
                    if m.use_baked:
                        mask_tree = get_mask_tree(m)
                        baked_source = mask_tree.nodes.get(m.baked_source)
                        if baked_source:
                            mask_image = baked_source.image
                    elif m.type == 'IMAGE':
                        #mask_tree = get_mask_tree(m)
                        #source = mask_tree.nodes.get(m.source)
                        #image = source.image
                        mask_image = source.image
                    elif m.type == 'VCOL' and is_a_mesh:
                        mask_vcol = get_vcol_from_source(obj, source)
                    elif m.type == 'COLOR_ID' and is_a_mesh:
                        colorid_vcol = vcols.get(COLOR_ID_VCOL_NAME)
                        colorid_col = get_mask_color_id_color(mask)

            # Use layer image if there is no mask image
            #if not mask:
            source = get_layer_source(layer, layer_tree)
            if layer.type == 'IMAGE':
                image = source.image
            elif layer.type == 'VCOL' and is_a_mesh:
                vcol = get_vcol_from_source(obj, source)

    # Set pointer for active layer and image
    if layer: box.context_pointer_set('layer', layer)
    if mask_image: box.context_pointer_set('image', mask_image)
    elif override_image: box.context_pointer_set('image', override_image)
    elif image: box.context_pointer_set('image', image)
    if entity: box.context_pointer_set('entity', entity)

    col = box.column()

    row = col.row()
    rcol = row.column()
    if len(yp.layers) > 0:
        #prow = rcol.row(align=True)

        prow = split_layout(rcol, 0.667, align=True)

        if yp.layer_preview_mode: prow.alert = True
        if not is_bl_newer_than(2, 80):
            prow.prop(yp, 'layer_preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')
        else: prow.prop(yp, 'layer_preview_mode', text='Preview Mode', icon='HIDE_OFF')
        #prow.alert = yp.mask_preview_mode and yp.layer_preview_mode
        #icon_value = lib.get_icon("mask)"
        prow.prop(yp, 'layer_preview_mode_type', text='') #, icon_only=True) #, expand=True)

    rcol.template_list("NODE_UL_YPaint_layers", "", yp,
            "layers", yp, "active_layer_index", rows=5, maxrows=5)  

    rcol = row.column(align=True)
    if is_bl_newer_than(2, 80):
        rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ADD')
    else: rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ZOOMIN')

    if layer:

        if has_children(layer): # or (image and not image.packed_file):

            if is_bl_newer_than(2, 80):
                rcol.operator("node.y_remove_layer_menu", icon='REMOVE', text='')
            else: rcol.operator("node.y_remove_layer_menu", icon='ZOOMOUT', text='')

        else: 
            if is_bl_newer_than(2, 80):
                c = rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
            else: c = rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

            c.remove_children = False

        if is_top_member(layer):
            c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_UP')
            c.direction = 'UP'
            c.move_out = True
        else:
            upper_idx, upper_layer = get_upper_neighbor(layer)

            if upper_layer and (upper_layer.type == 'GROUP' or upper_layer.parent_idx != layer.parent_idx):
                c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_UP')
                c.direction = 'UP'
                c.move_out = False
            else: 
                c = rcol.operator("node.y_move_layer", text='', icon='TRIA_UP')
                c.direction = 'UP'

        if is_bottom_member(layer):
            c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_DOWN')
            c.direction = 'DOWN'
            c.move_out = True
        else:
            lower_idx, lower_layer = get_lower_neighbor(layer)

            if lower_layer and (lower_layer.type == 'GROUP' and lower_layer.parent_idx == layer.parent_idx):
                c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'
                c.move_out = False
            else: 
                c = rcol.operator("node.y_move_layer", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'

    else:

        if is_bl_newer_than(2, 80):
            rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
        else: rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

        rcol.operator("node.y_move_layer", text='', icon='TRIA_UP').direction = 'UP'
        rcol.operator("node.y_move_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'

    rcol.menu("NODE_MT_y_layer_list_special_menu", text='', icon='DOWNARROW_HLT')

    if layer:
        layer_tree = get_tree(layer)
        source_tree = get_source_tree(layer)

        col = box.column()
        col.active = layer.enable and not is_parent_hidden(layer)

        linear = source_tree.nodes.get(layer.linear)

        # Get active vcol
        if mask_vcol: active_vcol = mask_vcol
        elif override_vcol: active_vcol = override_vcol
        elif vcol: active_vcol = vcol
        else: active_vcol = None

        # Check if any images aren't using proper linear pipelines
        if any_linear_images_problem(yp):
            col.alert = True
            col.operator('node.y_use_linear_color_space', text='Refresh Linear Color Space', icon='ERROR')
            col.alert = False

        # Check if AO is enabled or not
        scene = bpy.context.scene
        if is_bl_newer_than(2, 93) and not scene.eevee.use_gtao and scene.render.engine != 'BLENDER_EEVEE_NEXT':
            edge_detect_found = False
            for l in yp.layers:
                for m in l.masks:
                    if m.type == 'EDGE_DETECT' and get_mask_enabled(m, l):
                        edge_detect_found = True
                        break
            if edge_detect_found:
                col.alert = True
                col.operator('node.y_fix_edge_detect_ao', text='Fix EEVEE Edge Detect AO', icon='ERROR')
                col.alert = False

        if obj.type == 'MESH' and colorid_vcol:

            if colorid_vcol != get_active_vertex_color(obj):
                col.alert = True
                col.operator('mesh.y_set_active_vcol', text='Fix Active Vcol Mismatch!', icon='ERROR').vcol_name = colorid_vcol.name
                col.alert = False

            elif obj.mode == 'EDIT':

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
                col.alert = True
                col.operator('mesh.y_set_active_vcol', text='Fix Active Vcol Mismatch!', icon='ERROR').vcol_name = active_vcol.name
                col.alert = False

            elif obj.mode == 'EDIT':
                ve = context.scene.ve_edit

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

            elif obj.mode == 'VERTEX_PAINT' and is_bl_newer_than(2, 92) and ((layer.type == 'VCOL' and not mask_vcol) or (mask_vcol and mask.source_input == 'ALPHA')) and not override_vcol:
                bbox = col.box()
                row = bbox.row(align=True)
                row.operator('paint.y_toggle_eraser', text='Toggle Eraser')

            elif obj.mode == 'SCULPT' and is_bl_newer_than(3, 2) and ((layer.type == 'VCOL' and not mask_vcol) or (mask_vcol and mask.source_input == 'ALPHA')) and not override_vcol:

                bbox = col.box()
                row = bbox.row(align=True)
                row.operator('paint.y_toggle_eraser', text='Toggle Eraser')

        in_texture_paint_mode = obj.mode == 'TEXTURE_PAINT' or (
                is_bl_newer_than(4, 4) and obj.mode == 'SCULPT' and 
                # Assuming sculpt texture paint is already stable or enabled in experimental feature
                (not hasattr(context.preferences.experimental, 'use_sculpt_texture_paint') or context.preferences.experimental.use_sculpt_texture_paint)
                )

        if obj.type == 'MESH' and in_texture_paint_mode and ((layer.type == 'IMAGE' and not mask_image) or (mask_image and mask.source_input == 'ALPHA')) and not override_image:
            bbox = col.box()
            row = bbox.row(align=True)
            row.operator('paint.y_toggle_eraser', text='Toggle Eraser')

        ve = context.scene.ve_edit
        if in_texture_paint_mode:
            brush = context.tool_settings.image_paint.brush if obj.mode == 'TEXTURE_PAINT' else context.tool_settings.sculpt.brush
            if ((mask_image and mask.source_input == 'RGB') or override_image) and brush.name == eraser_names[obj.mode]:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        elif obj.mode == 'VERTEX_PAINT' and is_bl_newer_than(2, 80): 
            brush = context.tool_settings.vertex_paint.brush
            if mask_vcol and mask.source_input == 'RGB' and brush.name == eraser_names[obj.mode]:
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('paint.y_toggle_eraser', text='Disable Eraser')
                row.alert = False

        elif obj.mode == 'SCULPT' and is_bl_newer_than(3, 2): 
            brush = context.tool_settings.sculpt.brush
            if mask_vcol and mask.source_input == 'RGB' and brush.name == eraser_names[obj.mode]:
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
                    row.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')
                elif obj.data.uv_layers.active.name == TEMP_UV:
                    bbox = col.box()
                    row = bbox.row(align=True)
                    row.alert = True
                    row.operator('node.y_back_to_original_uv', icon='EDITMODE_HLT', text='Edit Original UV')
        else:
            if yp.need_temp_uv_refresh or is_active_uv_map_missmatch_active_entity(obj, layer):
                bbox = col.box()
                row = bbox.row(align=True)
                row.alert = True
                row.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

        if is_a_mesh and is_bl_newer_than(3, 2):
            height_layer_ch = get_height_channel(layer)
            if height_layer_ch and height_layer_ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
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

        # Source
        draw_layer_source(context, col, layer, layer_tree, source, image, vcol, is_a_mesh)

        # Channels
        draw_layer_channels(context, col, layer, layer_tree, image)

        # Masks
        draw_layer_masks(context, col, layer)

def main_draw(self, context):

    wm = context.window_manager
    area = context.area
    scene = context.scene
    obj = context.object
    mat = obj.active_material
    #slot = context.material_slot
    #space = context.space_data

    # Timer
    if wm.yptimer.time != '':
        print('INFO: Scene is updated in', '{:0.2f}'.format((time.time() - float(wm.yptimer.time)) * 1000), 'ms!')
        wm.yptimer.time = ''

    # Update ui props first
    update_yp_ui()

    node = get_active_ypaint_node()
    ypui = wm.ypui

    layout = self.layout

    #layout.operator("node.y_debug_mesh", icon='MESH_DATA')
    #layout.operator("node.y_test_ray", icon='MESH_DATA')

    from . import addon_updater_ops

    updater = addon_updater_ops.updater

    if not updater.auto_reload_post_update:
        saved_state = updater.json
        if "just_updated" in saved_state and saved_state["just_updated"]:
            row_update = layout.row()
            row_update.alert = True
            row_update.operator("wm.quit_blender",
                         text="Restart blender to complete update",
                         icon="ERROR")
            return
        
    if updater.update_ready and not ypui.hide_update:
        row_update = layout.row()
        row_update.alert = True
        if updater.using_development_build:
            update_now_txt = "Update to latest commit on '{}' branch".format(updater.current_branch)
            row_update.operator(addon_updater_ops.AddonUpdaterUpdateNow.bl_idname, text=update_now_txt)
        else:
            row_update.operator(addon_updater_ops.AddonUpdaterUpdateNow.bl_idname,
                        text="Update now to " + str(updater.update_version))
        row_update.alert = False

        row_update.operator(addon_updater_ops.UpdaterPendingUpdate.bl_idname, icon="X", text="")

    icon = 'TRIA_DOWN' if ypui.show_object else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_object', emboss=False, text='', icon=icon)
    text_object = pgettext_iface('Object: ')
    if obj:
        row.label(text=text_object + obj.name)
    else: row.label(text=text_object + '-')

    if not is_bl_newer_than(2, 80):
        row.menu("NODE_MT_ypaint_about_menu", text='', icon='INFO')
    else: row.popover("NODE_PT_ypaint_about_popover", text='', icon='INFO')

    if ypui.show_object:
        box = layout.box()
        col = box.column()
        col.prop(obj, 'pass_index')
        #row = box.row()

    # HACK: Create split layout to load all icons (Only for Blender 3.2+)
    if is_bl_newer_than(3, 2) and not wm.ypprops.all_icons_loaded:
        split = split_layout(layout, 1.0)
        row = split.row(align=True)
    else:
        row = layout.row(align=True)

    icon = 'TRIA_DOWN' if ypui.show_materials else 'TRIA_RIGHT'
    row.prop(ypui, 'show_materials', emboss=False, text='', icon=icon)
    text_material = pgettext_iface('Material: ')
    if mat:
        row.label(text=text_material + mat.name)
    else: row.label(text=text_material + '-')

    # HACK: Load all icons earlier so no missing icons possible (Only for Blender 3.2+)
    if is_bl_newer_than(3, 2) and not wm.ypprops.all_icons_loaded:
        wm.ypprops.all_icons_loaded = True
        row.label(text='', icon='BLANK1')
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

    if ypui.show_materials:
        is_sortable = len(obj.material_slots) > 1
        rows = 2
        if (is_sortable):
            rows = 4
        box = layout.box()
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

        box.template_ID(obj, "active_material", new="material.new")

    if not node:
        layout.label(text="No active " + get_addon_title() + " node!", icon='ERROR')
        layout.operator("node.y_quick_ypaint_node_setup", icon_value=lib.get_icon('nodetree'))

        return

    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp

    if version_tuple(yp.version) < version_tuple(get_current_version_str()):
        col = layout.column()
        col.alert = True
        col.label(text=group_tree.name + ' (' + yp.version + ')', icon_value=lib.get_icon('nodetree'))
        col.operator("node.y_update_yp_trees", text='Update node to version ' + get_current_version_str(), icon='ERROR')
        return

    #layout.label(text='Active: ' + node.node_tree.name, icon_value=lib.get_icon('nodetree'))
    row = layout.row(align=True)
    row.label(text='', icon_value=lib.get_icon('nodetree'))
    #row.label(text='Active: ' + node.node_tree.name)
    row.label(text=node.node_tree.name)
    #row.prop(node.node_tree, 'name', text='')

    icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
    row.menu("NODE_MT_ypaint_special_menu", text='', icon=icon)

    # Check for baked node
    baked_found = False
    for ch in yp.channels:
        baked = nodes.get(ch.baked)
        if baked: 
            baked_found = True

    # Channels
    icon = 'TRIA_DOWN' if ypui.show_channels else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_channels', emboss=False, text='', icon=icon)
    row.label(text='Channels')

    if ypui.show_channels:
        draw_root_channels_ui(context, layout, node)

    # Layers
    icon = 'TRIA_DOWN' if ypui.show_layers else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_layers', emboss=False, text='', icon=icon)
    row.label(text='Layers')

    height_root_ch = get_root_height_channel(yp)

    scenario_1 = (is_tangent_sign_hacks_needed(yp) and area.type == 'VIEW_3D' and 
            area.spaces[0].shading.type == 'RENDERED' and scene.render.engine == 'CYCLES')

    if scenario_1:
        row.operator('node.y_refresh_tangent_sign_vcol', icon='FILE_REFRESH', text='Tangent')

    if (baked_found or yp.use_baked) and not group_tree.users > 1:
        row.prop(yp, 'use_baked', toggle=True, text='Use Baked')
        row.prop(yp, 'enable_baked_outside', toggle=True, text='', icon='NODETREE')

    if ypui.show_layers :
        if yp.sculpt_mode:

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
            draw_layers_ui(context, layout, node)

    # Custom Bake Targets
    icon = 'TRIA_DOWN' if ypui.show_bake_targets else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_bake_targets', emboss=False, text='', icon=icon)
    row.label(text='Custom Bake Targets')

    if ypui.show_bake_targets:
        draw_bake_targets_ui(context, layout, node)

    # Stats
    icon = 'TRIA_DOWN' if ypui.show_stats else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_stats', emboss=False, text='', icon=icon)
    row.label(text='Stats')

    if ypui.show_stats:

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
            if layer.type == 'IMAGE':
                src = get_layer_source(layer)
                if src.image and src.image not in images:
                    images.append(src.image)
            elif layer.type == 'VCOL':
                src = get_layer_source(layer)
                vcol_name = get_source_vcol_name(src)
                if vcol_name != '' and vcol_name not in vcols:
                    vcols.append(vcol_name)
            elif layer.type in {'BRICK', 'CHECKER', 'GRADIENT', 'MAGIC', 'MUSGRAVE', 'NOISE', 'VORONOI', 'WAVE'}:
                num_gen_texs += 1

            for ch in layer.channels:
                if ch.enable:
                    if ch.override:
                        if ch.override_type == 'IMAGE':
                            #src = get_layer_source(layer)
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
                            ltree = get_tree(layer)
                            src = ltree.nodes.get(ch.source_1)
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
                if mask.use_baked:
                    mask_tree = get_mask_tree(mask)
                    src = mask_tree.nodes.get(mask.baked_source)
                    if src.image and src.image not in images:
                        images.append(src.image)
                elif mask.type == 'IMAGE':
                    src = get_mask_source(mask)
                    if src.image and src.image not in images:
                        images.append(src.image)
                elif mask.type == 'VCOL':
                    src = get_mask_source(mask)
                    vcol_name = get_source_vcol_name(src)
                    if vcol_name != '' and vcol_name not in vcols:
                        vcols.append(vcol_name)
                elif mask.type in {'BRICK', 'CHECKER', 'GRADIENT', 'MAGIC', 'MUSGRAVE', 'NOISE', 'VORONOI', 'WAVE'}:
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

        box = layout.box()
        col = box.column()
        #col = layout.column(align=True)
        col.label(text=pgettext_iface('Number of Images: ') + str(len(images)), icon_value=lib.get_icon('image'))
        #col.label(text='Number of Vertex Colors: ' + str(len(vcols)), icon='GROUP_VCOL')
        col.label(text=pgettext_iface('Number of Vertex Colors: ') + str(len(vcols)), icon_value=lib.get_icon('vertex_color'))
        #col.label(text='Number of Generated Textures: ' + str(num_gen_texs), icon='TEXTURE')
        col.label(text=pgettext_iface('Number of Generated Textures: ') + str(num_gen_texs), icon_value=lib.get_icon('texture'))
        col.label(text=pgettext_iface('Number of Color Ramps: ') + str(num_ramps), icon_value=lib.get_icon('modifier'))
        col.label(text=pgettext_iface('Number of RGB Curves: ') + str(num_curves), icon_value=lib.get_icon('modifier'))

        #col.operator('node.y_new_image_atlas_segment_test', icon_value=lib.get_icon('image'))
        #col.operator('node.y_new_udim_atlas_segment_test', icon_value=lib.get_icon('image'))
        #col.operator('node.y_uv_transform_test', icon_value=lib.get_icon('uv'))

class NODE_PT_YPaint(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = get_addon_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'TOOLS'
    #bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class NODE_PT_YPaintUI(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = get_addon_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'UI'
    bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_YPaint_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = get_addon_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_region_type = 'TOOLS'
    bl_category = get_addon_title()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_YPaint_ui(bpy.types.Panel):
    bl_label = get_addon_title() + " " + get_current_version_str() + get_alpha_suffix()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    #bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}

    def draw(self, context):
        main_draw(self, context)

def is_output_unconnected(node, index, root_ch=None):
    yp = node.node_tree.yp
    unconnected = len(node.outputs[index].links) == 0 and not (yp.use_baked and yp.enable_baked_outside)
    if root_ch and root_ch.type == 'NORMAL':
        unconnected &= not (not is_bl_newer_than(2, 80) and yp.use_baked and root_ch.subdiv_adaptive)
    return unconnected

def is_height_input_connected_but_has_no_start_process(node, root_ch):
    yp = node.node_tree.yp
    if root_ch.type != 'NORMAL': return False
    socket = node.inputs.get(root_ch.name + io_suffix['HEIGHT'])
    connected = len(socket.links) > 0 if socket else False
    start_bump_process = node.node_tree.nodes.get(root_ch.start_bump_process)
    if connected and not start_bump_process:
        return True
    return False

def is_height_input_unconnected_but_has_start_process(node, root_ch):
    yp = node.node_tree.yp
    if root_ch.type != 'NORMAL': return False
    socket = node.inputs.get(root_ch.name + io_suffix['HEIGHT'])
    unconnected = len(socket.links) == 0 if socket else True
    start_bump_process = node.node_tree.nodes.get(root_ch.start_bump_process)
    if unconnected and start_bump_process:
        return True
    return False

class NODE_UL_YPaint_bake_targets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        tree = item.id_data
        image_node = tree.nodes.get(item.image_node)
        image = image_node.image if image_node else None

        row = layout.row()

        if image:
            row.prop(image, 'name', text='', emboss=False, icon_value=lib.get_icon('bake'))

            # Asterisk icon to indicate dirty image
            if image.is_dirty:
                row.label(text='', icon_value=lib.get_icon('asterisk'))

            # Indicate packed image
            if image.packed_file:
                row.label(text='', icon='PACKAGE')
            
        else: row.prop(item, 'name', text='', emboss=False, icon_value=lib.get_icon('bake'))

class NODE_UL_YPaint_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_ypaint_node()
        inputs = group_node.inputs
        outputs = group_node.outputs
        yp = group_node.node_tree.yp

        input_index = item.io_index
        output_index = get_output_index(item)

        row = layout.row()

        icon_value = lib.get_icon(lib.channel_custom_icon_dict[item.type])
        row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)

        if not yp.use_baked or item.no_layer_using:
            if item.type == 'RGB':
                row = row.row(align=True)

            if len(inputs[input_index].links) == 0:
                if item.type == 'VALUE':
                    row.prop(inputs[input_index], 'default_value', text='') #, emboss=False)
                elif item.type == 'RGB':
                    row.prop(inputs[input_index], 'default_value', text='', icon='COLOR')
            else:
                row.label(text='', icon='LINKED')

            if is_output_unconnected(group_node, output_index, item):
                row.label(text='', icon='ERROR')

            if item.type=='RGB' and item.enable_alpha:
                if len(inputs[input_index+1].links) == 0:
                    row.prop(inputs[input_index+1], 'default_value', text='')
                else: row.label(text='', icon='LINKED')

                if is_output_unconnected(group_node, output_index+1, item):
                    row.label(text='', icon='ERROR')

class NODE_UL_YPaint_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_tree = item.id_data
        yp = group_tree.yp
        nodes = group_tree.nodes
        layer = item
        layer_tree = get_tree(layer)
        obj = context.object
        ypup = get_user_preferences()

        is_hidden = not is_parent_hidden(layer)

        master = layout.row(align=True)
        row = master.row(align=True)

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

        all_overrides = []
        selectable_overrides = []
        active_override = None
        override_idx = 0
        for c in layer.channels:
            #if not c.enable: continue
            if (c.override and c.override_type != 'DEFAULT') or (c.override_1 and c.override_1_type != 'DEFAULT'):
                if c.enable: selectable_overrides.append(c)
                all_overrides.append(c)
                if c.active_edit or c.active_edit_1:
                    active_override = c
                if c.active_edit_1:
                    override_idx = 1

        # Try to get image masks
        all_masks = []
        selectable_masks = []
        active_mask = None
        for m in layer.masks:
            #if m.type in {'IMAGE', 'VCOL'}:
            if m.enable: selectable_masks.append(m)
            all_masks.append(m)
            if m.active_edit:
                active_mask = m
                active_override = m

        if layer.parent_idx != -1:
            depth = get_layer_depth(layer)
            for i in range(depth):
                row.label(text='', icon='BLANK1')

        # Image icon
        if len(selectable_masks) == 0 and len(selectable_overrides) == 0:
            row = master.row(align=True)
            row.active = is_hidden
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
            elif layer.type == 'COLOR': 
                row.prop(layer, 'name', text='', emboss=False, icon='COLOR')
            elif layer.type == 'BACKGROUND': row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('background'))
            elif layer.type == 'GROUP': row.prop(layer, 'name', text='', emboss=False, icon_value=lib.get_icon('group'))
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
                    else: row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('image'))
                elif layer.type == 'VCOL': 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
                elif layer.type == 'COLOR': 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon='COLOR')
                elif layer.type == 'HEMI': 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('hemi'))
                elif layer.type == 'BACKGROUND': 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('background'))
                elif layer.type == 'GROUP': 
                    row.prop(active_override, ae_prop, text='', emboss=False, icon_value=lib.get_icon('group'))
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
                elif layer.type == 'HEMI': 
                    row.label(text='', icon_value=lib.get_icon('hemi'))
                elif layer.type == 'BACKGROUND': 
                    row.label(text='', icon_value=lib.get_icon('background'))
                elif layer.type == 'GROUP': 
                    row.label(text='', icon_value=lib.get_icon('group'))
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
                        else: row.label(text='', icon_value=lib.get_icon('image'))
                    elif c.override_type == 'VCOL':
                        #active_override_vcol = c
                        row.label(text='', icon_value=lib.get_icon('vertex_color'))
                    else:
                        row.label(text='', icon_value=lib.get_icon('texture'))
                else:
                    if c.override_type == 'IMAGE':
                        src = get_channel_source(c, layer)
                        if src: 
                            if ypup.use_image_preview and src.image.preview: 
                                #if not src.image.preview: src.image.preview_ensure()
                                row.prop(c, 'active_edit', text='', emboss=False, icon_value=src.image.preview.icon_id)
                            else: row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('image'))
                    elif c.override_type == 'VCOL':
                        row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
                    else:
                        row.prop(c, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('texture'))

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
                        else: row.label(text='', icon_value=lib.get_icon('image'))
                else:
                    if c.override_1_type == 'IMAGE':
                        src = get_channel_source_1(c, layer)
                        if src: 
                            if ypup.use_image_preview and src.image.preview: 
                                #if not src.image.preview: src.image.preview_ensure()
                                row.prop(c, 'active_edit_1', text='', emboss=False, icon_value=src.image.preview.icon_id)
                            else: row.prop(c, 'active_edit_1', text='', emboss=False, icon_value=lib.get_icon('image'))

        # Mask icons
        active_mask_image = None
        active_vcol_mask = None
        mask = None
        for m in selectable_masks:
            mask_tree = get_mask_tree(m)
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
                        if m.source_input == 'ALPHA':
                            row.label(text='', icon_value=lib.get_icon('alpha_image'))
                        else: row.label(text='', icon_value=lib.get_icon('image'))
                elif m.type == 'VCOL':
                    active_vcol_mask = m
                    if m.source_input == 'ALPHA':
                        row.label(text='', icon_value=lib.get_icon('vertex_color_alpha'))
                    else: row.label(text='', icon_value=lib.get_icon('vertex_color'))
                elif m.type == 'HEMI':
                    row.label(text='', icon_value=lib.get_icon('hemi'))
                elif m.type == 'OBJECT_INDEX':
                    row.label(text='', icon_value=lib.get_icon('object_index'))
                elif m.type == 'EDGE_DETECT':
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
                        if m.source_input == 'ALPHA':
                            row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('alpha_image'))
                        else: row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('image'))
                elif m.type == 'VCOL':
                    if m.source_input == 'ALPHA':
                        row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('vertex_color_alpha'))
                    else: row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('vertex_color'))
                elif m.type == 'HEMI':
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('hemi'))
                elif m.type == 'OBJECT_INDEX':
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=lib.get_icon('object_index'))
                elif m.type == 'EDGE_DETECT':
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
            row.active = is_hidden
            if override_ch:
                if active_override_image:
                    if active_override_image.yia.is_image_atlas or active_override_image.yua.is_udim_atlas:
                        #row.label(text='Image Atlas Override')
                        row.label(text=override_image.name)
                    else: row.prop(active_override_image, 'name', text='', emboss=False)
                elif override_ch.override_type == 'VCOL':
                    #row.label(text='Vertex Color Override')
                    row.prop(override_ch, 'override_vcol_name', text='', emboss=False)
                else:
                    row.label(text='Channel Override')
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

        if layer.type == 'COLOR' and layer.color_shortcut:
            src = get_layer_source(layer, layer_tree)
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
            #row.active = is_hidden
            row.active = layer.enable_masks
            if layer.enable_masks:
                icon_value = lib.get_icon("mask")
            else: icon_value = lib.get_icon("disabled_mask")
            row.prop(layer, 'enable_masks', emboss=False, text='', icon_value=icon_value)
            #row.prop(layer, 'enable_masks', emboss=False, text='', icon='MOD_MASK')

        # Layer intensity
        row = master.row()
        row.scale_x = 0.4
        if is_bl_newer_than(3):
            row.emboss = 'NONE_OR_STATUS'
        elif is_bl_newer_than(2, 92):
            row.emboss = 'UI_EMBOSS_NONE_OR_STATUS'
        elif is_bl_newer_than(2, 80): row.emboss = 'NONE'

        if is_bl_newer_than(2, 80):
            draw_input_prop(row, layer, 'intensity_value')
        else: draw_input_prop(row, layer, 'intensity_value', emboss=False)          

        # Layer visibility
        row = master.row()
        row.active = is_hidden
        if not is_bl_newer_than(2, 80):
            if layer.enable: eye_icon = 'RESTRICT_VIEW_OFF'
            else: eye_icon = 'RESTRICT_VIEW_ON'
        else:
            if layer.enable: eye_icon = 'HIDE_OFF'
            else: eye_icon = 'HIDE_ON'
        row.prop(layer, 'enable', emboss=False, text='', icon=eye_icon)

class YPAssetBrowserMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_asset_browser_menu"
    bl_label = get_addon_title() + " Asset Browser Menu"
    bl_description = get_addon_title() + " asset browser menu"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        obj = context.object
        op = self.layout.operator("node.y_open_images_from_material_to_single_layer", icon_value=lib.get_icon('image'), text='Open Material Images to Layer')
        op.mat_name = context.mat_asset.name if hasattr(context, 'mat_asset') else ''
        op.asset_library_path = context.mat_asset.full_library_path if hasattr(context, 'mat_asset') else ''

        if obj.type == 'MESH':
            op.texcoord_type = 'UV'
            active_uv_name = get_active_render_uv(obj)
            op.uv_map = active_uv_name
        else:
            op.texcoord_type = 'Generated'

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
            op = self.layout.operator("node.y_open_image_to_layer", icon_value=lib.get_icon('image'), text="Open Image as Layer")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'UV'
            op = self.layout.operator("node.y_open_image_as_mask", icon_value=lib.get_icon('image'), text="Open Image as Mask")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'UV'

            self.layout.separator()

            op = self.layout.operator("node.y_open_image_to_layer", icon_value=lib.get_icon('image'), text="Open Image as Decal Layer")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'Decal'
            op = self.layout.operator("node.y_open_image_as_mask", icon_value=lib.get_icon('image'), text="Open Image as Decal Mask")
            op.file_browser_filepath = filepath
            op.texcoord_type = 'Decal'

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
    col.label(text=get_addon_title() + ' is created by:')
    col.operator('wm.url_open', text='ucupumar', icon='ARMATURE_DATA').url = 'https://github.com/sponsors/ucupumar'
    col.operator('wm.url_open', text='arsa', icon='ARMATURE_DATA').url = 'https://sites.google.com/view/arsanagara'
    col.operator('wm.url_open', text='swifterik', icon='ARMATURE_DATA').url = 'https://jblaha.art/'
    col.operator('wm.url_open', text='rifai', icon='ARMATURE_DATA').url = 'https://github.com/rifai'
    col.operator('wm.url_open', text='morirain', icon='ARMATURE_DATA').url = 'https://github.com/morirain'
    col.operator('wm.url_open', text='kareemov03', icon='ARMATURE_DATA').url = 'https://www.artstation.com/kareem'
    col.operator('wm.url_open', text='passivestar', icon='ARMATURE_DATA').url = 'https://github.com/passivestar'
    col.separator()

    col.label(text='Documentation:')
    col.operator('wm.url_open', text=get_addon_title()+' Wiki', icon='TEXT').url = 'https://ucupumar.github.io/ucupaint-wiki/'

    from . import addon_updater_ops
    updater = addon_updater_ops.updater

    col.separator()
    row = col.row()            
    if updater.using_development_build:
        if addon_updater_ops.updater.legacy_blender:
            row.label(text="Branch: Master (Blender 2.7x)")
        else:
            row.label(text="Branch: "+updater.current_branch)
    else:
        row.label(text="Branch: Stable "+str(updater.current_version))
    if addon_updater_ops.updater.legacy_blender:
        col.operator(addon_updater_ops.AddonUpdaterUpdateTarget.bl_idname, text="Change Branch", icon="FILE_SCRIPT")
    else:
        icon = 'PREFERENCES' if is_bl_newer_than(2, 80) else 'SCRIPTWIN'
        row.menu(addon_updater_ops.UpdaterSettingMenu.bl_idname, text='', icon=icon)

    if updater.async_checking:
        col.enabled = False
        col.operator(addon_updater_ops.AddonUpdaterUpdateNow.bl_idname, text="Checking...")
    elif updater.update_ready:
        col.alert = True
        if updater.using_development_build:
            update_now_txt = "Update to latest commit on '{}' branch".format(
                updater.current_branch)
            col.operator(addon_updater_ops.AddonUpdaterUpdateNow.bl_idname, text=update_now_txt)
            
        else:
            col.operator(addon_updater_ops.AddonUpdaterUpdateNow.bl_idname,
                        text="Update now to " + str(updater.update_version))
    elif is_online() or updater.current_branch != None:
        col.operator(addon_updater_ops.RefreshBranchesReleasesNow.bl_idname, text="Check for update", icon="FILE_REFRESH")
        col.label(text="Ucupaint is up to date")

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

        col.operator('node.y_bake_channels', text='Bake All Channels', icon_value=lib.get_icon('bake')).only_active_channel = False
        col.operator('node.y_rename_ypaint_tree', text='Rename Tree', icon_value=lib.get_icon('rename'))

        col.separator()

        col.operator('node.y_remove_yp_node', icon_value=lib.get_icon('close'))

        col.separator()

        col.operator('node.y_clean_yp_caches', icon_value=lib.get_icon('clean'))

        col.separator()

        op = col.operator('node.y_duplicate_yp_nodes', text='Duplicate Material and ' + get_addon_title() + ' nodes', icon='COPY_ID')
        op.duplicate_material = True

        col.separator()

        col.label(text='Active Tree:', icon_value=lib.get_icon('nodetree'))
        for n in get_list_of_ypaint_nodes(mat):
            if n.name == node.name:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            #row = col.row()
            col.operator('node.y_change_active_ypaint_node', text=n.node_tree.name, icon=icon).name = n.name

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

class YBakeTargetMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_bake_target_menu"
    bl_description = 'Bake Target Menu'
    bl_label = "Bake Target Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):

        col = self.layout.column()
        col.operator('node.y_pack_image', icon='PACKAGE')
        col.operator('node.y_save_image', icon='FILE_TICK')

        if context.image:
            if context.image.packed_file:
                op = col.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE')
                op.unpack = True
                op.copy = False
            else: 
                op = col.operator('node.y_save_as_image', text='Save As Image')
                op.unpack = False
                op.copy = False
            col.operator('node.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

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

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['VALUE'])
        col.operator("node.y_add_new_ypaint_channel", icon_value=icon_value, text='Value').type = 'VALUE'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['RGB'])
        col.operator("node.y_add_new_ypaint_channel", icon_value=icon_value, text='RGB').type = 'RGB'

        icon_value = lib.get_icon(lib.channel_custom_icon_dict['NORMAL'])
        col.operator("node.y_add_new_ypaint_channel", icon_value=icon_value, text='Normal').type = 'NORMAL'

class YNewLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_layer_menu"
    bl_description = 'Add New Layer'
    bl_label = "New Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()

        row = self.layout.row()
        col = row.column()
        #col = self.layout.column(align=True)
        #col.context_pointer_set('group_node', context.group_node)
        #col.label(text='Image:')
        col.operator("node.y_new_layer", text='New Image', icon_value=lib.get_icon('image')).type = 'IMAGE'

        #col.separator()

        op = col.operator("node.y_open_image_to_layer", text='Open Image...')
        op.texcoord_type = 'UV'
        op.file_browser_filepath = ''
        col.operator("node.y_open_available_data_to_layer", text='Open Available Image').type = 'IMAGE'

        col.operator("node.y_open_images_to_single_layer", text='Open Images to Single Layer...')
        col.operator("node.y_open_images_from_material_to_single_layer", text='Open Images from Material').asset_library_path = ''

        # NOTE: Dedicated menu for opening images to single layer is kinda hard to see, so it's probably better be hidden for now
        #col.menu("NODE_MT_y_open_images_to_single_layer_menu", text='Open Images to Single Layer')

        col.separator()

        col.operator("node.y_new_layer", icon_value=lib.get_icon('group'), text='Layer Group').type = 'GROUP'
        col.separator()

        #col.label(text='Vertex Color:')
        #col.operator("node.y_new_layer", icon='GROUP_VCOL', text='New Vertex Color').type = 'VCOL'
        col.operator("node.y_new_layer", icon_value=lib.get_icon('vertex_color'), text='New Vertex Color').type = 'VCOL'
        col.operator("node.y_open_available_data_to_layer", text='Open Available Vertex Color').type = 'VCOL'
        col.separator()

        #col.menu("NODE_MT_y_new_solid_color_layer_menu", text='Solid Color', icon_value=lib.get_icon('color'))

        icon_value = lib.get_icon("color")
        c = col.operator("node.y_new_layer", icon_value=icon_value, text='Solid Color')
        c.type = 'COLOR'
        c.add_mask = False

        c = col.operator("node.y_new_layer", text='Solid Color w/ Image Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        c = col.operator("node.y_new_layer", text='Solid Color w/ Vertex Color Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'VCOL'

        c = col.operator("node.y_new_layer", text='Solid Color w/ Color ID Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'COLOR_ID'

        if is_bl_newer_than(2, 93):
            c = col.operator("node.y_new_layer", text='Solid Color w/ Edge Detect Mask')
            c.type = 'COLOR'
            c.add_mask = True
            c.mask_type = 'EDGE_DETECT'

        col.separator()

        #col.label(text='Background:')
        c = col.operator("node.y_new_layer", icon_value=lib.get_icon('background'), text='Background w/ Image Mask')
        c.type = 'BACKGROUND'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        #if is_bl_newer_than(2, 80):
        #    c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')
        #else: c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')
        c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')

        c.type = 'BACKGROUND'
        c.add_mask = True
        c.mask_type = 'VCOL'

        if is_bl_newer_than(3, 2):
            col.separator()
            col.operator("node.y_new_vdm_layer", text='Vector Displacement Image', icon='SCULPTMODE_HLT')

        col = row.column()
        col.label(text='Generated Layer:')
        #col.operator("node.y_new_layer", icon='TEXTURE', text='Brick').type = 'BRICK'
        col.operator("node.y_new_layer", icon_value=lib.get_icon('texture'), text='Brick').type = 'BRICK'
        col.operator("node.y_new_layer", text='Checker').type = 'CHECKER'
        col.operator("node.y_new_layer", text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_layer", text='Magic').type = 'MAGIC'
        if not is_bl_newer_than(4, 1): col.operator("node.y_new_layer", text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_layer", text='Noise').type = 'NOISE'
        col.operator("node.y_new_layer", text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_layer", text='Wave').type = 'WAVE'

        col.separator()
        col.operator("node.y_new_layer", icon_value=lib.get_icon('hemi'), text='Fake Lighting').type = 'HEMI'

        col = row.column()
        col.label(text='Bake as Layer:')
        c = col.operator("node.y_bake_to_layer", icon_value=lib.get_icon('bake'), text='Ambient Occlusion')
        c.type = 'AO'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Pointiness')
        c.type = 'POINTINESS'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Cavity')
        c.type = 'CAVITY'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Dust')
        c.type = 'DUST'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Paint Base')
        c.type = 'PAINT_BASE'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Bevel Normal')
        c.type = 'BEVEL_NORMAL'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        c = col.operator("node.y_bake_to_layer", text='Bevel Grayscale')
        c.type = 'BEVEL_MASK'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        if is_bl_newer_than(2, 80):
            col.separator()

            c = col.operator("node.y_bake_to_layer", text='Multires Normal')
            c.type = 'MULTIRES_NORMAL'
            c.target_type = 'LAYER'
            c.overwrite_current = False

            c = col.operator("node.y_bake_to_layer", text='Multires Displacement')
            c.type = 'MULTIRES_DISPLACEMENT'
            c.target_type = 'LAYER'
            c.overwrite_current = False

        if is_bl_newer_than(2, 77):
            col.separator()

            c = col.operator("node.y_bake_to_layer", text='Other Objects Emission')
            c.type = 'OTHER_OBJECT_EMISSION'
            c.target_type = 'LAYER'
            c.overwrite_current = False

            c = col.operator("node.y_bake_to_layer", text='Other Objects Normal')
            c.type = 'OTHER_OBJECT_NORMAL'
            c.target_type = 'LAYER'
            c.overwrite_current = False

            c = col.operator("node.y_bake_to_layer", text='Other Objects Channels')
            c.type = 'OTHER_OBJECT_CHANNELS'
            c.target_type = 'LAYER'
            c.overwrite_current = False

        col.separator()

        c = col.operator("node.y_bake_to_layer", text='Selected Vertices')
        c.type = 'SELECTED_VERTICES'
        c.target_type = 'LAYER'
        c.overwrite_current = False

        if ypup.show_experimental:
            col.separator()

            c = col.operator("node.y_bake_to_layer", text='Flow')
            c.type = 'FLOW'
            c.target_type = 'LAYER'
            c.overwrite_current = False

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
        #try:
        #    root_ch = yp.channels[yp.active_channel_index]
        row = col.row()
        row.active = not yp.enable_baked_outside
        row.prop(context.root_ch, 'disable_global_baked', text='Disable Baked Image(s)', icon='RESTRICT_RENDER_ON')
        col.separator()
        #except Exception as e: 
        #    print(e)

        col.operator('node.y_pack_image', icon='PACKAGE')
        col.operator('node.y_save_image', icon='FILE_TICK')

        if context.image.packed_file:
            op = col.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE')
            op.unpack = True
            op.copy = False
        else: 
            op = col.operator('node.y_save_as_image', text='Save As Image')
            op.unpack = False
            op.copy = False
        col.operator('node.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

        col.separator()

        icon = 'FILEBROWSER' if is_bl_newer_than(2, 80) else 'FILE_FOLDER'
        col.operator('node.y_save_all_baked_images', text='Save All Baked Images to...', icon=icon).copy = False
        col.operator('node.y_save_all_baked_images', text='Save All Baked Image Copies to...').copy = True

        col.separator()
        col.operator('node.y_delete_baked_channel_images', text='Delete All Baked Images', icon='ERROR')

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
        
        col.operator('node.y_merge_layer', text='Merge Layer Up', icon='TRIA_UP').direction = 'UP'
        col.operator('node.y_merge_layer', text='Merge Layer Down', icon='TRIA_DOWN').direction = 'DOWN'

        col.separator()

        c = col.operator("node.y_duplicate_layer", icon='COPY_ID', text='Duplicate Layer').duplicate_blank = False
        c = col.operator("node.y_duplicate_layer", icon='COPY_ID', text='Duplicate Blank Layer').duplicate_blank = True

        col.separator()

        col.operator('node.y_copy_layer', text='Copy Layer', icon='COPYDOWN').all_layers = False
        col.operator('node.y_copy_layer', text='Copy All Layers', icon='COPYDOWN').all_layers = True
        col.operator('node.y_paste_layer', text='Paste Layer(s)', icon='PASTEDOWN')

        if UDIM.is_udim_supported():
            col.separator()
            col.operator('node.y_refill_udim_tiles', text='Refill UDIM Tiles', icon_value=lib.get_icon('uv'))

        #col.prop(yp, 'layer_preview_mode', text='Layer Only Viewer')

        col = row.column()

        #col.context_pointer_set('space_data', context.screen.areas[6].spaces[0])
        #col.operator('image.save_as', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image:
            col.label(text=pgettext_iface('Active Image: ') + context.image.name, icon_value=lib.get_icon('image'))
        else:
            col.label(text='No active image')

        #col.separator()
        #col.operator('node.y_transfer_layer_uv', text='Transfer Active Layer UV', icon_value=lib.get_icon('uv'))
        #col.operator('node.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon_value=lib.get_icon('uv'))
        
        #if hasattr(context, 'image') and context.image:
        col.separator()
        op = col.operator('node.y_resize_image', text='Resize Image', icon='FULLSCREEN_ENTER')
        if hasattr(context, 'layer'):
            op.layer_name = context.layer.name
        if hasattr(context, 'image'):
            op.image_name = context.image.name
        col.operator("node.y_invert_image", icon='IMAGE_ALPHA')

        col.separator()
        col.operator('node.y_pack_image', icon='PACKAGE')
        col.operator('node.y_save_image', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image.packed_file:
            op = col.operator('node.y_save_as_image', text='Unpack As Image...', icon='UGLYPACKAGE')
            op.unpack = True
            op.copy = False
        else:
            if is_bl_newer_than(2, 80):
                op = col.operator('node.y_save_as_image', text='Save As Image...')
                op.unpack = False
                op.copy = False
            else: 
                op = col.operator('node.y_save_as_image', text='Save As Image...', icon='SAVE_AS')
                op.unpack = False
                op.copy = False
        col.operator('node.y_save_as_image', text='Save an Image Copy...', icon='FILE_TICK').copy = True

        col.separator()
        col.operator("node.y_reload_image", icon='FILE_REFRESH')

        col.separator()

        if hasattr(context, 'image'):
            col.menu("NODE_MT_y_image_convert_menu", text='Convert Image')

        if is_bl_newer_than(2, 80): col.operator('node.y_save_pack_all', text='Save/Pack All Images')
        else: col.operator('node.y_save_pack_all', text='Save/Pack All Images', icon='FILE_TICK')

class YOpenImagesToSingleLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_open_images_to_single_layer_menu"
    bl_label = "Open Images to Single Layer Menu"
    bl_description = "Open Images to Single Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        col.operator("node.y_open_images_to_single_layer", icon='FILE_FOLDER', text='From Directory')
        col.operator("node.y_open_images_from_material_to_single_layer", icon='MATERIAL_DATA', text='From Material').asset_library_path = ''

class YNewSolidColorLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_solid_color_layer_menu"
    bl_label = "New Solid Color Layer Menu"
    bl_description = "New Solid Color layer menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        icon_value = lib.get_icon("color")
        c = col.operator("node.y_new_layer", icon_value=icon_value, text='Solid Color')
        c.type = 'COLOR'
        c.add_mask = False

        c = col.operator("node.y_new_layer", text='Solid Color w/ Image Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        c = col.operator("node.y_new_layer", text='Solid Color w/ Vertex Color Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'VCOL'

        c = col.operator("node.y_new_layer", text='Solid Color w/ Color ID Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'COLOR_ID'

        if is_bl_newer_than(2, 93):
            c = col.operator("node.y_new_layer", text='Solid Color w/ Edge Detect Mask')
            c.type = 'COLOR'
            c.add_mask = True
            c.mask_type = 'EDGE_DETECT'

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

        if UDIM.is_udim_supported():
            #col.separator()
            text = 'Convert to ' + ('Non UDIM ' if context.image.source == 'TILED' else 'UDIM ') + 'Image'
            col.operator("image.y_convert_image_tiled", icon='IMAGE_DATA', text=text)

        col.separator()
        if context.image.yia.is_image_atlas or context.image.yua.is_udim_atlas:
            col.operator("node.y_convert_to_standard_image", icon='IMAGE_DATA', text='Convert to standard Image').all_images = False
            col.operator("node.y_convert_to_standard_image", icon='IMAGE_DATA', text='Convert All Image Atlas to standard Images').all_images = True
        else:
            col.operator("node.y_convert_to_image_atlas", icon='IMAGE_DATA', text='Convert to Image Atlas').all_images = False
            col.operator("node.y_convert_to_image_atlas", icon='IMAGE_DATA', text='Convert All Images to Image Atlas').all_images = True

class YUVSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_uv_special_menu"
    bl_label = "UV Special Menu"
    bl_description = "UV Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()

        col.operator('node.y_transfer_layer_uv', text='Transfer UV', icon_value=lib.get_icon('uv'))
        col.operator('node.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon_value=lib.get_icon('uv'))

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

        op = col.operator('node.y_move_ypaint_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_ypaint_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if is_bl_newer_than(2, 80):
            op = col.operator('node.y_remove_ypaint_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_ypaint_modifier', icon='ZOOMOUT', text='Remove Modifier')

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

        op = col.operator('node.y_move_normalmap_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_normalmap_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if is_bl_newer_than(2, 80):
            op = col.operator('node.y_remove_normalmap_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_normalmap_modifier', icon='ZOOMOUT', text='Remove Modifier')

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

        op = col.operator('node.y_move_mask_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_mask_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()

        if is_bl_newer_than(2, 80):
            op = col.operator('node.y_remove_mask_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_mask_modifier', icon='ZOOMOUT', text='Remove Modifier')

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
            col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='REMOVE').type = 'BUMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='ZOOMOUT').type = 'BUMP'

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
            col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='REMOVE').type = 'RAMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='ZOOMOUT').type = 'RAMP'

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
            col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='REMOVE').type = 'AO'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='ZOOMOUT').type = 'AO'

def new_mask_button(layout, operator, text, lib_icon='', otype='', target_type='', modifier_type='', overwrite_current=None):
    if lib_icon:
        op = layout.operator(operator, icon_value=lib.get_icon(lib_icon), text=text)
    else: op = layout.operator(operator, text=text)

    if otype != '': op.type = otype
    if target_type != '': op.target_type = target_type
    if overwrite_current != None: op.overwrite_current = overwrite_current
    if modifier_type != '': op.modifier_type = modifier_type

    return op

class YAddLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_layer_mask_menu"
    bl_description = 'Add Layer Mask'
    bl_label = "Add Layer Mask"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'layer')
        return get_active_ypaint_node()

    def draw(self, context):
        #print(context.layer)
        layout = self.layout
        row = layout.row()
        col = row.column(align=True)

        if not hasattr(context, 'layer'):
            col.label(text='ERROR: Context has no layer!', icon='ERROR')
            return

        col.context_pointer_set('layer', context.layer)

        col.label(text='Image Mask:')
        new_mask_button(col, 'node.y_new_layer_mask', 'New Image Mask', lib_icon='image', otype='IMAGE')
        op = new_mask_button(col, 'node.y_open_image_as_mask', 'Open Image as Mask...', lib_icon='open_image')
        op.texcoord_type = 'UV'
        op.file_browser_filepath = ''
        new_mask_button(col, 'node.y_open_available_data_as_mask', 'Open Available Image as Mask', lib_icon='open_image', otype='IMAGE')
        col.separator()

        col.label(text='Vertex Color Mask:')
        new_mask_button(col, 'node.y_new_layer_mask', 'New Vertex Color Mask', lib_icon='vertex_color', otype='VCOL')
        new_mask_button(col, 'node.y_open_available_data_as_mask', 'Open Available Vertex Color as Mask', lib_icon='vertex_color', otype='VCOL')

        new_mask_button(col, 'node.y_new_layer_mask', 'Color ID', lib_icon='color', otype='COLOR_ID')

        col = row.column(align=True)
        col.label(text='Generated Mask:')

        new_mask_button(col, 'node.y_new_layer_mask', 'Brick', otype='BRICK', lib_icon='texture')
        new_mask_button(col, 'node.y_new_layer_mask', 'Checker', otype='CHECKER')
        new_mask_button(col, 'node.y_new_layer_mask', 'Gradient', otype='GRADIENT')
        new_mask_button(col, 'node.y_new_layer_mask', 'Magic', otype='MAGIC')
        if not is_bl_newer_than(4, 1): 
            new_mask_button(col, 'node.y_new_layer_mask', 'Musgrave', otype='MUSGRAVE')
        new_mask_button(col, 'node.y_new_layer_mask', 'Noise', otype='NOISE')
        new_mask_button(col, 'node.y_new_layer_mask', 'Voronoi', otype='VORONOI')
        new_mask_button(col, 'node.y_new_layer_mask', 'Wave', otype='WAVE')

        col.separator()
        new_mask_button(col, 'node.y_new_layer_mask', 'Fake Lighting', lib_icon='hemi', otype='HEMI')

        col.separator()
        new_mask_button(col, 'node.y_new_layer_mask', 'Object Index', otype='OBJECT_INDEX', lib_icon='object_index')
        new_mask_button(col, 'node.y_new_layer_mask', 'Backface', otype='BACKFACE', lib_icon='backface')
        if is_bl_newer_than(2, 93):
            new_mask_button(col, 'node.y_new_layer_mask', 'Edge Detect', otype='EDGE_DETECT', lib_icon='edge_detect')

        col = row.column(align=True)
        col.label(text='Bake as Mask:')
        new_mask_button(col, 'node.y_bake_to_layer', 'Ambient Occlusion', lib_icon='bake', otype='AO', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Pointiness', otype='POINTINESS', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Cavity', otype='CAVITY', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Dust', otype='DUST', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Paint Base', otype='PAINT_BASE', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Bevel Grayscale', otype='BEVEL_MASK', target_type='MASK', overwrite_current=False)
        new_mask_button(col, 'node.y_bake_to_layer', 'Selected Vertices', otype='SELECTED_VERTICES', target_type='MASK', overwrite_current=False)

        col.separator()
        col.label(text='Inbetween Modifier Mask:')
        new_mask_button(col, 'node.y_new_layer_mask', 'Invert', otype='MODIFIER', modifier_type='INVERT', lib_icon='modifier')
        new_mask_button(col, 'node.y_new_layer_mask', 'Ramp', otype='MODIFIER', modifier_type='RAMP', lib_icon='modifier')
        new_mask_button(col, 'node.y_new_layer_mask', 'Curve', otype='MODIFIER', modifier_type='CURVE', lib_icon='modifier')

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
            mask_tree = get_mask_tree(mask)
            source = mask_tree.nodes.get(mask.source)
            col.context_pointer_set('image', source.image)
            col.operator('node.y_invert_image', text='Invert Image', icon='IMAGE_ALPHA')

        col.separator()

        op = col.operator('node.y_move_layer_mask', icon='TRIA_UP', text='Move Mask Up')
        op.direction = 'UP'
        op = col.operator('node.y_move_layer_mask', icon='TRIA_DOWN', text='Move Mask Down')
        op.direction = 'DOWN'

        col.separator()

        op = col.operator('node.y_merge_mask', icon='TRIA_UP', text='Merge Mask Up')
        op.direction = 'UP'
        op = col.operator('node.y_merge_mask', icon='TRIA_DOWN', text='Merge Mask Down')
        op.direction = 'DOWN'

        col.separator()

        col.context_pointer_set('entity', mask)
        col.operator('node.y_bake_entity_to_image', icon_value=lib.get_icon('bake'), text='Bake as Image')
        if mask.baked_source != '':
            if is_bl_newer_than(2, 80):
                col.operator('node.y_remove_baked_entity', text='Remove Baked Image', icon='REMOVE')
            else: col.operator('node.y_remove_baked_entity', text='Remove Baked Image', icon='ZOOMOUT')

        col.separator()

        #op = col.operator('node.y_transfer_layer_uv', icon_value=lib.get_icon('uv'), text='Transfer UV')

        #col.separator()

        if is_bl_newer_than(2, 80):
            col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='REMOVE')
        else: col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='ZOOMOUT')

        col = row.column(align=True)
        col.label(text='Add Modifier')

        col.operator('node.y_new_mask_modifier', text='Invert', icon_value=lib.get_icon('modifier')).type = 'INVERT'
        col.operator('node.y_new_mask_modifier', text='Ramp', icon_value=lib.get_icon('modifier')).type = 'RAMP'
        col.operator('node.y_new_mask_modifier', text='Curve', icon_value=lib.get_icon('modifier')).type = 'CURVE'

        #if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
        #    col.separator()
        #    col.prop(mask, 'enable_blur_vector', text='Blur Vector')

        ypup = get_user_preferences()

        if ypup.developer_mode:
            col = row.column(align=True)
            col.context_pointer_set('parent', mask)
            col.label(text='Advanced')
            if not mask.use_temp_bake:
                col.operator('node.y_bake_temp_image', text='Bake Temp Image', icon_value=lib.get_icon('bake'))
            else:
                col.operator('node.y_disable_temp_image', text='Disable Baked Temp Image', icon='FILE_REFRESH')

class YMaterialSpecialMenu(bpy.types.Menu):
    bl_idname = "MATERIAL_MT_y_special_menu"
    bl_label = "Material Special Menu"
    bl_description = 'Material Special Menu'

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        col = self.layout.column()
        col.operator('material.y_select_all_material_polygons', icon='FACESEL')
        col.operator('material.y_rename_uv_using_the_same_material', icon='GROUP_UVS')

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

        col.label(text='Override Type:')

        icon = 'RADIOBUT_ON' if ch.override_type == 'DEFAULT' else 'RADIOBUT_OFF'
        if root_ch.type == 'VALUE':
            col.operator('node.y_replace_layer_channel_override', text='Value', icon=icon).type = 'DEFAULT'
        else: col.operator('node.y_replace_layer_channel_override', text='Color', icon=icon).type = 'DEFAULT'

        col.separator()

        label = 'Image'
        cache_image = tree.nodes.get(ch.cache_image)
        #source = tree.nodes.get(ch.source)
        source = get_channel_source(ch, layer)
        if cache_image:
            label += ': ' + cache_image.image.name
        elif (ch.override_type == 'IMAGE' and source):
            label += ': ' + source.image.name

        icon = 'RADIOBUT_ON' if ch.override_type == 'IMAGE' else 'RADIOBUT_OFF'
        if cache_image and ch.override_type != 'IMAGE':
            col.operator('node.y_replace_layer_channel_override', text=label, icon=icon).type = 'IMAGE'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)

        ccol = row.column(align=True)
        ccol.operator('node.y_open_image_to_override_layer_channel', text='Open Image...', icon_value=lib.get_icon('open_image'))
        ccol.operator('node.y_open_available_data_to_override_channel', text='Open Available Image', icon_value=lib.get_icon('open_image')).type = 'IMAGE'
        
        col.separator()

        label = 'Vertex Color'
        cache_vcol = tree.nodes.get(ch.cache_vcol)
        #source = tree.nodes.get(ch.source)
        if cache_vcol:
            label += ': ' + get_source_vcol_name(cache_vcol)
        elif (ch.override_type == 'VCOL' and source):
            label += ': ' + get_source_vcol_name(source)

        icon = 'RADIOBUT_ON' if ch.override_type == 'VCOL' else 'RADIOBUT_OFF'
        if cache_vcol and ch.override_type != 'VCOL':
            col.operator('node.y_replace_layer_channel_override', text=label, icon=icon).type = 'VCOL'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)

        ccol = row.column(align=True)
        #ccol.operator('node.y_replace_layer_channel_override', text='New Vertex Color', icon_value=lib.get_icon('vertex_color')).type = 'VCOL'
        ccol.operator('node.y_new_vcol_to_override_channel', text='New Vertex Color', icon_value=lib.get_icon('vertex_color'))
        ccol.operator('node.y_open_available_data_to_override_channel', text='Use Available Vertex Color', icon_value=lib.get_icon('vertex_color')).type = 'VCOL'

        col.separator()

        for item in channel_override_type_items_410 if is_bl_newer_than(4, 1) else channel_override_type_items:
            if item[0] == ch.override_type:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            if item[0] in {'DEFAULT', 'IMAGE', 'VCOL'}: continue

            col.operator('node.y_replace_layer_channel_override', text=item[1], icon=icon).type = item[0]

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

        col.label(text='Override Type:')

        icon = 'RADIOBUT_ON' if ch.override_1_type == 'DEFAULT' else 'RADIOBUT_OFF'
        #if root_ch.type == 'VALUE':
        #    col.operator('node.y_replace_layer_channel_override_1', text='Value', icon=icon).type = 'DEFAULT'
        #else: 
        col.operator('node.y_replace_layer_channel_override_1', text='Color', icon=icon).type = 'DEFAULT'

        col.separator()

        label = 'Image'
        cache_1_image = tree.nodes.get(ch.cache_1_image)
        #source = tree.nodes.get(ch.source)
        source = get_channel_source_1(ch, layer)
        if cache_1_image:
            label += ': ' + cache_1_image.image.name
        elif (ch.override_1_type == 'IMAGE' and source):
            label += ': ' + source.image.name

        icon = 'RADIOBUT_ON' if ch.override_1_type == 'IMAGE' else 'RADIOBUT_OFF'
        if cache_1_image and ch.override_1_type != 'IMAGE':
            col.operator('node.y_replace_layer_channel_override_1', text=label, icon=icon).type = 'IMAGE'
        else:
            col.label(text=label, icon=icon)

        row = col.row(align=True)
        #ccol = row.column(align=True)
        #ccol.label(text='', icon='BLANK1')

        ccol = row.column(align=True)
        ccol.operator('node.y_open_image_to_override_1_layer_channel', text='Open Image...', icon_value=lib.get_icon('open_image'))
        ccol.operator('node.y_open_available_data_to_override_1_channel', text='Open Available Image', icon_value=lib.get_icon('open_image'))

class YChannelSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_channel_special_menu"
    bl_label = "Channel Special Menu"
    bl_description = 'Bake channel or add channel modifiers'

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

        col.operator('node.y_bake_channels', text="Bake " + context.parent.name + " Channel", icon_value=lib.get_icon('bake')).only_active_channel = True

        if context.parent.type != 'NORMAL':
            col.separator()
            col.label(text='Add Modifier')

            # List the items
            for mt in Modifier.modifier_type_items:
                # Override color and multiplier modifier are deprecated
                if mt[0] == 'OVERRIDE_COLOR': continue
                if mt[0] == 'MULTIPLIER': continue
                col.operator('node.y_new_ypaint_modifier', text=mt[1], icon_value=lib.get_icon('modifier')).type = mt[0]

        ypup = get_user_preferences()
        if ypup.show_experimental:

            col = row.column()
            col.label(text='Experimental')
            col.operator('node.y_bake_channel_to_vcol', text='Bake Channel to Vertex Color', icon_value=lib.get_icon('vertex_color')).all_materials = False
            col.operator('node.y_bake_channel_to_vcol', text='Bake Channel to Vertex Color (Batch All Materials)', icon_value=lib.get_icon('vertex_color')).all_materials = True
        
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

        is_bump_layer_channel = False
        is_normal_layer_channel = False
        is_bump_normal_layer_channel = False

        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        yp = context.parent.id_data.yp
        root_ch = yp.channels[int(m.group(2))]

        if root_ch.type == 'NORMAL':
            if context.parent.normal_map_type == 'BUMP_MAP':
                is_bump_layer_channel = True
            elif context.parent.normal_map_type == 'NORMAL_MAP':
                is_normal_layer_channel = True
            elif context.parent.normal_map_type == 'BUMP_NORMAL_MAP':
                is_bump_normal_layer_channel = True

        col.separator()

        if is_bump_normal_layer_channel or is_bump_layer_channel:
            col.label(text='Add Modifier (Bump)')
        elif is_normal_layer_channel:
            col.label(text='Add Modifier (Normal)')
        else:
            col.label(text='Add Modifier')

        if not is_normal_layer_channel:
            # List the items
            for mt in Modifier.modifier_type_items:
                # Override color and multiplier modifier are deprecated
                if mt[0] == 'OVERRIDE_COLOR': continue
                if mt[0] == 'MULTIPLIER': continue
                col.operator('node.y_new_ypaint_modifier', text=mt[1], icon_value=lib.get_icon('modifier')).type = mt[0]

        if is_bump_normal_layer_channel:
            col.separator()
            col.label(text='Add Modifier (Normal)')

        if is_normal_layer_channel or is_bump_normal_layer_channel:
            col.operator('node.y_new_normalmap_modifier', text='Invert', icon_value=lib.get_icon('modifier')).type = 'INVERT'
            col.operator('node.y_new_normalmap_modifier', text='Math', icon_value=lib.get_icon('modifier')).type = 'MATH'

        col = row.column()
        col.label(text='Transition Effects')
        if root_ch.type == 'NORMAL':
            col.operator('node.y_show_transition_bump', text='Transition Bump', icon_value=lib.get_icon('background'))
        else:
            col.operator('node.y_show_transition_ramp', text='Transition Ramp', icon_value=lib.get_icon('background'))
            col.operator('node.y_show_transition_ao', text='Transition AO', icon_value=lib.get_icon('background'))

        if root_ch.type != 'NORMAL':
            col = row.column()
            col.label(text='Extra Props')
            col.prop(context.parent, 'use_clamp')

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

        if context.parent.type != 'GROUP':
            col = row.column()
            col.label(text='Add Modifier')
            ## List the modifiers
            for mt in Modifier.modifier_type_items:
                # Override color modifier is deprecated
                if mt[0] == 'OVERRIDE_COLOR': continue
                if mt[0] == 'MULTIPLIER': continue
                col.operator('node.y_new_ypaint_modifier', text=mt[1], icon_value=lib.get_icon('modifier')).type = mt[0]

        col = row.column()
        col.label(text='Change Layer Type')
        col.operator('node.y_replace_layer_type', text='Image', icon_value=lib.get_icon('image')).type = 'IMAGE'

        #col.operator('node.y_replace_layer_type', text='Vertex Color', icon='GROUP_VCOL').type = 'VCOL'
        col.operator('node.y_replace_layer_type', text='Vertex Color', icon_value=lib.get_icon('vertex_color')).type = 'VCOL'
        #col.operator('node.y_replace_layer_type', text='Solid Color', icon='COLOR').type = 'COLOR'
        col.operator('node.y_replace_layer_type', text='Solid Color', icon_value=lib.get_icon('color')).type = 'COLOR'
        col.operator('node.y_replace_layer_type', text='Background', icon_value=lib.get_icon('background')).type = 'BACKGROUND'
        col.operator('node.y_replace_layer_type', text='Group', icon_value=lib.get_icon('group')).type = 'GROUP'

        col.separator()
        col.operator('node.y_replace_layer_type', text='Brick', icon_value=lib.get_icon('texture')).type = 'BRICK'
        col.operator('node.y_replace_layer_type', text='Checker', icon_value=lib.get_icon('texture')).type = 'CHECKER'
        col.operator('node.y_replace_layer_type', text='Gradient', icon_value=lib.get_icon('texture')).type = 'GRADIENT'
        col.operator('node.y_replace_layer_type', text='Magic', icon_value=lib.get_icon('texture')).type = 'MAGIC'
        if not is_bl_newer_than(4, 1): col.operator('node.y_replace_layer_type', text='Musgrave', icon_value=lib.get_icon('texture')).type = 'MUSGRAVE'
        col.operator('node.y_replace_layer_type', text='Noise', icon_value=lib.get_icon('texture')).type = 'NOISE'
        col.operator('node.y_replace_layer_type', text='Voronoi', icon_value=lib.get_icon('texture')).type = 'VORONOI'
        col.operator('node.y_replace_layer_type', text='Wave', icon_value=lib.get_icon('texture')).type = 'WAVE'

        col.separator()
        col.operator("node.y_replace_layer_type", icon_value=lib.get_icon('hemi'), text='Fake Lighting').type = 'HEMI'

        if ypup.developer_mode:
            #if context.parent.type == 'HEMI':
            col = row.column()
            col.label(text='Advanced')
            if context.parent.use_temp_bake:
                col.operator('node.y_disable_temp_image', text='Disable Baked Temp Image', icon='FILE_REFRESH')
            else:
                col.operator('node.y_bake_temp_image', text='Bake Temp Image', icon_value=lib.get_icon('bake'))

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

class YBakeTargetUI(bpy.types.PropertyGroup):
    expand_content : BoolProperty(
            name='Bake Target Options',
            description='Expand bake target options',
            default=True, update=update_bake_target_ui)

    expand_r : BoolProperty(
            name='R Channel',
            description='Expand bake target R channel options',
            default=False, update=update_bake_target_ui)

    expand_g : BoolProperty(
            name='G Channel',
            description='Expand bake target R channel options',
            default=False, update=update_bake_target_ui)

    expand_b : BoolProperty(
            name='B Channel',
            description='Expand bake target B channel options',
            default=False, update=update_bake_target_ui)

    expand_a : BoolProperty(
            name='A Channel',
            description='Expand bake target A channel options',
            default=False, update=update_bake_target_ui)

class YModifierUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(default=True, update=update_modifier_ui)

class YChannelUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(
            name='Channel Options',
            description='Expand channel options',
            default=False, update=update_channel_ui)

    expand_bump_settings : BoolProperty(
            name='Bump',
            description='Expand bump settings',
            default=False, update=update_channel_ui)

    expand_intensity_settings : BoolProperty(
            name='Intensity',
            description='Expand intensity settings',
            default=False, update=update_channel_ui)

    expand_base_vector : BoolProperty(
            name='Base Vector',
            description='Expand base vector options',
            default=True, update=update_channel_ui)

    expand_transition_bump_settings : BoolProperty(
            name='Transition Bump',
            description='Expand transition bump settings',
            default=True, update=update_channel_ui)

    expand_transition_ramp_settings : BoolProperty(
            name='Transition Ramp',
            description='Expand transition ramp settings',
            default=True, update=update_channel_ui)

    expand_transition_ao_settings : BoolProperty(
            name='Transition AO',
            description='Expand transition AO settings',
            default=True, update=update_channel_ui)

    expand_subdiv_settings : BoolProperty(
            name='Displacement Subdivision',
            description='Expand displacement subdivision settings',
            default=False, update=update_channel_ui)

    expand_parallax_settings : BoolProperty(
            name='Parallax',
            description='Expand parallax settings',
            default=False, update=update_channel_ui)

    expand_alpha_settings : BoolProperty(
            name='Channel Alpha',
            description='Expand alpha settings',
            default=False, update=update_channel_ui)

    expand_bake_to_vcol_settings : BoolProperty(
            name='Bake to Vertex Color',
            description='Expand bake to vertex color settings',
            default=False, update=update_channel_ui)

    expand_input_bump_settings : BoolProperty(
            name='Input Bump',
            description='Expand input bump settings',
            default=False, update=update_channel_ui)

    expand_smooth_bump_settings : BoolProperty(
            name='Smooth Bump',
            description='Expand smooth bump settings',
            default=False, update=update_channel_ui)

    expand_input_settings : BoolProperty(
            name='Input',
            description='Expand input settings',
            default=True, update=update_channel_ui)

    expand_source : BoolProperty(
            name='Channel Source',
            description='Expand channel source settings',
            default=True, update=update_channel_ui)

    expand_source_1 : BoolProperty(
            name='Channel Normal Source',
            description='Expand channel normal source settings',
            default=True, update=update_channel_ui)

    modifiers : CollectionProperty(type=YModifierUI)
    modifiers_1 : CollectionProperty(type=YModifierUI)

class YMaskChannelUI(bpy.types.PropertyGroup):
    expand_content : BoolProperty(
            name='Mask Channel Options',
            description='Expand mask channel options',
            default=False, update=update_mask_channel_ui)

class YMaskUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')
    expand_content : BoolProperty(
            name='Mask Options',
            description='Expand mask options',
            default=True, update=update_mask_ui)

    expand_channels : BoolProperty(
            name='Mask Channel',
            description='Expand mask channels',
            default=True, update=update_mask_ui)

    expand_source : BoolProperty(
            name='Mask Source',
            description='Expand mask source options',
            default=True, update=update_mask_ui)

    expand_vector : BoolProperty(
            name='Mask Vector',
            description='Expand mask vector options',
            default=True, update=update_mask_ui)

    channels : CollectionProperty(type=YMaskChannelUI)
    modifiers : CollectionProperty(type=YModifierUI)

class YLayerUI(bpy.types.PropertyGroup):
    #name : StringProperty(default='')

    expand_content : BoolProperty(
            name='Layer Options',
            description='Expand layer options',
            default=False, update=update_layer_ui)

    expand_vector : BoolProperty(
            name='Layer Vector',
            description='Expand layer vector options',
            default=False, update=update_layer_ui)

    expand_masks : BoolProperty(
            name='Masks',
            description='Expand all masks',
            default=False, update=update_layer_ui)

    expand_source : BoolProperty(
            name='Layer Source',
            description='Expand layer source options',
            default=False, update=update_layer_ui)

    expand_channels : BoolProperty(
            name='Layer Channels',
            description='Expand layer channels',
            default=True, update=update_layer_ui)

    channels : CollectionProperty(type=YChannelUI)
    masks : CollectionProperty(type=YMaskUI)
    modifiers : CollectionProperty(type=YModifierUI)

#def update_mat_active_yp_node(self, context):
#    print('Update:', self.active_ypaint_node)

class YMaterialUI(bpy.types.PropertyGroup):
    name : StringProperty(default='')
    active_ypaint_node : StringProperty(default='') #, update=update_mat_active_yp_node)

class YPaintUI(bpy.types.PropertyGroup):
    show_object : BoolProperty(
            name='Active Object',
            description='Show active object options',
            default=False)

    show_materials : BoolProperty(
            name='Materials',
            description='Show material lists',
            default=False)

    show_channels : BoolProperty(
            name='Channels',
            description='Show channel lists',
            default=True)

    show_layers : BoolProperty(
            name='Layers',
            description='Show layer lists',
            default=True)

    show_bake_targets : BoolProperty(
            name='Custom Bake Targets',
            description='Show custom bake target lists',
            default=False)

    show_stats : BoolProperty(
            name='Stats',
            description='Show node stats',
            default=False)

    show_support : BoolProperty(
            name='Support',
            description='Show support',
            default=False)

    expand_channels : BoolProperty(
            name='Show Channel Toggle',
            description="Show layer channels toggle",
            default=False)

    expand_mask_channels : BoolProperty(
            name='Expand all mask channels',
            description='Expand all mask channels',
            default=False)

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

def add_new_ypaint_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine not in {'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'HYDRA_STORM'}: return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_ypaint_node', text=get_addon_title(), icon_value=lib.get_icon('nodetree'))

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

def load_mat_ui_settings():
    ypui = bpy.context.window_manager.ypui
    for mat in bpy.data.materials:
        if mat.yp.active_ypaint_node != '':
            mui = ypui.materials.add()
            mui.name = mat.name
            mui.material = mat
            mui.active_ypaint_node = mat.yp.active_ypaint_node

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

def register():

    if not is_bl_newer_than(2, 80):
        bpy.utils.register_class(YPaintAboutMenu)
    else: bpy.utils.register_class(YPaintAboutPopover)

    bpy.utils.register_class(YPaintSpecialMenu)
    bpy.utils.register_class(YNewChannelMenu)
    bpy.utils.register_class(YNewLayerMenu)
    bpy.utils.register_class(YBakeTargetMenu)
    bpy.utils.register_class(YBakedImageMenu)
    bpy.utils.register_class(YLayerListSpecialMenu)
    bpy.utils.register_class(YImageConvertToMenu)
    bpy.utils.register_class(YOpenImagesToSingleLayerMenu)
    bpy.utils.register_class(YNewSolidColorLayerMenu)
    bpy.utils.register_class(YUVSpecialMenu)
    bpy.utils.register_class(YModifierMenu)
    bpy.utils.register_class(YModifier1Menu)
    bpy.utils.register_class(YMaskModifierMenu)
    bpy.utils.register_class(YTransitionBumpMenu)
    bpy.utils.register_class(YTransitionRampMenu)
    bpy.utils.register_class(YTransitionAOMenu)
    bpy.utils.register_class(YAddLayerMaskMenu)
    bpy.utils.register_class(YLayerMaskMenu)
    bpy.utils.register_class(YMaterialSpecialMenu)
    bpy.utils.register_class(YChannelSpecialMenu)
    bpy.utils.register_class(YLayerChannelSpecialMenu)
    bpy.utils.register_class(YReplaceChannelOverrideMenu)
    bpy.utils.register_class(YReplaceChannelOverride1Menu)
    bpy.utils.register_class(YLayerSpecialMenu)
    bpy.utils.register_class(YModifierUI)
    bpy.utils.register_class(YBakeTargetUI)
    bpy.utils.register_class(YChannelUI)
    bpy.utils.register_class(YMaskChannelUI)
    bpy.utils.register_class(YMaskUI)
    bpy.utils.register_class(YLayerUI)
    bpy.utils.register_class(YMaterialUI)
    bpy.utils.register_class(NODE_UL_YPaint_bake_targets)
    bpy.utils.register_class(NODE_UL_YPaint_channels)
    bpy.utils.register_class(NODE_UL_YPaint_layers)
    bpy.utils.register_class(YPAssetBrowserMenu)
    bpy.utils.register_class(YPFileBrowserMenu)

    if not is_bl_newer_than(2, 80):
        bpy.utils.register_class(VIEW3D_PT_YPaint_tools)
        bpy.utils.register_class(NODE_PT_YPaint)
    else: 
        bpy.utils.register_class(NODE_PT_YPaintUI)

    bpy.utils.register_class(VIEW3D_PT_YPaint_ui)
    bpy.utils.register_class(YPaintUI)

    bpy.types.Scene.ypui = PointerProperty(type=YPaintUI)
    bpy.types.WindowManager.ypui = PointerProperty(type=YPaintUI)

    # Add yPaint node ui
    bpy.types.NODE_MT_add.append(add_new_ypaint_node_menu)

    if is_bl_newer_than(3):
        bpy.types.ASSETBROWSER_MT_context_menu.append(draw_yp_asset_browser_menu)

    if is_bl_newer_than(2, 81):
        bpy.types.FILEBROWSER_MT_context_menu.append(draw_yp_file_browser_menu)

    # Handlers
    bpy.app.handlers.load_post.append(yp_load_ui_settings)
    bpy.app.handlers.save_pre.append(yp_save_ui_settings)

def unregister():

    if not is_bl_newer_than(2, 80):
        bpy.utils.unregister_class(YPaintAboutMenu)
    else: bpy.utils.unregister_class(YPaintAboutPopover)

    bpy.utils.unregister_class(YPaintSpecialMenu)
    bpy.utils.unregister_class(YNewChannelMenu)
    bpy.utils.unregister_class(YNewLayerMenu)
    bpy.utils.unregister_class(YBakeTargetMenu)
    bpy.utils.unregister_class(YBakedImageMenu)
    bpy.utils.unregister_class(YLayerListSpecialMenu)
    bpy.utils.unregister_class(YImageConvertToMenu)
    bpy.utils.unregister_class(YOpenImagesToSingleLayerMenu)
    bpy.utils.unregister_class(YNewSolidColorLayerMenu)
    bpy.utils.unregister_class(YUVSpecialMenu)
    bpy.utils.unregister_class(YModifierMenu)
    bpy.utils.unregister_class(YModifier1Menu)
    bpy.utils.unregister_class(YMaskModifierMenu)
    bpy.utils.unregister_class(YTransitionBumpMenu)
    bpy.utils.unregister_class(YTransitionRampMenu)
    bpy.utils.unregister_class(YTransitionAOMenu)
    bpy.utils.unregister_class(YAddLayerMaskMenu)
    bpy.utils.unregister_class(YLayerMaskMenu)
    bpy.utils.unregister_class(YMaterialSpecialMenu)
    bpy.utils.unregister_class(YChannelSpecialMenu)
    bpy.utils.unregister_class(YLayerChannelSpecialMenu)
    bpy.utils.unregister_class(YReplaceChannelOverrideMenu)
    bpy.utils.unregister_class(YReplaceChannelOverride1Menu)
    bpy.utils.unregister_class(YLayerSpecialMenu)
    bpy.utils.unregister_class(YModifierUI)
    bpy.utils.unregister_class(YBakeTargetUI)
    bpy.utils.unregister_class(YChannelUI)
    bpy.utils.unregister_class(YMaskChannelUI)
    bpy.utils.unregister_class(YMaskUI)
    bpy.utils.unregister_class(YLayerUI)
    bpy.utils.unregister_class(YMaterialUI)
    bpy.utils.unregister_class(NODE_UL_YPaint_bake_targets)
    bpy.utils.unregister_class(NODE_UL_YPaint_channels)
    bpy.utils.unregister_class(NODE_UL_YPaint_layers)
    bpy.utils.unregister_class(YPAssetBrowserMenu)
    bpy.utils.unregister_class(YPFileBrowserMenu)

    if not is_bl_newer_than(2, 80):
        bpy.utils.unregister_class(VIEW3D_PT_YPaint_tools)
        bpy.utils.unregister_class(NODE_PT_YPaint)
    else: 
        bpy.utils.unregister_class(NODE_PT_YPaintUI)

    bpy.utils.unregister_class(VIEW3D_PT_YPaint_ui)
    bpy.utils.unregister_class(YPaintUI)

    # Remove add yPaint node ui
    bpy.types.NODE_MT_add.remove(add_new_ypaint_node_menu)

    if is_bl_newer_than(3):
        bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_yp_asset_browser_menu)

    # Remove Handlers
    bpy.app.handlers.load_post.remove(yp_load_ui_settings)
    bpy.app.handlers.save_pre.remove(yp_save_ui_settings)
