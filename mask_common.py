import bpy, re
from .common import *
from .node_arrangements import *
from .node_connections import *
from . import ListItem, subtree, input_outputs, lib

def setup_color_id_source(mask, source, color_id=None):
    if is_bl_newer_than(2, 82):
        source.node_tree = get_node_tree_lib(lib.COLOR_ID_EQUAL_282)
    else: source.node_tree = get_node_tree_lib(lib.COLOR_ID_EQUAL)

    if color_id != None:
        mask.color_id = color_id
    else: color_id = mask.color_id

    col = (color_id[0], color_id[1], color_id[2], 1.0)
    source.inputs[0].default_value = col

def setup_object_idx_source(mask, source, object_index=None):
    source.node_tree = get_node_tree_lib(lib.OBJECT_INDEX_EQUAL)

    if object_index != None:
        mask.object_index = object_index
    else: object_index = mask.object_index

    source.inputs[0].default_value = object_index

def setup_modifier_mask_source(tree, mask, modifier_type):
    source = None
    if modifier_type == 'INVERT':
        source = new_node(tree, mask, 'source', 'ShaderNodeInvert', 'Mask Source')
    elif modifier_type == 'RAMP':
        source = new_node(tree, mask, 'source', 'ShaderNodeValToRGB', 'Mask Source')
        #ramp_mix = new_mix_node(tree, mask, 'ramp_mix', 'Ramp Mix', 'FLOAT')
    elif modifier_type == 'CURVE':
        source = new_node(tree, mask, 'source', 'ShaderNodeRGBCurve', 'Mask Source')

    return source

def get_new_mask_name(obj, layer, mask_type, modifier_type='', ignore_images=False):
    surname = '(' + layer.name + ')'
    items = layer.masks
    if mask_type == 'IMAGE':
        name = 'Mask'
        name = get_unique_name(name, layer.masks, surname)
        if not ignore_images:
            name = get_unique_name(name, bpy.data.images)
        return name
    elif mask_type == 'VCOL' and obj.type == 'MESH':
        name = 'Mask Attribute' if is_bl_newer_than(3, 2) else 'Mask VCol'
        items = get_vertex_color_names(obj)
        return get_unique_name(name, items, surname)
    elif mask_type == 'MODIFIER':
        name = 'Mask ' + modifier_type.title()
        return get_unique_name(name, items, surname)
    else:
        name = 'Mask ' + mask_type_labels[mask_type]
        return get_unique_name(name, items, surname)

def check_mask_image_projections(mask, source=None):
    if source == None: source = get_mask_source(mask)
    source.projection = 'BOX' if mask.texcoord_type in {'Generated', 'Object'} else 'FLAT'

def update_mask_texcoord_type(self, context, reconnect=True, check_io=True):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))
    mask = self
    tree = get_tree(layer)

    # Update global uv
    subtree.check_uv_nodes(yp)

    # Update layer tree inputs
    if check_io:
        input_outputs.check_all_layer_channel_io_and_nodes(layer, tree)

    # Set image source projection
    if mask.type == 'IMAGE':
        check_mask_image_projections(mask)

    if reconnect:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(self.id_data)
        rearrange_yp_nodes(self.id_data)

def add_new_mask(
        layer, name, mask_type, texcoord_type, uv_name, 
        image=None, vcol_name='', segment=None,
        object_index=0, blend_type='MULTIPLY', hemi_space='WORLD', hemi_use_prev_normal=False,
        color_id=(1, 0, 1), edge_detect_radius=0.05, edge_detect_method='CROSS',
        modifier_type='INVERT', interpolation='Linear', ao_distance=1.0, socket_input_name='Color'
    ):
    yp = layer.id_data.yp
    ori_halt_update = yp.halt_update
    yp.halt_update = True
    ypup = get_user_preferences()

    tree = get_tree(layer)
    nodes = tree.nodes

    mask = layer.masks.add()
    mask.name = get_unique_name(name, layer.masks)
    mask.type = mask_type
    mask.texcoord_type = texcoord_type
    mask.socket_input_name = socket_input_name

    # Uniform Scale
    if is_bl_newer_than(2, 81) and is_mask_using_vector(mask):
        mask.enable_uniform_scale = ypup.enable_uniform_uv_scale_by_default

    if segment:
        mask.segment_name = segment.name

    source = None
    if mask_type == 'VCOL':
        source = new_node(tree, mask, 'source', get_vcol_bl_idname(), 'Mask Source')
    elif mask_type == 'MODIFIER':
        source = setup_modifier_mask_source(tree, mask, modifier_type)
        mask.modifier_type = modifier_type

    elif mask.type != 'BACKFACE': source = new_node(tree, mask, 'source', layer_node_bl_idnames[mask_type], 'Mask Source')

    if image:
        source.image = image
        if hasattr(source, 'color_space'):
            source.color_space = 'NONE'
        source.interpolation = interpolation
    elif mask_type == 'VCOL':
        if vcol_name != '': set_source_vcol_name(source, vcol_name)
        else: set_source_vcol_name(source, name)

    if mask_type == 'HEMI':
        source.node_tree = get_node_tree_lib(lib.HEMI)
        duplicate_lib_node_tree(source)
        mask.hemi_space = hemi_space
        mask.hemi_use_prev_normal = hemi_use_prev_normal

    elif mask_type == 'OBJECT_INDEX':
        setup_object_idx_source(mask, source, object_index)

    elif mask_type == 'COLOR_ID':
        setup_color_id_source(mask, source, color_id)

    elif mask_type == 'EDGE_DETECT':
        mask.hemi_use_prev_normal = hemi_use_prev_normal
        lib.setup_edge_detect_source(mask, source, edge_detect_radius, edge_detect_method)

    elif mask_type == 'AO':
        mask.hemi_use_prev_normal = hemi_use_prev_normal
        mask.ao_distance = ao_distance
        enable_eevee_ao()

    # Set default uv name if it's an empty string
    if uv_name == '':
        uv_name = get_default_uv_name()

    mask.uv_name = uv_name

    if is_mapping_possible(mask_type):

        mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')
        mapping.vector_type = 'POINT' #if segment else 'TEXTURE'

        if segment:
            ImageAtlas.set_segment_mapping(mask, segment, image)
            refresh_temp_uv(bpy.context.object, mask)

    for i, root_ch in enumerate(yp.channels):
        c = mask.channels.add()

    mask.blend_type = blend_type

    # Check mask multiplies
    subtree.check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    subtree.check_mask_source_tree(layer)

    # Check the need of bump process
    subtree.check_layer_bump_process(layer, tree)

    # Check uv maps
    subtree.check_uv_nodes(yp)

    if ori_halt_update != yp.halt_update:
        yp.halt_update = ori_halt_update

    # Update coords
    update_mask_texcoord_type(mask, None, False, False)

    # Check layer io
    input_outputs.check_all_layer_channel_io_and_nodes(layer, tree)

    # Check mask linear
    subtree.check_mask_image_linear_node(mask)

    # Update list items
    ListItem.refresh_list_items(yp)

    return mask

