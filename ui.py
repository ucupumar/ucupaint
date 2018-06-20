import bpy
from bpy.props import *
from bpy.app.handlers import persistent
from . import lib, Modifier
from .common import *

def draw_tex_props(group_tree, tex, layout):

    nodes = group_tree.nodes
    tl = group_tree.tl

    if tex.source_tree:
        source = tex.source_tree.nodes.get(tex.source)
    else: source = tex.tree.nodes.get(tex.source)
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
    obj = context.object
    is_a_mesh = True if obj and obj.type == 'MESH' else False
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

    if tlui.show_channels:

        box = layout.box()
        col = box.column()
        row = col.row()

        rcol = row.column()
        if len(tl.channels) > 0:
            pcol = rcol.column()
            if tl.preview_mode: pcol.alert = True
            pcol.prop(tl, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')

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

            if channel.type == 'RGB':
                icon_name = 'rgb_channel'
            elif channel.type == 'VALUE':
                icon_name = 'value_channel'
            elif channel.type == 'NORMAL':
                icon_name = 'vector_channel'

            if chui.expand_content:
                icon_name = 'uncollapsed_' + icon_name
            else: icon_name = 'collapsed_' + icon_name

            icon_value = lib.custom_icons[icon_name].icon_id

            row = mcol.row(align=True)
            row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
            row.label(channel.name + ' Channel')

            if channel.type != 'NORMAL':
                row.context_pointer_set('parent', channel)
                row.context_pointer_set('channel_ui', chui)
                icon_value = lib.custom_icons["add_modifier"].icon_id
                row.menu("NODE_MT_y_texture_modifier_specials", icon_value=icon_value, text='')

            if chui.expand_content:

                row = mcol.row(align=True)
                row.label('', icon='BLANK1')
                bcol = row.column()

                for i, m in enumerate(channel.modifiers):

                    modui = chui.modifiers[i]

                    brow = bcol.row(align=True)
                    #brow.active = m.enable
                    if m.type in Modifier.can_be_expanded:
                        if modui.expand_content:
                            icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                        else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                        brow.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                        brow.label(m.name)
                    else:
                        brow.label('', icon='MODIFIER')
                        brow.label(m.name)

                    if m.type == 'RGB_TO_INTENSITY':
                        rgb2i = nodes.get(m.rgb2i)
                        brow.prop(rgb2i.inputs[2], 'default_value', text='', icon='COLOR')
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
                    split.prop(channel, 'non_color_data', text='')

    icon = 'TRIA_DOWN' if tlui.show_textures else 'TRIA_RIGHT'
    row = layout.row(align=True)
    row.prop(tlui, 'show_textures', emboss=False, text='', icon=icon)
    row.label('Textures')

    if tlui.show_textures:

        box = layout.box()

        # Check if uv is found
        uv_found = False
        if is_a_mesh and len(obj.data.uv_textures) > 0: 
            uv_found = True

        if is_a_mesh and not uv_found:
            row = box.row(align=True)
            row.alert = True
            row.operator("node.y_add_simple_uvs", icon='ERROR')
            row.alert = False
            return

        # Check duplicated textures (indicated by 4 users)
        if len(tl.textures) > 0 and tl.textures[0].tree.users > 3:
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
            box.context_pointer_set('texture', tex)

            if tex.source_tree:
                source = tex.source_tree.nodes.get(tex.source)
            else: source = tex.tree.nodes.get(tex.source)
            if tex.type == 'IMAGE':
                image = source.image
                box.context_pointer_set('image', image)

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
                if texui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_image"].icon_id
                else: icon_value = lib.custom_icons["collapsed_image"].icon_id

                row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                row.label(image.name)
                #row.operator("node.y_single_user_image_copy", text="2")
                #row.operator("node.y_reload_image", text="", icon='FILE_REFRESH')
                #row.separator()
            else:
                title = source.bl_idname.replace('ShaderNodeTex', '')
                #row.label(title + ' Properties:', icon='TEXTURE')
                if texui.expand_content:
                    icon_value = lib.custom_icons["uncollapsed_texture"].icon_id
                else: icon_value = lib.custom_icons["collapsed_texture"].icon_id

                row.prop(texui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                row.label(title)

            row.prop(tlui, 'expand_channels', text='', emboss=True, icon_value = lib.custom_icons['channels'].icon_id)

            if texui.expand_content:
                rrow = ccol.row(align=True)
                rrow.label('', icon='BLANK1')
                bbox = rrow.box()
                if not image:
                    draw_tex_props(group_tree, tex, bbox)
                else:
                    incol = bbox.column()
                    incol.template_ID(source, "image", unlink='node.y_remove_texture_layer')
                    if image.source == 'GENERATED':
                        incol.label('Generated image settings:')
                        row = incol.row()

                        col1 = row.column(align=True)
                        col1.prop(image, 'generated_width', text='X')
                        col1.prop(image, 'generated_height', text='Y')

                        col1.prop(image, 'use_generated_float', text='Float Buffer')
                        col2 = row.column(align=True)
                        col2.prop(image, 'generated_type', expand=True)

                        row = incol.row()
                        row.label('Color:')
                        row.prop(image, 'generated_color', text='')
                        incol.template_colorspace_settings(image, "colorspace_settings")

                    elif image.source == 'FILE':
                        if not image.filepath:
                            incol.label('Image Path: -')
                        else:
                            incol.label('Path: ' + image.filepath)

                        image_format = 'RGBA'
                        image_bit = int(image.depth/4)
                        if image.depth in {24, 48, 96}:
                            image_format = 'RGB'
                            image_bit = int(image.depth/3)

                        incol.label('Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                                ' ' + image_format + ' ' + str(image_bit) + '-bit')

                        incol.template_colorspace_settings(image, "colorspace_settings")
                        #incol.prop(image, 'use_view_as_render')
                        incol.prop(image, 'alpha_mode')
                        incol.prop(image, 'use_alpha')
                        #incol.prop(image, 'use_fields')
                        #incol.template_image(tex, "image", tex.image_user)

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

                if root_ch.type == 'RGB':
                    icon_name = 'rgb_channel'
                elif root_ch.type == 'VALUE':
                    icon_name = 'value_channel'
                elif root_ch.type == 'NORMAL':
                    icon_name = 'vector_channel'

                if len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL':
                    if chui.expand_content:
                        icon_name = 'uncollapsed_' + icon_name
                    else: icon_name = 'collapsed_' + icon_name

                icon_value = lib.custom_icons[icon_name].icon_id

                row = ccol.row(align=True)
                if len(ch.modifiers) > 0 or tex.type != 'IMAGE' or root_ch.type == 'NORMAL':
                    row.prop(chui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                else: row.label('', icon_value=icon_value)

                #row.label(tl.channels[i].name +' (' + str(ch.channel_index) + ')'+ ':')
                #row.label(tl.channels[i].name +' (' + str(ch.texture_index) + ')'+ ':')
                row.label(tl.channels[i].name + ':')

                if root_ch.type == 'NORMAL':
                    row.prop(ch, 'normal_blend', text='')
                else: row.prop(ch, 'blend_type', text='')

                intensity = tex.tree.nodes.get(ch.intensity)
                row.prop(intensity.inputs[0], 'default_value', text='')

                row.context_pointer_set('parent', ch)
                row.context_pointer_set('texture', tex)
                row.context_pointer_set('channel_ui', chui)
                icon_value = lib.custom_icons["add_modifier"].icon_id
                row.menu('NODE_MT_y_texture_modifier_specials', text='', icon_value=icon_value)

                if tlui.expand_channels:
                    row.prop(ch, 'enable', text='')

                if chui.expand_content:
                    extra_separator = False

                    if root_ch.type == 'NORMAL':
                        row = ccol.row(align=True)
                        row.label('', icon='BLANK1')
                        if ch.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
                            if chui.expand_bump_settings:
                                icon_value = lib.custom_icons["uncollapsed_input"].icon_id
                            else: icon_value = lib.custom_icons["collapsed_input"].icon_id
                            row.prop(chui, 'expand_bump_settings', text='', emboss=False, icon_value=icon_value)
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

                            bump = tex.tree.nodes.get(ch.bump)

                            brow = cccol.row(align=True)
                            brow.label('Bump Base:') #, icon='INFO')
                            brow.prop(ch, 'bump_base_value', text='')

                            brow = cccol.row(align=True)
                            if ch.normal_map_type == 'BUMP_MAP':
                                brow.label('Distance:') #, icon='INFO')
                                brow.prop(ch, 'bump_distance', text='')
                            elif ch.normal_map_type == 'FINE_BUMP_MAP':
                                brow.label('Scale:') #, icon='INFO')
                                brow.prop(ch, 'fine_bump_scale', text='')

                            brow = cccol.row(align=True)
                            brow.label('Intensity Multiplier:') #, icon='INFO')
                            brow.prop(ch, 'intensity_multiplier_value', text='')

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

                        row = ccol.row(align=True)
                        #row.active = m.enable
                        row.label('', icon='BLANK1')

                        try: modui = tlui.tex_ui.channels[i].modifiers[j]
                        except: 
                            tlui.need_update = True
                            return

                        if m.type in Modifier.can_be_expanded:
                            if modui.expand_content:
                                icon_value = lib.custom_icons["uncollapsed_modifier"].icon_id
                            else: icon_value = lib.custom_icons["collapsed_modifier"].icon_id
                            row.prop(modui, 'expand_content', text='', emboss=False, icon_value=icon_value)
                        else:
                            row.label('', icon='MODIFIER')

                        #row.label(m.name + ' (' + str(m.texture_index) + ')')
                        row.label(m.name)

                        if m.type == 'RGB_TO_INTENSITY':
                            if ch.mod_tree:
                                rgb2i = ch.mod_tree.nodes.get(m.rgb2i)
                            else: rgb2i = tex.tree.nodes.get(m.rgb2i)
                            row.prop(rgb2i.inputs[2], 'default_value', text='', icon='COLOR')
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
                            if ch.mod_tree:
                                Modifier.draw_modifier_properties(context, ch, ch.mod_tree.nodes, m, bbox)
                            else: Modifier.draw_modifier_properties(context, ch, tex.tree.nodes, m, bbox)

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

            #row.label('', icon='MOD_MASK')
            #row.label('Mask')
            #icon_value = lib.custom_icons["add_mask"].icon_id
            #row.menu("NODE_MT_y_new_texture_mask_menu", text='', icon_value=icon_value)
            ##row.menu("NODE_MT_y_new_texture_mask_menu", text='', icon='ZOOMIN')

            #col.separator()
            #ccol = col.column()
            #row = ccol.row(align=True)

            if texui.expand_vector:
                icon_value = lib.custom_icons["uncollapsed_uv"].icon_id
            else: icon_value = lib.custom_icons["collapsed_uv"].icon_id
            row.prop(texui, 'expand_vector', text='', emboss=False, icon_value=icon_value)

            split = row.split(percentage=0.275, align=True)
            split.label('Vector:')
            if is_a_mesh and tex.texcoord_type == 'UV':
                ssplit = split.split(percentage=0.33, align=True)
                ssplit.prop(tex, 'texcoord_type', text='')
                ssplit.prop_search(tex, "uv_name", obj.data, "uv_textures", text='')
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
                and context.scene.render.engine == 'CYCLES' and context.space_data.tree_type == 'ShaderNodeTree')

    def draw(self, context):
        main_draw(self, context)

class VIEW3D_PT_y_texture_layers_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "yTexLayers " + get_current_version_str()
    bl_region_type = 'TOOLS'
    bl_category = "yTexLayers"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in possible_object_types and context.scene.render.engine == 'CYCLES'

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
        return context.object and context.object.type in possible_object_types and context.scene.render.engine == 'CYCLES'

    def draw(self, context):
        main_draw(self, context)

class NODE_UL_y_tl_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_layers_node()
        #if not group_node: return
        inputs = group_node.inputs

        if item.type == 'RGB':
            icon_value = lib.custom_icons["rgb_channel"].icon_id
        elif item.type == 'VALUE':
            icon_value = lib.custom_icons["value_channel"].icon_id
        elif item.type == 'NORMAL':
            icon_value = lib.custom_icons["vector_channel"].icon_id

        row = layout.row()
        row.prop(item, 'name', text='', emboss=False, icon_value=icon_value)

        if item.type == 'RGB':
            row = row.row(align=True)

        if len(inputs[item.io_index].links) == 0:
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

        group_node = get_active_texture_layers_node()
        #if not group_node: return
        tl = group_node.node_tree.tl
        nodes = group_node.node_tree.nodes

        # Get active channel
        #channel_idx = tl.active_channel_index
        #channel = tl.channels[channel_idx]

        master = layout.row(align=True)

        row = master.row(align=True)
        #row.active = item.enable

        #if not item.enable or not item.channels[channel_idx].enable: row.active = False

        if item.type == 'IMAGE':
            if item.source_tree:
                source = item.source_tree.nodes.get(item.source)
            else: source = item.tree.nodes.get(item.source)
            image = source.image
            row.context_pointer_set('image', image)
            row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)

            # Asterisk icon to indicate dirty image and also for saving/packing
            if image.is_dirty:
                #if image.packed_file or image.filepath == '':
                #    row.operator('node.y_pack_image', text='', icon_value=lib.custom_icons['asterisk'].icon_id, emboss=False)
                #else: row.operator('node.y_save_image', text='', icon_value=lib.custom_icons['asterisk'].icon_id, emboss=False)
                row.label('', icon_value=lib.custom_icons['asterisk'].icon_id)

            # Indicate packed image
            if image.packed_file:
                row.label(text='', icon='PACKAGE')

        else:
            row.prop(item, 'name', text='', emboss=False, icon='TEXTURE')

        #blend = nodes.get(item.channels[channel_idx].blend)
        #row.prop(blend, 'blend_type', text ='')

        #intensity = nodes.get(item.channels[channel_idx].intensity)
        #row.prop(intensity.inputs[0], 'default_value', text='')

        #row = master.row()
        #if item.enable: row.active = True
        #else: row.active = False
        #row.prop(item.channels[channel_idx], 'enable', text='')

        # Modifier shortcut
        shortcut_found = False
        for ch in item.channels:
            for mod in ch.modifiers:
                if mod.shortcut:
                    shortcut_found = True
                    if mod.type == 'RGB_TO_INTENSITY':
                        rrow = row.row()
                        if ch.mod_tree:
                            rgb2i = ch.mod_tree.nodes.get(mod.rgb2i)
                        else: rgb2i = item.tree.nodes.get(mod.rgb2i)
                        rrow.prop(rgb2i.inputs[2], 'default_value', text='', icon='COLOR')
                    break
            if shortcut_found:
                break

        # Texture visibility
        row = master.row()
        if item.enable: eye_icon = 'RESTRICT_VIEW_OFF'
        else: eye_icon = 'RESTRICT_VIEW_ON'
        row.prop(item, 'enable', emboss=False, text='', icon=eye_icon)

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

class YNewTexMaskMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_texture_mask_menu"
    bl_description = 'New Texture Mask'
    bl_label = "New Texture Mask"

    @classmethod
    def poll(cls, context):
        node =  get_active_texture_layers_node()
        return node and len(node.node_tree.tl.textures) > 0

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label('Not implemented yet!', icon='ERROR')

def update_modifier_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl

    # Index -1 means modifier parent is group channel
    if self.ch_index == -1:
        mod = tl.channels[tl.active_channel_index].modifiers[self.index]
    else: mod = tl.textures[tl.active_texture_index].channels[self.ch_index].modifiers[self.index]

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

def update_channel_ui(self, context):
    tlui = context.window_manager.tlui
    if tlui.halt_prop_update: return

    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tl = group_node.node_tree.tl
    if len(tl.channels) == 0: return

    # Index -1 means this is group channel
    if self.index == -1:
        ch = tl.channels[tl.active_channel_index]
    else: 
        if len(tl.textures) == 0: return
        ch = tl.textures[tl.active_texture_index].channels[self.index]

    ch.expand_content = self.expand_content
    if hasattr(ch, 'expand_bump_settings'):
        ch.expand_bump_settings = self.expand_bump_settings
    if hasattr(ch, 'expand_base_vector'):
        ch.expand_base_vector = self.expand_base_vector

class YModifierUI(bpy.types.PropertyGroup):
    index = IntProperty(default=0)
    ch_index = IntProperty(default=-1)
    expand_content = BoolProperty(default=True, update=update_modifier_ui)

class YChannelUI(bpy.types.PropertyGroup):
    index = IntProperty(default=-1)
    expand_content = BoolProperty(default=False, update=update_channel_ui)
    expand_bump_settings = BoolProperty(default=False, update=update_channel_ui)
    expand_base_vector = BoolProperty(default=True, update=update_channel_ui)
    modifiers = CollectionProperty(type=YModifierUI)

class YTextureUI(bpy.types.PropertyGroup):
    expand_content = BoolProperty(default=False, update=update_texture_ui)
    expand_vector = BoolProperty(default=False, update=update_texture_ui)
    channels = CollectionProperty(type=YChannelUI)

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

def add_new_tl_node_menu(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine != 'CYCLES': return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_texture_layers_node', text='Texture Layers', icon='NODETREE')

@persistent
def ytl_ui_update(scene):
    # Check if active node is tl node or not
    mat = get_active_material()
    node = get_active_node()
    if node and node.type == 'GROUP' and node.node_tree and node.node_tree.tl.is_tl_node:
        # Update node name
        if mat.tl.active_tl_node != node.name:
            mat.tl.active_tl_node = node.name

    # Get active tl node
    group_node =  get_active_texture_layers_node()
    if not group_node: return
    tree = group_node.node_tree
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
                m.index = i
                m.expand_content = mod.expand_content

        if len(tl.textures) > 0:

            # Get texture
            tex = tl.textures[tl.active_texture_index]
            tlui.tex_ui.expand_content = tex.expand_content
            tlui.tex_ui.expand_vector = tex.expand_vector
            tlui.tex_ui.channels.clear()
            
            # Construct texture UI objects
            for i, ch in enumerate(tex.channels):
                c = tlui.tex_ui.channels.add()
                c.expand_bump_settings = ch.expand_bump_settings
                c.expand_content = ch.expand_content
                c.index = i
                for j, mod in enumerate(ch.modifiers):
                    m = c.modifiers.add()
                    m.ch_index = i
                    m.index = j
                    m.expand_content = mod.expand_content

        tlui.halt_prop_update = False

def copy_ui_settings(source, dest):
    for attr in dir(source):
        if attr.startswith(('show_', 'expand_')) or attr.endswith('_name'):
            setattr(dest, attr, getattr(source, attr))

@persistent
def ytl_save_ui_settings(scene):
    wmui = bpy.context.window_manager.tlui
    scui = bpy.context.scene.tlui
    copy_ui_settings(wmui, scui)

@persistent
def ytl_load_ui_settings(scene):
    wmui = bpy.context.window_manager.tlui
    scui = bpy.context.scene.tlui
    copy_ui_settings(scui, wmui)

    # Update texture UI
    wmui.need_update = True

def register():
    bpy.types.Scene.tlui = PointerProperty(type=YTLUI)
    bpy.types.WindowManager.tlui = PointerProperty(type=YTLUI)

    # Add texture layers node ui
    bpy.types.NODE_MT_add.append(add_new_tl_node_menu)

    # Handlers
    bpy.app.handlers.scene_update_pre.append(ytl_ui_update)
    bpy.app.handlers.load_post.append(ytl_load_ui_settings)
    bpy.app.handlers.save_pre.append(ytl_save_ui_settings)

def unregister():
    # Remove add texture layers node ui
    bpy.types.NODE_MT_add.remove(add_new_tl_node_menu)

    # Remove Handlers
    bpy.app.handlers.scene_update_pre.remove(ytl_ui_update)
    bpy.app.handlers.load_post.remove(ytl_load_ui_settings)
    bpy.app.handlers.save_pre.remove(ytl_save_ui_settings)
