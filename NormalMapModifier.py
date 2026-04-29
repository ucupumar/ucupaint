import bpy, re
from bpy.props import *
from .common import *
from .modifier_common import *
from .node_connections import *
from .node_arrangements import *

normalmap_modifier_type_items = (
    ('INVERT', 'Invert', 'Invert', 'MODIFIER', 0),
    ('MATH', 'Math', '', 'MODIFIER', 1),
)

def add_new_normalmap_modifier(ch, layer, modifier_type):
    tree = get_tree(layer)

    name = [mt[1] for mt in normalmap_modifier_type_items if mt[0] == modifier_type][0]

    m = ch.modifiers_1.add()
    m.name = get_unique_name(name, ch.modifiers_1)
    ch.modifiers_1.move(len(ch.modifiers_1)-1, 0)
    shift_normal_modifier_fcurves_down(ch)
    m = ch.modifiers_1[0]
    m.type = modifier_type

    check_modifier_nodes(m, tree)

class YNewNormalmapModifier(bpy.types.Operator):
    bl_idname = "wm.y_new_normalmap_modifier"
    bl_label = "New Normal Map Modifier"
    bl_description = "New Normal Map Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = normalmap_modifier_type_items,
        default = 'INVERT'
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent')

    def execute(self, context):

        yp = context.parent.id_data.yp
        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if not match: 
            self.report({'ERROR'}, "Wrong context!")
            return {'CANCELLED'}
        layer = yp.layers[int(match.group(1))]
        ch_idx = int(match.group(2))
        ch = layer.channels[ch_idx]
        root_ch = yp.channels[ch_idx]

        add_new_normalmap_modifier(ch, layer, self.type)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        # Update UI
        ypui = context.window_manager.ypui
        ypui.layer_ui.channels[ch_idx].expand_content = True
        ypui.need_update = True

        return {'FINISHED'}

class YMoveNormalMapModifier(bpy.types.Operator):
    bl_idname = "wm.y_move_normalmap_modifier"
    bl_label = "Move " + get_addon_title() + " Modifier"
    bl_description = "Move " + get_addon_title() + " Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
        name = 'Direction',
        items = (
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        ),
        default = 'UP'
    )

    @classmethod
    def poll(cls, context):
        return (
            get_active_ypaint_node() and 
            hasattr(context, 'parent') and
            hasattr(context, 'modifier')
        )

    def execute(self, context):
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp

        parent = context.parent

        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
        if not match: 
            self.report({'ERROR'}, "Wrong context!")
            return {'CANCELLED'}
        layer = yp.layers[int(match.group(1))]

        num_mods = len(parent.modifiers_1)
        if num_mods < 2: return {'CANCELLED'}

        mod = context.modifier
        index = -1
        for i, m in enumerate(parent.modifiers_1):
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

        # Swap modifier
        parent.modifiers_1.move(index, new_index)
        swap_normal_modifier_fcurves(parent, index, new_index)

        # Rearrange nodes
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YRemoveNormalMapModifier(bpy.types.Operator):
    bl_idname = "wm.y_remove_normalmap_modifier"
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

        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
        if not match: 
            self.report({'ERROR'}, "Wrong context!")
            return {'CANCELLED'}
        layer = yp.layers[int(match.group(1))]
        tree = get_tree(layer)

        index = -1
        for i, m in enumerate(parent.modifiers_1):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        if len(parent.modifiers_1) < 1: return {'CANCELLED'}

        # Remove modifier fcurves first
        remove_entity_fcurves(parent)
        shift_normal_modifier_fcurves_up(parent, index)

        # Delete the nodes
        delete_modifier_nodes(tree, mod)

        # Delete the modifier
        parent.modifiers_1.remove(index)

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

def update_invert_channel(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    invert = tree.nodes.get(self.invert)

    invert.inputs[2].default_value = 1.0 if self.invert_r_enable and self.enable else 0.0
    invert.inputs[3].default_value = 1.0 if self.invert_g_enable and self.enable else 0.0
    invert.inputs[4].default_value = 1.0 if self.invert_b_enable and self.enable else 0.0
    invert.inputs[5].default_value = 1.0 if self.invert_a_enable and self.enable else 0.0

def update_math_val_input(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    if self.type == 'MATH':
        math = tree.nodes.get(self.math)
        math.inputs[2].default_value = self.math_r_val if self.enable else 0.0
        math.inputs[3].default_value = self.math_g_val if self.enable else 0.0
        math.inputs[4].default_value = self.math_b_val if self.enable else 0.0
        math.inputs[5].default_value = self.math_a_val if self.enable else 0.0

def update_math_method(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    if self.type == 'MATH':
        math = tree.nodes.get(self.math)
        math.node_tree.nodes.get('Math.R').operation = self.math_meth
        math.node_tree.nodes.get('Math.G').operation = self.math_meth
        math.node_tree.nodes.get('Math.B').operation = self.math_meth
        math.node_tree.nodes.get('Math.A').operation = self.math_meth

def update_use_clamp(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    math = tree.nodes.get(self.math)
    math.node_tree.nodes.get('Math.R').use_clamp = self.use_clamp
    math.node_tree.nodes.get('Math.A').use_clamp = self.use_clamp
    math.node_tree.nodes.get('Math.G').use_clamp = self.use_clamp
    math.node_tree.nodes.get('Math.B').use_clamp = self.use_clamp

def update_affect_alpha(self, context):
    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    if self.type == 'MATH':
        math = tree.nodes.get(self.math).node_tree
        alpha = math.nodes.get('Mix.A')
        if self.affect_alpha:
            alpha.mute = False
        else:
            alpha.mute = True

def update_normalmap_modifier_enable(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    check_modifier_nodes(self, tree)
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

class YNormalMapModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_normalmap_modifier_enable)
    name = StringProperty(default='')

    type = EnumProperty(
        name = 'Modifier Type',
        items = normalmap_modifier_type_items,
        default = 'INVERT'
    )

    # Invert toggles
    invert_r_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_g_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_b_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_a_enable = BoolProperty(default=False, update=update_invert_channel)

    math_r_val = FloatProperty(default=1.0, update=update_math_val_input)
    math_g_val = FloatProperty(default=1.0, update=update_math_val_input)
    math_b_val = FloatProperty(default=1.0, update=update_math_val_input)
    math_a_val = FloatProperty(default=1.0, update=update_math_val_input)

    math_meth = EnumProperty(
        name = 'Method',
        items = math_method_items,
        default = "MULTIPLY",
        update = update_math_method
    )

    affect_alpha = BoolProperty(name='Affect Alpha', default=False, update=update_affect_alpha) 
    use_clamp = BoolProperty(name='Use Clamp', default=False, update=update_use_clamp)

    #ramp = StringProperty(default='')
    #ramp_mix = StringProperty(default='')
    invert = StringProperty(default='')
    math = StringProperty(default='')
    #curve = StringProperty(default='')

    # UI
    expand_content = BoolProperty(default=True)

def register():
    bpy.utils.register_class(YNewNormalmapModifier)
    bpy.utils.register_class(YMoveNormalMapModifier)
    bpy.utils.register_class(YRemoveNormalMapModifier)
    bpy.utils.register_class(YNormalMapModifier)

def unregister():
    bpy.utils.unregister_class(YNewNormalmapModifier)
    bpy.utils.unregister_class(YMoveNormalMapModifier)
    bpy.utils.unregister_class(YRemoveNormalMapModifier)
    bpy.utils.unregister_class(YNormalMapModifier)
