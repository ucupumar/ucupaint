import bpy, re
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *
from . import lib

modifier_type_items = (
        ('INVERT', 'Invert', '', 'MODIFIER', 0),
        ('RGB_TO_INTENSITY', 'RGB to Intensity', '', 'MODIFIER', 1),
        ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 2),
        ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 3),
        ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 4),
        ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 5),
        ('MULTIPLIER', 'Multiplier', '', 'MODIFIER', 6),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

can_be_expanded = {
        'INVERT', 
        'COLOR_RAMP',
        'RGB_CURVE',
        'HUE_SATURATION',
        'BRIGHT_CONTRAST',
        'MULTIPLIER',
        }

def reconnect_between_modifier_nodes(parent):

    tl = parent.id_data.tl
    modifiers = parent.modifiers

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]', parent.path_from_id())
    if match1:
        tex = tl.textures[int(match1.group(1))]
        root_ch = tl.channels[int(match1.group(2))]
    elif match2: 
        tex = None
        root_ch = tl.channels[int(match2.group(1))]
    else: return None

    if tex:
        if parent.mod_tree:
            tree = parent.mod_tree
        else: tree = tex.tree
    else: tree = parent.id_data

    nodes = tree.nodes
        
    if tex and parent.mod_tree:
        # start and end inside modifier tree
        parent_start = nodes.get(MODIFIER_TREE_START)
        parent_start_rgb = parent_start.outputs[0]
        parent_start_alpha = parent_start.outputs[1]

        parent_end = nodes.get(MODIFIER_TREE_END)
        parent_end_rgb = parent_end.inputs[0]
        parent_end_alpha = parent_end.inputs[1]

        # Connect outside tree nodes
        mod_group = tex.tree.nodes.get(parent.mod_group)
        start_rgb = tex.tree.nodes.get(parent.start_rgb)
        start_alpha = tex.tree.nodes.get(parent.start_alpha)
        end_rgb = tex.tree.nodes.get(parent.end_rgb)
        end_alpha = tex.tree.nodes.get(parent.end_alpha)

        create_link(tex.tree, start_rgb.outputs[0], mod_group.inputs[0])
        create_link(tex.tree, start_alpha.outputs[0], mod_group.inputs[1])
        create_link(tex.tree, mod_group.outputs[0], end_rgb.inputs[0])
        create_link(tex.tree, mod_group.outputs[1], end_alpha.inputs[0])

    else:
        parent_start_rgb = nodes.get(parent.start_rgb).outputs[0]
        parent_start_alpha = nodes.get(parent.start_alpha).outputs[0]
        parent_end_rgb = nodes.get(parent.end_rgb).inputs[0]
        parent_end_alpha = nodes.get(parent.end_alpha).inputs[0]

    if len(modifiers) == 0:
        create_link(tree, parent_start_rgb, parent_end_rgb)
        create_link(tree, parent_start_alpha, parent_end_alpha)

    for i, m in enumerate(modifiers):
        start_rgb = nodes.get(m.start_rgb)
        end_rgb = nodes.get(m.end_rgb)
        start_alpha = nodes.get(m.start_alpha)
        end_alpha = nodes.get(m.end_alpha)

        # Get previous modifier
        if i == len(modifiers)-1:
            prev_rgb = parent_start_rgb
            prev_alpha = parent_start_alpha
        else:
            prev_m = modifiers[i+1]
            prev_rgb = nodes.get(prev_m.end_rgb)
            prev_alpha = nodes.get(prev_m.end_alpha)
            prev_rgb = prev_rgb.outputs[0]
            prev_alpha = prev_alpha.outputs[0]

        # Connect to previous modifier
        create_link(tree, prev_rgb, start_rgb.inputs[0])
        create_link(tree, prev_alpha, start_alpha.inputs[0])

        if i == 0:
            # Connect to next modifier
            create_link(tree, end_rgb.outputs[0], parent_end_rgb)
            create_link(tree, end_alpha.outputs[0], parent_end_alpha)

def remove_modifier_start_end_nodes(m, tree):

    start_rgb = tree.nodes.get(m.start_rgb)
    start_alpha = tree.nodes.get(m.start_alpha)
    end_rgb = tree.nodes.get(m.end_rgb)
    end_alpha = tree.nodes.get(m.end_alpha)
    frame = tree.nodes.get(m.frame)

    tree.nodes.remove(start_rgb)
    tree.nodes.remove(start_alpha)
    tree.nodes.remove(end_rgb)
    tree.nodes.remove(end_alpha)
    tree.nodes.remove(frame)

def add_modifier_nodes(m, tree, ref_tree=None):

    tl = m.id_data.tl
    nodes = tree.nodes
    links = tree.links

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    if match1:
        root_ch = tl.channels[int(match1.group(2))]
    elif match2: 
        root_ch = tl.channels[int(match2.group(1))]
    else: return None

    # Get non color flag
    non_color = root_ch.colorspace == 'LINEAR'

    # Remove previous start and end if ref tree is passed
    if ref_tree:
        remove_modifier_start_end_nodes(m, ref_tree)

    # Create new pipeline nodes
    start_rgb = nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    m.start_rgb = start_rgb.name

    start_alpha = nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    m.start_alpha = start_alpha.name

    end_rgb = nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    m.end_rgb = end_rgb.name

    end_alpha = nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    m.end_alpha = end_alpha.name

    frame = nodes.new('NodeFrame')
    m.frame = frame.name
    start_rgb.parent = frame
    start_alpha.parent = frame
    end_rgb.parent = frame
    end_alpha.parent = frame

    # Link new nodes
    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])

    # Create the nodes
    if m.type == 'INVERT':

        invert = nodes.new('ShaderNodeGroup')

        if ref_tree:
            invert_ref = ref_tree.nodes.get(m.invert)
            copy_node_props(invert_ref, invert)
            ref_tree.nodes.remove(invert_ref)
        else:
            if m.channel_type == 'VALUE':
                invert.node_tree = lib.get_node_tree_lib(lib.MOD_INVERT_VALUE)
            else: invert.node_tree = lib.get_node_tree_lib(lib.MOD_INVERT)

        m.invert = invert.name

        links.new(start_rgb.outputs[0], invert.inputs[0])
        links.new(invert.outputs[0], end_rgb.inputs[0])

        links.new(start_alpha.outputs[0], invert.inputs[1])
        links.new(invert.outputs[1], end_alpha.inputs[0])

        frame.label = 'Invert'
        invert.parent = frame

    elif m.type == 'RGB_TO_INTENSITY':

        rgb2i = nodes.new('ShaderNodeGroup')

        if ref_tree:
            rgb2i_ref = ref_tree.nodes.get(m.rgb2i)
            copy_node_props(rgb2i_ref, rgb2i)
            ref_tree.nodes.remove(rgb2i_ref)
        else:
            rgb2i.node_tree = lib.get_node_tree_lib(lib.MOD_RGB2INT)
        
        m.rgb2i = rgb2i.name

        links.new(start_rgb.outputs[0], rgb2i.inputs[0])
        links.new(start_alpha.outputs[0], rgb2i.inputs[1])

        links.new(rgb2i.outputs[0], end_rgb.inputs[0])
        links.new(rgb2i.outputs[1], end_alpha.inputs[0])

        if non_color:
            rgb2i.inputs['Linearize'].default_value = 0.0
        else: rgb2i.inputs['Linearize'].default_value = 1.0

        frame.label = 'RGB to Intensity'
        rgb2i.parent = frame

    elif m.type == 'COLOR_RAMP':

        color_ramp_alpha_multiply = nodes.new('ShaderNodeMixRGB')
        color_ramp = nodes.new('ShaderNodeValToRGB')
        color_ramp_mix_alpha = nodes.new('ShaderNodeMixRGB')
        color_ramp_mix_rgb = nodes.new('ShaderNodeMixRGB')

        if ref_tree:
            color_ramp_alpha_multiply_ref = ref_tree.nodes.get(m.color_ramp_alpha_multiply)
            color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
            color_ramp_mix_alpha_ref = ref_tree.nodes.get(m.color_ramp_mix_alpha)
            color_ramp_mix_rgb_ref = ref_tree.nodes.get(m.color_ramp_mix_rgb)

            copy_node_props(color_ramp_alpha_multiply_ref, color_ramp_alpha_multiply)
            copy_node_props(color_ramp_ref, color_ramp)
            copy_node_props(color_ramp_mix_alpha_ref, color_ramp_mix_alpha)
            copy_node_props(color_ramp_mix_rgb_ref, color_ramp_mix_rgb)

            ref_tree.nodes.remove(color_ramp_alpha_multiply_ref)
            ref_tree.nodes.remove(color_ramp_ref)
            ref_tree.nodes.remove(color_ramp_mix_alpha_ref)
            ref_tree.nodes.remove(color_ramp_mix_rgb_ref)
        else:

            color_ramp_alpha_multiply.label = 'ColorRamp Alpha Multiply'
            color_ramp_alpha_multiply.inputs[0].default_value = 1.0
            color_ramp_alpha_multiply.blend_type = 'MULTIPLY'

            color_ramp_mix_alpha.label = 'ColorRamp Alpha Mix'
            color_ramp_mix_alpha.inputs[0].default_value = 1.0

            color_ramp_mix_rgb.label = 'ColorRamp RGB Mix'
            color_ramp_mix_rgb.inputs[0].default_value = 1.0

            # Set default color
            color_ramp.color_ramp.elements[0].color = (0,0,0,0)

        m.color_ramp_alpha_multiply = color_ramp_alpha_multiply.name
        m.color_ramp = color_ramp.name
        m.color_ramp_mix_alpha = color_ramp_mix_alpha.name
        m.color_ramp_mix_rgb = color_ramp_mix_rgb.name

        links.new(start_rgb.outputs[0], color_ramp_alpha_multiply.inputs[1])
        links.new(start_alpha.outputs[0], color_ramp_alpha_multiply.inputs[2])
        links.new(color_ramp_alpha_multiply.outputs[0], color_ramp.inputs[0])
        #links.new(start_rgb.outputs[0], color_ramp.inputs[0])
        #links.new(color_ramp.outputs[0], end_rgb.inputs[0])
        links.new(start_rgb.outputs[0], color_ramp_mix_rgb.inputs[1])
        links.new(color_ramp.outputs[0], color_ramp_mix_rgb.inputs[2])
        links.new(color_ramp_mix_rgb.outputs[0], end_rgb.inputs[0])

        links.new(start_alpha.outputs[0], color_ramp_mix_alpha.inputs[1])
        links.new(color_ramp.outputs[1], color_ramp_mix_alpha.inputs[2])
        links.new(color_ramp_mix_alpha.outputs[0], end_alpha.inputs[0])

        frame.label = 'Color Ramp'
        color_ramp.parent = frame
        color_ramp_alpha_multiply.parent = frame
        color_ramp_mix_alpha.parent = frame
        color_ramp_mix_rgb.parent = frame

    elif m.type == 'RGB_CURVE':

        rgb_curve = nodes.new('ShaderNodeRGBCurve')

        if ref_tree:
            rgb_curve_ref = ref_tree.nodes.get(m.rgb_curve)
            copy_node_props(rgb_curve_ref, rgb_curve)
            ref_tree.nodes.remove(rgb_curve_ref)

        m.rgb_curve = rgb_curve.name

        links.new(start_rgb.outputs[0], rgb_curve.inputs[1])
        links.new(rgb_curve.outputs[0], end_rgb.inputs[0])

        frame.label = 'RGB Curve'
        rgb_curve.parent = frame

    elif m.type == 'HUE_SATURATION':

        huesat = nodes.new('ShaderNodeHueSaturation')

        if ref_tree:
            huesat_ref = ref_tree.nodes.get(m.huesat)
            copy_node_props(huesat_ref, huesat)
            ref_tree.nodes.remove(huesat_ref)

        m.huesat = huesat.name

        links.new(start_rgb.outputs[0], huesat.inputs[4])
        links.new(huesat.outputs[0], end_rgb.inputs[0])

        frame.label = 'Hue Saturation Value'
        huesat.parent = frame

    elif m.type == 'BRIGHT_CONTRAST':

        brightcon = nodes.new('ShaderNodeBrightContrast')

        if ref_tree:
            brightcon_ref = ref_tree.nodes.get(m.brightcon)
            copy_node_props(brightcon_ref, brightcon)
            ref_tree.nodes.remove(brightcon_ref)

        m.brightcon = brightcon.name

        links.new(start_rgb.outputs[0], brightcon.inputs[0])
        links.new(brightcon.outputs[0], end_rgb.inputs[0])

        frame.label = 'Brightness Contrast'
        brightcon.parent = frame

    elif m.type == 'MULTIPLIER':

        multiplier = nodes.new('ShaderNodeGroup')

        if ref_tree:
            multiplier_ref = ref_tree.nodes.get(m.multiplier)
            copy_node_props(multiplier_ref, multiplier)
            ref_tree.nodes.remove(multiplier_ref)
        else:
            if m.channel_type == 'VALUE':
                multiplier.node_tree = lib.get_node_tree_lib(lib.MOD_MULTIPLIER_VALUE)
            else: multiplier.node_tree = lib.get_node_tree_lib(lib.MOD_MULTIPLIER)

        m.multiplier = multiplier.name

        links.new(start_rgb.outputs[0], multiplier.inputs[0])
        links.new(start_alpha.outputs[0], multiplier.inputs[1])
        links.new(multiplier.outputs[0], end_rgb.inputs[0])
        links.new(multiplier.outputs[1], end_alpha.inputs[0])

        frame.label = 'Multiplier'
        multiplier.parent = frame

def add_new_modifier(parent, modifier_type):

    tl = parent.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]', parent.path_from_id())
    if match1: 
        tex = tl.textures[int(match1.group(1))]
        root_ch = tl.channels[int(match1.group(2))]
        if parent.mod_tree:
            tree = parent.mod_tree
        else: tree = tex.tree
    elif match2:
        tex = None
        root_ch = tl.channels[int(match2.group(1))]
        tree = parent.id_data
    else: return None

    modifiers = parent.modifiers

    # Add new modifier and move it to the top
    m = modifiers.add()
    name = [mt[1] for mt in modifier_type_items if mt[0] == modifier_type][0]
    m.name = get_unique_name(name, modifiers)
    modifiers.move(len(modifiers)-1, 0)
    m = modifiers[0]
    m.type = modifier_type
    m.channel_type = root_ch.type

    add_modifier_nodes(m, tree)
    reconnect_between_modifier_nodes(parent)

    return m

def delete_modifier_nodes(nodes, mod):
    # Delete the nodes
    nodes.remove(nodes.get(mod.start_rgb))
    nodes.remove(nodes.get(mod.start_alpha))
    nodes.remove(nodes.get(mod.end_rgb))
    nodes.remove(nodes.get(mod.end_alpha))
    nodes.remove(nodes.get(mod.frame))

    if mod.type == 'RGB_TO_INTENSITY':
        nodes.remove(nodes.get(mod.rgb2i))

    elif mod.type == 'INVERT':
        nodes.remove(nodes.get(mod.invert))

    elif mod.type == 'COLOR_RAMP':
        nodes.remove(nodes.get(mod.color_ramp))
        nodes.remove(nodes.get(mod.color_ramp_alpha_multiply))
        nodes.remove(nodes.get(mod.color_ramp_mix_rgb))
        nodes.remove(nodes.get(mod.color_ramp_mix_alpha))

    elif mod.type == 'RGB_CURVE':
        nodes.remove(nodes.get(mod.rgb_curve))

    elif mod.type == 'HUE_SATURATION':
        nodes.remove(nodes.get(mod.huesat))

    elif mod.type == 'BRIGHT_CONTRAST':
        nodes.remove(nodes.get(mod.brightcon))

    elif mod.type == 'MULTIPLIER':
        nodes.remove(nodes.get(mod.multiplier))

class YNewTexModifier(bpy.types.Operator):
    bl_idname = "node.y_new_texture_modifier"
    bl_label = "New Texture Modifier"
    bl_description = "New Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node() and hasattr(context, 'parent')

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        tex = context.texture if hasattr(context, 'texture') else None

        if tex:
            root_ch = tl.channels[context.parent.channel_index]
            channel_type = root_ch.type
            mod = add_new_modifier(context.parent, self.type)
            mod.texture_index = context.parent.texture_index
            mod.channel_index = context.parent.channel_index
            nodes = tex.tree.nodes
        else:
            channel_type = context.parent.type
            mod = add_new_modifier(context.parent, self.type)
            nodes = group_tree.nodes

        if self.type == 'RGB_TO_INTENSITY' and channel_type == 'RGB':
            rgb2i = nodes.get(mod.rgb2i)
            rgb2i.inputs[2].default_value = (1,0,1,1)

        # If RGB to intensity is added, bump base is better be 0.0
        if tex and self.type == 'RGB_TO_INTENSITY':
            for i, ch in enumerate(tl.channels):
                c = context.texture.channels[i]
                if ch.type == 'NORMAL':
                    c.bump_base_value = 0.0

        # Expand channel content to see added modifier
        if hasattr(context, 'channel_ui'):
            context.channel_ui.expand_content = True

        # Rearrange nodes
        if tex:
            rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YMoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_move_texture_modifier"
    bl_label = "Move Texture Modifier"
    bl_description = "Move Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return (get_active_texture_layers_node() and 
                hasattr(context, 'parent') and hasattr(context, 'modifier'))

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        parent = context.parent

        num_mods = len(parent.modifiers)
        if num_mods < 2: return {'CANCELLED'}

        mod = context.modifier
        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_mods-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        tex = context.texture if hasattr(context, 'texture') else None

        if tex: tree = tex.tree
        else: tree = group_tree

        # Swap modifier
        parent.modifiers.move(index, new_index)

        # Reconnect modifier nodes
        reconnect_between_modifier_nodes(parent)

        # Rearrange nodes
        if tex: rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YRemoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_modifier"
    bl_label = "Remove Texture Modifier"
    bl_description = "Remove Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    parent_type = EnumProperty(
            name = 'Modifier Parent',
            items = (('CHANNEL', 'Channel', '' ),
                     ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
                    ),
            default = 'TEXTURE_CHANNEL')

    channel_index = IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and hasattr(context, 'modifier')

    def execute(self, context):
        group_tree = context.parent.id_data
        tl = group_tree.tl

        parent = context.parent
        mod = context.modifier

        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        if len(parent.modifiers) < 1: return {'CANCELLED'}

        tex = context.texture if hasattr(context, 'texture') else None

        if tex:
            if parent.mod_tree:
                tree = parent.mod_tree
            else: tree = tex.tree
        else: tree = group_tree

        # Delete the nodes
        delete_modifier_nodes(tree.nodes, mod)

        # Delete the modifier
        parent.modifiers.remove(index)

        # Reconnect nodes
        reconnect_between_modifier_nodes(parent)

        # Rearrange nodes
        if tex:
            rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

def draw_modifier_properties(context, channel, nodes, modifier, layout):

    #if modifier.type not in {'INVERT'}:
    #    label = [mt[1] for mt in modifier_type_items if modifier.type == mt[0]][0]
    #    layout.label(label + ' Properties:')

    if modifier.type == 'INVERT':
        row = layout.row(align=True)
        invert = nodes.get(modifier.invert)
        if modifier.channel_type == 'VALUE':
            row.prop(modifier, 'invert_r_enable', text='Value', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='Alpha', toggle=True)
        else:
            row.prop(modifier, 'invert_r_enable', text='R', toggle=True)
            row.prop(modifier, 'invert_g_enable', text='G', toggle=True)
            row.prop(modifier, 'invert_b_enable', text='B', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='A', toggle=True)

    #elif modifier.type == 'RGB_TO_INTENSITY':

    #    # Shortcut only available on texture layer channel
    #    if 'YLayerChannel' in str(type(channel)):
    #        row = layout.row(align=True)
    #        row.label('Color Shortcut:')
    #        row.prop(modifier, 'shortcut', text='')

    elif modifier.type == 'COLOR_RAMP':
        color_ramp = nodes.get(modifier.color_ramp)
        layout.template_color_ramp(color_ramp, "color_ramp", expand=True)

    elif modifier.type == 'RGB_CURVE':
        rgb_curve = nodes.get(modifier.rgb_curve)
        rgb_curve.draw_buttons_ext(context, layout)

    elif modifier.type == 'HUE_SATURATION':
        huesat = nodes.get(modifier.huesat)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label('Hue:')
        col.label('Saturation:')
        col.label('Value:')

        col = row.column(align=True)
        for i in range(3):
            col.prop(huesat.inputs[i], 'default_value', text='')

    elif modifier.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(modifier.brightcon)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label('Brightness:')
        col.label('Contrast:')

        col = row.column(align=True)
        col.prop(brightcon.inputs[1], 'default_value', text='')
        col.prop(brightcon.inputs[2], 'default_value', text='')

    elif modifier.type == 'MULTIPLIER':
        multiplier = nodes.get(modifier.multiplier)
        #row = layout.row(align=True)
        #col = row.column(align=True)
        #col.label('Brightness:')
        #col.label('Contrast:')

        col = layout.column(align=True)
        row = col.row()
        row.label('Clamp:')
        row.prop(modifier, 'use_clamp', text='')
        if modifier.channel_type == 'VALUE':
            col.prop(multiplier.inputs[3], 'default_value', text='Value')
            col.prop(multiplier.inputs[4], 'default_value', text='Alpha')
        else:
            col.prop(multiplier.inputs[3], 'default_value', text='R')
            col.prop(multiplier.inputs[4], 'default_value', text='G')
            col.prop(multiplier.inputs[5], 'default_value', text='B')
            #col = layout.column(align=True)
            col.separator()
            col.prop(multiplier.inputs[6], 'default_value', text='Alpha')

class NODE_UL_y_texture_modifiers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        #nodes = context.group_node.node_tree.nodes
        group_node = get_active_texture_layers_node()
        nodes = group_node.node_tree.nodes

        row = layout.row(align=True)

        row.label(item.name, icon='MODIFIER')

        if item.type == 'RGB_TO_INTENSITY':
            row.prop(rgb2i.inputs[2], 'default_value', text='', icon='COLOR')

        row.prop(item, 'enable', text='')

class YTexModifierSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_modifier_specials"
    bl_label = "Texture Channel Modifiers"
    bl_description = 'Add New Modifier'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_texture_layers_node()

    def draw(self, context):
        self.layout.label('Add Modifier')
        ## List the items
        for mt in modifier_type_items:
            self.layout.operator('node.y_new_texture_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

def update_modifier_enable(self, context):
    group_tree = self.id_data
    tl = group_tree.tl

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        tex = tl.textures[int(match1.group(1))]
        ch = tex.channels[int(match1.group(2))]
        if ch.mod_tree: nodes = ch.mod_tree.nodes
        else: nodes = tex.tree.nodes
    elif match2: 
        nodes = group_tree.nodes
    else: return None

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i = nodes.get(self.rgb2i)
        rgb2i.mute = not self.enable

    elif self.type == 'INVERT':
        invert = nodes.get(self.invert)
        invert.mute = not self.enable

    elif self.type == 'COLOR_RAMP':
        color_ramp = nodes.get(self.color_ramp)
        color_ramp.mute = not self.enable
        color_ramp_alpha_multiply = nodes.get(self.color_ramp_alpha_multiply)
        color_ramp_alpha_multiply.mute = not self.enable
        color_ramp_mix_rgb = nodes.get(self.color_ramp_mix_rgb)
        color_ramp_mix_rgb.mute = not self.enable
        color_ramp_mix_alpha = nodes.get(self.color_ramp_mix_alpha)
        color_ramp_mix_alpha.mute = not self.enable

    elif self.type == 'RGB_CURVE':
        rgb_curve = nodes.get(self.rgb_curve)
        rgb_curve.mute = not self.enable

    elif self.type == 'HUE_SATURATION':
        huesat = nodes.get(self.huesat)
        huesat.mute = not self.enable

    elif self.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(self.brightcon)
        brightcon.mute = not self.enable

    elif self.type == 'MULTIPLIER':
        multiplier = nodes.get(self.multiplier)
        multiplier.mute = not self.enable

def update_modifier_shortcut(self, context):
    group_tree = self.id_data
    tl = group_tree.tl

    if self.shortcut:
        mod_found = False
        # Check if modifier on group channel
        channel = tl.channels[tl.active_channel_index]
        for mod in channel.modifiers:
            if mod == self:
                mod_found = True
                break

        if mod_found:
            # Disable other shortcuts
            for mod in channel.modifiers:
                if mod != self: mod.shortcut = False
            return

        # Check texture channels
        tex = tl.textures[tl.active_texture_index]
        for ch in tex.channels:
            for mod in ch.modifiers:
                if mod != self:
                    mod.shortcut = False

def update_invert_channel(self, context):
    group_tree = self.id_data
    tl = group_tree.tl

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        tex = tl.textures[int(match1.group(1))]
        ch = tex.channels[int(match1.group(2))]
        if ch.mod_tree: nodes = ch.mod_tree.nodes
        else: nodes = tex.tree.nodes
    elif match2: 
        nodes = group_tree.nodes
    else: return None

    invert = nodes.get(self.invert)

    if self.invert_r_enable:
        invert.inputs[2].default_value = 1.0
    else: invert.inputs[2].default_value = 0.0

    if self.channel_type == 'VALUE':

        if self.invert_a_enable:
            invert.inputs[3].default_value = 1.0
        else: invert.inputs[3].default_value = 0.0

    else:

        if self.invert_g_enable:
            invert.inputs[3].default_value = 1.0
        else: invert.inputs[3].default_value = 0.0

        if self.invert_b_enable:
            invert.inputs[4].default_value = 1.0
        else: invert.inputs[4].default_value = 0.0

        if self.invert_a_enable:
            invert.inputs[5].default_value = 1.0
        else: invert.inputs[5].default_value = 0.0

def update_use_clamp(self, context):
    group_tree = self.id_data
    tl = group_tree.tl

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1:
        tex = tl.textures[int(match1.group(1))]
        ch = tex.channels[int(match1.group(2))]
        if ch.mod_tree: nodes = ch.mod_tree.nodes
        else: nodes = tex.tree.nodes
    elif match2: 
        nodes = group_tree.nodes
    else: return None

    if self.type == 'MULTIPLIER':
        multiplier = nodes.get(self.multiplier)
        multiplier.inputs[2].default_value = 1.0 if self.use_clamp else 0.0

class YTextureModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_modifier_enable)
    name = StringProperty(default='')

    channel_type = StringProperty(default='')
    texture_index = IntProperty(default=-1)
    channel_index = IntProperty(default=-1)

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    # Base nodes
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # RGB to Intensity nodes
    rgb2i = StringProperty(default='')

    # Invert nodes
    invert = StringProperty(default='')

    # Invert toggles
    invert_r_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_g_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_b_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_a_enable = BoolProperty(default=False, update=update_invert_channel)

    # Mask nodes
    #mask_texture = StringProperty(default='')

    # Color Ramp nodes
    color_ramp = StringProperty(default='')
    color_ramp_alpha_multiply = StringProperty(default='')
    color_ramp_mix_rgb = StringProperty(default='')
    color_ramp_mix_alpha = StringProperty(default='')

    # RGB Curve nodes
    rgb_curve = StringProperty(default='')

    # Brightness Contrast nodes
    brightcon = StringProperty(default='')

    # Hue Saturation nodes
    huesat = StringProperty(default='')

    # Multiplier nodes
    multiplier = StringProperty(default='')

    # Individual modifier node frame
    frame = StringProperty(default='')

    # Clamp prop is available in some modifiers
    use_clamp = BoolProperty(name='Use Clamp', default=False, update=update_use_clamp)

    shortcut = BoolProperty(
            name = 'Property Shortcut',
            description = 'Property shortcut on texture list (currently only available on RGB to Intensity)',
            default=False,
            update=update_modifier_shortcut)

    expand_content = BoolProperty(default=True)

def enable_modifiers_tree(ch):
    
    group_tree = ch.id_data
    tl = group_tree.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    if not m: return
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]

    # Check if modifier tree already available
    if ch.mod_tree: return

    mod_tree = bpy.data.node_groups.new('~TL Modifiers ' + root_ch.name + ' ' + tex.name, 'ShaderNodeTree')
    ch.mod_tree = mod_tree

    mod_tree.inputs.new('NodeSocketColor', 'RGB')
    mod_tree.inputs.new('NodeSocketFloat', 'Alpha')
    mod_tree.outputs.new('NodeSocketColor', 'RGB')
    mod_tree.outputs.new('NodeSocketFloat', 'Alpha')

    # New inputs and outputs
    mod_tree_start = mod_tree.nodes.new('NodeGroupInput')
    mod_tree_start.name = MODIFIER_TREE_START
    mod_tree_end = mod_tree.nodes.new('NodeGroupOutput')
    mod_tree_end.name = MODIFIER_TREE_END

    mod_group = tex.tree.nodes.new('ShaderNodeGroup')
    mod_group.node_tree = mod_tree
    ch.mod_group = mod_group.name

    for mod in ch.modifiers:
        add_modifier_nodes(mod, mod_tree, tex.tree)

    reconnect_between_modifier_nodes(ch)
    rearrange_tex_nodes(tex)

def disable_modifiers_tree(ch):
    group_tree = ch.id_data
    tl = group_tree.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    if not m: return
    tex = tl.textures[int(m.group(1))]

    # Check if modifier tree already gone
    if not ch.mod_tree: return

    # Check if texture channels has fine bump
    #fine_bump_found = False
    #for i, ch in enumerate(tex.channels):
    #    if tl.channels[i].type == 'NORMAL' and ch.normal_map_type == 'FINE_BUMP_MAP':
    #        fine_bump_found = True

    #if fine_bump_found: return

    for mod in ch.modifiers:
        add_modifier_nodes(mod, tex.tree, ch.mod_tree)

    # Remove modifier tree
    mod_group = tex.tree.nodes.get(ch.mod_group)
    tex.tree.nodes.remove(mod_group)
    bpy.data.node_groups.remove(ch.mod_tree)
    ch.mod_tree = None
    ch.mod_group = ''

    reconnect_between_modifier_nodes(ch)
    rearrange_tex_nodes(tex)

#def update_mod_tree(self, context):
#    group_tree = self.id_data
#
#    if self.is_mod_tree:
#        enable_modifiers_tree(self)
#    else:
#        disable_modifiers_tree(self)
#    #print('Neve sei neve')
