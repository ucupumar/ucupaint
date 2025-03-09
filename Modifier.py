import bpy, re
from bpy.props import *
from .common import *
from .modifier_common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *

modifier_type_items = (
    ('INVERT', 'Invert', 'Invert input RGB and/or Alpha', 'MODIFIER', 0),

    (
        'RGB_TO_INTENSITY', 'RGB to Alpha',
        'Input RGB will be used as alpha output, Output RGB will be replaced using custom color.', 
        'MODIFIER', 1
    ),

    (
        'INTENSITY_TO_RGB', 'Alpha to RGB',
        'Input alpha will be used as RGB output, Output Alpha will use solid value of one.', 
        'MODIFIER', 2
    ),

    # Deprecated
    (
        'OVERRIDE_COLOR', 'Override Color',
        'Input RGB will be replaced with custom RGB', 
        'MODIFIER', 3
    ),

    ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 4),
    ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 5),
    ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 6),
    ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 7),
    # Deprecated
    ('MULTIPLIER', 'Multiplier', '', 'MODIFIER', 8),
    ('MATH', 'Math', '', 'MODIFIER',9)
)

can_be_expanded = {
    'INVERT', 
    'RGB_TO_INTENSITY', 
    'OVERRIDE_COLOR', # Deprecated
    'COLOR_RAMP',
    'RGB_CURVE',
    'HUE_SATURATION',
    'BRIGHT_CONTRAST',
    'MULTIPLIER', # Deprecated
    'MATH'
}

def get_modifier_channel_type(mod, return_non_color=False):

    yp = mod.id_data.yp
    match1 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match2 = re.match(r'yp\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match3 = re.match(r'yp\.layers\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    if match1: 
        root_ch = yp.channels[int(match1.group(2))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type
    elif match2:
        root_ch = yp.channels[int(match2.group(1))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type
    elif match3:

        # Image layer modifiers always use srgb colorspace
        layer = yp.layers[int(match3.group(1))]
        non_color = layer.type != 'IMAGE'
        channel_type = 'RGB'

    if return_non_color:
        return channel_type, non_color

    return channel_type

def add_new_modifier(parent, modifier_type):

    yp = parent.id_data.yp

    match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())
    match3 = re.match(r'^yp\.channels\[(\d+)\]$', parent.path_from_id())

    if match1: 
        root_ch = yp.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match3:
        root_ch = yp.channels[int(match3.group(1))]
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
    shift_modifier_fcurves_down(parent)
    m = modifiers[0]
    m.type = modifier_type

    check_modifiers_trees(parent)

    return m

class YNewYPaintModifier(bpy.types.Operator):
    bl_idname = "wm.y_new_ypaint_modifier"
    bl_label = "New " + get_addon_title() + " Modifier"
    bl_description = "New " + get_addon_title() + " Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT'
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and hasattr(context, 'parent')

    def execute(self, context):
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp

        m1 = re.match(r'^yp\.layers\[(\d+)\]$', context.parent.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', context.parent.path_from_id())
        m3 = re.match(r'^yp\.channels\[(\d+)\]$', context.parent.path_from_id())

        if m1: layer = yp.layers[int(m1.group(1))]
        elif m2: layer = yp.layers[int(m2.group(1))]
        else: layer = None

        mod = add_new_modifier(context.parent, self.type)

        #if self.type == 'RGB_TO_INTENSITY' and root_ch.type == 'RGB':
        #    mod.rgb2i_col = (1,0,1,1)

        # If RGB to intensity is added, bump base is better be 0.0
        if layer and self.type == 'RGB_TO_INTENSITY':
            for i, ch in enumerate(yp.channels):
                c = context.layer.channels[i]
                if ch.type == 'NORMAL':
                    c.bump_base_value = 0.0

        # Expand channel content to see added modifier
        if m1:
            context.layer_ui.expand_content = True
        elif m2:
            context.layer_ui.channels[int(m2.group(2))].expand_content = True
        elif m3:
            context.channel_ui.expand_content = True

        # Reconnect and rearrange nodes
        if layer:
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)
        else: 
            reconnect_yp_nodes(group_tree)
            rearrange_yp_nodes(group_tree)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YMoveYPaintModifier(bpy.types.Operator):
    bl_idname = "wm.y_move_ypaint_modifier"
    bl_label = "Move " + get_addon_title() + " Modifier"
    bl_description = "Move " + get_addon_title() + " Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
        name = 'Direction',
        items = (
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        ),
        default = 'UP'
    )

    @classmethod
    def poll(cls, context):
        return (get_active_ypaint_node() and 
                hasattr(context, 'parent') and hasattr(context, 'modifier'))

    def execute(self, context):
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp

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

        layer = context.layer if hasattr(context, 'layer') else None

        # Swap modifier
        parent.modifiers.move(index, new_index)
        swap_modifier_fcurves(parent, index, new_index)

        # Reconnect and rearrange nodes
        if layer: 
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)
        else: 
            reconnect_yp_nodes(group_tree)
            rearrange_yp_nodes(group_tree)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YRemoveYPaintModifier(bpy.types.Operator):
    bl_idname = "wm.y_remove_ypaint_modifier"
    bl_label = "Remove " + get_addon_title() + " Modifier"
    bl_description = "Remove " + get_addon_title() + " Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and hasattr(context, 'modifier')

    def execute(self, context):
        group_tree = context.parent.id_data
        yp = group_tree.yp

        parent = context.parent
        mod = context.modifier

        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        if len(parent.modifiers) < 1: return {'CANCELLED'}

        layer = context.layer if hasattr(context, 'layer') else None

        tree = get_mod_tree(parent)

        # Remove modifier fcurves first
        remove_entity_fcurves(mod)
        shift_modifier_fcurves_up(parent, index)

        # Delete the nodes
        delete_modifier_nodes(tree, mod)

        # Delete the modifier
        parent.modifiers.remove(index)

        # Delete modifier pipeline if no modifier left
        #if len(parent.modifiers) == 0:
        #    unset_modifier_pipeline_nodes(tree, parent)

        check_modifiers_trees(parent)

        if layer:
            reconnect_layer_nodes(layer)
        else:
            reconnect_yp_nodes(group_tree)

        # Rearrange nodes
        if layer:
            rearrange_layer_nodes(layer)
        else: rearrange_yp_nodes(group_tree)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

def draw_modifier_properties(context, channel_type, nodes, modifier, layout, is_layer_ch=False):

    if modifier.type == 'INVERT':
        row = layout.row(align=True)
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
        rgb2i = nodes.get(modifier.rgb2i)
        if rgb2i:
            row.prop(rgb2i.inputs[3], 'default_value', text='')
        else: row.prop(modifier, 'rgb2i_col', text='')

        # Shortcut only available on layer channel
        if is_layer_ch:
            row = col.row(align=True)
            row.label(text='Shortcut on layer list:')
            row.prop(modifier, 'shortcut', text='')

    elif modifier.type == 'OVERRIDE_COLOR':
        col = layout.column(align=True)

        row = col.row()
        if channel_type == 'VALUE':
            row.label(text='Value:')
            row.prop(modifier, 'oc_val', text='')
        else:
            row.label(text='Color:')
            row.prop(modifier, 'oc_col', text='')

            row = col.row()
            row.label(text='Shortcut on layer list:')
            row.prop(modifier, 'shortcut', text='')

    elif modifier.type == 'COLOR_RAMP':
        color_ramp = nodes.get(modifier.color_ramp)
        if color_ramp:
            layout.template_color_ramp(color_ramp, "color_ramp", expand=True)

    elif modifier.type == 'RGB_CURVE':
        rgb_curve = nodes.get(modifier.rgb_curve)
        if rgb_curve:
            rgb_curve.draw_buttons_ext(context, layout)

    elif modifier.type == 'HUE_SATURATION':
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label(text='Hue:')
        col.label(text='Saturation:')
        col.label(text='Value:')

        col = row.column(align=True)
        huesat = nodes.get(modifier.huesat)
        if huesat:
            col.prop(huesat.inputs[0], 'default_value', text='')
            col.prop(huesat.inputs[1], 'default_value', text='')
            col.prop(huesat.inputs[2], 'default_value', text='')
        else:
            col.prop(modifier, 'huesat_hue_val', text='')
            col.prop(modifier, 'huesat_saturation_val', text='')
            col.prop(modifier, 'huesat_value_val', text='')

    elif modifier.type == 'BRIGHT_CONTRAST':
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label(text='Brightness:')
        col.label(text='Contrast:')

        col = row.column(align=True)
        brightcon = nodes.get(modifier.brightcon)
        if brightcon:
            col.prop(brightcon.inputs[1], 'default_value', text='')
            col.prop(brightcon.inputs[2], 'default_value', text='')
        else:
            col.prop(modifier, 'brightness_value', text='')
            col.prop(modifier, 'contrast_value', text='')

    elif modifier.type == 'MULTIPLIER':
        col = layout.column(align=True)
        row = col.row()
        row.label(text='Clamp:')
        row.prop(modifier, 'use_clamp', text='')
        if channel_type == 'VALUE':
            col.prop(modifier, 'multiplier_r_val', text='Value')
            col.prop(modifier, 'multiplier_a_val', text='Alpha')
        else:
            col.prop(modifier, 'multiplier_r_val', text='R')
            col.prop(modifier, 'multiplier_g_val', text='G')
            col.prop(modifier, 'multiplier_b_val', text='B')
            col.separator()
            col.prop(modifier, 'multiplier_a_val', text='Alpha')
    
    elif modifier.type == 'MATH':
        col = layout.column(align=True)
        row = col.row()
        col.prop(modifier, 'math_meth')
        row = col.row()
        row.label(text='Clamp:')
        row.prop(modifier, 'use_clamp', text='')
        math = nodes.get(modifier.math)
        if channel_type == 'VALUE':
            if math: col.prop(math.inputs[2], 'default_value', text='Value')
            else: col.prop(modifier, 'math_r_val', text='Value')
        else :
            if math:
                col.prop(math.inputs[2], 'default_value', text='R')
                col.prop(math.inputs[3], 'default_value', text='G')
                col.prop(math.inputs[4], 'default_value', text='B')
            else:
                col.prop(modifier, 'math_r_val', text='R')
                col.prop(modifier, 'math_g_val', text='G')
                col.prop(modifier, 'math_b_val', text='B')
        col.separator()
        row = col.row()
        row.label(text='Affect Alpha:')
        row.prop(modifier, 'affect_alpha', text='')
        if modifier.affect_alpha :
            if math: 
                if channel_type == 'VALUE':
                    col.prop(math.inputs[3], 'default_value', text='A')
                else: col.prop(math.inputs[5], 'default_value', text='A')
            else: col.prop(modifier, 'math_a_val', text='A')

def update_modifier_enable(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    tree = get_mod_tree(self)

    check_modifier_nodes(self, tree)

    match1 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'yp\.layers\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match3 = re.match(r'yp\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())

    if match1 or match2:
        if match1: layer = yp.layers[int(match1.group(1))]
        else: layer = yp.layers[int(match2.group(1))]

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

    elif match3:
        channel = yp.channels[int(match3.group(1))]
        reconnect_yp_nodes(self.id_data)
        rearrange_yp_nodes(self.id_data)

def update_modifier_shortcut(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return

    mod = self

    if mod.shortcut:

        match1 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
        match2 = re.match(r'yp\.layers\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
        match3 = re.match(r'yp\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())

        if match1 or match2:

            layer = yp.layers[int(match1.group(1))]
            layer.color_shortcut = False

            for m in layer.modifiers:
                if m != mod:
                    m.shortcut = False

            for ch in layer.channels:
                for m in ch.modifiers:
                    if m != mod:
                        m.shortcut = False

        elif match3:
            channel = yp.channels[int(match2.group(1))]
            for m in channel.modifiers:
                if m != mod: 
                    m.shortcut = False

def update_invert_channel(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    channel_type = get_modifier_channel_type(self)
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
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    tree = get_mod_tree(self)
    channel_type = get_modifier_channel_type(self)

    if self.type == 'MULTIPLIER':
        multiplier = tree.nodes.get(self.multiplier)
        multiplier.inputs[2].default_value = 1.0 if self.use_clamp and self.enable else 0.0
    elif self.type == 'MATH':
        math = tree.nodes.get(self.math)
        math.node_tree.nodes.get('Math.R').use_clamp = self.use_clamp
        math.node_tree.nodes.get('Math.A').use_clamp = self.use_clamp
        if channel_type != 'VALUE':
            math.node_tree.nodes.get('Math.G').use_clamp = self.use_clamp
            math.node_tree.nodes.get('Math.B').use_clamp = self.use_clamp

def update_affect_alpha(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    tree = get_mod_tree(self)

    if self.type == 'MATH':
        math = tree.nodes.get(self.math).node_tree
        alpha = math.nodes.get('Mix.A')
        if self.affect_alpha:
            alpha.mute = False
        else:
            alpha.mute = True

def update_math_method(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    tree = get_mod_tree(self)

    if self.type == 'MATH':
        math = tree.nodes.get(self.math)
        math.node_tree.nodes.get('Math.R').operation = self.math_meth
        math.node_tree.nodes.get('Math.G').operation = self.math_meth
        math.node_tree.nodes.get('Math.B').operation = self.math_meth
        math.node_tree.nodes.get('Math.A').operation = self.math_meth

def update_multiplier_val_input(self, context):

    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    channel_type = get_modifier_channel_type(self)
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

def update_oc_col(self, context):

    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    channel_type = get_modifier_channel_type(self)
    tree = get_mod_tree(self)

    if self.type == 'OVERRIDE_COLOR': #and not self.oc_use_normal_base:
        oc = tree.nodes.get(self.oc)

        if channel_type == 'VALUE':
            col = (self.oc_val, self.oc_val, self.oc_val, 1.0)
        else: col = self.oc_col

        if oc: oc.inputs['Override Color'].default_value = col

class YPaintModifier(bpy.types.PropertyGroup):
    enable : BoolProperty(default=True, update=update_modifier_enable)
    name : StringProperty(default='')

    type : EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT'
    )

    # RGB to Intensity nodes
    rgb2i : StringProperty(default='')

    rgb2i_col : FloatVectorProperty(
        name = 'RGB to Intensity Color',
        size = 4,
        subtype = 'COLOR', 
        default=(1.0, 0.0, 1.0, 1.0), min=0.0, max=1.0
    )

    # Intensity to RGB nodes
    i2rgb : StringProperty(default='')

    # Override Color nodes (Deprecated)
    oc : StringProperty(default='')

    oc_col : FloatVectorProperty(
        name = 'Override Color',
        size = 4,
        subtype = 'COLOR', 
        default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0,
        update = update_oc_col
    )

    oc_val : FloatProperty(
        name = 'Override Value',
        subtype = 'FACTOR', 
        default=1.0, min=0.0, max=1.0,
        update = update_oc_col
    )

    # Invert nodes
    invert : StringProperty(default='')

    # Invert toggles
    invert_r_enable : BoolProperty(default=True, update=update_invert_channel)
    invert_g_enable : BoolProperty(default=True, update=update_invert_channel)
    invert_b_enable : BoolProperty(default=True, update=update_invert_channel)
    invert_a_enable : BoolProperty(default=False, update=update_invert_channel)

    # Color Ramp nodes
    color_ramp : StringProperty(default='')
    color_ramp_linear_start : StringProperty(default='')
    color_ramp_linear : StringProperty(default='')
    color_ramp_alpha_multiply : StringProperty(default='')
    color_ramp_mix_rgb : StringProperty(default='')
    color_ramp_mix_alpha : StringProperty(default='')

    # RGB Curve nodes
    rgb_curve : StringProperty(default='')

    # Brightness Contrast nodes
    brightcon : StringProperty(default='')

    brightness_value : FloatProperty(
        name = 'Brightness',
        description = 'Brightness', 
        default=0.0, min=-100.0, max=100.0
    )

    contrast_value : FloatProperty(
        name = 'Contrast',
        description = 'Contrast', 
        default=0.0, min=-100.0, max=100.0
    )

    # Hue Saturation nodes
    huesat : StringProperty(default='')

    huesat_hue_val : FloatProperty(default=0.5, min=0.0, max=1.0, description='Hue')
    huesat_saturation_val : FloatProperty(default=1.0, min=0.0, max=2.0, description='Saturation')
    huesat_value_val : FloatProperty(default=1.0, min=0.0, max=2.0, description='Value')

    # Multiplier nodes (Deprecated)
    multiplier : StringProperty(default='')

    multiplier_r_val : FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_g_val : FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_b_val : FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_a_val : FloatProperty(default=1.0, update=update_multiplier_val_input)

    # Math nodes
    math : StringProperty(default='')

    math_r_val : FloatProperty(default=1.0)
    math_g_val : FloatProperty(default=1.0)
    math_b_val : FloatProperty(default=1.0)
    math_a_val : FloatProperty(default=1.0)

    math_meth : EnumProperty(
        name = 'Method',
        items = math_method_items,
        default = 'MULTIPLY',
        update = update_math_method
    )

    affect_alpha : BoolProperty(name='Affect Alpha', default=False, update=update_affect_alpha) 

    # Individual modifier node frame
    frame : StringProperty(default='')

    # Clamp prop is available in some modifiers
    use_clamp : BoolProperty(name='Use Clamp', default=False, update=update_use_clamp)

    shortcut : BoolProperty(
        name = 'Property Shortcut',
        description = 'Property shortcut on layer list (currently only available on RGB to Intensity)',
        default = False,
        update = update_modifier_shortcut
    )

    expand_content : BoolProperty(default=True)

class YPaintModifierGroupNode(bpy.types.PropertyGroup):
    # Name of the modifier group node
    name : StringProperty(default='')

def check_yp_modifier_linear_nodes(yp):
    for ch in yp.channels:
        check_modifiers_trees(ch)
        
    for layer in yp.layers:
        check_modifiers_trees(layer)
        for ch in layer.channels:
            check_modifiers_trees(ch)
        #for mask in layer.masks:
        #    check_modifiers_trees(mask)

def create_modifier_tree(name):

    # Create modifier tree
    mod_tree = bpy.data.node_groups.new('~yP Modifiers ' + name, 'ShaderNodeTree')

    new_tree_input(mod_tree, 'RGB', 'NodeSocketColor')
    new_tree_input(mod_tree, 'Alpha', 'NodeSocketFloat')
    new_tree_output(mod_tree, 'RGB', 'NodeSocketColor')
    new_tree_output(mod_tree, 'Alpha', 'NodeSocketFloat')

    # New inputs and outputs
    mod_tree_start = mod_tree.nodes.new('NodeGroupInput')
    mod_tree_start.name = MOD_TREE_START
    mod_tree_end = mod_tree.nodes.new('NodeGroupOutput')
    mod_tree_end.name = MOD_TREE_END

    return mod_tree

def check_layer_modifier_tree(layer):

    if layer.source_group != '':
        layer_tree = get_source_tree(layer)
    else: layer_tree = get_tree(layer)

    # Get socket name used by the channel inputs
    socket_names = []
    for ch in layer.channels:
        if not ch.enable: continue
        socket_name = get_channel_input_socket_name(layer, ch)
        #socket_name = ch.socket_input_name
        if socket_name not in socket_names:
            socket_names.append(socket_name)

    num_groups = len(layer.mod_groups)
    num_socs = len(socket_names)

    # Get first group tree
    mod_group = layer_tree.nodes.get(layer.mod_groups[0].name) if num_groups > 0 else None
    mod_tree = mod_group.node_tree if mod_group else None

    if num_socs > 1 and len(layer.modifiers) > 0:
        # Refresh groups
        if num_socs != num_groups:

            if not mod_tree:
                mod_tree = create_modifier_tree(layer.name)

                # Move modifiers to modifier tree
                for mod in layer.modifiers:
                    check_modifier_nodes(mod, mod_tree, layer_tree)

            if num_socs > num_groups:
                # Create new mod groups
                for i in range(num_groups, num_socs):
                    mg = layer.mod_groups.add()
                    mgn = new_node(layer_tree, mg, 'name', 'ShaderNodeGroup', 'modifier_group_' + str(i))
                    mgn.node_tree = mod_tree

            elif num_socs < num_groups:
                # Remove excess mod groups
                for i in reversed(range(num_socs, num_groups)):
                    mg = layer.mod_groups[i]
                    remove_node(layer_tree, mg, 'name')
                    layer.mod_groups.remove(i)

        elif mod_tree:
            # Update modifiers
            for mod in layer.modifiers:
                check_modifier_nodes(mod, mod_tree)

    else:
        if num_groups > 0:

            # Copy modifier nodes into the layer tree
            if mod_tree:
                for mod in layer.modifiers:
                    check_modifier_nodes(mod, layer_tree, mod_tree)

            # Remove mod groups
            if hasattr(layer, 'mod_groups'):
                for mg in layer.mod_groups:
                    remove_node(layer_tree, mg, 'name')
                layer.mod_groups.clear()

        else:
            # Update modifiers
            for mod in layer.modifiers:
                check_modifier_nodes(mod, layer_tree)

def check_modifiers_trees(parent, rearrange=False):
    group_tree = parent.id_data
    yp = group_tree.yp

    enable_tree = False
    is_layer = False

    match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())

    if match1:
        layer = yp.layers[int(match1.group(1))]
        root_ch = yp.channels[int(match1.group(2))]
        ch = parent
        name = root_ch.name + ' ' + layer.name
        if (
            root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and (
                (not ch.override and layer.type not in {'BACKGROUND', 'COLOR', 'OBJECT_INDEX'}) or 
                (ch.override and ch.override_type not in {'DEFAULT'} and ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'})
            )
            ):
            enable_tree = True
        parent_tree = get_tree(layer)

    elif match2:
        layer = parent
        name = layer.name
        check_layer_modifier_tree(layer)
        return
        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'MUSGRAVE'}:
            enable_tree = True
        if layer.source_group != '':
            parent_tree = get_source_tree(layer)
        else: parent_tree = get_tree(layer)
        is_layer=True

    else:
        parent_tree = group_tree

    if len(parent.modifiers) == 0:
        enable_tree = False

    mod_group = None
    if hasattr(parent, 'mod_groups'):
        if len(parent.mod_groups) > 0:
            mod_group = parent_tree.nodes.get(parent.mod_groups[0].name)
    elif hasattr(parent, 'mod_group'):
        mod_group = parent_tree.nodes.get(parent.mod_group)

    if enable_tree:
        if mod_group:
            for mod in parent.modifiers:
                check_modifier_nodes(mod, mod_group.node_tree)
        else:
            enable_modifiers_tree(parent, parent_tree, name, is_layer)
    else:
        if not mod_group:
            for mod in parent.modifiers:
                check_modifier_nodes(mod, parent_tree)
        else:
            disable_modifiers_tree(parent, parent_tree)

    if rearrange:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

def enable_modifiers_tree(parent, parent_tree=None, name='', is_layer=False, rearrange = False):
    
    group_tree = parent.id_data
    yp = group_tree.yp

    if not parent_tree and name == '':
        match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
        match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())

        if match1:
            layer = yp.layers[int(match1.group(1))]
            root_ch = yp.channels[int(match1.group(2))]
            ch = parent
            name = root_ch.name + ' ' + layer.name
            if (layer.type in {'BACKGROUND', 'COLOR', 'OBJECT_INDEX'} and not ch.override) or (ch.override and ch.override_type in {'DEFAULT'}):
                return
            parent_tree = get_tree(layer)
            is_layer=False

        elif match2:
            layer = parent
            name = layer.name
            if layer.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'MUSGRAVE'}:
                return
            if layer.source_group != '':
                parent_tree = get_source_tree(layer)
            else: parent_tree = get_tree(layer)
            is_layer=True

        else:
            return

    if len(parent.modifiers) == 0:
        return 

    if not is_layer:

        # Check if modifier tree already available
        if parent.mod_group != '': 
            return 

        mod_tree = create_modifier_tree(name)

        # Create main modifier group
        mod_group = new_node(parent_tree, parent, 'mod_group', 'ShaderNodeGroup', 'mod_group')
        mod_group.node_tree = mod_tree

        if not is_layer:
            # Create modifier group neighbor
            mod_n = new_node(parent_tree, parent, 'mod_n', 'ShaderNodeGroup', 'mod_n')
            mod_s = new_node(parent_tree, parent, 'mod_s', 'ShaderNodeGroup', 'mod_s')
            mod_e = new_node(parent_tree, parent, 'mod_e', 'ShaderNodeGroup', 'mod_e')
            mod_w = new_node(parent_tree, parent, 'mod_w', 'ShaderNodeGroup', 'mod_w')
            mod_n.node_tree = mod_tree
            mod_s.node_tree = mod_tree
            mod_e.node_tree = mod_tree
            mod_w.node_tree = mod_tree
        else:
            mod_group_1 = new_node(parent_tree, parent, 'mod_group_1', 'ShaderNodeGroup', 'mod_group_1')
            mod_group_1.node_tree = mod_tree

    else:

        # Check number of groups needed
        source = parent_tree.nodes.get(parent.source)
        num_socs = len([outp for outp in source.outputs if outp.enabled])

        #if len(parent.mod_groups) != num_socs:

            # Remove curent mod groups first
            #for mg in parent.mod_groups:
            #    remove_node(parent_tree, mg, 'name')
            #parent.mod_groups.clear()

        mod_tree = create_modifier_tree(name)

        # Create new mod groups
        for i in range(num_socs):
            mg = parent.mod_groups.add()
            mgn = new_node(parent_tree, mg, 'name', 'ShaderNodeGroup', 'modifier_group_' + str(i))
            mgn.node_tree = mod_tree

    for mod in parent.modifiers:
        check_modifier_nodes(mod, mod_tree, parent_tree)

    if rearrange:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

def disable_modifiers_tree(parent, parent_tree=None, rearrange=False):
    group_tree = parent.id_data
    yp = group_tree.yp

    if not parent_tree:

        match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
        match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())

        if match1: 
            layer = yp.layers[int(match1.group(1))]
            root_ch = yp.channels[int(match1.group(2))]

            # Check if fine bump map is still used
            if get_channel_enabled(parent, layer, root_ch) and len(parent.modifiers) > 0 and root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
                if layer.type not in {'BACKGROUND', 'COLOR', 'OBJECT_INDEX'} and not parent.override:
                    return
                if parent.override and parent.override_type != 'DEFAULT':
                    return
            parent_tree = get_tree(layer)

        elif match2:
            layer = parent
            if layer.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'MUSGRAVE'}:
                return
            if layer.source_group != '':
                parent_tree = get_source_tree(layer)
            else: parent_tree = get_tree(layer)

        else:
            return
    
    if not parent_tree: return

    # Get modifier group
    mod_group = parent_tree.nodes.get(parent.mod_group)

    if mod_group:

        # Add new copied modifier nodes into the layer tree
        for mod in parent.modifiers:
            check_modifier_nodes(mod, parent_tree, mod_group.node_tree)

        # Remove modifier tree
        remove_node(parent_tree, parent, 'mod_group')

        # Remove modifier group neighbor
        remove_node(parent_tree, parent, 'mod_n')
        remove_node(parent_tree, parent, 'mod_s')
        remove_node(parent_tree, parent, 'mod_e')
        remove_node(parent_tree, parent, 'mod_w')
        remove_node(parent_tree, parent, 'mod_group_1')

    # Remove mod groups
    if hasattr(parent, 'mod_groups'):
        for mg in parent.mod_groups:
            remove_node(parent_tree, mg, 'name')
        parent.mod_groups.clear()

def register():
    bpy.utils.register_class(YNewYPaintModifier)
    bpy.utils.register_class(YMoveYPaintModifier)
    bpy.utils.register_class(YRemoveYPaintModifier)
    bpy.utils.register_class(YPaintModifier)
    bpy.utils.register_class(YPaintModifierGroupNode)

def unregister():
    bpy.utils.unregister_class(YNewYPaintModifier)
    bpy.utils.unregister_class(YMoveYPaintModifier)
    bpy.utils.unregister_class(YRemoveYPaintModifier)
    bpy.utils.unregister_class(YPaintModifier)
    bpy.utils.unregister_class(YPaintModifierGroupNode)
