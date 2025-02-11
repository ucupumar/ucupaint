import bpy, re
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *

mask_modifier_type_items = (
    ('INVERT', 'Invert', 'Invert', 'MODIFIER', 0),
    ('RAMP', 'Ramp', '', 'MODIFIER', 1),
    ('CURVE', 'Curve', '', 'MODIFIER', 2),
)

mask_modifier_type_labels = {
    'INVERT' : 'Invert',
    'RAMP' : 'Ramp',
    'CURVE' : 'Curve',
}

can_be_expanded = {
    'RAMP',
    'CURVE',
}

def update_mask_modifier_enable(self, context):

    yp = self.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    mod = self

    tree = get_mask_tree(mask)

    if mod.type == 'INVERT':
        invert = tree.nodes.get(mod.invert)
        if invert:
            invert.mute = not mod.enable
            invert.inputs[0].default_value = 1.0 if mod.enable else 0.0

    elif mod.type == 'RAMP':

        ramp_mix = tree.nodes.get(mod.ramp_mix)
        if ramp_mix:
            ramp_mix.mute = not mod.enable
            #ramp_mix.inputs[0].default_value = 1.0 if mod.enable else 0.0

    elif mod.type == 'CURVE':

        curve = tree.nodes.get(mod.curve)
        if curve:
            curve.mute = not mod.enable
            #curve.inputs[0].default_value = 1.0 if mod.enable else 0.0

def add_modifier_nodes(mod, tree, ref_tree=None):

    # Create the nodes
    if mod.type == 'INVERT':
        if ref_tree:
            invert_ref = ref_tree.nodes.get(mod.invert)

        invert = new_node(tree, mod, 'invert', 'ShaderNodeInvert', 'Invert')

        if ref_tree:
            copy_node_props(invert_ref, invert)
            ref_tree.nodes.remove(invert_ref)

    elif mod.type == 'RAMP':
        if ref_tree:
            ramp_ref = ref_tree.nodes.get(mod.ramp)
            ramp_mix_ref = ref_tree.nodes.get(mod.ramp_mix)

        ramp = new_node(tree, mod, 'ramp', 'ShaderNodeValToRGB', 'Ramp')
        ramp_mix = new_mix_node(tree, mod, 'ramp_mix', 'Ramp Mix', 'FLOAT')

        if ref_tree:
            copy_node_props(ramp_ref, ramp)
            copy_node_props(ramp_mix_ref, ramp_mix)

            ref_tree.nodes.remove(ramp_ref)
            ref_tree.nodes.remove(ramp_mix_ref)
        else:
            ramp_mix.inputs[0].default_value = 1.0

    elif mod.type == 'CURVE':
        if ref_tree:
            curve_ref = ref_tree.nodes.get(mod.curve)

        curve = new_node(tree, mod, 'curve', 'ShaderNodeRGBCurve', 'Curve')

        if ref_tree:
            copy_node_props(curve_ref, curve)

            ref_tree.nodes.remove(curve_ref)

def delete_modifier_nodes(tree, mod):

    if mod.type == 'INVERT':
        remove_node(tree, mod, 'invert')

    elif mod.type == 'RAMP':
        remove_node(tree, mod, 'ramp')
        remove_node(tree, mod, 'ramp_mix')

    elif mod.type == 'CURVE':
        remove_node(tree, mod, 'curve')

def add_new_mask_modifier(mask, modifier_type):
    tree = get_mask_tree(mask)

    name = [mt[1] for mt in mask_modifier_type_items if mt[0] == modifier_type][0]

    m = mask.modifiers.add()
    m.name = get_unique_name(name, mask.modifiers)
    m.type = modifier_type

    add_modifier_nodes(m, tree)

def draw_modifier_properties(tree, m, layout):

    if m.type == 'RAMP':
        ramp = tree.nodes.get(m.ramp)
        layout.template_color_ramp(ramp, "color_ramp", expand=True)

    elif m.type == 'CURVE':
        curve = tree.nodes.get(m.curve)
        curve.draw_buttons_ext(bpy.context, layout)

class YNewMaskModifier(bpy.types.Operator):
    bl_idname = "wm.y_new_mask_modifier"
    bl_label = "New Mask Modifier"
    bl_description = "New Mask Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = mask_modifier_type_items,
        default = 'INVERT'
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'layer')

    def execute(self, context):

        match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', context.mask.path_from_id())
        mask_idx = int(match.group(2))

        add_new_mask_modifier(context.mask, self.type)

        rearrange_layer_nodes(context.layer)
        reconnect_layer_nodes(context.layer)

        # Update UI
        ypui = context.window_manager.ypui
        ypui.layer_ui.masks[mask_idx].expand_content = True
        ypui.need_update = True

        return {'FINISHED'}

class YMoveMaskModifier(bpy.types.Operator):
    bl_idname = "wm.y_move_mask_modifier"
    bl_label = "Move Mask Modifier"
    bl_description = "Move Mask Modifier"
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
        return hasattr(context, 'mask') and hasattr(context, 'modifier') and hasattr(context, 'layer')

    def execute(self, context):

        layer = context.layer
        mask = context.mask
        mod = context.modifier

        num_mods = len(mask.modifiers)
        if num_mods < 2: return {'CANCELLED'}

        index = -1
        for i, m in enumerate(mask.modifiers):
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
        mask.modifiers.move(index, new_index)

        # Reconnect modifier nodes
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YRemoveMaskModifier(bpy.types.Operator):
    bl_idname = "wm.y_remove_mask_modifier"
    bl_label = "Remove Mask Modifier"
    bl_description = "Remove Mask Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer') and hasattr(context, 'mask') and hasattr(context, 'modifier') 

    def execute(self, context):

        layer = context.layer
        mask = context.mask
        mod = context.modifier
        tree = get_mask_tree(mask)

        index = -1
        for i, m in enumerate(mask.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        delete_modifier_nodes(tree, context.modifier)

        mask.modifiers.remove(index)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        # Update UI
        context.window_manager.ypui.need_update = True

        return {'FINISHED'}

class YMaskModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(
        name = 'Enable Modifier',
        description = 'Enable modifier',
        default = True,
        update = update_mask_modifier_enable
    )

    name = StringProperty(default='')

    type = EnumProperty(
        name = 'Modifier Type',
        items = mask_modifier_type_items,
        default = 'INVERT'
    )

    ramp = StringProperty(default='')
    ramp_mix = StringProperty(default='')
    invert = StringProperty(default='')
    curve = StringProperty(default='')

    # UI
    expand_content = BoolProperty(default=True)

def register():
    bpy.utils.register_class(YNewMaskModifier)
    bpy.utils.register_class(YMoveMaskModifier)
    bpy.utils.register_class(YRemoveMaskModifier)
    bpy.utils.register_class(YMaskModifier)

def unregister():
    bpy.utils.unregister_class(YNewMaskModifier)
    bpy.utils.unregister_class(YMoveMaskModifier)
    bpy.utils.unregister_class(YRemoveMaskModifier)
    bpy.utils.unregister_class(YMaskModifier)
