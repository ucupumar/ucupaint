import bpy
from bpy.props import *
from .common import *
from .node_arrangements import *

modifier_type_items = (
        ('INVERT', 'Invert', '', 'MODIFIER', 0),
        ('RGB_TO_INTENSITY', 'RGB to Intensity', '', 'MODIFIER', 1),
        ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 2),
        ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 3),
        ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 4),
        ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 5),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

can_be_expanded = {
        'INVERT', 
        'COLOR_RAMP',
        'RGB_CURVE',
        'HUE_SATURATION',
        'BRIGHT_CONTRAST',
        }

def add_new_modifier(group_tree, parent, modifier_type):
    nodes = group_tree.nodes
    links = group_tree.links

    # Get start and end node
    parent_start_rgb = nodes.get(parent.start_rgb)
    parent_start_alpha = nodes.get(parent.start_alpha)
    parent_end_rgb = nodes.get(parent.end_rgb)
    parent_end_alpha = nodes.get(parent.end_alpha)
    parent_frame = nodes.get(parent.modifier_frame)

    # Get modifier list and its index
    modifiers = parent.modifiers
    #index = parent.active_modifier_index

    # Add new modifier and move it to the top
    m = modifiers.add()
    name = [mt[1] for mt in modifier_type_items if mt[0] == modifier_type][0]
    m.name = get_unique_name(name, modifiers)
    modifiers.move(len(modifiers)-1, 0)
    m = modifiers[0]
    m.type = modifier_type
    index = 0

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
    frame.parent = parent_frame
    start_rgb.parent = frame
    start_alpha.parent = frame
    end_rgb.parent = frame
    end_alpha.parent = frame

    # Link new nodes
    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])

    # Create the nodes
    if m.type == 'INVERT':
        invert_separate = nodes.new('ShaderNodeSeparateRGB')
        invert_separate.parent = frame
        m.invert_separate = invert_separate.name

        invert_r = nodes.new('ShaderNodeMath')
        invert_r.inputs[0].default_value = 1.0
        invert_r.operation = 'SUBTRACT'
        invert_r.mute = not m.invert_r_enable
        invert_r.parent = frame
        m.invert_r = invert_r.name

        invert_g = nodes.new('ShaderNodeMath')
        invert_g.inputs[0].default_value = 1.0
        invert_g.operation = 'SUBTRACT'
        invert_g.mute = not m.invert_g_enable
        invert_g.parent = frame
        m.invert_g = invert_g.name

        invert_b = nodes.new('ShaderNodeMath')
        invert_b.inputs[0].default_value = 1.0
        invert_b.operation = 'SUBTRACT'
        invert_b.mute = not m.invert_b_enable
        invert_b.parent = frame
        m.invert_b = invert_b.name

        invert_a = nodes.new('ShaderNodeMath')
        invert_a.inputs[0].default_value = 1.0
        invert_a.operation = 'SUBTRACT'
        invert_a.mute = not m.invert_a_enable
        invert_a.parent = frame
        m.invert_a = invert_a.name

        invert_combine = nodes.new('ShaderNodeCombineRGB')
        invert_combine.parent = frame
        m.invert_combine = invert_combine.name

        invert_mix_rgb = nodes.new('ShaderNodeMixRGB')
        invert_mix_rgb.inputs[0].default_value = 1.0
        invert_mix_rgb.parent = frame
        m.invert_mix_rgb = invert_mix_rgb.name

        links.new(start_rgb.outputs[0], invert_separate.inputs[0])
        links.new(start_rgb.outputs[0], invert_mix_rgb.inputs[1])
        links.new(start_alpha.outputs[0], invert_a.inputs[1])
        links.new(invert_separate.outputs[0], invert_r.inputs[1])
        links.new(invert_separate.outputs[1], invert_g.inputs[1])
        links.new(invert_separate.outputs[2], invert_b.inputs[1])
        links.new(invert_r.outputs[0], invert_combine.inputs[0])
        links.new(invert_g.outputs[0], invert_combine.inputs[1])
        links.new(invert_b.outputs[0], invert_combine.inputs[2])
        links.new(invert_combine.outputs[0], invert_mix_rgb.inputs[2])
        links.new(invert_mix_rgb.outputs[0], end_rgb.inputs[0])
        links.new(invert_a.outputs[0], end_alpha.inputs[0])

        #invert = nodes.new('ShaderNodeInvert')
        #m.invert = invert.name

        #links.new(start_rgb.outputs[0], invert.inputs[1])
        #links.new(invert.outputs[0], end_rgb.inputs[0])

        frame.label = 'Invert'
        #invert.parent = frame

    elif m.type == 'RGB_TO_INTENSITY':

        rgb2i_color = nodes.new('ShaderNodeRGB')
        rgb2i_color.outputs[0].default_value = (1,1,1,1)
        m.rgb2i_color = rgb2i_color.name

        rgb2i_linear = nodes.new('ShaderNodeGamma')
        rgb2i_linear.label = 'Linear'
        rgb2i_linear.inputs[1].default_value = 1.0/GAMMA
        m.rgb2i_linear = rgb2i_linear.name

        rgb2i_mix_rgb = nodes.new('ShaderNodeMixRGB')
        rgb2i_mix_rgb.label = 'Mix RGB'
        rgb2i_mix_rgb.inputs[0].default_value = 1.0
        m.rgb2i_mix_rgb = rgb2i_mix_rgb.name

        rgb2i_mix_alpha = nodes.new('ShaderNodeMixRGB')
        rgb2i_mix_alpha.label = 'Mix Alpha'
        rgb2i_mix_alpha.blend_type = 'MULTIPLY'
        rgb2i_mix_alpha.inputs[0].default_value = 1.0
        m.rgb2i_mix_alpha = rgb2i_mix_alpha.name

        links.new(rgb2i_color.outputs[0], rgb2i_linear.inputs[0])
        links.new(rgb2i_linear.outputs[0], rgb2i_mix_rgb.inputs[2])
        links.new(start_rgb.outputs[0], rgb2i_mix_rgb.inputs[1])
        links.new(rgb2i_mix_rgb.outputs[0], end_rgb.inputs[0])

        links.new(start_rgb.outputs[0], rgb2i_mix_alpha.inputs[2])
        links.new(start_alpha.outputs[0], rgb2i_mix_alpha.inputs[1])
        links.new(rgb2i_mix_alpha.outputs[0], end_alpha.inputs[0])

        frame.label = 'RGB to Intensity'
        rgb2i_color.parent = frame

    elif m.type == 'COLOR_RAMP':

        color_ramp_alpha_multiply = nodes.new('ShaderNodeMixRGB')
        color_ramp_alpha_multiply.name = 'ColorRamp Alpha Multiply'
        color_ramp_alpha_multiply.inputs[0].default_value = 1.0
        color_ramp_alpha_multiply.blend_type = 'MULTIPLY'
        m.color_ramp_alpha_multiply = color_ramp_alpha_multiply.name

        color_ramp = nodes.new('ShaderNodeValToRGB')
        m.color_ramp = color_ramp.name

        color_ramp_alpha_mix = nodes.new('ShaderNodeMixRGB')
        color_ramp_alpha_mix.name = 'ColorRamp Alpha Mix'
        color_ramp_alpha_mix.inputs[0].default_value = 1.0
        m.color_ramp_alpha_mix = color_ramp_alpha_mix.name

        # Set default color
        color_ramp.color_ramp.elements[0].color = (0,0,0,0)

        links.new(start_rgb.outputs[0], color_ramp_alpha_multiply.inputs[1])
        links.new(start_alpha.outputs[0], color_ramp_alpha_multiply.inputs[2])
        links.new(color_ramp_alpha_multiply.outputs[0], color_ramp.inputs[0])
        #links.new(start_rgb.outputs[0], color_ramp.inputs[0])
        links.new(color_ramp.outputs[0], end_rgb.inputs[0])

        links.new(start_alpha.outputs[0], color_ramp_alpha_mix.inputs[1])
        links.new(color_ramp.outputs[1], color_ramp_alpha_mix.inputs[2])
        links.new(color_ramp_alpha_mix.outputs[0], end_alpha.inputs[0])

        frame.label = 'Color Ramp'
        color_ramp.parent = frame

    elif m.type == 'RGB_CURVE':

        rgb_curve = nodes.new('ShaderNodeRGBCurve')
        m.rgb_curve = rgb_curve.name

        links.new(start_rgb.outputs[0], rgb_curve.inputs[1])
        links.new(rgb_curve.outputs[0], end_rgb.inputs[0])

        frame.label = 'RGB Curve'
        rgb_curve.parent = frame

    elif m.type == 'HUE_SATURATION':

        huesat = nodes.new('ShaderNodeHueSaturation')
        m.huesat = huesat.name

        links.new(start_rgb.outputs[0], huesat.inputs[4])
        links.new(huesat.outputs[0], end_rgb.inputs[0])

        frame.label = 'RGB Curve'
        huesat.parent = frame

    elif m.type == 'BRIGHT_CONTRAST':

        brightcon = nodes.new('ShaderNodeBrightContrast')
        m.brightcon = brightcon.name

        links.new(start_rgb.outputs[0], brightcon.inputs[0])
        links.new(brightcon.outputs[0], end_rgb.inputs[0])

        frame.label = 'Brightness Contrast'
        brightcon.parent = frame

    # Get previous modifier
    if len(modifiers) > 1 :
        prev_m = modifiers[1]
        prev_rgb = nodes.get(prev_m.end_rgb)
        prev_alpha = nodes.get(prev_m.end_alpha)
    else:
        prev_rgb = nodes.get(parent.start_rgb)
        prev_alpha = nodes.get(parent.start_alpha)

    # Connect to previous modifier
    links.new(prev_rgb.outputs[0], start_rgb.inputs[0])
    links.new(prev_alpha.outputs[0], start_alpha.inputs[0])

    # Connect to next modifier
    links.new(end_rgb.outputs[0], parent_end_rgb.inputs[0])
    links.new(end_alpha.outputs[0], parent_end_alpha.inputs[0])

    return m

def delete_modifier_nodes(nodes, mod):
    # Delete the nodes
    nodes.remove(nodes.get(mod.start_rgb))
    nodes.remove(nodes.get(mod.start_alpha))
    nodes.remove(nodes.get(mod.end_rgb))
    nodes.remove(nodes.get(mod.end_alpha))
    nodes.remove(nodes.get(mod.frame))

    if mod.type == 'RGB_TO_INTENSITY':
        nodes.remove(nodes.get(mod.rgb2i_color))
        nodes.remove(nodes.get(mod.rgb2i_linear))
        nodes.remove(nodes.get(mod.rgb2i_mix_rgb))
        nodes.remove(nodes.get(mod.rgb2i_mix_alpha))

    elif mod.type == 'INVERT':
        nodes.remove(nodes.get(mod.invert_separate))
        nodes.remove(nodes.get(mod.invert_r))
        nodes.remove(nodes.get(mod.invert_g))
        nodes.remove(nodes.get(mod.invert_b))
        nodes.remove(nodes.get(mod.invert_a))
        nodes.remove(nodes.get(mod.invert_combine))
        nodes.remove(nodes.get(mod.invert_mix_rgb))

    elif mod.type == 'COLOR_RAMP':
        nodes.remove(nodes.get(mod.color_ramp))
        nodes.remove(nodes.get(mod.color_ramp_alpha_multiply))
        nodes.remove(nodes.get(mod.color_ramp_alpha_mix))

    elif mod.type == 'RGB_CURVE':
        nodes.remove(nodes.get(mod.rgb_curve))

    elif mod.type == 'HUE_SATURATION':
        nodes.remove(nodes.get(mod.huesat))

    elif mod.type == 'BRIGHT_CONTRAST':
        nodes.remove(nodes.get(mod.brightcon))

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
        return get_active_texture_group_node() and hasattr(context, 'parent')

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        #if len(tl.channels) == 0: return {'CANCELLED'}

        #if self.parent_type == 'CHANNEL':
        #    parent = tl.channels[tl.active_channel_index]
        #elif self.parent_type == 'TEXTURE_CHANNEL':
        #    if len(tl.textures) == 0: return {'CANCELLED'}
        #    tex = tl.textures[tl.active_texture_index]
        #    parent = tex.channels[self.channel_index]
        #else: return

        add_new_modifier(group_tree, context.parent, self.type)

        # If RGB to intensity is added, bump base is better be 0.0
        #if self.parent_type == 'TEXTURE_CHANNEL' and self.type == 'RGB_TO_INTENSITY':
        if self.type == 'RGB_TO_INTENSITY' and hasattr(context, 'texture'):
            for i, ch in enumerate(tl.channels):
                c = context.texture.channels[i]
                if ch.type == 'NORMAL':
                    c.bump_base_value = 0.0

        # Expand channel content to see added modifier
        if hasattr(context, 'channel_ui'):
            context.channel_ui.expand_content = True

        rearrange_nodes(group_tree)

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
        return (get_active_texture_group_node() and 
                hasattr(context, 'parent') and hasattr(context, 'modifier'))

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        #tl = group_tree.tl

        #if len(tl.channels) == 0: return {'CANCELLED'}

        #if self.parent_type == 'CHANNEL':
        #    parent = tl.channels[tl.active_channel_index]
        #elif self.parent_type == 'TEXTURE_CHANNEL':
        #    if len(tl.textures) == 0: return {'CANCELLED'}
        #    tex = tl.textures[tl.active_texture_index]
        #    parent = tex.channels[self.channel_index]
        #else: return

        parent = context.parent

        num_mods = len(parent.modifiers)
        if num_mods < 2: return {'CANCELLED'}

        #index = parent.active_modifier_index
        #mod = parent.modifiers[index]

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

        swap_mod = parent.modifiers[new_index]

        start_rgb = nodes.get(mod.start_rgb)
        start_alpha = nodes.get(mod.start_alpha)
        end_rgb = nodes.get(mod.end_rgb)
        end_alpha = nodes.get(mod.end_alpha)

        swap_start_rgb = nodes.get(swap_mod.start_rgb)
        swap_start_alpha = nodes.get(swap_mod.start_alpha)
        swap_end_rgb = nodes.get(swap_mod.end_rgb)
        swap_end_alpha = nodes.get(swap_mod.end_alpha)

        if self.direction == 'UP':
            links.new(end_rgb.outputs[0], swap_end_rgb.outputs[0].links[0].to_socket)
            links.new(end_alpha.outputs[0], swap_end_alpha.outputs[0].links[0].to_socket)

            links.new(start_rgb.inputs[0].links[0].from_socket, swap_start_rgb.inputs[0])
            links.new(start_alpha.inputs[0].links[0].from_socket, swap_start_alpha.inputs[0])

            links.new(swap_end_rgb.outputs[0], start_rgb.inputs[0])
            links.new(swap_end_alpha.outputs[0], start_alpha.inputs[0])

        else:
            links.new(swap_end_rgb.outputs[0], end_rgb.outputs[0].links[0].to_socket)
            links.new(swap_end_alpha.outputs[0], end_alpha.outputs[0].links[0].to_socket)

            links.new(swap_start_rgb.inputs[0].links[0].from_socket, start_rgb.inputs[0])
            links.new(swap_start_alpha.inputs[0].links[0].from_socket, start_alpha.inputs[0])

            links.new(end_rgb.outputs[0], swap_start_rgb.inputs[0])
            links.new(end_alpha.outputs[0], swap_start_alpha.inputs[0])

        # Swap modifier
        parent.modifiers.move(index, new_index)
        parent.active_modifier_index = new_index

        # Rearrange nodes
        rearrange_nodes(group_tree)

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
        return (get_active_texture_group_node() and 
                hasattr(context, 'parent') and hasattr(context, 'modifier'))

    def execute(self, context):
        #print(context.modifier.name)
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        links = group_tree.links
        #tl = group_tree.tl

        #if len(tl.channels) == 0: return {'CANCELLED'}

        #if self.parent_type == 'CHANNEL':
        #    parent = tl.channels[tl.active_channel_index]
        #elif self.parent_type == 'TEXTURE_CHANNEL':
        #    if len(tl.textures) == 0: return {'CANCELLED'}
        #    tex = tl.textures[tl.active_texture_index]
        #    parent = tex.channels[self.channel_index]
        #else: return

        parent = context.parent
        mod = context.modifier

        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        if len(parent.modifiers) < 1: return {'CANCELLED'}

        #index = parent.active_modifier_index
        #mod = parent.modifiers[index]

        prev_rgb = nodes.get(mod.start_rgb).inputs[0].links[0].from_socket
        next_rgb = nodes.get(mod.end_rgb).outputs[0].links[0].to_socket
        links.new(prev_rgb, next_rgb)

        prev_alpha = nodes.get(mod.start_alpha).inputs[0].links[0].from_socket
        next_alpha = nodes.get(mod.end_alpha).outputs[0].links[0].to_socket
        links.new(prev_alpha, next_alpha)

        # Delete the nodes
        delete_modifier_nodes(nodes, mod)

        # Delete the modifier
        parent.modifiers.remove(index)
        rearrange_nodes(group_tree)

        # Set new active index
        #if (parent.active_modifier_index == len(parent.modifiers) and
        #    parent.active_modifier_index > 0
        #    ): parent.active_modifier_index -= 1

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

def draw_modifier_properties(context, channel, nodes, modifier, layout):

    #if modifier.type not in {'INVERT'}:
    #    label = [mt[1] for mt in modifier_type_items if modifier.type == mt[0]][0]
    #    layout.label(label + ' Properties:')

    if modifier.type == 'INVERT':
        row = layout.row(align=True)
        row.prop(modifier, 'invert_r_enable', text='R', toggle=True)
        row.prop(modifier, 'invert_g_enable', text='G', toggle=True)
        row.prop(modifier, 'invert_b_enable', text='B', toggle=True)
        row.prop(modifier, 'invert_a_enable', text='A', toggle=True)

    #elif modifier.type == 'RGB_TO_INTENSITY':
    #    rgb2i_color = nodes.get(modifier.rgb2i_color)
    #    row = layout.row(align=True)
    #    row.label('Color:')
    #    row.prop(rgb2i_color.outputs[0], 'default_value', text='')

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

class NODE_UL_y_texture_modifiers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        #nodes = context.group_node.node_tree.nodes
        group_node = get_active_texture_group_node()
        nodes = group_node.node_tree.nodes

        row = layout.row(align=True)

        row.label(item.name, icon='MODIFIER')

        if item.type == 'RGB_TO_INTENSITY':
            rgb2i_color = nodes.get(item.rgb2i_color)
            row.prop(rgb2i_color.outputs[0], 'default_value', text='', icon='COLOR')

        row.prop(item, 'enable', text='')

class YTexModifierSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_modifier_specials"
    bl_label = "Texture Channel Modifiers"
    bl_description = 'Add New Modifier'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_texture_group_node()

    def draw(self, context):
        #node = get_active_texture_group_node()
        #tl = node.node_tree.tl

        #if 'YLayerChannel' in str(type(context.channel)):
        #    tex = tl.textures[tl.active_texture_index]
        #    parent_type = 'TEXTURE_CHANNEL'
        #    #self.layout.prop(tex, 'name')

        #    # Get index number by channel from context
        #    index = [i for i, ch in enumerate(tex.channels) if ch == context.channel]
        #    if index: index = index[0]
        #    else: return
        #elif 'YGroupChannel' in str(type(context.channel)):
        #    parent_type = 'CHANNEL'
        #    index = 0
        #else: return

        ## List the items
        for mt in modifier_type_items:
            self.layout.operator('node.y_new_texture_modifier', text=mt[1], icon='MODIFIER').type = mt[0]
        #    op.type = mt[0]
        #    op.parent_type = parent_type
        #    op.channel_index = index

def update_modifier_enable(self, context):
    group_node = get_active_texture_group_node()
    nodes = group_node.node_tree.nodes
    #tl = group_node.node_tree.tl

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i_color = nodes.get(self.rgb2i_color)
        rgb2i_linear = nodes.get(self.rgb2i_linear)
        rgb2i_mix_rgb = nodes.get(self.rgb2i_mix_rgb)
        rgb2i_mix_alpha = nodes.get(self.rgb2i_mix_alpha)
        rgb2i_color.mute = not self.enable
        rgb2i_linear.mute = not self.enable
        rgb2i_mix_rgb.mute = not self.enable
        rgb2i_mix_alpha.mute = not self.enable

    elif self.type == 'INVERT':
        invert_mix_rgb = nodes.get(self.invert_mix_rgb)
        invert_mix_rgb.mute = not self.enable
        invert_a = nodes.get(self.invert_a)
        invert_a.mute = not self.enable or not self.invert_a_enable

    elif self.type == 'COLOR_RAMP':
        color_ramp = nodes.get(self.color_ramp)
        color_ramp.mute = not self.enable
        color_ramp_alpha_multiply = nodes.get(self.color_ramp_alpha_multiply)
        color_ramp_alpha_multiply.mute = not self.enable
        color_ramp_alpha_mix = nodes.get(self.color_ramp_alpha_mix)
        color_ramp_alpha_mix.mute = not self.enable

    elif self.type == 'RGB_CURVE':
        rgb_curve = nodes.get(self.rgb_curve)
        rgb_curve.mute = not self.enable

    elif self.type == 'HUE_SATURATION':
        huesat = nodes.get(self.huesat)
        huesat.mute = not self.enable

    elif self.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(self.brightcon)
        brightcon.mute = not self.enable

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
    nodes = group_tree.nodes

    invert_r = nodes.get(self.invert_r)
    invert_r.mute = not self.invert_r_enable

    invert_g = nodes.get(self.invert_g)
    invert_g.mute = not self.invert_g_enable

    invert_b = nodes.get(self.invert_b)
    invert_b.mute = not self.invert_b_enable

    invert_a = nodes.get(self.invert_a)
    invert_a.mute = not self.invert_a_enable or not self.enable

class YTextureModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_modifier_enable)
    name = StringProperty(default='')

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
    rgb2i_color = StringProperty(default='')
    rgb2i_linear = StringProperty(default='')
    rgb2i_mix_rgb = StringProperty(default='')
    rgb2i_mix_alpha = StringProperty(default='')

    # Invert nodes
    invert = StringProperty(default='')
    invert_separate = StringProperty(default='')
    invert_r = StringProperty(default='')
    invert_g = StringProperty(default='')
    invert_b = StringProperty(default='')
    invert_a = StringProperty(default='')
    invert_combine = StringProperty(default='')
    invert_mix_rgb = StringProperty(default='')

    # Invert toggles
    invert_r_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_g_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_b_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_a_enable = BoolProperty(default=False, update=update_invert_channel)

    # Mask nodes
    mask_texture = StringProperty(default='')

    # Color Ramp nodes
    color_ramp = StringProperty(default='')
    color_ramp_alpha_multiply = StringProperty(default='')
    color_ramp_alpha_mix = StringProperty(default='')

    # Grayscale to Normal nodes
    gray_to_normal = StringProperty(default='')

    # RGB Curve nodes
    rgb_curve = StringProperty(default='')

    # Brightness Contrast nodes
    brightcon = StringProperty(default='')

    # Hue Saturation nodes
    huesat = StringProperty(default='')

    # Individual modifier node frame
    frame = StringProperty(default='')

    shortcut = BoolProperty(
            name = 'Property Shortcut',
            description = 'Property shortcut on texture list (currently only available on RGB to Intensity)',
            default=False,
            update=update_modifier_shortcut)

    expand_content = BoolProperty(default=True)
