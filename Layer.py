import bpy, time, re
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import Modifier, lib, Blur, Mask, transition
from .common import *
from .node_arrangements import *
from .node_connections import *
from .subtree import *

DEFAULT_NEW_IMG_SUFFIX = ' Tex'
DEFAULT_NEW_VCOL_SUFFIX = ' VCol'

def check_all_texture_channel_io_and_nodes(tex, tree=None, specific_ch=None): #, has_parent=False):

    tl = tex.id_data.tl
    if not tree: tree = get_tree(tex)

    correct_index = 0
    valid_inputs = []
    valid_outputs = []

    has_parent = tex.parent_idx != -1
    
    # Tree input and outputs
    for i, ch in enumerate(tex.channels):
        root_ch = tl.channels[i]

        inp = tree.inputs.get(root_ch.name)
        if not inp:
            inp = tree.inputs.new(channel_socket_input_bl_idnames[root_ch.type], root_ch.name)
        fix_io_index(inp, tree.inputs, correct_index)
        valid_inputs.append(inp)

        outp = tree.outputs.get(root_ch.name)
        if not outp:
            outp = tree.outputs.new(channel_socket_output_bl_idnames[root_ch.type], root_ch.name)
        fix_io_index(outp, tree.outputs, correct_index)
        valid_outputs.append(outp)

        correct_index += 1

        name = root_ch.name + ' Alpha'
        inp = tree.inputs.get(name)
        outp = tree.outputs.get(name)

        if (root_ch.type == 'RGB' and root_ch.alpha) or has_parent:#(tex.type == 'GROUP' and has_parent):

            if not inp:
                inp = tree.inputs.new('NodeSocketFloatFactor', name)
                inp.min_value = 0.0
                inp.max_value = 1.0
                inp.default_value = 0.0
            fix_io_index(inp, tree.inputs, correct_index)
            valid_inputs.append(inp)

            if not outp:
                outp = tree.outputs.new(channel_socket_output_bl_idnames['VALUE'], name)
            fix_io_index(outp, tree.outputs, correct_index)
            valid_outputs.append(outp)

            correct_index += 1
        else:
            if inp: tree.inputs.remove(inp)
            if outp: tree.inputs.remove(outp)

    # Tree background inputs
    if tex.type in {'BACKGROUND', 'GROUP'}:

        suffix = ' Background' if tex.type == 'BACKGROUND' else ' Group'

        for i, ch in enumerate(tex.channels):
            root_ch = tl.channels[i]

            name = root_ch.name + suffix
            inp = tree.inputs.get(name)
            if not inp:
                inp = tree.inputs.new(channel_socket_input_bl_idnames[root_ch.type], name)
            fix_io_index(inp, tree.inputs, correct_index)
            valid_inputs.append(inp)

            correct_index += 1

            name = root_ch.name + ' Alpha' + suffix
            inp = tree.inputs.get(name)

            if root_ch.alpha or tex.type == 'GROUP':

                if not inp:
                    inp = tree.inputs.new(channel_socket_input_bl_idnames['VALUE'], name)
                fix_io_index(inp, tree.inputs, correct_index)
                valid_inputs.append(inp)

                correct_index += 1
            else:
                if inp: tree.inputs.remove(inp)

    # Check for invalid io
    for inp in tree.inputs:
        if inp not in valid_inputs:
            tree.inputs.remove(inp)

    for outp in tree.outputs:
        if outp not in valid_outputs:
            tree.outputs.remove(outp)

    # Mapping node
    if tex.type not in {'BACKGROUND', 'VCOL', 'GROUP', 'COLOR'}:
        source_tree = get_source_tree(tex, tree)
        mapping = source_tree.nodes.get(tex.mapping)
        if not mapping:
            mapping = new_node(source_tree, tex, 'mapping', 'ShaderNodeMapping', 'Mapping')

    # Channel nodes
    for i, ch in enumerate(tex.channels):
        root_ch = tl.channels[i]

        # Intensity nodes
        intensity = tree.nodes.get(ch.intensity)
        if not intensity:
            intensity = new_node(tree, ch, 'intensity', 'ShaderNodeMath', 'Intensity')
            intensity.operation = 'MULTIPLY'
            intensity.inputs[1].default_value = 1.0

        # Update texture ch blend type
        check_blend_type_nodes(root_ch, tex, ch)

        # Normal related nodes created by it's normal map type
        if root_ch.type == 'NORMAL':
            check_channel_normal_map_nodes(tree, tex, root_ch, ch)

def channel_items(self, context):
    node = get_active_texture_layers_node()
    tl = node.node_tree.tl

    items = []

    for i, ch in enumerate(tl.channels):
        if hasattr(lib, 'custom_icons'):
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, i))
        else: items.append((str(i), ch.name, '', lib.channel_icon_dict[ch.type], i))

    if hasattr(lib, 'custom_icons'):
        items.append(('-1', 'All Channels', '', lib.custom_icons['channels'].icon_id, len(items)))
    else: items.append(('-1', 'All Channels', '', 'GROUP_VERTEX', len(items)))

    return items

def tex_input_items(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    if not m: return []
    tex = tl.textures[int(m.group(1))]
    #root_ch = tl.channels[int(m.group(2))]

    items = []

    label = texture_type_labels[tex.type]

    items.append(('RGB', label + ' Color',  ''))
    items.append(('ALPHA', label + ' Factor',  ''))
        
    #if tex.type == 'IMAGE':
    #    items.append(('ALPHA', label + ' Alpha',  ''))
    #else: items.append(('ALPHA', label + ' Factor',  ''))

    #if root_ch.type in {'RGB', 'NORMAL'}:
    #    items.append(('CUSTOM', 'Custom Color',  ''))
    #elif root_ch.type == 'VALUE':
    #    items.append(('CUSTOM', 'Custom Value',  ''))

    return items

def mask_bump_type_items(self, context):

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    if not m: return []
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]

    items = []

    items.append(('BUMP_MAP', 'Bump Map', ''))
    items.append(('FINE_BUMP_MAP', 'Fine Bump Map', ''))

    return items

def normal_map_type_items_(tex_type):
    items = []

    if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
        items.append(('NORMAL_MAP', 'Normal Map', '', 'MATCAP_23', 0))
        items.append(('BUMP_MAP', 'Bump Map', '', 'MATCAP_09', 1))
        #if tex_type != 'VCOL':
        items.append(('FINE_BUMP_MAP', 'Fine Bump Map', '', 'MATCAP_09', 2))
    else: # Blender 2.8
        items.append(('NORMAL_MAP', 'Normal Map', ''))
        items.append(('BUMP_MAP', 'Bump Map', ''))
        #if tex_type != 'VCOL':
        items.append(('FINE_BUMP_MAP', 'Fine Bump Map', ''))

    return items

def tex_channel_normal_map_type_items(self, context):
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tl = self.id_data.tl
    tex = tl.textures[int(m.group(1))]
    return normal_map_type_items_(tex.type)

def new_tex_channel_normal_map_type_items(self, context):
    return normal_map_type_items_(self.type)

def img_normal_map_type_items(self, context):
    return normal_map_type_items_('IMAGE')

def add_new_texture(group_tree, tex_name, tex_type, channel_idx, 
        blend_type, normal_blend, normal_map_type, 
        texcoord_type, uv_name='', image=None, vcol=None, 
        add_rgb_to_intensity=False, rgb_to_intensity_color=(1,1,1),
        add_mask=False, mask_type='IMAGE'
        ):

    tl = group_tree.tl

    # Halt rearrangements and reconnections until all nodes already created
    tl.halt_reconnect = True

    # Get parent dict
    parent_dict = get_parent_dict(tl)

    # Get active tex
    try: active_tex = tl.textures[tl.active_texture_index]
    except: active_tex = None

    # Get a possible parent layer group
    parent_tex = None
    if active_tex: 
        if active_tex.type == 'GROUP':
            parent_tex = active_tex
        elif active_tex.parent_idx != -1:
            parent_tex = tl.textures[active_tex.parent_idx]

    # Get parent index
    if parent_tex: 
        parent_idx = get_tex_index(parent_tex)
        has_parent = True
    else: 
        parent_idx = -1
        has_parent = False

    # Add texture to group
    tex = tl.textures.add()
    tex.type = tex_type
    tex.name = tex_name
    tex.uv_name = uv_name

    if image:
        tex.image_name = image.name

    # Move new texture to current index
    last_index = len(tl.textures)-1
    if active_tex and active_tex.type == 'GROUP':
        index = tl.active_texture_index + 1
    else: index = tl.active_texture_index

    # Set parent index
    parent_dict = set_parent_dict_val(tl, parent_dict, tex.name, parent_idx)

    tl.textures.move(last_index, index)
    tex = tl.textures[index] # Repoint to new index

    # Remap other textures parent
    #for i, t in enumerate(tl.textures):
    #    if i > index and t.parent_idx != -1:
    #        t.parent_idx += 1

    # Remap parents
    for t in tl.textures:
        t.parent_idx = get_tex_index_by_name(tl, parent_dict[t.name])

    # New texture tree
    tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex_name, 'ShaderNodeTree')
    tree.tl.is_tl_tex_node = True
    tree.tl.version = get_current_version_str()

    # New texture node group
    group_node = new_node(group_tree, tex, 'group_node', 'ShaderNodeGroup', tex_name)
    group_node.node_tree = tree

    # Create info nodes
    create_info_nodes(group_tree, tex)

    # Tree start and end
    start = new_node(tree, tex, 'start', 'NodeGroupInput', 'Start')
    end = new_node(tree, tex, 'end', 'NodeGroupOutput', 'Start')

    # Add source frame
    source = new_node(tree, tex, 'source', texture_node_bl_idnames[tex_type], 'Source')

    if tex_type == 'IMAGE':
        # Always set non color to image node because of linear pipeline
        source.color_space = 'NONE'

        # Add new image if it's image texture
        source.image = image

    elif tex_type == 'VCOL':
        source.attribute_name = vcol.name

    # Solid alpha can be useful for many things
    solid_alpha = new_node(tree, tex, 'solid_alpha', 'ShaderNodeValue', 'Solid Alpha')
    solid_alpha.outputs[0].default_value = 1.0

    # Add geometry and texcoord node
    geometry = new_node(tree, tex, 'geometry', 'ShaderNodeNewGeometry', 'Source Geometry')
    texcoord = new_node(tree, tex, 'texcoord', 'ShaderNodeTexCoord', 'Source TexCoord')

    # Add uv map node
    #uv_map = new_node(tree, tex, 'uv_map', 'ShaderNodeUVMap', 'Source UV Map')
    #uv_map.uv_map = uv_name

    # Add uv attribute node
    uv_attr = new_node(tree, tex, 'uv_attr', 'ShaderNodeAttribute', 'Source UV Attribute')
    uv_attr.attribute_name = uv_name

    # Add tangent and bitangent node
    #tangent = new_node(tree, tex, 'tangent', 'ShaderNodeTangent', 'Source Tangent')
    #tangent.direction_type = 'UV_MAP'
    #tangent.uv_map = uv_name

    tangent = new_node(tree, tex, 'tangent', 'ShaderNodeNormalMap', 'Source Tangent')
    tangent.uv_map = uv_name
    tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)

    bitangent = new_node(tree, tex, 'bitangent', 'ShaderNodeNormalMap', 'Source Bitangent')
    bitangent.uv_map = uv_name
    bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)

    #hacky_tangent = new_node(tree, tex, 'hacky_tangent', 'ShaderNodeNormalMap', 'Hacky Source Tangent')
    #hacky_tangent.uv_map = uv_name
    #hacky_tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)

    #bitangent = new_node(tree, tex, 'bitangent', 'ShaderNodeGroup', 'Source Bitangent')
    #bitangent.node_tree = lib.get_node_tree_lib(lib.GET_BITANGENT)

    # Set tex coordinate type
    tex.texcoord_type = texcoord_type

    # Add channels to current texture
    for root_ch in tl.channels:
        ch = tex.channels.add()

    if add_mask:

        mask_name = 'Mask ' + tex.name
        mask_image = None
        mask_vcol = None

        if mask_type == 'IMAGE':
            mask_image = bpy.data.images.new(mask_name, 
                    width=1024, height=1024, alpha=False, float_buffer=False)
            #if self.color_option == 'WHITE':
            #    mask_image.generated_color = (1,1,1,1)
            #elif self.color_option == 'BLACK':
            #    mask_image.generated_color = (0,0,0,1)
            mask_image.generated_color = (0,0,0,1)
            mask_image.use_alpha = False

        # New vertex color
        elif mask_type == 'VCOL':
            obj = bpy.context.object
            mask_vcol = obj.data.vertex_colors.new(name=mask_name)
            #if self.color_option == 'WHITE':
            #    set_obj_vertex_colors(obj, mask_vcol, (1.0, 1.0, 1.0))
            #elif self.color_option == 'BLACK':
            #    set_obj_vertex_colors(obj, mask_vcol, (0.0, 0.0, 0.0))
            set_obj_vertex_colors(obj, mask_vcol, (0.0, 0.0, 0.0))

        mask = Mask.add_new_mask(tex, mask_name, mask_type, texcoord_type, uv_name, mask_image, mask_vcol)
        mask.active_edit = True

    # Fill channel layer props
    shortcut_created = False
    for i, ch in enumerate(tex.channels):

        root_ch = tl.channels[i]

        # Set some props to selected channel
        if channel_idx == i or channel_idx == -1:
            ch.enable = True
            if root_ch.type == 'NORMAL':
                ch.normal_blend = normal_blend
            else:
                ch.blend_type = blend_type
        else: 
            ch.enable = False

        if root_ch.type == 'NORMAL':
            ch.normal_map_type = normal_map_type

        if add_rgb_to_intensity:

            # If RGB to intensity is selected, bump base is better be 0.0
            if root_ch.type == 'NORMAL':
                ch.bump_base_value = 0.0

            m = Modifier.add_new_modifier(ch, 'RGB_TO_INTENSITY')
            if channel_idx == i or channel_idx == -1:
                col = (rgb_to_intensity_color[0], rgb_to_intensity_color[1], rgb_to_intensity_color[2], 1)
                mod_tree = get_mod_tree(m)
                m.rgb2i_col = col
                #rgb2i = mod_tree.nodes.get(m.rgb2i)
                #rgb2i.inputs[2].default_value = col

            if ch.enable and root_ch.type == 'RGB' and not shortcut_created:
                m.shortcut = True
                shortcut_created = True

        # Set linear node of texture channel
        #if root_ch.type == 'NORMAL':
        #    set_tex_channel_linear_node(tree, tex, root_ch, ch, custom_value=(0.5,0.5,1))
        #else: set_tex_channel_linear_node(tree, tex, root_ch, ch)
        set_tex_channel_linear_node(tree, tex, root_ch, ch)

    # Check and create layer channel nodes
    check_all_texture_channel_io_and_nodes(tex, tree) #, has_parent=has_parent)

    # Refresh paint image by updating the index
    tl.active_texture_index = index

    # Unhalt rearrangements and reconnections since all nodes already created
    tl.halt_reconnect = False

    # Rearrange node inside textures
    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

    return tex

def update_channel_idx_new_texture(self, context):
    node = get_active_texture_layers_node()
    tl = node.node_tree.tl

    if self.channel_idx == '-1':
        self.rgb_to_intensity_color = (1,1,1)
        return

    for i, ch in enumerate(tl.channels):
        if self.channel_idx == str(i):
            if ch.type == 'RGB':
                self.rgb_to_intensity_color = (1,0,1)
            else: self.rgb_to_intensity_color = (1,1,1)

def get_fine_bump_distance(tex, distance):
    scale = 100
    if tex.type == 'IMAGE':
        source = get_tex_source(tex)
        image = source.image
        if image: scale = image.size[0] / 10

    #return -1.0 * distance * scale
    return distance * scale

class YRefreshNeighborUV(bpy.types.Operator):
    """Refresh Neighbor UV"""
    bl_idname = "node.y_refresh_neighbor_uv"
    bl_label = "Refresh Neighbor UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'texture') and hasattr(context, 'channel') and hasattr(context, 'image') and context.image

    def execute(self, context):
        tree = get_tree(context.texture)

        uv_neighbor = tree.nodes.get(context.texture.uv_neighbor)
        uv_neighbor.inputs[1].default_value = context.image.size[0]
        uv_neighbor.inputs[2].default_value = context.image.size[1]
        
        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(uv_neighbor, 1)
        #    match_group_input(uv_neighbor, 2)

        #fine_bump = tree.nodes.get(context.parent.fine_bump)
        #fine_bump.inputs[0].default_value = get_fine_bump_distance(context.texture, context.channel.bump_distance)

        #if BLENDER_28_GROUP_INPUT_HACK:
        #    match_group_input(fine_bump, 0)
        #    #inp = fine_bump.node_tree.nodes.get('Group Input')
        #    #inp.outputs[0].links[0].to_socket.default_value = fine_bump.inputs[0].default_value

        return {'FINISHED'}

#def set_default_tex_input(tex):
#    tl = tex.id_data.tl
#
#    for i, root_ch in enumerate(tl.channels):
#        ch = tex.channels[i]
#
#        if root_ch.colorspace == 'SRGB':
#
#            if tex.type in {'CHECKER', 'IMAGE'}:
#                ch.tex_input = 'RGB_SRGB'
#            else: ch.tex_input = 'RGB_LINEAR'
#
#        else:
#            ch.tex_input = 'RGB_LINEAR'

class YNewTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_new_texture_layer"
    bl_label = "New Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'IMAGE')

    # For image texture
    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)
    color = FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    #alpha = BoolProperty(name='Alpha', default=True)
    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    add_mask = BoolProperty(
            name = 'Add Mask',
            description = 'Add mask to new layer',
            default = False)

    mask_type = EnumProperty(
            name = 'Mask Type',
            description = 'Mask type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    uv_map = StringProperty(default='')

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = new_tex_channel_normal_map_type_items)
            #default = 'BUMP_MAP')

    #make_transition_bump_default = BoolProperty(
    #        name = 'Use Transition Bump on Normal channel',
    #        description = 'Use Transition Bump on (first) Normal channel',
    #        default = False)

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()
        #return hasattr(context, 'group_node') and context.group_node

    def invoke(self, context, event):

        #self.group_node = node = context.group_node
        #print(self.group_node)
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        #tl = context.group_node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if self.type == 'IMAGE':
            name = obj.active_material.name + DEFAULT_NEW_IMG_SUFFIX
            items = bpy.data.images
        elif self.type == 'VCOL' and obj.type == 'MESH':
            name = obj.active_material.name + DEFAULT_NEW_VCOL_SUFFIX
            items = obj.data.vertex_colors
        else:
            name = [i[1] for i in texture_type_items if i[0] == self.type][0]
            items = tl.textures
            
        # Default normal map type is fine bump map
        #if self.type not in {'VCOL', 'COLOR'}:
        #self.normal_map_type = 'FINE_BUMP_MAP'
        self.normal_map_type = 'BUMP_MAP'
        #else: self.normal_map_type = 'BUMP_MAP'

        self.name = get_unique_name(name, items)

        if obj.type != 'MESH':
            #self.texcoord_type = 'Object'
            self.texcoord_type = 'Generated'
        else:
            # Use active uv layer name by default
            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            if obj.type == 'MESH' and len(uv_layers) > 0:
                self.uv_map = uv_layers.active.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        #tl = self.group_node.node_tree.tl
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        if len(tl.channels) == 0:
            self.layout.label(text='No channel found! Still want to create a texture?', icon='ERROR')
            return

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            row = self.layout.split(percentage=0.4)
        else: row = self.layout.split(factor=0.4)
        col = row.column(align=False)

        col.label(text='Name:')
        col.label(text='Channel:')
        if channel and channel.type == 'NORMAL':
            col.label(text='Type:')
        col.label(text='')

        if self.add_rgb_to_intensity:
            col.label(text='RGB To Intensity Color:')

        if self.type == 'IMAGE':
            if not self.add_rgb_to_intensity:
                col.label(text='Color:')
            col.label(text='')
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type != 'VCOL':
            col.label(text='Vector:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')

        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

        if self.type == 'IMAGE':
            if not self.add_rgb_to_intensity:
                col.prop(self, 'color', text='')
                #col.prop(self, 'alpha')
            col.prop(self, 'hdr')
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type != 'VCOL':
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')

    def execute(self, context):

        T = time.time()

        wm = context.window_manager
        obj = context.object
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        tlui = context.window_manager.tlui

        # Check if object is not a mesh
        if self.type == 'VCOL' and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color layer only works with mesh object!")
            return {'CANCELLED'}

        # Check if texture with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in obj.data.vertex_colors if i.name == self.name]
        else: same_name = [t for t in tl.textures if t.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
            elif self.type == 'VCOL':
                self.report({'ERROR'}, "Vertex Color named '" + self.name +"' is already available!")
            self.report({'ERROR'}, "Texture named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        img = None
        if self.type == 'IMAGE':
            alpha = False if self.add_rgb_to_intensity else True
            color = (0,0,0,1) if self.add_rgb_to_intensity else self.color
            img = bpy.data.images.new(name=self.name, 
                    width=self.width, height=self.height, alpha=alpha, float_buffer=self.hdr)
            #img.generated_type = self.generated_type
            img.generated_type = 'BLANK'
            img.generated_color = color
            img.use_alpha = False if self.add_rgb_to_intensity else True
            update_image_editor_image(context, img)

        vcol = None
        if self.type == 'VCOL':
            vcol = obj.data.vertex_colors.new(name=self.name)
            set_obj_vertex_colors(obj, vcol, (1.0, 1.0, 1.0))

        tl.halt_update = True
        tex = add_new_texture(node.node_tree, self.name, self.type, 
                int(self.channel_idx), self.blend_type, self.normal_blend, 
                self.normal_map_type, self.texcoord_type, self.uv_map, img, vcol,
                self.add_rgb_to_intensity, self.rgb_to_intensity_color,
                self.add_mask, self.mask_type)
        tl.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_tl_tex_nodes(node.node_tree)
        reconnect_tl_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        if self.type != 'IMAGE':
            tlui.tex_ui.expand_content = True
        tlui.need_update = True

        print('INFO: Texture', tex.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YOpenImageToLayer(bpy.types.Operator, ImportHelper):
    """Open Image to Texture Layer"""
    bl_idname = "node.y_open_image_to_layer"
    bl_label = "Open Image to Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files = CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory = StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type = EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative = BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = img_normal_map_type_items)
            #default = 'NORMAL_MAP')

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_layers_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            self.uv_map = obj.data.uv_layers.active.name

        # Normal map is the default
        self.normal_map_type = 'NORMAL_MAP'

        #return context.window_manager.invoke_props_dialog(self)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        
        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')
        col.label(text='Channel:')
        if channel and channel.type == 'NORMAL':
            col.label(text='Type:')

        if self.add_rgb_to_intensity:
            col.label(text='')
            col.label(text='RGB2I Color:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')

        #col.label(text='')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

        self.layout.prop(self, 'relative')

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_texture_layers_node()

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        node.node_tree.tl.halt_update = True

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            add_new_texture(node.node_tree, image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                    self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map,
                    image, None, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.tl.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_tl_tex_nodes(node.node_tree)
        reconnect_tl_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        wm.tlui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableImageToLayer(bpy.types.Operator):
    """Open Available Image to Texture Layer"""
    bl_idname = "node.y_open_available_image_to_layer"
    bl_label = "Open Available Image to Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = img_normal_map_type_items)
            #default = 'BUMP_MAP')

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_layers_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            self.uv_map = obj.data.uv_layers.active.name

        # Update image names
        self.image_coll.clear()
        imgs = bpy.data.images
        for img in imgs:
            self.image_coll.add().name = img.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        
        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')
        col.label(text='Channel:')
        if channel and channel.type == 'NORMAL':
            col.label(text='Type:')

        if self.add_rgb_to_intensity:
            col.label(text='')
            col.label(text='RGB2I Color:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')

        #col.label(text='')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_texture_layers_node()

        if self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}

        node.node_tree.tl.halt_update = True

        image = bpy.data.images.get(self.image_name)
        add_new_texture(node.node_tree, image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map, 
                image, None, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.tl.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_tl_tex_nodes(node.node_tree)
        reconnect_tl_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        wm.tlui.need_update = True
        print('INFO: Image', self.image_name, 'is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YMoveInOutLayerGroup(bpy.types.Operator):
    bl_idname = "node.y_move_in_out_layer_group"
    bl_label = "Move In/Out Texture Layer Group"
    bl_description = "Move in or out texture layer group"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.textures) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        num_tex = len(tl.textures)
        tex_idx = tl.active_texture_index
        tex = tl.textures[tex_idx]

        # Remember parent
        parent_dict = get_parent_dict(tl)
        
        # Move image slot
        if self.direction == 'UP':
            neighbor_idx, neighbor_tex = get_upper_neighbor(tex)
        elif self.direction == 'DOWN' and tex_idx < num_tex-1:
            neighbor_idx, neighbor_tex = get_lower_neighbor(tex)
        else:
            neighbor_idx = -1
            neighbor_tex = None

        # Move outside up
        if is_top_member(tex) and self.direction == 'UP':
            #print('Case 1')

            parent_dict = set_parent_dict_val(tl, parent_dict, tex.name, neighbor_tex.parent_idx)

            last_member_idx = get_last_child_idx(tex)
            tl.textures.move(neighbor_idx, last_member_idx)

            tl.active_texture_index = neighbor_idx

        # Move outside down
        elif is_bottom_member(tex) and self.direction == 'DOWN':
            #print('Case 2')

            parent_dict = set_parent_dict_val(tl, parent_dict, tex.name, tl.textures[tex.parent_idx].parent_idx)

        elif neighbor_tex and neighbor_tex.type == 'GROUP':

            # Move inside up
            if self.direction == 'UP':
                #print('Case 3')

                parent_dict = set_parent_dict_val(tl, parent_dict, tex.name, neighbor_idx)

            # Move inside down
            elif self.direction == 'DOWN':
                #print('Case 4')

                parent_dict = set_parent_dict_val(tl, parent_dict, tex.name, neighbor_idx)

                tl.textures.move(neighbor_idx, tex_idx)
                tl.active_texture_index = tex_idx+1

        # Remap parents
        for t in tl.textures:
            t.parent_idx = get_tex_index_by_name(tl, parent_dict[t.name])

        tex = tl.textures[tl.active_texture_index]
        #has_parent = tex.parent_idx != -1

        #if tex.type == 'GROUP' or has_parent:
        check_all_texture_channel_io_and_nodes(tex) #, has_parent=has_parent)
        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        # Refresh texture channel blend nodes
        rearrange_tl_nodes(node.node_tree)
        reconnect_tl_nodes(node.node_tree)

        # Update UI
        wm.tlui.need_update = True
        print('INFO: Texture', tex.name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YMoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_move_texture_layer"
    bl_label = "Move Texture Layer"
    bl_description = "Move texture layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.textures) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        num_tex = len(tl.textures)
        tex_idx = tl.active_texture_index
        tex = tl.textures[tex_idx]

        # Get last member of group if selected layer is a group
        last_member_idx = get_last_child_idx(tex)
        
        # Get neighbor
        neighbor_idx = None
        neighbor_tex = None

        if self.direction == 'UP':
            neighbor_idx, neighbor_tex = get_upper_neighbor(tex)

        elif self.direction == 'DOWN':
            neighbor_idx, neighbor_tex = get_lower_neighbor(tex)

        if not neighbor_tex:
            return {'CANCELLED'}

        # Remember all parents
        parent_dict = get_parent_dict(tl)

        if tex.type == 'GROUP' and neighbor_tex.type != 'GROUP':

            # Group layer UP to standard layer
            if self.direction == 'UP':
                #print('Case A')

                # Swap texture
                tl.textures.move(neighbor_idx, last_member_idx)
                tl.active_texture_index = neighbor_idx

                #affected_start = neighbor_idx
                #affected_end = last_member_idx+1

            # Group layer DOWN to standard layer
            elif self.direction == 'DOWN':
                #print('Case B')

                # Swap texture
                tl.textures.move(neighbor_idx, tex_idx)
                tl.active_texture_index = tex_idx+1

                #affected_start = neighbor_idx
                #affected_end = tex_idx+1

        elif tex.type == 'GROUP' and neighbor_tex.type == 'GROUP':

            # Group layer UP to group layer
            if self.direction == 'UP':
                #print('Case C')

                # Swap all related layers
                for i in range(last_member_idx+1 - tex_idx):
                    tl.textures.move(tex_idx+i, neighbor_idx+i)

                tl.active_texture_index = neighbor_idx

            # Group layer DOWN to group layer
            elif self.direction == 'DOWN':
                #print('Case D')

                last_neighbor_member_idx = get_last_child_idx(neighbor_tex)
                num_members = last_neighbor_member_idx+1 - neighbor_idx

                # Swap all related layers
                for i in range(num_members):
                    tl.textures.move(neighbor_idx+i, tex_idx+i)

                tl.active_texture_index = tex_idx+num_members

        elif tex.type != 'GROUP' and neighbor_tex.type == 'GROUP':

            # Standard layer UP to Group Layer
            if self.direction == 'UP':
                #print('Case E')

                # Swap texture
                tl.textures.move(tex_idx, neighbor_idx)
                tl.active_texture_index = neighbor_idx

                start_remap = neighbor_idx + 2
                end_remap = tex_idx + 1

            # Standard layer DOWN to Group Layer
            elif self.direction == 'DOWN':
                #print('Case F')

                last_neighbor_member_idx = get_last_child_idx(neighbor_tex)

                # Swap texture
                tl.textures.move(tex_idx, last_neighbor_member_idx)
                tl.active_texture_index = last_neighbor_member_idx

                start_remap = tex_idx + 1
                end_remap = last_neighbor_member_idx

        # Standard layer to standard Layer
        else:
            #print('Case G')

            # Swap texture
            tl.textures.move(tex_idx, neighbor_idx)
            tl.active_texture_index = neighbor_idx

        # Remap parents
        for t in tl.textures:
            t.parent_idx = get_tex_index_by_name(tl, parent_dict[t.name])

        # Refresh texture channel blend nodes
        reconnect_tl_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        wm.tlui.need_update = True

        print('INFO: Texture', tex.name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

def draw_move_up_in_layer_group(self, context):
    col = self.layout.column()

    c = col.operator("node.y_move_texture_layer", text='Move Up (skip group)', icon='TRIA_UP')
    c.direction = 'UP'

    c = col.operator("node.y_move_in_out_layer_group", text='Move inside group', icon='TRIA_UP')
    c.direction = 'UP'

def draw_move_down_in_layer_group(self, context):
    col = self.layout.column()

    c = col.operator("node.y_move_texture_layer", text='Move Down (skip group)', icon='TRIA_DOWN')
    c.direction = 'DOWN'

    c = col.operator("node.y_move_in_out_layer_group", text='Move inside group', icon='TRIA_DOWN')
    c.direction = 'DOWN'

def draw_move_up_out_layer_group(self, context):
    col = self.layout.column()
    c = col.operator("node.y_move_in_out_layer_group", text='Move outside group', icon='TRIA_UP')
    c.direction = 'UP'

def draw_move_down_out_layer_group(self, context):
    col = self.layout.column()
    c = col.operator("node.y_move_in_out_layer_group", text='Move outside group', icon='TRIA_DOWN')
    c.direction = 'DOWN'

class YMoveInOutLayerGroupMenu(bpy.types.Operator):
    bl_idname = "node.y_move_in_out_layer_group_menu"
    bl_label = "Move In/Out Layer Group"
    bl_description = "Move inside or outside layer group"
    #bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    move_out = BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.textures) > 0

    def execute(self, context):
        wm = bpy.context.window_manager

        if self.move_out:
            if self.direction == 'UP':
                wm.popup_menu(draw_move_up_out_layer_group, title="Options")
            elif self.direction == 'DOWN':
                wm.popup_menu(draw_move_down_out_layer_group, title="Options")
        else:
            if self.direction == 'UP':
                wm.popup_menu(draw_move_up_in_layer_group, title="Options")
            elif self.direction == 'DOWN':
                wm.popup_menu(draw_move_down_in_layer_group, title="Options")
        return {'FINISHED'}

def remove_tex(tl, index):
    group_tree = tl.id_data
    obj = bpy.context.object
    tex = tl.textures[index]
    tex_tree = get_tree(tex)

    # Remove the source first to remove image
    source_tree = get_source_tree(tex, tex_tree)
    remove_node(source_tree, tex, 'source', obj=obj)

    # Remove Mask source
    for mask in tex.masks:
        mask_tree = get_mask_tree(mask)
        remove_node(mask_tree, mask, 'source', obj=obj)

    # Remove node group and tex tree
    bpy.data.node_groups.remove(tex_tree)
    group_tree.nodes.remove(group_tree.nodes.get(tex.group_node))

    # Delete the texture
    tl.textures.remove(index)

def draw_remove_group(self, context):
    col = self.layout.column()

    c = col.operator("node.y_remove_layer", text='Remove parent only', icon='PANEL_CLOSE')
    c.remove_childs = False

    c = col.operator("node.y_remove_layer", text='Remove parent with all its childrens', icon='PANEL_CLOSE')
    c.remove_childs = True

class YRemoveLayerMenu(bpy.types.Operator):
    bl_idname = "node.y_remove_layer_menu"
    bl_label = "Remove Layer Menu"
    bl_description = "Remove Layer Menu"
    #bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return context.object and group_node and len(group_node.node_tree.tl.textures) > 0

    def execute(self, context):
        wm = bpy.context.window_manager
        wm.popup_menu(draw_remove_group, title="Options")
        return {'FINISHED'}

class YRemoveLayer(bpy.types.Operator):
    bl_idname = "node.y_remove_layer"
    bl_label = "Remove Layer"
    bl_description = "Remove Layer"
    bl_options = {'REGISTER', 'UNDO'}

    remove_childs = BoolProperty(name='Remove Childs', description='Remove layer childrens', default=False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return context.object and group_node and len(group_node.node_tree.tl.textures) > 0

    def invoke(self, context, event):
        obj = context.object
        if obj.mode != 'OBJECT':
            return context.window_manager.invoke_props_dialog(self, width=400)
        return self.execute(context)

    def draw(self, context):
        obj = context.object
        if obj.mode != 'OBJECT':
            self.layout.label(text='You cannot UNDO this operation under this mode, are you sure?', icon='ERROR')

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl
        tex = tl.textures[tl.active_texture_index]
        tex_name = tex.name
        tex_idx = get_tex_index(tex)

        # Remember parents
        parent_dict = get_parent_dict(tl)

        if self.remove_childs:
            last_idx = get_last_child_idx(tex)
            for i in reversed(range(tex_idx, last_idx+1)):
                remove_tex(tl, i)
        else:
            # Repoint its children parent
            for t in get_list_of_direct_childrens(tex):
                parent_dict = set_parent_dict_val(tl, parent_dict, t.name, tex.parent_idx)

            # Remove tex
            remove_tex(tl, tex_idx)

        # Set new active index
        if (tl.active_texture_index == len(tl.textures) and
            tl.active_texture_index > 0
            ):
            tl.active_texture_index -= 1
        else:
            # Force update the index to refesh paint image
            tl.active_texture_index = tl.active_texture_index

        # Remap parents
        for t in tl.textures:
            t.parent_idx = get_tex_index_by_name(tl, parent_dict[t.name])

        # Refresh texture channel blend nodes
        reconnect_tl_nodes(group_tree)
        rearrange_tl_nodes(group_tree)

        # Update UI
        wm.tlui.need_update = True

        # Refresh normal map
        tl.refresh_tree = True

        print('INFO: Texture', tex_name, 'is deleted at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YReplaceLayerType(bpy.types.Operator):
    bl_idname = "node.y_replace_layer_type"
    bl_label = "Replace Layer Type"
    bl_description = "Replace Layer Type"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Layer Type',
            items = texture_type_items,
            default = 'IMAGE')

    item_name = StringProperty(name="Item")
    item_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return context.object and group_node and len(group_node.node_tree.tl.textures) > 0

    def invoke(self, context, event):
        obj = context.object
        self.texture = context.texture
        if self.type in {'IMAGE', 'VCOL'}:

            self.item_coll.clear()
            self.item_name = ''

            # Update image names
            if self.type == 'IMAGE':
                for img in bpy.data.images:
                    self.item_coll.add().name = img.name
            else:
                for vcol in obj.data.vertex_colors:
                    self.item_coll.add().name = vcol.name

            return context.window_manager.invoke_props_dialog(self)#, width=400)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout

        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            split = layout.split(percentage=0.35)
        else: split = layout.split(factor=0.35, align=True)

        #row = self.layout.row()
        if self.type == 'IMAGE':
            split.label(text='Image:')
            split.prop_search(self, "item_name", self, "item_coll", text='', icon='IMAGE_DATA')
        else:
            split.label(text='Vertex Color:')
            split.prop_search(self, "item_name", self, "item_coll", text='', icon='GROUP_VCOL')

    def execute(self, context):

        T = time.time()

        wm = context.window_manager
        tex = self.texture
        tl = tex.id_data.tl

        if self.type == tex.type: return {'CANCELLED'}

        tl.halt_reconnect = True

        # Standard bump map is easier to convert
        fine_bump_channels = [ch for ch in tex.channels if ch.normal_map_type == 'FINE_BUMP_MAP']
        for ch in fine_bump_channels:
            ch.normal_map_type = 'BUMP_MAP'

        # Disable transition will also helps
        transition_channels = [ch for ch in tex.channels if ch.enable_mask_bump]
        for ch in transition_channels:
            ch.enable_mask_bump = False

        # Current source
        tree = get_tree(tex)
        source_tree = get_source_tree(tex)
        source = source_tree.nodes.get(tex.source)

        # Save source to cache if it's not image, vertex color, or background
        if tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
            setattr(tex, 'cache_' + tex.type.lower(), source.name)
            # Remove uv input link
            if any(source.inputs) and any(source.inputs[0].links):
                tree.links.remove(source.inputs[0].links[0])
            source.label = ''
        else:
            remove_node(source_tree, tex, 'source', remove_data=False)

        # Disable modifier tree
        if (tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'} and 
                self.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'}):
            Modifier.disable_modifiers_tree(tex)

        # Try to get available cache
        cache = None
        if self.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
            cache = tree.nodes.get(getattr(tex, 'cache_' + self.type.lower()))

        if cache:
            tex.source = cache.name
            setattr(tex, 'cache_' + self.type.lower(), '')
            cache.label = 'Source'
        else:
            source = new_node(source_tree, tex, 'source', texture_node_bl_idnames[self.type], 'Source')

            if self.type == 'IMAGE':
                image = bpy.data.images.get(self.item_name)
                source.image = image
                source.color_space = 'NONE'
            elif self.type == 'VCOL':
                source.attribute_name = self.item_name

        uv_neighbor = tree.nodes.get(tex.uv_neighbor)
        if uv_neighbor:
            if self.type == 'IMAGE':
                uv_neighbor.inputs[1].default_value = source.image.size[0]
                uv_neighbor.inputs[2].default_value = source.image.size[1]
            else:
                uv_neighbor.inputs[1].default_value = 1000
                uv_neighbor.inputs[2].default_value = 1000
                
            #if BLENDER_28_GROUP_INPUT_HACK:
            #    match_group_input(uv_neighbor, 1)
            #    match_group_input(uv_neighbor, 2)

        tex.type = self.type

        # Enable modifiers tree if generated texture is used
        if tex.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
            Modifier.enable_modifiers_tree(tex)

        # Update group ios
        check_all_texture_channel_io_and_nodes(tex, tree)
        if tex.type == 'BACKGROUND':
            # Remove bump and its base
            for ch in tex.channels:
                remove_node(tree, ch, 'bump_base')
                remove_node(tree, ch, 'bump')

        # Update linear stuff
        for i, ch in enumerate(tex.channels):
            root_ch = tl.channels[i]
            set_tex_channel_linear_node(tree, tex, root_ch, ch)

        # Back to use fine bump if conversion happen
        for ch in fine_bump_channels:
            ch.normal_map_type = 'FINE_BUMP_MAP'

        # Bring back transition
        for ch in transition_channels:
            ch.enable_mask_bump = True

        tl.halt_reconnect = False

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        if tex.type == 'BACKGROUND':
            reconnect_tl_nodes(tex.id_data)

        print('INFO: Layer', tex.name, 'is updated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

def update_channel_enable(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = tl.channels[ch_index]
    ch = self

    tree = get_tree(tex)

    mute = not tex.enable or not ch.enable
    intensity = tree.nodes.get(ch.intensity)
    if intensity:
        intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

    if ch.enable_mask_ramp:
        mr_intensity = tree.nodes.get(ch.mr_intensity)
        if mr_intensity: mr_intensity.inputs[1].default_value = 0.0 if mute else ch.mask_ramp_intensity_value

    #blend = tree.nodes.get(ch.blend)
    #blend.mute = not tex.enable or not ch.enable

    #if ch.enable_mask_ramp:
    #    mr_blend = tree.nodes.get(ch.mr_blend)
    #    if mr_blend: mr_blend.mute = blend.mute

    if ch.enable_mask_bump:
        transition.check_transition_bump_nodes(tex, tree, ch, ch_index)

def check_channel_normal_map_nodes(tree, tex, root_ch, ch):

    #print("Checking channel normal map nodes. Layer: " + tex.name + ' Channel: ' + root_ch.name)

    tl = tex.id_data.tl
    #if tl.halt_update: return

    if root_ch.type != 'NORMAL': return
    if tex.type in {'BACKGROUND', 'GROUP'}: return

    normal_map_type = ch.normal_map_type
    #if tex.type in {'VCOL', 'COLOR'} and ch.normal_map_type == 'FINE_BUMP_MAP':
    if tex.type == 'VCOL' and ch.normal_map_type == 'FINE_BUMP_MAP':
        normal_map_type = 'BUMP_MAP'
    #elif tex.type == 'COLOR':
    #elif tex.type in {'BACKGROUND', 'GROUP', 'COLOR'}:
    #    normal_map_type = ''

    if is_valid_to_remove_bump_nodes(tex, ch):
        normal_map_type = ''

    #print(normal_map_type)

    # Normal nodes
    if normal_map_type == 'NORMAL_MAP':

        normal = tree.nodes.get(ch.normal)
        if not normal:
            normal = new_node(tree, ch, 'normal', 'ShaderNodeNormalMap')
            normal.uv_map = tex.uv_name

    # Bump nodes
    elif normal_map_type == 'BUMP_MAP':

        bump = tree.nodes.get(ch.bump)
        if not bump:
            bump = new_node(tree, ch, 'bump', 'ShaderNodeBump')
            bump.inputs[1].default_value = ch.bump_distance

    # Fine bump nodes
    elif normal_map_type == 'FINE_BUMP_MAP':

        fine_bump = tree.nodes.get(ch.fine_bump)

        # Make sure to enable source tree and modifier tree
        enable_tex_source_tree(tex, False)
        Modifier.enable_modifiers_tree(ch, False)

        if not fine_bump:
            fine_bump = new_node(tree, ch, 'fine_bump', 'ShaderNodeGroup', 'Fine Bump')
            fine_bump.node_tree = lib.get_node_tree_lib(lib.FINE_BUMP)
            fine_bump.inputs[0].default_value = get_fine_bump_distance(tex, ch.bump_distance)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(fine_bump)

    # Remove bump nodes
    if normal_map_type != 'BUMP_MAP':
        remove_node(tree, ch, 'bump')

    # Remove normal nodes
    if normal_map_type != 'NORMAL_MAP':
        remove_node(tree, ch, 'normal')

    # Remove fine bump nodes
    if normal_map_type != 'FINE_BUMP_MAP':
        remove_node(tree, ch, 'fine_bump')

        disable_tex_source_tree(tex, False)
        Modifier.disable_modifiers_tree(ch, False)

    # Create normal flip node
    #if tex.type not in {'BACKGROUND', 'GROUP', 'COLOR'}:
    #if normal_map_type != '' or (normal_map_type == '' and ch.enable_mask_bump):

    #normal_flip = tree.nodes.get(ch.normal_flip)
    #if not normal_flip:
    #    normal_flip = new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 'Flip Backface Normal')
    #    normal_flip.node_tree = lib.get_node_tree_lib(lib.FLIP_BACKFACE_NORMAL)

    #else:
    #    remove_node(tree, ch, 'normal_flip')

    # Update override color modifier
    for mod in ch.modifiers:
        if mod.type == 'OVERRIDE_COLOR' and mod.oc_use_normal_base:
            if normal_map_type == 'NORMAL_MAP':
                mod.oc_col = (0.5, 0.5, 1.0, 1.0)
            else:
                val = ch.bump_base_value
                mod.oc_col = (val, val, val, 1.0)

    # Check bump base
    check_create_bump_base(tex, tree, ch)

    # Check mask multiplies
    check_mask_multiply_nodes(tex, tree)

    # Check mask source tree
    check_mask_source_tree(tex) #, ch)

def update_normal_map_type(self, context):
    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]
    tree = get_tree(tex)

    check_channel_normal_map_nodes(tree, tex, root_ch, self)

    #if not tl.halt_reconnect:
    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

def check_blend_type_nodes(root_ch, tex, ch):

    #print("Checking blend type nodes. Layer: " + tex.name + ' Channel: ' + root_ch.name)

    need_reconnect = False

    tree = get_tree(tex)
    nodes = tree.nodes
    blend = nodes.get(ch.blend)

    has_parent = tex.parent_idx != -1

    # Check blend type
    if blend:
        #if ((root_ch.alpha and ch.blend_type == 'MIX' and blend.bl_idname == 'ShaderNodeMixRGB') or
        #    (not root_ch.alpha and blend.bl_idname == 'ShaderNodeGroup') or
        #    (ch.blend_type != 'MIX' and blend.bl_idname == 'ShaderNodeGroup')):
        #    #nodes.remove(blend)
        #    remove_node(tree, ch, 'blend')
        #    blend = None
        #    need_reconnect = True
        #elif root_ch.type == 'NORMAL':
        #    #if ((ch.normal_blend == 'MIX' and blend.bl_idname == 'ShaderNodeGroup') or
        #    #    (ch.normal_blend in {'OVERLAY'} and blend.bl_idname == 'ShaderNodeMixRGB')):
        #    #nodes.remove(blend)
        #    remove_node(tree, ch, 'blend')
        #    blend = None
        #    need_reconnect = True
        remove_node(tree, ch, 'blend')
        blend = None
        need_reconnect = True

    # Create blend node if its missing
    if not blend:
        if has_parent and ch.blend_type == 'MIX':

            blend = new_node(tree, ch, 'blend', 'ShaderNodeGroup', 'Blend')

            if root_ch.type == 'RGB':
                if tex.type == 'BACKGROUND':
                    blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_BG)
                else: blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER)
            elif root_ch.type == 'VALUE':
                blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_BW)
            elif root_ch.type == 'NORMAL':
                blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_VEC)

        elif root_ch.type == 'RGB':
            if root_ch.alpha and ch.blend_type == 'MIX':
                blend = new_node(tree, ch, 'blend', 'ShaderNodeGroup', 'Blend')
                if tex.type == 'BACKGROUND':
                    blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_BG)
                else: blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER)
                #if BLENDER_28_GROUP_INPUT_HACK:
                #    duplicate_lib_node_tree(blend)

            else:
                blend = new_node(tree, ch, 'blend', 'ShaderNodeMixRGB', 'Blend')
                blend.blend_type = ch.blend_type

        elif root_ch.type == 'NORMAL':
            if ch.normal_blend == 'OVERLAY':
                blend = new_node(tree, ch, 'blend', 'ShaderNodeGroup', 'Blend')
                blend.node_tree = lib.get_node_tree_lib(lib.OVERLAY_NORMAL)
            #elif ch.normal_blend == 'VECTOR_MIX':
            elif ch.normal_blend == 'MIX':
                blend = new_node(tree, ch, 'blend', 'ShaderNodeGroup', 'Blend')
                blend.node_tree = lib.get_node_tree_lib(lib.VECTOR_MIX)

        else:
            blend = new_node(tree, ch, 'blend', 'ShaderNodeMixRGB', 'Blend')
            blend.blend_type = ch.blend_type

        # Blend mute
        mute = not tex.enable or not ch.enable
        intensity = nodes.get(ch.intensity)
        if intensity: intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value
        if ch.enable_mask_ramp:
            mr_intensity = nodes.get(ch.mr_intensity)
            if mr_intensity: mr_intensity.inputs[1].default_value = 0.0 if mute else ch.mask_ramp_intensity_value

        #if tex.enable and ch.enable:
        #    blend.mute = False
        #else: blend.mute = True

    # Update blend mix
    if root_ch.type != 'NORMAL' and blend.bl_idname == 'ShaderNodeMixRGB' and blend.blend_type != ch.blend_type:
        blend.blend_type = ch.blend_type

    # Check alpha tex input output connection
    start = nodes.get(tex.start)
    if (root_ch.type == 'RGB' and root_ch.alpha and ch.blend_type != 'MIX' and 
        #len(start.outputs[get_alpha_io_index(tex, root_ch)].links) == 0):
        len(start.outputs[root_ch.io_index+1].links) == 0):
        need_reconnect = True

    return need_reconnect

def update_blend_type(self, context):
    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = tl.channels[ch_index]

    if check_blend_type_nodes(root_ch, tex, self): # and not tl.halt_reconnect:
        reconnect_tex_nodes(tex, ch_index)
        rearrange_tex_nodes(tex)

def update_flip_backface_normal(self, context):
    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)

    normal_flip = tree.nodes.get(self.normal_flip)
    normal_flip.mute = self.invert_backface_normal

def update_bump_base_value(self, context):
    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)

    update_bump_base_value_(tree, self)

def update_bump_distance(self, context):
    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)

    normal_map_type = self.normal_map_type
    #if tex.type in {'VCOL', 'COLOR'} and self.normal_map_type == 'FINE_BUMP_MAP':
    if tex.type in {'VCOL'}  and self.normal_map_type == 'FINE_BUMP_MAP':
        normal_map_type = 'BUMP_MAP'

    if normal_map_type == 'BUMP_MAP':
        bump = tree.nodes.get(self.bump)
        if bump: bump.inputs[1].default_value = self.bump_distance

    elif normal_map_type == 'FINE_BUMP_MAP':

        fine_bump = tree.nodes.get(self.fine_bump)
        if fine_bump: 
            fine_bump.inputs[0].default_value = get_fine_bump_distance(tex, self.bump_distance)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    match_group_input(fine_bump, 0)

def set_tex_channel_linear_node(tree, tex, root_ch, ch):

    #if custom_value: 
    #    if root_ch.type in {'RGB', 'NORMAL'}:
    #        ch.custom_color = custom_value
    #    else: ch.custom_value = custom_value

    if (root_ch.type != 'NORMAL' and root_ch.colorspace == 'SRGB' 
            and tex.type not in {'IMAGE', 'BACKGROUND', 'GROUP'} and ch.tex_input == 'RGB' and not ch.gamma_space):
        if root_ch.type == 'VALUE':
            linear = replace_new_node(tree, ch, 'linear', 'ShaderNodeMath', 'Linear')
            #linear.inputs[0].default_value = ch.custom_value
            linear.inputs[1].default_value = 1.0
            linear.operation = 'POWER'
        elif root_ch.type == 'RGB':
            linear = replace_new_node(tree, ch, 'linear', 'ShaderNodeGamma', 'Linear')
            #if custom_value: col = custom_value
            #col = (ch.custom_color[0], ch.custom_color[1], ch.custom_color[2], 1.0)
            #linear.inputs[0].default_value = col

        #if root_ch.colorspace == 'SRGB' and (ch.tex_input == 'CUSTOM' or not ch.gamma_space):
        #if not ch.gamma_space:
        #    linear.inputs[1].default_value = 1.0 / GAMMA
        #else: linear.inputs[1].default_value = 1.0
        linear.inputs[1].default_value = 1.0 / GAMMA

    else:
        remove_node(tree, ch, 'linear')

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

    #if root_ch.type == 'NORMAL' and ch.tex_input == 'CUSTOM':
    #    source = replace_new_node(tree, ch, 'source', 'ShaderNodeRGB', 'Custom')
    #    col = (ch.custom_color[0], ch.custom_color[1], ch.custom_color[2], 1.0)
    #    source.outputs[0].default_value = col
    #else:
    #    remove_node(tree, ch, 'source')

#def update_custom_input(self, context):
#    tl = self.id_data.tl
#
#    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
#    tex = tl.textures[int(m.group(1))]
#    root_ch = tl.channels[int(m.group(2))]
#    tree = get_tree(tex)
#    ch = self
#
#    ch_source = tree.nodes.get(ch.source)
#    if ch_source:
#        if root_ch.type in {'RGB', 'NORMAL'}:
#            col = (ch.custom_color[0], ch.custom_color[1], ch.custom_color[2], 1.0)
#            ch_source.outputs[0].default_value = col
#        elif root_ch.type == 'VALUE':
#            ch_source.outputs[0].default_value = ch.custom_value
#
#    linear = tree.nodes.get(ch.linear)
#    if linear:
#        if root_ch.type == 'RGB':
#            col = (ch.custom_color[0], ch.custom_color[1], ch.custom_color[2], 1.0)
#            linear.inputs[0].default_value = col
#        elif root_ch.type == 'VALUE':
#            linear.inputs[0].default_value = ch.custom_value

def update_tex_input(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]
    tree = get_tree(tex)
    ch = self

    set_tex_channel_linear_node(tree, tex, root_ch, ch)

def update_uv_name(self, context):
    obj = context.object
    group_tree = self.id_data
    tl = group_tree.tl
    tex = self
    tree = get_tree(tex)
    if not tree: return

    nodes = tree.nodes

    uv_attr = nodes.get(tex.uv_attr)
    if uv_attr: uv_attr.attribute_name = tex.uv_name

    tangent = nodes.get(tex.tangent)
    if tangent: tangent.uv_map = tex.uv_name

    bitangent = nodes.get(tex.bitangent)
    if bitangent: bitangent.uv_map = tex.uv_name

    for ch in tex.channels:
        normal = nodes.get(ch.normal)
        if normal: normal.uv_map = tex.uv_name

    # Update uv layer
    if obj.type == 'MESH' and not any([m for m in tex.masks if m.active_edit]):
        if hasattr(obj.data, 'uv_textures'):
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        for i, uv in enumerate(uv_layers):
            if uv.name == tex.uv_name:
                if uv_layers.active_index != i:
                    uv_layers.active_index = i
                break

    # Update neighbor uv if mask bump is active
    rearrange = False
    for i, mask in enumerate(tex.masks):
        if set_mask_uv_neighbor(tree, tex, mask):
            rearrange = True

    if rearrange: #and not tl.halt_reconnect:
        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

def update_texcoord_type(self, context):
    tl = self.id_data.tl
    tex = self
    tree = get_tree(tex)

    # Check for normal channel for fine bump space switch
    # UV is using Tangent space
    # Generated, Normal, and object are using Object Space
    # Camera and Window are using View Space
    # Reflection actually aren't using view space, but whatever, no one use bump map in reflection texcoord
    #for i, ch in enumerate(tex.channels):
    #    root_ch = tl.channels[i]
    #    if root_ch.type == 'NORMAL':

    uv_neighbor = tree.nodes.get(tex.uv_neighbor)
    if uv_neighbor:
        cur_tree = uv_neighbor.node_tree
        sel_tree = lib.get_neighbor_uv_tree(tex.texcoord_type)

        if sel_tree != cur_tree:
            uv_neighbor.node_tree = sel_tree

            if cur_tree.users == 0:
                bpy.data.node_groups.remove(cur_tree)

            #if BLENDER_28_GROUP_INPUT_HACK:
            #    duplicate_lib_node_tree(uv_neighbor)

    #if not tl.halt_reconnect:
    reconnect_tex_nodes(self)

def update_texture_enable(self, context):
    group_tree = self.id_data
    tex = self
    tree = get_tree(tex)

    for i, ch in enumerate(tex.channels):
        #blend = tree.nodes.get(ch.blend)
        #blend.mute = not tex.enable or not ch.enable
        mute = not tex.enable or not ch.enable
        intensity = tree.nodes.get(ch.intensity)
        if intensity:
            intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

        if ch.enable_mask_ramp:
            #mr_blend = tree.nodes.get(ch.mr_blend)
            #if mr_blend: mr_blend.mute = blend.mute
            mr_intensity = tree.nodes.get(ch.mr_intensity)
            if mr_intensity: mr_intensity.inputs[1].default_value = 0.0 if mute else ch.mask_ramp_intensity_value

    context.window_manager.tltimer.time = str(time.time())

def update_channel_intensity_value(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch_index = int(m.group(2))
    root_ch = tl.channels[ch_index]

    if not tex.enable or not self.enable: return

    intensity = tree.nodes.get(self.intensity)
    intensity.inputs[1].default_value = self.intensity_value
    #intensity_multiplier = tree.nodes.get(self.intensity_multiplier)
    #intensity_multiplier.inputs[1].default_value = self.intensity_multiplier_value

    if self.enable_mask_ramp:
        flip_bump = any([c for c in tex.channels if c.mask_bump_flip and c.enable_mask_bump])
        if flip_bump:
            mr_intensity = tree.nodes.get(self.mr_intensity)
            mr_intensity.inputs[1].default_value = self.mask_ramp_intensity_value * self.intensity_value

            # Flip bump is better be muted if intensity is maximum
            mr_flip_hack = tree.nodes.get(self.mr_flip_hack)
            if mr_flip_hack:
                if self.intensity_value < 1.0:
                    mr_flip_hack.inputs[1].default_value = 1
                else: mr_flip_hack.inputs[1].default_value = 20

def update_texture_name(self, context):
    tl = self.id_data.tl
    src = get_tex_source(self)
    change_texture_name(tl, context.object, src, self, tl.textures)

class YLayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    tex_input = EnumProperty(
            name = 'Layer Input',
            #items = (('RGB', 'Color', ''),
            #         ('ALPHA', 'Alpha / Factor', '')),
            #default = 'RGB',
            items = tex_input_items,
            update = update_tex_input)

    gamma_space = BoolProperty(
            name='Gamma Space',
            description='Make sure texture input is in linear space',
            default = False,
            update = update_tex_input)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            items = tex_channel_normal_map_type_items,
            #default = 'BUMP_MAP',
            update = update_normal_map_type)

    blend_type = EnumProperty(
            name = 'Blend',
            items = blend_type_items,
            default = 'MIX',
            update = update_blend_type)

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX',
            update = update_blend_type)

    intensity_value = FloatProperty(
            name = 'Channel Intensity Factor', 
            description = 'Channel Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update = update_channel_intensity_value)

    # Modifiers
    modifiers = CollectionProperty(type=Modifier.YTextureModifier)

    # Blur
    #enable_blur = BoolProperty(default=False, update=Blur.update_tex_channel_blur)
    #blur = PointerProperty(type=Blur.YTextureBlur)

    invert_backface_normal = BoolProperty(default=False, update=update_flip_backface_normal)

    # Node names
    linear = StringProperty(default='')
    blend = StringProperty(default='')
    intensity = StringProperty(default='')
    source = StringProperty(default='')

    pipeline_frame = StringProperty(default='')

    # Modifier pipeline
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # Normal related
    bump = StringProperty(default='')
    fine_bump = StringProperty(default='')
    normal = StringProperty(default='')
    normal_flip = StringProperty(default='')

    bump_distance = FloatProperty(
            name='Bump Distance', 
            description= 'Distance of bump', 
            default=0.05, min=-1.0, max=1.0, precision=3, # step=1,
            update=update_bump_distance)

    bump_base_value = FloatProperty(
            name='Bump Base', 
            description= 'Base value of bump map', 
            default=0.5, min=0.0, max=1.0,
            update=update_bump_base_value)

    # Fine bump related
    neighbor_uv = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')

    # For some occasion, modifiers are stored in a tree
    mod_group = StringProperty(default='')
    mod_n = StringProperty(default='')
    mod_s = StringProperty(default='')
    mod_e = StringProperty(default='')
    mod_w = StringProperty(default='')

    # Bump bases
    bump_base = StringProperty(default='')
    bump_base_n = StringProperty(default='')
    bump_base_s = StringProperty(default='')
    bump_base_e = StringProperty(default='')
    bump_base_w = StringProperty(default='')

    # Bump hack
    #bump_hack = StringProperty(default='')
    #bump_hack_n = StringProperty(default='')
    #bump_hack_s = StringProperty(default='')
    #bump_hack_e = StringProperty(default='')
    #bump_hack_w = StringProperty(default='')

    # Intensity Stuff
    intensity_multiplier = StringProperty(default='')

    # Mask bump related
    enable_mask_bump = BoolProperty(name='Enable Mask Bump', description='Enable mask bump',
            default=False, update=transition.update_enable_transition_bump)

    mask_bump_value = FloatProperty(
        name = 'Mask Bump Value',
        description = 'Mask bump value',
        default=3.0, min=1.0, max=100.0, 
        update=transition.update_transition_bump_value)

    mask_bump_second_edge_value = FloatProperty(
            name = 'Second Edge Intensity', 
            description = 'Second Edge intensity value',
            default=1.2, min=1.0, max=100.0, 
            update=transition.update_transition_bump_value)

    mask_bump_distance = FloatProperty(
            name='Mask Bump Distance', 
            description= 'Distance of mask bump', 
            default=0.05, min=0.0, max=1.0, precision=3, # step=1,
            update=transition.update_transition_bump_distance)

    mask_bump_type = EnumProperty(
            name = 'Bump Type',
            #items = mask_bump_type_items,
            items = (
                ('BUMP_MAP', 'Bump', ''),
                ('FINE_BUMP_MAP', 'Fine Bump', ''),
                ('CURVED_BUMP_MAP', 'Curved Bump', ''),
                ),
            #default = 'FINE_BUMP_MAP',
            update=transition.update_enable_transition_bump)

    mask_bump_chain = IntProperty(
            name = 'Mask bump chain',
            description = 'Number of mask affected by transition bump',
            default=10, min=0, max=10,
            update=transition.update_transition_bump_chain)

    mask_bump_flip = BoolProperty(
            name = 'Mask Bump Flip',
            description = 'Mask bump flip',
            default=False,
            #update=Mask.update_mask_bump_flip)
            update=transition.update_enable_transition_bump)

    mask_bump_curved_offset = FloatProperty(
            name = 'Mask Bump Curved Offst',
            description = 'Mask bump curved offset',
            default=0.02, min=0.0, max=0.1,
            #update=Mask.update_mask_bump_flip)
            update=transition.update_transition_bump_curved_offset)

    mb_bump = StringProperty(default='')
    mb_fine_bump = StringProperty(default='')
    mb_curved_bump = StringProperty(default='')
    mb_inverse = StringProperty(default='')
    mb_intensity_multiplier = StringProperty(default='')
    mb_blend = StringProperty(default='')

    mb_neighbor_uv = StringProperty(default='')
    mb_source_n = StringProperty(default='')
    mb_source_s = StringProperty(default='')
    mb_source_e = StringProperty(default='')
    mb_source_w = StringProperty(default='')
    mb_mod_n = StringProperty(default='')
    mb_mod_s = StringProperty(default='')
    mb_mod_e = StringProperty(default='')
    mb_mod_w = StringProperty(default='')

    # Transition ramp related
    enable_mask_ramp = BoolProperty(name='Enable Transition Ramp', description='Enable alpha transition ramp', 
            default=False, update=transition.update_enable_transition_ramp)

    mask_ramp_intensity_value = FloatProperty(
            name = 'Channel Intensity Factor', 
            description = 'Channel Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_ramp_intensity_value)

    mask_ramp_blend_type = EnumProperty(
        name = 'Transition Ramp Blend Type',
        items = blend_type_items,
        default = 'MIX', update=transition.update_transition_ramp_blend_type)

    # Transition ramp nodes
    mr_ramp = StringProperty(default='')
    mr_linear = StringProperty(default='')
    mr_inverse = StringProperty(default='')
    mr_alpha = StringProperty(default='')
    mr_intensity_multiplier = StringProperty(default='')
    mr_intensity = StringProperty(default='')
    mr_blend = StringProperty(default='')

    # For flip transition bump
    mr_alpha1 = StringProperty(default='')
    mr_flip_hack = StringProperty(default='')
    mr_flip_blend = StringProperty(default='')

    # Transition AO related
    enable_transition_ao = BoolProperty(name='Enable Transition AO', 
            description='Enable alpha transition Ambient Occlusion (Need active transition bump)', default=False,
            update=transition.update_enable_transition_ao)

    transition_ao_edge = FloatProperty(name='Transition AO Edge',
            #description='Transition AO edge power (higher value means less AO)', min=1.0, max=100.0, default=4.0,
            description='Transition AO edge power', min=1.0, max=100.0, default=4.0,
            update=transition.update_transition_ao_edge)

    transition_ao_intensity = FloatProperty(name='Transition AO Intensity',
            description='Transition AO intensity', subtype='FACTOR', min=0.0, max=1.0, default=0.5,
            update=transition.update_transition_ao_intensity)

    transition_ao_color = FloatVectorProperty(name='Transition AO Color', description='Transition AO Color', 
            subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0),
            update=transition.update_transition_ao_color)

    tao = StringProperty(default='')

    # For UI
    expand_bump_settings = BoolProperty(default=False)
    expand_intensity_settings = BoolProperty(default=False)
    expand_content = BoolProperty(default=False)
    expand_mask_settings = BoolProperty(default=False)
    expand_transition_ramp_settings = BoolProperty(default=False)
    expand_transition_ao_settings = BoolProperty(default=False)
    expand_input_settings = BoolProperty(default=False)

def update_layer_color_chortcut(self, context):
    tex = self

    # If color shortcut is active, disable other shortcut
    if tex.type == 'COLOR' and tex.color_shortcut:

        for m in tex.modifiers:
            m.shortcut = False

        for ch in tex.channels:
            for m in ch.modifiers:
                m.shortcut = False

class YTextureLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='', update=update_texture_name)
    enable = BoolProperty(
            name = 'Enable Texture', description = 'Enable texture',
            default=True, update=update_texture_enable)
    channels = CollectionProperty(type=YLayerChannel)

    group_node = StringProperty(default='')

    start = StringProperty(default='')
    end = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'IMAGE')

    color_shortcut = BoolProperty(
            name = 'Color Shortcut on the list',
            description = 'Display color shortcut on the list',
            default=True,
            update=update_layer_color_chortcut)

    texcoord_type = EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_texcoord_type)

    # To detect change of texture image
    image_name = StringProperty(default='')

    uv_name = StringProperty(default='', update=update_uv_name)

    # Parent index
    parent_idx = IntProperty(default=-1)

    # Sources
    source = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')
    source_group = StringProperty(default='')

    # Layer type cache
    cache_brick = StringProperty(default='')
    cache_checker = StringProperty(default='')
    cache_gradient = StringProperty(default='')
    cache_magic = StringProperty(default='')
    cache_musgrave = StringProperty(default='')
    cache_noise = StringProperty(default='')
    cache_voronoi = StringProperty(default='')
    cache_wave = StringProperty(default='')
    cache_color = StringProperty(default='')

    # UV
    uv_neighbor = StringProperty(default='')
    uv_attr = StringProperty(default='')
    mapping = StringProperty(default='')

    # Other Vectors
    solid_alpha = StringProperty(default='')
    texcoord = StringProperty(default='')
    #uv_map = StringProperty(default='')
    tangent = StringProperty(default='')
    hacky_tangent = StringProperty(default='')
    bitangent = StringProperty(default='')
    geometry = StringProperty(default='')

    # Modifiers
    modifiers = CollectionProperty(type=Modifier.YTextureModifier)
    mod_group = StringProperty(default='')
    mod_group_1 = StringProperty(default='')

    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # Mask
    enable_masks = BoolProperty(name='Enable Texture Masks', description='Enable texture masks',
            default=True, update=Mask.update_enable_texture_masks)
    masks = CollectionProperty(type=Mask.YTextureMask)

    ## Transition 
    #enable_transition_bg = BoolProperty(name='Enable Transition to Background', 
    #        description='Enable transition to background (Useful to force transparency)', default=False)

    # UI related
    expand_content = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)
    expand_masks = BoolProperty(default=False)
    expand_channels = BoolProperty(default=True)
    expand_source = BoolProperty(default=False)

def register():
    bpy.utils.register_class(YRefreshNeighborUV)
    bpy.utils.register_class(YNewTextureLayer)
    bpy.utils.register_class(YOpenImageToLayer)
    bpy.utils.register_class(YOpenAvailableImageToLayer)
    bpy.utils.register_class(YMoveTextureLayer)
    bpy.utils.register_class(YMoveInOutLayerGroup)
    bpy.utils.register_class(YMoveInOutLayerGroupMenu)
    bpy.utils.register_class(YRemoveLayer)
    bpy.utils.register_class(YRemoveLayerMenu)
    bpy.utils.register_class(YReplaceLayerType)
    bpy.utils.register_class(YLayerChannel)
    bpy.utils.register_class(YTextureLayer)

def unregister():
    bpy.utils.unregister_class(YRefreshNeighborUV)
    bpy.utils.unregister_class(YNewTextureLayer)
    bpy.utils.unregister_class(YOpenImageToLayer)
    bpy.utils.unregister_class(YOpenAvailableImageToLayer)
    bpy.utils.unregister_class(YMoveTextureLayer)
    bpy.utils.unregister_class(YMoveInOutLayerGroup)
    bpy.utils.unregister_class(YMoveInOutLayerGroupMenu)
    bpy.utils.unregister_class(YRemoveLayer)
    bpy.utils.unregister_class(YRemoveLayerMenu)
    bpy.utils.unregister_class(YReplaceLayerType)
    bpy.utils.unregister_class(YLayerChannel)
    bpy.utils.unregister_class(YTextureLayer)
