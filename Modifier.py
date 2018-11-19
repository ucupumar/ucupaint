import bpy, re
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *
from . import lib

modifier_type_items = (
        ('INVERT', 'Invert', 
            'Invert input RGB and/or Alpha', 'MODIFIER', 0),

        ('RGB_TO_INTENSITY', 'RGB to Intensity',
            'Input RGB will be used as alpha output, Output RGB will be replaced using custom color.', 
            'MODIFIER', 1),

        ('INTENSITY_TO_RGB', 'Intensity to RGB',
            'Input alpha will be used as RGB output, Output Alpha will use solid value of one.', 
            'MODIFIER', 2),

        ('OVERRIDE_COLOR', 'Override Color',
            'Input RGB will be replaced with custom RGB', 
            'MODIFIER', 3),

        ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 4),
        ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 5),
        ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 6),
        ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 7),
        ('MULTIPLIER', 'Multiplier', '', 'MODIFIER', 8),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

can_be_expanded = {
        'INVERT', 
        'RGB_TO_INTENSITY', 
        'OVERRIDE_COLOR', 
        'COLOR_RAMP',
        'RGB_CURVE',
        'HUE_SATURATION',
        'BRIGHT_CONTRAST',
        'MULTIPLIER',
        }

def add_modifier_nodes(m, tree, ref_tree=None):

    tl = m.id_data.tl
    nodes = tree.nodes
    #links = tree.links

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    match3 = re.match(r'tl\.textures\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    if match1:
        root_ch = tl.channels[int(match1.group(2))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type
        
    elif match2: 
        root_ch = tl.channels[int(match2.group(1))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type

    elif match3: 
        # Texture modifier always use linear colorspace and rgb channel type
        non_color = True
        channel_type = 'RGB'

    else: return None

    # Remove previous start and end if ref tree is passed
    #if ref_tree:
    #    remove_modifier_start_end_nodes(m, ref_tree)

    # Create new pipeline nodes
    #start_rgb = new_node(tree, m, 'start_rgb', 'NodeReroute', 'Start RGB')
    #end_rgb = new_node(tree, m, 'end_rgb', 'NodeReroute', 'End RGB')
    #start_alpha = new_node(tree, m, 'start_alpha', 'NodeReroute', 'Start Alpha')
    #end_alpha = new_node(tree, m, 'end_alpha', 'NodeReroute', 'End Alpha')
    frame = new_node(tree, m, 'frame', 'NodeFrame')

    #start_rgb.parent = frame
    #start_alpha.parent = frame
    #end_rgb.parent = frame
    #end_alpha.parent = frame

    # Create the nodes
    if m.type == 'INVERT':

        if ref_tree:
            invert_ref = ref_tree.nodes.get(m.invert)

        invert = new_node(tree, m, 'invert', 'ShaderNodeGroup', 'Invert')

        if ref_tree:
            copy_node_props(invert_ref, invert)
            if invert_ref.parent:
                ref_tree.nodes.remove(invert_ref.parent)
            ref_tree.nodes.remove(invert_ref)
        else:
            if channel_type == 'VALUE':
                invert.node_tree = get_node_tree_lib(lib.MOD_INVERT_VALUE)
            else: invert.node_tree = get_node_tree_lib(lib.MOD_INVERT)

        frame.label = 'Invert'
        invert.parent = frame

    elif m.type == 'RGB_TO_INTENSITY':

        if ref_tree:
            rgb2i_ref = ref_tree.nodes.get(m.rgb2i)

        rgb2i = new_node(tree, m, 'rgb2i', 'ShaderNodeGroup', 'RGB to Intensity')

        if ref_tree:
            copy_node_props(rgb2i_ref, rgb2i)
            if rgb2i_ref.parent:
                ref_tree.nodes.remove(rgb2i_ref.parent)
            ref_tree.nodes.remove(rgb2i_ref)
        else:
            rgb2i.node_tree = get_node_tree_lib(lib.MOD_RGB2INT)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(rgb2i)

            if channel_type == 'RGB':
                m.rgb2i_col = (1.0, 0.0, 1.0, 1.0)
        
        if non_color:
            rgb2i.inputs['Gamma'].default_value = 1.0
        else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(rgb2i, 'Gamma')

        frame.label = 'RGB to Intensity'
        rgb2i.parent = frame

    elif m.type == 'INTENSITY_TO_RGB':

        if ref_tree:
            i2rgb_ref = ref_tree.nodes.get(m.i2rgb)

        i2rgb = new_node(tree, m, 'i2rgb', 'ShaderNodeGroup', 'Intensity to RGB')

        if ref_tree:
            copy_node_props(i2rgb_ref, i2rgb)
            if i2rgb_ref.parent:
                ref_tree.nodes.remove(i2rgb_ref.parent)
            ref_tree.nodes.remove(i2rgb_ref)
        else:
            i2rgb.node_tree = get_node_tree_lib(lib.MOD_INT2RGB)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(i2rgb)

        #if non_color:
        #    i2rgb.inputs['Gamma'].default_value = 1.0
        #else: i2rgb.inputs['Gamma'].default_value = 1.0/GAMMA

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(i2rgb, 'Gamma')

        frame.label = 'Intensity to RGB'
        i2rgb.parent = frame

    elif m.type == 'OVERRIDE_COLOR':

        if ref_tree:
            oc_ref = ref_tree.nodes.get(m.oc)

        oc = new_node(tree, m, 'oc', 'ShaderNodeGroup', 'Override Color')

        if ref_tree:
            copy_node_props(oc_ref, oc)
            if oc_ref.parent:
                ref_tree.nodes.remove(oc_ref.parent)
            ref_tree.nodes.remove(oc_ref)
        else:
            oc.node_tree = get_node_tree_lib(lib.MOD_OVERRIDE_COLOR)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(oc)

            #if channel_type == 'RGB':
            m.oc_col = (1.0, 1.0, 1.0, 1.0)
            #elif channel_type == 'NORMAL':
            #    m.oc_use_normal_base = True
        
        if non_color:
            oc.inputs['Gamma'].default_value = 1.0
        else: oc.inputs['Gamma'].default_value = 1.0/GAMMA

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(oc, 'Gamma')

        frame.label = 'Override Color'
        oc.parent = frame

    elif m.type == 'COLOR_RAMP':

        if ref_tree:
            color_ramp_alpha_multiply_ref = ref_tree.nodes.get(m.color_ramp_alpha_multiply)
            color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
            color_ramp_linear_ref = ref_tree.nodes.get(m.color_ramp_linear)
            color_ramp_mix_alpha_ref = ref_tree.nodes.get(m.color_ramp_mix_alpha)
            color_ramp_mix_rgb_ref = ref_tree.nodes.get(m.color_ramp_mix_rgb)

        color_ramp_alpha_multiply = new_node(tree, m, 'color_ramp_alpha_multiply', 'ShaderNodeMixRGB', 
                'ColorRamp Alpha Multiply')
        color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
        color_ramp_linear = new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp')
        color_ramp_mix_alpha = new_node(tree, m, 'color_ramp_mix_alpha', 'ShaderNodeMixRGB', 'ColorRamp Mix Alpha')
        color_ramp_mix_rgb = new_node(tree, m, 'color_ramp_mix_rgb', 'ShaderNodeMixRGB', 'ColorRamp Mix RGB')

        if ref_tree:
            copy_node_props(color_ramp_alpha_multiply_ref, color_ramp_alpha_multiply)
            copy_node_props(color_ramp_ref, color_ramp)
            copy_node_props(color_ramp_linear_ref, color_ramp_linear)
            copy_node_props(color_ramp_mix_alpha_ref, color_ramp_mix_alpha)
            copy_node_props(color_ramp_mix_rgb_ref, color_ramp_mix_rgb)

            if color_ramp_ref.parent:
                ref_tree.nodes.remove(color_ramp_ref.parent)

            ref_tree.nodes.remove(color_ramp_alpha_multiply_ref)
            ref_tree.nodes.remove(color_ramp_ref)
            ref_tree.nodes.remove(color_ramp_linear_ref)
            ref_tree.nodes.remove(color_ramp_mix_alpha_ref)
            ref_tree.nodes.remove(color_ramp_mix_rgb_ref)
        else:

            color_ramp_alpha_multiply.inputs[0].default_value = 1.0
            color_ramp_alpha_multiply.blend_type = 'MULTIPLY'

            color_ramp_mix_alpha.inputs[0].default_value = 1.0

            color_ramp_mix_rgb.inputs[0].default_value = 1.0

            if non_color:
                color_ramp_linear.inputs[1].default_value = 1.0
            else: color_ramp_linear.inputs[1].default_value = 1.0/GAMMA

            # Set default color
            color_ramp.color_ramp.elements[0].color = (0,0,0,0)

        frame.label = 'Color Ramp'
        color_ramp.parent = frame
        color_ramp_linear.parent = frame
        color_ramp_alpha_multiply.parent = frame
        color_ramp_mix_alpha.parent = frame
        color_ramp_mix_rgb.parent = frame

    elif m.type == 'RGB_CURVE':

        if ref_tree:
            rgb_curve_ref = ref_tree.nodes.get(m.rgb_curve)

        rgb_curve = new_node(tree, m, 'rgb_curve', 'ShaderNodeRGBCurve', 'RGB Curve')

        if ref_tree:
            copy_node_props(rgb_curve_ref, rgb_curve)
            if rgb_curve_ref.parent:
                ref_tree.nodes.remove(rgb_curve_ref.parent)
            ref_tree.nodes.remove(rgb_curve_ref)

        frame.label = 'RGB Curve'
        rgb_curve.parent = frame

    elif m.type == 'HUE_SATURATION':

        if ref_tree:
            huesat_ref = ref_tree.nodes.get(m.huesat)

        huesat = new_node(tree, m, 'huesat', 'ShaderNodeHueSaturation', 'Hue Saturation')

        if ref_tree:
            copy_node_props(huesat_ref, huesat)
            if huesat_ref.parent:
                ref_tree.nodes.remove(huesat_ref.parent)
            ref_tree.nodes.remove(huesat_ref)

        frame.label = 'Hue Saturation Value'
        huesat.parent = frame

    elif m.type == 'BRIGHT_CONTRAST':

        if ref_tree:
            brightcon_ref = ref_tree.nodes.get(m.brightcon)

        brightcon = new_node(tree, m, 'brightcon', 'ShaderNodeBrightContrast', 'Brightness Contrast')

        if ref_tree:
            copy_node_props(brightcon_ref, brightcon)
            if brightcon_ref.parent:
                ref_tree.nodes.remove(brightcon_ref.parent)
            ref_tree.nodes.remove(brightcon_ref)

        frame.label = 'Brightness Contrast'
        brightcon.parent = frame

    elif m.type == 'MULTIPLIER':

        if ref_tree:
            multiplier_ref = ref_tree.nodes.get(m.multiplier)

        multiplier = new_node(tree, m, 'multiplier', 'ShaderNodeGroup', 'Multiplier')

        if ref_tree:
            copy_node_props(multiplier_ref, multiplier)
            if multiplier_ref.parent:
                ref_tree.nodes.remove(multiplier_ref.parent)
            ref_tree.nodes.remove(multiplier_ref)
        else:
            if channel_type == 'VALUE':
                multiplier.node_tree = get_node_tree_lib(lib.MOD_MULTIPLIER_VALUE)
            else: multiplier.node_tree = get_node_tree_lib(lib.MOD_MULTIPLIER)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(multiplier)

        frame.label = 'Multiplier'
        multiplier.parent = frame

    #rgb, alpha = reconnect_modifier_nodes(tree, m, start_rgb.outputs[0], start_alpha.outputs[0])

    #create_link(tree, rgb, end_rgb.inputs[0])
    #create_link(tree, alpha, end_alpha.inputs[0])

def add_new_modifier(parent, modifier_type):

    tl = parent.id_data.tl

    match1 = re.match(r'^tl\.textures\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^tl\.textures\[(\d+)\]$', parent.path_from_id())
    match3 = re.match(r'^tl\.channels\[(\d+)\]$', parent.path_from_id())

    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match3:
        root_ch = tl.channels[int(match3.group(1))]
        channel_type = root_ch.type
    elif match2:
        channel_type = 'RGB'
    
    tree = get_mod_tree(parent)
    modifiers = parent.modifiers

    # Add new modifier and move it to the top
    m = modifiers.add()

    if channel_type == 'VALUE' and modifier_type == 'OVERRIDE_COLOR':
        name = 'Override Value'
    else: name = [mt[1] for mt in modifier_type_items if mt[0] == modifier_type][0]

    m.name = get_unique_name(name, modifiers)
    modifiers.move(len(modifiers)-1, 0)
    m = modifiers[0]
    m.type = modifier_type
    #m.channel_type = root_ch.type

    add_modifier_nodes(m, tree)

    if match1: 
        # Enable modifier tree if fine bump map is used
        if parent.normal_map_type == 'FINE_BUMP_MAP' or (
                parent.enable_mask_bump and parent.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}):
            enable_modifiers_tree(parent)
    elif match2 and parent.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
        enable_modifiers_tree(parent)

    return m

def delete_modifier_nodes(tree, mod):

    # Delete the nodes
    remove_node(tree, mod, 'start_rgb')
    remove_node(tree, mod, 'start_alpha')
    remove_node(tree, mod, 'end_rgb')
    remove_node(tree, mod, 'end_alpha')
    remove_node(tree, mod, 'frame')

    if mod.type == 'RGB_TO_INTENSITY':
        remove_node(tree, mod, 'rgb2i')

    elif mod.type == 'INTENSITY_TO_RGB':
        remove_node(tree, mod, 'i2rgb')

    elif mod.type == 'OVERRIDE_COLOR':
        remove_node(tree, mod, 'oc')

    elif mod.type == 'INVERT':
        remove_node(tree, mod, 'invert')

    elif mod.type == 'COLOR_RAMP':
        remove_node(tree, mod, 'color_ramp')
        remove_node(tree, mod, 'color_ramp_linear')
        remove_node(tree, mod, 'color_ramp_alpha_multiply')
        remove_node(tree, mod, 'color_ramp_mix_rgb')
        remove_node(tree, mod, 'color_ramp_mix_alpha')

    elif mod.type == 'RGB_CURVE':
        remove_node(tree, mod, 'rgb_curve')

    elif mod.type == 'HUE_SATURATION':
        remove_node(tree, mod, 'huesat')

    elif mod.type == 'BRIGHT_CONTRAST':
        remove_node(tree, mod, 'brightcon')

    elif mod.type == 'MULTIPLIER':
        remove_node(tree, mod, 'multiplier')

class YNewTexModifier(bpy.types.Operator):
    bl_idname = "node.y_new_texture_modifier"
    bl_label = "New Texture Modifier"
    bl_description = "New Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node() and hasattr(context, 'parent')

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        m = re.match(r'^tl\.textures\[(\d+)\]', context.parent.path_from_id())
        if m: tex = tl.textures[int(m.group(1))]
        else: tex = None

        mod = add_new_modifier(context.parent, self.type)

        #if self.type == 'RGB_TO_INTENSITY' and root_ch.type == 'RGB':
        #    mod.rgb2i_col = (1,0,1,1)

        # If RGB to intensity is added, bump base is better be 0.0
        if tex and self.type == 'RGB_TO_INTENSITY':
            for i, ch in enumerate(tl.channels):
                c = context.texture.channels[i]
                if ch.type == 'NORMAL':
                    c.bump_base_value = 0.0

        # Expand channel content to see added modifier
        if hasattr(context, 'channel_ui'):
            context.channel_ui.expand_content = True

        if hasattr(context, 'tex_ui'):
            context.tex_ui.expand_content = True

        # Rearrange nodes
        if tex:
            rearrange_tex_nodes(tex)
            reconnect_tex_nodes(tex)
        else: 
            rearrange_tl_nodes(group_tree)
            reconnect_tl_nodes(group_tree)

        # Reconnect modifier nodes
        #reconnect_between_modifier_nodes(context.parent)

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

    #parent_type = EnumProperty(
    #        name = 'Modifier Parent',
    #        items = (('CHANNEL', 'Channel', '' ),
    #                 ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
    #                ),
    #        default = 'TEXTURE_CHANNEL')

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

        if tex: tree = get_tree(tex)
        else: tree = group_tree

        # Swap modifier
        parent.modifiers.move(index, new_index)

        # Reconnect modifier nodes
        #reconnect_between_modifier_nodes(parent)
        reconnect_tex_nodes(tex)

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

    #parent_type = EnumProperty(
    #        name = 'Modifier Parent',
    #        items = (('CHANNEL', 'Channel', '' ),
    #                 ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
    #                ),
    #        default = 'TEXTURE_CHANNEL')

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

        tree = get_mod_tree(parent)

        # Delete the nodes
        delete_modifier_nodes(tree, mod)

        # Delete the modifier
        parent.modifiers.remove(index)

        # Delete modifier pipeline if no modifier left
        #if len(parent.modifiers) == 0:
        #    unset_modifier_pipeline_nodes(tree, parent)

        if tex:
            if len(parent.modifiers) == 0:
                disable_modifiers_tree(parent, False)
            reconnect_tex_nodes(tex)
        else:
            # Reconnect nodes
            #reconnect_between_modifier_nodes(parent)
            reconnect_tl_nodes(group_tree)

        # Rearrange nodes
        if tex:
            rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

def draw_modifier_properties(context, channel_type, nodes, modifier, layout, is_tex_ch=False):

    #if modifier.type not in {'INVERT'}:
    #    label = [mt[1] for mt in modifier_type_items if modifier.type == mt[0]][0]
    #    layout.label(label + ' Properties:')

    if modifier.type == 'INVERT':
        row = layout.row(align=True)
        invert = nodes.get(modifier.invert)
        if channel_type == 'VALUE':
            row.prop(modifier, 'invert_r_enable', text='Value', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='Alpha', toggle=True)
        else:
            row.prop(modifier, 'invert_r_enable', text='R', toggle=True)
            row.prop(modifier, 'invert_g_enable', text='G', toggle=True)
            row.prop(modifier, 'invert_b_enable', text='B', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='A', toggle=True)

    elif modifier.type == 'RGB_TO_INTENSITY':
        col = layout.column(align=True)
        row = col.row()
        row.label(text='Color:')
        row.prop(modifier, 'rgb2i_col', text='')

        # Shortcut only available on texture layer channel
        #if 'YLayerChannel' in str(type(channel)):
        if is_tex_ch:
            row = col.row(align=True)
            row.label(text='Shortcut on texture list:')
            row.prop(modifier, 'shortcut', text='')

    elif modifier.type == 'OVERRIDE_COLOR':
        col = layout.column(align=True)
        #if channel_type == 'NORMAL':
        #    row = col.row()
        #    row.label(text='Use Normal Base:')
        #    row.prop(modifier, 'oc_use_normal_base', text='')

        #if not modifier.oc_use_normal_base:
        row = col.row()
        if channel_type == 'VALUE':
            row.label(text='Value:')
            row.prop(modifier, 'oc_val', text='')
        else:
            row.label(text='Color:')
            row.prop(modifier, 'oc_col', text='')

            row = col.row()
            row.label(text='Shortcut on texture list:')
            row.prop(modifier, 'shortcut', text='')

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
        col.label(text='Hue:')
        col.label(text='Saturation:')
        col.label(text='Value:')

        col = row.column(align=True)
        for i in range(3):
            col.prop(huesat.inputs[i], 'default_value', text='')

    elif modifier.type == 'BRIGHT_CONTRAST':
        #brightcon = nodes.get(modifier.brightcon)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label(text='Brightness:')
        col.label(text='Contrast:')

        col = row.column(align=True)
        #col.prop(brightcon.inputs[1], 'default_value', text='')
        #col.prop(brightcon.inputs[2], 'default_value', text='')
        col.prop(modifier, 'brightness_value', text='')
        col.prop(modifier, 'contrast_value', text='')

    elif modifier.type == 'MULTIPLIER':
        multiplier = nodes.get(modifier.multiplier)

        col = layout.column(align=True)
        row = col.row()
        row.label(text='Clamp:')
        row.prop(modifier, 'use_clamp', text='')
        if channel_type == 'VALUE':
            #col.prop(multiplier.inputs[3], 'default_value', text='Value')
            #col.prop(multiplier.inputs[4], 'default_value', text='Alpha')
            col.prop(modifier, 'multiplier_r_val', text='Value')
            col.prop(modifier, 'multiplier_a_val', text='Alpha')
        else:
            #col.prop(multiplier.inputs[3], 'default_value', text='R')
            #col.prop(multiplier.inputs[4], 'default_value', text='G')
            #col.prop(multiplier.inputs[5], 'default_value', text='B')
            col.prop(modifier, 'multiplier_r_val', text='R')
            col.prop(modifier, 'multiplier_g_val', text='G')
            col.prop(modifier, 'multiplier_b_val', text='B')
            #col = layout.column(align=True)
            col.separator()
            #col.prop(multiplier.inputs[6], 'default_value', text='Alpha')
            col.prop(modifier, 'multiplier_a_val', text='Alpha')

def update_modifier_enable(self, context):

    tree = get_mod_tree(self)
    nodes = tree.nodes

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i = nodes.get(self.rgb2i)
        #rgb2i.mute = not self.enable
        rgb2i.inputs['Intensity'].default_value = 1.0 if self.enable else 0.0

    elif self.type == 'INTENSITY_TO_RGB':
        i2rgb = nodes.get(self.i2rgb)
        #i2rgb.mute = not self.enable
        i2rgb.inputs['Intensity'].default_value = 1.0 if self.enable else 0.0

    elif self.type == 'OVERRIDE_COLOR':
        oc = nodes.get(self.oc)
        #oc.mute = not self.enable
        oc.inputs['Intensity'].default_value = 1.0 if self.enable else 0.0

    elif self.type == 'INVERT':
        invert = nodes.get(self.invert)
        #invert.mute = not self.enable
        update_invert_channel(self, context)

    elif self.type == 'COLOR_RAMP':
        #color_ramp = nodes.get(self.color_ramp)
        #color_ramp.mute = not self.enable
        #color_ramp_linear = nodes.get(self.color_ramp_linear)
        #color_ramp_linear.mute = not self.enable
        #color_ramp_alpha_multiply = nodes.get(self.color_ramp_alpha_multiply)
        #color_ramp_alpha_multiply.mute = not self.enable

        color_ramp_mix_rgb = nodes.get(self.color_ramp_mix_rgb)
        color_ramp_mix_rgb.inputs['Fac'].default_value = 1.0 if self.enable else 0.0
        #color_ramp_mix_rgb.mute = not self.enable

        color_ramp_mix_alpha = nodes.get(self.color_ramp_mix_alpha)
        color_ramp_mix_alpha.inputs['Fac'].default_value = 1.0 if self.enable else 0.0
        #color_ramp_mix_alpha.mute = not self.enable

    elif self.type == 'RGB_CURVE':
        rgb_curve = nodes.get(self.rgb_curve)
        rgb_curve.inputs['Fac'].default_value = 1.0 if self.enable else 0.0
        #rgb_curve.mute = not self.enable

    elif self.type == 'HUE_SATURATION':
        huesat = nodes.get(self.huesat)
        huesat.inputs['Fac'].default_value = 1.0 if self.enable else 0.0
        #huesat.mute = not self.enable

    elif self.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(self.brightcon)
        #brightcon.mute = not self.enable
        update_brightcon_value(self, context)

    elif self.type == 'MULTIPLIER':
        multiplier = nodes.get(self.multiplier)
        #multiplier.mute = not self.enable
        update_use_clamp(self, context)
        update_multiplier_val_input(self, context)

def update_modifier_shortcut(self, context):

    tl = self.id_data.tl

    mod = self

    if mod.shortcut:

        match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
        match2 = re.match(r'tl\.textures\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
        match3 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())


        if match1 or match2:

            tex = tl.textures[int(match1.group(1))]
            tex.color_shortcut = False

            for m in tex.modifiers:
                if m != mod:
                    m.shortcut = False

            for ch in tex.channels:
                for m in ch.modifiers:
                    if m != mod:
                        m.shortcut = False

        elif match3:
            channel = tl.channels[int(match2.group(1))]
            for m in channel.modifiers:
                if m != mod: 
                    m.shortcut = False

def update_invert_channel(self, context):

    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'tl\.textures\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]
        channel_type = root_ch.type
    elif match3:
        channel_type = 'RGB'

    tree = get_mod_tree(self)
    invert = tree.nodes.get(self.invert)

    invert.inputs[2].default_value = 1.0 if self.invert_r_enable and self.enable else 0.0
    if channel_type == 'VALUE':
        invert.inputs[3].default_value = 1.0 if self.invert_a_enable and self.enable else 0.0
    else:
        invert.inputs[3].default_value = 1.0 if self.invert_g_enable and self.enable else 0.0
        invert.inputs[4].default_value = 1.0 if self.invert_b_enable and self.enable else 0.0
        invert.inputs[5].default_value = 1.0 if self.invert_a_enable and self.enable else 0.0

def update_use_clamp(self, context):
    tree = get_mod_tree(self)

    if self.type == 'MULTIPLIER':
        multiplier = tree.nodes.get(self.multiplier)
        multiplier.inputs[2].default_value = 1.0 if self.use_clamp and self.enable else 0.0

def update_multiplier_val_input(self, context):
    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'tl\.textures\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]
        channel_type = root_ch.type
    elif match3:
        channel_type = 'RGB'

    tree = get_mod_tree(self)

    if self.type == 'MULTIPLIER':
        multiplier = tree.nodes.get(self.multiplier)
        multiplier.inputs[3].default_value = self.multiplier_r_val if self.enable else 1.0
        if channel_type == 'VALUE':
            multiplier.inputs[4].default_value = self.multiplier_a_val if self.enable else 1.0
        else:
            multiplier.inputs[4].default_value = self.multiplier_g_val if self.enable else 1.0
            multiplier.inputs[5].default_value = self.multiplier_b_val if self.enable else 1.0
            multiplier.inputs[6].default_value = self.multiplier_a_val if self.enable else 1.0

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(multiplier)

def update_brightcon_value(self, context):
    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'tl\.textures\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]
        channel_type = root_ch.type
    elif match3:
        channel_type = 'RGB'

    tree = get_mod_tree(self)

    if self.type == 'BRIGHT_CONTRAST':
        brightcon = tree.nodes.get(self.brightcon)
        brightcon.inputs['Bright'].default_value = self.brightness_value if self.enable else 0.0
        brightcon.inputs['Contrast'].default_value = self.contrast_value if self.enable else 0.0

def update_rgb2i_col(self, context):
    tree = get_mod_tree(self)

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i = tree.nodes.get(self.rgb2i)
        rgb2i.inputs['RGB To Intensity Color'].default_value = self.rgb2i_col

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(rgb2i, 2)

def update_oc_col(self, context):
    tree = get_mod_tree(self)

    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())

    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]
        channel_type = root_ch.type
    else:
        channel_type = 'RGB'

    if self.type == 'OVERRIDE_COLOR': #and not self.oc_use_normal_base:
        oc = tree.nodes.get(self.oc)

        if channel_type == 'VALUE':
            col = (self.oc_val, self.oc_val, self.oc_val, 1.0)
        else: col = self.oc_col

        if oc: oc.inputs['Override Color'].default_value = col

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(oc, 2)

#def update_oc_use_normal_base(self, context):
#    tree = get_mod_tree(self)
#
#    if self.type != 'OVERRIDE_COLOR': return 
#    
#    if self.oc_use_normal_base:
#
#        tl = self.id_data.tl
#        match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
#        #match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
#        if match1: 
#            tex = tl.textures[int(match1.group(1))]
#            ch = tex.channels[int(match1.group(2))]
#            root_ch = tl.channels[int(match1.group(2))]
#        #elif match2:
#        #    root_ch = tl.channels[int(match2.group(1))]
#        else: return
#
#        if root_ch.type != 'NORMAL': return
#
#        if ch.normal_map_type in {'FINE_BUMP_MAP', 'BUMP_MAP'}:
#            #if ch.enable_mask_bump:
#            #    val = 1.0
#            #else: 
#            val = ch.bump_base_value
#            val = (val, val, val, 1.0)
#        else: 
#            val = (0.5, 0.5, 1.0, 1.0)
#
#        #oc = tree.nodes.get(self.oc)
#        #if oc: oc.inputs[2].default_value = val
#
#        self.oc_col = val

class YTextureModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_modifier_enable)
    name = StringProperty(default='')

    #channel_type = StringProperty(default='')

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

    rgb2i_col = FloatVectorProperty(name='RGB to Intensity Color', size=4, subtype='COLOR', 
            default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0,
            update=update_rgb2i_col)

    # Intensity to RGB nodes
    i2rgb = StringProperty(default='')

    # Override Color nodes
    oc = StringProperty(default='')

    oc_col = FloatVectorProperty(name='Override Color', size=4, subtype='COLOR', 
            default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0,
            update=update_oc_col)

    oc_val = FloatProperty(name='Override Value', subtype='FACTOR', 
            default=1.0, min=0.0, max=1.0,
            update=update_oc_col)

    #oc_use_normal_base = BoolProperty(
    #        name = 'Use Normal Base',
    #        description = 'Use normal base instead of custom color',
    #        default=False,
    #        update=update_oc_use_normal_base)

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
    color_ramp_linear = StringProperty(default='')
    color_ramp_alpha_multiply = StringProperty(default='')
    color_ramp_mix_rgb = StringProperty(default='')
    color_ramp_mix_alpha = StringProperty(default='')

    # RGB Curve nodes
    rgb_curve = StringProperty(default='')

    # Brightness Contrast nodes
    brightcon = StringProperty(default='')

    brightness_value = FloatProperty(name='Brightness', description='Brightness', 
            default=0.0, min=-100.0, max=100.0, update=update_brightcon_value)
    contrast_value = FloatProperty(name='Contrast', description='Contrast', 
            default=0.0, min=-100.0, max=100.0, update=update_brightcon_value)

    # Hue Saturation nodes
    huesat = StringProperty(default='')

    # Multiplier nodes
    multiplier = StringProperty(default='')

    multiplier_r_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_g_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_b_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_a_val = FloatProperty(default=1.0, update=update_multiplier_val_input)

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

def enable_modifiers_tree(parent, rearrange = False):
    
    group_tree = parent.id_data
    tl = group_tree.tl

    match1 = re.match(r'^tl\.textures\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^tl\.textures\[(\d+)\]$', parent.path_from_id())
    if match1:
        tex = tl.textures[int(match1.group(1))]
        root_ch = tl.channels[int(match1.group(2))]
        name = root_ch.name + ' ' + tex.name
        #if tex.type == 'BACKGROUND':
        if tex.type in {'BACKGROUND', 'COLOR'}:
            return
        #if tex.type == 'GROUP' and root_ch.type == 'NORMAL':
        #    return
    elif match2:
        tex = parent
        name = tex.name
        if tex.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
            return
    else:
        return

    if len(parent.modifiers) == 0:
        return None

    # Check if modifier tree already available
    if parent.mod_group != '': 
        return 

    # Create modifier tree
    mod_tree = bpy.data.node_groups.new('~TL Modifiers ' + name, 'ShaderNodeTree')

    mod_tree.inputs.new('NodeSocketColor', 'RGB')
    mod_tree.inputs.new('NodeSocketFloat', 'Alpha')
    mod_tree.outputs.new('NodeSocketColor', 'RGB')
    mod_tree.outputs.new('NodeSocketFloat', 'Alpha')

    # New inputs and outputs
    mod_tree_start = mod_tree.nodes.new('NodeGroupInput')
    mod_tree_start.name = MOD_TREE_START
    mod_tree_end = mod_tree.nodes.new('NodeGroupOutput')
    mod_tree_end.name = MOD_TREE_END

    if match2 and tex.source_group != '':
        tex_tree = get_source_tree(tex)
    else: tex_tree = get_tree(tex)

    # Create main modifier group
    mod_group = new_node(tex_tree, parent, 'mod_group', 'ShaderNodeGroup', 'mod_group')
    mod_group.node_tree = mod_tree

    if match1:
        # Create modifier group neighbor
        mod_n = new_node(tex_tree, parent, 'mod_n', 'ShaderNodeGroup', 'mod_n')
        mod_s = new_node(tex_tree, parent, 'mod_s', 'ShaderNodeGroup', 'mod_s')
        mod_e = new_node(tex_tree, parent, 'mod_e', 'ShaderNodeGroup', 'mod_e')
        mod_w = new_node(tex_tree, parent, 'mod_w', 'ShaderNodeGroup', 'mod_w')
        mod_n.node_tree = mod_tree
        mod_s.node_tree = mod_tree
        mod_e.node_tree = mod_tree
        mod_w.node_tree = mod_tree
    elif match2:
        mod_group_1 = new_node(tex_tree, parent, 'mod_group_1', 'ShaderNodeGroup', 'mod_group_1')
        mod_group_1.node_tree = mod_tree

    for mod in parent.modifiers:
        add_modifier_nodes(mod, mod_tree, tex_tree)

    if rearrange:
        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

    return mod_tree

def disable_modifiers_tree(parent, rearrange=False):
    group_tree = parent.id_data
    tl = group_tree.tl

    match1 = re.match(r'^tl\.textures\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^tl\.textures\[(\d+)\]$', parent.path_from_id())
    if match1: 
        tex = tl.textures[int(match1.group(1))]
        root_ch = tl.channels[int(match1.group(2))]

        # Check if fine bump map is still used
        if len(parent.modifiers) > 0 and root_ch.type == 'NORMAL' and (
                parent.normal_map_type == 'FINE_BUMP_MAP'
                or (parent.enable_mask_bump and parent.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'})):
            return

        # Check if channel use blur
        if hasattr(parent, 'enable_blur') and parent.enable_blur:
            return
    elif match2:
        tex = parent
        if tex.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP'}:
            return
    else:
        return

    # Check if modifier tree already gone
    if parent.mod_group == '': return

    if match2 and tex.source_group != '':
        tex_tree = get_source_tree(tex)
    else: tex_tree = get_tree(tex)

    # Get modifier group
    mod_group = tex_tree.nodes.get(parent.mod_group)

    # Add new copied modifier nodes on texture tree
    for mod in parent.modifiers:
        add_modifier_nodes(mod, tex_tree, mod_group.node_tree)

    # Remove modifier tree
    remove_node(tex_tree, parent, 'mod_group')

    if match1:
        # Remove modifier group neighbor
        remove_node(tex_tree, parent, 'mod_n')
        remove_node(tex_tree, parent, 'mod_s')
        remove_node(tex_tree, parent, 'mod_e')
        remove_node(tex_tree, parent, 'mod_w')
    elif match2:
        remove_node(tex_tree, parent, 'mod_group_1')

    if rearrange:
        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

def register():
    bpy.utils.register_class(YNewTexModifier)
    bpy.utils.register_class(YMoveTexModifier)
    bpy.utils.register_class(YRemoveTexModifier)
    bpy.utils.register_class(YTextureModifier)

def unregister():
    bpy.utils.unregister_class(YNewTexModifier)
    bpy.utils.unregister_class(YMoveTexModifier)
    bpy.utils.unregister_class(YRemoveTexModifier)
    bpy.utils.unregister_class(YTextureModifier)
