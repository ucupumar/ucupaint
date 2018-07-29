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
                c.expand_content = ch.expand_content
                for j, mod in enumerate(ch.modifiers):
                    m = c.modifiers.add()
                    m.expand_content = mod.expand_content

            # Construct texture masks UI objects
            for i, mask in enumerate(tex.masks):
                m = tlui.tex_ui.masks.add()
                m.expand_content = mask.expand_content
                m.expand_source = mask.expand_source
                m.expand_vector = mask.expand_vector

        tlui.halt_prop_update = False

def draw_image_props(source, layout):

    image = source.image

    col = layout.column()
    col.template_ID(source, "image", unlink='node.y_remove_texture_layer')
    if image.source == 'GENERATED':
        col.label('Generated image settings:')
        row = col.row()

        col1 = row.column(align=True)
        col1.prop(image, 'generated_width', text='X')
        col1.prop(image, 'generated_height', text='Y')

        col1.prop(image, 'use_generated_float', text='Float Buffer')
        col2 = row.column(align=True)
        col2.prop(image, 'generated_type', expand=True)

        row = col.row()
        row.label('Color:')
        row.prop(image, 'generated_color', text='')
        col.template_colorspace_settings(image, "colorspace_settings")

    elif image.source == 'FILE':
        if not image.filepath:
            col.label('Image Path: -')
        else:
            col.label('Path: ' + image.filepath)

        image_format = 'RGBA'
        image_bit = int(image.depth/4)
        if image.depth in {24, 48, 96}:
            image_format = 'RGB'
            image_bit = int(image.depth/3)

        col.label('Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                ' ' + image_format + ' ' + str(image_bit) + '-bit')

        col.template_colorspace_settings(image, "colorspace_settings")
        #col.prop(image, 'use_view_as_render')
        col.prop(image, 'alpha_mode')
        col.prop(image, 'use_alpha')
        #col.prop(image, 'use_fields')

def draw_tex_props(source, layout):

    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(title + ' Properties:')
    #col.separator()

    if title == 'Brick':
        row = col.row()
        col = row.column(align=True)
        col.label('Offset:')
        col.label('Frequency:')
        col.separator()

        col.label('Squash:')
        col.label('Frequency:')
        col.separator()

        col.label('Color 1:')
        col.label('Color 2:')
        col.label('Mortar:')
        col.separator()
        col.label('Scale:')
        col.label('Mortar Size:')
        col.label('Mortar Smooth:')
        col.label('Bias:')
        col.label('Brick Width:')
        col.label('Brick Height:')

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
        col.label('Color 1:')
        col.label('Color 2:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        for i in range (1,4):
            if i == 3: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Gradient':

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col = row.column(align=True)
        col.prop(source, 'gradient_type', text='')

    elif title == 'Magic':

        row = col.row()
        col = row.column(align=True)
        col.label('Depth:')
        col.label('Scale:')
        col.label('Distortion:')
        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')

    elif title == 'Musgrave':

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col.separator()
        col.label('Scale:')
        col.label('Detail:')
        col.label('Dimension:')
        col.label('Lacunarity:')
        col.label('Offset:')
        col.label('Gain:')
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
        col.label('Scale:')
        col.label('Detail:')
        col.label('Distortion:')
        col = row.column(align=True)
        for i in range (1,4):
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Voronoi':

        row = col.row()
        col = row.column(align=True)
        col.label('Coloring:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        col.prop(source, 'coloring', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')

    elif title == 'Wave':

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col.label('Profile:')
        col.label('Scale:')
        col.label('Distortion:')
        col.label('Detail:')
        col.label('Detail Scale:')
        col = row.column(align=True)
        col.prop(source, 'wave_type', text='')
        col.prop(source, 'wave_profile', text='')
        col.separator()
        for i in range (1,5):
            col.prop(source.inputs[i], 'default_value', text='')

def main_draw(self, context):

    # Update ui props first
    update_tl_ui()

    if hasattr(lib, 'custom_icons'):
        custom_icon_enable = True
    else: custom_icon_enable = False

    obj = context.object
    is_a_mesh = True if obj and obj.type == 'MESH' else False
    #node = get_active_texture_layers_node()
    node = get_active_texture_layers_node()

    layout = self.layout

    if not node:
        #layout.alert = True
        #layout.label("No active texture layers node!", icon='NODETREE')
        layout.label("No active texture layers node!", icon='ERROR')
        #layout.operator("node.y_quick_setup_texture_layers_node", icon='ERROR')
        layout.operator("node.y_quick_setup_texture_layers_node", icon='NODETREE')
        #layout.alert = False
        return

    #layout.label('Active: ' + node.node_tree.name, icon='NODETREE')
    row = layout.row(align=True)
    row.label('', icon='NODETREE')
    #row.label('Active: ' + node.node_tree.name)
    row.label(node.node_tree.name)
    #row.prop(node.node_tree, 'name', text='')
    row.menu("NODE_MT_y_tl_special_menu", text='', icon='SCRIPTWIN')

    group_tree = node.node_tree
    nodes = group_tree.nodes
    tl = group_tree.tl
    tlui = context.window_manager.tlui

    icon = 'TRIA_DOWN' if tlui.show_channels else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_channels', emboss=False, text='', icon=icon)
    row.label('Channels')

    #tlui.random_prop = True
    #tl.random_prop = True

    if tlui.show_channels:

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

            row.label(channel.name + ' Channel')

            if channel.type != 'NORMAL':
                row.context_pointer_set('parent', channel)
                row.context_pointer_set('channel_ui', chui)
                if custom_icon_enable:
                    icon_value = lib.custom_icons["add_modifier"].icon_id
                    row.menu("NODE_MT_y_texture_modifier_specials", icon_value=icon_value, text='')
                else:
                    row.menu("NODE_MT_y_texture_modifier_specials", icon='MODIFIER', text='')

            if chui.expand_content:

                row = mcol.row(align=True)
                row.label('', icon='BLANK1')
                bcol = row.column()

                for i, m in enumerate(channel.modifiers):

                    try: modui = chui.modifiers[i]
                    except: 
                        tlui.need_update = True
                        return

                    brow = bcol.row(align=True)
                    #brow.active = m.enable
                    if m.type in Modifier.can_be_expanded:
                        if custom_icon_enable:
                            if modui.expand_content:
                                icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                            else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                            brow.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                        else:
                            brow.prop(modui, 'expand_content', text='', emboss=False, icon='MODIFIER')
                        brow.label(m.name)
                    else:
                        brow.label('', icon='MODIFIER')
                        brow.label(m.name)

                    if m.type == 'RGB_TO_INTENSITY':
                        brow.prop(m, 'rgb2i_col', text='', icon='COLOR')
                        brow.separator()

                    #brow.context_pointer_set('texture', tex)
                    brow.context_pointer_set('parent', channel)
                    brow.context_pointer_set('modifier', m)
                    brow.menu("NODE_MT_y_modifier_menu", text='', icon='SCRIPTWIN')
                    brow.prop(m, 'enable', text='')

                    if modui.expand_content and m.type in Modifier.can_be_expanded:
                        row = bcol.row(align=True)
                        #row.label('', icon='BLANK1')
                        row.label('', icon='BLANK1')
                        bbox = row.box()
                        bbox.active = m.enable
                        Modifier.draw_modifier_properties(context, channel, nodes, m, bbox)
                        row.label('', icon='BLANK1')

                #if len(channel.modifiers) > 0:
                #    brow = bcol.row(align=True)
                #    brow.label('', icon='TEXTURE')
                #    brow.label('Textures happen here..')

                inp = node.inputs[channel.io_index]

                brow = bcol.row(align=True)

                #if channel.type == 'NORMAL':
                #    if chui.expand_base_vector:
                #        icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                #    else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                #    brow.prop(chui, 'expand_base_vector', text='', emboss=False, icon_value=icon_value)
                #else: brow.label('', icon='INFO')

                brow.label('', icon='INFO')

                if channel.type == 'RGB':
                    brow.label('Background:')
                elif channel.type == 'VALUE':
                    brow.label('Base Value:')
                elif channel.type == 'NORMAL':
                    #if chui.expand_base_vector:
                    #    brow.label('Base Normal:')
                    #else: brow.label('Base Normal')
                    brow.label('Base Normal')

                if channel.type == 'NORMAL':
                    #if chui.expand_base_vector:
                    #    brow = bcol.row(align=True)
                    #    brow.label('', icon='BLANK1')
                    #    brow.prop(inp,'default_value', text='')
                    pass
                elif len(inp.links) == 0:
                    brow.prop(inp,'default_value', text='')
                else:
                    brow.label('', icon='LINKED')

                if len(channel.modifiers) > 0:
                    brow.label('', icon='BLANK1')

                if channel.type == 'RGB':
                    brow = bcol.row(align=True)
                    brow.label('', icon='INFO')
                    if channel.alpha:
                        inp_alpha = node.inputs[channel.io_index+1]
                        #brow = bcol.row(align=True)
                        #brow.label('', icon='BLANK1')
                        brow.label('Base Alpha:')
                        if len(node.inputs[channel.io_index+1].links)==0:
                            brow.prop(inp_alpha, 'default_value', text='')
                        else:
                            brow.label('', icon='LINKED')
                    else:
                        brow.label('Alpha:')
                    brow.prop(channel, 'alpha', text='')

                    #if len(channel.modifiers) > 0:
                    #    brow.label('', icon='BLANK1')

                if channel.type in {'RGB', 'VALUE'}:
                    brow = bcol.row(align=True)
                    brow.label('', icon='INFO')
                    split = brow.split(percentage=0.375)
                    split.label('Space:')
                    split.prop(channel, 'colorspace', text='')

    icon = 'TRIA_DOWN' if tlui.show_textures else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_textures', emboss=False, text='', icon=icon)
    row.label('Textures')

    if tlui.show_textures:

        box = layout.box()

        # Check if uv is found
        uv_found = False
        if is_a_mesh and len(obj.data.uv_layers) > 0: 
            uv_found = True

        if is_a_mesh and not uv_found:
            row = box.row(align=True)
            row.alert = True
            row.operator("node.y_add_simple_uvs", icon='ERROR')
            row.alert = False
            return

        # Check duplicated textures (indicated by 4 users)
        if len(tl.textures) > 0 and get_tree(tl.textures[-1]).users > 1:
        #if len(tl.textures) > 0 and get_tree(tl.textures[0]).users > 1:
            row = box.row(align=True)
            row.alert = True
            row.operator("node.y_fix_duplicated_textures", icon='ERROR')
            row.alert = False
            box.prop(tlui, 'make_image_single_user')
            return

        # Get texture, image and set context pointer
        tex = None
        source = None
        image = None
        if len(tl.textures) > 0:
            tex = tl.textures[tl.active_texture_index]
            tex_tree = get_tree(tex)
            box.context_pointer_set('texture', tex)

            source = get_tex_source(tex, tex_tree)

            active_image = None # Active image on list
            image = None # Global texture image

            # Check for active mask
            for m in tex.masks:
                if m.type == 'IMAGE' and m.active_edit:
                    mask_tree = get_mask_tree(m)
                    src = mask_tree.nodes.get(m.source)
                    active_image = src.image

            # Use tex image if there is no mask image
            if tex.type == 'IMAGE':
                image = source.image
                if not active_image:
                    active_image = image

            # Set pointer for active image
            if active_image:
                box.context_pointer_set('image', active_image)

        col = box.column()

        row = col.row()
        row.template_list("NODE_UL_y_tl_textures", "", tl,
                "textures", tl, "active_texture_index", rows=5, maxrows=5)  

        rcol = row.column(align=True)
        #rcol.operator_menu_enum("node.y_new_texture_layer", 'type', icon='ZOOMIN', text='')
        #rcol.context_pointer_set('group_node', node)
        rcol.menu("NODE_MT_y_new_texture_layer_menu", text='', icon='ZOOMIN')
        rcol.operator("node.y_remove_texture_layer", icon='ZOOMOUT', text='')
        rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_UP').direction = 'UP'
        rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'
        rcol.menu("NODE_MT_y_texture_specials", text='', icon='DOWNARROW_HLT')

        col = box.column()

        if tex:

            col.active = tex.enable

            texui = tlui.tex_ui

            ccol = col.column() #align=True)
            row = ccol.row(align=True)
            
            if image:
                if custom_icon_enable:
                    if texui.expand_content:
                        icon_value = lib.custom_icons["uncollapsed_image"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_image"].icon_id
                    row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(texui, 'expand_content', text='', emboss=True, icon='IMAGE_DATA')
                row.label(image.name)
                #row.operator("node.y_single_user_image_copy", text="2")
                #row.operator("node.y_reload_image", text="", icon='FILE_REFRESH')
                #row.separator()
            else:
                title = source.bl_idname.replace('ShaderNodeTex', '')
                #row.label(title + ' Properties:', icon='TEXTURE')
                if custom_icon_enable:
                    if texui.expand_content:
                        icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_texture"].icon_id
                    row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(texui, 'expand_content', text='', emboss=True, icon='TEXTURE')
                row.label(title)

            if custom_icon_enable:
                row.prop(tlui, 'expand_channels', text='', emboss=True, icon_value = lib.custom_icons['channels'].icon_id)
            else: row.prop(tlui, 'expand_channels', text='', emboss=True, icon = 'GROUP_VERTEX')

            if texui.expand_content:
                rrow = ccol.row(align=True)
                rrow.label('', icon='BLANK1')
                bbox = rrow.box()
                if image:
                    draw_image_props(source, bbox)
                else: draw_tex_props(source, bbox)

                if tlui.expand_channels:
                    rrow.label('', icon='BLANK1')

                ccol.separator()

            if len(tex.channels) == 0:
                col.label('No channel found!', icon='ERROR')

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

                if custom_icon_enable:
                    icon_name = lib.channel_custom_icon_dict[root_ch.type]
                    if len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL':
                        if chui.expand_content:
                            icon_name = 'uncollapsed_' + icon_name
                        else: icon_name = 'collapsed_' + icon_name
                    icon_value = lib.custom_icons[icon_name].icon_id
                    if len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL':
                        row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                    else: row.label('', icon_value=icon_value)
                else:
                    icon = lib.channel_icon_dict[root_ch.type]
                    if len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL':
                        row.prop(chui, 'expand_content', text='', emboss=True, icon=icon)
                    else: row.label('', icon=icon)

                row.label(tl.channels[i].name + ':')

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
                else:
                    row.menu('NODE_MT_y_texture_modifier_specials', text='', icon='MODIFIER')

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
                                brow.label('', icon='BLANK1')
                                #brow.label('', icon='BLANK1')
                                brow.alert = True
                                brow.context_pointer_set('channel', ch)
                                brow.context_pointer_set('image', image)
                                brow.operator('node.y_refresh_neighbor_uv', icon='ERROR')
                                if tlui.expand_channels:
                                    brow.label('', icon='BLANK1')

                        row = ccol.row(align=True)
                        row.label('', icon='BLANK1')
                        if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:

                            if custom_icon_enable:
                                if chui.expand_bump_settings:
                                    icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                                else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                                row.prop(chui, 'expand_bump_settings', text='', emboss=False, icon_value=icon_value)
                            else:
                                row.prop(chui, 'expand_bump_settings', text='', emboss=True, icon='INFO')

                        else:
                            row.label('', icon='INFO')
                        split = row.split(percentage=0.275)
                        split.label('Type:') #, icon='INFO')
                        split.prop(ch, 'normal_map_type', text='')

                        if tlui.expand_channels:
                            row.label('', icon='BLANK1')

                        if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'} and chui.expand_bump_settings:
                            row = ccol.row(align=True)
                            row.label('', icon='BLANK1')
                            row.label('', icon='BLANK1')

                            bbox = row.box()
                            cccol = bbox.column(align=True)

                            bump = tex_tree.nodes.get(ch.bump)

                            brow = cccol.row(align=True)
                            brow.label('Bump Base:') #, icon='INFO')
                            brow.prop(ch, 'bump_base_value', text='')

                            #cccol.separator()
                            #brow = cccol.row(align=True)
                            #brow.label('Intensity Multiplier:') #, icon='INFO')
                            #brow.prop(ch, 'intensity_multiplier_value', text='')
                            #brow.prop(ch, 'intensity_multiplier_link', toggle=True, text='', icon='LINKED')

                            if tlui.expand_channels:
                                row.label('', icon='BLANK1')

                        brow = ccol.row(align=True)
                        brow.label('', icon='BLANK1')
                        brow.label('', icon='INFO')
                        #if ch.normal_map_type == 'BUMP_MAP':
                        brow.label('Distance:') #, icon='INFO')
                        brow.prop(ch, 'bump_distance', text='')
                        #elif ch.normal_map_type == 'FINE_BUMP_MAP':
                        #    brow.label('Scale:') #, icon='INFO')
                        #    brow.prop(ch, 'fine_bump_scale', text='')
                        if tlui.expand_channels:
                            brow.label('', icon='BLANK1')

                        if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
                            row = ccol.row(align=True)
                            row.label('', icon='BLANK1')

                            if custom_icon_enable:
                                if chui.expand_intensity_settings:
                                    icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                                else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                                row.prop(chui, 'expand_intensity_settings', text='', emboss=False, icon_value=icon_value)
                            else: 
                                row.prop(chui, 'expand_intensity_settings', text='', emboss=True, icon='INFO')

                            #row.label('', icon='INFO')
                            row.label('Intensity Multiplier:') #, icon='INFO')
                            row.prop(ch, 'intensity_multiplier_value', text='')
                            row.prop(ch, 'intensity_multiplier_link', toggle=True, text='', icon='LINKED')
                            if tlui.expand_channels:
                                row.label('', icon='BLANK1')
                            
                            if chui.expand_intensity_settings:
                                row = ccol.row(align=True)
                                row.label('', icon='BLANK1')
                                row.label('', icon='BLANK1')

                                bbox = row.box()
                                bbox.active = ch.intensity_multiplier_link
                                cccol = bbox.column(align=True)

                                #bbbox = cccol.box()
                                #brow = bbbox.row(align=True)
                                #brow.label('Intensity Multiplier Settings') #, icon='INFO')

                                brow = cccol.row(align=True)
                                brow.label('Link All Channels:') #, icon='INFO')
                                brow.prop(ch, 'im_link_all_channels', text='')

                                brow = cccol.row(align=True)
                                brow.label('Link All Masks:') #, icon='INFO')
                                brow.prop(ch, 'im_link_all_masks', text='')

                                brow = cccol.row(align=True)
                                brow.label('Invert Others:') #, icon='INFO')
                                brow.prop(ch, 'im_invert_others', text='')

                                brow = cccol.row(align=True)
                                brow.label('Sharpen:') #, icon='INFO')
                                brow.prop(ch, 'im_sharpen', text='')

                                if tlui.expand_channels:
                                    row.label('', icon='BLANK1')

                        row = ccol.row(align=True)
                        row.label('', icon='BLANK1')
                        row.label('', icon='INFO')
                        row.label('Invert Backface Normal')
                        row.prop(ch, 'invert_backface_normal', text='')
                        if tlui.expand_channels:
                            row.label('', icon='BLANK1')

                        extra_separator = True

                    for j, m in enumerate(ch.modifiers):

                        mod_tree = get_mod_tree(m)

                        row = ccol.row(align=True)
                        #row.active = m.enable
                        row.label('', icon='BLANK1')

                        try: modui = tlui.tex_ui.channels[i].modifiers[j]
                        except: 
                            tlui.need_update = True
                            return

                        if m.type in Modifier.can_be_expanded:
                            if custom_icon_enable:
                                if modui.expand_content:
                                    icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                                else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                                row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                            else:
                                row.prop(modui, 'expand_content', text='', emboss=True, icon='MODIFIER')
                        else:
                            row.label('', icon='MODIFIER')

                        #row.label(m.name + ' (' + str(m.texture_index) + ')')
                        row.label(m.name)

                        if m.type == 'RGB_TO_INTENSITY':
                            row.prop(m, 'rgb2i_col', text='', icon='COLOR')
                            row.separator()

                        row.context_pointer_set('texture', tex)
                        row.context_pointer_set('parent', ch)
                        row.context_pointer_set('modifier', m)
                        row.menu("NODE_MT_y_modifier_menu", text='', icon='SCRIPTWIN')
                        row.prop(m, 'enable', text='')

                        if tlui.expand_channels:
                            row.label('', icon='BLANK1')

                        if modui.expand_content and m.type in Modifier.can_be_expanded:
                            row = ccol.row(align=True)
                            row.label('', icon='BLANK1')
                            row.label('', icon='BLANK1')
                            bbox = row.box()
                            bbox.active = m.enable
                            Modifier.draw_modifier_properties(context, root_ch, mod_tree.nodes, m, bbox)

                            if tlui.expand_channels:
                                row.label('', icon='BLANK1')

                        extra_separator = True

                    if tex.type != 'IMAGE':
                        row = ccol.row(align=True)
                        row.label('', icon='BLANK1')
                        row.label('', icon='INFO')
                        split = row.split(percentage=0.275)
                        split.label('Input:')
                        split.prop(ch, 'tex_input', text='')

                        if tlui.expand_channels:
                            row.label('', icon='BLANK1')

                        extra_separator = True

                    #if hasattr(ch, 'is_mod_tree'):
                    #    row = ccol.row(align=True)
                    #    row.label('', icon='BLANK1')
                    #    row.label('', icon='INFO')
                    #    row.label('Mod Tree')
                    #    row.prop(ch, 'is_mod_tree', text='')
                    #    if tlui.expand_channels:
                    #        row.label('', icon='BLANK1')

                    #    extra_separator = True

                    if hasattr(ch, 'enable_blur'):
                        row = ccol.row(align=True)
                        row.label('', icon='BLANK1')
                        row.label('', icon='INFO')
                        row.label('Blur')
                        row.prop(ch, 'enable_blur', text='')
                        if tlui.expand_channels:
                            row.label('', icon='BLANK1')

                        extra_separator = True

                    if extra_separator:
                        ccol.separator()

                #if i == len(tex.channels)-1: #and i > 0:
                #    ccol.separator()

            if not tlui.expand_channels and ch_count == 0:
                col.label('No active channel!')

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

            split = row.split(percentage=0.275, align=True)
            split.label('Vector:')
            if is_a_mesh and tex.texcoord_type == 'UV':
                ssplit = split.split(percentage=0.33, align=True)
                ssplit.prop(tex, 'texcoord_type', text='')
                ssplit.prop_search(tex, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            else:
                split.prop(tex, 'texcoord_type', text='')

            if texui.expand_vector:
                row = ccol.row()
                row.label('', icon='BLANK1')
                bbox = row.box()
                crow = row.column()
                bbox.prop(source.texture_mapping, 'translation', text='Offset')
                bbox.prop(source.texture_mapping, 'rotation')
                bbox.prop(source.texture_mapping, 'scale')

            #col.separator()
            ccol = col.column()
            ccol = col.column()

            row = ccol.row(align=True)
            row.active = tex.enable_masks
            if len(tex.masks) == 0:
                row.label('', icon='MOD_MASK')
            else: 
                if custom_icon_enable:
                    if texui.expand_masks:
                        icon_value = lib.custom_icons["uncollapsed_mask"].icon_id
                    else: icon_value = lib.custom_icons["collapsed_mask"].icon_id
                    row.prop(texui, 'expand_masks', text='', emboss=False, icon_value=icon_value)
                else:
                    row.prop(texui, 'expand_masks', text='', emboss=True, icon='MOD_MASK')

            if len(tex.masks) > 1:
                label = 'Masks:'
            else: label = 'Mask:'

            if len(tex.masks) == 0:
                row.label(label + ' -')

            else: row.label(label)
            row.menu("NODE_MT_y_add_texture_mask_menu", text='', icon='ZOOMIN')

            #if len(tex.masks) > 0:
            #    row.prop(tex, 'enable_masks', text='')

            if texui.expand_masks:
                ccol = col.column()
                ccol.active = tex.enable_masks

                image_masks_count = len([m for m in tex.masks if m.type == 'IMAGE'])

                for j, mask in enumerate(tex.masks):

                    try: maskui = tlui.tex_ui.masks[j]
                    except: 
                        tlui.need_update = True
                        return

                    row = ccol.row(align=True)
                    row.active = mask.enable
                    row.label('', icon='BLANK1')
                    #row.label('', icon='MOD_MASK')

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
                        row.label(mask_image.name)
                        #row.prop(mask_image, 'name', text='', emboss=False)
                    else:
                        row.label(mask.name)

                    if mask.type == 'IMAGE':
                        row.prop(mask, 'active_edit', text='', toggle=True, icon='IMAGE_DATA')
                    #else:
                    #    #row.prop(mask, 'active_edit', text='', toggle=True, icon='TEXTURE')
                    #    row.label('', icon='TEXTURE')

                    #row.separator()
                    row.context_pointer_set('mask', mask)
                    row.menu("NODE_MT_y_texture_mask_menu_special", text='', icon='SCRIPTWIN')

                    row = row.row(align=True)
                    row.prop(mask, 'enable', text='')
                    #row.label('', icon='BLANK1')

                    if maskui.expand_content:
                        row = ccol.row(align=True)
                        row.active = mask.enable
                        row.label('', icon='BLANK1')
                        row.label('', icon='BLANK1')
                        rcol = row.column()

                        # Channels row
                        for k, c in enumerate(mask.channels):
                            rrow = rcol.row(align=True)
                            root_ch = tl.channels[k]
                            if custom_icon_enable:
                                rrow.label('', icon_value=lib.custom_icons[lib.channel_custom_icon_dict[root_ch.type]].icon_id)
                            else:
                                rrow.label('', icon = lib.channel_icon_dict[root_ch.type].icon_id)
                            rrow.label(root_ch.name)
                            rrow.prop(c, 'enable', text='')

                            if root_ch.type == 'NORMAL':

                                rrow = rcol.row(align=True)
                                rrow.label('', icon='BLANK1')
                                rrow.label('', icon='INFO')
                                rrow.label('Bump')
                                rrow.prop(c, 'enable_bump', text='')

                                rrow = rcol.row(align=True)
                                rrow.label('', icon='BLANK1')
                                rrow.label('', icon='INFO')
                                splits = rrow.split(percentage=0.4)
                                splits.label('Bump Height')
                                splits.prop(c, 'bump_height', text='')
                                #rrow.label('', icon='BLANK1')

                            elif root_ch.type == 'RGB':

                                rrow = rcol.row(align=True)
                                rrow.label('', icon='BLANK1')
                                rrow.label('', icon='INFO')
                                rrow.label('Ramp')
                                rrow.prop(c, 'enable_ramp', text='')

                                if c.enable_ramp:
                                    rrow = rcol.row(align=True)
                                    rrow.label('', icon='BLANK1')
                                    rrow.label('', icon='BLANK1')
                                    bbbox = rrow.box()
                                    cccol = bbbox.column(align=False)
                                    rrrow = cccol.row(align=True)
                                    rrrow.prop(c, 'ramp_blend_type', text='')
                                    rrrow.prop(c, 'ramp_intensity_value', text='')
                                    ramp = tex_tree.nodes.get(c.ramp)
                                    cccol.template_color_ramp(ramp, "color_ramp", expand=True)

                        # Hardness row
                        if mask.enable_hardness:
                            rrow = rcol.row(align=True)
                            rrow.label('', icon='MODIFIER')
                            splits = rrow.split(percentage=0.4)
                            splits.label('Hardness:')
                            splits.prop(mask, 'hardness_value', text='')

                        # Source row
                        rrow = rcol.row(align=True)

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
                            rrow.label('Source: ' + mask_image.name)
                        else: rrow.label('Source: ' + mask.name)

                        if maskui.expand_source:
                            rrow = rcol.row(align=True)
                            rrow.label('', icon='BLANK1')
                            rbox = rrow.box()
                            if mask_image:
                                draw_image_props(mask_source, rbox)
                            else: draw_tex_props(mask_source, rbox)

                        # Vector row
                        rrow = rcol.row(align=True)

                        if custom_icon_enable:
                            if maskui.expand_vector:
                                icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
                            else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
                            rrow.prop(maskui, 'expand_vector', text='', emboss=False, icon_value=icon_value)
                        else:
                            rrow.prop(maskui, 'expand_vector', text='', emboss=True, icon='GROUP_UVS')

                        splits = rrow.split(percentage=0.3)
                        splits.label('Vector:')
                        rrrow = splits.row(align=True)
                        rrrow.prop(mask, 'texcoord_type', text='')
                        if mask.texcoord_type == 'UV':
                            rrrow.prop_search(mask, "uv_name", obj.data, "uv_layers", text='')

                        if maskui.expand_vector:
                            rrow = rcol.row(align=True)
                            rrow.label('', icon='BLANK1')
                            rbox = rrow.box()
                            rbox.prop(mask_source.texture_mapping, 'translation', text='Offset')
                            rbox.prop(mask_source.texture_mapping, 'rotation')
                            rbox.prop(mask_source.texture_mapping, 'scale')

                        #bcol.label('Ahahah')
                        row.label('', icon='BLANK1')

    # Hide support this addon panel for now
    return

    icon = 'TRIA_DOWN' if tlui.show_support else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_support', emboss=False, text='', icon=icon)
    row.label('Support This Addon!')

    if tlui.show_support:
        box = layout.box()
        col = box.column()
        col.alert = True
        col.operator('wm.url_open', text='Become A Patron!', icon='POSE_DATA').url = 'https://www.patreon.com/ucupumar'
        col.alert = False
        col.label('Patron List (June 2018):')
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
            if BLENDER_28_HACK:
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
            row.label('', icon='LINKED')

        if item.type=='RGB' and item.alpha:
            if len(inputs[item.io_index+1].links) == 0:
                row.prop(inputs[item.io_index+1], 'default_value', text='')
            else: row.label('', icon='LINKED')

class NODE_UL_y_tl_textures(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_tree = item.id_data
        tl = group_tree.tl
        nodes = group_tree.nodes
        tex = item
        tex_tree = get_tree(tex)

        master = layout.row(align=True)
        row = master.row(align=True)

        # Try to get image
        image = None
        if tex.type == 'IMAGE':
            source = get_tex_source(tex, tex_tree)
            image = source.image

        # Try to get image masks
        image_masks = []
        active_mask = None
        for m in tex.masks:
            if m.type == 'IMAGE':
                image_masks.append(m)
                if m.active_edit:
                    active_mask = m

        # Image icon
        if len(image_masks) == 0:
            if image: row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)
            else: row.prop(tex, 'name', text='', emboss=False, icon='TEXTURE')
        else:
            if active_mask:
                row.active = False
                if image: row.prop(active_mask, 'active_edit', text='', emboss=False, icon_value=image.preview.icon_id)
                else: row.prop(active_mask, 'active_edit', text='', emboss=False, icon='TEXTURE')
            else:
                if image: row.label('', icon_value=image.preview.icon_id)
                else: row.label('', icon='TEXTURE')

        # Image mask icons
        active_mask_image = None
        for m in image_masks:
            mask_tree = get_mask_tree(m)
            src = mask_tree.nodes.get(m.source)
            row = master.row(align=True)
            row.active = m.active_edit
            if m.active_edit:
                active_mask_image = src.image
                row.label('', icon_value=src.image.preview.icon_id)
            else:
                row.prop(m, 'active_edit', text='', emboss=False, icon_value=src.image.preview.icon_id)

        # Active image/tex label
        if len(image_masks) > 0:
            row = master.row(align=True)
            if active_mask_image:
                row.prop(active_mask_image, 'name', text='', emboss=False)
            else: 
                if image: row.prop(image, 'name', text='', emboss=False)
                else: row.prop(tex, 'name', text='', emboss=False)

        # Active image
        if active_mask_image: active_image = active_mask_image
        elif image: active_image = image
        else: active_image = None

        if active_image:
            # Asterisk icon to indicate dirty image and also for saving/packing
            if active_image.is_dirty:
                #if active_image.packed_file or active_image.filepath == '':
                #    row.operator('node.y_pack_image', text='', icon_value=lib.custom_icons['asterisk'].icon_id, emboss=False)
                #else: row.operator('node.y_save_image', text='', icon_value=lib.custom_icons['asterisk'].icon_id, emboss=False)
                if hasattr(lib, 'custom_icons'):
                    row.label('', icon_value=lib.custom_icons['asterisk'].icon_id)
                else:
                    row.label('', icon='PARTICLES')

            # Indicate packed image
            if active_image.packed_file:
                row.label(text='', icon='PACKAGE')

        #blend = nodes.get(tex.channels[channel_idx].blend)
        #row.prop(blend, 'blend_type', text ='')

        #intensity = nodes.get(tex.channels[channel_idx].intensity)
        #row.prop(intensity.inputs[0], 'default_value', text='')

        #row = master.row()
        #if tex.enable: row.active = True
        #else: row.active = False
        #row.prop(tex.channels[channel_idx], 'enable', text='')

        # Modifier shortcut
        shortcut_found = False
        for ch in tex.channels:
            for mod in ch.modifiers:
                if mod.shortcut:
                    shortcut_found = True
                    if mod.type == 'RGB_TO_INTENSITY':
                        rrow = row.row()
                        mod_tree = get_mod_tree(mod)
                        rrow.prop(mod, 'rgb2i_col', text='', icon='COLOR')
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
        col.label('Image:')
        col.operator("node.y_new_texture_layer", text='New Image', icon='IMAGE_DATA').type = 'IMAGE'
        col.operator("node.y_open_image_to_layer", text='Open Image', icon='IMASEL')
        col.operator("node.y_open_available_image_to_layer", text='Open Available Image', icon='IMASEL')
        col.separator()

        #col = row.column()
        col.label('Generated:')
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

        if hasattr(context, 'texture') and context.modifier.type == 'RGB_TO_INTENSITY':
            col.separator()
            col.prop(context.modifier, 'shortcut', text='Shortcut on texture list')

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
        col = layout.column(align=True)
        col.context_pointer_set('texture', context.texture)

        col.label('Image Mask:')
        col.operator('node.y_new_texture_mask', icon='IMAGE_DATA', text='New Image Mask').type = 'IMAGE'
        col.label('Open Image as Mask', icon='IMASEL')
        col.label('Open Available Image as Mask', icon='IMASEL')
        #col.label('Not implemented yet!', icon='ERROR')
        col.separator()
        #col.label('Open Mask:')
        col.label('Open Other Mask', icon='MOD_MASK')

        col.separator()
        col.label('Generated Mask:')
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

def update_mask_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.channels) == 0: return

    match = re.match(r'tlui\.tex_ui\.masks\[(\d+)\]', self.path_from_id())
    mask = tl.textures[tl.active_texture_index].masks[int(match.group(1))]

    mask.expand_content = self.expand_content
    mask.expand_source = self.expand_source
    mask.expand_vector = self.expand_vector

class YMaskUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=True, update=update_mask_ui)
    expand_source = BoolProperty(default=True, update=update_mask_ui)
    expand_vector = BoolProperty(default=True, update=update_mask_ui)

class YModifierUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=True, update=update_modifier_ui)

class YChannelUI(bpy.types.PropertyGroup):
    #name = StringProperty(default='')
    expand_content = BoolProperty(default=False, update=update_channel_ui)
    expand_bump_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_intensity_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_base_vector = BoolProperty(default=True, update=update_channel_ui)
    modifiers = CollectionProperty(type=YModifierUI)

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

    # To store active node and tree
    tree_name = StringProperty(default='')
    
    # Texture related UI
    tex_idx = IntProperty(default=0)
    tex_ui = PointerProperty(type=YTextureUI)

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
    bpy.utils.register_class(YMaskUI)
    bpy.utils.register_class(YModifierUI)
    bpy.utils.register_class(YChannelUI)
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
    bpy.utils.unregister_class(YMaskUI)
    bpy.utils.unregister_class(YModifierUI)
    bpy.utils.unregister_class(YChannelUI)
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
