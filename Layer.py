import bpy, time, re, os, random
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import Modifier, lib, Mask, transition, ImageAtlas, UDIM, NormalMapModifier
from .common import *
#from .bake_common import *
from .node_arrangements import *
from .node_connections import *
from .subtree import *
from .input_outputs import *

DEFAULT_NEW_IMG_SUFFIX = ' Layer'
DEFAULT_NEW_VCOL_SUFFIX = ' VCol'

def channel_items(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp

    items = []

    for i, ch in enumerate(yp.channels):
        #if hasattr(lib, 'custom_icons'):
        if not is_greater_than_280():
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, i))
        else: items.append((str(i), ch.name, '', lib.channel_icon_dict[ch.type], i))

    #if hasattr(lib, 'custom_icons'):
    if not is_greater_than_280():
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

    #if is_greater_than_281() and layer.type in {'NOISE'}:
    #    items.append(('RGB', label + ' Color',  ''))
    #    items.append(('ALPHA', label + ' Factor',  ''))
    #else:
    if is_greater_than_281() and layer.type == 'VORONOI':
        items.append(('RGB', label + ' Color',  ''))
        items.append(('ALPHA', label + ' Distance',  ''))
    else:
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

def get_normal_map_type_items(self, context):
    items = []

    if is_greater_than_280():
        items.append(('BUMP_MAP', 'Bump Map', ''))
        items.append(('NORMAL_MAP', 'Normal Map', ''))
        items.append(('BUMP_NORMAL_MAP', 'Bump + Normal Map', ''))
    else: 
        items.append(('BUMP_MAP', 'Bump Map', '', 'MATCAP_09', 0))
        items.append(('NORMAL_MAP', 'Normal Map', '', 'MATCAP_23', 1))
        items.append(('BUMP_NORMAL_MAP', 'Bump + Normal Map', '', 'MATCAP_23', 1))

    return items

def load_hemi_props(layer, source):
    norm = source.node_tree.nodes.get('Normal')
    if norm: norm.outputs[0].default_value = layer.hemi_vector
    trans = source.node_tree.nodes.get('Vector Transform')
    if trans: trans.convert_from = layer.hemi_space

def add_new_layer(group_tree, layer_name, layer_type, channel_idx, 
        blend_type, normal_blend_type, normal_map_type, 
        texcoord_type, uv_name='', image=None, vcol=None, segment=None,
        solid_color = (1,1,1),
        add_mask=False, mask_type='IMAGE', mask_color='BLACK', mask_use_hdr=False, 
        mask_uv_name = '', mask_width=1024, mask_height=1024, use_image_atlas_for_mask=False,
        hemi_space = 'WORLD', hemi_use_prev_normal = True,
        mask_color_id=(1,0,1), mask_vcol_data_type='BYTE_COLOR', mask_vcol_domain='CORNER',
        use_divider_alpha = False, use_udim_for_mask=False
        ):

    yp = group_tree.yp
    #ypup = get_user_preferences()
    obj = bpy.context.object
    mat = obj.active_material

    # Halt rearrangements and reconnections until all nodes already created
    yp.halt_reconnect = True
    #yp.halt_update = True

    # Get parent and index dict
    parent_dict = get_parent_dict(yp)
    index_dict = get_index_dict(yp)

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
    check_uvmap_on_other_objects_with_same_mat(mat, uv_name)

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

    # Remap parents
    for lay in yp.layers:
        lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

    # Remap fcurves
    remap_layer_fcurves(yp, index_dict)

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
    if layer_type == 'VCOL':
        source = new_node(tree, layer, 'source', get_vcol_bl_idname(), 'Source')
    else: source = new_node(tree, layer, 'source', layer_node_bl_idnames[layer_type], 'Source')

    if layer_type == 'IMAGE':
        # Always set non color to image node because of linear pipeline
        if hasattr(source, 'color_space'):
            source.color_space = 'NONE'

        # Add new image if it's image layer
        source.image = image

    elif layer_type == 'VCOL':
        set_source_vcol_name(source, vcol.name)

    elif layer_type == 'COLOR':
        col = (solid_color[0], solid_color[1], solid_color[2], 1.0)
        source.outputs[0].default_value = col

    elif layer_type == 'HEMI':
        source.node_tree = get_node_tree_lib(lib.HEMI)
        duplicate_lib_node_tree(source)

        load_hemi_props(layer, source)
        layer.hemi_space = hemi_space
        layer.hemi_use_prev_normal = hemi_use_prev_normal

    # Add texcoord node
    texcoord = new_node(tree, layer, 'texcoord', 'NodeGroupInput', 'TexCoord Inputs')

    # Add mapping node
    if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'}:
        mapping = new_node(tree, layer, 'mapping', 'ShaderNodeMapping', 'Mapping')

    # Set layer coordinate type
    layer.texcoord_type = texcoord_type

    # Set layer spread fix
    #if image and image.is_float:
    #    layer.divide_rgb_by_alpha = True
    #else: 
    layer.divide_rgb_by_alpha = use_divider_alpha

    # Add channels to current layer
    for root_ch in yp.channels:
        ch = layer.channels.add()

    if add_mask:

        #mask_name = 'Mask ' + layer.name
        mask_name = Mask.get_new_mask_name(obj, layer, mask_type)
        mask_image = None
        mask_vcol = None
        mask_segment = None

        if mask_type == 'IMAGE':

            color = (0,0,0,0)
            if mask_color == 'WHITE':
                color = (1,1,1,1)
            elif mask_color == 'BLACK':
                color = (0,0,0,1)

            if use_udim_for_mask:
                objs = get_all_objects_with_same_materials(mat)
                tilenums = UDIM.get_tile_numbers(objs, mask_uv_name)

            if use_image_atlas_for_mask:
                if use_udim_for_mask:
                    mask_segment = UDIM.get_set_udim_atlas_segment(tilenums,
                            mask_width, mask_height, color, colorspace='Non-Color', hdr=mask_use_hdr, yp=yp)
                else:
                    mask_segment = ImageAtlas.get_set_image_atlas_segment(
                            mask_width, mask_height, mask_color, mask_use_hdr, yp=yp)
                mask_image = mask_segment.id_data
            else:
                if use_udim_for_mask:
                    mask_image = bpy.data.images.new(mask_name, 
                            width=mask_width, height=mask_height, alpha=False, float_buffer=mask_use_hdr, tiled=True)

                    # Fill tiles
                    for tilenum in tilenums:
                        UDIM.fill_tile(mask_image, tilenum, color, mask_width, mask_height)
                    UDIM.initial_pack_udim(mask_image, color)

                else:
                    mask_image = bpy.data.images.new(mask_name, 
                            width=mask_width, height=mask_height, alpha=False, float_buffer=mask_use_hdr)

                mask_image.generated_color = color
                if hasattr(mask_image, 'use_alpha'):
                    mask_image.use_alpha = False

            if mask_image.colorspace_settings.name != 'Non-Color' and not mask_image.is_dirty:
                mask_image.colorspace_settings.name = 'Non-Color'

        # New vertex color
        elif mask_type in {'VCOL', 'COLOR_ID'}:
            objs = [obj]
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            if mask_type == 'VCOL':

                for o in objs:
                    if mask_name not in get_vertex_colors(o):
                        try:
                            mask_vcol = new_vertex_color(o, mask_name, mask_vcol_data_type, mask_vcol_domain)
                            if mask_color == 'WHITE':
                                set_obj_vertex_colors(o, mask_vcol.name, (1.0, 1.0, 1.0, 1.0))
                            elif mask_color == 'BLACK':
                                set_obj_vertex_colors(o, mask_vcol.name, (0.0, 0.0, 0.0, 1.0))
                            set_active_vertex_color(o, mask_vcol)
                        except Exception as e: print (e)
            elif mask_type == 'COLOR_ID':
                check_colorid_vcol(objs)

        mask = Mask.add_new_mask(layer, mask_name, mask_type, 'UV', #texcoord_type, 
                mask_uv_name, mask_image, mask_vcol, mask_segment)
        mask.active_edit = True

        if mask_type == 'COLOR_ID':
            mask.color_id = mask_color_id

    # Fill channel layer props
    shortcut_created = False
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        # Set some props to selected channel
        if layer.type in {'GROUP', 'BACKGROUND'} or channel_idx == i or channel_idx == -1:
            ch.enable = True
            if root_ch.type == 'NORMAL':
                ch.normal_blend_type = normal_blend_type
            else:
                ch.blend_type = blend_type
        else: 
            ch.enable = False

        if root_ch.type == 'NORMAL':
            ch.normal_map_type = normal_map_type
            
            # Background layer has default bump distance of 0.0
            if layer.type in {'BACKGROUND'}:
                ch.bump_distance = 0.0

        # Set linear node of layer channel
        check_layer_channel_linear_node(ch, layer, root_ch)

    # Check uv maps
    check_uv_nodes(yp)

    # Check and create layer channel nodes
    check_all_layer_channel_io_and_nodes(layer, tree) #, has_parent=has_parent)

    # Refresh paint image by updating the index
    yp.active_layer_index = index

    # Unhalt rearrangements and reconnections since all nodes already created
    yp.halt_reconnect = False
    #yp.halt_update = False

    # Rearrange node inside layers
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    return layer

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

class YUseLinearColorSpace(bpy.types.Operator):
    """This addon need to linear color space image to works properly"""
    bl_idname = "node.y_use_linear_color_space"
    bl_label = "Use Linear Color Space"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer') #and hasattr(context, 'channel') and hasattr(context, 'image') and context.image

    def execute(self, context):
        yp = context.layer.id_data.yp
        check_yp_linear_nodes(yp)

        return {'FINISHED'}

class YNewVcolToOverrideChannel(bpy.types.Operator):
    bl_idname = "node.y_new_vcol_to_override_channel"
    bl_label = "New Vertex Color To Override Channel Layer"
    bl_description = "New Vertex Color To Override Channel Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(default='')

    data_type : EnumProperty(
            name = 'Vertex Color Data Type',
            description = 'Vertex color data type',
            items = vcol_data_type_items,
            default='BYTE_COLOR')

    domain : EnumProperty(
            name = 'Vertex Color Domain',
            description = 'Vertex color domain',
            items = vcol_domain_items,
            default='CORNER')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.ch = context.parent

        yp = self.ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.ch.path_from_id())
        if not m: return []
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]
        self.tree = get_tree(layer)

        self.name = layer.name + ' ' + root_ch.name +  ' Override'

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column()
        col.label(text='Name:')

        if is_greater_than_320():
            col.label(text='Domain:')
            col.label(text='Data Type:')

        col = row.column()
        col.prop(self, 'name', text='')

        if is_greater_than_320():
            crow = col.row(align=True)
            crow.prop(self, 'domain', expand=True)
            crow = col.row(align=True)
            crow.prop(self, 'data_type', expand=True)

    def execute(self, context):

        T = time.time()

        ch = self.ch
        yp = ch.id_data.yp
        tree = self.tree
        obj = context.object
        mat = obj.active_material
        wm = context.window_manager

        if self.name == '' :
            self.report({'ERROR'}, "Vertex color cannot be empty!")
            return {'CANCELLED'}

        # Make sure channel is on
        if not ch.enable:
            ch.enable = True

        # Make sure override is on
        if not ch.override:
            ch.override = True

        objs = [obj]
        if mat.users > 1:
            for o in get_scene_objects():
                if o.type != 'MESH': continue
                if mat.name in o.data.materials and o not in objs:
                    objs.append(o)

        for o in objs:
            if self.name not in get_vertex_colors(o):
                try:
                    vcol = new_vertex_color(o, self.name, self.data_type, self.domain)
                    set_obj_vertex_colors(o, vcol.name, (1.0, 1.0, 1.0, 1.0))
                    set_active_vertex_color(o, vcol)
                except: pass

        # Update vcol cache
        if ch.override_type == 'VCOL':
            source_label = root_ch.name + ' Override : ' + ch.override_type
            vcol_node, dirty = check_new_node(tree, ch, 'source', get_vcol_bl_idname(), source_label, True)
        else: vcol_node, dirty = check_new_node(tree, ch, 'cache_vcol', get_vcol_bl_idname(), '', True)

        set_source_vcol_name(vcol_node, self.name)

        # Set vcol name attribute
        yp.halt_update = True
        ch.override_vcol_name = self.name
        yp.halt_update = False

        ch.override_type = 'VCOL'
        ch.active_edit = True

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Vertex Color is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def update_new_layer_uv_map(self, context):
    if not UDIM.is_udim_supported(): return
    if self.type != 'IMAGE': 
        self.use_udim = False
        return

    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat)
    self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_map)

def update_new_layer_mask_uv_map(self, context):
    if not UDIM.is_udim_supported(): return
    if self.mask_type != 'IMAGE': 
        self.use_udim_for_mask = False
        return

    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat)
    self.use_udim_for_mask = UDIM.is_uvmap_udim(objs, self.mask_uv_name)

class YNewLayer(bpy.types.Operator):
    bl_idname = "node.y_new_layer"
    bl_label = "New Layer"
    bl_description = "New Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(default='')

    type : EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    # For image layer
    width : IntProperty(name='Width', default = 1234, min=1, max=4096)
    height : IntProperty(name='Height', default = 1234, min=1, max=4096)
    #color : FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    #alpha : BoolProperty(name='Alpha', default=True)
    hdr : BoolProperty(name='32 bit Float', default=False)

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    channel_idx : EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = channel_items)
            #update=update_channel_idx_new_layer)

    blend_type : EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = blend_type_items,
        default = 'MIX')

    normal_blend_type : EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    solid_color : FloatVectorProperty(
            name='Solid Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    add_mask : BoolProperty(
            name = 'Add Mask',
            description = 'Add mask to new layer',
            default = False)

    mask_type : EnumProperty(
            name = 'Mask Type',
            description = 'Mask type',
            items = (
                ('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
                ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1),
                ('COLOR_ID', 'Color ID', '', 'COLOR', 2)
                ),
            default = 'IMAGE')

    mask_color : EnumProperty(
            name = 'Mask Color',
            description = 'Mask Color',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='BLACK')

    mask_width : IntProperty(name='Mask Width', default = 1234, min=1, max=4096)
    mask_height : IntProperty(name='Mask Height', default = 1234, min=1, max=4096)

    mask_uv_name : StringProperty(default='', update=update_new_layer_mask_uv_map)
    mask_use_hdr : BoolProperty(name='32 bit Float', default=False)

    mask_color_id : FloatVectorProperty(
            name='Color ID', size=3,
            subtype='COLOR',
            default=(1.0, 0.0, 1.0),
            min=0.0, max=1.0,
            )

    uv_map : StringProperty(default='', update=update_new_layer_uv_map)

    normal_map_type : EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = get_normal_map_type_items)
            #default = 'BUMP_MAP')

    use_udim : BoolProperty(
            name = 'Use UDIM Tiles',
            description='Use UDIM Tiles',
            default=False)

    use_udim_for_mask : BoolProperty(
            name = 'Use UDIM Tiles for Mask',
            description='Use UDIM Tiles for Mask',
            default=False)

    use_image_atlas : BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    use_image_atlas_for_mask : BoolProperty(
            name = 'Use Image Atlas for Mask',
            description='Use Image Atlas for Mask',
            default=False)

    hemi_space : EnumProperty(
            name = 'Fake Lighting Space',
            description = 'Fake lighting space',
            items = hemi_space_items,
            default='WORLD')

    hemi_use_prev_normal : BoolProperty(
            name = 'Use previous Normal',
            description = 'Take account previous Normal',
            default = True)

    vcol_data_type : EnumProperty(
            name = 'Vertex Color Data Type',
            description = 'Vertex color data type',
            items = vcol_data_type_items,
            default='BYTE_COLOR')

    vcol_domain : EnumProperty(
            name = 'Vertex Color Domain',
            description = 'Vertex color domain',
            items = vcol_domain_items,
            default='CORNER')

    mask_vcol_data_type : EnumProperty(
            name = 'Mask Vertex Color Data Type',
            description = 'Mask Vertex color data type',
            items = vcol_data_type_items,
            default='BYTE_COLOR')

    mask_vcol_domain : EnumProperty(
            name = 'Mask Vertex Color Domain',
            description = 'Mask Vertex color domain',
            items = vcol_domain_items,
            default='CORNER')

    use_divider_alpha : BoolProperty(
            name = 'Spread Fix',
            description='Use spread fix (very recommended for vertex color or image layer)',
            default=False)

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()
        #return hasattr(context, 'group_node') and context.group_node

    def invoke(self, context, event):

        ypup = get_user_preferences()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        if self.type == 'IMAGE':
            name = obj.active_material.name + DEFAULT_NEW_IMG_SUFFIX
            items = bpy.data.images
        elif self.type == 'VCOL' and obj.type == 'MESH':
            name = obj.active_material.name + DEFAULT_NEW_VCOL_SUFFIX
            items = get_vertex_colors(obj)
        else:
            name = [i[1] for i in layer_type_items if i[0] == self.type][0]
            items = yp.layers

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size
        if self.mask_width == 1234 and self.mask_height == 1234:
            self.mask_width = self.mask_height = ypup.default_new_image_size

        # Make sure add mask is inactive
        if self.type not in {'COLOR', 'BACKGROUND'}: #, 'GROUP'}:
            self.add_mask = False

        # Set spread fix by default on vertex color layer
        self.use_divider_alpha = True if self.type in {'VCOL'} else False

        # Use white color mask as default for group
        if self.type == 'GROUP':
            self.mask_color = 'WHITE'
        else: self.mask_color = 'BLACK'

        # Default normal map type is fine bump map
        #self.normal_map_type = 'FINE_BUMP_MAP'
        self.normal_map_type = 'BUMP_MAP'

        # Fake lighting default blend type is add
        if self.type == 'HEMI':
            self.blend_type = 'ADD'
        else: self.blend_type = 'MIX'

        # Layer name
        self.name = get_unique_name(name, items)

        # Layer name must also unique
        if self.type == 'IMAGE':
            self.name = get_unique_name(self.name, yp.layers)

        # Check if color id already being used
        while True:
            # Use color id tolerance value as lowest value to avoid pure black color
            self.mask_color_id = (random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0))
            if not is_colorid_already_being_used(yp, self.mask_color_id): break

        if obj.type != 'MESH':
            #self.texcoord_type = 'Object'
            self.texcoord_type = 'Generated'
        else:
            if obj.type == 'MESH':
                uv_name = get_default_uv_name(obj, yp)
                self.uv_map = uv_name
                if self.add_mask: self.mask_uv_name = uv_name

                # UV Map collections update
                self.uv_map_coll.clear()
                for uv in get_uv_layers(obj):
                    if not uv.name.startswith(TEMP_UV):
                        self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    #def is_mask_using_udim(self):
    #    return self.use_udim_for_mask and UDIM.is_udim_supported()

    #def is_mask_using_image_atlas(self):
    #    return self.use_image_atlas_for_mask and not self.is_mask_using_udim()

    def check(self, context):
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        if self.use_image_atlas_for_mask:
            if self.mask_use_hdr: mask_max_size = ypup.hdr_image_atlas_size
            else: mask_max_size = ypup.image_atlas_size
            if self.mask_width > mask_max_size: self.mask_width = mask_max_size
            if self.mask_height > mask_max_size: self.mask_height = mask_max_size

        # Init mask uv name
        if self.add_mask and self.mask_uv_name == '':

            node = get_active_ypaint_node()
            yp = node.node_tree.yp
            obj = context.object

            uv_name = get_default_uv_name(obj, yp)
            self.mask_uv_name = uv_name

        return True

    def get_to_be_cleared_image_atlas(self, context, yp):
        if self.type == 'IMAGE' and not self.add_mask and self.use_image_atlas:
            return ImageAtlas.check_need_of_erasing_segments(yp, 'TRANSPARENT', self.width, self.height, self.hdr)
        if self.add_mask and self.mask_type == 'IMAGE' and self.use_image_atlas_for_mask:
            return ImageAtlas.check_need_of_erasing_segments(yp, self.mask_color, self.mask_width, self.mask_height, self.hdr)

        return None

    def draw(self, context):
        #yp = self.group_node.node_tree.yp
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        if len(yp.channels) == 0:
            self.layout.label(text='No channel found! Still want to create a layer?', icon='ERROR')
            return

        try:
            channel_idx = int(self.channel_idx)
            if channel_idx != -1:
                channel = yp.channels[channel_idx]
            else: channel = None
        except: channel = None

        if is_greater_than_280():
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

        if self.type == 'VCOL' and is_greater_than_320():
            col.label(text='Domain:')
            col.label(text='Data Type:')

        #if self.type == 'IMAGE':
        #    col.label(text='')

        if self.type == 'HEMI':
            col.label(text='Space:')
            col.label(text='')

        if self.type == 'IMAGE':
            col.label(text='')
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type not in {'VCOL', 'GROUP', 'COLOR', 'BACKGROUND', 'HEMI'}:
            col.label(text='Vector:')

        if self.type in {'VCOL'}:
            col.label(text='')

        if self.type == 'IMAGE':
            col.label(text='')

        #if self.type in {'COLOR', 'GROUP', 'BACKGROUND'}:
        if self.type != 'IMAGE':
            col.label(text='')
            if self.add_mask:
                col.label(text='Mask Type:')
                if self.mask_type == 'COLOR_ID':
                    col.label(text='Mask Color ID:')
                else:
                    col.label(text='Mask Color:')
                    if self.mask_type == 'IMAGE':
                        col.label(text='')
                        col.label(text='Mask Width:')
                        col.label(text='Mask Height:')
                        col.label(text='Mask UV Map:')
                        if UDIM.is_udim_supported():
                            col.label(text='')
                        col.label(text='')
                if is_greater_than_320() and self.mask_type == 'VCOL':
                    col.label(text='Mask Domain:')
                    col.label(text='Mask Data Type:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')

        if self.type not in {'GROUP', 'BACKGROUND'}:
            rrow = col.row(align=True)
            rrow.prop(self, 'channel_idx', text='')
            if channel:
                if channel.type == 'NORMAL':
                    rrow.prop(self, 'normal_blend_type', text='')
                    col.prop(self, 'normal_map_type', text='')
                else: 
                    rrow.prop(self, 'blend_type', text='')

        if self.type == 'COLOR':
            col.prop(self, 'solid_color', text='')

        if self.type == 'VCOL' and is_greater_than_320():
            crow = col.row(align=True)
            crow.prop(self, 'vcol_domain', expand=True)
            crow = col.row(align=True)
            crow.prop(self, 'vcol_data_type', expand=True)

        if self.type == 'HEMI':
            col.prop(self, 'hemi_space', text='')
            col.prop(self, 'hemi_use_prev_normal')

        if self.type == 'IMAGE':
            col.prop(self, 'hdr')
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type not in {'VCOL', 'GROUP', 'COLOR', 'BACKGROUND', 'HEMI'}:
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if self.type in {'VCOL'}:
            col.prop(self, 'use_divider_alpha')

        if self.type == 'IMAGE':
            if UDIM.is_udim_supported():
                col.prop(self, 'use_udim')
            ccol = col.column()
            ccol.prop(self, 'use_image_atlas')

        if self.type != 'IMAGE':
            col.prop(self, 'add_mask', text='Add Mask')
            if self.add_mask:
                col.prop(self, 'mask_type', text='')
                if self.mask_type == 'COLOR_ID':
                    col.prop(self, 'mask_color_id', text='')
                else:
                    col.prop(self, 'mask_color', text='')
                    if self.mask_type == 'IMAGE':
                        col.prop(self, 'mask_use_hdr')
                        col.prop(self, 'mask_width', text='')
                        col.prop(self, 'mask_height', text='')
                        #col.prop_search(self, "mask_uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                        col.prop_search(self, "mask_uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
                        if UDIM.is_udim_supported():
                            col.prop(self, 'use_udim_for_mask')
                        ccol = col.column()
                        ccol.prop(self, 'use_image_atlas_for_mask', text='Use Image Atlas')
                if is_greater_than_320() and self.mask_type == 'VCOL':
                    crow = col.row(align=True)
                    crow.prop(self, 'mask_vcol_domain', expand=True)
                    crow = col.row(align=True)
                    crow.prop(self, 'mask_vcol_data_type', expand=True)

        if self.get_to_be_cleared_image_atlas(context, yp):
            col = self.layout.column(align=True)
            col.label(text='INFO: An unused atlas segment can be used.', icon='ERROR')
            col.label(text='It will take a couple seconds to clear.')

    def execute(self, context):

        T = time.time()

        #ypup = get_user_preferences()
        wm = context.window_manager
        area = context.area
        obj = context.object
        mat = obj.active_material
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypui = context.window_manager.ypui
        vcols = get_vertex_colors(obj)

        # Check if object is not a mesh
        if (self.type == 'VCOL' or (self.add_mask and self.mask_type == 'VCOL')) and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color only works with mesh object!")
            return {'CANCELLED'}

        if (not is_greater_than_330() and
                (
                ((self.type == 'VCOL' or (self.add_mask and self.mask_type == 'VCOL')) 
                and len(vcols) >= 8) 
            or
                ((self.type == 'VCOL' and (self.add_mask and self.mask_type == 'VCOL')) 
                and len(vcols) >= 7)
                )
            ):
            self.report({'ERROR'}, "Mesh can only use 8 vertex colors!")
            return {'CANCELLED'}

        # Check if layer with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in vcols if i.name == self.name]
        else: same_name = [lay for lay in yp.layers if lay.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
            elif self.type == 'VCOL':
                self.report({'ERROR'}, "Vertex Color named '" + self.name +"' is already available!")
            self.report({'ERROR'}, "Layer named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Clearing unused image atlas segments
        img_atlas = self.get_to_be_cleared_image_atlas(context, yp)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        img = None
        segment = None
        if self.type == 'IMAGE':

            alpha = True
            color = (0,0,0,0)

            if self.use_udim:
                objs = get_all_objects_with_same_materials(mat)
                tilenums = UDIM.get_tile_numbers(objs, self.uv_map)

            if self.use_image_atlas:
                if self.use_udim:
                    segment = UDIM.get_set_udim_atlas_segment(tilenums, self.width, self.height, color, 'sRGB', self.hdr, yp)
                else:
                    segment = ImageAtlas.get_set_image_atlas_segment(
                            self.width, self.height, 'TRANSPARENT', self.hdr, yp=yp) #, ypup.image_atlas_size)
                img = segment.id_data
            else:

                if self.use_udim:
                    img = bpy.data.images.new(name=self.name, width=self.width, height=self.height, 
                            alpha=alpha, float_buffer=self.hdr, tiled=True)

                    # Fill tiles
                    for tilenum in tilenums:
                        UDIM.fill_tile(img, tilenum, color, self.width, self.height)
                    UDIM.initial_pack_udim(img, color)

                else:
                    img = bpy.data.images.new(name=self.name, width=self.width, height=self.height, 
                            alpha=alpha, float_buffer=self.hdr)

                #img.generated_type = self.generated_type
                img.generated_type = 'BLANK'
                img.generated_color = color
                if hasattr(img, 'use_alpha'):
                    img.use_alpha = True

            #if img.colorspace_settings.name != 'Non-Color':
            #    img.colorspace_settings.name = 'Non-Color'

            update_image_editor_image(context, img)

        vcol = None
        if self.type == 'VCOL':

            objs = [obj]
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            for o in objs:
                if self.name not in get_vertex_colors(o):
                    try:
                        vcol = new_vertex_color(o, self.name, self.vcol_data_type, self.vcol_domain)

                        if is_greater_than_292():
                            set_obj_vertex_colors(o, vcol.name, (0.0, 0.0, 0.0, 0.0))
                        else: set_obj_vertex_colors(o, vcol.name, (1.0, 1.0, 1.0, 1.0))

                        set_active_vertex_color(o, vcol)
                    except Exception as e: print(e)

        yp.halt_update = True

        try: channel_idx = int(self.channel_idx)
        except: channel_idx = 0

        layer = add_new_layer(node.node_tree, self.name, self.type, 
                channel_idx, self.blend_type, self.normal_blend_type, 
                self.normal_map_type, self.texcoord_type, self.uv_map, img, vcol, segment,
                self.solid_color,
                self.add_mask, self.mask_type, self.mask_color, self.mask_use_hdr, 
                self.mask_uv_name, self.mask_width, self.mask_height, self.use_image_atlas_for_mask, 
                self.hemi_space, self.hemi_use_prev_normal, self.mask_color_id,
                self.mask_vcol_data_type, self.mask_vcol_domain, self.use_divider_alpha,
                self.use_udim_for_mask)

        if segment:
            ImageAtlas.set_segment_mapping(layer, segment, img)
            refresh_temp_uv(obj, layer)

        yp.halt_update = False

        # Reconnect and rearrange nodes
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        if self.type != 'IMAGE':
            ypui.layer_ui.expand_content = True
        ypui.need_update = True

        print('INFO: Layer', layer.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenImageToOverrideChannel(bpy.types.Operator, ImportHelper):
    """Open Image to Override Channel"""
    bl_idname = "node.y_open_image_to_override_layer_channel"
    bl_label = "Open Image to Override Channel Layer"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.ch = context.parent
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def execute(self, context):
        ch = self.ch
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()

        import_list, directory = self.generate_paths()
        loaded_images = tuple(load_image(path, directory) for path in import_list)

        images = []
        for i, new_img in enumerate(loaded_images):

            # Check for existing images
            old_image_found = False
            for old_img in bpy.data.images:
                if old_img.filepath == new_img.filepath:
                    images.append(old_img)
                    old_image_found = True
                    break

            if not old_image_found:
                images.append(new_img)

        # Remove already existing images
        for img in loaded_images:
            if img not in images:
                bpy.data.images.remove(img)

        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m: return []
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]
        tree = get_tree(layer)

        # Make sure channel is on
        if not ch.enable:
            ch.enable = True

        image = None
        image_1 = None

        if root_ch.type == 'NORMAL':
            for img in images:
                img_name = os.path.splitext(os.path.basename(img.filepath))[0].lower()
                # Image 1 will represents normal
                if 'normal' in img_name or 'norm' in img_name or img_name.endswith(('_nor', '.nor', '_n', '.n')):
                    image_1 = img
                elif not image:
                    image = img

                if image and image_1:
                    break
        else:
            image = images[0]

        if image:
            # Make sure override is on
            if not ch.override:
                ch.override = True

            # Update image cache
            if ch.override_type == 'IMAGE':
                source_tree = get_channel_source_tree(ch, layer)
                source_label = root_ch.name + ' Override : ' + ch.override_type
                image_node, dirty = check_new_node(source_tree, ch, 'source', 'ShaderNodeTexImage', source_label, True)
            else:
                image_node, dirty = check_new_node(tree, ch, 'cache_image', 'ShaderNodeTexImage', '', True)

            image_node.image = image
            ch.override_type = 'IMAGE'
            ch.active_edit = True

        if image_1:

            if not ch.override_1:
                ch.override_1 = True

            # Update image 1 cache
            if ch.override_1_type == 'IMAGE':
                source_label = root_ch.name + ' Override 1 : ' + ch.override_1_type
                image_node_1, dirty = check_new_node(tree, ch, 'source_1', 'ShaderNodeTexImage', source_label, True)
            else:
                image_node_1, dirty = check_new_node(tree, ch, 'cache_1_image', 'ShaderNodeTexImage', '', True)

            image_node_1.image = image_1
            ch.override_1_type = 'IMAGE'
            ch.active_edit_1 = True

        if root_ch.type == 'NORMAL':

            if image and image_1:
                if ch.normal_map_type != 'BUMP_NORMAL_MAP':
                    ch.normal_map_type = 'BUMP_NORMAL_MAP'

            elif image_1:
                if ch.normal_map_type == 'BUMP_MAP':
                    ch.normal_map_type = 'NORMAL_MAP'

            elif image:
                if ch.normal_map_type == 'NORMAL_MAP':
                    ch.normal_map_type = 'BUMP_MAP'

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenImageToOverride1Channel(bpy.types.Operator, ImportHelper):
    """Open Image to Override 1 Channel"""
    bl_idname = "node.y_open_image_to_override_1_layer_channel"
    bl_label = "Open Image to Override 1 Channel Layer"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.ch = context.parent
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def execute(self, context):
        ch = self.ch
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()

        import_list, directory = self.generate_paths()
        loaded_images = tuple(load_image(path, directory) for path in import_list)

        images = []
        for i, new_img in enumerate(loaded_images):

            # Check for existing images
            old_image_found = False
            for old_img in bpy.data.images:
                if old_img.filepath == new_img.filepath:
                    images.append(old_img)
                    old_image_found = True
                    break

            if not old_image_found:
                images.append(new_img)

        # Remove already existing images
        for img in loaded_images:
            if img not in images:
                bpy.data.images.remove(img)

        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m: return []
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]
        tree = get_tree(layer)

        # Make sure channel is on
        if not ch.enable:
            ch.enable = True

        image = None
        image_1 = None

        for img in images:
            img_name = os.path.splitext(os.path.basename(img.filepath))[0].lower()
            # Image 1 will represents bump
            if 'displacement' in img_name or 'bump' in img_name or img_name.endswith(('_disp', '.disp')):
                image_1 = img
            elif not image:
                image = img

            if image and image_1:
                break

        #print(images)

        if image:
            # Make sure override is on
            if not ch.override_1:
                ch.override_1 = True

            # Update image cache
            if ch.override_1_type == 'IMAGE':
                source_label = root_ch.name + ' Override 1 : ' + ch.override_1_type
                image_node, dirty = check_new_node(tree, ch, 'source_1', 'ShaderNodeTexImage', source_label, True)
            else:
                image_node, dirty = check_new_node(tree, ch, 'cache_1_image', 'ShaderNodeTexImage', '', True)
                #print(image_node, dirty)

            image_node.image = image
            ch.override_1_type = 'IMAGE'
            ch.active_edit_1 = True

        if image_1:

            # Make sure override is on
            if not ch.override:
                ch.override = True

            # Update image 1 cache
            if ch.override_type == 'IMAGE':
                source_tree = get_channel_source_tree(ch, layer)
                source_label = root_ch.name + ' Override : ' + ch.override_type
                image_node_1, dirty = check_new_node(source_tree, ch, 'source', 'ShaderNodeTexImage', source_label, True)
            else:
                image_node_1, dirty = check_new_node(tree, ch, 'cache_image', 'ShaderNodeTexImage', '', True)

            image_node_1.image = image_1
            ch.override_type = 'IMAGE'
            ch.active_edit = True

        if image and image_1:
            if ch.normal_map_type != 'BUMP_NORMAL_MAP':
                ch.normal_map_type = 'BUMP_NORMAL_MAP'

        elif image_1:
            if ch.normal_map_type == 'NORMAL_MAP':
                ch.normal_map_type = 'BUMP_MAP'

        elif image:
            if ch.normal_map_type == 'BUMP_MAP':
                ch.normal_map_type = 'NORMAL_MAP'

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class BaseMultipleImagesLayer():
    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    add_mask : BoolProperty(
            name = 'Add Mask',
            description = 'Add mask to new layer',
            default = False)

    mask_type : EnumProperty(
            name = 'Mask Type',
            description = 'Mask type',
            items = (('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
                ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1)),
            default = 'IMAGE')

    mask_color : EnumProperty(
            name = 'Mask Color',
            description = 'Mask Color',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='BLACK')

    mask_width : IntProperty(name='Mask Width', default = 1234, min=1, max=4096)
    mask_height : IntProperty(name='Mask Height', default = 1234, min=1, max=4096)

    mask_uv_name : StringProperty(default='', update=update_new_layer_mask_uv_map)
    mask_use_hdr : BoolProperty(name='32 bit Float', default=False)

    use_udim_for_mask : BoolProperty(
            name = 'Use UDIM Tiles for Mask',
            description='Use UDIM Tiles for Mask',
            default=False)

    use_image_atlas_for_mask : BoolProperty(
            name = 'Use Image Atlas for Mask',
            description='Use Image Atlas for Mask',
            default=False)

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    #def is_mask_using_udim(self):
    #    return self.use_udim_for_mask and UDIM.is_udim_supported()

    #def is_mask_using_image_atlas(self):
    #    return self.use_image_atlas_for_mask and not self.is_mask_using_udim()
    
    def open_images_to_single_layer(self, context:bpy.context, directory:str, import_list) -> bool:
    
        T = time.time()

        #images = tuple(load_image(path, directory) for path in import_list)
        images = list(load_image(path, directory) for path in import_list)

        # Check existing images
        #exist_images = []
        #for i, new_img in enumerate(images):
        #    for old_img in bpy.data.images:
        #        if old_img.filepath == new_img.filepath:
        #            exist_images.append(old_img)
        #            break

        #print(images)

        valid_channels = []
        valid_images = []
        valid_synonyms = []
        #channel_ids = []

        # Dict

        # Check image names
        #for image in images:

        #    # Get filename without extension
        #    name = os.path.splitext(os.path.basename(image.filepath))[0]
        #    #print(name)

        #    for i, ch in enumerate(yp.channels):

        #        # Check image name suffix and match it with channel name
        #        if name.lower().endswith(ch.name.lower()):
        #            valid_images.append(image)
        #            channel_ids.append(i)

        #        # Check displacement
        #        elif name.lower().endswith('displacement') and ch.type == 'NORMAL':
        #            valid_images.append(image)
        #            channel_ids.append(i)

        synonym_libs = {
                'color' : ['albedo', 'diffuse', 'base color'], 
                'ambient occlusion' : ['ao'], 
                'roughness' : ['glossiness'],
                'normal' : ['displacement', 'height', 'bump'], # Prioritize displacement/bump before actual normal map
                }

        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        for ch in yp.channels:

            # One channel will only use one image
            if ch in valid_channels: continue

            ch_name = ch.name.lower()

            # Get synonyms
            synonyms = []
            if ch_name in synonym_libs:
                synonyms = synonym_libs[ch_name]
            synonyms.append(ch_name)

            # Normal channel can use two override images, this flag will check it
            secondary_imgae_found = False
            main_image_found = False
                
            for syname in synonyms:

                # Break if channel already used
                #if ch in valid_channels: break
                if main_image_found: break
            
                # Get channel name possible variation
                initial = syname[0]

                if len(ch.name) > 3:
                    threes = syname[:3]
                else: threes = ''

                no_whitespace = syname.replace(' ', '')
                underscore = syname.replace(' ', '_')

                for image in images:

                    # One image will only use one channel
                    if image in valid_images: continue

                    # Get filename without extension
                    img_name = os.path.splitext(os.path.basename(image.filepath))[0].lower()

                    if (
                            ## Check image name suffix and match it with channel name
                            #(img_name.endswith(syname)) or

                            #(img_name.endswith(no_whitespace)) or

                            #(img_name.endswith(underscore)) or

                            # Check if synonym is in image name
                            (syname in img_name) or

                            (no_whitespace in img_name) or

                            (underscore in img_name) or

                            # Check image name suffix and match it with channel initial first threes
                            (threes != '' and img_name.endswith(('_' + threes, '.' + threes))) or

                            # Check image name suffix and match it with channel initial name
                            # Avoid initial a because it's too common
                            (initial != 'a' and img_name.endswith(('_' + initial, '.' + initial)))

                            ):
                        valid_images.append(image)
                        valid_channels.append(ch)
                        valid_synonyms.append(syname)

                        if ch.type != 'NORMAL' or secondary_imgae_found:
                            main_image_found = True
                            break

                        secondary_imgae_found = True

        for i, image in enumerate(valid_images):
            #print(image.name, yp.channels[channel_ids[i]].name)
            print(image.name, valid_channels[i].name, valid_synonyms[i])

        if not valid_images:
            # Remove loaded images
            for image in images:
                #if image not in exist_images:
                bpy.data.images.remove(image)
            return False

        # Check if found more than 1 images for normal channel
        
        if len([ch for ch in valid_channels if ch.type == 'NORMAL']) >= 2:
            normal_map_type = 'BUMP_NORMAL_MAP'
        elif any([ch for i, ch in enumerate(valid_channels) if ch.type == 'NORMAL' and valid_synonyms[i] == 'normal']):
            normal_map_type = 'NORMAL_MAP'
        else: normal_map_type = 'BUMP_MAP'

        #if valid_channels and valid_channels[0]
        layer = None
        for i, image in enumerate(valid_images):
            root_ch = valid_channels[i]
            syname = valid_synonyms[i]

            # Set image to linear
            #if image.colorspace_settings.name != 'Non-Color':
            #    image.colorspace_settings.name = 'Non-Color'

            m = re.match(r'^yp\.channels\[(\d+)\].*', root_ch.path_from_id())
            ch_idx = int(m.group(1))

            # Use image directly to layer for the first index
            if i == 0:
                yp.halt_update = True
                #layer = add_new_layer(node.node_tree, image.name, 'IMAGE', int(ch_idx), 'MIX', 
                #        'MIX', normal_map_type, self.texcoord_type, self.uv_map,
                #        image, None, None, 
                #        )

                                                 
                layer = add_new_layer(node.node_tree, image.name, 'IMAGE', 
                        int(ch_idx), 'MIX', 'MIX', 
                        normal_map_type, self.texcoord_type, self.uv_map, image, None, None,
                        (1,1,1),self.add_mask, self.mask_type, self.mask_color, self.mask_use_hdr, 
                        self.mask_uv_name, self.mask_width, self.mask_height, self.use_image_atlas_for_mask, 
                        use_udim_for_mask=self.use_udim_for_mask)

                yp.halt_update = False
                #reconnect_yp_nodes(node.node_tree)
                #rearrange_yp_nodes(node.node_tree)
                tree = get_tree(layer)
            else:
                ch = layer.channels[ch_idx]
                ch.enable = True
                if root_ch.type == 'NORMAL' and syname == 'normal':
                    image_node, dirty = check_new_node(tree, ch, 'cache_1_image', 'ShaderNodeTexImage', '', True)
                    image_node.image = image
                    ch.override_1 = True
                    ch.override_1_type = 'IMAGE'
                else:
                    image_node, dirty = check_new_node(tree, ch, 'cache_image', 'ShaderNodeTexImage', '', True)
                    image_node.image = image
                    ch.override = True
                    ch.override_type = 'IMAGE'

        ## Reconnect and rearrange nodes
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Remove unused images
        for image in images:
            if image not in valid_images: # and image not in exist_images:
                bpy.data.images.remove(image)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        # Make sure to expand channels so it can be obvious which channels are active
        wm.ypui.expand_channels = True

    def invoke_operator(self, context:bpy.context):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()

        # Use user preference default image size if input uses default image size
        if self.mask_width == 1234 and self.mask_height == 1234:
            self.mask_width = self.mask_height = ypup.default_new_image_size

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH':
            uv_name = get_default_uv_name(obj, yp)
            self.uv_map = uv_name
            if self.add_mask and self.mask_type == 'IMAGE': self.mask_uv_name = uv_name

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # Normal map is the default
        #self.normal_map_type = 'NORMAL_MAP'

        #return context.window_manager.invoke_props_dialog(self)
    def draw_operator(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        #channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        
        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')

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

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

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
                if UDIM.is_udim_supported():
                    col.prop(self, 'use_udim_for_mask')
                ccol = col.column()
                ccol.prop(self, 'use_image_atlas_for_mask', text='Use Image Atlas')

        #col.label(text='')
        #rrow = col.row(align=True)
        #rrow.prop(self, 'channel_idx', text='')
        #if channel:
        #    if channel.type == 'NORMAL':
        #        rrow.prop(self, 'normal_blend_type', text='')
        #        col.prop(self, 'normal_map_type', text='')
        #    else: 
        #        rrow.prop(self, 'blend_type', text='')

        self.layout.prop(self, 'relative')

    def check_operator(self, context:bpy.context):
        ypup = get_user_preferences()
        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas_for_mask:
            if self.mask_use_hdr: mask_max_size = ypup.hdr_image_atlas_size
            else: mask_max_size = ypup.image_atlas_size
            if self.mask_width > mask_max_size: self.mask_width = mask_max_size
            if self.mask_height > mask_max_size: self.mask_height = mask_max_size

        # Init mask uv name
        if self.add_mask and self.mask_uv_name == '':

            node = get_active_ypaint_node()
            yp = node.node_tree.yp
            obj = context.object

            uv_name = get_default_uv_name(obj, yp)
            self.mask_uv_name = uv_name


class YOpenMultipleImagesToSingleLayer(bpy.types.Operator, ImportHelper, BaseMultipleImagesLayer):
    """Open Multiple Images to Single Layer"""
    bl_idname = "node.y_open_multiple_images_to_single_layer"
    bl_label = "Open Multiple Images to Single Layer"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.invoke_operator(context)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return self.check_operator(context)

    def draw(self, context):
        self.draw_operator(context)

    def execute(self, context):
        import_list, directory = self.generate_paths()
        if not self.open_images_to_single_layer(context, directory, import_list):
            self.report({'ERROR'}, "Images should have channel name as suffix!")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class YOpenImageToLayer(bpy.types.Operator, ImportHelper):
    """Open Image to Layer"""
    bl_idname = "node.y_open_image_to_layer"
    bl_label = "Open Image to Layer"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')

    channel_idx : EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = channel_items)
            #update=update_channel_idx_new_layer)

    blend_type : EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend_type : EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    normal_map_type : EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = get_normal_map_type_items)
            #default = 'NORMAL_MAP')

    use_udim_detecting : BoolProperty(
            name = 'Detect UDIMs',
            description = 'Detect selected UDIM files and load all matching tiles.',
            default = True)

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

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

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH':
            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # Normal map is the default
        #self.normal_map_type = 'NORMAL_MAP'

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

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend_type', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        self.layout.prop(self, 'relative')

        if UDIM.is_udim_supported():
            self.layout.prop(self, 'use_udim_detecting')

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()

        import_list, directory = self.generate_paths()
        if not UDIM.is_udim_supported():
            images = tuple(load_image(path, directory) for path in import_list)
        else:
            ori_ui_type = bpy.context.area.ui_type
            bpy.context.area.ui_type = 'IMAGE_EDITOR'
            images = []
            for path in import_list:
                bpy.ops.image.open(filepath=directory+os.sep+path, directory=directory, 
                        relative_path=self.relative, use_udim_detecting=self.use_udim_detecting)
                image = bpy.context.space_data.image
                if image not in images:
                    images.append(image)
            bpy.context.area.ui_type = ori_ui_type

        node.node_tree.yp.halt_update = True

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            add_new_layer(node.node_tree, image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                    self.normal_blend_type, self.normal_map_type, self.texcoord_type, self.uv_map,
                    image, None, None, 
                    )

        node.node_tree.yp.halt_update = False

        # Reconnect and rearrange nodes
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableDataToOverride1Channel(bpy.types.Operator):
    """Open Available Data to Override 1 Channel Layer"""
    bl_idname = "node.y_open_available_data_to_override_1_channel"
    bl_label = "Open Available Data to Override 1 Channel Layer"
    bl_options = {'REGISTER', 'UNDO'}

    image_name : StringProperty(name="Image")
    image_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.ch = context.parent
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        # Update image names
        self.image_coll.clear()
        imgs = bpy.data.images
        baked_channel_images = get_all_baked_channel_images(node.node_tree)
        for img in imgs:
            if not img.yia.is_image_atlas and img not in baked_channel_images:
                self.image_coll.add().name = img.name

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')

    def execute(self, context):
        T = time.time()
        wm = context.window_manager

        obj = context.object
        mat = obj.active_material

        ch = self.ch
        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m: return []
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]
        tree = get_tree(layer)

        # Make sure channel is on
        if not ch.enable:
            ch.enable = True

        if self.image_name == '':
            self.report({'ERROR'}, "Image name cannot be empty!")
            return {'CANCELLED'}
        image = bpy.data.images.get(self.image_name)

        if not image:
            self.report({'ERROR'}, "Image named " + self.image_name + " is not found!")
            return {'CANCELLED'}

        should_be_bump = False

        #img_name = os.path.splitext(os.path.basename(image.filepath))[0].lower()
        img_name = image.name.lower()
        if 'displacement' in img_name or 'bump' in img_name or img_name.endswith(('_disp', '.disp')):
            should_be_bump = True

        # Update image cache
        if should_be_bump:
            # Make sure override is on
            if not ch.override:
                ch.override = True

            if ch.override_type == 'IMAGE':
                source_tree = get_channel_source_tree(ch, layer)
                source_label = root_ch.name + ' Override : ' + ch.override_type
                image_node, dirty = check_new_node(source_tree, ch, 'source', 'ShaderNodeTexImage', source_label, True)
            else: image_node, dirty = check_new_node(tree, ch, 'cache_image', 'ShaderNodeTexImage', '', True)
        else:

            # Make sure override is on
            if not ch.override_1:
                ch.override_1 = True

            if ch.override_1_type == 'IMAGE':
                #source_tree = get_channel_source_tree(ch, layer)
                source_label = root_ch.name + ' Override 1 : ' + ch.override_1_type
                image_node, dirty = check_new_node(tree, ch, 'source_1', 'ShaderNodeTexImage', source_label, True)
            else: image_node, dirty = check_new_node(tree, ch, 'cache_1_image', 'ShaderNodeTexImage', '', True)

        image_node.image = image
        #if image.colorspace_settings.name != 'Non-Color':
        #    image.colorspace_settings.name = 'Non-Color'

        if should_be_bump:
            ch.override_type = 'IMAGE'
            if ch.normal_map_type != 'BUMP_NORMAL_MAP': ch.normal_map_type = 'BUMP_MAP'
            ch.active_edit = True
        else:
            ch.override_1_type = 'IMAGE'
            ch.active_edit_1 = True

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Data is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableDataToOverrideChannel(bpy.types.Operator):
    """Open Available Data to Override Channel Layer"""
    bl_idname = "node.y_open_available_data_to_override_channel"
    bl_label = "Open Available Data to Override Channel Layer"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Layer Type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    image_name : StringProperty(name="Image")
    image_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name : StringProperty(name="Vertex Color")
    vcol_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.ch = context.parent
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            baked_channel_images = get_all_baked_channel_images(node.node_tree)
            for img in imgs:
                if not img.yia.is_image_atlas and img not in baked_channel_images:
                    self.image_coll.add().name = img.name
        elif self.type == 'VCOL':
            self.vcol_coll.clear()
            for vcol in get_vertex_colors(obj):
                self.vcol_coll.add().name = vcol.name

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = context.object

        if self.type == 'IMAGE':
            self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        elif self.type == 'VCOL':
            self.layout.prop_search(self, "vcol_name", self, "vcol_coll", icon='GROUP_VCOL')

    def execute(self, context):
        T = time.time()
        wm = context.window_manager

        obj = context.object
        mat = obj.active_material

        ch = self.ch
        yp = ch.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m: return []
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]
        tree = get_tree(layer)

        # Make sure channel is on
        if not ch.enable:
            ch.enable = True

        # To check if normal image is selected
        should_be_normal = False

        if self.type == 'IMAGE':
            if self.image_name == '':
                self.report({'ERROR'}, "Image name cannot be empty!")
                return {'CANCELLED'}
            image = bpy.data.images.get(self.image_name)

            if not image:
                self.report({'ERROR'}, "Image named " + self.image_name + " is not found!")
                return {'CANCELLED'}

            if root_ch.type == 'NORMAL':
                #img_name = os.path.splitext(os.path.basename(image.filepath))[0].lower()
                img_name = image.name.lower()
                if 'normal' in img_name or 'norm' in img_name or img_name.endswith(('_nor', '.nor', '_n', '.n')):
                    should_be_normal = True

            # Make sure override is on
            if should_be_normal:
                ch.override_1 = True
            else: ch.override = True

            # Update image cache
            if should_be_normal:
                if ch.override_1_type == 'IMAGE':
                    source_label = root_ch.name + ' Override 1 : ' + ch.override_1_type
                    image_node, dirty = check_new_node(tree, ch, 'source_1', 'ShaderNodeTexImage', source_label, True)
                else:
                    image_node, dirty = check_new_node(tree, ch, 'cache_1_image', 'ShaderNodeTexImage', '', True)
            else:
                if ch.override_type == 'IMAGE':
                    source_tree = get_channel_source_tree(ch, layer)
                    source_label = root_ch.name + ' Override : ' + ch.override_type
                    image_node, dirty = check_new_node(source_tree, ch, 'source', 'ShaderNodeTexImage', source_label, True)
                else: image_node, dirty = check_new_node(tree, ch, 'cache_image', 'ShaderNodeTexImage', '', True)

            image_node.image = image
            #if image.colorspace_settings.name != 'Non-Color':
            #    image.colorspace_settings.name = 'Non-Color'

        elif self.type == 'VCOL':

            if self.vcol_name == '':
                self.report({'ERROR'}, "Vertex Color name cannot be empty!")
                return {'CANCELLED'}

            vcols = get_vertex_colors(obj)
            vcol = vcols.get(self.vcol_name)
            if not vcol:
                self.report({'ERROR'}, "Vertex Color named " + self.vcol_name + " is not found!")
                return {'CANCELLED'}

            # Make sure override is on
            if not ch.override:
                ch.override = True

            objs = [obj]
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            for o in objs:

                if self.vcol_name not in get_vertex_colors(o):
                    try:
                        if is_greater_than_320():
                            other_v = new_vertex_color(o, self.vcol_name, vcol.data_type, vcol.domain)
                        else: other_v = new_vertex_color(o, self.vcol_name)
                        #if vcol_color == 'WHITE':
                        #    set_obj_vertex_colors(o, other_v.name, (1.0, 1.0, 1.0, 1.0))
                        #elif vcol_color == 'BLACK':
                        #    set_obj_vertex_colors(o, other_v.name, (0.0, 0.0, 0.0, 1.0))
                        set_obj_vertex_colors(o, other_v.name, (0.0, 0.0, 0.0, 1.0))
                        set_active_vertex_color(o, other_v)
                    except Exception as e: pass

            # Update vcol cache
            if ch.override_type == 'VCOL':
                source_label = root_ch.name + ' Override : ' + ch.override_type
                vcol_node, dirty = check_new_node(tree, ch, 'source', get_vcol_bl_idname(), source_label, True)
            else: vcol_node, dirty = check_new_node(tree, ch, 'cache_vcol', get_vcol_bl_idname(), '', True)

            set_source_vcol_name(vcol_node, self.vcol_name)

            # Set vcol name attribute
            yp.halt_update = True
            ch.override_vcol_name = self.vcol_name
            yp.halt_update = False

        if should_be_normal:
            ch.override_1_type = self.type
            if ch.normal_map_type != 'BUMP_NORMAL_MAP': ch.normal_map_type = 'NORMAL_MAP'
            ch.active_edit_1 = self.type in {'IMAGE', 'VCOL'}
        else:
            ch.override_type = self.type
            ch.active_edit = self.type in {'IMAGE', 'VCOL'}

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Data is opened at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableDataToLayer(bpy.types.Operator):
    """Open Available Data to Layer"""
    bl_idname = "node.y_open_available_data_to_layer"
    bl_label = "Open Available Data to Layer"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Layer Type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')

    channel_idx : EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = channel_items)
            #update=update_channel_idx_new_layer)

    blend_type : EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend_type : EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    normal_map_type : EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = get_normal_map_type_items)
            #default = 'BUMP_MAP')

    image_name : StringProperty(name="Image")
    image_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name : StringProperty(name="Vertex Color")
    vcol_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_ypaint_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH':
            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            baked_channel_images = get_all_baked_channel_images(node.node_tree)
            for img in imgs:
                if not img.yia.is_image_atlas and img not in baked_channel_images:
                    self.image_coll.add().name = img.name
        elif self.type == 'VCOL':
            self.vcol_coll.clear()
            for vcol in get_vertex_colors(obj):
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
                rrow.prop(self, 'normal_blend_type', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

    def execute(self, context):
        T = time.time()

        obj = context.object
        mat = obj.active_material
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
            #if image.colorspace_settings.name != 'Non-Color':
            #    image.colorspace_settings.name = 'Non-Color'
        elif self.type == 'VCOL':
            vcols = get_vertex_colors(obj)
            vcol = vcols.get(self.vcol_name)
            name = vcol.name

            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH' or o == obj: continue
                    if mat.name in o.data.materials and self.vcol_name not in get_vertex_colors(o):
                        try:
                            if is_greater_than_320():
                                other_v = new_vertex_color(o, self.vcol_name, vcol.data_type, vcol.domain)
                            else: other_v = new_vertex_color(o, self.vcol_name)
                            if is_greater_than_292():
                                set_obj_vertex_colors(o, other_v.name, (0.0, 0.0, 0.0, 0.0))
                            else: set_obj_vertex_colors(o, other_v.name, (0.0, 0.0, 0.0, 1.0))
                            set_active_vertex_color(o, other_v)
                        except: pass

        add_new_layer(node.node_tree, name, self.type, int(self.channel_idx), self.blend_type, 
                self.normal_blend_type, self.normal_map_type, self.texcoord_type, self.uv_map, 
                image, vcol, None, 
                )

        node.node_tree.yp.halt_update = False

        # Reconnect and rearrange nodes
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

    direction : EnumProperty(
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

        # Remember parent and indices
        parent_dict = get_parent_dict(yp)
        index_dict = get_index_dict(yp)
        
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

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        layer = yp.layers[yp.active_layer_index]
        #has_parent = layer.parent_idx != -1

        # Check uv maps
        check_uv_nodes(yp)

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

    direction : EnumProperty(
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

        # Remember all parents and indices
        parent_dict = get_parent_dict(yp)
        index_dict = get_index_dict(yp)

        if layer.type == 'GROUP' and neighbor_layer.type != 'GROUP':

            # Group layer UP to standard layer
            if self.direction == 'UP':
                #print('Case A')

                # Swap layer
                yp.layers.move(neighbor_idx, last_member_idx)
                yp.active_layer_index = neighbor_idx

            # Group layer DOWN to standard layer
            elif self.direction == 'DOWN':
                #print('Case B')

                # Swap layer
                yp.layers.move(neighbor_idx, layer_idx)
                yp.active_layer_index = layer_idx+1

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

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        # Height calculation can be changed after moving layer
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch: update_displacement_height_ratio(height_root_ch)

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

    direction : EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    move_out : BoolProperty(default=False)

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
    mat = obj.active_material

    # Dealing with image atlas segments
    if layer.type == 'IMAGE': # and layer.segment_name != '':
        src = get_layer_source(layer)
        if src:
            if src.image.yia.is_image_atlas and layer.segment_name != '':
                segment = src.image.yia.segments.get(layer.segment_name)
                entities = ImageAtlas.get_entities_with_specific_segment(yp, segment)
                if len(entities) == 1:
                    segment.unused = True
            elif src.image.yua.is_udim_atlas and layer.segment_name != '':
                UDIM.remove_udim_atlas_segment_by_name(src.image, layer.segment_name, yp=yp)

    # Remove the source first to remove image
    source_tree = get_source_tree(layer) #, layer_tree)
    remove_node(source_tree, layer, 'source')

    # Remove Mask source
    for mask in layer.masks:

        # Dealing with image atlas segments
        if mask.type == 'IMAGE': # and mask.segment_name != '':
            src = get_mask_source(mask)
            if not src: continue
            if src.image.yia.is_image_atlas and mask.segment_name != '':
                segment = src.image.yia.segments.get(mask.segment_name)
                entities = ImageAtlas.get_entities_with_specific_segment(yp, segment)
                if len(entities) == 1:
                    segment.unused = True
            elif src.image.yua.is_udim_atlas and mask.segment_name != '':
                UDIM.remove_udim_atlas_segment_by_name(src.image, mask.segment_name, yp=yp)

        mask_tree = get_mask_tree(mask)
        remove_node(mask_tree, mask, 'source')

    # Remove node group and layer tree
    if layer_tree: bpy.data.node_groups.remove(layer_tree)
    if layer.trash_group_node != '':
        trash = group_tree.nodes.get(yp.trash)
        if trash: trash.node_tree.nodes.remove(trash.node_tree.nodes.get(layer.trash_group_node))
    else:
        layer_node = group_tree.nodes.get(layer.group_node)
        if layer_node: group_tree.nodes.remove(layer_node)

    # Remove node group from parallax tree
    parallax = group_tree.nodes.get(PARALLAX)
    if parallax:
        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
        depth_source_0.node_tree.nodes.remove(depth_source_0.node_tree.nodes.get(layer.depth_group_node))

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

    remove_childs : BoolProperty(name='Remove Childs', description='Remove layer childrens', default=False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def invoke(self, context, event):
        # Removing UDIM atlas segment is can't be undoed
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = yp.layers[yp.active_layer_index]
        self.using_udim_atlas = False
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image and source.image.yua.is_udim_atlas:
                self.using_udim_atlas = True
                return context.window_manager.invoke_props_dialog(self, width=300)
            for mask in layer.masks:
                if mask.type != 'IMAGE': continue
                source = get_mask_source(mask)
                if source and source.image and source.image.yua.is_udim_atlas:
                    self.using_udim_atlas = True
                    return context.window_manager.invoke_props_dialog(self, width=300)

        obj = context.object
        if obj.mode != 'OBJECT':
            return context.window_manager.invoke_props_dialog(self, width=400)
        return self.execute(context)

    def draw(self, context):
        obj = context.object
        if obj.mode != 'OBJECT':
            self.layout.label(text='You cannot UNDO this operation under this mode, are you sure?', icon='ERROR')
        elif self.using_udim_atlas:
            col = self.layout.column(align=True)
            col.label(text='This layer is using UDIM atlas image segment', icon='ERROR')
            col.label(text='You cannot UNDO after removal', icon='BLANK1')
            col.label(text='Are you sure want to continue?', icon='BLANK1')

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
        index_dict = get_index_dict(yp)

        need_reconnect_layers = False

        # Remove layer fcurves first
        remove_entity_fcurves(layer)

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
        uv_layers = get_uv_layers(obj)
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

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        # Check uv maps
        check_uv_nodes(yp)

        # Check childrens
        #if need_reconnect_layers:
        for i in child_ids:
            lay = yp.layers[i-1]
            check_all_layer_channel_io_and_nodes(lay)
            rearrange_layer_nodes(lay)
            reconnect_layer_nodes(lay)

        # Update max height
        height_ch = get_root_height_channel(yp)
        if height_ch: update_displacement_height_ratio(height_ch)

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

def replace_layer_type(layer, new_type, item_name='', remove_data=False):

    yp = layer.id_data.yp

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

    # Save hemi vector
    if layer.type == 'HEMI':
        src = get_layer_source(layer)
        save_hemi_props(layer, src)

    yp.halt_reconnect = True

    # Standard bump map is easier to convert
    #fine_bump_channels = [ch for ch in layer.channels if ch.normal_map_type == 'FINE_BUMP_MAP']
    #for ch in fine_bump_channels:
    #    ch.normal_map_type = 'BUMP_MAP'
    fine_bump_channels = [ch for ch in yp.channels if ch.enable_smooth_bump]
    for ch in fine_bump_channels:
        ch.enable_smooth_bump = False

    # Disable transition will also helps
    transition_channels = [ch for ch in layer.channels if ch.enable_transition_bump]
    for ch in transition_channels:
        ch.enable_transition_bump = False

    # Current source
    tree = get_tree(layer)
    source_tree = get_source_tree(layer)
    source = source_tree.nodes.get(layer.source)

    # Save source to cache if it's not image, vertex color, or background
    if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP', 'HEMI'}:
        setattr(layer, 'cache_' + layer.type.lower(), source.name)
        # Remove uv input link
        if any(source.inputs) and any(source.inputs[0].links):
            tree.links.remove(source.inputs[0].links[0])
        source.label = ''
    else:
        remove_node(source_tree, layer, 'source', remove_data=remove_data)

    # Try to get available cache
    cache = None
    if new_type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP', 'HEMI'}:
        cache = tree.nodes.get(getattr(layer, 'cache_' + new_type.lower()))

    if cache:
        layer.source = cache.name
        setattr(layer, 'cache_' + new_type.lower(), '')
        cache.label = 'Source'
    else:
        source = new_node(source_tree, layer, 'source', layer_node_bl_idnames[new_type], 'Source')

        if new_type == 'IMAGE':
            image = bpy.data.images.get(item_name)
            source.image = image
            if hasattr(source, 'color_space'):
                source.color_space = 'NONE'
            #if image.colorspace_settings.name != 'Non-Color':
            #    image.colorspace_settings.name = 'Non-Color'
        elif new_type == 'VCOL':
            set_source_vcol_name(source, item_name)
        elif new_type == 'HEMI':
            source.node_tree = get_node_tree_lib(lib.HEMI)
            duplicate_lib_node_tree(source)

            load_hemi_props(layer, source)

    # Change layer type
    ori_type = layer.type
    layer.type = new_type

    # Check modifiers tree
    Modifier.check_modifiers_trees(layer)

    # Update group ios
    check_all_layer_channel_io_and_nodes(layer, tree)
    if layer.type == 'BACKGROUND':
        # Remove bump and its base
        for ch in layer.channels:
            #remove_node(tree, ch, 'bump_base')
            #remove_node(tree, ch, 'bump')
            remove_node(tree, ch, 'normal_process')

    # Update linear stuff
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        check_layer_channel_linear_node(ch, layer, root_ch)

    # Back to use fine bump if conversion happen
    for ch in fine_bump_channels:
        #ch.normal_map_type = 'FINE_BUMP_MAP'
        ch.enable_smooth_bump = True

    # Bring back transition
    for ch in transition_channels:
        ch.enable_transition_bump = True

    # Update uv neighbor
    set_uv_neighbor_resolution(layer)

    yp.halt_reconnect = False

    # Remap parents
    for lay in yp.layers:
        lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

    # Check uv maps
    check_uv_nodes(yp)

    # Refresh colorspace
    for root_ch in yp.channels:
        if root_ch.type == 'RGB':
            root_ch.colorspace = root_ch.colorspace

    # Check childrens which need rearrange
    for lay in yp.layers:
        check_all_layer_channel_io_and_nodes(lay)
        rearrange_layer_nodes(lay)
        reconnect_layer_nodes(lay)

    if layer.type in {'BACKGROUND', 'GROUP'} or ori_type == 'GROUP':
        rearrange_yp_nodes(layer.id_data)
        reconnect_yp_nodes(layer.id_data)

def replace_mask_type(mask, new_type, item_name='', remove_data=False):

    yp = mask.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', mask.path_from_id())
    layer = yp.layers[int(match.group(1))]

    # Remove segment if original mask using image atlas
    if mask.type == 'IMAGE' and mask.segment_name != '':
        src = get_mask_source(mask)
        segment = src.image.yia.segments.get(mask.segment_name)
        segment.unused = True
        mask.segment_name = ''

    # Save hemi vector
    if mask.type == 'HEMI':
        src = get_mask_source(mask)
        save_hemi_props(mask, src)

    #if new_type = 

    yp.halt_reconnect = True

    # Standard bump map is easier to convert
    #fine_bump_channels = [ch for ch in mask.channels if ch.normal_map_type == 'FINE_BUMP_MAP']
    #for ch in fine_bump_channels:
    #    ch.normal_map_type = 'BUMP_MAP'
    fine_bump_channels = [ch for ch in yp.channels if ch.enable_smooth_bump]
    for ch in fine_bump_channels:
        ch.enable_smooth_bump = False

    # Disable transition will also helps
    transition_channels = [ch for ch in layer.channels if ch.enable_transition_bump]
    for ch in transition_channels:
        ch.enable_transition_bump = False

    # Current source
    tree = get_mask_tree(mask)
    #source_tree = get_source_tree(mask)
    #source = source_tree.nodes.get(mask.source)
    source = get_mask_source(mask)

    # Save source to cache if it's not image, vertex color, or background
    #if mask.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP', 'HEMI'}:
    #    setattr(mask, 'cache_' + mask.type.lower(), source.name)
    #    # Remove uv input link
    #    if any(source.inputs) and any(source.inputs[0].links):
    #        tree.links.remove(source.inputs[0].links[0])
    #    source.label = ''
    #else:
    #    remove_node(source_tree, mask, 'source', remove_data=remove_data)
    remove_node(tree, mask, 'source', remove_data=remove_data)

    # Disable modifier tree
    #if (mask.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'HEMI'} and 
    #        new_type in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'HEMI'}):
    #    Modifier.disable_modifiers_tree(mask)

    # Try to get available cache
    #cache = None
    #if new_type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP', 'HEMI'}:
    #    cache = tree.nodes.get(getattr(mask, 'cache_' + new_type.lower()))

    #if cache:
    #    mask.source = cache.name
    #    setattr(mask, 'cache_' + new_type.lower(), '')
    #    cache.label = 'Source'
    #else:

    #source = new_node(source_tree, mask, 'source', layer_node_bl_idnames[new_type], 'Source')
    source = new_node(tree, mask, 'source', layer_node_bl_idnames[new_type], 'Source')

    if new_type == 'IMAGE':
        image = bpy.data.images.get(item_name)
        source.image = image
        if hasattr(source, 'color_space'):
            source.color_space = 'NONE'
        if image.colorspace_settings.name != 'Non-Color' and not image.is_dirty:
            image.colorspace_settings.name = 'Non-Color'
    elif new_type == 'VCOL':
        set_source_vcol_name(source, item_name)
    elif new_type == 'HEMI':
        source.node_tree = get_node_tree_lib(lib.HEMI)
        duplicate_lib_node_tree(source)

        load_hemi_props(mask, source)

    # Change mask type
    ori_type = mask.type
    mask.type = new_type

    # Enable modifiers tree if generated texture is used
    #if mask.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
    #    Modifier.enable_modifiers_tree(mask)
    Modifier.check_modifiers_trees(mask)

    # Update group ios
    check_all_layer_channel_io_and_nodes(layer, tree)
    #if mask.type == 'BACKGROUND':
    #    # Remove bump and its base
    #    for ch in mask.channels:
    #        #remove_node(tree, ch, 'bump_base')
    #        #remove_node(tree, ch, 'bump')
    #        remove_node(tree, ch, 'normal_process')

    mapping = tree.nodes.get(mask.mapping)
    if new_type == 'IMAGE' :
        if not mapping:
            mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')
    else:
        remove_node(tree, mask, 'mapping')

    # Update linear stuff
    #for i, ch in enumerate(mask.channels):
    #    root_ch = yp.channels[i]
    #    set_layer_channel_linear_node(tree, mask, root_ch, ch)

    # Back to use fine bump if conversion happen
    for ch in fine_bump_channels:
        #ch.normal_map_type = 'FINE_BUMP_MAP'
        ch.enable_smooth_bump = True

    # Bring back transition
    for ch in transition_channels:
        ch.enable_transition_bump = True

    # Update uv neighbor
    #set_uv_neighbor_resolution(mask)

    yp.halt_reconnect = False

    # Check uv maps
    check_uv_nodes(yp)

    # Check childrens which need rearrange
    #for i in child_ids:
        #lay = yp.layers[i]
    #for lay in yp.layers:
    #    check_all_layer_channel_io_and_nodes(lay)
    #    rearrange_layer_nodes(lay)
    #    reconnect_layer_nodes(lay)

    for lay in yp.layers:
        check_all_layer_channel_io_and_nodes(lay)
        rearrange_layer_nodes(lay)
        reconnect_layer_nodes(lay)

    #rearrange_layer_nodes(layer)
    #reconnect_layer_nodes(layer)

    #if mask.type in {'BACKGROUND', 'GROUP'} or ori_type == 'GROUP':
    rearrange_yp_nodes(mask.id_data)
    reconnect_yp_nodes(mask.id_data)

class YReplaceLayerChannelOverride(bpy.types.Operator):
    bl_idname = "node.y_replace_layer_channel_override"
    bl_label = "Replace Layer Channel Override"
    bl_description = "Replace Layer Channel Override"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Layer Type',
            items = channel_override_type_items,
            default = 'IMAGE')

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        #print(context.parent)
        ch = context.parent
        ch.override_type = self.type
        ch.override = True
        return {'FINISHED'}

class YReplaceLayerChannelOverride1(bpy.types.Operator):
    bl_idname = "node.y_replace_layer_channel_override_1"
    bl_label = "Replace Layer Channel Normal Override"
    bl_description = "Replace Layer Channel Normal Override"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Layer Type',
            items = channel_override_1_type_items,
            default = 'IMAGE')

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        #print(context.parent)
        ch = context.parent
        ch.override_1_type = self.type
        ch.override_1 = True
        return {'FINISHED'}

class YReplaceLayerType(bpy.types.Operator):
    bl_idname = "node.y_replace_layer_type"
    bl_label = "Replace Layer Type"
    bl_description = "Replace Layer Type"
    bl_options = {'REGISTER', 'UNDO'}

    type : EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    item_name : StringProperty(name="Item")
    item_coll : CollectionProperty(type=bpy.types.PropertyGroup)

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
                baked_channel_images = get_all_baked_channel_images(self.layer.id_data)
                for img in bpy.data.images:
                    if not img.yia.is_image_atlas and img not in baked_channel_images:
                        self.item_coll.add().name = img.name
            else:
                for vcol in get_vertex_colors(obj):
                    self.item_coll.add().name = vcol.name

            return context.window_manager.invoke_props_dialog(self)#, width=400)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout

        if is_greater_than_280():
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

        if layer.use_temp_bake:
            self.report({'ERROR'}, "Cannot replace temporarily baked layer!")
            return {'CANCELLED'}

        if self.type == layer.type: return {'CANCELLED'}
        #if layer.type == 'GROUP':
        #    self.report({'ERROR'}, "You can't change type of group layer!")
        #    return {'CANCELLED'}

        if self.type in {'VCOL', 'IMAGE'} and self.item_name == '':
            self.report({'ERROR'}, "Form is cannot be empty!")
            return {'CANCELLED'}

        replace_layer_type(self.layer, self.type, self.item_name)

        print('INFO: Layer', layer.name, 'is updated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def duplicate_layer_nodes_and_images(tree, specific_layer=None, make_image_single_user=True, make_image_blank=False):

    yp = tree.yp
    ypup = get_user_preferences()

    img_users = []
    img_nodes = []
    imgs = []

    for layer in yp.layers:
        if specific_layer and layer != specific_layer: continue

        oldtree = get_tree(layer)
        ttree = oldtree.copy()
        node = tree.nodes.get(layer.group_node)
        node.node_tree = ttree

        # Duplicate layer source groups
        if layer.source_group != '':
            source_group = ttree.nodes.get(layer.source_group)
            source_group.node_tree = source_group.node_tree.copy()
            source = source_group.node_tree.nodes.get(layer.source)

            for d in neighbor_directions:
                s = ttree.nodes.get(getattr(layer, 'source_' + d))
                if s: s.node_tree = source_group.node_tree

            # Duplicate layer modifier groups
            mod_group = source_group.node_tree.nodes.get(layer.mod_group)
            if mod_group:
                mod_group.node_tree = mod_group.node_tree.copy()

                mod_group_1 = source_group.node_tree.nodes.get(layer.mod_group_1)
                if mod_group_1: mod_group_1.node_tree = mod_group.node_tree

        else:
            source = ttree.nodes.get(layer.source)

            # Duplicate layer modifier groups
            mod_group = ttree.nodes.get(layer.mod_group)
            if mod_group:
                mod_group.node_tree = mod_group.node_tree.copy()

                mod_group_1 = ttree.nodes.get(layer.mod_group_1)
                if mod_group_1: mod_group_1.node_tree = mod_group.node_tree

        if layer.type == 'IMAGE': # and ypui.make_image_single_user:
            img = source.image
            if img:
                #mapping = get_layer_mapping(layer)
                #img_mappings.append(mapping)
                img_users.append(layer)
                img_nodes.append(source)
                imgs.append(img)
                #source.image = img.copy()
        elif layer.type == 'HEMI':
            duplicate_lib_node_tree(source)

        # Duplicate override channel
        for ch in layer.channels:
            if ch.override and ch.override_type == 'IMAGE':
                #ch_source = ttree.nodes.get(ch.source)
                ch_source = get_channel_source(ch, layer)
                img = ch_source.image
                if img:
                    img_users.append(ch)
                    img_nodes.append(ch_source)
                    imgs.append(img)

        # Duplicate masks
        for mask in layer.masks:
            if mask.group_node != '':
                mask_group =  ttree.nodes.get(mask.group_node)
                mask_group.node_tree = mask_group.node_tree.copy()
                mask_source = mask_group.node_tree.nodes.get(mask.source)

                for d in neighbor_directions:
                    s = ttree.nodes.get(getattr(mask, 'source_' + d))
                    if s: s.node_tree = mask_group.node_tree
            else:
                mask_source = ttree.nodes.get(mask.source)

            if mask.type == 'IMAGE': # and ypui.make_image_single_user:
                img = mask_source.image
                if img:
                    #mapping = get_mask_mapping(mask)
                    #img_mappings.append(mapping)
                    img_users.append(mask)
                    img_nodes.append(mask_source)
                    imgs.append(img)
                    #mask_source.image = img.copy()
            elif mask.type == 'HEMI':
                duplicate_lib_node_tree(mask_source)

        # Duplicate some channel nodes
        for i, ch in enumerate(layer.channels):

            # Modifier group
            mod_group = ttree.nodes.get(ch.mod_group)
            if mod_group:
                mod_group.node_tree = mod_group.node_tree.copy()

                for d in neighbor_directions:
                    m = ttree.nodes.get(getattr(ch, 'mod_' + d))
                    if m: m.node_tree = mod_group.node_tree

            # Transition Ramp
            tr_ramp = ttree.nodes.get(ch.tr_ramp)
            if tr_ramp and '_Copy' in tr_ramp.node_tree.name: 
                tr_ramp.node_tree = tr_ramp.node_tree.copy()

            # Transition Ramp Blend
            tr_ramp_blend = ttree.nodes.get(ch.tr_ramp_blend)
            if tr_ramp_blend and '_Copy' in tr_ramp_blend.node_tree.name: 
                tr_ramp_blend.node_tree = tr_ramp_blend.node_tree.copy()

            # Transition AO
            tao = ttree.nodes.get(ch.tao)
            if tao and '_Copy' in tao.node_tree.name: 
                tao.node_tree = tao.node_tree.copy()

            # Transition Bump Falloff
            tb_falloff = ttree.nodes.get(ch.tb_falloff)
            if tb_falloff and '_Copy' in tb_falloff.node_tree.name: 
                tb_falloff.node_tree = tb_falloff.node_tree.copy()

                ori = tb_falloff.node_tree.nodes.get('_original')
                if ori and '_Copy' in ori.node_tree.name: 
                    ori.node_tree = ori.node_tree.copy()

                    for n in tb_falloff.node_tree.nodes:
                        if n.type == 'GROUP' and n != ori:
                            n.node_tree = ori.node_tree

    # Make all images single user
    if make_image_single_user:

        already_copied_ids = []
        copied_image_atlas = {}

        # Copy image on layer and masks
        for i, img in enumerate(imgs):

            if img.yia.is_image_atlas:
                segment = img.yia.segments.get(img_users[i].segment_name)
                new_segment = None

                # create new segment based on previous one
                if make_image_blank:
                    new_segment = ImageAtlas.get_set_image_atlas_segment(segment.width, segment.height,
                            img.yia.color, img.is_float, yp=yp)

                # If using different image atlas per yp, just copy the image (unless specific layer is on)
                elif ypup.unique_image_atlas_per_yp and not specific_layer:
                    if img.name not in copied_image_atlas:
                        copied_image_atlas[img.name] = duplicate_image(img)
                    img_nodes[i].image = copied_image_atlas[img.name]

                else:
                    new_segment = ImageAtlas.get_set_image_atlas_segment(segment.width, segment.height,
                            img.yia.color, img.is_float, img, segment)

                if new_segment:

                    img_users[i].segment_name = new_segment.name

                    # Change image if different image is returned
                    if new_segment.id_data != img:
                        img_nodes[i].image = new_segment.id_data

                    # Update layer transform
                    update_mapping(img_users[i])

            elif img.yua.is_udim_atlas:
                segment = img.yua.segments.get(img_users[i].segment_name)
                new_segment = None

                tilenums = UDIM.get_udim_segment_base_tilenums(segment)
                segment_tilenums = UDIM.get_udim_segment_tilenums(segment)

                # create new segment based on previous one
                if make_image_blank:
                    new_segment = UDIM.get_set_udim_atlas_segment(tilenums, color=img.yui.base_color, 
                            colorspace=img.colorspace_settings.name, hdr=img.is_float, yp=yp) #, source_image=img)

                # If using different image atlas per yp, just copy the image (unless specific layer is on)
                elif not specific_layer:
                    if img.name not in copied_image_atlas:
                        copied_image_atlas[img.name] = duplicate_image(img)
                    img_nodes[i].image = copied_image_atlas[img.name]

                else:
                    new_segment = UDIM.get_set_udim_atlas_segment(tilenums, color=img.yui.base_color, 
                            colorspace=img.colorspace_settings.name, hdr=img.is_float, yp=yp, 
                            source_image=img, source_tilenums=segment_tilenums)

                if new_segment:

                    img_users[i].segment_name = new_segment.name

                    # Change image if different image is returned
                    if new_segment.id_data != img:
                        img_nodes[i].image = new_segment.id_data

                    # Update layer transform
                    update_mapping(img_users[i])

            elif i not in already_copied_ids:
                # Copy image if not atlas
                if make_image_blank:

                    if hasattr(img, 'use_alpha'):
                        alpha = img.use_alpha
                    else: alpha = True

                    # Mask will have alpha filled
                    m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', img_users[i].path_from_id())
                    if m: 
                        mask_idx = int(m.group(2))

                        # Only first mask will be black by default, others will be white
                        if mask_idx == 0:
                            color = (0,0,0,1)
                        else: color = (1,1,1,1)
                    else: color = (0,0,0,0)

                    img_name = get_unique_name(img.name, bpy.data.images)

                    if img.source == 'TILED':
                        img_nodes[i].image = img.copy()
                        img_nodes[i].image.name = img_name
                        UDIM.fill_tiles(img_nodes[i].image, color)
                        UDIM.initial_pack_udim(img_nodes[i].image, color)
                    else:
                        img_nodes[i].image = bpy.data.images.new(img_name,
                                width=img.size[0], height=img.size[1], alpha=alpha, float_buffer=img.is_float)
                        img_nodes[i].image.generated_color = color

                    img_nodes[i].image.colorspace_settings.name = img.colorspace_settings.name

                else:
                    img_nodes[i].image = duplicate_image(img)

                # Check other nodes using the same image
                for j, imgg in enumerate(imgs):
                    if j != i and imgg == img:
                        img_nodes[j].image = img_nodes[i].image
                        already_copied_ids.append(j)

class YDuplicateLayer(bpy.types.Operator):
    bl_idname = "node.y_duplicate_layer"
    bl_label = "Duplicate layer"
    bl_description = "Duplicate Layer"
    bl_options = {'REGISTER', 'UNDO'}

    make_image_blank : BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        # Get parent and index dict
        parent_dict = get_parent_dict(yp)
        index_dict = get_index_dict(yp)

        # Get active layer
        layer_idx = yp.active_layer_index
        layer = yp.layers[layer_idx]

        # Get all childrens
        childs, child_ids = get_list_of_all_childs_and_child_ids(layer)

        # Collect relevant ids to duplicate
        relevant_layer_names = [layer.name]
        relevant_ids = [layer_idx]
        for child in childs:
            relevant_layer_names.append(child.name)
        relevant_ids.extend(child_ids)

        # Halt update to prevent needless reconnection
        yp.halt_update = True

        # List of newly created ids
        created_ids = []

        # Duplicate all relevant layers
        for i, lname in enumerate(relevant_layer_names):
            #idx = relevant_ids[i]

            # Create new layer
            new_layer = yp.layers.add()
            new_layer.name = get_unique_name(lname, yp.layers)

            # Get original layer
            l = yp.layers.get(lname)
            group_node = tree.nodes.get(l.group_node)

            # Copy layer props
            copy_id_props(l, new_layer, ['name'])

            # Duplicate groups
            new_group_node = new_node(tree, new_layer, 'group_node', 'ShaderNodeGroup', group_node.label)
            new_group_node.node_tree = group_node.node_tree

            # Duplicate images and some nodes inside
            duplicate_layer_nodes_and_images(tree, new_layer, True, self.make_image_blank)

            # Rename masks
            for mask in new_layer.masks:
                if mask.type in {'VCOL'}: continue
                m = re.match(r'^Mask\s.*\((.+)\)$', mask.name)
                if m:
                    old_layer_name = m.group(1)
                    if old_layer_name == lname:
                        mask.name = mask.name.replace(old_layer_name, new_layer.name)

            #yp.layers.move(len(yp.layers)-1, idx)
            created_ids.append(len(yp.layers)-1)

        # Move duplicated layer to current index
        for i, idx in enumerate(created_ids):
            relevant_id = relevant_ids[i]
            yp.layers.move(idx, relevant_id)

        # Remap parent index
        for lay in yp.layers:
            if lay.name in parent_dict:
                lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])
            #print(lay.name, yp.layers[lay.parent_idx].name)

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        # Revert back halt update
        yp.halt_update = False

        # Rearrange and reconnect
        rearrange_yp_nodes(tree)
        reconnect_yp_nodes(tree)

        # Refresh active layer
        yp.active_layer_index = yp.active_layer_index

        print('INFO: Layer', layer.name, 'is duplicated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YCopyLayer(bpy.types.Operator):
    bl_idname = "node.y_copy_layer"
    bl_label = "Copy Layer"
    bl_description = "Copy Layer"
    bl_options = {'REGISTER', 'UNDO'}

    all_layers : BoolProperty(
            name='Copy All Layers',
            description='Copy all layers instead of only the active one',
            default = False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        wmp = context.window_manager.ypprops

        layer = yp.layers[yp.active_layer_index]

        wmp.clipboard_tree = node.node_tree.name
        wmp.clipboard_layer = layer.name if not self.all_layers else ''

        return {'FINISHED'}

class YPasteLayer(bpy.types.Operator):
    bl_idname = "node.y_paste_layer"
    bl_label = "Paste Layer"
    bl_description = "Paste Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        wmp = wm.ypprops

        #print(wmp.clipboard_tree, wmp.clipboard_layer)

        tree_source = bpy.data.node_groups.get(wmp.clipboard_tree)
        if not tree_source:
            self.report({'ERROR'}, "Cannot paste as clipboard source isn't found!")
            return {'CANCELLED'}

        yp_source = tree_source.yp

        if not tree_source:
            self.report({'ERROR'}, "Cannot paste as clipboard source isn't found!")
            return {'CANCELLED'}

        # Check if the source yp has matching channel order
        matching = True
        if len(yp.channels) != len(yp_source.channels):
            matching = False
        else:
            for i, ch in enumerate(yp.channels):
                ch_source = yp_source.channels[i]
                if ch.name != ch_source.name or ch.type != ch_source.type:
                    matching = False
                    break

        if not matching:
            self.report({'ERROR'}, "Copied tree has different channel names or orders!")
            return {'CANCELLED'}
        
        if wmp.clipboard_layer == '':

            if len(yp_source.layers) == 0:
                self.report({'ERROR'}, "Copied tree has no layers!")
                return {'CANCELLED'}

            # Get datas
            first_copied_index = 0
            relevant_layer_names = [l.name for l in yp_source.layers]

        else:

            # Source layer
            layer_source = yp_source.layers.get(wmp.clipboard_layer)

            if not layer_source:
                self.report({'ERROR'}, "Cannot find copied layer! Maybe it was deleted or renamed.")
                return {'CANCELLED'}

            # Check index of copied layer to know the offest
            first_copied_index = get_layer_index_by_name(yp_source, layer_source.name)

            # Get all childrens
            childs, child_ids = get_list_of_all_childs_and_child_ids(layer_source)

            # Collect relevant names
            relevant_layer_names = [layer_source.name]
            for child in childs:
                relevant_layer_names.append(child.name)

        # Get parent and index dict
        parent_dict = get_parent_dict(yp)
        index_dict = get_index_dict(yp)

        # Current index
        cur_idx = yp.active_layer_index
        if len(yp.layers) > 0:
            cur_layer = yp.layers[cur_idx]
            cur_parent_idx = cur_layer.parent_idx
        else:
            cur_parent_idx = -1

        # List of newly pasted datas
        pasted_layer_names = []

        # Halt update to prevent needless reconnection
        yp.halt_update = True

        for lname in relevant_layer_names:

            ls = yp_source.layers.get(lname)

            # Create new layer
            new_layer = yp.layers.add()
            new_layer.name = get_unique_name(ls.name, yp.layers)

            copy_id_props(ls, new_layer, ['name'])

            # Duplicate groups
            new_group_node = new_node(tree, new_layer, 'group_node', 'ShaderNodeGroup', new_layer.name)
            new_group_node.node_tree = get_tree(ls)

            # Duplicate images and some nodes inside
            duplicate_layer_nodes_and_images(tree, new_layer, True, False) #self.make_image_blank)

            pasted_layer_names.append(new_layer.name)

        # Move pasted layer to current index
        for i, lname in enumerate(pasted_layer_names):
            nl = yp.layers.get(lname)
            idx = get_layer_index_by_name(yp, lname)
            yp.layers.move(idx, cur_idx+i)

        for i, lname in enumerate(pasted_layer_names):
            nl = yp.layers.get(lname)

            # Remap parent index
            if i == 0:
                # Set upmost pasted layer to current parent index
                nl.parent_idx = cur_parent_idx
            else:
                if nl.parent_idx != -1:
                    nl.parent_idx += cur_idx - first_copied_index
                else:
                    nl.parent_idx = cur_parent_idx

            # Refresh io and nodes
            check_all_layer_channel_io_and_nodes(nl)

            rearrange_layer_nodes(nl)
            reconnect_layer_nodes(nl)

        # Remap parents for non pasted layers
        for lay in yp.layers:
            if lay.name in pasted_layer_names: continue
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        # Check uv maps
        check_uv_nodes(yp)

        # Revert back halt update
        yp.halt_update = False

        # Rearrange and reconnect
        rearrange_yp_nodes(tree)
        reconnect_yp_nodes(tree)

        # Refresh active layer
        yp.active_layer_index = yp.active_layer_index

        print('INFO: Layer(s) are pasted at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

def update_layer_channel_override_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    ch_index = int(m.group(2))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[ch_index]
    ch = self

    update_override_value(root_ch, layer, ch)

def update_layer_channel_override_1_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    ch_index = int(m.group(2))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[ch_index]
    ch = self

    update_override_1_value(root_ch, layer, ch)

def update_layer_channel_override_1(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    ch_index = int(m.group(2))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[ch_index]
    ch = self

    check_override_1_layer_channel_nodes(root_ch, layer, ch)

    # Disable active edit if override is off
    if not ch.override_1:
        ch.halt_update = True
        ch.active_edit_1 = False
        ch.halt_update = False

    check_all_layer_channel_io_and_nodes(layer) #, has_parent=has_parent)
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def update_layer_channel_override(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    ch_index = int(m.group(2))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[ch_index]
    ch = self

    check_override_layer_channel_nodes(root_ch, layer, ch)

    # Disable active edit if override is off
    if not ch.override:
        ch.halt_update = True
        ch.active_edit = False
        ch.halt_update = False

    check_all_layer_channel_io_and_nodes(layer) #, has_parent=has_parent)
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    # Reselect layer so vcol or image will be updated
    yp.active_layer_index = yp.active_layer_index

def update_channel_enable(self, context):
    T = time.time()
    yp = self.id_data.yp
    if yp.halt_update: return
    wm = context.window_manager

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    ch_index = int(m.group(2))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[ch_index]
    ch = self

    tree = get_tree(layer)

    # Check uv maps
    check_uv_nodes(yp)

    #if yp.disable_quick_toggle:
    check_all_layer_channel_io_and_nodes(layer, tree, ch)

    if yp.halt_reconnect: return

    if yp.layer_preview_mode:
        # Refresh preview mode, rearrange and reconnect already done in this event
        yp.layer_preview_mode = yp.layer_preview_mode
    else:

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        rearrange_yp_nodes(self.id_data)
        reconnect_yp_nodes(self.id_data)

    # Disable active edit on overrides
    if not ch.enable:
        ch.active_edit = False
        ch.active_edit_1 = False

    print('INFO: Channel', root_ch.name, ' of ' + layer.name + ' is changed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    wm.yptimer.time = str(time.time())

def update_normal_map_type(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    check_channel_normal_map_nodes(tree, layer, root_ch, self)

    #if not yp.halt_reconnect:
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def update_blend_type(self, context):
    T = time.time()

    wm = context.window_manager
    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = yp.channels[ch_index]

    if check_blend_type_nodes(root_ch, layer, self): # and not yp.halt_reconnect:

        rearrange_layer_nodes(layer)

        # Reconnect all layer channels if normal channel is updated
        if root_ch.type == 'NORMAL':
            reconnect_layer_nodes(layer) 
        else: reconnect_layer_nodes(layer, ch_index)

    print('INFO: Layer', layer.name, ' blend type is changed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    wm.yptimer.time = str(time.time())

def update_flip_backface_normal(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)

    normal_flip = tree.nodes.get(self.normal_flip)
    normal_flip.mute = self.invert_backface_normal

def update_write_height(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = yp.channels[ch_index]
    ch = self
    tree = get_tree(layer)

    check_channel_normal_map_nodes(tree, layer, root_ch, ch)

    #max_height = get_displacement_max_height(root_ch)
    #root_ch.displacement_height_ratio = max_height
    update_displacement_height_ratio(root_ch)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer) #, ch_index)

def update_normal_strength(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    ch_index = int(m.group(2))
    root_ch = yp.channels[ch_index]
    ch = self
    tree = get_tree(layer)

    normal_proc = tree.nodes.get(ch.normal_proc)
    if 'Strength' in normal_proc.inputs:
        normal_proc.inputs['Strength'].default_value = ch.normal_strength

def update_bump_distance(self, context):
    group_tree = self.id_data
    yp = group_tree.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    if self.normal_map_type == 'NORMAL_MAP' and self.enable_transition_bump: return

    update_displacement_height_ratio(root_ch)

def update_bump_smooth_multiplier(self, context):
    group_tree = self.id_data
    yp = group_tree.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    if self.override and self.override_type != 'DEFAULT':
        set_uv_neighbor_resolution(self)
    else: set_uv_neighbor_resolution(layer)

def update_layer_input(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    #m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    #layer = yp.layers[int(m.group(1))]
    #root_ch = yp.channels[int(m.group(2))]
    #tree = get_tree(layer)
    #ch = self

    check_layer_channel_linear_node(self, reconnect=True)

def update_uv_name(self, context):
    obj = context.object
    mat = obj.active_material
    group_tree = self.id_data
    yp = group_tree.yp
    if yp.halt_update: return

    ypui = context.window_manager.ypui
    layer = self
    active_layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)
    if not tree: return

    nodes = tree.nodes

    # Use first uv if temp uv or empty is selected
    if layer.uv_name in {TEMP_UV, ''}:
        if len(yp.uvs) > 0:
            for uv in yp.uvs:
                layer.uv_name = uv.name
                break

    # Update uv layer
    if obj.type == 'MESH' and not any([m for m in layer.masks if m.active_edit]) and layer == active_layer:

        if layer.segment_name != '':
            refresh_temp_uv(obj, layer)
        else:
            uv_layers = get_uv_layers(obj)
            uv_layers.active = uv_layers.get(layer.uv_name)

        # Check for other objects with same material
        check_uvmap_on_other_objects_with_same_mat(mat, layer.uv_name)

    # Update global uv
    check_uv_nodes(yp)

    # Update uv neighbor
    smooth_bump_ch = get_smooth_bump_channel(layer)
    if smooth_bump_ch and smooth_bump_ch.enable:
        uv_neighbor = replace_new_node(tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), 
                return_status=False, hard_replace=True)
        set_uv_neighbor_resolution(layer, uv_neighbor)
        if smooth_bump_ch.override and smooth_bump_ch.override_type != 'DEFAULT':
            uv_neighbor = replace_new_node(tree, smooth_bump_ch, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                    lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), 
                    return_status=False, hard_replace=True)
            set_uv_neighbor_resolution(smooth_bump_ch, uv_neighbor)

    # Update neighbor uv if mask bump is active
    for i, mask in enumerate(layer.masks):
        set_mask_uv_neighbor(tree, layer, mask, i)

    # Update layer tree inputs
    check_layer_tree_ios(layer, tree)

    #if yp_dirty or layer_dirty: #and not yp.halt_reconnect:
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    # Update layer tree inputs
    #if yp_dirty:
    rearrange_yp_nodes(group_tree)
    reconnect_yp_nodes(group_tree)

def update_texcoord_type(self, context):
    yp = self.id_data.yp
    layer = self
    tree = get_tree(layer)

    if yp.halt_update: return

    # Update global uv
    check_uv_nodes(yp)

    # Update uv neighbor
    smooth_bump_ch = get_smooth_bump_channel(layer)
    if smooth_bump_ch and smooth_bump_ch.enable:
        uv_neighbor = replace_new_node(tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), hard_replace=True)
        set_uv_neighbor_resolution(layer, uv_neighbor)
        if smooth_bump_ch.override and smooth_bump_ch.override_type != 'DEFAULT':
            uv_neighbor = replace_new_node(tree, smooth_bump_ch, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                    lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), hard_replace=True)
            set_uv_neighbor_resolution(smooth_bump_ch, uv_neighbor)
    #else:
    #    remove_node(tree, layer, 'uv_neighbor')

    # Update layer tree inputs
    #yp_dirty = True if check_layer_tree_ios(layer, tree) else False
    check_layer_tree_ios(layer, tree)

    #if not yp.halt_reconnect:
    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    # Update layer tree inputs
    #if yp_dirty:
    rearrange_yp_nodes(self.id_data)
    reconnect_yp_nodes(self.id_data)

def update_hemi_space(self, context):
    if self.type != 'HEMI': return

    source = get_layer_source(self)
    #if source and source.node_tree:
    trans = source.node_tree.nodes.get('Vector Transform')
    if trans: trans.convert_from = self.hemi_space

def update_hemi_camera_ray_mask(self, context):
    yp = self.id_data.yp

    tree = get_source_tree(self)
    source = get_layer_source(self)

    if source:

        # Check if source has the inputs, if not reload the node
        if 'Camera Ray Mask' not in source.inputs:
            source = replace_new_node(tree, self, 'source', 'ShaderNodeGroup', 'Source', 
                    lib.HEMI, force_replace=True)
            duplicate_lib_node_tree(source)
            trans = source.node_tree.nodes.get('Vector Transform')
            if trans: trans.convert_from = self.hemi_space

            rearrange_layer_nodes(self)
            reconnect_layer_nodes(self)

        source.inputs['Camera Ray Mask'].default_value = 1.0 if self.hemi_camera_ray_mask else 0.0

def update_hemi_use_prev_normal(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    layer = self
    tree = get_tree(layer)

    check_layer_tree_ios(layer, tree)
    check_layer_bump_process(layer, tree)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    reconnect_yp_nodes(layer.id_data)

def update_channel_intensity_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

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

    height_proc = tree.nodes.get(ch.height_proc)
    if height_proc:
        height_proc.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    normal_proc = tree.nodes.get(ch.normal_proc)
    if normal_proc and 'Intensity' in normal_proc.inputs:
        normal_proc.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    if ch.enable_transition_ramp:
        transition.set_ramp_intensity_value(tree, layer, ch)

    if ch.enable_transition_ao:
        tao = tree.nodes.get(ch.tao)
        if tao: tao.inputs['Intensity'].default_value = 0.0 if mute else transition.get_transition_ao_intensity(ch)

    if ch.enable_transition_bump and ch.transition_bump_crease:
        tb_crease_intensity = tree.nodes.get(ch.tb_crease_intensity)
        if tb_crease_intensity:
            tb_crease_intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

    if root_ch.type == 'NORMAL':
        #transition.check_transition_bump_nodes(layer, tree, ch)
        update_displacement_height_ratio(root_ch)

def group_trash_update(yp):
    tree = yp.id_data

    # Get trash node
    trash = tree.nodes.get(yp.trash)
    if not trash:
        trash = new_node(tree, yp, 'trash', 'ShaderNodeGroup', 'Trash')
        trash.node_tree = bpy.data.node_groups.new(tree.name + ' Trash', 'ShaderNodeTree')

    ttree = trash.node_tree

    for layer in yp.layers:

        is_hidden = not layer.enable or is_parent_hidden(layer)

        #if layer.enable and layer.trash_group_node != '':
        if not is_hidden and layer.trash_group_node != '':
            tnode = ttree.nodes.get(layer.trash_group_node)

            # Move node back to tree if found
            if tnode:
                node = tree.nodes.new('ShaderNodeGroup')
                node.node_tree = tnode.node_tree
                layer.group_node = node.name

                ttree.nodes.remove(tnode)
                layer.trash_group_node = ''

        #if not layer.enable and layer.trash_group_node == '':
        if is_hidden and layer.trash_group_node == '':

            node = tree.nodes.get(layer.group_node)

            # Move node to trash if found
            if node:
                tnode = ttree.nodes.new('ShaderNodeGroup')
                tnode.node_tree = node.node_tree
                layer.trash_group_node = tnode.name

                tree.nodes.remove(node)

def update_layer_enable(self, context):
    T = time.time()
    yp = self.id_data.yp
    if yp.halt_update: return
    layer = self
    tree = get_tree(layer)

    #group_trash_update(yp)

    height_root_ch = get_root_height_channel(yp)
    if height_root_ch:
        update_displacement_height_ratio(height_root_ch)

    if yp.layer_preview_mode:
        # Refresh preview mode, rearrange and reconnect already done in this event
        yp.layer_preview_mode = yp.layer_preview_mode
    else:
        #if yp.disable_quick_toggle:
        rearrange_yp_nodes(layer.id_data)
        reconnect_yp_nodes(layer.id_data)

    context.window_manager.yptimer.time = str(time.time())

    print('INFO: Layer', layer.name, 'is updated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_layer_name(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    if self.type == 'IMAGE' and self.segment_name != '': return

    src = get_layer_source(self)
    change_layer_name(yp, context.object, src, self, yp.layers)

def update_layer_channel_override_vcol_name(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    obj = context.object
    mat = obj.active_material

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    source = tree.nodes.get(self.source)
    change_vcol_name(yp, obj, source, self.override_vcol_name)

def update_layer_channel_use_clamp(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    tree = get_tree(layer)

    if root_ch.type == 'NORMAL': return

    check_blend_type_nodes(root_ch, layer, self)

def update_divide_rgb_by_alpha(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    check_layer_divider_alpha(self)

    rearrange_layer_nodes(self)
    reconnect_layer_nodes(self)

def update_image_flip_y(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m1 = re.match(r'yp\.layers\[(\d+)\]$', self.path_from_id())
    m2 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', self.path_from_id())

    if m1:
        #layer = yp.layers[int(m1.group(1))]
        layer = self
        tree = get_source_tree(self)

    elif m2:
        layer = yp.layers[int(m2.group(1))]
        #ch = layer.channels[int(m2.group(2))]
        tree = get_tree(layer)
    else:
        return

    if self.image_flip_y:
        flip_y = check_new_node(tree, self, 'flip_y', 'ShaderNodeGroup', 'Flip Y')
        flip_y.node_tree = lib.get_node_tree_lib(lib.FLIP_Y)
    else:
        remove_node(tree, self, 'flip_y')

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def update_channel_active_edit(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer_idx = int(m.group(1))
    layer = yp.layers[int(m.group(1))]
    root_ch = yp.channels[int(m.group(2))]
    ch = self
    tree = get_tree(layer)

    # Disable other active edits
    yp.halt_update = True
    if (
        (self.active_edit and self.override and self.override_type != 'DEFAULT') or
        (self.active_edit_1 and self.override_1 and self.override_1_type != 'DEFAULT')
        ):

        for c in layer.channels:
            if c == self: continue
            c.active_edit = False
            c.active_edit_1 = False
            c.prev_active_edit_idx = 0
        for m in layer.masks:
            m.active_edit = False

    else:
        self.active_edit = False

    # Check previous active edit index
    if ch.prev_active_edit_idx == 0 and ch.active_edit_1:
        ch.active_edit = False
        ch.prev_active_edit_idx = 1
    elif ch.prev_active_edit_idx == 1 and ch.active_edit:
        ch.active_edit_1 = False
        ch.prev_active_edit_idx = 0

    yp.halt_update = False

    # Refresh
    yp.active_layer_index = layer_idx

class YLayerChannel(bpy.types.PropertyGroup):
    enable : BoolProperty(default=True, update=update_channel_enable)

    layer_input : EnumProperty(
            name = 'Layer Input',
            #items = (('RGB', 'Color', ''),
            #         ('ALPHA', 'Alpha / Factor', '')),
            #default = 'RGB',
            items = layer_input_items,
            update = update_layer_input)

    gamma_space : BoolProperty(
            name='Gamma Space',
            description='Make sure layer input is in linear space',
            default = False,
            update = update_layer_input)

    use_clamp : BoolProperty(
            name = 'Use Clamp',
            description = 'Clamp result to 0..1 range',
            default = False,
            update=update_layer_channel_use_clamp)

    normal_map_type : EnumProperty(
            name = 'Normal Map Type',
            items = get_normal_map_type_items,
            #default = 'BUMP_MAP',
            update = update_normal_map_type)

    blend_type : EnumProperty(
            name = 'Blend',
            items = blend_type_items,
            default = 'MIX',
            update = update_blend_type)

    normal_blend_type : EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX',
            update = update_blend_type)

    height_blend_type : EnumProperty(
            name = 'Height Blend Type',
            items = normal_blend_items,
            default = 'MIX',
            update = update_blend_type)

    intensity_value : FloatProperty(
            name = 'Channel Intensity Factor', 
            description = 'Channel Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update = update_channel_intensity_value)

    # Modifiers
    modifiers : CollectionProperty(type=Modifier.YPaintModifier)
    modifiers_1 : CollectionProperty(type=NormalMapModifier.YNormalMapModifier)

    # Override source
    override : BoolProperty(default=False, update=update_layer_channel_override)
    #override_tex : BoolProperty(default=False)
    override_type : EnumProperty(items=channel_override_type_items, default='DEFAULT', update=update_layer_channel_override)
    override_color : FloatVectorProperty(subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.5, 0.5, 0.5), update=update_layer_channel_override_value)
    override_value : FloatProperty(min=0.0, max=1.0, default=1.0, update=update_layer_channel_override_value)
    override_vcol_name : StringProperty(name='Vertex Color Name', description='Channel override vertex color name', default='', update=update_layer_channel_override_vcol_name)

    # Extra override needed when bump and normal are used at the same time
    override_1 : BoolProperty(default=False, update=update_layer_channel_override_1)
    override_1_type : EnumProperty(items=channel_override_1_type_items, default='DEFAULT', update=update_layer_channel_override_1)
    override_1_color : FloatVectorProperty(subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.5, 0.5, 1.0), update=update_layer_channel_override_1_value)
    #override_1_value : FloatProperty(min=0.0, max=1.0, default=1.0, update=update_layer_channel_override_1_value)
    #override_1_vcol_name : StringProperty(name='Vertex Color Name', description='Channel override vertex color name', default='', update=update_layer_channel_override_vcol_name)

    # Sources
    source : StringProperty(default='')
    source_n : StringProperty(default='')
    source_s : StringProperty(default='')
    source_e : StringProperty(default='')
    source_w : StringProperty(default='')
    source_group : StringProperty(default='')

    # Other source needed when bump and normal are used at the same time
    source_1 : StringProperty(default='')
    #source_1_n : StringProperty(default='')
    #source_1_s : StringProperty(default='')
    #source_1_e : StringProperty(default='')
    #source_1_w : StringProperty(default='')
    #source_1_group : StringProperty(default='')

    # UV
    uv_neighbor : StringProperty(default='')
    #uv_neighbor_1 : StringProperty(default='')

    invert_backface_normal : BoolProperty(default=False, update=update_flip_backface_normal)

    # Node names
    linear : StringProperty(default='')
    linear_1 : StringProperty(default='')
    blend : StringProperty(default='')
    intensity : StringProperty(default='')
    extra_alpha : StringProperty(default='')

    # Flip y node
    flip_y : StringProperty(default='')

    # Height related
    height_proc : StringProperty(default='')
    height_blend : StringProperty(default='')

    # For pack/unpack height io
    height_group_unpack : StringProperty(default='')
    height_alpha_group_unpack : StringProperty(default='')

    # Normal related
    normal_proc : StringProperty(default='')
    #normal_blend : StringProperty(default='')
    normal_flip : StringProperty(default='')

    bump_distance : FloatProperty(
            name='Bump Height Range', 
            description= 'Bump height range.\n(White equals this value, black equals negative of this value)', 
            default=0.05, min=-1.0, max=1.0, precision=3, # step=1,
            update=update_bump_distance)

    bump_smooth_multiplier : FloatProperty(
        name = 'Smooth Bump Step Multiplier',
        description = 'Multiply the smooth bump step.\n(The default step is based on image resolution or 1000 for generated blender texture)',
        default=1.0, min=0.1, max=10.0, 
        update=update_bump_smooth_multiplier)

    normal_bump_distance : FloatProperty(
            name='Bump Height Range for normal', 
            description= 'Bump height range for normal channel.\n(White equals this value, black equals negative of this value)', 
            default=0.00, min=-1.0, max=1.0, precision=3, # step=1,
            update=update_bump_distance)

    write_height : BoolProperty(
            name = 'Write Height',
            description = 'Write height for this layer channel',
            default = True,
            update=update_write_height)

    normal_write_height : BoolProperty(
            name = 'Write Normal Height',
            description = 'Write height for this normal layer channel',
            default = False,
            update=update_write_height)

    normal_strength : FloatProperty(
        name = 'Normal Strength',
        description = 'Normal strength',
        default=1.0, min=0.0, max=10.0, 
        update=update_normal_strength)

    image_flip_y : BoolProperty(
            name = 'Image Flip Y',
            description = "Image Flip Y (Use this if you're using normal map created for DirectX application) ",
            default = False,
            update=update_image_flip_y)

    # For some occasion, modifiers are stored in a tree
    mod_group : StringProperty(default='')
    mod_n : StringProperty(default='')
    mod_s : StringProperty(default='')
    mod_e : StringProperty(default='')
    mod_w : StringProperty(default='')

    # Spread alpha hack nodes
    spread_alpha : StringProperty(default='')

    # Intensity Stuff
    intensity_multiplier : StringProperty(default='')

    # Transition bump related
    enable_transition_bump : BoolProperty(name='Enable Transition Bump', description='Enable transition bump',
            default=False, update=transition.update_enable_transition_bump)

    show_transition_bump : BoolProperty(name='Toggle Transition Bump',
            description = "Toggle transition Bump (This will affect other channels)", 
            default=False) #, update=transition.update_show_transition_bump)

    transition_bump_value : FloatProperty(
        name = 'Transition Bump Value',
        description = 'Transition bump value',
        default=3.0, min=1.0, max=100.0, 
        update=transition.update_transition_bump_value)

    transition_bump_second_edge_value : FloatProperty(
            name = 'Second Edge Intensity', 
            description = 'Second Edge intensity value',
            default=1.2, min=1.0, max=100.0, 
            update=transition.update_transition_bump_value)

    transition_bump_distance : FloatProperty(
            #name='Transition Bump Distance', 
            #description= 'Distance of mask bump', 
            name='Transition Bump Height Range', 
            description= 'Transition bump height range.\n(White equals this value, black equals negative of this value)', 
            default=0.05, min=0.0, max=1.0, precision=3, # step=1,
            update=transition.update_transition_bump_distance)

    transition_bump_chain : IntProperty(
            name = 'Transition bump chain',
            description = 'Number of mask affected by transition bump',
            default=10, min=0, max=10,
            update=transition.update_transition_bump_chain)

    transition_bump_flip : BoolProperty(
            name = 'Transition Bump Flip',
            description = 'Transition bump flip',
            default=False,
            update=transition.update_enable_transition_bump)

    transition_bump_curved_offset : FloatProperty(
            name = 'Transition Bump Curved Offst',
            description = 'Transition bump curved offset',
            default=0.02, min=0.0, max=0.1,
            update=transition.update_transition_bump_curved_offset)

    transition_bump_crease : BoolProperty(
            name = 'Transition Bump Crease',
            description = 'Transition bump crease (only works if flip is inactive)',
            default=False,
            update=transition.update_enable_transition_bump)

    transition_bump_crease_factor : FloatProperty(
            name = 'Transition Bump Crease Factor',
            description = 'Transition bump crease factor',
            default=0.33, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_crease_factor)

    transition_bump_crease_power : FloatProperty(
            name = 'Transition Bump Crease Power',
            description = 'Transition Bump Crease Power',
            default=5.0, min=1.0, max=100.0,
            update=transition.update_transition_bump_crease_power)

    transition_bump_fac : FloatProperty(
            name='Transition Bump Factor',
            description = 'Transition bump factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_fac)

    transition_bump_second_fac : FloatProperty(
            name='Transition Bump Second Factor',
            description = 'Transition bump second factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_fac)

    transition_bump_falloff : BoolProperty(
            name = 'Transition Bump Falloff',
            default = False, update=transition.update_enable_transition_bump)

    transition_bump_falloff_type : EnumProperty(
            name = 'Transition Bump Falloff Type',
            items = (
                ('EMULATED_CURVE', 'Emulated Curve', ''),
                ('CURVE', 'Curve', ''),
                ),
            default = 'EMULATED_CURVE',
            update=transition.update_enable_transition_bump)

    transition_bump_falloff_emulated_curve_fac : FloatProperty(
            name='Transition Bump Falloff Emulated Curve Factor',
            description = 'Transition bump curve emulated curve factor',
            default=1.0, min=-1.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_bump_falloff_emulated_curve_fac)

    tb_bump : StringProperty(default='')
    tb_bump_flip : StringProperty(default='')
    tb_inverse : StringProperty(default='')
    tb_intensity_multiplier : StringProperty(default='')

    tb_falloff : StringProperty(default='')
    #tb_falloff_n : StringProperty(default='')
    #tb_falloff_s : StringProperty(default='')
    #tb_falloff_e : StringProperty(default='')
    #tb_falloff_w : StringProperty(default='')

    # Transition ramp related
    enable_transition_ramp : BoolProperty(name='Enable Transition Ramp', description='Enable alpha transition ramp', 
            default=False, update=transition.update_enable_transition_ramp)

    show_transition_ramp : BoolProperty(name='Toggle Transition Ramp',
            description = "Toggle transition Ramp (Works best if there's transition bump enabled on other channel)", 
            default=False) #, update=transition.update_show_transition_ramp)

    transition_ramp_intensity_value : FloatProperty(
            name = 'Channel Intensity Factor', 
            description = 'Channel Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update=transition.update_transition_ramp_intensity_value)

    transition_ramp_blend_type : EnumProperty(
        name = 'Transition Ramp Blend Type',
        items = blend_type_items,
        default = 'MIX', 
        update=transition.update_enable_transition_ramp)

    transition_ramp_intensity_unlink : BoolProperty(
            name='Unlink Transition Ramp with Channel Intensity', 
            description='Unlink Transition Ramp with Channel Intensity', 
            default=False,
            update=transition.update_enable_transition_ramp)

    # Transition ramp nodes
    tr_ramp : StringProperty(default='')
    tr_ramp_blend : StringProperty(default='')

    # To save ramp and falloff
    cache_ramp : StringProperty(default='')
    cache_falloff_curve : StringProperty(default='')

    # Override type cache
    cache_brick : StringProperty(default='')
    cache_checker : StringProperty(default='')
    cache_gradient : StringProperty(default='')
    cache_magic : StringProperty(default='')
    cache_musgrave : StringProperty(default='')
    cache_noise : StringProperty(default='')
    cache_voronoi : StringProperty(default='')
    cache_wave : StringProperty(default='')

    cache_image : StringProperty(default='')
    cache_1_image : StringProperty(default='')
    cache_vcol : StringProperty(default='')
    cache_hemi : StringProperty(default='')

    # Transition AO related
    enable_transition_ao : BoolProperty(name='Enable Transition AO', 
            description='Enable alpha transition Ambient Occlusion (Need active transition bump)', default=False,
            update=transition.update_enable_transition_ao)

    show_transition_ao : BoolProperty(name='Toggle Transition AO',
            description = "Toggle transition AO (Only works if there's transition bump enabled on other channel)", 
            default=False) #, update=transition.update_show_transition_ao)

    transition_ao_power : FloatProperty(name='Transition AO Power',
            #description='Transition AO edge power (higher value means less AO)', min=1.0, max=100.0, default=4.0,
            description='Transition AO power', min=1.0, max=100.0, default=4.0,
            update=transition.update_transition_ao_edge)

    transition_ao_intensity : FloatProperty(name='Transition AO Intensity',
            description='Transition AO intensity', subtype='FACTOR', min=0.0, max=1.0, default=0.5,
            update=transition.update_transition_ao_intensity)

    transition_ao_color : FloatVectorProperty(name='Transition AO Color', description='Transition AO Color', 
            subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0),
            update=transition.update_transition_ao_color)

    transition_ao_inside_intensity : FloatProperty(name='Transition AO Inside Intensity', 
            description='Transition AO Inside Intensity', subtype='FACTOR', min=0.0, max=1.0, default=0.0,
            update=transition.update_transition_ao_exclude_inside)

    transition_ao_blend_type : EnumProperty(
        name = 'Transition AO Blend Type',
        items = blend_type_items,
        default = 'MIX', 
        update=transition.update_enable_transition_ao)

    transition_ao_intensity_unlink : BoolProperty(
            name='Unlink Transition AO with Channel Intensity', 
            description='Unlink Transition AO with Channel Intensity', 
            default=False,
            update=transition.update_transition_ao_intensity)

    tao : StringProperty(default='')

    active_edit : BoolProperty(
            name='Active override channel for editing or preview', 
            description='Active override channel for editing or preview', 
            default=False,
            update=update_channel_active_edit)

    active_edit_1 : BoolProperty(
            name='Active override channel for editing or preview', 
            description='Active override channel for editing or preview', 
            default=False,
            update=update_channel_active_edit)

    prev_active_edit_idx : IntProperty(
            name='Previous Active Edit Index',
            description='To store previous active edit index',
            default=0)

    # For UI
    expand_bump_settings : BoolProperty(default=False)
    expand_intensity_settings : BoolProperty(default=False)
    expand_content : BoolProperty(default=False)
    expand_transition_bump_settings : BoolProperty(default=False)
    expand_transition_ramp_settings : BoolProperty(default=False)
    expand_transition_ao_settings : BoolProperty(default=False)
    expand_input_settings : BoolProperty(default=False)
    expand_source : BoolProperty(default=False)
    expand_source_1 : BoolProperty(default=False)

def update_layer_color_chortcut(self, context):
    layer = self
    yp = layer.id_data.yp
    if yp.halt_update: return

    # If color shortcut is active, disable other shortcut
    if layer.type == 'COLOR' and layer.color_shortcut:

        for m in layer.modifiers:
            m.shortcut = False

        for ch in layer.channels:
            for m in ch.modifiers:
                m.shortcut = False

def update_layer_transform(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    update_mapping(self)

def update_layer_blur_vector(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    layer = self
    tree = get_tree(layer)

    if layer.enable_blur_vector:
        blur_vector = new_node(tree, layer, 'blur_vector', 'ShaderNodeGroup', 'Blur Vector')
        blur_vector.node_tree = get_node_tree_lib(lib.BLUR_VECTOR)
        blur_vector.inputs[0].default_value = layer.blur_vector_factor / 100.0
    else:
        remove_node(tree, layer, 'blur_vector')

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def update_layer_blur_vector_factor(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    layer = self
    tree = get_tree(layer)

    blur_vector = tree.nodes.get(layer.blur_vector)

    if blur_vector:
        blur_vector.inputs[0].default_value = layer.blur_vector_factor / 100.0

class YLayer(bpy.types.PropertyGroup):
    name : StringProperty(default='', update=update_layer_name)
    enable : BoolProperty(
            name = 'Enable Layer', description = 'Enable layer',
            default=True, update=update_layer_enable)

    channels : CollectionProperty(type=YLayerChannel)

    group_node : StringProperty(default='')
    trash_group_node : StringProperty(default='')
    depth_group_node : StringProperty(default='')

    type : EnumProperty(
            name = 'Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    color_shortcut : BoolProperty(
            name = 'Color Shortcut on the list',
            description = 'Display color shortcut on the list',
            default=True,
            update=update_layer_color_chortcut)

    texcoord_type : EnumProperty(
        name = 'Layer Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_texcoord_type)

    # For temporary bake
    use_temp_bake : BoolProperty(
            name = 'Use Temporary Bake',
            description = 'Use temporary bake, it can be useful for prevent glitch on cycles',
            default = False,
            #update=update_layer_temp_bake
            )

    original_type : EnumProperty(
            name = 'Original Layer Type',
            items = layer_type_items,
            default = 'IMAGE')

    image_flip_y : BoolProperty(
            name = 'Image Flip Y',
            description = "Image Flip Y (Use this if you're using normal map created for DirectX application) ",
            default = False,
            update=update_image_flip_y)

    divide_rgb_by_alpha : BoolProperty(
            name = 'Spread Fix',
            description = "Spread fix will divide RGB value by its alpha\nThis can be useful remove dark outline on painted image/vertex color\nWARNING: This is a hack solution so the result might not looks right",
            default = False,
            update=update_divide_rgb_by_alpha)

    # Fake lighting related

    hemi_space : EnumProperty(
            name = 'Fake Lighting Space',
            description = 'Fake lighting space',
            items = hemi_space_items,
            default = 'OBJECT',
            update=update_hemi_space)

    hemi_vector : FloatVectorProperty(
            name='Cache Hemi vector', size=3, precision=3,
            default=(0.0, 0.0, 1.0))

    hemi_camera_ray_mask : BoolProperty(
            name = 'Camera Ray Mask',
            description = "Use Camera Ray value so the back of the mesh won't be affected by fake lighting",
            default = False, update=update_hemi_camera_ray_mask)

    hemi_use_prev_normal : BoolProperty(
            name = 'Use previous Normal',
            description = 'Take account previous Normal',
            default = False, update=update_hemi_use_prev_normal)

    bump_process : StringProperty(default='')

    # To detect change of layer image
    image_name : StringProperty(default='')

    # To get segment if using image atlas
    segment_name : StringProperty(default='')

    uv_name : StringProperty(default='', update=update_uv_name)

    # Parent index
    parent_idx : IntProperty(default=-1)

    # Transform
    translation : FloatVectorProperty(
            name='Translation', size=3, precision=3, 
            default=(0.0, 0.0, 0.0),
            update=update_layer_transform
            ) #, step=1)

    rotation : FloatVectorProperty(
            name='Rotation', subtype='AXISANGLE', size=3, precision=3, unit='ROTATION', 
            default=(0.0, 0.0, 0.0),
            update=update_layer_transform
            ) #, step=3)

    scale : FloatVectorProperty(
            name='Scale', size=3, precision=3, 
            default=(1.0, 1.0, 1.0),
            update=update_layer_transform,
            ) #, step=3)

    enable_blur_vector : BoolProperty(
            name = 'Enable Blur Vector',
            description = "Enable blur vector",
            default = False, update=update_layer_blur_vector)

    blur_vector_factor : FloatProperty(
            name = 'Blur Vector Factor', 
            description = 'Mask Intensity Factor',
            default=1.0, min=0.0, max=100.0,
            update=update_layer_blur_vector_factor)

    # Sources
    source : StringProperty(default='')
    source_n : StringProperty(default='')
    source_s : StringProperty(default='')
    source_e : StringProperty(default='')
    source_w : StringProperty(default='')
    source_group : StringProperty(default='')

    source_temp : StringProperty(default='')

    # Linear node
    linear : StringProperty(default='')

    # Fix nodes
    flip_y : StringProperty(default='')
    divider_alpha : StringProperty(default='')

    # Layer type cache
    cache_brick : StringProperty(default='')
    cache_checker : StringProperty(default='')
    cache_gradient : StringProperty(default='')
    cache_magic : StringProperty(default='')
    cache_musgrave : StringProperty(default='')
    cache_noise : StringProperty(default='')
    cache_voronoi : StringProperty(default='')
    cache_wave : StringProperty(default='')
    cache_color : StringProperty(default='')

    # UV
    uv_neighbor : StringProperty(default='')
    uv_neighbor_1 : StringProperty(default='')
    uv_map : StringProperty(default='')
    mapping : StringProperty(default='')
    texcoord : StringProperty(default='')
    blur_vector : StringProperty(default='')

    #need_temp_uv_refresh : BoolProperty(default=False)

    # Other Vectors
    tangent : StringProperty(default='')
    bitangent : StringProperty(default='')
    tangent_flip : StringProperty(default='')
    bitangent_flip : StringProperty(default='')

    # Modifiers
    modifiers : CollectionProperty(type=Modifier.YPaintModifier)
    mod_group : StringProperty(default='')
    mod_group_1 : StringProperty(default='')

    # Mask
    enable_masks : BoolProperty(name='Enable Layer Masks', description='Enable layer masks',
            default=True, update=Mask.update_enable_layer_masks)
    masks : CollectionProperty(type=Mask.YLayerMask)

    # UI related
    expand_content : BoolProperty(default=False)
    expand_vector : BoolProperty(default=False)
    expand_masks : BoolProperty(default=False)
    expand_channels : BoolProperty(default=True)
    expand_source : BoolProperty(default=False)

def register():
    bpy.utils.register_class(YRefreshNeighborUV)
    bpy.utils.register_class(YUseLinearColorSpace)
    bpy.utils.register_class(YNewLayer)
    bpy.utils.register_class(YNewVcolToOverrideChannel)
    bpy.utils.register_class(YOpenImageToLayer)
    bpy.utils.register_class(YOpenMultipleImagesToSingleLayer)
    bpy.utils.register_class(YOpenImageToOverrideChannel)
    bpy.utils.register_class(YOpenImageToOverride1Channel)
    bpy.utils.register_class(YOpenAvailableDataToLayer)
    bpy.utils.register_class(YOpenAvailableDataToOverrideChannel)
    bpy.utils.register_class(YOpenAvailableDataToOverride1Channel)
    bpy.utils.register_class(YMoveLayer)
    bpy.utils.register_class(YMoveInOutLayerGroup)
    bpy.utils.register_class(YMoveInOutLayerGroupMenu)
    bpy.utils.register_class(YRemoveLayer)
    bpy.utils.register_class(YRemoveLayerMenu)
    bpy.utils.register_class(YReplaceLayerType)
    bpy.utils.register_class(YReplaceLayerChannelOverride)
    bpy.utils.register_class(YReplaceLayerChannelOverride1)
    bpy.utils.register_class(YDuplicateLayer)
    bpy.utils.register_class(YCopyLayer)
    bpy.utils.register_class(YPasteLayer)
    bpy.utils.register_class(YLayerChannel)
    bpy.utils.register_class(YLayer)

def unregister():
    bpy.utils.unregister_class(YRefreshNeighborUV)
    bpy.utils.unregister_class(YUseLinearColorSpace)
    bpy.utils.unregister_class(YNewLayer)
    bpy.utils.unregister_class(YNewVcolToOverrideChannel)
    bpy.utils.unregister_class(YOpenImageToLayer)
    bpy.utils.unregister_class(YOpenMultipleImagesToSingleLayer)
    bpy.utils.unregister_class(YOpenImageToOverrideChannel)
    bpy.utils.unregister_class(YOpenImageToOverride1Channel)
    bpy.utils.unregister_class(YOpenAvailableDataToLayer)
    bpy.utils.unregister_class(YOpenAvailableDataToOverrideChannel)
    bpy.utils.unregister_class(YOpenAvailableDataToOverride1Channel)
    bpy.utils.unregister_class(YMoveLayer)
    bpy.utils.unregister_class(YMoveInOutLayerGroup)
    bpy.utils.unregister_class(YMoveInOutLayerGroupMenu)
    bpy.utils.unregister_class(YRemoveLayer)
    bpy.utils.unregister_class(YRemoveLayerMenu)
    bpy.utils.unregister_class(YReplaceLayerType)
    bpy.utils.unregister_class(YReplaceLayerChannelOverride)
    bpy.utils.unregister_class(YReplaceLayerChannelOverride1)
    bpy.utils.unregister_class(YDuplicateLayer)
    bpy.utils.unregister_class(YCopyLayer)
    bpy.utils.unregister_class(YPasteLayer)
    bpy.utils.unregister_class(YLayerChannel)
    bpy.utils.unregister_class(YLayer)
