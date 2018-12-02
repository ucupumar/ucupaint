import bpy, re
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *

mask_modifier_type_items = (
        ('INVERT', 'Invert', 'Invert', 'MODIFIER', 0),
        ('RAMP', 'Ramp', '', 'MODIFIER', 1),
        )

can_be_expanded = {
        'RAMP',
        }

def update_mask_modifier_enable(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.layers\[(\d+)\]\.masks\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    layer = tl.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    mod = self

    tree = get_mask_tree(mask)

    if mod.type == 'INVERT':
        invert = tree.nodes.get(mod.invert)
        if invert:
            #invert.mute = not mod.enable
            invert.inputs[0].default_value = 1.0 if mod.enable else 0.0

    elif mod.type == 'RAMP':

        ramp_mix = tree.nodes.get(mod.ramp_mix)
        if ramp_mix:
            #ramp_mix.mute = not mod.enable
            ramp_mix.inputs[0].default_value = 1.0 if mod.enable else 0.0

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
        ramp_mix = new_node(tree, mod, 'ramp_mix', 'ShaderNodeMixRGB', 'Ramp Mix')

        if ref_tree:
            copy_node_props(ramp_ref, ramp)
            copy_node_props(ramp_mix_ref, ramp_mix)

            ref_tree.nodes.remove(ramp_ref)
            ref_tree.nodes.remove(ramp_mix_ref)
        else:
            ramp_mix.inputs[0].default_value = 1.0

def delete_modifier_nodes(tree, mod):

    if mod.type == 'INVERT':
        remove_node(tree, mod, 'invert')

    elif mod.type == 'RAMP':
        remove_node(tree, mod, 'ramp')
        remove_node(tree, mod, 'ramp_mix')

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

class YNewMaskModifier(bpy.types.Operator):
    bl_idname = "node.y_new_mask_modifier"
    bl_label = "New Mask Modifier"
    bl_description = "New Mask Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = mask_modifier_type_items,
        default = 'INVERT')

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'texture')

    def execute(self, context):

        #print('Owowowow', self.type)
        add_new_mask_modifier(context.mask, self.type)

        rearrange_tex_nodes(context.texture)
        reconnect_tex_nodes(context.texture)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YMoveMaskModifier(bpy.types.Operator):
    bl_idname = "node.y_move_mask_modifier"
    bl_label = "Move Mask Modifier"
    bl_description = "Move Mask Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'modifier') and hasattr(context, 'texture')

    def execute(self, context):

        layer = context.texture
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
        rearrange_tex_nodes(layer)
        reconnect_tex_nodes(layer)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YRemoveMaskModifier(bpy.types.Operator):
    bl_idname = "node.y_remove_mask_modifier"
    bl_label = "Remove Mask Modifier"
    bl_description = "Remove Mask Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'texture') and hasattr(context, 'mask') and hasattr(context, 'modifier') 

    def execute(self, context):

        layer = context.texture
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

        rearrange_tex_nodes(layer)
        reconnect_tex_nodes(layer)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YMaskModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_mask_modifier_enable)
    name = StringProperty(default='')

    type = EnumProperty(
        name = 'Modifier Type',
        items = mask_modifier_type_items,
        default = 'INVERT')

    ramp = StringProperty(default='')
    ramp_mix = StringProperty(default='')
    invert = StringProperty(default='')

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
