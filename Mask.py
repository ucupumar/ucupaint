import bpy, re
from bpy.props import *
from . import lib
from .common import *
from .node_connections import *
from .node_arrangements import *

def add_new_mask(tex, name, mask_type, texcoord_type, uv_name, image = None):
    tl = tex.id_data.tl
    tl.halt_update = True

    tree = get_tree(tex)
    nodes = tree.nodes

    mask = tex.masks.add()
    mask.name = name
    mask.type = mask_type
    mask.texcoord_type = texcoord_type

    source = new_node(tree, mask, 'source', texture_node_bl_idnames[mask_type], 'Mask Source')
    if image:
        source.image = image
        source.color_space = 'NONE'

    uv_map = new_node(tree, mask, 'uv_map', 'ShaderNodeUVMap', 'Mask UV Map')
    uv_map.uv_map = uv_name
    mask.uv_name = uv_name

    final = new_node(tree, mask, 'final', 'NodeReroute', 'Mask Final')

    # Check if there's any link all masks on
    link_all_masks = False
    norm_ch = None
    for i, ch in enumerate(tex.channels):
        root_ch = tl.channels[i]
        if root_ch.type == 'NORMAL' and ch.intensity_multiplier_link and ch.im_link_all_masks:
            norm_ch = ch
            link_all_masks = True

    for i, root_ch in enumerate(tl.channels):
        ch = tex.channels[i]
        c = mask.channels.add()

        multiply = new_node(tree, c, 'multiply', 'ShaderNodeMath', 'Mask Multiply')
        multiply.operation = 'MULTIPLY'

        if root_ch.type == 'NORMAL' or link_all_masks:
            intensity_multiplier = new_node(tree, c, 'intensity_multiplier', 'ShaderNodeGroup', 'Mask Intensity Multiplier')
            intensity_multiplier.node_tree = lib.get_node_tree_lib(lib.INTENSITY_MULTIPLIER)
            if norm_ch:
                intensity_multiplier.inputs[1].default_value = norm_ch.intensity_multiplier_value
                if ch != norm_ch:
                    if norm_ch.im_invert_others:
                        intensity_multiplier.inputs[2].default_value = 1.0
                    if norm_ch.im_sharpen:
                        intensity_multiplier.inputs[3].default_value = 1.0
            else: intensity_multiplier.inputs[1].default_value = ch.intensity_multiplier_value

    tl.halt_update = False

    return mask

def remove_mask(tex, mask):

    tree = get_tree(tex)

    # Remove mask nodes
    if mask.tree:
        remove_node(mask.tree, mask, 'source')
        remove_node(tree, mask, 'group_node')
    else: 
        remove_node(tree, mask, 'source')
        remove_node(tree, mask, 'hardness')

    remove_node(tree, mask, 'uv_map')
    remove_node(tree, mask, 'final')

    # Remove mask channel nodes
    for c in mask.channels:

        # Bump related
        remove_node(tree, c, 'neighbor_uv')
        remove_node(tree, c, 'source_n')
        remove_node(tree, c, 'source_s')
        remove_node(tree, c, 'source_e')
        remove_node(tree, c, 'source_w')
        remove_node(tree, c, 'fine_bump')
        remove_node(tree, c, 'invert')
        remove_node(tree, c, 'intensity_multiplier')
        remove_node(tree, c, 'vector_intensity_multiplier')
        remove_node(tree, c, 'vector_mix')

        # Ramp related
        remove_node(tree, c, 'ramp')
        remove_node(tree, c, 'ramp_multiply')
        remove_node(tree, c, 'ramp_subtract')
        remove_node(tree, c, 'ramp_intensity')
        remove_node(tree, c, 'ramp_mix')

        # Multiply
        remove_node(tree, c, 'multiply')

    # Remove mask
    for i, m in enumerate(tex.masks):
        if m == mask:
            tex.masks.remove(i)
            break

class YNewTextureMask(bpy.types.Operator):
    bl_idname = "node.y_new_texture_mask"
    bl_label = "New Texture Mask"
    bl_description = "New Texture Mask"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Mask Type',
            items = texture_type_items,
            default = 'IMAGE')

    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)

    color_option = EnumProperty(
            name = 'Color Option',
            description = 'Color Option',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='WHITE')

    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_name = StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):

        # HACK: For some reason, checking context.texture on poll will cause problem
        # This method below is to get around that
        self.auto_cancel = False
        if not hasattr(context, 'texture'):
            self.auto_cancel = True
            return self.execute(context)

        obj = context.object
        self.texture = context.texture
        tex = context.texture

        name = tex.name
        if self.type != 'IMAGE':
            name += ' ' + [i[1] for i in texture_type_items if i[0] == self.type][0]
            items = tex.masks
        else:
            items = bpy.data.images
        name = 'Mask ' + name

        self.name = get_unique_name(name, items)

        if obj.type != 'MESH':
            self.texcoord_type = 'Generated'
        elif len(obj.data.uv_layers) > 0:
            # Use active uv layer name by default
            self.uv_name = obj.data.uv_layers.active.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        row = self.layout.split(percentage=0.4)
        col = row.column(align=False)
        col.label('Name:')
        if self.type == 'IMAGE':
            col.label('Width:')
            col.label('Height:')
            col.label('Color:')
            col.label('')
        col.label('Vector:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'IMAGE':
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')
            col.prop(self, 'color_option', text='')
            col.prop(self, 'hdr')

        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

    def execute(self, context):
        if self.auto_cancel: return {'CANCELLED'}

        tlui = context.window_manager.tlui
        tex = self.texture

        # Check if texture with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        else: same_name = [m for m in tex.masks if m.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
            else: self.report({'ERROR'}, "Mask named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        alpha = False
        img = None
        if self.type == 'IMAGE':
            img = bpy.data.images.new(self.name, self.width, self.height, alpha, self.hdr)
            if self.color_option == 'WHITE':
                img.generated_color = (1,1,1,1)
            elif self.color_option == 'BLACK':
                img.generated_color = (0,0,0,1)
            img.use_alpha = False
        mask = add_new_mask(tex, self.name, self.type, self.texcoord_type, self.uv_name, img)

        # Enable edit mask
        if self.type == 'IMAGE':
            mask.active_edit = True

        reconnect_tex_nodes(tex)
        rearrange_tex_nodes(tex)

        tlui.tex_ui.expand_masks = True
        tlui.need_update = True

        return {'FINISHED'}

class YRemoveTextureMask(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_mask"
    bl_label = "Remove Texture Mask"
    bl_description = "Remove Texture Mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'texture')

    def execute(self, context):
        mask = context.mask
        tex = context.texture
        tree = get_tree(tex)

        remove_mask(tex, mask)

        reconnect_tex_nodes(tex)
        rearrange_tex_nodes(tex)

        # Seach for active edit mask
        found_active_edit = False
        for m in tex.masks:
            if m.active_edit:
                found_active_edit = True
                break

        # Use texture image as active image if active edit mask not found
        if not found_active_edit:
            if tex.type == 'IMAGE':
                if tex.source_tree:
                    source = tex.source_tree.nodes.get(tex.source)
                else: source = tree.nodes.get(tex.source)
                update_image_editor_image(context, source.image)
            else:
                update_image_editor_image(context, None)

        # Refresh viewport and image editor
        for area in bpy.context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

def update_mask_active_edit(self, context):
    if self.halt_update: return

    # Only image mask can be edited
    if self.active_edit and self.type != 'IMAGE':
        self.halt_update = True
        self.active_edit = False
        self.halt_update = False
        return

    tl = self.id_data.tl

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex_idx = int(match.group(1))
    tex = tl.textures[int(match.group(1))]
    mask_idx = int(match.group(2))

    if self.active_edit: 
        for m in tex.masks:
            if m == self: continue
            m.halt_update = True
            m.active_edit = False
            m.halt_update = False

    # Refresh
    tl.active_texture_index = tex_idx

def update_enable_texture_masks(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    tex = self
    tree = get_tree(tex)
    for mask in tex.masks:
        for ch in mask.channels:
            multiply = tree.nodes.get(ch.multiply)
            multiply.mute = not ch.enable or not mask.enable or not tex.enable_masks

def update_tex_mask_channel_enable(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    mask = tl.textures[int(match.group(2))]

    multiply = tree.nodes.get(self.multiply)
    multiply.mute = not self.enable or not mask.enable or not tex.enable_masks

def update_tex_mask_enable(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    for ch in self.channels:
        multiply = tree.nodes.get(ch.multiply)
        multiply.mute = not ch.enable or not self.enable or not tex.enable_masks

        vector_mix = tree.nodes.get(ch.vector_mix)
        if vector_mix:
            vector_mix.mute = not ch.enable or not self.enable or not tex.enable_masks

def update_mask_texcoord_type(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]

    reconnect_tex_nodes(tex)

def update_mask_uv_name(self, context):
    obj = context.object
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    
    uv_map = tree.nodes.get(self.uv_map)
    uv_map.uv_map = self.uv_name

    # Update uv layer
    if self.active_edit and obj.type == 'MESH':
        for i, uv in enumerate(obj.data.uv_layers):
            if uv.name == self.uv_name:
                if obj.data.uv_layers.active_index != i:
                    obj.data.uv_layers.active_index = i
                break

def update_mask_hardness_enable(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]

    if self.tree: 
        tree = get_tree(self)
    else: tree = get_tree(tex)

    hardness = tree.nodes.get(self.hardness)

    if self.enable_hardness and not hardness:
        hardness = new_node(tree, self, 'hardness', 'ShaderNodeGroup', 'Mask Hardness')
        hardness.node_tree = lib.get_node_tree_lib(lib.MOD_INTENSITY_HARDNESS)
        hardness.inputs[1].default_value = self.hardness_value
    if not self.enable_hardness and hardness:
        remove_node(tree, self, 'hardness')

    reconnect_tex_nodes(tex)
    rearrange_tex_nodes(tex)

def update_mask_hardness_value(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]

    if self.tree:
        hardness = self.tree.nodes.get(self.hardness)
    else: 
        tex_tree = get_tree(tex)
        hardness = tex_tree.nodes.get(self.hardness)

    if hardness:
        hardness.inputs[1].default_value = self.hardness_value

def update_mask_bump_height(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    fine_bump = tree.nodes.get(self.fine_bump)

    if fine_bump:
        fine_bump.inputs[0].default_value = self.bump_height

def update_mask_ramp_intensity_value(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = tex.channels[int(match.group(3))]
    tree = get_tree(tex)

    ramp_intensity = tree.nodes.get(self.ramp_intensity)
    ramp_intensity.inputs[1].default_value = ch.intensity_value * self.ramp_intensity_value

def update_mask_ramp_blend_type(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    ramp_mix = tree.nodes.get(self.ramp_mix)
    ramp_mix.blend_type = self.ramp_blend_type

def update_mask_enable_ramp(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    mask = tex.masks[int(match.group(2))]
    ch = tex.channels[int(match.group(3))]

    tree = get_tree(tex)

    if self.enable_ramp:

        ramp = tree.nodes.get(self.ramp)
        ramp_multiply = tree.nodes.get(self.ramp_multiply)
        ramp_subtract = tree.nodes.get(self.ramp_subtract)
        ramp_intensity = tree.nodes.get(self.ramp_intensity)
        ramp_mix = tree.nodes.get(self.ramp_mix)

        if not ramp:
            ramp = new_node(tree, self, 'ramp', 'ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color = (1,1,1,1)
            ramp.color_ramp.elements[1].color = (0.5,0.5,0.5,1)
        if not ramp_multiply:
            ramp_multiply = new_node(tree, self, 'ramp_multiply', 'ShaderNodeMath')
            ramp_multiply.operation = 'MULTIPLY'
        if not ramp_subtract:
            ramp_subtract = new_node(tree, self, 'ramp_subtract', 'ShaderNodeMath')
            ramp_subtract.operation = 'SUBTRACT'
            ramp_subtract.use_clamp = True
        if not ramp_intensity:
            ramp_intensity = new_node(tree, self, 'ramp_intensity', 'ShaderNodeMath')
            ramp_intensity.operation = 'MULTIPLY'
            ramp_intensity.inputs[1].default_value = ch.intensity_value * self.ramp_intensity_value
        if not ramp_mix:
            #ramp_mix = new_node(tree, self, 'ramp_mix', 'ShaderNodeGroup')
            #ramp_mix.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER)
            ramp_mix = new_node(tree, self, 'ramp_mix', 'ShaderNodeMixRGB')
            ramp_mix.blend_type = self.ramp_blend_type
    else:
        remove_node(tree, self, 'ramp_multiply')
        remove_node(tree, self, 'ramp_subtract')
        remove_node(tree, self, 'ramp_intensity')
        remove_node(tree, self, 'ramp_mix')

    reconnect_tex_nodes(tex)
    rearrange_tex_nodes(tex)

def update_mask_bump_enable(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    mask = tex.masks[int(match.group(2))]
    ch = tex.channels[int(match.group(3))]

    tree = get_tree(tex)

    directions = ['n', 's', 'e', 'w']

    if self.enable_bump:
        enable_mask_source(tex, mask, False)

        neighbor_uv = tree.nodes.get(self.neighbor_uv)
        fine_bump = tree.nodes.get(self.fine_bump)
        invert = tree.nodes.get(self.invert)
        intensity_multiplier = tree.nodes.get(self.intensity_multiplier)
        vector_intensity_multiplier = tree.nodes.get(self.vector_intensity_multiplier)
        vector_mix = tree.nodes.get(self.vector_mix)

        if not neighbor_uv:
            neighbor_uv = new_node(tree, self, 'neighbor_uv', 'ShaderNodeGroup', 'Mask Neighbor UV')
            neighbor_uv.node_tree = lib.get_node_tree_lib(lib.NEIGHBOR_UV)
            if mask.type == 'IMAGE':
                src = mask.tree.nodes.get(mask.source)
                neighbor_uv.inputs[1].default_value = src.image.size[0]
                neighbor_uv.inputs[2].default_value = src.image.size[1]
            else:
                neighbor_uv.inputs[1].default_value = 1000
                neighbor_uv.inputs[2].default_value = 1000

        if not fine_bump:
            fine_bump = new_node(tree, self, 'fine_bump', 'ShaderNodeGroup', 'Mask Fine Bump')
            fine_bump.node_tree = lib.get_node_tree_lib(lib.FINE_BUMP)
            #fine_bump.inputs[0].default_value = ch.fine_bump_scale
            fine_bump.inputs[0].default_value = self.bump_height

        if not invert:
            invert = new_node(tree, self, 'invert', 'ShaderNodeInvert', 'Mask Bump Invert')

        if not vector_intensity_multiplier:
            vector_intensity_multiplier = new_node(tree, self, 'vector_intensity_multiplier', 
                    'ShaderNodeGroup', 'Mask Vector Intensity Multiplier')
            vector_intensity_multiplier.node_tree = lib.get_node_tree_lib(lib.INTENSITY_MULTIPLIER)
            vector_intensity_multiplier.inputs[1].default_value = ch.intensity_multiplier_value

        if not vector_mix:
            vector_mix = new_node(tree, self, 'vector_mix', 'ShaderNodeGroup', 'Mask Vector Mix')
            vector_mix.node_tree = lib.get_node_tree_lib(lib.VECTOR_MIX)

        if not intensity_multiplier:
            intensity_multiplier = new_node(tree, self, 'intensity_multiplier', 
                    'ShaderNodeGroup', 'Mask Intensity Multiplier')
            intensity_multiplier.node_tree = lib.get_node_tree_lib(lib.INTENSITY_MULTIPLIER)
            intensity_multiplier.inputs[1].default_value = ch.intensity_multiplier_value

        for d in directions:
            src = tree.nodes.get(getattr(self, 'source_' + d))
            if not src:
                src = new_node(tree, self, 'source_' + d, 'ShaderNodeGroup', 'Mask_' + d)
                src.node_tree = mask.tree
                src.hide = True

    else:
        disable_mask_source(tex, mask)

        remove_node(tree, self, 'neighbor_uv')
        remove_node(tree, self, 'fine_bump')
        remove_node(tree, self, 'invert')
        #remove_node(tree, self, 'intensity_multiplier')
        remove_node(tree, self, 'vector_intensity_multiplier')
        remove_node(tree, self, 'vector_mix')

        for d in directions:
            remove_node(tree, self, 'source_' + d)

    # Reconnect outside nodes
    reconnect_tex_nodes(tex)

    # Rearrange nodes
    rearrange_tex_nodes(tex)

def enable_mask_source(tex, mask, reconnect_and_rearrange = True):

    # Check if source tree is already available
    if mask.tree: return

    tex_tree = get_tree(tex)

    # Get current source for reference
    source_ref = tex_tree.nodes.get(mask.source)
    hardness_ref = tex_tree.nodes.get(mask.hardness)

    # Create mask tree
    mask.tree = bpy.data.node_groups.new(MASKGROUP_PREFIX + mask.name, 'ShaderNodeTree')

    # Create input and outputs
    mask.tree.inputs.new('NodeSocketVector', 'Vector')
    #mask.tree.outputs.new('NodeSocketColor', 'Color')
    mask.tree.outputs.new('NodeSocketFloat', 'Value')

    start = mask.tree.nodes.new('NodeGroupInput')
    start.name = MASK_TREE_START
    end = mask.tree.nodes.new('NodeGroupOutput')
    end.name = MASK_TREE_END

    # Copy nodes from reference
    source = new_node(mask.tree, mask, 'source', source_ref.bl_idname)
    copy_node_props(source_ref, source)

    hardness = None
    if hardness_ref:
        hardness = new_node(mask.tree, mask, 'hardness', hardness_ref.bl_idname)
        copy_node_props(hardness_ref, hardness)

    # Create source node group
    group_node = new_node(tex_tree, mask, 'group_node', 'ShaderNodeGroup')
    group_node.node_tree = mask.tree

    # Remove previous nodes
    tex_tree.nodes.remove(source_ref)
    if hardness_ref:
        tex_tree.nodes.remove(hardness_ref)

    if reconnect_and_rearrange:
        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def disable_mask_source(tex, mask):

    # Check if source tree is already gone
    if not mask.tree: return

    tex_tree = get_tree(tex)

    source_ref = mask.tree.nodes.get(mask.source)
    hardness_ref = mask.tree.nodes.get(mask.hardness)
    group_node = tex_tree.nodes.get(mask.group_node)

    # Create new nodes
    source = new_node(tex_tree, mask, 'source', source_ref.bl_idname)
    copy_node_props(source_ref, source)

    if hardness_ref:
        hardness = new_node(tex_tree, mask, 'hardness', hardness_ref.bl_idname)
        copy_node_props(hardness_ref, hardness)

    # Remove previous source
    #remove_node(mask.tree, mask, 'source')
    #remove_node(mask.tree, mask, 'hardness')
    remove_node(tex_tree, mask, 'group_node')
    bpy.data.node_groups.remove(mask.tree)
    mask.tree = None

    # Reconnect outside nodes
    reconnect_tex_nodes(tex)

    # Rearrange nodes
    rearrange_tex_nodes(tex)

class YTextureMaskChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_tex_mask_channel_enable)

    intensity_multiplier = StringProperty(default='')
    multiply = StringProperty(default='')

    enable_bump = BoolProperty(default=False, update=update_mask_bump_enable)
    bump_height = FloatProperty(default=4.0, update=update_mask_bump_height)
    bump_type = EnumProperty(
            items = (
                ('BUMP_MULTIPLY', 'Bump Multiply', ''),
                ('NORMAL_MIX', ' Normal Mix', ''),
                ),
            default='NORMAL_MIX')

    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')
    neighbor_uv = StringProperty(default='')
    fine_bump = StringProperty(default='')
    invert = StringProperty(default='')
    vector_intensity_multiplier = StringProperty(default='')
    vector_mix = StringProperty(default='')

    # Color Ramp
    enable_ramp = BoolProperty(default=False, update=update_mask_enable_ramp)
    ramp_blend_type = EnumProperty(
        name = 'Ramp Blend',
        description = 'Ramp Blend type',
        items = blend_type_items,
        default = 'MIX',
        update=update_mask_ramp_blend_type)

    ramp_intensity_value = FloatProperty(
        name = 'Ramp Intensity',
        description = 'Ramp Intensity',
        default=1.0, min=0.0, max=1.0, subtype='FACTOR', unit='NONE',
        update = update_mask_ramp_intensity_value)

    # Ramp nodes
    ramp = StringProperty(default='')
    ramp_multiply = StringProperty(default='')
    ramp_subtract = StringProperty(default='')
    ramp_intensity = StringProperty(default='')
    ramp_mix = StringProperty(default='')

class YTextureMask(bpy.types.PropertyGroup):

    halt_update = BoolProperty(default=False)
    
    tree = PointerProperty(type=bpy.types.ShaderNodeTree)
    group_node = StringProperty(default='')

    enable = BoolProperty(
            name='Enable Mask', 
            description = 'Enable Mask',
            default=True, update=update_tex_mask_enable)

    enable_hardness = BoolProperty(
            name='Enable Hardness', 
            description = 'Enable Hardness',
            default=False, update=update_mask_hardness_enable)

    hardness_value = FloatProperty(default=1.0, min=1.0, update=update_mask_hardness_value)

    active_edit = BoolProperty(
            name='Active mask for editing', 
            description='Active mask for editing', 
            default=False,
            update=update_mask_active_edit)

    type = EnumProperty(
            name = 'Mask Type',
            items = texture_type_items,
            default = 'IMAGE')

    texcoord_type = EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_mask_texcoord_type)

    uv_name = StringProperty(default='', update=update_mask_uv_name)

    channels = CollectionProperty(type=YTextureMaskChannel)

    # Nodes
    source = StringProperty(default='')
    #source_tree = PointerProperty(type=bpy.types.ShaderNodeTree)
    #source_group = StringProperty(default='')
    final = StringProperty('')

    #texcoord = StringProperty(default='')
    uv_map = StringProperty(default='')

    hardness = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_source = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)

def register():
    bpy.utils.register_class(YNewTextureMask)
    bpy.utils.register_class(YRemoveTextureMask)
    bpy.utils.register_class(YTextureMaskChannel)
    bpy.utils.register_class(YTextureMask)

def unregister():
    bpy.utils.unregister_class(YNewTextureMask)
    bpy.utils.unregister_class(YRemoveTextureMask)
    bpy.utils.unregister_class(YTextureMaskChannel)
    bpy.utils.unregister_class(YTextureMask)
