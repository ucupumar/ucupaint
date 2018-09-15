import bpy, re
from bpy.props import *
from bpy.app.handlers import persistent
from . import lib, Modifier
from .common import *

def update_tl_ui():

    # Get active tl node
    node = get_active_texture_layers_node()
    if not node or node.type != 'GROUP': return
    tree = node.node_tree
    tl = tree.tl
    tlui = bpy.context.window_manager.tlui

    # Check if tex channel ui consistency
    if len(tl.textures) > 0:
        if len(tlui.tex_ui.channels) != len(tl.channels):
            tlui.need_update = True

    # Update UI
    if (tlui.tree_name != tree.name or 
        tlui.tex_idx != tl.active_texture_index or 
        tlui.channel_idx != tl.active_channel_index or 
        tlui.need_update
        ):

        tlui.tree_name = tree.name
        tlui.tex_idx = tl.active_texture_index
        tlui.channel_idx = tl.active_channel_index
        tlui.need_update = False
        tlui.halt_prop_update = True

        if len(tl.channels) > 0:

            # Get channel
            channel = tl.channels[tl.active_channel_index]
            tlui.channel_ui.expand_content = channel.expand_content
            tlui.channel_ui.expand_base_vector = channel.expand_base_vector
            tlui.channel_ui.modifiers.clear()

            # Construct channel UI objects
            for i, mod in enumerate(channel.modifiers):
                m = tlui.channel_ui.modifiers.add()
                m.expand_content = mod.expand_content

        if len(tl.textures) > 0:

            # Get texture
            tex = tl.textures[tl.active_texture_index]
            tlui.tex_ui.expand_content = tex.expand_content
            tlui.tex_ui.expand_vector = tex.expand_vector
            tlui.tex_ui.expand_masks = tex.expand_masks
            tlui.tex_ui.channels.clear()
            tlui.tex_ui.masks.clear()
            
            # Construct texture channel UI objects
            for i, ch in enumerate(tex.channels):
                c = tlui.tex_ui.channels.add()
                c.expand_bump_settings = ch.expand_bump_settings
                c.expand_intensity_settings = ch.expand_intensity_settings
                c.expand_mask_settings = ch.expand_mask_settings
                c.expand_input_settings = ch.expand_input_settings
                c.expand_content = ch.expand_content
                for j, mod in enumerate(ch.modifiers):
                    m = c.modifiers.add()
                    m.expand_content = mod.expand_content

            # Construct texture masks UI objects
            for i, mask in enumerate(tex.masks):
                m = tlui.tex_ui.masks.add()
                m.expand_content = mask.expand_content
                m.expand_channels = mask.expand_channels
                m.expand_source = mask.expand_source
                m.expand_vector = mask.expand_vector
                for mch in mask.channels:
                    mc = m.channels.add()
                    mc.expand_content = mch.expand_content

        tlui.halt_prop_update = False

def draw_image_props(source, layout):

    image = source.image

    col = layout.column()
    col.template_ID(source, "image", unlink='node.y_remove_texture_layer')
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

def draw_root_channels_ui(context, layout, node, custom_icon_enable):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    tlui = context.window_manager.tlui

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

    rcol.template_list("NODE_UL_y_tl_channels", "", tl,
            "channels", tl, "active_channel_index", rows=3, maxrows=5)  

    rcol = row.column(align=True)
    rcol.operator_menu_enum("node.y_add_new_texture_layers_channel", 'type', icon='ZOOMIN', text='')
    rcol.operator("node.y_remove_texture_layers_channel", icon='ZOOMOUT', text='')
    rcol.operator("node.y_move_texture_layers_channel", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("node.y_move_texture_layers_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

    if len(tl.channels) > 0:

        mcol = col.column(align=False)

        channel = tl.channels[tl.active_channel_index]
        mcol.context_pointer_set('channel', channel)

        chui = tlui.channel_ui

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

        if channel.type != 'NORMAL':
            row.context_pointer_set('parent', channel)
            row.context_pointer_set('channel_ui', chui)
            if custom_icon_enable:
                icon_value = lib.custom_icons["add_modifier"].icon_id
                row.menu("NODE_MT_y_texture_modifier_specials", icon_value=icon_value, text='')
            else: row.menu("NODE_MT_y_texture_modifier_specials", icon='MODIFIER', text='')

        if chui.expand_content:

            row = mcol.row(align=True)
            row.label(text='', icon='BLANK1')
            bcol = row.column()

            for i, m in enumerate(channel.modifiers):

                try: modui = chui.modifiers[i]
                except: 
                    tlui.need_update = True
                    return

                brow = bcol.row(align=True)

                can_be_expanded = m.type in Modifier.can_be_expanded

                #brow.active = m.enable
                if can_be_expanded:
                    if custom_icon_enable:
                        if modui.expand_content:
                            icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                        else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                        brow.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                    else:
                        brow.prop(modui, 'expand_content', text='', emboss=False, icon='MODIFIER')
                    brow.label(text=m.name)
                else:
                    brow.label(text='', icon='MODIFIER')
                    brow.label(text=m.name)

                if not modui.expand_content:

                    if m.type == 'RGB_TO_INTENSITY':
                        brow.prop(m, 'rgb2i_col', text='', icon='COLOR')
                        brow.separator()

                    if m.type == 'OVERRIDE_COLOR':
                        brow.prop(m, 'oc_col', text='', icon='COLOR')
                        brow.separator()

                #brow.context_pointer_set('texture', tex)
                brow.context_pointer_set('parent', channel)
                brow.context_pointer_set('modifier', m)
                brow.menu("NODE_MT_y_modifier_menu", text='', icon='SCRIPTWIN')
                brow.prop(m, 'enable', text='')

                if modui.expand_content and can_be_expanded:
                    row = bcol.row(align=True)
                    #row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')
                    bbox = row.box()
                    bbox.active = m.enable
                    Modifier.draw_modifier_properties(context, channel, nodes, m, bbox, False)
                    row.label(text='', icon='BLANK1')

            #if len(channel.modifiers) > 0:
            #    brow = bcol.row(align=True)
            #    brow.label(text='', icon='TEXTURE')
            #    brow.label(text='Textures happen here..')

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
                if BLENDER_28_GROUP_INPUT_HACK:
                    if channel.type == 'RGB':
                        brow.prop(channel,'col_input', text='')
                    elif channel.type == 'VALUE':
                        brow.prop(channel,'val_input', text='')
                else:
                    brow.prop(inp,'default_value', text='')
            else:
                brow.label(text='', icon='LINKED')

            if len(channel.modifiers) > 0:
                brow.label(text='', icon='BLANK1')

            if channel.type == 'RGB':
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')
                if channel.alpha:
                    inp_alpha = node.inputs[channel.io_index+1]
                    #brow = bcol.row(align=True)
                    #brow.label(text='', icon='BLANK1')
                    brow.label(text='Base Alpha:')
                    if len(node.inputs[channel.io_index+1].links)==0:
                        if BLENDER_28_GROUP_INPUT_HACK:
                            brow.prop(channel,'val_input', text='')
                        else:
                            brow.prop(inp_alpha, 'default_value', text='')
                    else:
                        brow.label(text='', icon='LINKED')
                else:
                    brow.label(text='Alpha:')
                brow.prop(channel, 'alpha', text='')

                #if len(channel.modifiers) > 0:
                #    brow.label(text='', icon='BLANK1')

            if channel.type in {'RGB', 'VALUE'}:
                brow = bcol.row(align=True)
                brow.label(text='', icon='INFO')
                if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                    split = brow.split(percentage=0.375)
                else: split = brow.split(factor=0.375, align=True)
                #split = brow.row(align=False)
                split.label(text='Space:')
                split.prop(channel, 'colorspace', text='')

def draw_texture_ui(context, layout, tex, source, image, vcol, is_a_mesh, custom_icon_enable):
    obj = context.object
    tl = tex.id_data.tl
    tlui = context.window_manager.tlui

    col = layout.column()
    col.active = tex.enable

    ccol = col.column() #align=True)
    row = ccol.row(align=True)

    tex_tree = get_tree(tex)
    
    texui = tlui.tex_ui

    if image:
        if custom_icon_enable:
            if texui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_image"].icon_id
            else: icon_value = lib.custom_icons["collapsed_image"].icon_id
            row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_content', text='', emboss=True, icon='IMAGE_DATA')
        row.label(text=image.name)
        #row.operator("node.y_reload_image", text="", icon='FILE_REFRESH')
        #row.separator()
    elif vcol:
        row.label(text='', icon='GROUP_VCOL')
        row.label(text=vcol.name)
    else:
        title = source.bl_idname.replace('ShaderNodeTex', '')
        #row.label(text=title + ' Properties:', icon='TEXTURE')
        if custom_icon_enable:
            if texui.expand_content:
                icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
            else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
            row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_content', text='', emboss=True, icon='TEXTURE')
        row.label(text=title)

    if custom_icon_enable:
        row.menu('NODE_MT_y_add_texture_mask_menu', text='', icon_value = lib.custom_icons['add_mask'].icon_id)
    else: row.menu("NODE_MT_y_add_texture_mask_menu", text='', icon='MOD_MASK')

    row.context_pointer_set('parent', tex)
    #row.context_pointer_set('channel_ui', chui)
    if custom_icon_enable:
        icon_value = lib.custom_icons["add_modifier"].icon_id
        row.menu("NODE_MT_y_texture_modifier_specials", icon_value=icon_value, text='')
    else: row.menu("NODE_MT_y_texture_modifier_specials", icon='MODIFIER', text='')

    #row.separator()
    #row = row.row()

    if custom_icon_enable:
        row.prop(tlui, 'expand_channels', text='', emboss=True, icon_value = lib.custom_icons['channels'].icon_id)
    else: row.prop(tlui, 'expand_channels', text='', emboss=True, icon = 'GROUP_VERTEX')

    if tex.type != 'VCOL' and texui.expand_content:
        rrow = ccol.row(align=True)
        rrow.label(text='', icon='BLANK1')
        bbox = rrow.box()
        if image:
            draw_image_props(source, bbox)
        else: draw_tex_props(source, bbox)

        if tlui.expand_channels:
            rrow.label(text='', icon='BLANK1')

        ccol.separator()

    #row = ccol.row(align=True)
    #if custom_icon_enable:
    #    row.label(text='', icon_value = lib.custom_icons['channels'].icon_id)
    #else: row.label(text='',  icon = 'GROUP_VERTEX')
    #row.label(text='Channels:')

    if len(tex.channels) == 0:
        col.label(text='No channel found!', icon='ERROR')

    # Check if theres any mask bump
    mask_bump_found = any([c for i, c in enumerate(tex.channels) 
        if tl.channels[i].type == 'NORMAL' and c.enable_mask_bump and c.enable])

    ch_count = 0
    for i, ch in enumerate(tex.channels):

        if not tlui.expand_channels and not ch.enable:
            continue

        root_ch = tl.channels[i]
        ch_count += 1

        try: chui = tlui.tex_ui.channels[i]
        except: 
            tlui.need_update = True
            return

        ccol = col.column()
        ccol.active = ch.enable
        ccol.context_pointer_set('channel', ch)

        row = ccol.row(align=True)

        #expandable = len(tex.masks) > 0 or len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL'
        expandable = True
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

        if root_ch.type == 'NORMAL':
            row.prop(ch, 'normal_blend', text='')
        else: row.prop(ch, 'blend_type', text='')

        #intensity = tex_tree.nodes.get(ch.intensity)
        #row.prop(intensity.inputs[0], 'default_value', text='')
        row.prop(ch, 'intensity_value', text='')

        row.context_pointer_set('parent', ch)
        row.context_pointer_set('texture', tex)
        row.context_pointer_set('channel_ui', chui)

        if custom_icon_enable:
            icon_value = lib.custom_icons["add_modifier"].icon_id
            row.menu('NODE_MT_y_texture_modifier_specials', text='', icon_value=icon_value)
        else: row.menu('NODE_MT_y_texture_modifier_specials', text='', icon='MODIFIER')

        if tlui.expand_channels:
            row.prop(ch, 'enable', text='')

        if chui.expand_content:
            extra_separator = False

            if root_ch.type == 'NORMAL':

                if ch.normal_map_type == 'FINE_BUMP_MAP' and image:
                    neighbor_uv = tex_tree.nodes.get(ch.neighbor_uv)
                    cur_x = neighbor_uv.inputs[1].default_value 
                    cur_y = neighbor_uv.inputs[1].default_value 
                    if cur_x != image.size[0] or cur_y != image.size[1]:
                        brow = ccol.row(align=True)
                        brow.label(text='', icon='BLANK1')
                        #brow.label(text='', icon='BLANK1')
                        brow.alert = True
                        brow.context_pointer_set('channel', ch)
                        brow.context_pointer_set('image', image)
                        brow.operator('node.y_refresh_neighbor_uv', icon='ERROR')
                        if tlui.expand_channels:
                            brow.label(text='', icon='BLANK1')

                #if len(tex.masks) > 0 and (not mask_bump_found or ch.enable_mask_bump):
                brow = ccol.row(align=True)
                brow.label(text='', icon='BLANK1')
                #brow.label(text='', icon='INFO')
                if custom_icon_enable:
                    if chui.expand_mask_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    brow.prop(chui, 'expand_mask_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    brow.prop(chui, 'expand_mask_settings', text='', emboss=True, icon='MOD_MASK')
                brow.label(text='Intensity Bump:')

                if ch.enable_mask_bump and not chui.expand_mask_settings:
                    brow.prop(ch, 'mask_bump_value', text='')

                brow.prop(ch, 'enable_mask_bump', text='')

                if tlui.expand_channels:
                    brow.label(text='', icon='BLANK1')

                if chui.expand_mask_settings:
                    row = ccol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')

                    bbox = row.box()
                    cccol = bbox.column(align=True)

                    #crow = cccol.row(align=True)
                    #crow.label(text='Type:') #, icon='INFO')
                    #crow.prop(ch, 'mask_bump_type', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 1:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Edge 2:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_second_edge_value', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Distance:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_distance', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Type:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_type', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Mask Only:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_mask_only', text='')

                    crow = cccol.row(align=True)
                    crow.label(text='Flip:') #, icon='INFO')
                    crow.prop(ch, 'mask_bump_flip', text='')

                    if tlui.expand_channels:
                        row.label(text='', icon='BLANK1')

                row = ccol.row(align=True)
                row.label(text='', icon='BLANK1')

                if custom_icon_enable:
                    if chui.expand_bump_settings:
                        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                    row.prop(chui, 'expand_bump_settings', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(chui, 'expand_bump_settings', text='', emboss=True, icon='INFO')

                #else:
                #    row.label(text='', icon='INFO')
                if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                    split = row.split(percentage=0.275)
                else: split = row.split(factor=0.275)
                split.label(text='Type:') #, icon='INFO')
                srow = split.row(align=True)
                srow.prop(ch, 'normal_map_type', text='')
                if not chui.expand_bump_settings and ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
                    srow.prop(ch, 'bump_distance', text='')

                if tlui.expand_channels:
                    row.label(text='', icon='BLANK1')

                #if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'} and chui.expand_bump_settings:
                if chui.expand_bump_settings:
                    row = ccol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')

                    bbox = row.box()
                    cccol = bbox.column(align=True)

                    if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:

                        brow = cccol.row(align=True)
                        brow.label(text='Distance:') #, icon='INFO')
                        brow.prop(ch, 'bump_distance', text='')

                        brow = cccol.row(align=True)
                        brow.label(text='Bump Base:') #, icon='INFO')
                        brow.prop(ch, 'bump_base_value', text='')

                    brow = cccol.row(align=True)
                    brow.label(text='Invert Backface Normal')
                    brow.prop(ch, 'invert_backface_normal', text='')

                    if tlui.expand_channels:
                        row.label(text='', icon='BLANK1')

                extra_separator = True

            if root_ch.type in {'RGB', 'VALUE'}: #and len(tex.masks) > 0:
                row = ccol.row(align=True)
                row.label(text='', icon='BLANK1')

                ramp = tex_tree.nodes.get(ch.mr_ramp)
                if not ramp:
                    row.label(text='', icon='INFO')
                else:
                    if custom_icon_enable:
                        if chui.expand_mask_settings:
                            icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                        else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                        row.prop(chui, 'expand_mask_settings', text='', emboss=False, icon_value=icon_value)
                    else:
                        row.prop(chui, 'expand_mask_settings', text='', emboss=True, icon='MOD_MASK')
                row.label(text='Intensity Ramp:')
                if ch.enable_mask_ramp and not chui.expand_mask_settings:
                    row.prop(ch, 'mask_ramp_intensity_value', text='')
                row.prop(ch, 'enable_mask_ramp', text='')

                if tlui.expand_channels:
                    row.label(text='', icon='BLANK1')

                if ramp and chui.expand_mask_settings:
                    row = ccol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    bcol = box.column(align=False)
                    brow = bcol.row(align=True)
                    brow.label(text='Blend:')
                    brow.prop(ch, 'mask_ramp_blend_type', text='')
                    brow.prop(ch, 'mask_ramp_intensity_value', text='')
                    #brow.prop(ch, 'ramp_intensity_value', text='')
                    bcol.template_color_ramp(ramp, "color_ramp", expand=True)

                    if tlui.expand_channels:
                        row.label(text='', icon='BLANK1')

                extra_separator = True

            for j, m in enumerate(ch.modifiers):

                mod_tree = get_mod_tree(m)

                row = ccol.row(align=True)
                #row.active = m.enable
                row.label(text='', icon='BLANK1')

                try: modui = tlui.tex_ui.channels[i].modifiers[j]
                except: 
                    tlui.need_update = True
                    return

                can_be_expanded = m.type in Modifier.can_be_expanded #or (
                        #m.type == 'OVERRIDE_COLOR' and root_ch.type == 'NORMAL')

                if can_be_expanded:
                    if custom_icon_enable:
                        if modui.expand_content:
                            icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                        else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                        row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                    else:
                        row.prop(modui, 'expand_content', text='', emboss=True, icon='MODIFIER')
                else:
                    row.label(text='', icon='MODIFIER')

                row.label(text=m.name)

                if not modui.expand_content:

                    if m.type == 'RGB_TO_INTENSITY':
                        row.prop(m, 'rgb2i_col', text='', icon='COLOR')
                        row.separator()

                    if m.type == 'OVERRIDE_COLOR' and not m.oc_use_normal_base:
                        row.prop(m, 'oc_col', text='', icon='COLOR')
                        row.separator()

                row.context_pointer_set('texture', tex)
                row.context_pointer_set('parent', ch)
                row.context_pointer_set('modifier', m)
                row.menu("NODE_MT_y_modifier_menu", text='', icon='SCRIPTWIN')
                row.prop(m, 'enable', text='')

                if tlui.expand_channels:
                    row.label(text='', icon='BLANK1')

                if modui.expand_content and can_be_expanded:
                    row = ccol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')
                    bbox = row.box()
                    bbox.active = m.enable
                    Modifier.draw_modifier_properties(context, root_ch, mod_tree.nodes, m, bbox, True)

                    if tlui.expand_channels:
                        row.label(text='', icon='BLANK1')

                extra_separator = True

            if tex.type not in {'IMAGE', 'VCOL'}:
                row = ccol.row(align=True)
                row.label(text='', icon='BLANK1')

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
                if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                    split = row.split(percentage=0.275)
                else: split = row.split(factor=0.275)
                split.label(text='Input:')
                srow = split.row(align=True)
                srow.prop(ch, 'tex_input', text='')

                if tlui.expand_channels:
                    row.label(text='', icon='BLANK1')

                if chui.expand_input_settings and input_settings_available:
                    row = ccol.row(align=True)
                    row.label(text='', icon='BLANK1')
                    row.label(text='', icon='BLANK1')
                    box = row.box()
                    bcol = box.column(align=False)

                    brow = bcol.row(align=True)
                    brow.label(text='Gamma Space:')
                    brow.prop(ch, 'gamma_space', text='')

                    if tlui.expand_channels:
                        row.label(text='', icon='BLANK1')

                extra_separator = True

            if hasattr(ch, 'enable_blur'):
                row = ccol.row(align=True)
                row.label(text='', icon='BLANK1')
                row.label(text='', icon='INFO')
                row.label(text='Blur')
                row.prop(ch, 'enable_blur', text='')
                if tlui.expand_channels:
                    row.label(text='', icon='BLANK1')

                extra_separator = True

            if extra_separator:
                ccol.separator()

        #if i == len(tex.channels)-1: #and i > 0:
        #    ccol.separator()

    if not tlui.expand_channels and ch_count == 0:
        col.label(text='No active channel!')


    # Vector

    if tex.type != 'VCOL':

        #col.separator()
        ccol = col.column()
        ccol = col.column()
        row = ccol.row(align=True)

        if custom_icon_enable:
            if texui.expand_vector:
                icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
            else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
            row.prop(texui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
        else:
            row.prop(texui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            split = row.split(percentage=0.275, align=True)
        else: split = row.split(factor=0.275, align=True)
        split.label(text='Vector:')
        if is_a_mesh and tex.texcoord_type == 'UV':
            if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                ssplit = split.split(percentage=0.33, align=True)
            else: ssplit = split.split(factor=0.33, align=True)
            #ssplit = split.split(percentage=0.33, align=True)
            ssplit.prop(tex, 'texcoord_type', text='')
            ssplit.prop_search(tex, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
        else:
            split.prop(tex, 'texcoord_type', text='')

        #if tlui.expand_channels:
        #    row.label(text='', icon='BLANK1')

        if texui.expand_vector:
            row = ccol.row(align=True)
            row.label(text='', icon='BLANK1')
            bbox = row.box()
            crow = row.column()
            bbox.prop(source.texture_mapping, 'translation', text='Offset')
            bbox.prop(source.texture_mapping, 'rotation')
            bbox.prop(source.texture_mapping, 'scale')

            #if tlui.expand_channels:
            #    row.label(text='', icon='BLANK1')

    # Masks

    ccol = col.column()
    ccol = col.column()
    ccol.active = tex.enable_masks

    for j, mask in enumerate(tex.masks):

        try: maskui = tlui.tex_ui.masks[j]
        except: 
            tlui.need_update = True
            return

        row = ccol.row(align=True)
        row.active = mask.enable
        #row.label(text='', icon='BLANK1')
        #row.label(text='', icon='MOD_MASK')

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
            row.label(text=mask_image.name)
        else: row.label(text=mask.name)

        if mask.type == 'IMAGE':
            row.prop(mask, 'active_edit', text='', toggle=True, icon='IMAGE_DATA')
        elif mask.type == 'VCOL':
            row.prop(mask, 'active_edit', text='', toggle=True, icon='GROUP_VCOL')

        #row.separator()
        row.context_pointer_set('mask', mask)
        row.menu("NODE_MT_y_texture_mask_menu_special", text='', icon='SCRIPTWIN')

        row = row.row(align=True)
        row.prop(mask, 'enable', text='')

        #if tlui.expand_channels:
        #    row.label(text='', icon='BLANK1')

        if maskui.expand_content:
            row = ccol.row(align=True)
            row.active = mask.enable
            row.label(text='', icon='BLANK1')
            #row.label(text='', icon='BLANK1')
            rcol = row.column()

            #if tlui.expand_channels:
            #    row.label(text='', icon='BLANK1')

            # Source row
            rrow = rcol.row(align=True)

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
                rrow = rcol.row(align=True)
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                if mask_image:
                    draw_image_props(mask_source, rbox)
                else: draw_tex_props(mask_source, rbox)

            # Vector row
            if mask.type != 'VCOL':
                rrow = rcol.row(align=True)

                if custom_icon_enable:
                    if maskui.expand_vector:
                        icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                    rrow.prop(maskui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
                else:
                    rrow.prop(maskui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

                if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                    splits = rrow.split(percentage=0.3)
                else: splits = rrow.split(factor=0.3)
                #splits = rrow.split(percentage=0.3)
                splits.label(text='Vector:')
                if mask.texcoord_type != 'UV':
                    splits.prop(mask, 'texcoord_type', text='')
                else:
                    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                        rrrow = splits.split(percentage=0.35, align=True)
                    else: rrrow = splits.split(factor=0.35, align=True)
                    #rrrow = splits.split(percentage=0.35, align=True)
                    rrrow.prop(mask, 'texcoord_type', text='')
                    rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

                if maskui.expand_vector:
                    rrow = rcol.row(align=True)
                    rrow.label(text='', icon='BLANK1')
                    rbox = rrow.box()
                    rbox.prop(mask_source.texture_mapping, 'translation', text='Offset')
                    rbox.prop(mask_source.texture_mapping, 'rotation')
                    rbox.prop(mask_source.texture_mapping, 'scale')

                row.label(text='', icon='BLANK1')

            # Hardness row
            if mask.enable_hardness:
                rrow = rcol.row(align=True)
                rrow.label(text='', icon='MODIFIER')
                if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
                    splits = rrow.split(percentage=0.4)
                else: splits = rrow.split(factor=0.4)
                #splits = rrow.split(percentage=0.4)
                splits.label(text='Hardness:')
                splits.prop(mask, 'hardness_value', text='')

            # Mask Channels row
            rrow = rcol.row(align=True)
            if custom_icon_enable:
                if maskui.expand_channels:
                    icon_value = lib.custom_icons["uncollapsed_channels"].icon_id
                else: icon_value = lib.custom_icons["collapsed_channels"].icon_id
                rrow.prop(maskui, 'expand_channels', text='', emboss=False, icon_value=icon_value)
            else:
                rrow.prop(maskui, 'expand_channels', text='', emboss=True, icon='GROUP_VERTEX')
            rrow.label(text='Channels')

            if maskui.expand_channels:

                rrow = rcol.row()
                rrow.label(text='', icon='BLANK1')
                rbox = rrow.box()
                bcol = rbox.column(align=True)

                # Channels row
                for k, c in enumerate(mask.channels):
                    rrow = bcol.row(align=True)
                    root_ch = tl.channels[k]
                    if custom_icon_enable:
                        rrow.label(text='', icon_value=lib.custom_icons[lib.channel_custom_icon_dict[root_ch.type]].icon_id)
                    else:
                        rrow.label(text='', icon = lib.channel_icon_dict[root_ch.type].icon_id)
                    rrow.label(text=root_ch.name)
                    rrow.prop(c, 'enable', text='')

    # Mask effects

    ccol = col.column()
    #ccol = col.column()
    ccol.active = tex.enable_masks

def draw_textures_ui(context, layout, node, custom_icon_enable):
    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    tlui = context.window_manager.tlui
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

    # Check duplicated textures (indicated by more than one users)
    if len(tl.textures) > 0 and get_tree(tl.textures[-1]).users > 1:
        row = box.row(align=True)
        row.alert = True
        row.operator("node.y_fix_duplicated_textures", icon='ERROR')
        row.alert = False
        box.prop(tlui, 'make_image_single_user')
        return

    # Check source for missing data
    missing_data = False
    for tex in tl.textures:
        if tex.type in {'IMAGE' , 'VCOL'}:
            src = get_tex_source(tex)

            if ((tex.type == 'IMAGE' and not src.image) or 
                (tex.type == 'VCOL' and obj.type == 'MESH' 
                    and not obj.data.vertex_colors.get(src.attribute_name))
                ):
                missing_data = True
                break

            # Also check mask source
            for mask in tex.masks:
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

    # Get texture, image and set context pointer
    tex = None
    source = None
    image = None
    vcol = None
    mask_image = None
    mask = None
    mask_idx = 0

    if len(tl.textures) > 0:
        tex = tl.textures[tl.active_texture_index]

        if tex:
            # Check for active mask
            for i, m in enumerate(tex.masks):
                if m.active_edit:
                    mask = m
                    mask_idx = i
                    if m.type == 'IMAGE':
                        mask_tree = get_mask_tree(m)
                        source = mask_tree.nodes.get(m.source)
                        #image = source.image
                        mask_image = source.image

            # Use tex image if there is no mask image
            #if not mask:
            tex_tree = get_tree(tex)
            source = get_tex_source(tex, tex_tree)
            if tex.type == 'IMAGE':
                image = source.image
            elif tex.type == 'VCOL' and obj.type == 'MESH':
                vcol = obj.data.vertex_colors.get(source.attribute_name)

    # Set pointer for active texture and image
    if tex: box.context_pointer_set('texture', tex)
    if mask_image: box.context_pointer_set('image', mask_image)
    elif image: box.context_pointer_set('image', image)

    col = box.column()

    row = col.row()
    row.template_list("NODE_UL_y_tl_textures", "", tl,
            "textures", tl, "active_texture_index", rows=5, maxrows=5)  

    rcol = row.column(align=True)
    rcol.menu("NODE_MT_y_new_texture_layer_menu", text='', icon='ZOOMIN')
    rcol.operator("node.y_remove_texture_layer", icon='ZOOMOUT', text='')
    rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_UP').direction = 'UP'
    rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'
    rcol.menu("NODE_MT_y_texture_specials", text='', icon='DOWNARROW_HLT')

    #if mask:
    #    draw_mask_ui(context, box, tex, mask, mask_idx, source, image, is_a_mesh, custom_icon_enable)
    #elif tex:
    if tex:
        draw_texture_ui(context, box, tex, source, image, vcol, is_a_mesh, custom_icon_enable)

def main_draw(self, context):

    # Update ui props first
    update_tl_ui()

    if hasattr(lib, 'custom_icons'):
        custom_icon_enable = True
    else: custom_icon_enable = False

    node = get_active_texture_layers_node()

    layout = self.layout

    if not node:
        #layout.alert = True
        #layout.label(text="No active texture layers node!", icon='NODETREE')
        layout.label(text="No active texture layers node!", icon='ERROR')
        #layout.operator("node.y_quick_setup_texture_layers_node", icon='ERROR')
        layout.operator("node.y_quick_setup_texture_layers_node", icon='NODETREE')
        #layout.alert = False
        return

    #layout.label(text='Active: ' + node.node_tree.name, icon='NODETREE')
    row = layout.row(align=True)
    row.label(text='', icon='NODETREE')
    #row.label(text='Active: ' + node.node_tree.name)
    row.label(text=node.node_tree.name)
    #row.prop(node.node_tree, 'name', text='')
    row.menu("NODE_MT_y_tl_special_menu", text='', icon='SCRIPTWIN')

    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    tlui = context.window_manager.tlui

    icon = 'TRIA_DOWN' if tlui.show_channels else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_channels', emboss=False, text='', icon=icon)
    row.label(text='Channels')

    if tlui.show_channels:
        draw_root_channels_ui(context, layout, node, custom_icon_enable)

    icon = 'TRIA_DOWN' if tlui.show_textures else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_textures', emboss=False, text='', icon=icon)
    row.label(text='Textures')

    if tlui.show_textures:
        draw_textures_ui(context, layout, node, custom_icon_enable)

    # Hide support this addon panel for now
    return

    icon = 'TRIA_DOWN' if tlui.show_support else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_support', emboss=False, text='', icon=icon)
    row.label(text='Support This Addon!')

    if tlui.show_support:
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


class NODE_PT_y_texture_layers(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_label = "yTexLayers " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = "yTexLayers"

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type in possible_object_types 
                and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'} and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_y_texture_layers_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "yTexLayers " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = "yTexLayers"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_y_texture_layers_ui(bpy.types.Panel):
    bl_label = "yTexLayers " + get_current_version_str()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'} 

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine in {'CYCLES', 'BLENDER_EEVEE'}

    def draw(self, context):
        main_draw(self, context)

class NODE_UL_y_tl_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_layers_node()
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
            if BLENDER_28_GROUP_INPUT_HACK:
                if item.type == 'VALUE':
                    row.prop(item, 'val_input', text='') #, emboss=False)
                elif item.type == 'RGB':
                    row.prop(item, 'col_input', text='', icon='COLOR') #, emboss=False)
            else:
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

        if item.type=='RGB' and item.alpha:
            if len(inputs[item.io_index+1].links) == 0:
                if BLENDER_28_GROUP_INPUT_HACK:
                    row.prop(item,'val_input', text='')
                else: row.prop(inputs[item.io_index+1], 'default_value', text='')
            else: row.label(text='', icon='LINKED')

class NODE_UL_y_tl_textures(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_tree = item.id_data
        tl = group_tree.tl
        nodes = group_tree.nodes
        tex = item
        tex_tree = get_tree(tex)
        obj = context.object

        master = layout.row(align=True)
        row = master.row(align=True)

        # Try to get image
        image = None
        if tex.type == 'IMAGE':
            source = get_tex_source(tex, tex_tree)
            image = source.image

        # Try to get vertex color
        #vcol = None
        #if tex.type == 'VCOL':
        #    source = get_tex_source(tex, tex_tree)
        #    vcol = obj.data.vertex_colors.get(source.attribute_name)

        # Try to get image masks
        editable_masks = []
        active_image_mask = None
        for m in tex.masks:
            if m.type in {'IMAGE', 'VCOL'}:
                editable_masks.append(m)
                if m.active_edit:
                    active_image_mask = m

        # Image icon
        if len(editable_masks) == 0:
            if image: row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            #elif vcol: row.prop(vcol, 'name', text='', emboss=False, icon='GROUP_VCOL')
            elif tex.type == 'VCOL': row.prop(tex, 'name', text='', emboss=False, icon='GROUP_VCOL')
            else: row.prop(tex, 'name', text='', emboss=False, icon='TEXTURE')
        else:
            if active_image_mask:
                row.active = False
                if image: 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, 
                            icon_value=image.preview.icon_id)
                #elif vcol: 
                elif tex.type == 'VCOL': 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='GROUP_VCOL')
                else: 
                    row.prop(active_image_mask, 'active_edit', text='', emboss=False, icon='TEXTURE')
            else:
                if image: 
                    row.label(text='', icon_value=image.preview.icon_id)
                #elif vcol: 
                elif tex.type == 'VCOL': 
                    row.label(text='', icon='GROUP_VCOL')
                else: 
                    row.label(text='', icon='TEXTURE')

        # Image mask icons
        active_mask_image = None
        active_vcol_mask = None
        for m in editable_masks:
            mask_tree = get_mask_tree(m)
            row = master.row(align=True)
            row.active = m.active_edit
            if m.active_edit:
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

        # Active image/tex label
        if len(editable_masks) > 0:
            row = master.row(align=True)
            if active_mask_image:
                row.prop(active_mask_image, 'name', text='', emboss=False)
            elif active_vcol_mask:
                row.prop(active_vcol_mask, 'name', text='', emboss=False)
            else: 
                if image: row.prop(image, 'name', text='', emboss=False)
                else: row.prop(tex, 'name', text='', emboss=False)

        # Active image
        if active_mask_image: active_image = active_mask_image
        elif image: active_image = image
        else: active_image = None

        if active_image:
            # Asterisk icon to indicate dirty image
            if active_image.is_dirty:
                if hasattr(lib, 'custom_icons'):
                    row.label(text='', icon_value=lib.custom_icons['asterisk'].icon_id)
                else: row.label(text='', icon='PARTICLES')

            # Indicate packed image
            if active_image.packed_file:
                row.label(text='', icon='PACKAGE')

        # Modifier shortcut
        shortcut_found = False
        for ch in tex.channels:
            for mod in ch.modifiers:
                if mod.shortcut and mod.enable:

                    if mod.type == 'RGB_TO_INTENSITY':
                        rrow = row.row()
                        mod_tree = get_mod_tree(mod)
                        rrow.prop(mod, 'rgb2i_col', text='', icon='COLOR')
                        shortcut_found = True
                        break

                    elif mod.type == 'OVERRIDE_COLOR':
                        rrow = row.row()
                        mod_tree = get_mod_tree(mod)
                        rrow.prop(mod, 'oc_col', text='', icon='COLOR')
                        shortcut_found = True
                        break

            if shortcut_found:
                break

        # Mask visibility
        if len(tex.masks) > 0:
            row = master.row()
            row.active = tex.enable_masks
            row.prop(tex, 'enable_masks', emboss=False, text='', icon='MOD_MASK')

        # Texture visibility
        row = master.row()
        if hasattr(lib, 'custom_icons'):
            if tex.enable: eye_icon = 'RESTRICT_VIEW_OFF'
            else: eye_icon = 'RESTRICT_VIEW_ON'
        else:
            if tex.enable: eye_icon = 'HIDE_OFF'
            else: eye_icon = 'HIDE_ON'
        row.prop(tex, 'enable', emboss=False, text='', icon=eye_icon)

class YTLSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_tl_special_menu"
    bl_label = "Texture Layers Special Menu"
    bl_description = "Texture Layers Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

    def draw(self, context):
        self.layout.operator('node.y_rename_tl_tree')

class YNewTexMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_texture_layer_menu"
    bl_description = 'New Texture Layer'
    bl_label = "Texture Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

    def draw(self, context):
        #row = self.layout.row()
        #col = row.column()
        col = self.layout.column(align=True)
        #col.context_pointer_set('group_node', context.group_node)
        col.label(text='Image:')
        col.operator("node.y_new_texture_layer", text='New Image', icon='IMAGE_DATA').type = 'IMAGE'
        col.operator("node.y_open_image_to_layer", text='Open Image', icon='IMASEL')
        col.operator("node.y_open_available_image_to_layer", text='Open Available Image', icon='IMASEL')
        col.separator()

        col.label(text='Vertex Color:')
        col.operator("node.y_new_texture_layer", icon='GROUP_VCOL', text='Vertex Color').type = 'VCOL'
        col.separator()

        #col = row.column()
        col.label(text='Generated:')
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Checker').type = 'CHECKER'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Magic').type = 'MAGIC'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Noise').type = 'NOISE'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Wave').type = 'WAVE'

class YTexSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_specials"
    bl_label = "Texture Special Menu"
    bl_description = "Texture Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

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
        return hasattr(context, 'modifier') and hasattr(context, 'parent') and get_active_texture_layers_node()

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        op = col.operator('node.y_move_texture_modifier', icon='TRIA_UP', text='Move Modifier Up')
        op.direction = 'UP'

        op = col.operator('node.y_move_texture_modifier', icon='TRIA_DOWN', text='Move Modifier Down')
        op.direction = 'DOWN'

        col.separator()
        op = col.operator('node.y_remove_texture_modifier', icon='ZOOMOUT', text='Remove Modifier')

        #if hasattr(context, 'texture') and context.modifier.type in {'RGB_TO_INTENSITY', 'OVERRIDE_COLOR'}:
        #    col.separator()
        #    col.prop(context.modifier, 'shortcut', text='Shortcut on texture list')

class YAddTexMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_add_texture_mask_menu"
    bl_description = 'Add Texture Mask'
    bl_label = "Add Texture Mask"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'texture')
        #node =  get_active_texture_layers_node()
        #return node and len(node.node_tree.tl.textures) > 0

    def draw(self, context):
        #print(context.texture)
        layout = self.layout
        row = layout.row()
        col = row.column(align=True)
        col.context_pointer_set('texture', context.texture)

        col.label(text='Image Mask:')
        col.operator('node.y_new_texture_mask', icon='IMAGE_DATA', text='New Image Mask').type = 'IMAGE'
        col.label(text='Open Image as Mask', icon='IMASEL')
        col.label(text='Open Available Image as Mask', icon='IMASEL')
        #col.label(text='Not implemented yet!', icon='ERROR')
        col.separator()
        #col.label(text='Open Mask:')
        #col.label(text='Open Other Mask', icon='MOD_MASK')

        col.label(text='Vertex Color Mask:')
        col.operator('node.y_new_texture_mask', text='New Vertex Color Mask', icon='GROUP_VCOL').type = 'VCOL'
        col.label(text='Open Available Vertex Color as Mask', icon='GROUP_VCOL')

        col = row.column(align=True)
        #col.separator()
        col.label(text='Generated Mask:')
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Checker').type = 'CHECKER'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Gradient').type = 'GRADIENT'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Magic').type = 'MAGIC'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Musgrave').type = 'MUSGRAVE'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Noise').type = 'NOISE'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Voronoi').type = 'VORONOI'
        col.operator("node.y_new_texture_mask", icon='TEXTURE', text='Wave').type = 'WAVE'

class YTexMaskMenuSpecial(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_mask_menu_special"
    bl_description = 'Texture Mask Menu'
    bl_label = "Texture Mask Menu"

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'texture')

    def draw(self, context):
        #print(context.mask)
        mask = context.mask
        tex = context.texture
        tex_tree = get_tree(tex)
        layout = self.layout
        col = layout.column(align=True)
        if mask.type == 'IMAGE':
            mask_tree = get_mask_tree(mask)
            source = mask_tree.nodes.get(mask.source)
            col.context_pointer_set('image', source.image)
            col.operator('node.y_invert_image', text='Invert Image', icon='IMAGE_ALPHA')
        col.prop(mask, 'enable_hardness', text='Hardness')
        col.separator()
        col.operator('node.y_remove_texture_mask', text='Remove Mask', icon='ZOOMOUT')

def update_modifier_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl

    match1 = re.match(r'tlui\.tex_ui\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tlui\.channel_ui\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        mod = tl.textures[tl.active_texture_index].channels[int(match1.group(1))].modifiers[int(match1.group(2))]
    elif match2:
        mod = tl.channels[tl.active_channel_index].modifiers[int(match2.group(1))]
    #else: return #yolo

    mod.expand_content = self.expand_content

def update_texture_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.textures) == 0: return

    tex = tl.textures[tl.active_texture_index]
    tex.expand_content = self.expand_content
    tex.expand_vector = self.expand_vector
    tex.expand_masks = self.expand_masks

def update_channel_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.channels) == 0: return

    match1 = re.match(r'tlui\.tex_ui\.channels\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tlui\.channel_ui', self.path_from_id())

    if match1:
        ch = tl.textures[tl.active_texture_index].channels[int(match1.group(1))]
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
    if hasattr(ch, 'expand_mask_settings'):
        ch.expand_mask_settings = self.expand_mask_settings
    if hasattr(ch, 'expand_input_settings'):
        ch.expand_input_settings = self.expand_input_settings

def update_mask_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    #if len(tl.channels) == 0: return

    match = re.match(r'tlui\.tex_ui\.masks\[(\d+)\]', self.path_from_id())
    mask = tl.textures[tl.active_texture_index].masks[int(match.group(1))]

    mask.expand_content = self.expand_content
    mask.expand_channels = self.expand_channels
    mask.expand_source = self.expand_source
    mask.expand_vector = self.expand_vector

def update_mask_channel_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    #if len(tl.channels) == 0: return

    match = re.match(r'tlui\.tex_ui\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    mask = tl.textures[tl.active_texture_index].masks[int(match.group(1))]
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
    expand_mask_settings = BoolProperty(default=True, update=update_channel_ui)
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

class YTextureUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=False, update=update_texture_ui)
    expand_vector = BoolProperty(default=False, update=update_texture_ui)
    expand_masks = BoolProperty(default=False, update=update_texture_ui)

    channels = CollectionProperty(type=YChannelUI)
    masks = CollectionProperty(type=YMaskUI)

#def update_mat_active_tl_node(self, context):
#    print('Update:', self.active_tl_node)

class YMaterialUI(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    active_tl_node = StringProperty(default='') #, update=update_mat_active_tl_node)

class YTLUI(bpy.types.PropertyGroup):
    show_channels = BoolProperty(default=True)
    show_textures = BoolProperty(default=True)
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
    
    # Texture related UI
    tex_idx = IntProperty(default=0)
    tex_ui = PointerProperty(type=YTextureUI)

    #mask_ui = PointerProperty(type=YMaskUI)

    # Group channel related UI
    channel_idx = IntProperty(default=0)
    channel_ui = PointerProperty(type=YChannelUI)
    modifiers = CollectionProperty(type=YModifierUI)

    # Update related
    need_update = BoolProperty(default=False)
    halt_prop_update = BoolProperty(default=False)

    # Duplicated texture related
    make_image_single_user = BoolProperty(
            name = 'Make Images Single User',
            description = 'Make duplicated image textures single user',
            default=True)

    # HACK: For some reason active float image will glitch after auto save
    # This prop will notify if float image is active after saving
    refresh_image_hack = BoolProperty(default=False)

    materials = CollectionProperty(type=YMaterialUI)
    #active_obj = StringProperty(default='')
    active_mat = StringProperty(default='')
    active_tl_node = StringProperty(default='')

    #random_prop = BoolProperty(default=False)

def add_new_tl_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine not in {'CYCLES', 'BLENDER_EEVEE'}: return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_texture_layers_node', text='Texture Layers', icon='NODETREE')

def copy_ui_settings(source, dest):
    for attr in dir(source):
        if attr.startswith(('show_', 'expand_')) or attr.endswith('_name'):
            setattr(dest, attr, getattr(source, attr))

def save_mat_ui_settings():
    tlui = bpy.context.window_manager.tlui
    for mui in tlui.materials:
        mat = bpy.data.materials.get(mui.name)
        if mat: mat.tl.active_tl_node = mui.active_tl_node

def load_mat_ui_settings():
    tlui = bpy.context.window_manager.tlui
    for mat in bpy.data.materials:
        if mat.tl.active_tl_node != '':
            mui = tlui.materials.add()
            mui.name = mat.name
            mui.material = mat
            mui.active_tl_node = mat.tl.active_tl_node

@persistent
def ytl_save_ui_settings(scene):
    save_mat_ui_settings()
    wmui = bpy.context.window_manager.tlui
    scui = bpy.context.scene.tlui
    copy_ui_settings(wmui, scui)

@persistent
def ytl_load_ui_settings(scene):
    load_mat_ui_settings()
    wmui = bpy.context.window_manager.tlui
    scui = bpy.context.scene.tlui
    copy_ui_settings(scui, wmui)

    # Update texture UI
    wmui.need_update = True

def register():
    bpy.utils.register_class(YTLSpecialMenu)
    bpy.utils.register_class(YNewTexMenu)
    bpy.utils.register_class(YTexSpecialMenu)
    bpy.utils.register_class(YModifierMenu)
    bpy.utils.register_class(YAddTexMaskMenu)
    bpy.utils.register_class(YTexMaskMenuSpecial)
    #bpy.utils.register_class(YTexMaskBumpMenuSpecial)
    #bpy.utils.register_class(YTexMaskRampMenuSpecial)
    bpy.utils.register_class(YModifierUI)
    bpy.utils.register_class(YChannelUI)
    bpy.utils.register_class(YMaskChannelUI)
    bpy.utils.register_class(YMaskUI)
    bpy.utils.register_class(YTextureUI)
    bpy.utils.register_class(YMaterialUI)
    bpy.utils.register_class(NODE_UL_y_tl_channels)
    bpy.utils.register_class(NODE_UL_y_tl_textures)
    bpy.utils.register_class(NODE_PT_y_texture_layers)
    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        bpy.utils.register_class(VIEW3D_PT_y_texture_layers_tools)
    bpy.utils.register_class(VIEW3D_PT_y_texture_layers_ui)
    bpy.utils.register_class(YTLUI)

    bpy.types.Scene.tlui = PointerProperty(type=YTLUI)
    bpy.types.WindowManager.tlui = PointerProperty(type=YTLUI)

    # Add texture layers node ui
    bpy.types.NODE_MT_add.append(add_new_tl_node_menu)

    # Handlers
    bpy.app.handlers.load_post.append(ytl_load_ui_settings)
    bpy.app.handlers.save_pre.append(ytl_save_ui_settings)

def unregister():
    bpy.utils.unregister_class(YTLSpecialMenu)
    bpy.utils.unregister_class(YNewTexMenu)
    bpy.utils.unregister_class(YTexSpecialMenu)
    bpy.utils.unregister_class(YModifierMenu)
    bpy.utils.unregister_class(YAddTexMaskMenu)
    bpy.utils.unregister_class(YTexMaskMenuSpecial)
    #bpy.utils.unregister_class(YTexMaskBumpMenuSpecial)
    #bpy.utils.unregister_class(YTexMaskRampMenuSpecial)
    bpy.utils.unregister_class(YModifierUI)
    bpy.utils.unregister_class(YChannelUI)
    bpy.utils.unregister_class(YMaskChannelUI)
    bpy.utils.unregister_class(YMaskUI)
    bpy.utils.unregister_class(YTextureUI)
    bpy.utils.unregister_class(YMaterialUI)
    bpy.utils.unregister_class(NODE_UL_y_tl_channels)
    bpy.utils.unregister_class(NODE_UL_y_tl_textures)
    bpy.utils.unregister_class(NODE_PT_y_texture_layers)
    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        bpy.utils.unregister_class(VIEW3D_PT_y_texture_layers_tools)
    bpy.utils.unregister_class(VIEW3D_PT_y_texture_layers_ui)
    bpy.utils.unregister_class(YTLUI)

    # Remove add texture layers node ui
    bpy.types.NODE_MT_add.remove(add_new_tl_node_menu)

    # Remove Handlers
    bpy.app.handlers.load_post.remove(ytl_load_ui_settings)
    bpy.app.handlers.save_pre.remove(ytl_save_ui_settings)
