import bpy, time, re
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import Modifier, lib, Blur, Mask, transition, ImageAtlas
from .common import *
from .node_arrangements import *
from .node_connections import *
from .subtree import *

DEFAULT_NEW_IMG_SUFFIX = ' Layer'
DEFAULT_NEW_VCOL_SUFFIX = ' VCol'

def check_all_layer_channel_io_and_nodes(layer, tree=None, specific_ch=None): #, has_parent=False):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    # Check uv maps
    check_uv_nodes(yp)

    # Check layer tree io
    check_layer_tree_ios(layer, tree)

    # Mapping node
    if layer.type not in {'BACKGROUND', 'VCOL', 'GROUP', 'COLOR'}:
        source_tree = get_source_tree(layer, tree)
        mapping = source_tree.nodes.get(layer.mapping)
        if not mapping:
            mapping = new_node(source_tree, layer, 'mapping', 'ShaderNodeMapping', 'Mapping')

    # Channel nodes
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]

        # Displacement blend node
        #if root_ch.type == 'NORMAL' and root_ch.enable_displacement:
        #    disp_blend = tree.nodes.get(ch.disp_blend)
        #    if not disp_blend:
        #        disp_blend = new_node(tree, ch, 'disp_blend', 'ShaderNodeMixRGB', 'Displacement Blend')

        #    #if ch.normal_blend == 'MIX':
        #    #    disp_blend.blend_type = 'MIX'
        #    #elif ch.normal_blend == 'OVERLAY':
        #    #    disp_blend.blend_type = 'ADD'
        #else:
        #    remove_node(tree, ch, 'disp_blend')

        if ch.enable_transition_ramp:
            transition.check_transition_ramp_nodes(tree, layer, ch)

        if ch.enable_transition_ao:
            bump_ch = get_transition_bump_channel(layer)
            transition.check_transition_ao_nodes(tree, layer, ch, bump_ch)

        # Update layer ch blend type
        check_blend_type_nodes(root_ch, layer, ch)

        # Normal related nodes created by it's normal map type
        if root_ch.type == 'NORMAL':
            check_channel_normal_map_nodes(tree, layer, root_ch, ch)

def channel_items(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp

    items = []

    for i, ch in enumerate(yp.channels):
        if hasattr(lib, 'custom_icons'):
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, i))
        else: items.append((str(i), ch.name, '', lib.channel_icon_dict[ch.type], i))

    if hasattr(lib, 'custom_icons'):
        items.append(('-1', 'All Channels', '', lib.custom_icons['channels'].icon_id, len(items)))
    else: items.append(('-1', 'All Channels', '', 'GROUP_VERTEX', len(items)))

    return items

def layer_input_items(self, context):
    yp = self.id_data.yp

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    if not m: return []
    layer = yp.layers[int(m.group(1))]
    #root_ch = yp.channels[int(m.group(2))]

    items = []

    label = layer_type_labels[layer.type]

    items.append(('RGB', label + ' Color',  ''))
    items.append(('ALPHA', label + ' Factor',  ''))
        
    #if layer.type == 'IMAGE':
    #    items.append(('ALPHA', label + ' Alpha',  ''))
    #else: items.append(('ALPHA', label + ' Factor',  ''))

    #if root_ch.type in {'RGB', 'NORMAL'}:
    #    items.append(('CUSTOM', 'Custom Color',  ''))
    #elif root_ch.type == 'VALUE':
    #    items.append(('CUSTOM', 'Custom Value',  ''))

    return items

def normal_map_type_items_(layer_type):
    items = []

    if bpy.app.version_string.startswith('2.8'):
        items.append(('NORMAL_MAP', 'Normal Map', ''))
        items.append(('BUMP_MAP', 'Bump Map', ''))
        #if layer_type != 'VCOL':
        items.append(('FINE_BUMP_MAP', 'Fine Bump Map', ''))
    else: 
        items.append(('NORMAL_MAP', 'Normal Map', '', 'MATCAP_23', 0))
        items.append(('BUMP_MAP', 'Bump Map', '', 'MATCAP_09', 1))
        #if layer_type != 'VCOL':
        items.append(('FINE_BUMP_MAP', 'Fine Bump Map', '', 'MATCAP_09', 2))

    return items

def layer_channel_normal_map_type_items(self, context):
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    yp = self.id_data.yp
    layer = yp.layers[int(m.group(1))]
    return normal_map_type_items_(layer.type)

def new_layer_channel_normal_map_type_items(self, context):
    return normal_map_type_items_(self.type)

def img_normal_map_type_items(self, context):
    return normal_map_type_items_('IMAGE')

def add_new_layer(group_tree, layer_name, layer_type, channel_idx, 
        blend_type, normal_blend, normal_map_type, 
        texcoord_type, uv_name='', image=None, vcol=None, segment=None,
        add_rgb_to_intensity=False, rgb_to_intensity_color=(1,1,1),
        solid_color = (1,1,1),
        add_mask=False, mask_type='IMAGE', mask_color='BLACK', mask_use_hdr=False, 
        mask_uv_name = '', mask_width=1024, mask_height=1024, use_image_atlas_for_mask=False
        ):

    yp = group_tree.yp
    #ypup = bpy.context.user_preferences.addons[__package__].preferences
    obj = bpy.context.object

    # Halt rearrangements and reconnections until all nodes already created
    yp.halt_reconnect = True

    # Get parent dict
    parent_dict = get_parent_dict(yp)

    # Get active layer
    try: active_layer = yp.layers[yp.active_layer_index]
    except: active_layer = None

    # Get a possible parent layer group
    parent_layer = None
    if active_layer: 
        if active_layer.type == 'GROUP':
            parent_layer = active_layer
        elif active_layer.parent_idx != -1:
            parent_layer = yp.layers[active_layer.parent_idx]

    # Get parent index
    if parent_layer: 
        parent_idx = get_layer_index(parent_layer)
        has_parent = True
    else: 
        parent_idx = -1
        has_parent = False

    # Add layer to group
    layer = yp.layers.add()
    layer.type = layer_type
    layer.name = layer_name
    layer.uv_name = uv_name

    if segment:
        layer.segment_name = segment.name

    if image:
        layer.image_name = image.name

    # Move new layer to current index
    last_index = len(yp.layers)-1
    if active_layer and active_layer.type == 'GROUP':
        index = yp.active_layer_index + 1
    else: index = yp.active_layer_index

    # Set parent index
    parent_dict = set_parent_dict_val(yp, parent_dict, layer.name, parent_idx)

    yp.layers.move(last_index, index)
    layer = yp.layers[index] # Repoint to new index

    # Remap other layers parent
    #for i, lay in enumerate(yp.layers):
    #    if i > index and lay.parent_idx != -1:
    #        lay.parent_idx += 1

    # Remap parents
    for lay in yp.layers:
        lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

    # New layer tree
    tree = bpy.data.node_groups.new(LAYERGROUP_PREFIX + layer_name, 'ShaderNodeTree')
    tree.yp.is_ypaint_layer_node = True
    tree.yp.version = get_current_version_str()

    # New layer node group
    group_node = new_node(group_tree, layer, 'group_node', 'ShaderNodeGroup', layer_name)
    group_node.node_tree = tree

    # Create info nodes
    create_info_nodes(tree)

    # Tree start and end
    create_essential_nodes(tree, True, False, True)

    # Add source
    source = new_node(tree, layer, 'source', layer_node_bl_idnames[layer_type], 'Source')

    if layer_type == 'IMAGE':
        # Always set non color to image node because of linear pipeline
        source.color_space = 'NONE'

        # Add new image if it's image layer
        source.image = image

    elif layer_type == 'VCOL':
        source.attribute_name = vcol.name

    elif layer_type == 'COLOR':
        col = (solid_color[0], solid_color[1], solid_color[2], 1.0)
        source.outputs[0].default_value = col

    # Add uv map node
    #uv_map = new_node(tree, layer, 'uv_map', 'ShaderNodeUVMap', 'UV Map')
    #uv_map.uv_map = uv_name

    #uv_map = new_node(tree, layer, 'uv_map', 'NodeGroupInput', 'UV Map Inputs')
    texcoord = new_node(tree, layer, 'texcoord', 'NodeGroupInput', 'TexCoord Inputs')

    # Add tangent and bitangent node
    #tangent = new_node(tree, layer, 'tangent', 'ShaderNodeTangent', 'Source Tangent')
    #tangent.direction_type = 'UV_MAP'
    #tangent.uv_map = uv_name

    #tangent = new_node(tree, layer, 'tangent', 'ShaderNodeNormalMap', 'Tangent')
    #tangent.uv_map = uv_name
    #tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)

    #tangent_flip = new_node(tree, layer, 'tangent_flip', 'ShaderNodeGroup', 'Tangent Backface Flip')
    #tangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_TANGENT)

    #set_tangent_backface_flip(tangent_flip, yp.flip_backface)

    #bitangent = new_node(tree, layer, 'bitangent', 'ShaderNodeNormalMap', 'Bitangent')
    #bitangent.uv_map = uv_name
    #bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)

    #bitangent_flip = new_node(tree, layer, 'bitangent_flip', 'ShaderNodeGroup', 'Bitangent Backface Flip')
    #bitangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_BITANGENT)

    #set_bitangent_backface_flip(bitangent_flip, yp.flip_backface)

    #hacky_tangent = new_node(tree, layer, 'hacky_tangent', 'ShaderNodeNormalMap', 'Hacky Source Tangent')
    #hacky_tangent.uv_map = uv_name
    #hacky_tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)

    #bitangent = new_node(tree, layer, 'bitangent', 'ShaderNodeGroup', 'Source Bitangent')
    #bitangent.node_tree = get_node_tree_lib(lib.GET_BITANGENT)

    # Set layer coordinate type
    layer.texcoord_type = texcoord_type

    # Add channels to current layer
    for root_ch in yp.channels:
        ch = layer.channels.add()

    if add_mask:

        mask_name = 'Mask ' + layer.name
        mask_image = None
        mask_vcol = None
        mask_segment = None

        if mask_type == 'IMAGE':
            if use_image_atlas_for_mask:
                mask_segment = ImageAtlas.get_set_image_atlas_segment(
                        mask_width, mask_height, mask_color, mask_use_hdr) #, ypup.image_atlas_size)
                mask_image = mask_segment.id_data
            else:
                mask_image = bpy.data.images.new(mask_name, 
                        width=mask_width, height=mask_height, alpha=False, float_buffer=mask_use_hdr)
                if mask_color == 'WHITE':
                    mask_image.generated_color = (1,1,1,1)
                elif mask_color == 'BLACK':
                    mask_image.generated_color = (0,0,0,1)
                #mask_image.generated_color = (0,0,0,1)
                mask_image.use_alpha = False

        # New vertex color
        elif mask_type == 'VCOL':
            mask_vcol = obj.data.vertex_colors.new(name=mask_name)
            if mask_color == 'WHITE':
                set_obj_vertex_colors(obj, mask_vcol, (1.0, 1.0, 1.0))
            elif mask_color == 'BLACK':
                set_obj_vertex_colors(obj, mask_vcol, (0.0, 0.0, 0.0))
            #set_obj_vertex_colors(obj, mask_vcol, (0.0, 0.0, 0.0))

        mask = Mask.add_new_mask(layer, mask_name, mask_type, 'UV', #texcoord_type, 
                mask_uv_name, mask_image, mask_vcol, mask_segment)
        mask.active_edit = True

        #if mask_segment:
        #    scale_x = mask_width/mask_image.size[0]
        #    scale_y = mask_height/mask_image.size[1]

        #    offset_x = scale_x * mask_segment.tile_x
        #    offset_y = scale_y * mask_segment.tile_y

        #    mapping = get_mask_mapping(mask)
        #    if mapping:
        #        mapping.scale[0] = scale_x
        #        mapping.scale[1] = scale_y

        #        mapping.translation[0] = offset_x
        #        mapping.translation[1] = offset_y

        #    refresh_temp_uv(obj, mask)

    # Fill channel layer props
    shortcut_created = False
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        # Set some props to selected channel
        if layer.type in {'GROUP', 'BACKGROUND'} or channel_idx == i or channel_idx == -1:
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

        # Set linear node of layer channel
        #if root_ch.type == 'NORMAL':
        #    set_layer_channel_linear_node(tree, layer, root_ch, ch, custom_value=(0.5,0.5,1))
        #else: set_layer_channel_linear_node(tree, layer, root_ch, ch)
        set_layer_channel_linear_node(tree, layer, root_ch, ch)

    # Check and create layer channel nodes
    check_all_layer_channel_io_and_nodes(layer, tree) #, has_parent=has_parent)

    # Refresh paint image by updating the index
    yp.active_layer_index = index

    # Unhalt rearrangements and reconnections since all nodes already created
    yp.halt_reconnect = False

    # Rearrange node inside layers
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    return layer

def update_channel_idx_new_layer(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp

    if self.channel_idx == '-1':
        self.rgb_to_intensity_color = (1,1,1)
        return

    if hasattr(self, 'rgb_to_intensity_color'):
        for i, ch in enumerate(yp.channels):
            if self.channel_idx == str(i):
                if ch.type == 'RGB':
                    self.rgb_to_intensity_color = (1,0,1)
                else: self.rgb_to_intensity_color = (1,1,1)

def get_fine_bump_distance(layer, distance):
    scale = 200
    #if layer.type == 'IMAGE':
    #    source = get_layer_source(layer)
    #    image = source.image
    #    if image: scale = image.size[0] / 10

    #return -1.0 * distance * scale
    return distance * scale

class YRefreshNeighborUV(bpy.types.Operator):
    """Refresh Neighbor UV"""
    bl_idname = "node.y_refresh_neighbor_uv"
    bl_label = "Refresh Neighbor UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer') and hasattr(context, 'channel') and hasattr(context, 'image') and context.image

    def execute(self, context):
        set_uv_neighbor_resolution(context.layer)
        return {'FINISHED'}

class YNewLayer(bpy.types.Operator):
    bl_idname = "node.y_new_layer"
    bl_label = "New Layer"
    bl_description = "New Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    # For image layer
    width = IntProperty(name='Width', default = 1024, min=1, max=4096)
    height = IntProperty(name='Height', default = 1024, min=1, max=4096)
    #color = FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    #alpha = BoolProperty(name='Alpha', default=True)
    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_layer)

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
            description = 'Add RGB To Intensity modifier to all channels of newly created layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    solid_color = FloatVectorProperty(
            name='Solid Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    add_mask = BoolProperty(
            name = 'Add Mask',
            description = 'Add mask to new layer',
            default = False)

    mask_type = EnumProperty(
            name = 'Mask Type',
            description = 'Mask type',
            items = (('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
                ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1)),
            default = 'IMAGE')

    mask_color = EnumProperty(
            name = 'Mask Color',
            description = 'Mask Color',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='BLACK')

    mask_width = IntProperty(name='Mask Width', default = 1024, min=1, max=4096)
    mask_height = IntProperty(name='Mask Height', default = 1024, min=1, max=4096)

    mask_uv_name = StringProperty(default='')
    mask_use_hdr = BoolProperty(name='32 bit Float', default=False)

    uv_map = StringProperty(default='')

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = new_layer_channel_normal_map_type_items)
            #default = 'BUMP_MAP')

    use_image_atlas = BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    use_image_atlas_for_mask = BoolProperty(
            name = 'Use Image Atlas for Mask',
            description='Use Image Atlas for Mask',
            default=False)

    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()
        #return hasattr(context, 'group_node') and context.group_node

    def invoke(self, context, event):

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if self.type == 'IMAGE':
            name = obj.active_material.name + DEFAULT_NEW_IMG_SUFFIX
            items = bpy.data.images
        elif self.type == 'VCOL' and obj.type == 'MESH':
            name = obj.active_material.name + DEFAULT_NEW_VCOL_SUFFIX
            items = obj.data.vertex_colors
        else:
            name = [i[1] for i in layer_type_items if i[0] == self.type][0]
            items = yp.layers

        # Make sure add rgb to intensity is inactive
        if self.type != 'IMAGE':
            self.add_rgb_to_intensity = False

        # Make sure add rgb to intensity is inactive
        if self.type not in {'COLOR', 'BACKGROUND', 'GROUP'}:
            self.add_mask = False

        # Default normal map type is fine bump map
        self.normal_map_type = 'FINE_BUMP_MAP'

        # Layer name
        self.name = get_unique_name(name, items)

        # Layer name must also unique
        if self.type == 'IMAGE':
            self.name = get_unique_name(self.name, yp.layers)

        if obj.type != 'MESH':
            #self.texcoord_type = 'Object'
            self.texcoord_type = 'Generated'
        else:
            # Use active uv layer name by default
            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            # Use active uv layer name by default
            if obj.type == 'MESH' and len(uv_layers) > 0:
                active_name = uv_layers.active.name
                if active_name == TEMP_UV:
                    self.uv_map = yp.layers[yp.active_layer_index].uv_name
                else: self.uv_map = uv_layers.active.name

                self.mask_uv_name = self.uv_map

                # UV Map collections update
                self.uv_map_coll.clear()
                for uv in obj.data.uv_layers:
                    if not uv.name.startswith(TEMP_UV):
                        self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def get_to_be_cleared_image_atlas(self, context):
        if self.type == 'IMAGE' and not self.add_mask and self.use_image_atlas:
            return ImageAtlas.check_need_of_erasing_segments('TRANSPARENT', self.width, self.height, self.hdr)
        if self.add_mask and self.mask_type == 'IMAGE' and self.use_image_atlas_for_mask:
            return ImageAtlas.check_need_of_erasing_segments(self.mask_color, self.mask_width, self.mask_height, self.hdr)

        return None

    def draw(self, context):
        #yp = self.group_node.node_tree.yp
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        if len(yp.channels) == 0:
            self.layout.label(text='No channel found! Still want to create a layer?', icon='ERROR')
            return

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        if bpy.app.version_string.startswith('2.8'):
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)
        col = row.column(align=False)

        col.label(text='Name:')

        if self.type not in {'GROUP', 'BACKGROUND'}:
            col.label(text='Channel:')
            if channel and channel.type == 'NORMAL':
                col.label(text='Type:')

        if self.type == 'COLOR':
            col.label(text='Color:')

        if self.type == 'IMAGE':
            col.label(text='')

        if self.add_rgb_to_intensity:
            col.label(text='RGB To Intensity Color:')

        if self.type == 'IMAGE':
            #if not self.add_rgb_to_intensity:
            #    col.label(text='Color:')
            col.label(text='')
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type not in {'VCOL', 'GROUP', 'COLOR', 'BACKGROUND'}:
            col.label(text='Vector:')

        if self.type == 'IMAGE':
            col.label(text='')

        #if self.type in {'COLOR', 'GROUP', 'BACKGROUND'}:
        if self.type != 'IMAGE':
            col.label(text='')
            if self.add_mask:
                col.label(text='Mask Type:')
                col.label(text='Mask Color:')
                if self.mask_type == 'IMAGE':
                    col.label(text='')
                    col.label(text='Mask Width:')
                    col.label(text='Mask Height:')
                    col.label(text='Mask UV Map:')
                    col.label(text='')

        col = row.column(align=False)
        col.prop(self, 'name', text='')

        if self.type not in {'GROUP', 'BACKGROUND'}:
            rrow = col.row(align=True)
            rrow.prop(self, 'channel_idx', text='')
            if channel:
                if channel.type == 'NORMAL':
                    rrow.prop(self, 'normal_blend', text='')
                    col.prop(self, 'normal_map_type', text='')
                else: 
                    rrow.prop(self, 'blend_type', text='')

        if self.type == 'COLOR':
            col.prop(self, 'solid_color', text='')

        if self.type == 'IMAGE':
            col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

        if self.type == 'IMAGE':
            #if not self.add_rgb_to_intensity:
            #    col.prop(self, 'color', text='')
                #col.prop(self, 'alpha')
            col.prop(self, 'hdr')
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type not in {'VCOL', 'GROUP', 'COLOR', 'BACKGROUND'}:
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if self.type == 'IMAGE':
            col.prop(self, 'use_image_atlas')

        if self.type != 'IMAGE':
            col.prop(self, 'add_mask', text='Add Mask')
            if self.add_mask:
                col.prop(self, 'mask_type', text='')
                col.prop(self, 'mask_color', text='')
                if self.mask_type == 'IMAGE':
                    col.prop(self, 'mask_use_hdr')
                    col.prop(self, 'mask_width', text='')
                    col.prop(self, 'mask_height', text='')
                    #col.prop_search(self, "mask_uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                    col.prop_search(self, "mask_uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
                    col.prop(self, 'use_image_atlas_for_mask', text='Use Image Atlas')

        if self.get_to_be_cleared_image_atlas(context):
            col = self.layout.column(align=True)
            col.label(text='INFO: An unused atlas segment can be used.', icon='ERROR')
            col.label(text='It will take a couple seconds to clear.')

    def execute(self, context):

        T = time.time()

        #ypup = bpy.context.user_preferences.addons[__package__].preferences
        wm = context.window_manager
        area = context.area
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypui = context.window_manager.ypui

        # Check if object is not a mesh
        if (self.type == 'VCOL' or (self.add_mask and self.mask_type == 'VCOL')) and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color only works with mesh object!")
            return {'CANCELLED'}

        if (    ((self.type == 'VCOL' or (self.add_mask and self.mask_type == 'VCOL')) 
                and len(obj.data.vertex_colors) >= 8) 
            or
                ((self.type == 'VCOL' and (self.add_mask and self.mask_type == 'VCOL')) 
                and len(obj.data.vertex_colors) >= 7)
            ):
            self.report({'ERROR'}, "Mesh can only use 8 vertex colors!")
            return {'CANCELLED'}

        # Check if layer with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in obj.data.vertex_colors if i.name == self.name]
        else: same_name = [lay for lay in yp.layers if lay.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
            elif self.type == 'VCOL':
                self.report({'ERROR'}, "Vertex Color named '" + self.name +"' is already available!")
            self.report({'ERROR'}, "Layer named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Clearing unused image atlas segments
        img_atlas = self.get_to_be_cleared_image_atlas(context)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        img = None
        segment = None
        if self.type == 'IMAGE':

            if self.use_image_atlas:
                segment = ImageAtlas.get_set_image_atlas_segment(
                        self.width, self.height, 'TRANSPARENT', self.hdr) #, ypup.image_atlas_size)
                img = segment.id_data
            else:

                alpha = False if self.add_rgb_to_intensity else True
                #color = (0,0,0,1) if self.add_rgb_to_intensity else self.color
                color = (0,0,0,1) if self.add_rgb_to_intensity else (0,0,0,0)
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

        yp.halt_update = True

        layer = add_new_layer(node.node_tree, self.name, self.type, 
                int(self.channel_idx), self.blend_type, self.normal_blend, 
                self.normal_map_type, self.texcoord_type, self.uv_map, img, vcol, segment,
                self.add_rgb_to_intensity, self.rgb_to_intensity_color, self.solid_color,
                self.add_mask, self.mask_type, self.mask_color, self.mask_use_hdr, 
                self.mask_uv_name, self.mask_width, self.mask_height, self.use_image_atlas_for_mask)

        if segment:
            #layer.segment_name = segment.name

            scale_x = self.width/img.size[0]
            scale_y = self.height/img.size[1]

            offset_x = scale_x * segment.tile_x
            offset_y = scale_y * segment.tile_y

            mapping = get_layer_mapping(layer)
            if mapping:
                mapping.scale[0] = scale_x
                mapping.scale[1] = scale_y

                mapping.translation[0] = offset_x
                mapping.translation[1] = offset_y

            refresh_temp_uv(obj, layer)

        yp.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_yp_layer_nodes(node.node_tree)
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        if self.type != 'IMAGE':
            ypui.layer_ui.expand_content = True
        ypui.need_update = True

        print('INFO: Layer', layer.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenImageToLayer(bpy.types.Operator, ImportHelper):
    """Open Image to Layer"""
    bl_idname = "node.y_open_image_to_layer"
    bl_label = "Open Image to Layer"
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
            description = 'Channel of new layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_layer)

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
            description = 'Add RGB To Intensity modifier to all channels of newly created layer',
            default=False)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = img_normal_map_type_items)
            #default = 'NORMAL_MAP')

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            active_name = obj.data.uv_layers.active.name
            if active_name == TEMP_UV:
                self.uv_map = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_map = obj.data.uv_layers.active.name

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # Normal map is the default
        self.normal_map_type = 'NORMAL_MAP'

        #return context.window_manager.invoke_props_dialog(self)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        
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
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

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
        node = get_active_ypaint_node()

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        node.node_tree.yp.halt_update = True

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            add_new_layer(node.node_tree, image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                    self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map,
                    image, None, None, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.yp.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_yp_layer_nodes(node.node_tree)
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableDataToLayer(bpy.types.Operator):
    """Open Available Data to Layer"""
    bl_idname = "node.y_open_available_data_to_layer"
    bl_label = "Open Available Data to Layer"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Layer Type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_layer)

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
            description = 'Add RGB To Intensity modifier to all channels of newly created layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = img_normal_map_type_items)
            #default = 'BUMP_MAP')

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name = StringProperty(name="Vertex Color")
    vcol_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            if obj.data.uv_layers.active.name == TEMP_UV:
                self.uv_map = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_map = obj.data.uv_layers.active.name

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        if self.type == 'VCOL':
            self.add_rgb_to_intensity = False

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            for img in imgs:
                if not img.yia.is_image_atlas:
                    self.image_coll.add().name = img.name
        elif self.type == 'VCOL':
            self.vcol_coll.clear()
            vcols = obj.data.vertex_colors
            for vcol in vcols:
                self.vcol_coll.add().name = vcol.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        if self.type == 'IMAGE':
            self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        elif self.type == 'VCOL':
            self.layout.prop_search(self, "vcol_name", self, "vcol_coll", icon='GROUP_VCOL')
        
        row = self.layout.row()

        col = row.column()
        if self.type == 'IMAGE':
            col.label(text='Vector:')
        col.label(text='Channel:')
        if channel and channel.type == 'NORMAL':
            col.label(text='Type:')

        if self.type == 'IMAGE' and self.add_rgb_to_intensity:
            col.label(text='')
            col.label(text='RGB2I Color:')

        col = row.column()

        if self.type == 'IMAGE':
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        #col.label(text='')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        if self.type == 'IMAGE':
            col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

            if self.add_rgb_to_intensity:
                col.prop(self, 'rgb_to_intensity_color', text='')

    def execute(self, context):
        T = time.time()

        obj = context.object
        wm = context.window_manager
        node = get_active_ypaint_node()

        if self.type == 'IMAGE' and self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}
        elif self.type == 'VCOL' and self.vcol_name == '':
            self.report({'ERROR'}, "No vertex color selected!")
            return {'CANCELLED'}

        node.node_tree.yp.halt_update = True

        image = None
        vcol = None
        if self.type == 'IMAGE':
            image = bpy.data.images.get(self.image_name)
            name = image.name
        elif self.type == 'VCOL':
            vcol = obj.data.vertex_colors.get(self.vcol_name)
            name = vcol.name

        add_new_layer(node.node_tree, name, self.type, int(self.channel_idx), self.blend_type, 
                self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map, 
                image, vcol, None, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.yp.halt_update = False

        # Reconnect and rearrange nodes
        #reconnect_yp_layer_nodes(node.node_tree)
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image', self.image_name, 'is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YMoveInOutLayerGroup(bpy.types.Operator):
    bl_idname = "node.y_move_in_out_layer_group"
    bl_label = "Move In/Out Layer Group"
    bl_description = "Move in or out layer group"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        num_layers = len(yp.layers)
        layer_idx = yp.active_layer_index
        layer = yp.layers[layer_idx]

        # Remember parent
        parent_dict = get_parent_dict(yp)
        
        # Move image slot
        if self.direction == 'UP':
            neighbor_idx, neighbor_layer = get_upper_neighbor(layer)
        elif self.direction == 'DOWN' and layer_idx < num_layers-1:
            neighbor_idx, neighbor_layer = get_lower_neighbor(layer)
        else:
            neighbor_idx = -1
            neighbor_layer = None

        # Move outside up
        if is_top_member(layer) and self.direction == 'UP':
            #print('Case 1')

            parent_dict = set_parent_dict_val(yp, parent_dict, layer.name, neighbor_layer.parent_idx)

            last_member_idx = get_last_child_idx(layer)
            yp.layers.move(neighbor_idx, last_member_idx)

            yp.active_layer_index = neighbor_idx

        # Move outside down
        elif is_bottom_member(layer) and self.direction == 'DOWN':
            #print('Case 2')

            parent_dict = set_parent_dict_val(yp, parent_dict, layer.name, yp.layers[layer.parent_idx].parent_idx)

        elif neighbor_layer and neighbor_layer.type == 'GROUP':

            # Move inside up
            if self.direction == 'UP':
                #print('Case 3')

                parent_dict = set_parent_dict_val(yp, parent_dict, layer.name, neighbor_idx)

            # Move inside down
            elif self.direction == 'DOWN':
                #print('Case 4')

                parent_dict = set_parent_dict_val(yp, parent_dict, layer.name, neighbor_idx)

                yp.layers.move(neighbor_idx, layer_idx)
                yp.active_layer_index = layer_idx+1

        # Remap parents
        for lay in yp.layers:
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        layer = yp.layers[yp.active_layer_index]
        #has_parent = layer.parent_idx != -1

        #if layer.type == 'GROUP' or has_parent:
        check_all_layer_channel_io_and_nodes(layer) #, has_parent=has_parent)
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        # Refresh layer channel blend nodes
        rearrange_yp_nodes(node.node_tree)
        reconnect_yp_nodes(node.node_tree)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Layer', layer.name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YMoveLayer(bpy.types.Operator):
    bl_idname = "node.y_move_layer"
    bl_label = "Move Layer"
    bl_description = "Move layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        num_layers = len(yp.layers)
        layer_idx = yp.active_layer_index
        layer = yp.layers[layer_idx]

        # Get last member of group if selected layer is a group
        last_member_idx = get_last_child_idx(layer)
        
        # Get neighbor
        neighbor_idx = None
        neighbor_layer = None

        if self.direction == 'UP':
            neighbor_idx, neighbor_layer = get_upper_neighbor(layer)

        elif self.direction == 'DOWN':
            neighbor_idx, neighbor_layer = get_lower_neighbor(layer)

        if not neighbor_layer:
            return {'CANCELLED'}

        # Remember all parents
        parent_dict = get_parent_dict(yp)

        if layer.type == 'GROUP' and neighbor_layer.type != 'GROUP':

            # Group layer UP to standard layer
            if self.direction == 'UP':
                #print('Case A')

                # Swap layer
                yp.layers.move(neighbor_idx, last_member_idx)
                yp.active_layer_index = neighbor_idx

                #affected_start = neighbor_idx
                #affected_end = last_member_idx+1

            # Group layer DOWN to standard layer
            elif self.direction == 'DOWN':
                #print('Case B')

                # Swap layer
                yp.layers.move(neighbor_idx, layer_idx)
                yp.active_layer_index = layer_idx+1

                #affected_start = neighbor_idx
                #affected_end = layer_idx+1

        elif layer.type == 'GROUP' and neighbor_layer.type == 'GROUP':

            # Group layer UP to group layer
            if self.direction == 'UP':
                #print('Case C')

                # Swap all related layers
                for i in range(last_member_idx+1 - layer_idx):
                    yp.layers.move(layer_idx+i, neighbor_idx+i)

                yp.active_layer_index = neighbor_idx

            # Group layer DOWN to group layer
            elif self.direction == 'DOWN':
                #print('Case D')

                last_neighbor_member_idx = get_last_child_idx(neighbor_layer)
                num_members = last_neighbor_member_idx+1 - neighbor_idx

                # Swap all related layers
                for i in range(num_members):
                    yp.layers.move(neighbor_idx+i, layer_idx+i)

                yp.active_layer_index = layer_idx+num_members

        elif layer.type != 'GROUP' and neighbor_layer.type == 'GROUP':

            # Standard layer UP to Group Layer
            if self.direction == 'UP':
                #print('Case E')

                # Swap layer
                yp.layers.move(layer_idx, neighbor_idx)
                yp.active_layer_index = neighbor_idx

                start_remap = neighbor_idx + 2
                end_remap = layer_idx + 1

            # Standard layer DOWN to Group Layer
            elif self.direction == 'DOWN':
                #print('Case F')

                last_neighbor_member_idx = get_last_child_idx(neighbor_layer)

                # Swap layer
                yp.layers.move(layer_idx, last_neighbor_member_idx)
                yp.active_layer_index = last_neighbor_member_idx

                start_remap = layer_idx + 1
                end_remap = last_neighbor_member_idx

        # Standard layer to standard Layer
        else:
            #print('Case G')

            # Swap layer
            yp.layers.move(layer_idx, neighbor_idx)
            yp.active_layer_index = neighbor_idx

        # Remap parents
        for lay in yp.layers:
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        # Refresh layer channel blend nodes
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        wm.ypui.need_update = True

        print('INFO: Layer', layer.name, 'is moved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def draw_move_up_in_layer_group(self, context):
    col = self.layout.column()

    c = col.operator("node.y_move_layer", text='Move Up (skip group)', icon='TRIA_UP')
    c.direction = 'UP'

    c = col.operator("node.y_move_in_out_layer_group", text='Move inside group', icon='TRIA_UP')
    c.direction = 'UP'

def draw_move_down_in_layer_group(self, context):
    col = self.layout.column()

    c = col.operator("node.y_move_layer", text='Move Down (skip group)', icon='TRIA_DOWN')
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
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.layers) > 0

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

def remove_layer(yp, index):
    group_tree = yp.id_data
    obj = bpy.context.object
    layer = yp.layers[index]
    layer_tree = get_tree(layer)

    # Dealing with image atlas segments
    if layer.type == 'IMAGE' and layer.segment_name != '':
        src = get_layer_source(layer)
        segment = src.image.yia.segments.get(layer.segment_name)
        segment.unused = True

    # Remove the source first to remove image
    source_tree = get_source_tree(layer, layer_tree)
    remove_node(source_tree, layer, 'source', obj=obj)

    # Remove Mask source
    for mask in layer.masks:

        # Dealing with image atlas segments
        if mask.type == 'IMAGE' and mask.segment_name != '':
            src = get_mask_source(mask)
            segment = src.image.yia.segments.get(mask.segment_name)
            segment.unused = True

        mask_tree = get_mask_tree(mask)
        remove_node(mask_tree, mask, 'source', obj=obj)

    # Remove node group and layer tree
    bpy.data.node_groups.remove(layer_tree)
    group_tree.nodes.remove(group_tree.nodes.get(layer.group_node))

    # Delete the layer
    yp.layers.remove(index)

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
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

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
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

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

        obj = context.object
        wm = context.window_manager
        node = get_active_ypaint_node()
        group_tree = node.node_tree
        yp = group_tree.yp
        layer = yp.layers[yp.active_layer_index]
        layer_name = layer.name
        layer_idx = get_layer_index(layer)

        # Remember parents
        parent_dict = get_parent_dict(yp)

        need_reconnect_layers = False

        if self.remove_childs:

            last_idx = get_last_child_idx(layer)
            for i in reversed(range(layer_idx, last_idx+1)):
                remove_layer(yp, i)
                
            # The childs are all gone
            child_ids = []

        else:
            # Get childrens and repoint child parents
            child_ids = get_list_of_direct_child_ids(layer)
            for i in child_ids:
                parent_dict[yp.layers[i].name] = parent_dict[layer.name]

            # Remove layer
            remove_layer(yp, layer_idx)

        # Remove temp uv layer
        if hasattr(obj.data, 'uv_textures'): # Blender 2.7 only
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        for uv in uv_layers:
            if uv.name == TEMP_UV:
                uv_layers.remove(uv)

        # Set new active index
        if (yp.active_layer_index == len(yp.layers) and
            yp.active_layer_index > 0
            ):
            yp.active_layer_index -= 1
        else:
            # Force update the index to refesh paint image
            yp.active_layer_index = yp.active_layer_index

        # Remap parents
        for lay in yp.layers:
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        # Check childrens
        #if need_reconnect_layers:
        for i in child_ids:
            lay = yp.layers[i-1]
            check_all_layer_channel_io_and_nodes(lay)
            rearrange_layer_nodes(lay)
            reconnect_layer_nodes(lay)

        # Refresh layer channel blend nodes
        reconnect_yp_nodes(group_tree)
        rearrange_yp_nodes(group_tree)

        # Update UI
        wm.ypui.need_update = True

        # Refresh normal map
        yp.refresh_tree = True

        print('INFO: Layer', layer_name, 'is deleted at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YReplaceLayerType(bpy.types.Operator):
    bl_idname = "node.y_replace_layer_type"
    bl_label = "Replace Layer Type"
    bl_description = "Replace Layer Type"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    item_name = StringProperty(name="Item")
    item_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def invoke(self, context, event):
        obj = context.object
        self.layer = context.layer
        if self.type in {'IMAGE', 'VCOL'}:

            self.item_coll.clear()
            self.item_name = ''

            # Update image names
            if self.type == 'IMAGE':
                for img in bpy.data.images:
                    if not img.yia.is_image_atlas:
                        self.item_coll.add().name = img.name
            else:
                for vcol in obj.data.vertex_colors:
                    self.item_coll.add().name = vcol.name

            return context.window_manager.invoke_props_dialog(self)#, width=400)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout

        if bpy.app.version_string.startswith('2.8'):
            split = layout.split(factor=0.35, align=True)
        else: split = layout.split(percentage=0.35)

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
        layer = self.layer
        yp = layer.id_data.yp

        if self.type == layer.type: return {'CANCELLED'}
        #if layer.type == 'GROUP':
        #    self.report({'ERROR'}, "You can't change type of group layer!")
        #    return {'CANCELLED'}

        if self.type in {'VCOL', 'IMAGE'} and self.item_name == '':
            self.report({'ERROR'}, "Form is cannot be empty!")
            return {'CANCELLED'}

        # Remember parents
        parent_dict = get_parent_dict(yp)
        child_ids = []

        # If layer type is group, get childrens and repoint child parents
        if layer.type == 'GROUP':
            # Get childrens and repoint child parents
            child_ids = get_list_of_direct_child_ids(layer)
            for i in child_ids:
                parent_dict[yp.layers[i].name] = parent_dict[layer.name]

        # Remove segment if original layer using image atlas
        if layer.type == 'IMAGE' and layer.segment_name != '':
            src = get_layer_source(layer)
            segment = src.image.yia.segments.get(layer.segment_name)
            segment.unused = True
            layer.segment_name = ''

        yp.halt_reconnect = True

        # Standard bump map is easier to convert
        fine_bump_channels = [ch for ch in layer.channels if ch.normal_map_type == 'FINE_BUMP_MAP']
        for ch in fine_bump_channels:
            ch.normal_map_type = 'BUMP_MAP'

        # Disable transition will also helps
        transition_channels = [ch for ch in layer.channels if ch.enable_transition_bump]
        for ch in transition_channels:
            ch.enable_transition_bump = False

        # Current source
        tree = get_tree(layer)
        source_tree = get_source_tree(layer)
        source = source_tree.nodes.get(layer.source)

        # Save source to cache if it's not image, vertex color, or background
        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP'}:
            setattr(layer, 'cache_' + layer.type.lower(), source.name)
            # Remove uv input link
            if any(source.inputs) and any(source.inputs[0].links):
                tree.links.remove(source.inputs[0].links[0])
            source.label = ''
        else:
            remove_node(source_tree, layer, 'source', remove_data=False)

        # Disable modifier tree
        if (layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'} and 
                self.type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR'}):
            Modifier.disable_modifiers_tree(layer)

        # Try to get available cache
        cache = None
        if self.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP'}:
            cache = tree.nodes.get(getattr(layer, 'cache_' + self.type.lower()))

        if cache:
            layer.source = cache.name
            setattr(layer, 'cache_' + self.type.lower(), '')
            cache.label = 'Source'
        else:
            source = new_node(source_tree, layer, 'source', layer_node_bl_idnames[self.type], 'Source')

            if self.type == 'IMAGE':
                image = bpy.data.images.get(self.item_name)
                source.image = image
                source.color_space = 'NONE'
            elif self.type == 'VCOL':
                source.attribute_name = self.item_name

        # Change layer type
        ori_type = layer.type
        layer.type = self.type

        # Enable modifiers tree if generated texture is used
        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
            Modifier.enable_modifiers_tree(layer)

        # Update group ios
        check_all_layer_channel_io_and_nodes(layer, tree)
        if layer.type == 'BACKGROUND':
            # Remove bump and its base
            for ch in layer.channels:
                remove_node(tree, ch, 'bump_base')
                #remove_node(tree, ch, 'bump')
                remove_node(tree, ch, 'normal')

        # Update linear stuff
        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]
            set_layer_channel_linear_node(tree, layer, root_ch, ch)

        # Back to use fine bump if conversion happen
        for ch in fine_bump_channels:
            ch.normal_map_type = 'FINE_BUMP_MAP'

        # Bring back transition
        for ch in transition_channels:
            ch.enable_transition_bump = True

        # Update uv neighbor
        set_uv_neighbor_resolution(layer)

        yp.halt_reconnect = False

        # Remap parents
        for lay in yp.layers:
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        # Check childrens which need rearrange
        for i in child_ids:
            lay = yp.layers[i]
            check_all_layer_channel_io_and_nodes(lay)
            rearrange_layer_nodes(lay)
            reconnect_layer_nodes(lay)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        if layer.type in {'BACKGROUND', 'GROUP'} or ori_type == 'GROUP':
            rearrange_yp_nodes(layer.id_data)
            reconnect_yp_nodes(layer.id_data)

        print('INFO: Layer', layer.name, 'is updated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def update_channel_enable(self, context):
    yp = self.id_data.yp

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    ch = self

    tree = get_tree(layer)
    blend = tree.nodes.get(ch.blend)

    if blend:
        mute = not layer.enable or not ch.enable

        if yp.disable_quick_toggle:
            blend.mute = mute
        else: blend.mute = False

    update_channel_intensity_value(ch, context)

def check_channel_normal_map_nodes(tree, layer, root_ch, ch):

    #print("Checking channel normal map nodes. Layer: " + layer.name + ' Channel: ' + root_ch.name)

    yp = layer.id_data.yp
    #if yp.halt_update: return

    if root_ch.type != 'NORMAL': return
    if layer.type in {'BACKGROUND', 'GROUP'}: return

    # Normal nodes
    if ch.normal_map_type == 'NORMAL_MAP':

        #normal = replace_new_node(tree, ch, 'normal', 'ShaderNodeNormalMap', 'Normal')
        #normal.uv_map = layer.uv_name
        normal = replace_new_node(tree, ch, 'normal', 'ShaderNodeGroup', 'Normal', lib.NORMAL_MAP)

        #normal_flip = replace_new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 
        #        'Normal Backface Flip', lib.FLIP_BACKFACE_NORMAL)

        #set_normal_backface_flip(normal_flip, yp.flip_backface)
        remove_node(tree, ch, 'normal_flip')

    # Bump nodes
    elif ch.normal_map_type == 'BUMP_MAP':

        normal = replace_new_node(tree, ch, 'normal', 'ShaderNodeBump', 'Bump')
        normal.inputs[1].default_value = ch.bump_distance

        normal_flip = replace_new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 
                'Normal Backface Flip', lib.FLIP_BACKFACE_BUMP)

        set_bump_backface_flip(normal_flip, yp.flip_backface)

    # Fine bump nodes
    elif ch.normal_map_type == 'FINE_BUMP_MAP':

        # Make sure to enable source tree and modifier tree
        enable_layer_source_tree(layer, False)
        Modifier.enable_modifiers_tree(ch, False)

        normal = replace_new_node(tree, ch, 'normal', 'ShaderNodeGroup', 'Fine Bump', lib.FINE_BUMP)
        normal.inputs[0].default_value = get_fine_bump_distance(layer, ch.bump_distance)

        remove_node(tree, ch, 'normal_flip')

    # Remove neighbor related nodes
    if ch.normal_map_type != 'FINE_BUMP_MAP':

        disable_layer_source_tree(layer, False)
        Modifier.disable_modifiers_tree(ch, False)

    # Create normal flip node
    #if layer.type not in {'BACKGROUND', 'GROUP', 'COLOR'}:
    #if ch.normal_map_type != '' or (ch.normal_map_type == '' and ch.enable_transition_bump):

    #normal_flip = tree.nodes.get(ch.normal_flip)
    #if not normal_flip:
    #    normal_flip = new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 'Flip Backface Normal')
    #    normal_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_NORMAL)

    #else:
    #    remove_node(tree, ch, 'normal_flip')

    # Update override color modifier
    #for mod in ch.modifiers:
    #    if mod.type == 'OVERRIDE_COLOR' and mod.oc_use_normal_base:
    #        if ch.normal_map_type == 'NORMAL_MAP':
    #            mod.oc_col = (0.5, 0.5, 1.0, 1.0)
    #        else:
    #            val = ch.bump_base_value
    #            mod.oc_col = (val, val, val, 1.0)

    # Check bump base
    check_create_bump_base(layer, tree, ch)

    # Check mask multiplies
    check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    check_mask_source_tree(layer) #, ch)

def update_normal_map_type(self, context):
    yp = self.id_data.yp
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    check_channel_normal_map_nodes(tree, layer, root_ch, self)

    #if not yp.halt_reconnect:
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def check_blend_type_nodes(root_ch, layer, ch):

    #print("Checking blend type nodes. Layer: " + layer.name + ' Channel: ' + root_ch.name)

    need_reconnect = False

    yp = layer.id_data.yp
    tree = get_tree(layer)
    nodes = tree.nodes
    blend = nodes.get(ch.blend)

    has_parent = layer.parent_idx != -1

    # Background layer always using mix blend type
    if layer.type == 'BACKGROUND':
        blend_type = 'MIX'
        normal_blend = 'MIX'
    else: 
        blend_type = ch.blend_type
        normal_blend = ch.normal_blend

    if root_ch.type == 'RGB':

        if (has_parent or root_ch.enable_alpha) and blend_type == 'MIX':

            if layer.type == 'BACKGROUND':
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG, return_status = True, 
                        hard_replace=True)

            else: 
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER, 
                        return_status = True, hard_replace=True)

        else:
            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeMixRGB', 'Blend', return_status = True, hard_replace=True)

            #if blend.blend_type != blend_type:
            #    blend.blend_type = blend_type

    elif root_ch.type == 'NORMAL':

        if has_parent and normal_blend == 'MIX':
            if layer.type == 'BACKGROUND':
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_VEC, 
                        return_status = True, hard_replace=True)
            else:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_VEC, 
                        return_status = True, hard_replace=True)

        elif normal_blend == 'OVERLAY':
            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeGroup', 'Blend', lib.OVERLAY_NORMAL, 
                    return_status = True, hard_replace=True)

        elif normal_blend == 'MIX':
            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeGroup', 'Blend', lib.VECTOR_MIX, 
                    return_status = True, hard_replace=True)

        disp_ch = get_displacement_channel(yp)

        #if not root_ch.enable_displacement:
        #    remove_node(tree, ch, 'disp_blend')

        if root_ch == disp_ch:
            #ch_index = get_channel_index(root_ch)

            disp_blend = tree.nodes.get(ch.disp_blend)
            disp_scale = tree.nodes.get(ch.disp_scale)

            max_height = get_displacement_max_height(root_ch)
            root_ch.displacement_height_ratio = max_height

            # Displacement blend node
            if not disp_blend:
                disp_blend = new_node(tree, ch, 'disp_blend', 'ShaderNodeMixRGB', 'Displacement Blend')

            #if ch.normal_blend == 'MIX':
            #    #disp_blend.blend_type = 'MIX'
            #    disp_blend, need_reconnect = replace_new_node(tree, ch, 'disp_blend', 
            #            'ShaderNodeGroup', 'Displacement Blend', lib.DISP_MIX, 
            #            return_status = True, hard_replace=True)
            #elif ch.normal_blend == 'OVERLAY':
            #    #disp_blend.blend_type = 'ADD'
            #    disp_blend, need_reconnect = replace_new_node(tree, ch, 'disp_blend', 
            #            'ShaderNodeGroup', 'Displacement Blend', lib.DISP_OVERLAY, 
            #            return_status = True, hard_replace=True)

            if ch.normal_blend == 'MIX':
                disp_blend.blend_type = 'MIX'
            elif ch.normal_blend == 'OVERLAY':
                disp_blend.blend_type = 'ADD'

            #if max_height > 0.0:
            #for l in yp.layers:
                #ttree = get_tree(l)
                #print(l.name)
                #c = l.channels[ch_index]
            #disp_blend = tree.nodes.get(ch.disp_blend)
            #if disp_blend:
            #    disp_blend.inputs['Scale'].default_value = ch.bump_distance #/ max_height

            #if not disp_scale:
            #    disp_scale = new_node(tree, ch, 'disp_scale', 'ShaderNodeGroup', 'Displacement Scale')
            #    disp_scale.node_tree = get_node_tree_lib(lib.DISP_SCALE)

            #if ch.enable_transition_bump:
            #    disp_scale, need_reconnect = replace_new_node(tree, ch, 'disp_scale', 
            #            'ShaderNodeGroup', 'Displacement Scale', lib.DISP_SCALE_TRANS_BUMP, 
            #            return_status = True, hard_replace=True)

            #    delta = ch.transition_bump_distance - abs(ch.bump_distance)
            #    disp_scale.inputs['Delta'].default_value = delta
            #    disp_scale.inputs['RGB Max Height'].default_value = ch.bump_distance
            #    disp_scale.inputs['Alpha Max Height'].default_value = ch.transition_bump_distance

            #else:
            #    disp_scale, need_reconnect = replace_new_node(tree, ch, 'disp_scale', 
            #            'ShaderNodeGroup', 'Displacement Scale', lib.DISP_SCALE, 
            #            return_status = True, hard_replace=True)

            #    disp_scale.inputs['Scale'].default_value = ch.bump_distance #/ max_height
            update_disp_scale_node(tree, root_ch, ch)

        else:
            remove_node(tree, ch, 'disp_blend')
            remove_node(tree, ch, 'disp_scale')

    elif root_ch.type == 'VALUE':

        if has_parent and blend_type == 'MIX':
            if layer.type == 'BACKGROUND':
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_BW, 
                        return_status = True, hard_replace=True)
            else:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BW, 
                        return_status = True, hard_replace=True)
        else:

            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeMixRGB', 'Blend', return_status = True, hard_replace=True)

    if root_ch.type != 'NORMAL' and blend.type == 'MIX_RGB' and blend.blend_type != blend_type:
        blend.blend_type = blend_type

    #print(need_reconnect)

    # Blend mute
    #mute = not layer.enable or not ch.enable
    #intensity = nodes.get(ch.intensity)
    #if intensity: intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value
    #if ch.enable_transition_ramp:
    #    tr_intensity = nodes.get(ch.tr_intensity)
    #    if tr_intensity: tr_intensity.inputs[1].default_value = 0.0 if mute else ch.transition_ramp_intensity_value

    mute = not layer.enable or not ch.enable
    if yp.disable_quick_toggle:
        blend.mute = mute
    else: blend.mute = False

    # Intensity nodes
    intensity = tree.nodes.get(ch.intensity)
    if not intensity:
        intensity = new_node(tree, ch, 'intensity', 'ShaderNodeMath', 'Intensity')
        intensity.operation = 'MULTIPLY'

    # Channel mute
    intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

    return need_reconnect

def update_blend_type(self, context):
    T = time.time()

    wm = context.window_manager
    yp = self.id_data.yp
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = yp.channels[ch_index]

    if check_blend_type_nodes(root_ch, layer, self): # and not yp.halt_reconnect:
        reconnect_layer_nodes(layer, ch_index)
        rearrange_layer_nodes(layer)

    print('INFO: Layer', layer.name, ' blend type is changed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    wm.yptimer.time = str(time.time())

def update_flip_backface_normal(self, context):
    yp = self.id_data.yp
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)

    normal_flip = tree.nodes.get(self.normal_flip)
    normal_flip.mute = self.invert_backface_normal

def update_bump_base_value(self, context):
    yp = self.id_data.yp
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)

    update_bump_base_value_(tree, self)

def update_bump_distance(self, context):
    group_tree = self.id_data
    yp = group_tree.yp
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    normal = tree.nodes.get(self.normal)

    if normal:
        if self.normal_map_type == 'BUMP_MAP':
            normal.inputs[1].default_value = self.bump_distance

        elif self.normal_map_type == 'FINE_BUMP_MAP':
            normal.inputs[0].default_value = get_fine_bump_distance(layer, self.bump_distance)

    disp_ch = get_displacement_channel(yp)
    if disp_ch == root_ch:

        max_height = get_displacement_max_height(root_ch)
        root_ch.displacement_height_ratio = max_height

        #disp_blend = tree.nodes.get(self.disp_blend)
        #if disp_blend:
        #    disp_blend.inputs['Scale'].default_value = self.bump_distance
        disp_scale = tree.nodes.get(self.disp_scale)
        if disp_scale:
            if self.enable_transition_bump:
                disp_scale.inputs['RGB Max Height'].default_value = self.bump_distance
                disp_scale.inputs['Delta'].default_value = get_transition_disp_delta(self)
            else: disp_scale.inputs['Scale'].default_value = self.bump_distance

        #end_linear = group_tree.nodes.get(root_ch.end_linear)
        #if end_linear:
        #    pass

def set_layer_channel_linear_node(tree, layer, root_ch, ch):

    #if custom_value: 
    #    if root_ch.type in {'RGB', 'NORMAL'}:
    #        ch.custom_color = custom_value
    #    else: ch.custom_value = custom_value

    if (root_ch.type != 'NORMAL' and root_ch.colorspace == 'SRGB' 
            and layer.type not in {'IMAGE', 'BACKGROUND', 'GROUP'} and ch.layer_input == 'RGB' and not ch.gamma_space):
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

        #if root_ch.colorspace == 'SRGB' and (ch.layer_input == 'CUSTOM' or not ch.gamma_space):
        #if not ch.gamma_space:
        #    linear.inputs[1].default_value = 1.0 / GAMMA
        #else: linear.inputs[1].default_value = 1.0
        linear.inputs[1].default_value = 1.0 / GAMMA

    else:
        remove_node(tree, ch, 'linear')

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    #if root_ch.type == 'NORMAL' and ch.layer_input == 'CUSTOM':
    #    source = replace_new_node(tree, ch, 'source', 'ShaderNodeRGB', 'Custom')
    #    col = (ch.custom_color[0], ch.custom_color[1], ch.custom_color[2], 1.0)
    #    source.outputs[0].default_value = col
    #else:
    #    remove_node(tree, ch, 'source')

#def update_custom_input(self, context):
#    yp = self.id_data.yp
#
#    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
#    layer = yp.layers[int(m.group(1))]
#    root_ch = yp.channels[int(m.group(2))]
#    tree = get_tree(layer)
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

def update_layer_input(self, context):
    yp = self.id_data.yp

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)
    ch = self

    set_layer_channel_linear_node(tree, layer, root_ch, ch)

def update_uv_name(self, context):
    obj = context.object
    group_tree = self.id_data
    yp = group_tree.yp
    if yp.halt_update: return

    ypui = context.window_manager.ypui
    layer = self
    active_layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)
    if not tree: return

    nodes = tree.nodes

    #uv_map = nodes.get(layer.uv_map)
    #if uv_map: 
    #    # Cannot use temp uv as standard uv
    #    if layer.uv_name == TEMP_UV:
    #        layer.uv_name = uv_map.uv_map

    #    uv_map.uv_map = layer.uv_name

    if layer.uv_name == TEMP_UV:
        if len(yp.uvs) > 0:
            for uv in yp.uvs:
                layer.uv_name = uv.name
                break

    #tangent = nodes.get(layer.tangent)
    #if tangent: tangent.uv_map = layer.uv_name

    #bitangent = nodes.get(layer.bitangent)
    #if bitangent: bitangent.uv_map = layer.uv_name

    for ch in layer.channels:
        normal = nodes.get(ch.normal)
        if normal and normal.type == 'NORMAL_MAP': normal.uv_map = layer.uv_name

    # Update uv layer
    if obj.type == 'MESH' and not any([m for m in layer.masks if m.active_edit]) and layer == active_layer:

        if layer.segment_name != '':
            #if ypui.disable_auto_temp_uv_update:
            #    update_image_editor_image(context, None)
            #    yp.need_temp_uv_refresh = True
            #else: 
            refresh_temp_uv(obj, layer)
        else:
            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            uv_layers.active = uv_layers.get(layer.uv_name)

            #for i, uv in enumerate(uv_layers):
            #    if uv.name == layer.uv_name:
            #        if uv_layers.active_index != i:
            #            uv_layers.active_index = i
            #        break

    # Update neighbor uv if mask bump is active
    rearrange = False
    for i, mask in enumerate(layer.masks):
        if set_mask_uv_neighbor(tree, layer, mask):
            rearrange = True

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    yp_dirty = True if check_layer_tree_ios(layer, tree) else False

    if rearrange or yp_dirty: #and not yp.halt_reconnect:
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

    # Update layer tree inputs
    if yp_dirty:
        rearrange_yp_nodes(group_tree)
        reconnect_yp_nodes(group_tree)

def update_texcoord_type(self, context):
    yp = self.id_data.yp
    layer = self
    tree = get_tree(layer)

    if yp.halt_update: return

    # Check for normal channel for fine bump space switch
    # UV is using Tangent space
    # Generated, Normal, and object are using Object Space
    # Camera and Window are using View Space
    # Reflection actually aren't using view space, but whatever, no one use bump map in reflection texcoord
    #for i, ch in enumerate(layer.channels):
    #    root_ch = yp.channels[i]
    #    if root_ch.type == 'NORMAL':

    #uv_neighbor = tree.nodes.get(layer.uv_neighbor)
    #if uv_neighbor:
    #    cur_tree = uv_neighbor.node_tree
    #    sel_tree = lib.get_neighbor_uv_tree(layer.texcoord_type)

    #    if sel_tree != cur_tree:
    #        uv_neighbor.node_tree = sel_tree

    #        if cur_tree.users == 0:
    #            bpy.data.node_groups.remove(cur_tree)
    #if layer.type 
    uv_neighbor = replace_new_node(tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
            lib.get_neighbor_uv_tree_name(layer.texcoord_type), hard_replace=True)

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    yp_dirty = True if check_layer_tree_ios(layer, tree) else False

    #if not yp.halt_reconnect:
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    # Update layer tree inputs
    if yp_dirty:
        rearrange_yp_nodes(self.id_data)
        reconnect_yp_nodes(self.id_data)

def update_channel_intensity_value(self, context):
    yp = self.id_data.yp

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)
    ch_index = int(m.group(2))
    ch = self
    root_ch = yp.channels[ch_index]

    mute = not layer.enable or not ch.enable

    intensity = tree.nodes.get(ch.intensity)
    if intensity:
        intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

    if ch.enable_transition_ramp:
        transition.set_ramp_intensity_value(tree, layer, ch)

    if ch.enable_transition_ao:
        tao = tree.nodes.get(ch.tao)
        if tao: tao.inputs['Intensity'].default_value = 0.0 if mute else transition.get_transition_ao_intensity(ch)

    if ch.enable_transition_bump and ch.transition_bump_crease:
        tb_crease_intensity = tree.nodes.get(ch.tb_crease_intensity)
        if tb_crease_intensity:
            tb_crease_intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

def update_layer_enable(self, context):
    yp = self.id_data.yp
    layer = self
    tree = get_tree(layer)

    for ch in layer.channels:
        update_channel_enable(ch, context)

    context.window_manager.yptimer.time = str(time.time())

def update_layer_name(self, context):
    yp = self.id_data.yp
    if self.type == 'IMAGE' and self.segment_name != '': return

    src = get_layer_source(self)
    change_layer_name(yp, context.object, src, self, yp.layers)

class YLayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    layer_input = EnumProperty(
            name = 'Layer Input',
            #items = (('RGB', 'Color', ''),
            #         ('ALPHA', 'Alpha / Factor', '')),
            #default = 'RGB',
            items = layer_input_items,
            update = update_layer_input)

    gamma_space = BoolProperty(
            name='Gamma Space',
            description='Make sure layer input is in linear space',
            default = False,
            update = update_layer_input)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            items = layer_channel_normal_map_type_items,
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
    modifiers = CollectionProperty(type=Modifier.YPaintModifier)

    # Blur
    #enable_blur = BoolProperty(default=False, update=Blur.update_layer_channel_blur)
    #blur = PointerProperty(type=Blur.YLayerBlur)

    invert_backface_normal = BoolProperty(default=False, update=update_flip_backface_normal)

    # Node names
    linear = StringProperty(default='')
    blend = StringProperty(default='')
    intensity = StringProperty(default='')
    source = StringProperty(default='')

    # Normal related
    normal = StringProperty(default='')
    normal_flip = StringProperty(default='')
    
    # Displacement blend
    disp_scale = StringProperty(default='')
    disp_blend = StringProperty(default='')

    bump_distance = FloatProperty(
            name='Bump Height Range', 
            description= 'Bump height range.\n(White equals this value, black equals negative of this value)', 
            default=0.05, min=-1.0, max=1.0, precision=3, # step=1,
            update=update_bump_distance)

    bump_base_value = FloatProperty(
            name='Bump Base', 
            description= 'Value of empty area for bump map', 
            default=0.5, min=0.0, max=1.0,
            update=update_bump_base_value)

    enable_displacement = BoolProperty(
            name = 'Enable Displacement',
            description = 'Enable displacement for this channel',
            default = True)

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

    # Intensity Stuff
    intensity_multiplier = StringProperty(default='')

    # Transition bump related
    enable_transition_bump = BoolProperty(name='Enable Transition Bump', description='Enable transition bump',
            default=False, update=transition.update_enable_transition_bump)

    show_transition_bump = BoolProperty(name='Toggle Transition Bump',
            description = "Toggle transition Bump (This will affect other channels)", 
            default=False) #, update=transition.update_show_transition_bump)

    transition_bump_value = FloatProperty(
        name = 'Transition Bump Value',
        description = 'Transition bump value',
        default=3.0, min=1.0, max=100.0, 
        update=transition.update_transition_bump_value)

    transition_bump_second_edge_value = FloatProperty(
            name = 'Second Edge Intensity', 
            description = 'Second Edge intensity value',
            default=1.2, min=1.0, max=100.0, 
            update=transition.update_transition_bump_value)

    transition_bump_distance = FloatProperty(
            #name='Transition Bump Distance', 
            #description= 'Distance of mask bump', 
            name='Transition Bump Height Range', 
            description= 'Transition bump height range.\n(White equals this value, black equals negative of this value)', 
            default=0.05, min=0.0, max=1.0, precision=3, # step=1,
            update=transition.update_transition_bump_distance)

    transition_bump_type = EnumProperty(
            name = 'Bump Type',
            items = (
                ('BUMP_MAP', 'Bump', ''),
                ('FINE_BUMP_MAP', 'Fine Bump', ''),
                ('CURVED_BUMP_MAP', 'Curved Bump', ''),
                ),
            default = 'FINE_BUMP_MAP',
            update=transition.update_enable_transition_bump)

    transition_bump_chain = IntProperty(
            name = 'Transition bump chain',
            description = 'Number of mask affected by transition bump',
            default=10, min=0, max=10,
            update=transition.update_transition_bump_chain)

    transition_bump_flip = BoolProperty(
            name = 'Transition Bump Flip',
            description = 'Transition bump flip',
            default=False,
            update=transition.update_enable_transition_bump)

    transition_bump_curved_offset = FloatProperty(
            name = 'Transition Bump Curved Offst',
            description = 'Transition bump curved offset',
            default=0.02, min=0.0, max=0.1,
            update=transition.update_transition_bump_curved_offset)

    transition_bump_crease = BoolProperty(
            name = 'Transition Bump Crease',
            description = 'Transition bump crease (only works if flip is inactive)',
            default=False,
            update=transition.update_enable_transition_bump)

    transition_bump_crease_factor = FloatProperty(
            name = 'Transition Bump Crease Factor',
            description = 'Transition bump crease factor',
            default=0.33, min=0.0, max=10.0,
            update=transition.update_transition_bump_crease_factor)

    transition_bump_fac = FloatProperty(
            name='Transition Bump Factor',
            description = 'Transition bump factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_fac)

    transition_bump_second_fac = FloatProperty(
            name='Transition Bump Second Factor',
            description = 'Transition bump second factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_fac)

    tb_bump = StringProperty(default='')
    tb_bump_flip = StringProperty(default='')
    tb_inverse = StringProperty(default='')
    tb_intensity_multiplier = StringProperty(default='')
    tb_blend = StringProperty(default='')

    tb_crease = StringProperty(default='')
    tb_crease_flip = StringProperty(default='')
    tb_crease_intensity = StringProperty(default='')
    tb_crease_mix = StringProperty(default='')

    # Transition ramp related
    enable_transition_ramp = BoolProperty(name='Enable Transition Ramp', description='Enable alpha transition ramp', 
            default=False, update=transition.update_enable_transition_ramp)

    show_transition_ramp = BoolProperty(name='Toggle Transition Ramp',
            description = "Toggle transition Ramp (Works best if there's transition bump enabled on other channel)", 
            default=False) #, update=transition.update_show_transition_ramp)

    transition_ramp_intensity_value = FloatProperty(
            name = 'Channel Intensity Factor', 
            description = 'Channel Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_ramp_intensity_value)

    transition_ramp_blend_type = EnumProperty(
        name = 'Transition Ramp Blend Type',
        items = blend_type_items,
        default = 'MIX', 
        update=transition.update_enable_transition_ramp)

    transition_ramp_intensity_unlink = BoolProperty(
            name='Unlink Transition Ramp with Channel Intensity', 
            description='Unlink Transition Ramp with Channel Intensity', 
            default=False,
            update=transition.update_enable_transition_ramp)

    # Transition ramp nodes
    tr_ramp = StringProperty(default='')
    tr_ramp_blend = StringProperty(default='')

    # To save ramp
    cache_ramp = StringProperty(default='')

    # Transition AO related
    enable_transition_ao = BoolProperty(name='Enable Transition AO', 
            description='Enable alpha transition Ambient Occlusion (Need active transition bump)', default=False,
            update=transition.update_enable_transition_ao)

    show_transition_ao = BoolProperty(name='Toggle Transition AO',
            description = "Toggle transition AO (Only works if there's transition bump enabled on other channel)", 
            default=False) #, update=transition.update_show_transition_ao)

    transition_ao_power = FloatProperty(name='Transition AO Power',
            #description='Transition AO edge power (higher value means less AO)', min=1.0, max=100.0, default=4.0,
            description='Transition AO power', min=1.0, max=100.0, default=4.0,
            update=transition.update_transition_ao_edge)

    transition_ao_intensity = FloatProperty(name='Transition AO Intensity',
            description='Transition AO intensity', subtype='FACTOR', min=0.0, max=1.0, default=0.5,
            update=transition.update_transition_ao_intensity)

    transition_ao_color = FloatVectorProperty(name='Transition AO Color', description='Transition AO Color', 
            subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0),
            update=transition.update_transition_ao_color)

    transition_ao_inside_intensity = FloatProperty(name='Transition AO Inside Intensity', 
            description='Transition AO Inside Intensity', subtype='FACTOR', min=0.0, max=1.0, default=0.0,
            update=transition.update_transition_ao_exclude_inside)

    transition_ao_blend_type = EnumProperty(
        name = 'Transition AO Blend Type',
        items = blend_type_items,
        default = 'MIX', 
        update=transition.update_enable_transition_ao)

    transition_ao_intensity_unlink = BoolProperty(
            name='Unlink Transition AO with Channel Intensity', 
            description='Unlink Transition AO with Channel Intensity', 
            default=False,
            update=transition.update_transition_ao_intensity)

    tao = StringProperty(default='')

    # For UI
    expand_bump_settings = BoolProperty(default=False)
    expand_intensity_settings = BoolProperty(default=False)
    expand_content = BoolProperty(default=False)
    expand_transition_bump_settings = BoolProperty(default=False)
    expand_transition_ramp_settings = BoolProperty(default=False)
    expand_transition_ao_settings = BoolProperty(default=False)
    expand_input_settings = BoolProperty(default=False)

def update_layer_color_chortcut(self, context):
    layer = self

    # If color shortcut is active, disable other shortcut
    if layer.type == 'COLOR' and layer.color_shortcut:

        for m in layer.modifiers:
            m.shortcut = False

        for ch in layer.channels:
            for m in ch.modifiers:
                m.shortcut = False

def update_layer_transform(self, context):
    update_mapping(self)

class YLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='', update=update_layer_name)
    enable = BoolProperty(
            name = 'Enable Layer', description = 'Enable layer',
            default=True, update=update_layer_enable)

    channels = CollectionProperty(type=YLayerChannel)

    group_node = StringProperty(default='')
    depth_group_node = StringProperty(default='')

    type = EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    color_shortcut = BoolProperty(
            name = 'Color Shortcut on the list',
            description = 'Display color shortcut on the list',
            default=True,
            update=update_layer_color_chortcut)

    texcoord_type = EnumProperty(
        name = 'Layer Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_texcoord_type)

    # To detect change of layer image
    image_name = StringProperty(default='')

    # To get segment if using image atlas
    segment_name = StringProperty(default='')

    uv_name = StringProperty(default='', update=update_uv_name)

    # Parent index
    parent_idx = IntProperty(default=-1)

    # Transform
    translation = FloatVectorProperty(
            name='Translation', size=3, precision=3, 
            default=(0.0, 0.0, 0.0),
            update=update_layer_transform
            ) #, step=1)

    rotation = FloatVectorProperty(
            name='Rotation', subtype='AXISANGLE', size=3, precision=3, unit='ROTATION', 
            default=(0.0, 0.0, 0.0),
            update=update_layer_transform
            ) #, step=3)

    scale = FloatVectorProperty(
            name='Scale', size=3, precision=3, 
            default=(1.0, 1.0, 1.0),
            update=update_layer_transform,
            ) #, step=3)

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
    uv_map = StringProperty(default='')
    mapping = StringProperty(default='')
    texcoord = StringProperty(default='')

    need_temp_uv_refresh = BoolProperty(default=False)

    # Other Vectors
    tangent = StringProperty(default='')
    bitangent = StringProperty(default='')
    tangent_flip = StringProperty(default='')
    bitangent_flip =StringProperty(default='')

    # Modifiers
    modifiers = CollectionProperty(type=Modifier.YPaintModifier)
    mod_group = StringProperty(default='')
    mod_group_1 = StringProperty(default='')

    # Mask
    enable_masks = BoolProperty(name='Enable Layer Masks', description='Enable layer masks',
            default=True, update=Mask.update_enable_layer_masks)
    masks = CollectionProperty(type=Mask.YLayerMask)

    # UI related
    expand_content = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)
    expand_masks = BoolProperty(default=False)
    expand_channels = BoolProperty(default=True)
    expand_source = BoolProperty(default=False)

def register():
    bpy.utils.register_class(YRefreshNeighborUV)
    bpy.utils.register_class(YNewLayer)
    bpy.utils.register_class(YOpenImageToLayer)
    bpy.utils.register_class(YOpenAvailableDataToLayer)
    bpy.utils.register_class(YMoveLayer)
    bpy.utils.register_class(YMoveInOutLayerGroup)
    bpy.utils.register_class(YMoveInOutLayerGroupMenu)
    bpy.utils.register_class(YRemoveLayer)
    bpy.utils.register_class(YRemoveLayerMenu)
    bpy.utils.register_class(YReplaceLayerType)
    bpy.utils.register_class(YLayerChannel)
    bpy.utils.register_class(YLayer)

def unregister():
    bpy.utils.unregister_class(YRefreshNeighborUV)
    bpy.utils.unregister_class(YNewLayer)
    bpy.utils.unregister_class(YOpenImageToLayer)
    bpy.utils.unregister_class(YOpenAvailableDataToLayer)
    bpy.utils.unregister_class(YMoveLayer)
    bpy.utils.unregister_class(YMoveInOutLayerGroup)
    bpy.utils.unregister_class(YMoveInOutLayerGroupMenu)
    bpy.utils.unregister_class(YRemoveLayer)
    bpy.utils.unregister_class(YRemoveLayerMenu)
    bpy.utils.unregister_class(YReplaceLayerType)
    bpy.utils.unregister_class(YLayerChannel)
    bpy.utils.unregister_class(YLayer)
