import bpy, re, time
from bpy.props import *
from bpy.app.handlers import persistent
from . import lib, Modifier, MaskModifier
from .common import *

def update_tl_ui():

    # Get active tl node
    node = get_active_cpaint_node()
    if not node or node.type != 'GROUP': return
    tree = node.node_tree
    tl = tree.tl
    ycpui = bpy.context.window_manager.ycpui

    # Check layer channel ui consistency
    if len(tl.layers) > 0:
        if len(ycpui.layer_ui.channels) != len(tl.channels):
            ycpui.need_update = True

    # Update UI
    if (ycpui.tree_name != tree.name or 
        ycpui.layer_idx != tl.active_layer_index or 
        ycpui.channel_idx != tl.active_channel_index or 
        ycpui.need_update
        ):

        ycpui.tree_name = tree.name
        ycpui.layer_idx = tl.active_layer_index
        ycpui.channel_idx = tl.active_channel_index
        ycpui.need_update = False
        ycpui.halt_prop_update = True

        if len(tl.channels) > 0:

            # Get channel
            channel = tl.channels[tl.active_channel_index]
            ycpui.channel_ui.expand_content = channel.expand_content
            ycpui.channel_ui.expand_base_vector = channel.expand_base_vector
            ycpui.channel_ui.modifiers.clear()

            # Construct channel UI objects
            for i, mod in enumerate(channel.modifiers):
                m = ycpui.channel_ui.modifiers.add()
                m.expand_content = mod.expand_content

        if len(tl.layers) > 0:

            # Get layer
            layer = tl.layers[tl.active_layer_index]
            ycpui.layer_ui.expand_content = layer.expand_content
            ycpui.layer_ui.expand_vector = layer.expand_vector
            ycpui.layer_ui.expand_source = layer.expand_source
            ycpui.layer_ui.expand_masks = layer.expand_masks
            ycpui.layer_ui.expand_channels = layer.expand_channels
            ycpui.layer_ui.channels.clear()
            ycpui.layer_ui.masks.clear()
            ycpui.layer_ui.modifiers.clear()

            # Construct layer modifier UI objects
            for mod in layer.modifiers:
                m = ycpui.layer_ui.modifiers.add()
                m.expand_content = mod.expand_content
            
            # Construct layer channel UI objects
            for i, ch in enumerate(layer.channels):
                c = ycpui.layer_ui.channels.add()
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
                m = ycpui.layer_ui.masks.add()
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

        ycpui.halt_prop_update = False

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
        col.prop(image, 'use_alpha')
        #col.prop(image, 'use_fields')

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
    ycpui = bpy.context.window_manager.ycpui
    tree = get_mask_tree(mask)

    for i, m in enumerate(mask.modifiers):

        try: modui = ui.modifiers[i]
        except: 
            ycpui.need_update = True
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
                row.prop(modui, 'expand_content', text='', emboss=False, icon='MODIFIER')
        else:
            row.label(text='', icon='MODIFIER')

        row.label(text=m.name)

        row.context_pointer_set('layer', layer)
        row.context_pointer_set('mask', mask)
        row.context_pointer_set('modifier', m)
        if bpy.app.version_string.startswith('2.8'):
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

    ycpui = context.window_manager.ycpui

    for i, m in enumerate(parent.modifiers):

        try: modui = ui.modifiers[i]
        except: 
            ycpui.need_update = True
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
                row.prop(modui, 'expand_content', text='', emboss=False, icon='MODIFIER')
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
        if bpy.app.version_string.startswith('2.8'):
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
    tl = group_tree.tl
    ycpui = context.window_manager.ycpui

    box = layout.box()
    col = box.column()
    row = col.row()

    rcol = row.column()
    if len(tl.channels) > 0:
        pcol = rcol.column()
        if tl.preview_mode: pcol.alert = True
        if custom_icon_enable:
            pcol.prop(tl, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')
        else: pcol.prop(tl, 'preview_mode', text='Preview Mode', icon='HIDE_OFF')

    rcol.template_list("NODE_UL_y_cp_channels", "", tl,
            "channels", tl, "active_channel_index", rows=3, maxrows=5)  

    rcol = row.column(align=True)
    #rcol.context_pointer_set('node', node)

    if bpy.app.version_string.startswith('2.8'):
        rcol.operator_menu_enum("node.y_add_new_cpaint_channel", 'type', icon='ADD', text='')
        rcol.operator("node.y_remove_cpaint_channel", icon='REMOVE', text='')
    else: 
        rcol.operator_menu_enum("node.y_add_new_cpaint_channel", 'type', icon='ZOOMIN', text='')
        rcol.operator("node.y_remove_cpaint_channel", icon='ZOOMOUT', text='')

    rcol.operator("node.y_move_cpaint_channel", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("node.y_move_cpaint_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

    if len(tl.channels) > 0:

        mcol = col.column(align=False)

        channel = tl.channels[tl.active_channel_index]
        mcol.context_pointer_set('channel', channel)

        chui = ycpui.channel_ui

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
        if bpy.app.version_string.startswith('2.8'):
            row.menu("NODE_MT_y_new_modifier_menu", icon='PREFERENCES', text='')
        else: row.menu("NODE_MT_y_new_modifier_menu", icon='SCRIPTWIN', text='')

        if chui.expand_content:

            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            draw_modifier_stack(context, channel, channel.type, bcol, chui, custom_icon_enable)

            inp = node.inputs[channel.io_index]

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
            elif channel.type == 'NORMAL':
                #if chui.expand_base_vector:
                #    brow.label(text='Base Normal:')
                #else: brow.label(text='Base Normal')
                brow.label(text='Base Normal')

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

            if channel.type == 'RGB':
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')
                if channel.enable_alpha:
                    inp_alpha = node.inputs[channel.io_index+1]
                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='BLANK1')
                    brow.label(text='Base Alpha:')
                    if len(node.inputs[channel.io_index+1].links)==0:
                        #if BLENDER_28_GROUP_INPUT_HACK:
                        #    brow.prop(channel,'val_input', text='')
                        #else:
                        brow.prop(inp_alpha, 'default_value', text='')
                    else:
                        brow.label(text='', icon='LINKED')
                else:
                    brow.label(text='Alpha:')
                brow.prop(channel, 'enable_alpha', text='')

                #if len(channel.modifiers) > 0:
                #    brow.label(text='', icon='BLANK1')

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')

                if bpy.app.version_string.startswith('2.8'):
                    split = brow.split(factor=0.375, align=True)
                else: split = brow.split(percentage=0.375)

                #split = brow.row(align=False)
                split.label(text='Space:')
                split.prop(channel, 'colorspace', text='')

def draw_layer_source(context, layout, layer, layer_tree, source, image, vcol, is_a_mesh, custom_icon_enable):
    obj = context.object
    tl = layer.id_data.tl
    ycpui = context.window_manager.ycpui
    texui = ycpui.layer_ui
    scene = context.scene

    row = layout.row(align=True)
    if image:
        if custom_icon_enable:
            if texui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_image"].icon_id
            else: icon_value = lib.custom_icons["collapsed_image"].icon_id
            row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_content', text='', emboss=True, icon='IMAGE_DATA')
        if image.yia.is_image_atlas:
            row.label(text=layer.name)
        else: row.label(text=image.name)
    elif vcol:
        if len(layer.modifiers) > 0:
            if custom_icon_enable:
                if texui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_vcol"].icon_id
                else: icon_value = lib.custom_icons["collapsed_vcol"].icon_id
                row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(texui, 'expand_content', text='', emboss=True, icon='GROUP_VCOL')
        else:
            row.label(text='', icon='GROUP_VCOL')
        row.label(text=vcol.name)
    elif layer.type == 'BACKGROUND':
        if len(layer.modifiers) > 0:
            if custom_icon_enable:
                if texui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
                else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
                row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(texui, 'expand_content', text='', emboss=True, icon='TEXTURE')
        else:
            row.label(text='', icon='TEXTURE')
        row.label(text=layer.name)
    elif layer.type == 'COLOR':
        if custom_icon_enable:
            if texui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_color"].icon_id
            else: icon_value = lib.custom_icons["collapsed_color"].icon_id
            row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_content', text='', emboss=True, icon='COLOR')
        row.label(text=layer.name)
    elif layer.type == 'GROUP':
        row.label(text='', icon='FILE_FOLDER')
        row.label(text=layer.name)
    else:
        title = source.bl_idname.replace('ShaderNodeTex', '')
        if custom_icon_enable:
            if texui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
            else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
            row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_content', text='', emboss=True, icon='TEXTURE')
        row.label(text=title)

    row.context_pointer_set('parent', layer)
    row.context_pointer_set('layer', layer)
    row.context_pointer_set('layer_ui', texui)

    if obj.mode == 'EDIT':
        if obj.type == 'MESH' and obj.data.uv_layers.active and obj.data.uv_layers.active.name == TEMP_UV:
            row = row.row(align=True)
            row.alert = True
            row.operator('node.y_back_to_original_uv', icon='EDITMODE_HLT', text='Edit Original UV')
    elif tl.need_temp_uv_refresh:
    #if ycpui.disable_auto_temp_uv_update and tl.need_temp_uv_refresh:
        row = row.row(align=True)
        row.alert = True
        row.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Transformed UV')

    if layer.type != 'GROUP':
        if bpy.app.version_string.startswith('2.8'):
            row.menu("NODE_MT_y_layer_special_menu", icon='PREFERENCES', text='')
        else: row.menu("NODE_MT_y_layer_special_menu", icon='SCRIPTWIN', text='')

    if layer.type == 'GROUP': return
    if layer.type in {'VCOL', 'BACKGROUND'} and len(layer.modifiers) == 0: return
    if not texui.expand_content: return

    rrow = layout.row(align=True)
    rrow.label(text='', icon='BLANK1')
    rcol = rrow.column(align=False)

    modcol = rcol.column()
    modcol.active = layer.type not in {'BACKGROUND', 'GROUP'}
    draw_modifier_stack(context, layer, 'RGB', modcol, 
            texui, custom_icon_enable, layer)

    if layer.type not in {'VCOL', 'BACKGROUND'}:
        row = rcol.row(align=True)

        if custom_icon_enable:
            if layer.type == 'IMAGE':
                suffix = 'image'
            elif layer.type == 'COLOR':
                suffix = 'color'
            else: suffix = 'texture'

            if texui.expand_source:
                icon_value = lib.custom_icons["uncollapsed_" + suffix].icon_id
            else: icon_value = lib.custom_icons["collapsed_" + suffix].icon_id
            row.prop(texui, 'expand_source', text='', emboss=False, icon_value=icon_value)
        else:
            icon = 'IMAGE_DATA' if layer.type == 'IMAGE' else 'TEXTURE'
            row.prop(texui, 'expand_source', text='', emboss=True, icon=icon)

        if image:
            row.label(text='Source: ' + image.name)
        else: row.label(text='Source: ' + layer.name)

        if texui.expand_source:
            row = rcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bbox = row.box()
            if image:
                draw_image_props(source, bbox, layer)
            elif layer.type == 'COLOR':
                draw_solid_color_props(layer, source, bbox)
            else: draw_tex_props(source, bbox)

        # Vector
        if layer.type != 'COLOR':
            row = rcol.row(align=True)

            if custom_icon_enable:
                if texui.expand_vector:
                    icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                row.prop(texui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
            else:
                row.prop(texui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

            if bpy.app.version_string.startswith('2.8'):
                split = row.split(factor=0.275, align=True)
            else: split = row.split(percentage=0.275, align=True)

            split.label(text='Vector:')
            if is_a_mesh and layer.texcoord_type == 'UV':

                if bpy.app.version_string.startswith('2.8'):
                    ssplit = split.split(factor=0.33, align=True)
                else: ssplit = split.split(percentage=0.33, align=True)

                #ssplit = split.split(percentage=0.33, align=True)
                ssplit.prop(layer, 'texcoord_type', text='')
                ssplit.prop_search(layer, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            else:
                split.prop(layer, 'texcoord_type', text='')

            if texui.expand_vector:
                row = rcol.row(align=True)
                row.label(text='', icon='BLANK1')
                bbox = row.box()
                crow = row.column()
                bbox.prop(layer, 'translation', text='Offset')
                bbox.prop(layer, 'rotation')
                bbox.prop(layer, 'scale')

                if tl.need_temp_uv_refresh:
                    rrow = bbox.row(align=True)
                    rrow.alert = True
                    rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh Transformed UV')

    layout.separator()

def draw_layer_channels(context, layout, layer, layer_tree, image, custom_icon_enable):

    tl = layer.id_data.tl
    ycpui = context.window_manager.ycpui
    texui = ycpui.layer_ui
    
    row = layout.row(align=True)
    if custom_icon_enable:
        if texui.expand_channels:
            icon_value = lib.custom_icons["uncollapsed_channels"].icon_id
        else: icon_value = lib.custom_icons["collapsed_channels"].icon_id
        row.prop(texui, 'expand_channels', text='', emboss=False, icon_value=icon_value)
    else: row.prop(texui, 'expand_channels', text='', emboss=True, icon='GROUP_VERTEX')

    #label = 'Channels:'
    #if not texui.expand_channels:
    #    for i, ch in enumerate(layer.channels):

    #        if ch.enable:

    #            if i == 0:
    #                label += ' '
    #            #elif i < len(layer.channels)-1:
    #            else:
    #                label += ', '

    #            label += tl.channels[i].name

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

    if texui.expand_channels:
        label += ':'
    
    row.label(text=label)

    if not texui.expand_channels:
        return

    if custom_icon_enable:
        row.prop(ycpui, 'expand_channels', text='', emboss=True, icon_value = lib.custom_icons['channels'].icon_id)
    else: row.prop(ycpui, 'expand_channels', text='', emboss=True, icon = 'GROUP_VERTEX')

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

        if not ycpui.expand_channels and not ch.enable:
            continue

        root_ch = tl.channels[i]
        ch_count += 1

        try: chui = ycpui.layer_ui.channels[i]
        except: 
            ycpui.need_update = True
            return

        ccol = rcol.column()
        ccol.active = ch.enable
        ccol.context_pointer_set('channel', ch)

        row = ccol.row(align=True)

        #expandable = True
        expandable = (
                len(ch.modifiers) > 0 or 
                layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'} or 
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

        row.label(text=tl.channels[i].name + ':')

        if layer.type != 'BACKGROUND':
            if root_ch.type == 'NORMAL':
                row.prop(ch, 'normal_blend', text='')
            else: row.prop(ch, 'blend_type', text='')

        row.prop(ch, 'intensity_value', text='')

        row.context_pointer_set('parent', ch)
        row.context_pointer_set('layer', layer)
        row.context_pointer_set('channel_ui', chui)

        #if custom_icon_enable:
        if bpy.app.version_string.startswith('2.8'):
            row.menu("NODE_MT_y_new_modifier_menu", icon='PREFERENCES', text='')
        else:
            row.menu("NODE_MT_y_new_modifier_menu", icon='SCRIPTWIN', text='')

        if ycpui.expand_channels:
            row.prop(ch, 'enable', text='')

        if not expandable or not chui.expand_content: continue

        mrow = ccol.row(align=True)
        mrow.label(text='', icon='BLANK1')
        mcol = mrow.column()

        if root_ch.type == 'NORMAL':

            if ch.normal_map_type == 'FINE_BUMP_MAP' and image:

                uv_neighbor = layer_tree.nodes.get(layer.uv_neighbor)
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
                    brow.prop(ch, 'transition_bump_value', text='')

                brow.context_pointer_set('parent', ch)
                if bpy.app.version_string.startswith('2.8'):
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

                    crow = cccol.row(align=True)
                    crow.label(text='Type:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_type', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 1:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 2:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_second_edge_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Distance:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_distance', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Affected Masks:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_chain', text='')

                    if ch.transition_bump_type == 'CURVED_BUMP_MAP':
                        crow = cccol.row(align=True)
                        crow.label(text='Offset:') #, icon='INFO')
                        crow.prop(ch, 'transition_bump_curved_offset', text='')

                    crow = cccol.row(align=True)
                    crow.active = layer.type != 'BACKGROUND'
                    crow.label(text='Flip:') #, icon='INFO')
                    crow.prop(ch, 'transition_bump_flip', text='')

                    crow = cccol.row(align=True)
                    crow.active = layer.type != 'BACKGROUND' and not ch.transition_bump_flip
                    crow.label(text='Crease:') #, icon='INFO')
                    if ch.transition_bump_crease:
                        crow.prop(ch, 'transition_bump_crease_factor', text='')
                    crow.prop(ch, 'transition_bump_crease', text='')

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
            #    row.label(text='', icon='INFO')
            if bpy.app.version_string.startswith('2.8'):
                split = row.split(factor=0.275)
            else: split = row.split(percentage=0.275)

            split.label(text='Type:') #, icon='INFO')
            srow = split.row(align=True)
            srow.prop(ch, 'normal_map_type', text='')
            if not chui.expand_bump_settings and ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
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

                if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:

                    brow = cccol.row(align=True)
                    brow.label(text='Distance:') #, icon='INFO')
                    brow.prop(ch, 'bump_distance', text='')

                    #if not ch.enable_transition_bump:
                    brow = cccol.row(align=True)
                    brow.active = not ch.enable_transition_bump
                    brow.label(text='Bump Base:') #, icon='INFO')
                    brow.prop(ch, 'bump_base_value', text='')

                    brow = cccol.row(align=True)
                    brow.active = not ch.enable_transition_bump
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
                if bpy.app.version_string.startswith('2.8'):
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
                if bpy.app.version_string.startswith('2.8'):
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
                ycpui.layer_ui.channels[i], custom_icon_enable, layer)

        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
            row = mcol.row(align=True)

            input_settings_available = (ch.tex_input != 'ALPHA' 
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
            if bpy.app.version_string.startswith('2.8'):
                split = row.split(factor=0.275)
            else: split = row.split(percentage=0.275)

            split.label(text='Input:')
            srow = split.row(align=True)
            srow.prop(ch, 'tex_input', text='')

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

        if ycpui.expand_channels:
            mrow.label(text='', icon='BLANK1')

        if extra_separator and i < len(layer.channels)-1:
            ccol.separator()

    if not ycpui.expand_channels and ch_count == 0:
        rcol.label(text='No active channel!')

    layout.separator()

def draw_layer_masks(context, layout, layer, custom_icon_enable):
    obj = context.object
    tl = layer.id_data.tl
    ycpui = context.window_manager.ycpui
    texui = ycpui.layer_ui

    col = layout.column()
    col.active = layer.enable_masks

    row = col.row(align=True)
    if len(layer.masks) > 0:
        if custom_icon_enable:
            if texui.expand_masks:
                icon_value = lib.custom_icons["uncollapsed_mask"].icon_id
            else: icon_value = lib.custom_icons["collapsed_mask"].icon_id
            row.prop(texui, 'expand_masks', text='', emboss=False, icon_value=icon_value)
        else: row.prop(texui, 'expand_masks', text='', emboss=True, icon='MOD_MASK')
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

    if texui.expand_masks:
        label += ':'

    row.label(text=label)

    if custom_icon_enable:
        #row.menu('NODE_MT_y_add_layer_mask_menu', text='', icon_value = lib.custom_icons['add_mask'].icon_id)
        row.menu('NODE_MT_y_add_layer_mask_menu', text='', icon='ZOOMIN')
    else: 
        #row.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='MOD_MASK')
        row.menu("NODE_MT_y_add_layer_mask_menu", text='', icon='ADD')

    if not texui.expand_masks or len(layer.masks) == 0: return

    row = col.row(align=True)
    row.label(text='', icon='BLANK1')
    rcol = row.column(align=False)

    for i, mask in enumerate(layer.masks):

        try: maskui = ycpui.layer_ui.masks[i]
        except: 
            ycpui.need_update = True
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

        if bpy.app.version_string.startswith('2.8'):
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
            if mask_image:
                draw_image_props(mask_source, rbox, mask)
            else: draw_tex_props(mask_source, rbox)

        # Vector row
        if mask.type != 'VCOL':
            rrow = rrcol.row(align=True)

            if custom_icon_enable:
                if maskui.expand_vector:
                    icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                rrow.prop(maskui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
            else:
                rrow.prop(maskui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

            if bpy.app.version_string.startswith('2.8'):
                splits = rrow.split(factor=0.3)
            else: splits = rrow.split(percentage=0.3)

            #splits = rrow.split(percentage=0.3)
            splits.label(text='Vector:')
            if mask.texcoord_type != 'UV':
                splits.prop(mask, 'texcoord_type', text='')
            else:

                if bpy.app.version_string.startswith('2.8'):
                    rrrow = splits.split(factor=0.35, align=True)
                else: rrrow = splits.split(percentage=0.35, align=True)

                #rrrow = splits.split(percentage=0.35, align=True)
                rrrow.prop(mask, 'texcoord_type', text='')
                rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

            if maskui.expand_vector:
                rrow = rrcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                rbox.prop(mask, 'translation', text='Offset')
                rbox.prop(mask, 'rotation')
                rbox.prop(mask, 'scale')

                if mask.type == 'IMAGE' and mask.active_edit and tl.need_temp_uv_refresh:
                    rrow = rbox.row(align=True)
                    rrow.alert = True
                    rrow.operator('node.y_refresh_transformed_uv', icon='FILE_REFRESH', text='Refresh Transformed UV')

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
                root_ch = tl.channels[k]
                if custom_icon_enable:
                    rrow.label(text='', 
                            icon_value=lib.custom_icons[lib.channel_custom_icon_dict[root_ch.type]].icon_id)
                else:
                    rrow.label(text='', icon = lib.channel_icon_dict[root_ch.type].icon_id)
                rrow.label(text=root_ch.name)
                rrow.prop(c, 'enable', text='')

        if i < len(layer.masks)-1:
            rcol.separator()

def draw_layers_ui(context, layout, node, custom_icon_enable):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    ycpui = context.window_manager.ycpui
    obj = context.object
    is_a_mesh = True if obj and obj.type == 'MESH' else False

    # Check if uv is found
    uv_found = False
    if is_a_mesh and len(obj.data.uv_layers) > 0: 
        uv_found = True

    box = layout.box()

    if is_a_mesh and not uv_found:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_add_simple_uvs", icon='ERROR')
        row.alert = False
        return

    # Check duplicated layers (indicated by more than one users)
    if len(tl.layers) > 0 and get_tree(tl.layers[-1]).users > 1:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_fix_duplicated_layers", icon='ERROR')
        row.alert = False
        box.prop(ycpui, 'make_image_single_user')
        return

    # Check source for missing data
    missing_data = False
    for layer in tl.layers:
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

    # Get layer, image and set context pointer
    layer = None
    source = None
    image = None
    vcol = None
    mask_image = None
    mask = None
    mask_idx = 0

    if len(tl.layers) > 0:
        layer = tl.layers[tl.active_layer_index]

        if layer:
            # Check for active mask
            for i, m in enumerate(layer.masks):
                if m.active_edit:
                    mask = m
                    mask_idx = i
                    if m.type == 'IMAGE':
                        mask_tree = get_mask_tree(m)
                        source = mask_tree.nodes.get(m.source)
                        #image = source.image
                        mask_image = source.image

            # Use layer image if there is no mask image
            #if not mask:
            layer_tree = get_tree(layer)
            source = get_layer_source(layer, layer_tree)
            if layer.type == 'IMAGE':
                image = source.image
            elif layer.type == 'VCOL' and obj.type == 'MESH':
                vcol = obj.data.vertex_colors.get(source.attribute_name)

    # Set pointer for active layer and image
    if layer: box.context_pointer_set('layer', layer)
    if mask_image: box.context_pointer_set('image', mask_image)
    elif image: box.context_pointer_set('image', image)

    col = box.column()

    row = col.row()
    row.template_list("NODE_UL_y_cp_layers", "", tl,
            "layers", tl, "active_layer_index", rows=5, maxrows=5)  

    rcol = row.column(align=True)
    if bpy.app.version_string.startswith('2.8'):
        rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ADD')
    else: rcol.menu("NODE_MT_y_new_layer_menu", text='', icon='ZOOMIN')

    if layer:

        if has_childrens(layer):

            if bpy.app.version_string.startswith('2.8'):
                rcol.operator("node.y_remove_layer_menu", icon='REMOVE', text='')
            else: rcol.operator("node.y_remove_layer_menu", icon='ZOOMOUT', text='')

        else: 
            if bpy.app.version_string.startswith('2.8'):
                c = rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
            else: c = rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

            c.remove_childs = False

        if is_top_member(layer):
            c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_UP')
            c.direction = 'UP'
            c.move_out = True
        else:
            upper_idx, upper_tex = get_upper_neighbor(layer)

            if upper_tex and (upper_tex.type == 'GROUP' or upper_tex.parent_idx != layer.parent_idx):
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
            lower_idx, lower_tex = get_lower_neighbor(layer)

            if lower_tex and (lower_tex.type == 'GROUP' and lower_tex.parent_idx == layer.parent_idx):
                c = rcol.operator("node.y_move_in_out_layer_group_menu", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'
                c.move_out = False
            else: 
                c = rcol.operator("node.y_move_layer", text='', icon='TRIA_DOWN')
                c.direction = 'DOWN'

    else:

        if bpy.app.version_string.startswith('2.8'):
            rcol.operator("node.y_remove_layer", icon='REMOVE', text='')
        else: rcol.operator("node.y_remove_layer", icon='ZOOMOUT', text='')

        rcol.operator("node.y_move_layer", text='', icon='TRIA_UP').direction = 'UP'
        rcol.operator("node.y_move_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'

    rcol.menu("NODE_MT_y_layer_list_special_menu", text='', icon='DOWNARROW_HLT')

    if layer:
        layer_tree = get_tree(layer)

        col = box.column()
        col.active = layer.enable and not is_parent_hidden(layer)

        # Source
        draw_layer_source(context, col, layer, layer_tree, source, image, vcol, is_a_mesh, custom_icon_enable)

        # Channels
        draw_layer_channels(context, col, layer, layer_tree, image, custom_icon_enable)

        # Masks
        draw_layer_masks(context, col, layer, custom_icon_enable)

def main_draw(self, context):

    wm = context.window_manager

    # Timer
    if wm.tltimer.time != '':
        print('INFO: Scene is updated at', '{:0.2f}'.format((time.time() - float(wm.tltimer.time)) * 1000), 'ms!')
        wm.tltimer.time = ''

    # Update ui props first
    update_tl_ui()

    if hasattr(lib, 'custom_icons'):
        custom_icon_enable = True
    else: custom_icon_enable = False

    node = get_active_cpaint_node()

    layout = self.layout

    if not node:
        layout.label(text="No active CounterPaint node!", icon='ERROR')
        layout.operator("node.y_quick_setup_contrapaint_node", icon='NODETREE')
        return

    #layout.label(text='Active: ' + node.node_tree.name, icon='NODETREE')
    row = layout.row(align=True)
    row.label(text='', icon='NODETREE')
    #row.label(text='Active: ' + node.node_tree.name)
    row.label(text=node.node_tree.name)
    #row.prop(node.node_tree, 'name', text='')

    if bpy.app.version_string.startswith('2.8'):
        row.menu("NODE_MT_y_cp_special_menu", text='', icon='PREFERENCES')
    else: row.menu("NODE_MT_y_cp_special_menu", text='', icon='SCRIPTWIN')

    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    ycpui = wm.ycpui

    icon = 'TRIA_DOWN' if ycpui.show_channels else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ycpui, 'show_channels', emboss=False, text='', icon=icon)
    row.label(text='Channels')

    if ycpui.show_channels:
        draw_root_channels_ui(context, layout, node, custom_icon_enable)

    icon = 'TRIA_DOWN' if ycpui.show_layers else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ycpui, 'show_layers', emboss=False, text='', icon=icon)
    row.label(text='Layers')

    if ycpui.show_layers:
        draw_layers_ui(context, layout, node, custom_icon_enable)

    # Stats
    icon = 'TRIA_DOWN' if ycpui.show_stats else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ycpui, 'show_stats', emboss=False, text='', icon=icon)
    row.label(text='Stats')

    if ycpui.show_stats:

        images = []
        vcols = []
        num_gen_texs = 0

        for layer in tl.layers:
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

    icon = 'TRIA_DOWN' if ycpui.show_support else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(ycpui, 'show_support', emboss=False, text='', icon=icon)
    row.label(text='Support This Addon!')

    if ycpui.show_support:
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


class NODE_PT_ContraPaint(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = "CounterPaint " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = "CounterPaint"

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_ContraPaint_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "CounterPaint " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = "CounterPaint"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_ContraPaint_ui(bpy.types.Panel):
    bl_label = "CounterPaint " + get_current_version_str()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class NODE_UL_y_cp_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_cpaint_node()
        #if not group_node: return
        inputs = group_node.inputs

        row = layout.row()

        if hasattr(lib, 'custom_icons'):
            icon_value = lib.custom_icons[lib.channel_custom_icon_dict[item.type]].icon_id
            row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(item, 'name', text='', emboss=False, icon=lib.channel_icon_dict[item.type])

        if item.type == 'RGB':
            row = row.row(align=True)

        if len(inputs[item.io_index].links) == 0:
            #if BLENDER_28_GROUP_INPUT_HACK:
            #    if item.type == 'VALUE':
            #        row.prop(item, 'val_input', text='') #, emboss=False)
            #    elif item.type == 'RGB':
            #        row.prop(item, 'col_input', text='', icon='COLOR') #, emboss=False)
            #else:
            if item.type == 'VALUE':
                row.prop(inputs[item.io_index], 'default_value', text='') #, emboss=False)
            elif item.type == 'RGB':
                row.prop(inputs[item.io_index], 'default_value', text='', icon='COLOR')
            #elif item.type == 'NORMAL':
            #    socket = inputs[item.io_index]
            #    socket.draw(context, row, group_node, iface_(socket.name, socket.bl_rna.translation_context))
            #    #row.prop(inputs[item.io_index], 'default_value', text='', expand=False)
        else:
            row.label(text='', icon='LINKED')

        if item.type=='RGB' and item.enable_alpha:
            if len(inputs[item.io_index+1].links) == 0:
                #if BLENDER_28_GROUP_INPUT_HACK:
                #    row.prop(item,'val_input', text='')
                #else: 
                row.prop(inputs[item.io_index+1], 'default_value', text='')
            else: row.label(text='', icon='LINKED')

class NODE_UL_y_cp_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_tree = item.id_data
        tl = group_tree.tl
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
                if m.type == 'IMAGE':
                    src = mask_tree.nodes.get(m.source)
                    active_mask_image = src.image
                    row.label(text='', icon_value=src.image.preview.icon_id)
                elif m.type == 'VCOL':
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

class YCPSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_cp_special_menu"
    bl_label = "CounterPaint Special Menu"
    bl_description = "CounterPaint Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_cpaint_node()

    def draw(self, context):
        node = get_active_cpaint_node()
        mat = get_active_material()

        col = self.layout.column()

        col.operator('node.y_rename_cp_tree', text='Rename', icon='GREASEPENCIL')

        col.separator()

        col.label('Active:', icon='NODETREE')
        for n in get_list_of_tl_nodes(mat):
            if n.name == node.name:
                icon = 'RADIOBUT_ON'
            else: icon = 'RADIOBUT_OFF'

            row = col.row()
            row.operator('node.y_change_active_tl', text=n.node_tree.name, icon=icon).name = n.name

class YNewLayerMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_layer_menu"
    bl_description = 'Add New Layer'
    bl_label = "New Layer Menu"

    @classmethod
    def poll(cls, context):
        return get_active_cpaint_node()

    def draw(self, context):
        #row = self.layout.row()
        #col = row.column()
        col = self.layout.column(align=True)
        #col.context_pointer_set('group_node', context.group_node)
        #col.label(text='Image:')
        col.operator("node.y_new_layer", text='New Image', icon='IMAGE_DATA').type = 'IMAGE'

        #col.separator()

        col.operator("node.y_open_image_to_layer", text='Open Image')
        if bpy.app.version_string.startswith('2.8'):
            #col.operator("node.y_open_image_to_layer", text='Open Image', icon='FILEBROWSER')
            col.operator("node.y_open_available_data_to_layer", text='Open Available Image').type = 'IMAGE'
        else:
            #col.operator("node.y_open_image_to_layer", text='Open Image', icon='IMASEL')
            col.operator("node.y_open_available_data_to_layer", text='Open Available Image').type = 'IMAGE'

        col.separator()

        col.operator("node.y_new_layer", icon='FILE_FOLDER', text='New Layer Group').type = 'GROUP'
        col.separator()

        #col.label(text='Vertex Color:')
        col.operator("node.y_new_layer", icon='GROUP_VCOL', text='New Vertex Color').type = 'VCOL'
        col.operator("node.y_open_available_data_to_layer", text='Open Available Vertex Color').type = 'VCOL'
        col.separator()

        #col.label(text='Solid Color:')

        c = col.operator("node.y_new_layer", icon='COLOR', text='Solid Color w/ Image Mask')
        c.type = 'COLOR'
        c.add_mask = True
        c.mask_type = 'IMAGE'

        if bpy.app.version_string.startswith('2.8'):
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

        if bpy.app.version_string.startswith('2.8'):
            c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')
        else: c = col.operator("node.y_new_layer", text='Background w/ Vertex Color Mask')

        c.type = 'BACKGROUND'
        c.add_mask = True
        c.mask_type = 'VCOL'

        col.separator()

        #col = row.column()
        #col.label(text='Generated:')
        col.operator("node.y_new_layer", icon='TEXTURE', text='Brick').type = 'BRICK'
        col.operator("node.y_new_layer", text='Checker').type = 'CHECKER'
        col.operator("node.y_new_layer", text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_layer", text='Magic').type = 'MAGIC'
        col.operator("node.y_new_layer", text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_layer", text='Noise').type = 'NOISE'
        col.operator("node.y_new_layer", text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_layer", text='Wave').type = 'WAVE'

class YLayerListSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_list_special_menu"
    bl_label = "Layer Special Menu"
    bl_description = "Layer Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_cpaint_node()

    def draw(self, context):
        #self.layout.context_pointer_set('space_data', context.screen.areas[6].spaces[0])
        #self.layout.operator('image.save_as', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image:
            self.layout.label(text='Active Image: ' + context.image.name, icon='IMAGE_DATA')
        else:
            self.layout.label(text='No active image')
        self.layout.separator()
        self.layout.operator('node.y_pack_image', icon='PACKAGE')
        self.layout.operator('node.y_save_image', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image.packed_file:
            self.layout.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').unpack = True
        else:
            if bpy.app.version_string.startswith('2.8'):
                self.layout.operator('node.y_save_as_image', text='Save As Image')
                self.layout.operator('node.y_save_pack_all', text='Save/Pack All')
            else: 
                self.layout.operator('node.y_save_as_image', text='Save As Image', icon='SAVE_AS')
                self.layout.operator('node.y_save_pack_all', text='Save/Pack All', icon='FILE_TICK')

        self.layout.separator()
        self.layout.operator("node.y_reload_image", icon='FILE_REFRESH')
        self.layout.separator()
        self.layout.operator("node.y_invert_image", icon='IMAGE_ALPHA')

class YModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_modifier_menu"
    bl_label = "Modifier Menu"
    bl_description = "Modifier Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'modifier') and hasattr(context, 'parent') and get_active_cpaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        op = col.operator('node.y_move_layer_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_layer_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        if bpy.app.version_string.startswith('2.8'):
            op = col.operator('node.y_remove_layer_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_layer_modifier', icon='ZOOMOUT', text='Remove Modifier')

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

        if bpy.app.version_string.startswith('2.8'):
            op = col.operator('node.y_remove_mask_modifier', icon='REMOVE', text='Remove Modifier')
        else: op = col.operator('node.y_remove_mask_modifier', icon='ZOOMOUT', text='Remove Modifier')

class YTransitionBumpMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_bump_menu"
    bl_label = "Transition Bump Menu"
    bl_description = "Transition Bump Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_cpaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        #col.label(text=context.parent.path_from_id())

        if bpy.app.version_string.startswith('2.8'):
            col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='REMOVE').type = 'BUMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Bump', icon='ZOOMOUT').type = 'BUMP'

class YTransitionRampMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ramp_menu"
    bl_label = "Transition Ramp Menu"
    bl_description = "Transition Ramp Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_cpaint_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        col.prop(context.parent, 'transition_ramp_intensity_unlink', text='Unlink Ramp with Channel Intensity')

        col.separator()

        if bpy.app.version_string.startswith('2.8'):
            col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='REMOVE').type = 'RAMP'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition Ramp', icon='ZOOMOUT').type = 'RAMP'

class YTransitionAOMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_transition_ao_menu"
    bl_label = "Transition AO Menu"
    bl_description = "Transition AO Menu"

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'parent') and get_active_cpaint_node()
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
        if bpy.app.version_string.startswith('2.8'):
            col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='REMOVE').type = 'AO'
        else: col.operator('node.y_hide_transition_effect', text='Remove Transition AO', icon='ZOOMOUT').type = 'AO'

class YAddLayerMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_layer_mask_menu"
    bl_description = 'Add Layer Mask'
    bl_label = "Add Layer Mask"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')
        #node =  get_active_cpaint_node()
        #return node and len(node.node_tree.tl.layers) > 0

    def draw(self, context):
        #print(context.layer)
        layout = self.layout
        row = layout.row()
        col = row.column(align=True)
        col.context_pointer_set('layer', context.layer)

        col.label(text='Image Mask:')
        col.operator('node.y_new_layer_mask', icon='IMAGE_DATA', text='New Image Mask').type = 'IMAGE'
        if bpy.app.version_string.startswith('2.8'):
            col.operator('node.y_open_image_as_mask', text='Open Image as Mask', icon='FILEBROWSER')
            col.operator('node.y_open_available_data_as_mask', text='Open Available Image as Mask', icon='FILEBROWSER')
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
        if bpy.app.version_string.startswith('2.8'):
            col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='REMOVE')
        else: col.operator('node.y_remove_layer_mask', text='Remove Mask', icon='ZOOMOUT')

        col = row.column(align=True)
        col.label(text='Add Modifier')

        col.operator('node.y_new_mask_modifier', text='Invert', icon='MODIFIER').type = 'INVERT'
        col.operator('node.y_new_mask_modifier', text='Ramp', icon='MODIFIER').type = 'RAMP'

class YAddModifierMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_modifier_menu"
    bl_label = "Add Modifier Menu"
    bl_description = 'Add New Modifier'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_cpaint_node()

    def draw(self, context):
        row = self.layout.row()

        col = row.column()

        col.label(text='Add Modifier')
        ## List the items
        for mt in Modifier.modifier_type_items:
            col.operator('node.y_new_layer_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

        m = re.match(r'tl\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if m:

            ch = context.parent
            tl = ch.id_data.tl
            root_ch = tl.channels[int(m.group(2))]

            col = row.column()
            col.label(text='Transition Effects')
            if root_ch.type == 'NORMAL':
                col.operator('node.y_show_transition_bump', text='Transition Bump', icon='IMAGE_RGB_ALPHA')
            else:
                col.operator('node.y_show_transition_ramp', text='Transition Ramp', icon='IMAGE_RGB_ALPHA')
                col.operator('node.y_show_transition_ao', text='Transition AO', icon='IMAGE_RGB_ALPHA')

            #col.label(context.parent.path_from_id())

class YLayerSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_layer_special_menu"
    bl_label = "Layer Special Menu"
    bl_description = 'Layer Special Menu'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_cpaint_node()

    def draw(self, context):
        ycpui = context.window_manager.ycpui

        row = self.layout.row()

        col = row.column()
        col.label(text='Add Modifier')
        ## List the modifiers
        for mt in Modifier.modifier_type_items:
            col.operator('node.y_new_layer_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

        col = row.column()
        col.label(text='Change Layer Type')
        col.operator('node.y_replace_layer_type', text='Image', icon='IMAGE_DATA').type = 'IMAGE'

        col.operator('node.y_replace_layer_type', text='Vertex Color', icon='GROUP_VCOL').type = 'VCOL'
        col.operator('node.y_replace_layer_type', text='Solid Color', icon='COLOR').type = 'COLOR'
        col.operator('node.y_replace_layer_type', text='Background', icon='IMAGE_RGB_ALPHA').type = 'BACKGROUND'

        col.separator()
        col.operator('node.y_replace_layer_type', text='Brick', icon='TEXTURE').type = 'BRICK'
        col.operator('node.y_replace_layer_type', text='Checker', icon='TEXTURE').type = 'CHECKER'
        col.operator('node.y_replace_layer_type', text='Gradient', icon='TEXTURE').type = 'GRADIENT'
        col.operator('node.y_replace_layer_type', text='Magic', icon='TEXTURE').type = 'MAGIC'
        col.operator('node.y_replace_layer_type', text='Musgrave', icon='TEXTURE').type = 'MUSGRAVE'
        col.operator('node.y_replace_layer_type', text='Noise', icon='TEXTURE').type = 'NOISE'
        col.operator('node.y_replace_layer_type', text='Voronoi', icon='TEXTURE').type = 'VORONOI'
        col.operator('node.y_replace_layer_type', text='Wave', icon='TEXTURE').type = 'WAVE'

        col = row.column()
        col.label(text='Options:')
        col.prop(ycpui, 'disable_auto_temp_uv_update')

def update_modifier_ui(self, context):
    ycpui = context.window_manager.ycpui
    if ycpui.halt_prop_update: return

    group_node =  get_active_cpaint_node()
    if not group_node: return
    tl = group_node.node_tree.tl

    match1 = re.match(r'ycpui\.layer_ui\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'ycpui\.channel_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'ycpui\.layer_ui\.modifiers\[(\d+)\]', self.path_from_id())
    match4 = re.match(r'ycpui\.layer_ui\.masks\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        mod = tl.layers[tl.active_layer_index].channels[int(match1.group(1))].modifiers[int(match1.group(2))]
    elif match2:
        mod = tl.channels[tl.active_channel_index].modifiers[int(match2.group(1))]
    elif match3:
        mod = tl.layers[tl.active_layer_index].modifiers[int(match3.group(1))]
    elif match4:
        mod = tl.layers[tl.active_layer_index].masks[int(match4.group(1))].modifiers[int(match4.group(2))]
    #else: return #yolo

    mod.expand_content = self.expand_content

def update_layer_ui(self, context):
    ycpui = context.window_manager.ycpui
    if ycpui.halt_prop_update: return

    group_node =  get_active_cpaint_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.layers) == 0: return

    layer = tl.layers[tl.active_layer_index]
    layer.expand_content = self.expand_content
    layer.expand_vector = self.expand_vector
    layer.expand_masks = self.expand_masks

def update_channel_ui(self, context):
    ycpui = context.window_manager.ycpui
    if ycpui.halt_prop_update: return

    group_node =  get_active_cpaint_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.channels) == 0: return

    match1 = re.match(r'ycpui\.layer_ui\.channels\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'ycpui\.channel_ui', self.path_from_id())

    if match1:
        ch = tl.layers[tl.active_layer_index].channels[int(match1.group(1))]
    elif match2:
        ch = tl.channels[tl.active_channel_index]
    #else: return #yolo

    ch.expand_content = self.expand_content
    if hasattr(ch, 'expand_bump_settings'):
        ch.expand_bump_settings = self.expand_bump_settings
    if hasattr(ch, 'expand_base_vector'):
        ch.expand_base_vector = self.expand_base_vector
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
    ycpui = context.window_manager.ycpui
    if ycpui.halt_prop_update: return

    group_node =  get_active_cpaint_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    #if len(tl.channels) == 0: return

    match = re.match(r'ycpui\.layer_ui\.masks\[(\d+)\]', self.path_from_id())
    mask = tl.layers[tl.active_layer_index].masks[int(match.group(1))]

    mask.expand_content = self.expand_content
    mask.expand_channels = self.expand_channels
    mask.expand_source = self.expand_source
    mask.expand_vector = self.expand_vector

def update_mask_channel_ui(self, context):
    ycpui = context.window_manager.ycpui
    if ycpui.halt_prop_update: return

    group_node =  get_active_cpaint_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    #if len(tl.channels) == 0: return

    match = re.match(r'ycpui\.layer_ui\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    mask = tl.layers[tl.active_layer_index].masks[int(match.group(1))]
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

#def update_mat_active_tl_node(self, context):
#    print('Update:', self.active_tl_node)

class YMaterialUI(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    active_tl_node = StringProperty(default='') #, update=update_mat_active_tl_node)

class YCPUI(bpy.types.PropertyGroup):
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
    active_tl_node = StringProperty(default='')

    #random_prop = BoolProperty(default=False)

def add_new_cp_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine not in {'CYCLES', 'BLENDER_EEVEE'}: return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_cpaint_node', text='CounterPaint', icon='NODETREE')

def copy_ui_settings(source, dest):
    for attr in dir(source):
        if attr.startswith(('show_', 'expand_')) or attr.endswith('_name'):
            setattr(dest, attr, getattr(source, attr))

def save_mat_ui_settings():
    ycpui = bpy.context.window_manager.ycpui
    for mui in ycpui.materials:
        mat = bpy.data.materials.get(mui.name)
        if mat: mat.tl.active_tl_node = mui.active_tl_node

def load_mat_ui_settings():
    ycpui = bpy.context.window_manager.ycpui
    for mat in bpy.data.materials:
        if mat.tl.active_tl_node != '':
            mui = ycpui.materials.add()
            mui.name = mat.name
            mui.material = mat
            mui.active_tl_node = mat.tl.active_tl_node

@persistent
def ycp_save_ui_settings(scene):
    save_mat_ui_settings()
    wmui = bpy.context.window_manager.ycpui
    scui = bpy.context.scene.ycpui
    copy_ui_settings(wmui, scui)

@persistent
def ycp_load_ui_settings(scene):
    load_mat_ui_settings()
    wmui = bpy.context.window_manager.ycpui
    scui = bpy.context.scene.ycpui
    copy_ui_settings(scui, wmui)

    # Update UI
    wmui.need_update = True

def register():
    bpy.utils.register_class(YCPSpecialMenu)
    bpy.utils.register_class(YNewLayerMenu)
    bpy.utils.register_class(YLayerListSpecialMenu)
    bpy.utils.register_class(YModifierMenu)
    bpy.utils.register_class(YMaskModifierMenu)
    bpy.utils.register_class(YTransitionBumpMenu)
    bpy.utils.register_class(YTransitionRampMenu)
    bpy.utils.register_class(YTransitionAOMenu)
    bpy.utils.register_class(YAddLayerMaskMenu)
    bpy.utils.register_class(YLayerMaskMenu)
    bpy.utils.register_class(YAddModifierMenu)
    bpy.utils.register_class(YLayerSpecialMenu)
    bpy.utils.register_class(YModifierUI)
    bpy.utils.register_class(YChannelUI)
    bpy.utils.register_class(YMaskChannelUI)
    bpy.utils.register_class(YMaskUI)
    bpy.utils.register_class(YLayerUI)
    bpy.utils.register_class(YMaterialUI)
    bpy.utils.register_class(NODE_UL_y_cp_channels)
    bpy.utils.register_class(NODE_UL_y_cp_layers)
    bpy.utils.register_class(NODE_PT_ContraPaint)
    if not bpy.app.version_string.startswith('2.8'):
        bpy.utils.register_class(VIEW3D_PT_ContraPaint_tools)
    bpy.utils.register_class(VIEW3D_PT_ContraPaint_ui)
    bpy.utils.register_class(YCPUI)

    bpy.types.Scene.ycpui = PointerProperty(type=YCPUI)
    bpy.types.WindowManager.ycpui = PointerProperty(type=YCPUI)

    # Add CounterPaint node ui
    bpy.types.NODE_MT_add.append(add_new_cp_node_menu)

    # Handlers
    bpy.app.handlers.load_post.append(ycp_load_ui_settings)
    bpy.app.handlers.save_pre.append(ycp_save_ui_settings)

def unregister():
    bpy.utils.unregister_class(YCPSpecialMenu)
    bpy.utils.unregister_class(YNewLayerMenu)
    bpy.utils.unregister_class(YLayerListSpecialMenu)
    bpy.utils.unregister_class(YModifierMenu)
    bpy.utils.unregister_class(YMaskModifierMenu)
    bpy.utils.unregister_class(YTransitionBumpMenu)
    bpy.utils.unregister_class(YTransitionRampMenu)
    bpy.utils.unregister_class(YTransitionAOMenu)
    bpy.utils.unregister_class(YAddLayerMaskMenu)
    bpy.utils.unregister_class(YLayerMaskMenu)
    bpy.utils.unregister_class(YAddModifierMenu)
    bpy.utils.unregister_class(YLayerSpecialMenu)
    bpy.utils.unregister_class(YModifierUI)
    bpy.utils.unregister_class(YChannelUI)
    bpy.utils.unregister_class(YMaskChannelUI)
    bpy.utils.unregister_class(YMaskUI)
    bpy.utils.unregister_class(YLayerUI)
    bpy.utils.unregister_class(YMaterialUI)
    bpy.utils.unregister_class(NODE_UL_y_cp_channels)
    bpy.utils.unregister_class(NODE_UL_y_cp_layers)
    bpy.utils.unregister_class(NODE_PT_ContraPaint)
    if not bpy.app.version_string.startswith('2.8'):
        bpy.utils.unregister_class(VIEW3D_PT_ContraPaint_tools)
    bpy.utils.unregister_class(VIEW3D_PT_ContraPaint_ui)
    bpy.utils.unregister_class(YCPUI)

    # Remove add CounterPaint node ui
    bpy.types.NODE_MT_add.remove(add_new_cp_node_menu)

    # Remove Handlers
    bpy.app.handlers.load_post.remove(ycp_load_ui_settings)
    bpy.app.handlers.save_pre.remove(ycp_save_ui_settings)
