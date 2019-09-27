import bpy, re, time
from bpy.props import *
from bpy.app.handlers import persistent
from . import lib, Modifier, MaskModifier, Root
from .common import *
#from .subtree import *

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
        ypui.need_update
        ):

        ypui.tree_name = tree.name
        ypui.layer_idx = yp.active_layer_index
        ypui.channel_idx = yp.active_channel_index
        ypui.need_update = False
        ypui.halt_prop_update = True

        if len(yp.channels) > 0:

            # Get channel
            channel = yp.channels[yp.active_channel_index]
            ypui.channel_ui.expand_content = channel.expand_content
            ypui.channel_ui.expand_base_vector = channel.expand_base_vector
            ypui.channel_ui.expand_subdiv_settings = channel.expand_subdiv_settings
            ypui.channel_ui.expand_parallax_settings = channel.expand_parallax_settings
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
                c.expand_content = ch.expand_content

                for mod in ch.modifiers:
                    m = c.modifiers.add()
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

def draw_image_props(source, layout, entity=None):

    image = source.image

    col = layout.column()

    if image.yia.is_image_atlas:
        col.label(text=image.name, icon='IMAGE_DATA')
        segment = image.yia.segments.get(entity.segment_name)
        if segment:
            row = col.row()
            row.label(text='Tile X: ' + str(segment.tile_x))
            row.label(text='Tile Y: ' + str(segment.tile_y))
            row = col.row()
            row.label(text='Width: ' + str(segment.width))
            row.label(text='Height: ' + str(segment.height))

        return

    col.template_ID(source, "image", unlink='node.y_remove_layer')
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
        col.template_colorspace_settings(image, "colorspace_settings")

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

        col.template_colorspace_settings(image, "colorspace_settings")
        #col.prop(image, 'use_view_as_render')
        col.prop(image, 'alpha_mode')
        if hasattr(image, 'use_alpha'):
            col.prop(image, 'use_alpha')
        #col.prop(image, 'use_fields')

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

def draw_vcol_props(entity, vcol, layout):
    layout.label(text='You can also edit vertex color on edit mode')

def draw_tex_props(source, layout):

    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(text=title + ' Properties:')
    #col.separator()

    if title == 'Brick':
        row = col.row()
        col = row.column(align=True)
        col.label(text='Offset:')
        col.label(text='Frequency:')
        col.separator()

        col.label(text='Squash:')
        col.label(text='Frequency:')
        col.separator()

        col.label(text='Color 1:')
        col.label(text='Color 2:')
        col.label(text='Mortar:')
        col.separator()
        col.label(text='Scale:')
        col.label(text='Mortar Size:')
        col.label(text='Mortar Smooth:')
        col.label(text='Bias:')
        col.label(text='Brick Width:')
        col.label(text='Brick Height:')

        col = row.column(align=True)
        col.prop(source, 'offset', text='')
        col.prop(source, 'offset_frequency', text='')
        col.separator()

        col.prop(source, 'squash', text='')
        col.prop(source, 'squash_frequency', text='')
        col.separator()
        for i in range (1,10):
            if i == 4: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Checker':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Color 1:')
        col.label(text='Color 2:')
        col.separator()
        col.label(text='Scale:')
        col = row.column(align=True)
        for i in range (1,4):
            if i == 3: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

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
        col.label(text='Scale:')
        col.label(text='Distortion:')
        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')

    elif title == 'Musgrave':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Type:')
        col.separator()
        col.label(text='Scale:')
        col.label(text='Detail:')
        col.label(text='Dimension:')
        col.label(text='Lacunarity:')
        col.label(text='Offset:')
        col.label(text='Gain:')
        col = row.column(align=True)
        col.prop(source, 'musgrave_type', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')
        col.prop(source.inputs[3], 'default_value', text='')
        col.prop(source.inputs[4], 'default_value', text='')
        col.prop(source.inputs[5], 'default_value', text='')
        col.prop(source.inputs[6], 'default_value', text='')

    elif title == 'Noise':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Scale:')
        col.label(text='Detail:')
        col.label(text='Distortion:')
        col = row.column(align=True)
        for i in range (1,4):
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Voronoi':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Coloring:')
        col.separator()
        col.label(text='Scale:')
        col = row.column(align=True)
        col.prop(source, 'coloring', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')

    elif title == 'Wave':

        row = col.row()
        col = row.column(align=True)
        col.label(text='Type:')
        col.label(text='Profile:')
        col.label(text='Scale:')
        col.label(text='Distortion:')
        col.label(text='Detail:')
        col.label(text='Detail Scale:')
        col = row.column(align=True)
        col.prop(source, 'wave_type', text='')
        col.prop(source, 'wave_profile', text='')
        col.separator()
        for i in range (1,5):
            col.prop(source.inputs[i], 'default_value', text='')

def draw_solid_color_props(layer, source, layout):
    col = layout.column()
    #col.label(text='Ewsom')
    row = col.row()
    row.label(text='Color:')
    row.prop(source.outputs[0], 'default_value', text='')
    row = col.row()
    row.label(text='Shortcut on list:')
    row.prop(layer, 'color_shortcut', text='')

def draw_mask_modifier_stack(layer, mask, layout, ui, custom_icon_enable):
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
            if custom_icon_enable:
                if modui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(modui, 'expand_content', text='', icon='MODIFIER')
        else:
            row.label(text='', icon='MODIFIER')

        row.label(text=m.name)

        row.context_pointer_set('layer', layer)
        row.context_pointer_set('mask', mask)
        row.context_pointer_set('modifier', m)
        if is_28():
            row.menu("NODE_MT_y_mask_modifier_menu", text='', icon='PREFERENCES')
        else: row.menu("NODE_MT_y_mask_modifier_menu", text='', icon='SCRIPTWIN')

        row.prop(m, 'enable', text='')

        if modui.expand_content and can_be_expanded:
            row = layout.row(align=True)
            row.label(text='', icon='BLANK1')
            box = row.box()
            box.active = m.enable
            MaskModifier.draw_modifier_properties(tree, m, box)

def draw_modifier_stack(context, parent, channel_type, layout, ui, custom_icon_enable, layer=None, extra_blank=False):

    ypui = context.window_manager.ypui

    for i, m in enumerate(parent.modifiers):

        try: modui = ui.modifiers[i]
        except: 
            ypui.need_update = True
            return

        mod_tree = get_mod_tree(m)
        can_be_expanded = m.type in Modifier.can_be_expanded
        
        row = layout.row(align=True)

        if can_be_expanded:
            if custom_icon_enable:
                if modui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(modui, 'expand_content', text='', icon='MODIFIER')
        else:
            row.label(text='', icon='MODIFIER')
        
        row.label(text=m.name)

        if not modui.expand_content:

            if m.type == 'RGB_TO_INTENSITY':
                row.prop(m, 'rgb2i_col', text='', icon='COLOR')
                row.separator()

            if m.type == 'OVERRIDE_COLOR': # and not m.oc_use_normal_base:
                if channel_type == 'VALUE':
                    row.prop(m, 'oc_val', text='')
                else: 
                    row.prop(m, 'oc_col', text='', icon='COLOR')
                    row.separator()

        row.context_pointer_set('layer', layer)
        row.context_pointer_set('parent', parent)
        row.context_pointer_set('modifier', m)
        if is_28():
            row.menu("NODE_MT_y_modifier_menu", text='', icon='PREFERENCES')
        else: row.menu("NODE_MT_y_modifier_menu", text='', icon='SCRIPTWIN')
        row.prop(m, 'enable', text='')

        if modui.expand_content and can_be_expanded:
            row = layout.row(align=True)
            #row.label(text='', icon='BLANK1')
            row.label(text='', icon='BLANK1')
            box = row.box()
            box.active = m.enable
            Modifier.draw_modifier_properties(bpy.context, channel_type, mod_tree.nodes, m, box, False)
            #row.label(text='', icon='BLANK1')

def draw_root_channels_ui(context, layout, node, custom_icon_enable):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui

    box = layout.box()
    col = box.column()
    row = col.row()

    rcol = row.column()
    if len(yp.channels) > 0:
        pcol = rcol.column()
        if yp.preview_mode: pcol.alert = True
        if custom_icon_enable:
            pcol.prop(yp, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')
        else: pcol.prop(yp, 'preview_mode', text='Preview Mode', icon='HIDE_OFF')

    rcol.template_list("NODE_UL_YPaint_channels", "", yp,
            "channels", yp, "active_channel_index", rows=3, maxrows=5)  

    rcol = row.column(align=True)
    #rcol.context_pointer_set('node', node)

    if is_28():
        rcol.operator_menu_enum("node.y_add_new_ypaint_channel", 'type', icon='ADD', text='')
        rcol.operator("node.y_remove_ypaint_channel", icon='REMOVE', text='')
    else: 
        rcol.operator_menu_enum("node.y_add_new_ypaint_channel", 'type', icon='ZOOMIN', text='')
        rcol.operator("node.y_remove_ypaint_channel", icon='ZOOMOUT', text='')

    rcol.operator("node.y_move_ypaint_channel", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("node.y_move_ypaint_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

    if len(yp.channels) > 0:

        mcol = col.column(align=False)

        channel = yp.channels[yp.active_channel_index]
        mcol.context_pointer_set('channel', channel)

        chui = ypui.channel_ui

        row = mcol.row(align=True)

        if custom_icon_enable:
            icon_name = lib.channel_custom_icon_dict[channel.type]
            if chui.expand_content:
                icon_name = 'uncollapsed_' + icon_name
            else: icon_name = 'collapsed_' + icon_name
            icon_value = lib.custom_icons[icon_name].icon_id
            row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(chui, 'expand_content', text='', emboss=True, icon=lib.channel_icon_dict[channel.type])

        row.label(text=channel.name + ' Channel')

        #if channel.type != 'NORMAL':
        row.context_pointer_set('parent', channel)
        row.context_pointer_set('channel_ui', chui)
        #if custom_icon_enable:
        if is_28():
            row.menu("NODE_MT_y_new_modifier_menu", icon='PREFERENCES', text='')
        else: row.menu("NODE_MT_y_new_modifier_menu", icon='SCRIPTWIN', text='')

        if chui.expand_content:

            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            draw_modifier_stack(context, channel, channel.type, bcol, chui, custom_icon_enable)

            inp = node.inputs[channel.io_index]

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)

                #if channel.type == 'NORMAL':
                #    if chui.expand_base_vector:
                #        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                #    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                #    brow.prop(chui, 'expand_base_vector', text='', emboss=False, icon_value=icon_value)
                #else: brow.label(text='', icon='INFO')

                brow.label(text='', icon='INFO')

                if channel.type == 'RGB':
                    brow.label(text='Background:')
                elif channel.type == 'VALUE':
                    brow.label(text='Base Value:')
                #elif channel.type == 'NORMAL':
                    #if chui.expand_base_vector:
                    #    brow.label(text='Base Normal:')
                    #else: brow.label(text='Base Normal')
                    #brow.label(text='Base Normal')

            if channel.type == 'NORMAL':
                #if chui.expand_base_vector:
                #    brow = bcol.row(align=True)
                #    brow.label(text='', icon='BLANK1')
                #    brow.prop(inp,'default_value', text='')
                pass
            elif len(inp.links) == 0:
                #if BLENDER_28_GROUP_INPUT_HACK:
                #    if channel.type == 'RGB':
                #        brow.prop(channel,'col_input', text='')
                #    elif channel.type == 'VALUE':
                #        brow.prop(channel,'val_input', text='')
                #else:
                brow.prop(inp,'default_value', text='')
            else:
                brow.label(text='', icon='LINKED')

            if len(channel.modifiers) > 0:
                brow.label(text='', icon='BLANK1')

            #if channel.type == 'RGB':
            brow = bcol.row(align=True)
            brow.label(text='', icon='INFO')
            if channel.enable_alpha:
                inp_alpha = node.inputs[channel.io_index+1]
                brow.label(text='Base Alpha:')
                if len(node.inputs[channel.io_index+1].links)==0:
                    brow.prop(inp_alpha, 'default_value', text='')
                else: brow.label(text='', icon='LINKED')
            else: brow.label(text='Alpha:')
            brow.prop(channel, 'enable_alpha', text='')

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.active = not yp.use_baked or channel.no_layer_using
                brow.label(text='', icon='INFO')
                brow.label(text='Use Clamp:')
                brow.prop(channel, 'use_clamp', text='')

            #if len(channel.modifiers) > 0:
            #    brow.label(text='', icon='BLANK1')

            if channel.type == 'NORMAL':
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')
                brow.label(text='Smooth Bump:')
                brow.prop(channel, 'enable_smooth_bump', text='')

                #brow = bcol.row(align=True)
                #brow.label(text='', icon='INFO')
                #brow.label(text='Displacement:')
                #brow.prop(channel, 'enable_parallax', text='')

                brow = bcol.row(align=True)
                brow.active = channel.enable_parallax and (
                        not yp.use_baked or not channel.enable_subdiv_setup or channel.subdiv_adaptive)

                if custom_icon_enable:
                    if chui.expand_parallax_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    brow.prop(chui, 'expand_parallax_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    brow.prop(chui, 'expand_parallax_settings', text='', emboss=True, icon='INFO')

                #brow.label(text='', icon='INFO')

                brow.label(text='Parallax:')
                #if channel.enable_parallax:
                if not chui.expand_parallax_settings and channel.enable_parallax:
                    brow.prop(channel, 'parallax_num_of_layers', text='')
                    brow.prop(channel, 'baked_parallax_num_of_layers', text='')
                brow.prop(channel, 'enable_parallax', text='')

                if chui.expand_parallax_settings:

                    brow = bcol.row(align=True)
                    brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)
                    bbcol.active = channel.enable_parallax and (
                            not yp.use_baked or not channel.enable_subdiv_setup or channel.subdiv_adaptive)

                    brow = bbcol.row(align=True)
                    brow.label(text='Steps:')
                    brow.prop(channel, 'parallax_num_of_layers', text='')

                    brow = bbcol.row(align=True)
                    brow.label(text='Steps (Baked):')
                    brow.prop(channel, 'baked_parallax_num_of_layers', text='')

                    brow = bbcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    brow.label(text='Rim Hack:')
                    if channel.parallax_rim_hack:
                        brow.prop(channel, 'parallax_rim_hack_hardness', text='')
                    brow.prop(channel, 'parallax_rim_hack', text='')

                    brow = bbcol.row(align=True)
                    brow.label(text='Main UV: ' + channel.main_uv)

                #if channel.enable_parallax:

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Height Ratio:')
                    #brow.prop(channel, 'displacement_height_ratio', text='')

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Reference Plane:')
                    #brow.prop(channel, 'displacement_ref_plane', text='')

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Number of Samples:')
                    #brow.prop(channel, 'parallax_num_of_layers', text='')

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Linear Samples:')
                    #brow.prop(channel, 'parallax_num_of_linear_samples', text='')

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Binary Samples:')
                    #brow.prop(channel, 'parallax_num_of_binary_samples', text='')

                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='INFO')
                    #brow.label(text='Rim Hack:')
                    #if channel.parallax_rim_hack:
                    #    brow.prop(channel, 'parallax_rim_hack_hardness', text='')
                    #brow.prop(channel, 'parallax_rim_hack', text='')

                brow = bcol.row(align=True)
                #brow.label(text='', icon='INFO')

                if custom_icon_enable:
                    if chui.expand_subdiv_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    brow.prop(chui, 'expand_subdiv_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    brow.prop(chui, 'expand_subdiv_settings', text='', emboss=True, icon='INFO')

                brow.label(text='Subdiv Setup:')
                brow.active = yp.use_baked
                brow.prop(channel, 'enable_subdiv_setup', text='')

                if chui.expand_subdiv_settings:

                    #subsurf = get_subsurf_modifier(context.object)
                    #displace = get_displace_modifier(context.object)

                    brow = bcol.row(align=True)
                    brow.label(text='', icon='BLANK1')
                    bbox = brow.box()
                    bbcol = bbox.column() #align=True)
                    bbcol.active = yp.use_baked

                    #if subsurf:
                    #    brow = bbcol.row(align=True)
                    #    brow.label(text='Type:')
                    #    brow.prop(subsurf, 'subdivision_type', expand=True)

                    brow = bbcol.row(align=True)
                    brow.label(text='Adaptive (Cycles Only):')
                    brow.prop(channel, 'subdiv_adaptive', text='')

                    brow = bbcol.row(align=True)
                    brow.label(text='Type:')
                    brow.prop(channel, 'subdiv_standard_type', expand=True)

                    #if not channel.enable_subdiv_setup or channel.subdiv_adaptive:
                    brow = bbcol.row(align=True)
                    if channel.subdiv_adaptive:
                        brow.label(text='Viewport Level:')
                    else: brow.label(text='Setup Off Level:')
                    brow.prop(channel, 'subdiv_off_level', text='')

                    if channel.subdiv_adaptive:
                        brow = bbcol.row(align=True)
                        brow.label(text='Global Dicing:')
                        brow.prop(channel, 'subdiv_global_dicing', text='')

                        brow = bbcol.row(align=True)
                        brow.label(text='Dicing Scale:')
                        brow.prop(context.object.cycles, 'dicing_rate', text='')
                    else:
                    #if channel.enable_subdiv_setup and not channel.subdiv_adaptive:
                        brow = bbcol.row(align=True)
                        brow.label(text='Setup On Level:')
                        brow.prop(channel, 'subdiv_on_level', text='')

                    brow = bbcol.row(align=True)
                    brow.label(text='Subdiv Tweak:')
                    brow.prop(channel, 'subdiv_tweak', text='')

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')

                if is_28():
                    split = brow.split(factor=0.375, align=True)
                else: split = brow.split(percentage=0.375)

                #split = brow.row(align=False)
                split.label(text='Space:')
                split.prop(channel, 'colorspace', text='')

def draw_layer_source(context, layout, layer, layer_tree, source, image, vcol, is_a_mesh, custom_icon_enable):
    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    scene = context.scene

    row = layout.row(align=True)
    if image:
        if custom_icon_enable:
            if lui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_image"].icon_id
            else: icon_value = lib.custom_icons["collapsed_image"].icon_id
            row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(lui, 'expand_content', text='', emboss=True, icon='IMAGE_DATA')
        if image.yia.is_image_atlas:
            row.label(text=layer.name)
        else: row.label(text=image.name)
    elif vcol:
        if len(layer.modifiers) > 0:
            if custom_icon_enable:
                if lui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_vcol"].icon_id
                else: icon_value = lib.custom_icons["collapsed_vcol"].icon_id
                row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(lui, 'expand_content', text='', emboss=True, icon='GROUP_VCOL')
        else:
            row.label(text='', icon='GROUP_VCOL')
        row.label(text=vcol.name)
    elif layer.type == 'BACKGROUND':
        if len(layer.modifiers) > 0:
            if custom_icon_enable:
                if lui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
                else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
                row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(lui, 'expand_content', text='', emboss=True, icon='TEXTURE')
        else:
            row.label(text='', icon='TEXTURE')
        row.label(text=layer.name)
    elif layer.type == 'COLOR':
        if custom_icon_enable:
            if lui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_color"].icon_id
            else: icon_value = lib.custom_icons["collapsed_color"].icon_id
            row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(lui, 'expand_content', text='', emboss=True, icon='COLOR')
        row.label(text=layer.name)
    elif layer.type == 'GROUP':
        row.label(text='', icon='FILE_FOLDER')
        row.label(text=layer.name)
    elif layer.type == 'HEMI':
        if custom_icon_enable:
            if lui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
            else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
            row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            if is_28(): row.prop(lui, 'expand_content', text='', emboss=True, icon='LIGHT')
            else: row.prop(lui, 'expand_content', text='', emboss=True, icon='LAMP')
        row.label(text=layer.name)
    else:
        title = source.bl_idname.replace('ShaderNodeTex', '')
        if custom_icon_enable:
            if lui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
            else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
            row.prop(lui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(lui, 'expand_content', text='', emboss=True, icon='TEXTURE')
        row.label(text=title)

    row.context_pointer_set('parent', layer)
    row.context_pointer_set('layer', layer)
    row.context_pointer_set('layer_ui', lui)

    if obj.mode == 'EDIT':
        if obj.type == 'MESH' and obj.data.uv_layers.active and obj.data.uv_layers.active.name == TEMP_UV:
            row = row.row(align=True)
            row.alert = True
            row.operator('node.y_back_to_original_uv', icon='EDITMODE_HLT', text='Edit Original UV')
    else:
        #if ypui.disable_auto_temp_uv_update and yp.need_temp_uv_refresh:
        if yp.need_temp_uv_refresh or is_active_uv_map_match_entity(obj, layer):
            row = row.row(align=True)
            row.alert = True
            row.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

    if layer.use_temp_bake:
        row = row.row(align=True)
        row.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')

    #if layer.type != 'GROUP':
    if is_28():
        row.menu("NODE_MT_y_layer_special_menu", icon='PREFERENCES', text='')
    else: row.menu("NODE_MT_y_layer_special_menu", icon='SCRIPTWIN', text='')

    if layer.type == 'GROUP': return
    if layer.type in {'VCOL', 'BACKGROUND'} and len(layer.modifiers) == 0: return
    #if layer.type in {'BACKGROUND'} and len(layer.modifiers) == 0: return
    if not lui.expand_content: return

    rrow = layout.row(align=True)
    rrow.label(text='', icon='BLANK1')
    rcol = rrow.column(align=False)

    modcol = rcol.column()
    modcol.active = layer.type not in {'BACKGROUND', 'GROUP'}
    draw_modifier_stack(context, layer, 'RGB', modcol, 
            lui, custom_icon_enable, layer)

    if layer.type not in {'VCOL', 'BACKGROUND'}:
    #if layer.type not in {'BACKGROUND'}:
        row = rcol.row(align=True)

        if custom_icon_enable:
            if layer.type == 'IMAGE':
                suffix = 'image'
            elif layer.type == 'COLOR':
                suffix = 'color'
            else: suffix = 'texture'

            if lui.expand_source:
                icon_value = lib.custom_icons["uncollapsed_" + suffix].icon_id
            else: icon_value = lib.custom_icons["collapsed_" + suffix].icon_id
            row.prop(lui, 'expand_source', text='', emboss=False, icon_value=icon_value)
        else:
            if layer.type == 'IMAGE':
                icon = 'IMAGE_DATA'
            #elif layer.type == 'VCOL':
            #    icon = 'GROUP_VCOL'
            else:
                icon = 'TEXTURE'
            #icon = 'IMAGE_DATA' if layer.type == 'IMAGE' else 'TEXTURE'
            row.prop(lui, 'expand_source', text='', emboss=True, icon=icon)

        if image:
            row.label(text='Source: ' + image.name)
        elif vcol:
            row.label(text='Source: ' + vcol.name)
        else: row.label(text='Source: ' + layer.name)

        if lui.expand_source:
            row = rcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bbox = row.box()

            if layer.use_temp_bake:
                bbox.context_pointer_set('parent', layer)
                bbox.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')
            elif image:
                draw_image_props(source, bbox, layer)
            elif layer.type == 'COLOR':
                draw_solid_color_props(layer, source, bbox)
            elif layer.type == 'VCOL':
                draw_vcol_props(layer, vcol, bbox)
            elif layer.type == 'HEMI':
                draw_hemi_props(layer, source, bbox)
            else: draw_tex_props(source, bbox)

        # Vector
        if layer.type not in {'VCOL', 'COLOR', 'HEMI', 'OBJECT_INDEX'}:
            row = rcol.row(align=True)

            if custom_icon_enable:
                if lui.expand_vector:
                    icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                row.prop(lui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(lui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

            if is_28():
                split = row.split(factor=0.275, align=True)
            else: split = row.split(percentage=0.275, align=True)

            split.label(text='Vector:')
            if is_a_mesh and layer.texcoord_type == 'UV':

                if is_28():
                    ssplit = split.split(factor=0.33, align=True)
                else: ssplit = split.split(percentage=0.33, align=True)

                #ssplit = split.split(percentage=0.33, align=True)
                ssplit.prop(layer, 'texcoord_type', text='')
                ssplit.prop_search(layer, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            else:
                split.prop(layer, 'texcoord_type', text='')

            if layer.texcoord_type == 'UV':
                if is_28():
                    row.menu("NODE_MT_y_uv_special_menu", icon='PREFERENCES', text='')
                else: row.menu("NODE_MT_y_uv_special_menu", icon='SCRIPTWIN', text='')

            if lui.expand_vector:
                row = rcol.row(align=True)
                row.label(text='', icon='BLANK1')
                bbox = row.box()
                crow = row.column()
                bbox.prop(layer, 'translation', text='Offset')
                bbox.prop(layer, 'rotation')
                bbox.prop(layer, 'scale')

                if yp.need_temp_uv_refresh or is_active_uv_map_match_entity(obj, layer):
                    rrow = bbox.row(align=True)
                    rrow.alert = True
                    rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

    layout.separator()

def draw_layer_channels(context, layout, layer, layer_tree, image, custom_icon_enable):

    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui
    
    row = layout.row(align=True)
    if custom_icon_enable:
        if lui.expand_channels:
            icon_value = lib.custom_icons["uncollapsed_channels"].icon_id
        else: icon_value = lib.custom_icons["collapsed_channels"].icon_id
        row.prop(lui, 'expand_channels', text='', emboss=False, icon_value=icon_value)
    else: row.prop(lui, 'expand_channels', text='', emboss=True, icon='GROUP_VERTEX')

    #label = 'Channels:'
    #if not lui.expand_channels:
    #    for i, ch in enumerate(layer.channels):

    #        if ch.enable:

    #            if i == 0:
    #                label += ' '
    #            #elif i < len(layer.channels)-1:
    #            else:
    #                label += ', '

    #            label += yp.channels[i].name

    #    row.label(text=label)
    #    return

    enabled_channels = len([c for c in layer.channels if c.enable])

    label = 'Channel'
    if enabled_channels == 0:
        #label += ' (0)'
        pass
    elif enabled_channels == 1:
        label += ' (1)'
    else:
        label += 's (' + str(enabled_channels) + ')'

    if lui.expand_channels:
        label += ':'
    
    row.label(text=label)

    if not lui.expand_channels:
        return

    if custom_icon_enable:
        row.prop(ypui, 'expand_channels', text='', emboss=True, icon_value = lib.custom_icons['channels'].icon_id)
    else: row.prop(ypui, 'expand_channels', text='', emboss=True, icon = 'GROUP_VERTEX')

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

        #expandable = True
        expandable = (
                len(ch.modifiers) > 0 or 
                layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'} or 
                root_ch.type == 'NORMAL' or
                ch.show_transition_ramp or
                ch.show_transition_ao or
                showed_bump_ch_found
                )

        if custom_icon_enable:
            icon_name = lib.channel_custom_icon_dict[root_ch.type]
            if expandable:
                if chui.expand_content:
                    icon_name = 'uncollapsed_' + icon_name
                else: icon_name = 'collapsed_' + icon_name
            icon_value = lib.custom_icons[icon_name].icon_id
            if expandable:
                row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else: row.label(text='', icon_value=icon_value)
        else:
            icon = lib.channel_icon_dict[root_ch.type]
            if expandable:
                row.prop(chui, 'expand_content', text='', emboss=True, icon=icon)
            else: row.label(text='', icon=icon)

        row.label(text=yp.channels[i].name + ':')

        #if layer.type != 'BACKGROUND':
        if root_ch.type == 'NORMAL':
            row.prop(ch, 'normal_blend_type', text='')
        elif layer.type != 'BACKGROUND':
            row.prop(ch, 'blend_type', text='')

        row.prop(ch, 'intensity_value', text='')

        row.context_pointer_set('parent', ch)
        row.context_pointer_set('layer', layer)
        row.context_pointer_set('channel_ui', chui)

        #if custom_icon_enable:
        if is_28():
            row.menu("NODE_MT_y_new_modifier_menu", icon='PREFERENCES', text='')
        else:
            row.menu("NODE_MT_y_new_modifier_menu", icon='SCRIPTWIN', text='')

        if ypui.expand_channels:
            row.prop(ch, 'enable', text='')

        if not expandable or not chui.expand_content: continue

        mrow = ccol.row(align=True)
        mrow.label(text='', icon='BLANK1')
        mcol = mrow.column()

        if root_ch.type == 'NORMAL':

            #if ch.normal_map_type == 'FINE_BUMP_MAP' and image:
            if root_ch.enable_smooth_bump and image:

                uv_neighbor = layer_tree.nodes.get(layer.uv_neighbor)
                if uv_neighbor:
                    cur_x = uv_neighbor.inputs[1].default_value 
                    cur_y = uv_neighbor.inputs[2].default_value 

                    mapping = get_layer_mapping(layer)
                    correct_x = image.size[0] * mapping.scale[0]
                    correct_y = image.size[1] * mapping.scale[1]

                    if cur_x != correct_x or cur_y != correct_y:
                        brow = mcol.row(align=True)
                        brow.alert = True
                        brow.context_pointer_set('channel', ch)
                        brow.context_pointer_set('image', image)
                        brow.operator('node.y_refresh_neighbor_uv', icon='ERROR')

            if ch.show_transition_bump or ch.enable_transition_bump:

                brow = mcol.row(align=True)
                if custom_icon_enable:
                    if chui.expand_transition_bump_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    brow.prop(chui, 'expand_transition_bump_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    brow.prop(chui, 'expand_transition_bump_settings', text='', emboss=True, icon='MOD_MASK')
                brow.label(text='Transition Bump:')

                if ch.enable_transition_bump and not chui.expand_transition_bump_settings:
                    #brow.prop(ch, 'transition_bump_value', text='')
                    brow.prop(ch, 'transition_bump_distance', text='')

                brow.context_pointer_set('parent', ch)
                if is_28():
                    brow.menu("NODE_MT_y_transition_bump_menu", text='', icon='PREFERENCES')
                else: brow.menu("NODE_MT_y_transition_bump_menu", text='', icon='SCRIPTWIN')

                brow.prop(ch, 'enable_transition_bump', text='')

                if chui.expand_transition_bump_settings:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')

                    bbox = row.box()
                    bbox.active = ch.enable_transition_bump
                    cccol = bbox.column(align=True)

                    #crow = cccol.row(align=True)
                    #crow.label(text='Type:') #, icon='INFO')
                    #crow.prop(ch, 'transition_bump_type', text='')

                    #crow = cccol.row(align=True)
                    #crow.label(text='Type:') #, icon='INFO')
                    #crow.prop(ch, 'transition_bump_type', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Max Height:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_distance', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 1:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 2:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_second_edge_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Affected Masks:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_chain', text='')

                    #if ch.transition_bump_type == 'CURVED_BUMP_MAP':
                    #    crow = cccol.row(align=True)
                    #    crow.label(text='Offset:') #, icon='INFO')
                    #    crow.prop(ch, 'transition_bump_curved_offset', text='')

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND'
                    crow.label(text='Flip:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_flip', text='')

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                    crow.active = not ch.transition_bump_flip
                    crow.label(text='Crease:') #, icon='INFO')
                    #if ch.transition_bump_crease:
                    #    crow.prop(ch, 'transition_bump_crease_factor', text='')
                    crow.prop(ch, 'transition_bump_crease', text='')

                    if ch.transition_bump_crease:
                        crow = cccol.row(align=True)
                        crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                        crow.label(text='Crease Factor:') #, icon='INFO')
                        crow.prop(ch, 'transition_bump_crease_factor', text='')

                        crow = cccol.row(align=True)
                        crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                        crow.label(text='Crease Power:') #, icon='INFO')
                        crow.prop(ch, 'transition_bump_crease_power', text='')

                        cccol.separator()

                    crow = cccol.row(align=True)
                    #crow.active = layer.type != 'BACKGROUND'
                    crow.label(text='Falloff:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_falloff', text='')

                    if ch.transition_bump_falloff:

                        crow = cccol.row(align=True)
                        crow.label(text='Falloff Type :') #, icon='INFO')
                        crow.prop(ch, 'transition_bump_falloff_type', text='')

                        if ch.transition_bump_falloff_type == 'EMULATED_CURVE':

                            crow = cccol.row(align=True)
                            crow.label(text='Falloff Factor:') #, icon='INFO')
                            crow.prop(ch, 'transition_bump_falloff_emulated_curve_fac', text='')
                        
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

            if custom_icon_enable:
                if chui.expand_bump_settings:
                    icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                row.prop(chui, 'expand_bump_settings', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(chui, 'expand_bump_settings', text='', emboss=True, icon='INFO')

            #else:
            if layer.type == 'GROUP':
                if chui.expand_bump_settings:
                    row.label(text='Group Normal Settings:') #, icon='INFO')
                else: row.label(text='Group Normal Settings') #, icon='INFO')
            else:
                #    row.label(text='', icon='INFO')
                if is_28():
                    split = row.split(factor=0.275)
                else: split = row.split(percentage=0.275)

                split.label(text='Type:') #, icon='INFO')
                srow = split.row(align=True)
                srow.prop(ch, 'normal_map_type', text='')
                if not chui.expand_bump_settings: #and ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
                    srow.prop(ch, 'bump_distance', text='')

            #row.label(text='', icon='BLANK1')

            #if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'} and chui.expand_bump_settings:
            if chui.expand_bump_settings:
                row = mcol.row(align=True)
                row.label(text='', icon='BLANK1')

                bbox = row.box()
                #bbox.active = layer.type != 'COLOR'
                #bbox.active = not is_valid_to_remove_bump_nodes(layer, ch)
                cccol = bbox.column(align=True)

                brow = cccol.row(align=True)
                brow.label(text='Write Height:') #, icon='INFO')
                brow.prop(ch, 'write_height', text='')

                #if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:

                if layer.type != 'GROUP':
                    brow = cccol.row(align=True)
                    brow.active = not ch.enable_transition_bump or ch.normal_map_type != 'NORMAL_MAP'
                    if ch.normal_map_type == 'BUMP_MAP':
                        brow.label(text='Max Height:') #, icon='INFO')
                    else: brow.label(text='Bump Height:') #, icon='INFO')
                    brow.prop(ch, 'bump_distance', text='')

                    #if any(layer.masks):
                    brow = cccol.row(align=True)
                    brow.active = not ch.enable_transition_bump and any(layer.masks) and not ch.write_height
                    brow.label(text='Affected Masks:') #, icon='INFO')
                    brow.prop(ch, 'transition_bump_chain', text='')

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
                    row.label(text='', icon='INFO')
                else:
                    if custom_icon_enable:
                        if chui.expand_transition_ramp_settings:
                            icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                        else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                        row.prop(chui, 'expand_transition_ramp_settings', text='', emboss=False, icon_value=icon_value)
                    else:
                        row.prop(chui, 'expand_transition_ramp_settings', text='', emboss=True, icon='MOD_MASK')
                row.label(text='Transition Ramp:')
                if ch.enable_transition_ramp and not chui.expand_transition_ramp_settings:
                    row.prop(ch, 'transition_ramp_intensity_value', text='')

                row.context_pointer_set('parent', ch)
                if is_28():
                    row.menu("NODE_MT_y_transition_ramp_menu", text='', icon='PREFERENCES')
                else: row.menu("NODE_MT_y_transition_ramp_menu", text='', icon='SCRIPTWIN')

                row.prop(ch, 'enable_transition_ramp', text='')

                if tr_ramp and chui.expand_transition_ramp_settings:
                    row = mcol.row(align=True)
                    row.active = ch.enable_transition_ramp
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    bcol = box.column(align=False)

                    brow = bcol.row(align=True)
                    brow.label(text='Intensity:')
                    brow.prop(ch, 'transition_ramp_intensity_value', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ramp_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.active = bump_ch_found
                    brow.label(text='Transition Factor:')
                    brow.prop(ch, 'transition_bump_second_fac', text='')

                    if tr_ramp.type == 'GROUP':
                        ramp = tr_ramp.node_tree.nodes.get('_RAMP')

                        #brow.prop(ch, 'ramp_intensity_value', text='')
                        bcol.template_color_ramp(ramp, "color_ramp", expand=True)
                        #row.label(text='', icon='BLANK1')

            if ch.show_transition_ao or ch.enable_transition_ao:

                # Transition AO
                row = mcol.row(align=True)
                row.active = bump_ch_found #and layer.type != 'BACKGROUND'
                if custom_icon_enable:
                    if chui.expand_transition_ao_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    row.prop(chui, 'expand_transition_ao_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(chui, 'expand_transition_ao_settings', text='', emboss=True, icon='MOD_MASK')
                row.label(text='Transition AO:')
                if ch.enable_transition_ao and not chui.expand_transition_ao_settings:
                    row.prop(ch, 'transition_ao_intensity', text='')

                row.context_pointer_set('layer', layer)
                row.context_pointer_set('parent', ch)
                if is_28():
                    row.menu("NODE_MT_y_transition_ao_menu", text='', icon='PREFERENCES')
                else: row.menu("NODE_MT_y_transition_ao_menu", text='', icon='SCRIPTWIN')

                row.prop(ch, 'enable_transition_ao', text='')

                if chui.expand_transition_ao_settings:
                    row = mcol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    box.active = bump_ch_found #and layer.type != 'BACKGROUND'
                    bcol = box.column(align=False)

                    brow = bcol.row(align=True)
                    brow.label(text='Intensity:')
                    brow.prop(ch, 'transition_ao_intensity', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'transition_ao_blend_type', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Power:')
                    brow.prop(ch, 'transition_ao_power', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Color:')
                    brow.prop(ch, 'transition_ao_color', text='')

                    brow = bcol.row(align=True)
                    brow.label(text='Inside:')
                    brow.prop(ch, 'transition_ao_inside_intensity', text='')
                    #row.label(text='', icon='BLANK1')

            # Transition Bump Intensity
            if showed_bump_ch_found:
                row = mcol.row(align=True)
                row.active = bump_ch_found
                row.label(text='', icon='INFO')
                row.label(text='Transition Factor')
                row.prop(ch, 'transition_bump_fac', text='')

            extra_separator = True

        modcol = mcol.column()
        modcol.active = layer.type != 'BACKGROUND'
        draw_modifier_stack(context, ch, root_ch.type, modcol, 
                ypui.layer_ui.channels[i], custom_icon_enable, layer)

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'}:
            row = mcol.row(align=True)

            input_settings_available = (ch.layer_input != 'ALPHA' 
                    and root_ch.colorspace == 'SRGB' and root_ch.type != 'NORMAL' )

            if input_settings_available:
                if custom_icon_enable:
                    if chui.expand_input_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    row.prop(chui, 'expand_input_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(chui, 'expand_input_settings', text='', emboss=True, icon='INFO')
            else:
                row.label(text='', icon='INFO')

            #row.label(text='', icon='INFO')
            if is_28():
                split = row.split(factor=0.275)
            else: split = row.split(percentage=0.275)

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

        if hasattr(ch, 'enable_blur'):
            row = mcol.row(align=True)
            row.label(text='', icon='INFO')
            row.label(text='Blur')
            row.prop(ch, 'enable_blur', text='')

            extra_separator = True

        if ypui.expand_channels:
            mrow.label(text='', icon='BLANK1')

        if extra_separator and i < len(layer.channels)-1:
            ccol.separator()

    if not ypui.expand_channels and ch_count == 0:
        rcol.label(text='No active channel!')

    layout.separator()

def draw_layer_masks(context, layout, layer, custom_icon_enable):
    obj = context.object
    yp = layer.id_data.yp
    ypui = context.window_manager.ypui
    lui = ypui.layer_ui

    col = layout.column()
    col.active = layer.enable_masks

    row = col.row(align=True)
    if len(layer.masks) > 0:
        if custom_icon_enable:
            if lui.expand_masks:
                icon_value = lib.custom_icons["uncollapsed_mask"].icon_id
            else: icon_value = lib.custom_icons["collapsed_mask"].icon_id
            row.prop(lui, 'expand_masks', text='', emboss=False, icon_value=icon_value)
        else: row.prop(lui, 'expand_masks', text='', emboss=True, icon='MOD_MASK')
    else: row.label(text='', icon='MOD_MASK')

    #label = 'Masks'

    num_masks = len(layer.masks)
    num_enabled_masks = len([m for m in layer.masks if m.enable])

    if num_masks == 0:
        #label += ' (0)'
        label = 'Mask' # (0)'
    elif num_enabled_masks == 0:
        label = 'Mask (0)'
    elif num_enabled_masks == 1:
        label = 'Mask (1)'
    else:
        label = 'Masks ('
        label += str(num_enabled_masks) + ')'

    if lui.expand_masks:
        label += ':'

    row.label(text=label)

    if custom_icon_enable:
        #row.menu('NODE_MT_y_add_layer_mask_menu', text='', icon_value = lib.custom_icons['add_mask'].icon_id)
        row.menu('NODE_MT_y_add_layer_mask_menu', text='', icon='ZOOMIN')
    else: 
        #row.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='MOD_MASK')
        row.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='ADD')

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

        if custom_icon_enable:
            if maskui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_mask"].icon_id
            else: icon_value = lib.custom_icons["collapsed_mask"].icon_id
            row.prop(maskui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(maskui, 'expand_content', text='', emboss=True, icon='MOD_MASK')

        mask_image = None
        mask_tree = get_mask_tree(mask)
        mask_source = mask_tree.nodes.get(mask.source)
        if mask.type == 'IMAGE':
            mask_image = mask_source.image
            if mask_image.yia.is_image_atlas:
                row.label(text=mask.name)
            else: row.label(text=mask_image.name)
        else: row.label(text=mask.name)

        if mask.type == 'IMAGE':
            row.prop(mask, 'active_edit', text='', toggle=True, icon='IMAGE_DATA')
        elif mask.type == 'VCOL':
            row.prop(mask, 'active_edit', text='', toggle=True, icon='GROUP_VCOL')

        row.context_pointer_set('mask', mask)

        if is_28():
            row.menu("NODE_MT_y_layer_mask_menu", text='', icon='PREFERENCES')
        else: row.menu("NODE_MT_y_layer_mask_menu", text='', icon='SCRIPTWIN')

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
            rrow.label(text='', icon='GROUP_VCOL')
        else:
            if custom_icon_enable:
                suffix = 'image' if mask.type == 'IMAGE' else 'texture'
                if maskui.expand_source:
                    icon_value = lib.custom_icons["uncollapsed_" + suffix].icon_id
                else: icon_value = lib.custom_icons["collapsed_" + suffix].icon_id
                rrow.prop(maskui, 'expand_source', text='', emboss=False, icon_value=icon_value)
            else:
                icon = 'IMAGE_DATA' if mask.type == 'IMAGE' else 'TEXTURE'
                rrow.prop(maskui, 'expand_source', text='', emboss=True, icon=icon)

        if mask_image:
            rrow.label(text='Source: ' + mask_image.name)
        else: rrow.label(text='Source: ' + mask.name)

        if maskui.expand_source and mask.type != 'VCOL':
            rrow = rrcol.row(align=True)
            rrow.label(text='', icon='BLANK1')
            rbox = rrow.box()
            if mask.use_temp_bake:
                rbox.context_pointer_set('parent', mask)
                rbox.operator('node.y_disable_temp_image', icon='FILE_REFRESH', text='Disable Baked Temp')
            elif mask_image:
                draw_image_props(mask_source, rbox, mask)
            elif mask.type == 'HEMI':
                draw_hemi_props(mask, mask_source, rbox)
            elif mask.type == 'OBJECT_INDEX':
                draw_object_index_props(mask, rbox)
            else: draw_tex_props(mask_source, rbox)

        # Vector row
        if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
            rrow = rrcol.row(align=True)

            if custom_icon_enable:
                if maskui.expand_vector:
                    icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                rrow.prop(maskui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
            else:
                rrow.prop(maskui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

            if is_28():
                splits = rrow.split(factor=0.3)
            else: splits = rrow.split(percentage=0.3)

            #splits = rrow.split(percentage=0.3)
            splits.label(text='Vector:')
            if mask.texcoord_type != 'UV':
                splits.prop(mask, 'texcoord_type', text='')
            else:

                if is_28():
                    rrrow = splits.split(factor=0.35, align=True)
                else: rrrow = splits.split(percentage=0.35, align=True)

                #rrrow = splits.split(percentage=0.35, align=True)
                rrrow.prop(mask, 'texcoord_type', text='')
                rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

                rrow.context_pointer_set('mask', mask)
                if is_28():
                    rrow.menu("NODE_MT_y_uv_special_menu", icon='PREFERENCES', text='')
                else: rrow.menu("NODE_MT_y_uv_special_menu", icon='SCRIPTWIN', text='')

            if maskui.expand_vector:
                rrow = rrcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                rbox.prop(mask, 'translation', text='Offset')
                rbox.prop(mask, 'rotation')
                rbox.prop(mask, 'scale')

                if mask.type == 'IMAGE' and mask.active_edit and (
                        yp.need_temp_uv_refresh or is_active_uv_map_match_entity(obj, mask)):
                    rrow = rbox.row(align=True)
                    rrow.alert = True
                    rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh UV')

        draw_mask_modifier_stack(layer, mask, rrcol, maskui, custom_icon_enable)

        rrow = rrcol.row(align=True)
        rrow.label(text='', icon='IMAGE_ZDEPTH')
        rrow.label(text='Blend:')
        rrow.prop(mask, 'blend_type', text='')
        rrow.prop(mask, 'intensity_value', text='')

        # Mask Channels row
        rrow = rrcol.row(align=True)
        if custom_icon_enable:
            if maskui.expand_channels:
                icon_value = lib.custom_icons["uncollapsed_channels"].icon_id
            else: icon_value = lib.custom_icons["collapsed_channels"].icon_id
            rrow.prop(maskui, 'expand_channels', text='', emboss=False, icon_value=icon_value)
        else:
            rrow.prop(maskui, 'expand_channels', text='', emboss=True, icon='GROUP_VERTEX')
        rrow.label(text='Channels')

        if maskui.expand_channels:

            rrow = rrcol.row()
            rrow.label(text='', icon='BLANK1')
            rbox = rrow.box()
            bcol = rbox.column(align=True)

            # Channels row
            for k, c in enumerate(mask.channels):
                rrow = bcol.row(align=True)
                root_ch = yp.channels[k]
                if custom_icon_enable:
                    rrow.label(text='', 
                            icon_value=lib.custom_icons[lib.channel_custom_icon_dict[root_ch.type]].icon_id)
                else:
                    rrow.label(text='', icon = lib.channel_icon_dict[root_ch.type])
                rrow.label(text=root_ch.name)
                rrow.prop(c, 'enable', text='')

        if i < len(layer.masks)-1:
            rcol.separator()

def draw_layers_ui(context, layout, node, custom_icon_enable):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp
    ypui = context.window_manager.ypui
    obj = context.object
    is_a_mesh = True if obj and obj.type == 'MESH' else False

    if is_28():
        uv_layers = obj.data.uv_layers
    else: uv_layers = obj.data.uv_textures

    # Check if uv is found
    uv_found = False
    if is_a_mesh and len(uv_layers) > 0: 
        uv_found = True

    box = layout.box()

    if yp.use_baked:
        col = box.column(align=False)
        #bbox = col.box()
        #bbox.alert = True
        #bbox.label(text="Disable 'Use Baked' to see layers!")
        ##bbox.operator("node.y_disable_baked_result", icon='ERROR')
        #bbox.alert = False

        if len(yp.channels) > 0:
            root_ch = yp.channels[yp.active_channel_index]

            baked = nodes.get(root_ch.baked)
            if not baked or not baked.image or root_ch.no_layer_using:
                col.label(text='No layer is using this channel !')
            else:
                row = col.row(align=True)
                #label = 'Baked Image (' + root_ch.name + '):'
                label = 'Baked ' + root_ch.name + ':'
                if custom_icon_enable:
                    icon_name = lib.channel_custom_icon_dict[root_ch.type]
                    icon_value = lib.custom_icons[icon_name].icon_id
                    row.label(text=label, icon_value=icon_value)
                else:
                    row.label(text=label, icon=lib.channel_icon_dict[root_ch.type])

                row.context_pointer_set('image', baked.image)

                if is_28():
                    row.menu("NODE_MT_y_baked_image_menu", text='', icon='PREFERENCES')
                else: row.menu("NODE_MT_y_baked_image_menu", text='', icon='SCRIPTWIN')

                #row.label(text='Baked Image (' + root_ch.name + '):')
                row = col.row(align=True)
                row.label(text='', icon='BLANK1')
                if baked.image.is_dirty:
                    label = baked.image.name + ' *'
                else: label = baked.image.name
                row.label(text=label, icon='IMAGE_DATA')

                if baked.image.packed_file:
                    row.label(text='', icon='PACKAGE')

            if root_ch.type == 'NORMAL':

                baked_normal_overlay = nodes.get(root_ch.baked_normal_overlay)
                if baked_normal_overlay and baked_normal_overlay.image:
                    row = col.row(align=True)
                    row.label(text='', icon='BLANK1')
                    if baked_normal_overlay.image.is_dirty:
                        label = baked_normal_overlay.image.name + ' *'
                    else: label = baked_normal_overlay.image.name
                    row.label(text=label, icon='IMAGE_DATA')

                    if baked_normal_overlay.image.packed_file:
                        row.label(text='', icon='PACKAGE')

                baked_disp = nodes.get(root_ch.baked_disp)
                if baked_disp and baked_disp.image:
                    row = col.row(align=True)
                    row.label(text='', icon='BLANK1')
                    if baked_disp.image.is_dirty:
                        label = baked_disp.image.name + ' *'
                    else: label = baked_disp.image.name
                    row.label(text=label, icon='IMAGE_DATA')

                    if baked_disp.image.packed_file:
                        row.label(text='', icon='PACKAGE')
        return

    if is_a_mesh and not uv_found:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_add_simple_uvs", icon='ERROR')
        row.alert = False
        return

    # If error happens, halt update can stuck on, add button to disable it
    if yp.halt_update:
        row = box.row(align=True)
        row.alert = True
        row.prop(yp, 'halt_update', text='Disable Halt Update', icon='ERROR')
        row.alert = False

    # Check if parallax is enabled
    height_root_ch = get_root_height_channel(yp)
    if height_root_ch: enable_parallax = height_root_ch.enable_parallax
    else: enable_parallax = False

    # Check duplicated layers (indicated by more than one users)
    if len(yp.layers) > 0 and (
            (not enable_parallax and get_tree(yp.layers[-1]).users > 1) or
            (enable_parallax and get_tree(yp.layers[-1]).users > 2)
            ):
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_fix_duplicated_layers", icon='ERROR')
        row.alert = False
        box.prop(ypui, 'make_image_single_user')
        return

    # Check source for missing data
    missing_data = False
    for layer in yp.layers:
        if layer.type in {'IMAGE' , 'VCOL'}:
            src = get_layer_source(layer)

            if ((layer.type == 'IMAGE' and not src.image) or 
                (layer.type == 'VCOL' and obj.type == 'MESH' 
                    and not obj.data.vertex_colors.get(src.attribute_name))
                ):
                missing_data = True
                break

        # Also check mask source
        for mask in layer.masks:
            if mask.type in {'IMAGE' , 'VCOL'}:
                mask_src = get_mask_source(mask)

                if ((mask.type == 'IMAGE' and not mask_src.image) or 
                    (mask.type == 'VCOL' and obj.type == 'MESH' 
                        and not obj.data.vertex_colors.get(mask_src.attribute_name))
                    ):
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
        #for uv in yp.uvs:
        #    uv_layer = uv_layers.get(uv.name)
        #    if not uv_layer:
        #        uv_missings.append(uv.name)

        # Check baked images
        if yp.baked_uv_name != '':
            uv_layer = uv_layers.get(yp.baked_uv_name)
            if not uv_layer and yp.baked_uv_name not in uv_missings:
                uv_missings.append(yp.baked_uv_name)

        # Check main uv of height channel
        height_ch = get_root_height_channel(yp)
        if height_ch and height_ch.main_uv != '':
            uv_layer = uv_layers.get(height_ch.main_uv)
            if not uv_layer and height_ch.main_uv not in uv_missings:
                uv_missings.append(height_ch.main_uv)

        # Check layer and mask uv
        for layer in yp.layers:
            if layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
                uv_layer = uv_layers.get(layer.uv_name)
                if not uv_layer and layer.uv_name not in uv_missings:
                    uv_missings.append(layer.uv_name)

            for mask in layer.masks:
                if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX'}:
                    uv_layer = uv_layers.get(mask.uv_name)
                    if not uv_layer and mask.uv_name not in uv_missings:
                        uv_missings.append(mask.uv_name)

        for uv_name in uv_missings:
            row = box.row(align=True)
            row.alert = True
            title = 'UV ' + uv_name + ' is missing or renamed!'
            row.operator("node.y_fix_missing_uv", text=title, icon='ERROR').source_uv_name = uv_name
            row.alert = False

    # Check if tangent refresh is needed
    need_tangent_refresh = False
    if height_root_ch and yp.enable_tangent_sign_hacks:
        for uv in yp.uvs:
            if TANGENT_SIGN_PREFIX + uv.name not in obj.data.vertex_colors:
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
    #entity = None

    if len(yp.layers) > 0:
        layer = yp.layers[yp.active_layer_index]
        #layer = entity = yp.layers[yp.active_layer_index]

        if layer:
            # Check for active mask
            for i, m in enumerate(layer.masks):
                if m.active_edit:
                    #mask = entity = m
                    mask = m
                    mask_idx = i
                    source = get_mask_source(m)
                    if m.type == 'IMAGE':
                        #mask_tree = get_mask_tree(m)
                        #source = mask_tree.nodes.get(m.source)
                        #image = source.image
                        mask_image = source.image
                    elif m.type == 'VCOL' and is_a_mesh:
                        mask_vcol = obj.data.vertex_colors.get(source.attribute_name)

            # Use layer image if there is no mask image
            #if not mask:
            layer_tree = get_tree(layer)
            source = get_layer_source(layer, layer_tree)
            if layer.type == 'IMAGE':
                image = source.image
            elif layer.type == 'VCOL' and is_a_mesh:
                vcol = obj.data.vertex_colors.get(source.attribute_name)

    # Set pointer for active layer and image
    if layer: box.context_pointer_set('layer', layer)
    if mask_image: box.context_pointer_set('image', mask_image)
    elif image: box.context_pointer_set('image', image)
    #if entity: box.context_pointer_set('entity', entity)

    col = box.column()

    row = col.row()
    rcol = row.column()
    if len(yp.layers) > 0:
        pcol = rcol.column()
        if yp.layer_preview_mode: pcol.alert = True
        if custom_icon_enable:
            pcol.prop(yp, 'layer_preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')
        else: pcol.prop(yp, 'layer_preview_mode', text='Preview Mode', icon='HIDE_OFF')

    rcol.template_list("NODE_UL_YPaint_layers", "", yp,
            "layers", yp, "active_layer_index", rows=5, maxrows=5)  

    rcol = row.column(align=True)
    if is_28():
        rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ADD')
    else: rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ZOOMIN')

    if layer:

        if has_childrens(layer):

            if is_28():
                rcol.operator("node.y_remove_layer_menu", icon='REMOVE', text='')
            else: rcol.operator("node.y_remove_layer_menu", icon='ZOOMOUT', text='')

        else: 
            if is_28():
                c = rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
            else: c = rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

            c.remove_childs = False

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

        if is_28():
            rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
        else: rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

        rcol.operator("node.y_move_layer", text='', icon='TRIA_UP').direction = 'UP'
        rcol.operator("node.y_move_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'

    rcol.menu("NODE_MT_y_layer_list_special_menu", text='', icon='DOWNARROW_HLT')

    if layer:
        layer_tree = get_tree(layer)

        col = box.column()
        col.active = layer.enable and not is_parent_hidden(layer)

        # Get active vcol
        if mask_vcol: active_vcol = mask_vcol
        elif vcol: active_vcol = vcol
        else: active_vcol = None

        if (
            (image and image.colorspace_settings.name != 'Linear') or 
            (mask_image and mask_image.colorspace_settings.name != 'Linear')
            ):
            col.alert = True
            col.operator('node.y_use_linear_color_space', text='Please Use Linear Color Space', icon='ERROR')
            col.alert = False

        if obj.type == 'MESH' and active_vcol: # and layer.enable:

            if active_vcol != obj.data.vertex_colors.active:
                col.alert = True
                col.operator('mesh.y_set_active_vcol', text='Fix Active Vcol Mismatch!', icon='ERROR').vcol_name = active_vcol.name
                col.alert = False

            if obj.mode == 'EDIT':
                ve = context.scene.ve_edit

                bbox = col.box()
                ccol = bbox.column()
                row = ccol.row(align=True)
                row.label(text='', icon='GROUP_VCOL')
                row.label(text='Fill ' + obj.data.vertex_colors.active.name + ':')
                row = ccol.row(align=True)
                #row.prop(ve, 'fill_mode', text='') #, expand=True)
                #row.separator()
                row.operator('mesh.y_vcol_fill', text='White').color_option = 'WHITE'
                row.operator('mesh.y_vcol_fill', text='Black').color_option = 'BLACK'
                row.separator()
                row.operator('mesh.y_vcol_fill', text='Color').color_option = 'CUSTOM'

                row.prop(ve, "color", text="", icon='COLOR')

        # Source
        draw_layer_source(context, col, layer, layer_tree, source, image, vcol, is_a_mesh, custom_icon_enable)

        # Channels
        draw_layer_channels(context, col, layer, layer_tree, image, custom_icon_enable)

        # Masks
        draw_layer_masks(context, col, layer, custom_icon_enable)

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
        print('INFO: Scene is updated at', '{:0.2f}'.format((time.time() - float(wm.yptimer.time)) * 1000), 'ms!')
        wm.yptimer.time = ''

    # Update ui props first
    update_yp_ui()

    if hasattr(lib, 'custom_icons'):
        custom_icon_enable = True
    else: custom_icon_enable = False

    node = get_active_ypaint_node()
    ypui = wm.ypui

    layout = self.layout

    #layout.operator("node.y_debug_mesh", icon='MESH_DATA')
    #layout.operator("node.y_test_ray", icon='MESH_DATA')

    icon = 'TRIA_DOWN' if ypui.show_object else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_object', emboss=False, text='', icon=icon)
    if obj:
        row.label(text='Object: ' + obj.name)
    else: row.label(text='Object: -')

    if ypui.show_object:
        box = layout.box()
        col = box.column()
        col.prop(obj, 'pass_index')
        #row = box.row()

    icon = 'TRIA_DOWN' if ypui.show_materials else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_materials', emboss=False, text='', icon=icon)
    if mat:
        row.label(text='Material: ' + mat.name)
    else: row.label(text='Material: -')

    if ypui.show_materials:
        is_sortable = len(obj.material_slots) > 1
        rows = 2
        if (is_sortable):
            rows = 4
        box = layout.box()
        row = box.row()
        row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index", rows=rows)
        col = row.column(align=True)
        col.operator("object.material_slot_add", icon='ADD', text="")
        col.operator("object.material_slot_remove", icon='REMOVE', text="")

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

        #split = box.split(factor=0.65)

        #if obj:
        #    split.template_ID(obj, "active_material", new="material.new")
        #    row = split.row()

        #    if slot:
        #        row.prop(slot, "link", text="")
        #    else:
        #        row.label()
        #elif mat:
        #    split.template_ID(space, "pin_id")
        #    split.separator()

    if not node:
        layout.label(text="No active " + ADDON_TITLE + " node!", icon='ERROR')
        layout.operator("node.y_quick_ypaint_node_setup", icon='NODETREE')

        return

    group_tree = node.node_tree
    nodes = group_tree.nodes
    yp = group_tree.yp

    #layout.label(text='Active: ' + node.node_tree.name, icon='NODETREE')
    row = layout.row(align=True)
    row.label(text='', icon='NODETREE')
    #row.label(text='Active: ' + node.node_tree.name)
    row.label(text=node.node_tree.name)
    #row.prop(node.node_tree, 'name', text='')

    if is_28():
        row.menu("NODE_MT_ypaint_special_menu", text='', icon='PREFERENCES')
    else: row.menu("NODE_MT_ypaint_special_menu", text='', icon='SCRIPTWIN')

    # Check for baked node
    baked_found = False
    for ch in yp.channels:
        baked = nodes.get(ch.baked)
        if baked: 
            baked_found = True

    icon = 'TRIA_DOWN' if ypui.show_channels else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_channels', emboss=False, text='', icon=icon)
    row.label(text='Channels')

    if ypui.show_channels:
        draw_root_channels_ui(context, layout, node, custom_icon_enable)

    icon = 'TRIA_DOWN' if ypui.show_layers else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_layers', emboss=False, text='', icon=icon)
    row.label(text='Layers')

    height_root_ch = get_root_height_channel(yp)

    if (area.type == 'VIEW_3D' and area.spaces[0].shading.type == 'RENDERED' 
            and is_28() and height_root_ch
            and scene.render.engine == 'CYCLES' and not yp.enable_tangent_sign_hacks):
        rrow = row.row(align=True)
        rrow.alert = True
        rrow.prop(yp, 'enable_tangent_sign_hacks', text='Fix Tangent', icon='ERROR', toggle=True)
        rrow.alert = False

    scenario_1 = (yp.enable_tangent_sign_hacks and area.type == 'VIEW_3D' and 
            area.spaces[0].shading.type == 'RENDERED' and scene.render.engine == 'CYCLES')

    if scenario_1:
        row.operator('node.y_refresh_tangent_sign_vcol', icon='FILE_REFRESH', text='Tangent')

    if baked_found or yp.use_baked:
        row.prop(yp, 'use_baked', toggle=True, text='Use Baked')

    if ypui.show_layers :
        draw_layers_ui(context, layout, node, custom_icon_enable)

    # Stats
    icon = 'TRIA_DOWN' if ypui.show_stats else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_stats', emboss=False, text='', icon=icon)
    row.label(text='Stats')

    if ypui.show_stats:

        images = []
        vcols = []
        num_gen_texs = 0

        for layer in yp.layers:
            if not layer.enable: continue
            if layer.type == 'IMAGE':
                src = get_layer_source(layer)
                if src.image and src.image not in images:
                    images.append(src.image)
            elif layer.type == 'VCOL':
                src = get_layer_source(layer)
                if src.attribute_name != '' and src.attribute_name not in vcols:
                    vcols.append(src.attribute_name)
            elif layer.type not in {'COLOR', 'BACKGROUND', 'GROUP'}:
                num_gen_texs += 1

            if not layer.enable_masks: continue

            for mask in layer.masks:
                if not mask.enable: continue
                if mask.type == 'IMAGE':
                    src = get_mask_source(mask)
                    if src.image and src.image not in images:
                        images.append(src.image)
                elif mask.type == 'VCOL':
                    src = get_mask_source(mask)
                    if src.attribute_name != '' and src.attribute_name not in vcols:
                        vcols.append(src.attribute_name)
                else:
                    num_gen_texs += 1

        box = layout.box()
        col = box.column()
        #col = layout.column(align=True)
        col.label(text='Number of Images: ' + str(len(images)), icon='IMAGE_DATA')
        col.label(text='Number of Vertex Colors: ' + str(len(vcols)), icon='GROUP_VCOL')
        col.label(text='Number of Generated Textures: ' + str(num_gen_texs), icon='TEXTURE')

        #col.operator('node.y_new_image_atlas_segment_test', icon='IMAGE_DATA')
        #col.operator('node.y_uv_transform_test', icon='GROUP_UVS')

    # Hide support this addon panel for now
    return

    icon = 'TRIA_DOWN' if ypui.show_support else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ypui, 'show_support', emboss=False, text='', icon=icon)
    row.label(text='Support This Addon!')

    if ypui.show_support:
        box = layout.box()
        col = box.column()
        col.alert = True
        col.operator('wm.url_open', text='Become A Patron!', icon='POSE_DATA').url = 'https://www.patreon.com/ucupumar'
        col.alert = False
        col.label(text='Patron List (June 2018):')
        col = col.column(align=True)
        col.operator('wm.url_open', text='masterxeon1001').url = 'https://masterxeon1001.com/'
        col.operator('wm.url_open', text='Stephen Bates').url = 'https://twitter.com/pharion3d'
        col.operator('wm.url_open', text='Chala').url = 'https://steamcommunity.com/id/BlenderNova/'


class NODE_PT_YPaint(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = ADDON_TITLE + " " + get_current_version_str()
    bl_region_type = 'TOOLS'
    #bl_category = ADDON_TITLE

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class NODE_PT_YPaintUI(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = ADDON_TITLE + " " + get_current_version_str()
    bl_region_type = 'UI'
    bl_category = ADDON_TITLE

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_YPaint_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = ADDON_TITLE + " " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = ADDON_TITLE

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_YPaint_ui(bpy.types.Panel):
    bl_label = ADDON_TITLE + " " + get_current_version_str()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = ADDON_TITLE
    #bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class NODE_UL_YPaint_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_ypaint_node()
        inputs = group_node.inputs
        yp = group_node.node_tree.yp

        row = layout.row()

        if hasattr(lib, 'custom_icons'):
            icon_value = lib.custom_icons[lib.channel_custom_icon_dict[item.type]].icon_id
            row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)
        else: row.prop(item, 'name', text='', emboss=False, icon=lib.channel_icon_dict[item.type])

        if not yp.use_baked or item.no_layer_using:
            if item.type == 'RGB':
                row = row.row(align=True)

            if len(inputs[item.io_index].links) == 0:
                if item.type == 'VALUE':
                    row.prop(inputs[item.io_index], 'default_value', text='') #, emboss=False)
                elif item.type == 'RGB':
                    row.prop(inputs[item.io_index], 'default_value', text='', icon='COLOR')
            else:
                row.label(text='', icon='LINKED')

            if item.type=='RGB' and item.enable_alpha:
                if len(inputs[item.io_index+1].links) == 0:
                    row.prop(inputs[item.io_index+1], 'default_value', text='')
                else: row.label(text='', icon='LINKED')

class NODE_UL_YPaint_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_tree = item.id_data
        yp = group_tree.yp
        nodes = group_tree.nodes
        layer = item
        layer_tree = get_tree(layer)
        obj = context.object

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
        #    vcol = obj.data.vertex_colors.get(source.attribute_name)

        # Try to get image masks
        editable_masks = []
        active_image_mask = None
        for m in layer.masks:
            if m.type in {'IMAGE', 'VCOL'}:
                editable_masks.append(m)
                if m.active_edit:
                    active_image_mask = m

        if layer.parent_idx != -1:
            depth = get_layer_depth(layer)
            for i in range(depth):
                row.label(text='', icon='BLANK1')

        # Image icon
        if len(editable_masks) == 0:
            row = master.row(align=True)
            row.active = is_hidden
            if image and image.yia.is_image_atlas: 
                row.prop(layer, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            elif image: row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            #elif vcol: row.prop(vcol, 'name', text='', emboss=False, icon='GROUP_VCOL')
            elif layer.type == 'VCOL': row.prop(layer, 'name', text='', emboss=False, icon='GROUP_VCOL')
            elif layer.type == 'HEMI': 
                if is_28(): row.prop(layer, 'name', text='', emboss=False, icon='LIGHT')
                else: row.prop(layer, 'name', text='', emboss=False, icon='LAMP')
            elif layer.type == 'COLOR': row.prop(layer, 'name', text='', emboss=False, icon='COLOR')
            elif layer.type == 'BACKGROUND': row.prop(layer, 'name', text='', emboss=False, icon='IMAGE_RGB_ALPHA')
            elif layer.type == 'GROUP': row.prop(layer, 'name', text='', emboss=False, icon='FILE_FOLDER')
            else: row.prop(layer, 'name', text='', emboss=False, icon='TEXTURE')
        else:
            if active_image_mask:
                row.active = False
                if image: 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, 
                            icon_value=image.preview.icon_id)
                #elif vcol: 
                elif layer.type == 'VCOL': 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='GROUP_VCOL')
                elif layer.type == 'COLOR': 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='COLOR')
                elif layer.type == 'HEMI': 
                    if is_28():
                        row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='LIGHT')
                    else: row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='LAMP')
                elif layer.type == 'BACKGROUND': 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='IMAGE_RGB_ALPHA')
                elif layer.type == 'GROUP': 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='FILE_FOLDER')
                else: 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='TEXTURE')
            else:
                if image: 
                    row.label(text='', icon_value=image.preview.icon_id)
                #elif vcol: 
                elif layer.type == 'VCOL': 
                    row.label(text='', icon='GROUP_VCOL')
                elif layer.type == 'COLOR': 
                    row.label(text='', icon='COLOR')
                elif layer.type == 'HEMI': 
                    if is_28(): row.label(text='', icon='LIGHT')
                    else: row.label(text='', icon='LAMP')
                elif layer.type == 'BACKGROUND': 
                    row.label(text='', icon='IMAGE_RGB_ALPHA')
                elif layer.type == 'GROUP': 
                    row.label(text='', icon='FILE_FOLDER')
                else: 
                    row.label(text='', icon='TEXTURE')

        # Image mask icons
        active_mask_image = None
        active_vcol_mask = None
        mask = None
        for m in editable_masks:
            mask_tree = get_mask_tree(m)
            row = master.row(align=True)
            row.active = m.active_edit
            if m.active_edit:
                mask = m
                src = mask_tree.nodes.get(m.source)
                if m.type == 'IMAGE':
                    active_mask_image = src.image
                    row.label(text='', icon_value=src.image.preview.icon_id)
                elif m.type == 'VCOL':
                    #active_vcol_mask = obj.data.vertex_colors.get(src.attribute_name)
                    active_vcol_mask = m
                    row.label(text='', icon='GROUP_VCOL')
            else:
                if m.type == 'IMAGE':
                    src = mask_tree.nodes.get(m.source)
                    row.prop(m, 'active_edit', text='', emboss=False, icon_value=src.image.preview.icon_id)
                elif m.type == 'VCOL':
                    row.prop(m, 'active_edit', text='', emboss=False, icon='GROUP_VCOL')

        # Debug parent
        #row.label(text=str(index) + ' (' + str(layer.parent_idx) + ')')

        # Active image/layer label
        if len(editable_masks) > 0:
            row = master.row(align=True)
            row.active = is_hidden
            if active_mask_image:
                if active_mask_image.yia.is_image_atlas:
                    row.prop(mask, 'name', text='', emboss=False)
                else: row.prop(active_mask_image, 'name', text='', emboss=False)
            elif active_vcol_mask:
                row.prop(active_vcol_mask, 'name', text='', emboss=False)
            else: 
                if image and not image.yia.is_image_atlas: 
                    row.prop(image, 'name', text='', emboss=False)
                else: row.prop(layer, 'name', text='', emboss=False)

        row = master.row(align=True)

        # Active image
        if active_mask_image: active_image = active_mask_image
        elif image: active_image = image
        else: active_image = None

        if active_image:
            # Asterisk icon to indicate dirty image
            if active_image.is_dirty:
                if hasattr(lib, 'custom_icons'):
                    row.label(text='', icon_value=lib.custom_icons['asterisk'].icon_id)
                else: row.label(text='', icon='FREEZE')

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
        if len(layer.masks) > 0:
            row = master.row()
            #row.active = is_hidden
            row.active = layer.enable_masks
            row.prop(layer, 'enable_masks', emboss=False, text='', icon='MOD_MASK')

        # Layer visibility
        row = master.row()
        row.active = is_hidden
        if hasattr(lib, 'custom_icons'):
            if layer.enable: eye_icon = 'RESTRICT_VIEW_OFF'
            else: eye_icon = 'RESTRICT_VIEW_ON'
        else:
            if layer.enable: eye_icon = 'HIDE_OFF'
            else: eye_icon = 'HIDE_ON'
        row.prop(layer, 'enable', emboss=False, text='', icon=eye_icon)

class YPaintSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_ypaint_special_menu"
    bl_label = ADDON_TITLE + " Special Menu"
    bl_description = ADDON_TITLE + " Special Menu"

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

        col.operator('node.y_bake_channels', text='Bake All Channels', icon='RENDER_STILL')
        col.operator('node.y_rename_ypaint_tree', text='Rename', icon='GREASEPENCIL')

        col.separator()

        col.label(text='Active:', icon='NODETREE')
        for n in get_list_of_ypaint_nodes(mat):
            if n.name == node.name:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            #row = col.row()
            col.operator('node.y_change_active_ypaint_node', text=n.node_tree.name, icon=icon).name = n.name

        col = row.column()
        col.label(text='Options:')
        col.prop(yp, 'enable_backface_always_up')
        col.separator()
        col.label(text='Performance Options:')
        col.prop(ypui, 'disable_auto_temp_uv_update')
        #col.prop(yp, 'disable_quick_toggle')
        col.separator()
        col.label(text='Hacks:')
        col.prop(yp, 'enable_tangent_sign_hacks')

class YNewLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_layer_menu"
    bl_description = 'Add New Layer'
    bl_label = "New Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        row = self.layout.row()
        col = row.column()
        #col = self.layout.column(align=True)
        #col.context_pointer_set('group_node', context.group_node)
        #col.label(text='Image:')
        col.operator("node.y_new_layer", text='New Image', icon='IMAGE_DATA').type = 'IMAGE'

        #col.separator()

        col.operator("node.y_open_image_to_layer", text='Open Image')
        if is_28():
            #col.operator("node.y_open_image_to_layer", text='Open Image', icon='FILEBROWSER')
            col.operator("node.y_open_available_data_to_layer", text='Open Available Image').type = 'IMAGE'
        else:
            #col.operator("node.y_open_image_to_layer", text='Open Image', icon='IMASEL')
            col.operator("node.y_open_available_data_to_layer", text='Open Available Image').type = 'IMAGE'

        col.separator()

        col.operator("node.y_new_layer", icon='FILE_FOLDER', text='Layer Group').type = 'GROUP'
        col.separator()

        #col.label(text='Vertex Color:')
        col.operator("node.y_new_layer", icon='GROUP_VCOL', text='New Vertex Color').type = 'VCOL'
        col.operator("node.y_open_available_data_to_layer", text='Open Available Vertex Color').type = 'VCOL'
        col.separator()

        #col.label(text='Solid Color:')
        c = col.operator("node.y_new_layer", icon='COLOR', text='Solid Color')
        c.type = 'COLOR'
        c.add_mask = False

        c = col.operator("node.y_new_layer", text='Solid Color w/ Image Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        if is_28():
            c = col.operator("node.y_new_layer", text='Solid Color w/ Vertex Color Mask')
        else: c = col.operator("node.y_new_layer", text='Solid Color w/ Vertex Color Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'VCOL'

        col.separator()

        #col.label(text='Background:')
        c = col.operator("node.y_new_layer", icon='IMAGE_RGB_ALPHA', text='Background w/ Image Mask')
        c.type = 'BACKGROUND'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        if is_28():
            c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')
        else: c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')

        c.type = 'BACKGROUND'
        c.add_mask = True
        c.mask_type = 'VCOL'

        col.separator()

        c = col.operator("node.y_duplicate_layer", icon='COPY_ID', text='New Duplicated Layer')
        c.make_image_blank = False
        c = col.operator("node.y_duplicate_layer", icon='COPY_ID', text='New Blank Layer with copied setup')
        c.make_image_blank = True

        col = row.column()
        #col.label(text='Generated:')
        col.operator("node.y_new_layer", icon='TEXTURE', text='Brick').type = 'BRICK'
        col.operator("node.y_new_layer", text='Checker').type = 'CHECKER'
        col.operator("node.y_new_layer", text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_layer", text='Magic').type = 'MAGIC'
        col.operator("node.y_new_layer", text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_layer", text='Noise').type = 'NOISE'
        col.operator("node.y_new_layer", text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_layer", text='Wave').type = 'WAVE'

        col.separator()
        if is_28():
            col.operator("node.y_new_layer", icon='LIGHT', text='Fake Lighting').type = 'HEMI'
        else: col.operator("node.y_new_layer", icon='LAMP', text='Fake Lighting').type = 'HEMI'

        col = row.column()
        c = col.operator("node.y_bake_to_layer", icon='RENDER_STILL', text='Ambient Occlusion')
        c.type = 'AO'
        c.target_type = 'LAYER'

        c = col.operator("node.y_bake_to_layer", text='Pointiness')
        c.type = 'POINTINESS'
        c.target_type = 'LAYER'

        c = col.operator("node.y_bake_to_layer", text='Cavity')
        c.type = 'CAVITY'
        c.target_type = 'LAYER'

class YBakedImageMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_baked_image_menu"
    bl_label = "Baked Image Menu"
    bl_description = "Baked Image Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        col = self.layout.column()
        #col.label('Ya dun sai')
        col.operator('node.y_pack_image', icon='PACKAGE')
        col.operator('node.y_save_image', icon='FILE_TICK')

        if context.image.packed_file:
            col.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').unpack = True
        else: col.operator('node.y_save_as_image', text='Save As Image')

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

        row = self.layout.row()
        col = row.column()
        
        col.operator('node.y_merge_layer', text='Merge Layer Up', icon='TRIA_UP').direction = 'UP'
        col.operator('node.y_merge_layer', text='Merge Layer Down', icon='TRIA_DOWN').direction = 'DOWN'

        col.separator()

        col.prop(yp, 'layer_preview_mode', text='Layer Only Viewer')

        col = row.column()

        #col.context_pointer_set('space_data', context.screen.areas[6].spaces[0])
        #col.operator('image.save_as', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image:
            col.label(text='Active Image: ' + context.image.name, icon='IMAGE_DATA')
        else:
            col.label(text='No active image')

        #col.separator()
        #col.operator('node.y_transfer_layer_uv', text='Transfer Active Layer UV', icon='GROUP_UVS')
        #col.operator('node.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon='GROUP_UVS')
        
        #if hasattr(context, 'image') and context.image:
        col.separator()
        op = col.operator('node.y_resize_image', text='Resize Image', icon='FULLSCREEN_ENTER')
        if hasattr(context, 'layer'):
            op.layer_name = context.layer.name
        if hasattr(context, 'image'):
            op.image_name = context.image.name

        col.separator()
        col.operator('node.y_pack_image', icon='PACKAGE')
        col.operator('node.y_save_image', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image.packed_file:
            col.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').unpack = True
        else:
            if is_28():
                col.operator('node.y_save_as_image', text='Save As Image')
                col.operator('node.y_save_pack_all', text='Save/Pack All')
            else: 
                col.operator('node.y_save_as_image', text='Save As Image', icon='SAVE_AS')
                col.operator('node.y_save_pack_all', text='Save/Pack All', icon='FILE_TICK')

        col.separator()
        col.operator("node.y_reload_image", icon='FILE_REFRESH')
        col.separator()
        col.operator("node.y_invert_image", icon='IMAGE_ALPHA')

        #if hasattr(context, 'entity') and context.entity:
        #    col = row.column()
        #    col.label(text=context.entity.name, icon=get_layer_type_icon(context.entity.type))

class YUVSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_uv_special_menu"
    bl_label = "UV Special Menu"
    bl_description = "UV Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def draw(self, context):
        self.layout.operator('node.y_transfer_layer_uv', text='Transfer UV', icon='GROUP_UVS')
        self.layout.operator('node.y_transfer_some_layer_uv', text='Transfer All Layers & Masks UV', icon='GROUP_UVS')

class YModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_modifier_menu"
    bl_label = "Modifier Menu"
    bl_description = "Modifier Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'modifier') and hasattr(context, 'parent') and get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        op = col.operator('node.y_move_ypaint_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_ypaint_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if is_28():
            op = col.operator('node.y_remove_ypaint_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_ypaint_modifier', icon='ZOOMOUT', text='Remove Modifier')

        #if hasattr(context, 'layer') and context.modifier.type in {'RGB_TO_INTENSITY', 'OVERRIDE_COLOR'}:
        #    col.separator()
        #    col.prop(context.modifier, 'shortcut', text='Shortcut on layer list')

class YMaskModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_mask_modifier_menu"
    bl_label = "Mask Modifier Menu"
    bl_description = "Mask Modifier Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'modifier') and hasattr(context, 'mask') and hasattr(context, 'layer')

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        op = col.operator('node.y_move_mask_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_mask_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()

        if is_28():
            op = col.operator('node.y_remove_mask_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_mask_modifier', icon='ZOOMOUT', text='Remove Modifier')

class YTransitionBumpMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_bump_menu"
    bl_label = "Transition Bump Menu"
    bl_description = "Transition Bump Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        #col.label(text=context.parent.path_from_id())

        if is_28():
            col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='REMOVE').type = 'BUMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='ZOOMOUT').type = 'BUMP'

class YTransitionRampMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ramp_menu"
    bl_label = "Transition Ramp Menu"
    bl_description = "Transition Ramp Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_ypaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col.prop(context.parent, 'transition_ramp_intensity_unlink', text='Unlink Ramp with Channel Intensity')

        col.separator()

        if is_28():
            col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='REMOVE').type = 'RAMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='ZOOMOUT').type = 'RAMP'

class YTransitionAOMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ao_menu"
    bl_label = "Transition AO Menu"
    bl_description = "Transition AO Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_ypaint_node()
        return hasattr(context, 'parent') and hasattr(context, 'layer')

    def draw(self, context):
        layout = self.layout

        trans_bump = get_transition_bump_channel(context.layer)
        trans_bump_flip = (trans_bump and trans_bump.transition_bump_flip) or context.layer.type == 'BACKGROUND'

        col = layout.column()
        col.active = not trans_bump_flip
        col.prop(context.parent, 'transition_ao_intensity_unlink', text='Unlink AO with Channel Intensity')

        col.separator()

        col = layout.column()
        if is_28():
            col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='REMOVE').type = 'AO'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='ZOOMOUT').type = 'AO'

class YAddLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_layer_mask_menu"
    bl_description = 'Add Layer Mask'
    bl_label = "Add Layer Mask"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')
        #node =  get_active_ypaint_node()
        #return node and len(node.node_tree.yp.layers) > 0

    def draw(self, context):
        #print(context.layer)
        layout = self.layout
        row = layout.row()
        col = row.column(align=True)
        col.context_pointer_set('layer', context.layer)

        col.label(text='Image Mask:')
        col.operator('node.y_new_layer_mask', icon='IMAGE_DATA', text='New Image Mask').type = 'IMAGE'
        if is_28():
            col.operator('node.y_open_image_as_mask', text='Open Image as Mask', icon='FILEBROWSER')
            col.operator('node.y_open_available_data_as_mask', text='Open Available Image as Mask', icon='FILEBROWSER').type = 'IMAGE'
        else:
            col.operator('node.y_open_image_as_mask', text='Open Image as Mask', icon='IMASEL')
            col.operator('node.y_open_available_data_as_mask', text='Open Available Image as Mask', icon='IMASEL').type = 'IMAGE'
        #col.label(text='Not implemented yet!', icon='ERROR')
        col.separator()
        #col.label(text='Open Mask:')
        #col.label(text='Open Other Mask', icon='MOD_MASK')

        col.label(text='Vertex Color Mask:')
        col.operator('node.y_new_layer_mask', text='New Vertex Color Mask', icon='GROUP_VCOL').type = 'VCOL'
        col.operator('node.y_open_available_data_as_mask', text='Open Available Vertex Color as Mask', icon='GROUP_VCOL').type = 'VCOL'

        col = row.column(align=True)
        #col.separator()
        col.label(text='Generated Mask:')
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Brick').type = 'BRICK'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Checker').type = 'CHECKER'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Magic').type = 'MAGIC'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Noise').type = 'NOISE'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_layer_mask", icon='TEXTURE', text='Wave').type = 'WAVE'

        col.separator()
        if is_28():
            col.operator("node.y_new_layer_mask", icon='LIGHT', text='Fake Lighting').type = 'HEMI'
        else: col.operator("node.y_new_layer_mask", icon='LAMP', text='Fake Lighting').type = 'HEMI'

        col.separator()
        col.operator("node.y_new_layer_mask", icon='OBJECT_DATA', text='Object Index').type = 'OBJECT_INDEX'

        col = row.column()
        c = col.operator("node.y_bake_to_layer", icon='RENDER_STILL', text='Ambient Occlusion')
        c.type = 'AO'
        c.target_type = 'MASK'

        c = col.operator("node.y_bake_to_layer", text='Pointiness')
        c.type = 'POINTINESS'
        c.target_type = 'MASK'

        c = col.operator("node.y_bake_to_layer", text='Cavity')
        c.type = 'CAVITY'
        c.target_type = 'MASK'

class YLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_mask_menu"
    bl_description = 'Layer Mask Menu'
    bl_label = "Layer Mask Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'layer')

    def draw(self, context):
        #print(context.mask)
        mask = context.mask
        layer = context.layer
        layer_tree = get_tree(layer)
        layout = self.layout

        row = layout.row()
        col = row.column(align=True)

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

        op = col.operator('node.y_transfer_layer_uv', icon='GROUP_UVS', text='Transfer UV')

        col.separator()

        if is_28():
            col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='REMOVE')
        else: col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='ZOOMOUT')

        col = row.column(align=True)
        col.label(text='Add Modifier')

        col.operator('node.y_new_mask_modifier', text='Invert', icon='MODIFIER').type = 'INVERT'
        col.operator('node.y_new_mask_modifier', text='Ramp', icon='MODIFIER').type = 'RAMP'
        col.operator('node.y_new_mask_modifier', text='Curve', icon='MODIFIER').type = 'CURVE'

        col = row.column(align=True)
        col.context_pointer_set('parent', mask)
        col.label(text='Advanced')
        if not mask.use_temp_bake:
            col.operator('node.y_bake_temp_image', text='Bake Temp Image', icon='RENDER_STILL')
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

class YAddModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_modifier_menu"
    bl_label = "Add Modifier Menu"
    bl_description = 'Add New Modifier'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_ypaint_node()

    def draw(self, context):
        row = self.layout.row()

        col = row.column()

        col.label(text='Add Modifier')
        ## List the items
        for mt in Modifier.modifier_type_items:
            col.operator('node.y_new_ypaint_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if m:

            ch = context.parent
            yp = ch.id_data.yp
            root_ch = yp.channels[int(m.group(2))]

            col = row.column()
            col.label(text='Transition Effects')
            if root_ch.type == 'NORMAL':
                col.operator('node.y_show_transition_bump', text='Transition Bump', icon='IMAGE_RGB_ALPHA')
            else:
                col.operator('node.y_show_transition_ramp', text='Transition Ramp', icon='IMAGE_RGB_ALPHA')
                col.operator('node.y_show_transition_ao', text='Transition AO', icon='IMAGE_RGB_ALPHA')

            #col.label(context.parent.path_from_id())

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
        return hasattr(context, 'parent') and get_active_ypaint_node()

    def draw(self, context):
        yp = context.parent.id_data.yp
        ypui = context.window_manager.ypui

        row = self.layout.row()

        if context.parent.type != 'GROUP':
            col = row.column()
            col.label(text='Add Modifier')
            ## List the modifiers
            for mt in Modifier.modifier_type_items:
                col.operator('node.y_new_ypaint_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

        col = row.column()
        col.label(text='Change Layer Type')
        col.operator('node.y_replace_layer_type', text='Image', icon='IMAGE_DATA').type = 'IMAGE'

        col.operator('node.y_replace_layer_type', text='Vertex Color', icon='GROUP_VCOL').type = 'VCOL'
        col.operator('node.y_replace_layer_type', text='Solid Color', icon='COLOR').type = 'COLOR'
        col.operator('node.y_replace_layer_type', text='Background', icon='IMAGE_RGB_ALPHA').type = 'BACKGROUND'
        col.operator('node.y_replace_layer_type', text='Group', icon='FILE_FOLDER').type = 'GROUP'

        col.separator()
        col.operator('node.y_replace_layer_type', text='Brick', icon='TEXTURE').type = 'BRICK'
        col.operator('node.y_replace_layer_type', text='Checker', icon='TEXTURE').type = 'CHECKER'
        col.operator('node.y_replace_layer_type', text='Gradient', icon='TEXTURE').type = 'GRADIENT'
        col.operator('node.y_replace_layer_type', text='Magic', icon='TEXTURE').type = 'MAGIC'
        col.operator('node.y_replace_layer_type', text='Musgrave', icon='TEXTURE').type = 'MUSGRAVE'
        col.operator('node.y_replace_layer_type', text='Noise', icon='TEXTURE').type = 'NOISE'
        col.operator('node.y_replace_layer_type', text='Voronoi', icon='TEXTURE').type = 'VORONOI'
        col.operator('node.y_replace_layer_type', text='Wave', icon='TEXTURE').type = 'WAVE'

        col.separator()
        if is_28():
            col.operator("node.y_replace_layer_type", icon='LIGHT', text='Fake Lighting').type = 'HEMI'
        else: col.operator("node.y_replace_layer_type", icon='LAMP', text='Fake Lighting').type = 'HEMI'

        #if context.parent.type == 'HEMI':
        col = row.column()
        col.label(text='Advanced')
        if context.parent.use_temp_bake:
            col.operator('node.y_disable_temp_image', text='Disable Baked Temp Image', icon='FILE_REFRESH')
        else:
            col.operator('node.y_bake_temp_image', text='Bake Temp Image', icon='RENDER_STILL')

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
    match2 = re.match(r'ypui\.channel_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'ypui\.layer_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match4 = re.match(r'ypui\.layer_ui\.masks\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        mod = yp.layers[yp.active_layer_index].channels[int(match1.group(1))].modifiers[int(match1.group(2))]
    elif match2:
        mod = yp.channels[yp.active_channel_index].modifiers[int(match2.group(1))]
    elif match3:
        mod = yp.layers[yp.active_layer_index].modifiers[int(match3.group(1))]
    elif match4:
        mod = yp.layers[yp.active_layer_index].masks[int(match4.group(1))].modifiers[int(match4.group(2))]
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

class YModifierUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=True, update=update_modifier_ui)

class YChannelUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=False, update=update_channel_ui)
    expand_bump_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_intensity_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_base_vector = BoolProperty(default=True, update=update_channel_ui)
    expand_transition_bump_settings = BoolProperty(default=True, update=update_channel_ui)
    expand_transition_ramp_settings = BoolProperty(default=True, update=update_channel_ui)
    expand_transition_ao_settings = BoolProperty(default=True, update=update_channel_ui)
    expand_subdiv_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_parallax_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_input_settings = BoolProperty(default=True, update=update_channel_ui)
    modifiers = CollectionProperty(type=YModifierUI)

class YMaskChannelUI(bpy.types.PropertyGroup):
    expand_content = BoolProperty(default=False, update=update_mask_channel_ui)

class YMaskUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=True, update=update_mask_ui)
    expand_channels = BoolProperty(default=True, update=update_mask_ui)
    expand_source = BoolProperty(default=True, update=update_mask_ui)
    expand_vector = BoolProperty(default=True, update=update_mask_ui)
    channels = CollectionProperty(type=YMaskChannelUI)
    modifiers = CollectionProperty(type=YModifierUI)

class YLayerUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=False, update=update_layer_ui)
    expand_vector = BoolProperty(default=False, update=update_layer_ui)
    expand_masks = BoolProperty(default=False, update=update_layer_ui)
    expand_source = BoolProperty(default=False, update=update_layer_ui)
    expand_channels = BoolProperty(default=False, update=update_layer_ui)

    channels = CollectionProperty(type=YChannelUI)
    masks = CollectionProperty(type=YMaskUI)
    modifiers = CollectionProperty(type=YModifierUI)

#def update_mat_active_yp_node(self, context):
#    print('Update:', self.active_ypaint_node)

class YMaterialUI(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    active_ypaint_node = StringProperty(default='') #, update=update_mat_active_yp_node)

class YPaintUI(bpy.types.PropertyGroup):
    show_object = BoolProperty(default=False)
    show_materials = BoolProperty(default=False)
    show_channels = BoolProperty(default=True)
    show_layers = BoolProperty(default=True)
    show_stats = BoolProperty(default=False)
    show_support = BoolProperty(default=False)

    expand_channels = BoolProperty(
            name='Expand all channels',
            description='Expand all channels',
            default=False)

    expand_mask_channels = BoolProperty(
            name='Expand all mask channels',
            description='Expand all mask channels',
            default=False)

    # To store active node and tree
    tree_name = StringProperty(default='')
    
    # Layer related UI
    layer_idx = IntProperty(default=0)
    layer_ui = PointerProperty(type=YLayerUI)

    disable_auto_temp_uv_update = BoolProperty(
            name = 'Disable Transformed UV Auto Update',
            description = "UV won't be created automatically if layer with custom offset/rotation/scale is selected.\n(This can make selecting layer faster)",
            default=False)

    #mask_ui = PointerProperty(type=YMaskUI)

    # Group channel related UI
    channel_idx = IntProperty(default=0)
    channel_ui = PointerProperty(type=YChannelUI)
    modifiers = CollectionProperty(type=YModifierUI)

    # Update related
    need_update = BoolProperty(default=False)
    halt_prop_update = BoolProperty(default=False)

    # Duplicated layer related
    make_image_single_user = BoolProperty(
            name = 'Make Images Single User',
            description = 'Make duplicated image layers single user',
            default=True)

    # HACK: For some reason active float image will glitch after auto save
    # This prop will notify if float image is active after saving
    refresh_image_hack = BoolProperty(default=False)

    materials = CollectionProperty(type=YMaterialUI)
    #active_obj = StringProperty(default='')
    active_mat = StringProperty(default='')
    active_ypaint_node = StringProperty(default='')

    #random_prop = BoolProperty(default=False)

def add_new_ypaint_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine not in {'CYCLES', 'BLENDER_EEVEE'}: return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_ypaint_node', text=ADDON_TITLE, icon='NODETREE')

def copy_ui_settings(source, dest):
    for attr in dir(source):
        if attr.startswith(('show_', 'expand_')) or attr.endswith('_name'):
            setattr(dest, attr, getattr(source, attr))

def save_mat_ui_settings():
    ypui = bpy.context.window_manager.ypui
    for mui in ypui.materials:
        mat = bpy.data.materials.get(mui.name)
        if mat: mat.yp.active_ypaint_node = mui.active_ypaint_node

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
    bpy.utils.register_class(YPaintSpecialMenu)
    bpy.utils.register_class(YNewLayerMenu)
    bpy.utils.register_class(YBakedImageMenu)
    bpy.utils.register_class(YLayerListSpecialMenu)
    bpy.utils.register_class(YUVSpecialMenu)
    bpy.utils.register_class(YModifierMenu)
    bpy.utils.register_class(YMaskModifierMenu)
    bpy.utils.register_class(YTransitionBumpMenu)
    bpy.utils.register_class(YTransitionRampMenu)
    bpy.utils.register_class(YTransitionAOMenu)
    bpy.utils.register_class(YAddLayerMaskMenu)
    bpy.utils.register_class(YLayerMaskMenu)
    bpy.utils.register_class(YMaterialSpecialMenu)
    bpy.utils.register_class(YAddModifierMenu)
    bpy.utils.register_class(YLayerSpecialMenu)
    bpy.utils.register_class(YModifierUI)
    bpy.utils.register_class(YChannelUI)
    bpy.utils.register_class(YMaskChannelUI)
    bpy.utils.register_class(YMaskUI)
    bpy.utils.register_class(YLayerUI)
    bpy.utils.register_class(YMaterialUI)
    bpy.utils.register_class(NODE_UL_YPaint_channels)
    bpy.utils.register_class(NODE_UL_YPaint_layers)

    if not is_28():
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

    # Handlers
    bpy.app.handlers.load_post.append(yp_load_ui_settings)
    bpy.app.handlers.save_pre.append(yp_save_ui_settings)

def unregister():
    bpy.utils.unregister_class(YPaintSpecialMenu)
    bpy.utils.unregister_class(YNewLayerMenu)
    bpy.utils.unregister_class(YBakedImageMenu)
    bpy.utils.unregister_class(YLayerListSpecialMenu)
    bpy.utils.unregister_class(YUVSpecialMenu)
    bpy.utils.unregister_class(YModifierMenu)
    bpy.utils.unregister_class(YMaskModifierMenu)
    bpy.utils.unregister_class(YTransitionBumpMenu)
    bpy.utils.unregister_class(YTransitionRampMenu)
    bpy.utils.unregister_class(YTransitionAOMenu)
    bpy.utils.unregister_class(YAddLayerMaskMenu)
    bpy.utils.unregister_class(YLayerMaskMenu)
    bpy.utils.unregister_class(YMaterialSpecialMenu)
    bpy.utils.unregister_class(YAddModifierMenu)
    bpy.utils.unregister_class(YLayerSpecialMenu)
    bpy.utils.unregister_class(YModifierUI)
    bpy.utils.unregister_class(YChannelUI)
    bpy.utils.unregister_class(YMaskChannelUI)
    bpy.utils.unregister_class(YMaskUI)
    bpy.utils.unregister_class(YLayerUI)
    bpy.utils.unregister_class(YMaterialUI)
    bpy.utils.unregister_class(NODE_UL_YPaint_channels)
    bpy.utils.unregister_class(NODE_UL_YPaint_layers)

    if not is_28():
        bpy.utils.unregister_class(VIEW3D_PT_YPaint_tools)
        bpy.utils.unregister_class(NODE_PT_YPaint)
    else: 
        bpy.utils.unregister_class(NODE_PT_YPaintUI)

    bpy.utils.unregister_class(VIEW3D_PT_YPaint_ui)
    bpy.utils.unregister_class(YPaintUI)

    # Remove add yPaint node ui
    bpy.types.NODE_MT_add.remove(add_new_ypaint_node_menu)

    # Remove Handlers
    bpy.app.handlers.load_post.remove(yp_load_ui_settings)
    bpy.app.handlers.save_pre.remove(yp_save_ui_settings)
