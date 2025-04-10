import bpy, re, time, random
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from . import lib, ImageAtlas, MaskModifier, UDIM, ListItem
from .common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *
from .input_outputs import *

#def check_object_index_props(entity, source=None):
#    source.inputs[0].default_value = entity.object_index

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

def setup_edge_detect_source(entity, source, edge_detect_radius=None):
    if entity.hemi_use_prev_normal:
        lib_name = lib.EDGE_DETECT_CUSTOM_NORMAL
    else: lib_name = lib.EDGE_DETECT

    ori_lib = source.node_tree
    if not ori_lib or ori_lib.name != lib_name:
        source.node_tree = get_node_tree_lib(lib_name)
        if ori_lib and ori_lib.users == 0:
            remove_datablock(bpy.data.node_groups, ori_lib)

    if edge_detect_radius != None:
        source.inputs[0].default_value = entity.edge_detect_radius = edge_detect_radius
    else: source.inputs[0].default_value = entity.edge_detect_radius

    enable_eevee_ao()

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

def add_new_mask(
        layer, name, mask_type, texcoord_type, uv_name, image=None, vcol=None, segment=None,
        object_index=0, blend_type='MULTIPLY', hemi_space='WORLD', hemi_use_prev_normal=False,
        color_id=(1, 0, 1), source_input='RGB', edge_detect_radius=0.05,
        modifier_type='INVERT', interpolation='Linear', ao_distance=1.0
    ):
    yp = layer.id_data.yp
    yp.halt_update = True
    ypup = get_user_preferences()

    tree = get_tree(layer)
    nodes = tree.nodes

    mask = layer.masks.add()
    mask.name = get_unique_name(name, layer.masks)
    mask.type = mask_type
    mask.texcoord_type = texcoord_type
    mask.source_input = source_input

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
        if vcol: set_source_vcol_name(source, vcol.name)
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
        setup_edge_detect_source(mask, source, edge_detect_radius)

    elif mask_type == 'AO':
        mask.hemi_use_prev_normal = hemi_use_prev_normal
        mask.ao_distance = ao_distance
        enable_eevee_ao()

    if is_mapping_possible(mask_type):
        mask.uv_name = uv_name

        mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')
        mapping.vector_type = 'POINT' if segment else 'TEXTURE'

        if segment:
            ImageAtlas.set_segment_mapping(mask, segment, image)
            refresh_temp_uv(bpy.context.object, mask)

    for i, root_ch in enumerate(yp.channels):
        ch = layer.channels[i]
        c = mask.channels.add()

    mask.blend_type = blend_type

    # Check mask multiplies
    check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    check_mask_source_tree(layer)

    # Check the need of bump process
    check_layer_bump_process(layer, tree)

    # Check uv maps
    check_uv_nodes(yp)

    # Check layer io
    check_all_layer_channel_io_and_nodes(layer, tree)

    # Check mask linear
    check_mask_image_linear_node(mask)

    yp.halt_update = False

    # Update coords
    update_mask_texcoord_type(mask, None, False)

    # Update list items
    ListItem.refresh_list_items(yp)

    return mask

def remove_mask_channel_nodes(tree, c):
    remove_node(tree, c, 'mix')
    remove_node(tree, c, 'mix_n')
    remove_node(tree, c, 'mix_s')
    remove_node(tree, c, 'mix_e')
    remove_node(tree, c, 'mix_w')
    remove_node(tree, c, 'mix_pure')
    remove_node(tree, c, 'mix_remains')
    remove_node(tree, c, 'mix_normal')
    remove_node(tree, c, 'mix_limit')
    remove_node(tree, c, 'mix_limit_normal')

def remove_mask_channel(tree, layer, ch_index):

    # Remove mask nodes
    for mask in layer.masks:

        # Get channels
        c = mask.channels[ch_index]
        ch = layer.channels[ch_index]

        # Remove mask channel nodes first
        remove_mask_channel_nodes(tree, c)

    # Remove the mask itself
    for mask in layer.masks:
        mask.channels.remove(ch_index)

def remove_mask(layer, mask, obj):

    tree = get_tree(layer)
    yp = layer.id_data.yp
    mat = obj.active_material

    # Get mask index
    mask_index = [i for i, m in enumerate(layer.masks) if m == mask][0]

    # Dealing with decal object
    remove_decal_object(tree, mask)

    # Remove mask fcurves first
    remove_entity_fcurves(mask)
    shift_mask_fcurves_up(layer, mask_index)

    # Dealing with image atlas segments
    if mask.type == 'IMAGE':
        src = get_mask_source(mask)
        if src and src.image:
            image = src.image
            if mask.segment_name != '':
                if image.yia.is_image_atlas:
                    segment = image.yia.segments.get(mask.segment_name)
                    segment.unused = True
                elif image.yua.is_udim_atlas:
                    print('ZEGMENT:', mask.segment_name)
                    UDIM.remove_udim_atlas_segment_by_name(image, mask.segment_name, yp=yp)

    disable_mask_source_tree(layer, mask)

    remove_node(tree, mask, 'source')
    remove_node(tree, mask, 'baked_source')
    remove_node(tree, mask, 'blur_vector')
    remove_node(tree, mask, 'separate_color_channels')
    remove_node(tree, mask, 'mapping')
    remove_node(tree, mask, 'texcoord')
    remove_node(tree, mask, 'baked_mapping')
    remove_node(tree, mask, 'linear')
    remove_node(tree, mask, 'uv_map')
    remove_node(tree, mask, 'uv_neighbor')

    # Remove mask modifiers
    for m in mask.modifiers:
        MaskModifier.delete_modifier_nodes(tree, m)

    # Remove mask channel nodes
    for c in mask.channels:
        remove_mask_channel_nodes(tree, c)

    # Remove mask
    layer.masks.remove(mask_index)

    # Update list items
    ListItem.refresh_list_items(yp)

def get_new_mask_name(obj, layer, mask_type, modifier_type=''):
    surname = '(' + layer.name + ')'
    items = layer.masks
    if mask_type == 'IMAGE':
        name = 'Mask'
        name = get_unique_name(name, layer.masks, surname)
        name = get_unique_name(name, bpy.data.images)
        return name
    elif mask_type == 'VCOL' and obj.type == 'MESH':
        name = 'Mask VCol'
        items = get_vertex_color_names(obj)
        return get_unique_name(name, items, surname)
    elif mask_type == 'MODIFIER':
        name = 'Mask ' + modifier_type.title()
        return get_unique_name(name, items, surname)
    else:
        name = 'Mask ' + [i[1] for i in mask_type_items if i[0] == mask_type][0]
        return get_unique_name(name, items, surname)

def update_new_mask_uv_map(self, context):
    if not UDIM.is_udim_supported(): return
    if self.type != 'IMAGE': 
        self.use_udim = False
        return

    if get_user_preferences().enable_auto_udim_detection:
        mat = get_active_material()
        objs = get_all_objects_with_same_materials(mat)
        self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_name)


def get_mask_cache_name(mask_type, modifier_type=''):
    name = 'cache_' + mask_type.lower()

    if mask_type == 'MODIFIER':
        name += '_' + modifier_type.lower()

    return name

def is_mask_type_cacheable(mask_type, modifier_type=''):
    if mask_type == 'MODIFIER':
        return modifier_type in {'RAMP', 'CURVE'}

    return mask_type not in {'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'EDGE_DETECT', 'BACKFACE', 'AO'}

def replace_mask_type(mask, new_type, item_name='', remove_data=False, modifier_type='INVERT'):

    yp = mask.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', mask.path_from_id())
    layer = yp.layers[int(match.group(1))]

    # Check if mask is using image atlas
    if mask.type == 'IMAGE' and mask.segment_name != '':

        # Replace to non atlas image will remove the segment
        if new_type == 'IMAGE':
            src = get_mask_source(mask)
            if src.image.yia.is_image_atlas:
                segment = src.image.yia.segments.get(mask.segment_name)
                segment.unused = True
            elif src.image.yua.is_udim_atlas:
                UDIM.remove_udim_atlas_segment_by_name(src.image, mask.segment_name, yp=yp)

            # Set segment name to empty
            mask.segment_name = ''

        # Reset mapping
        clear_mapping(mask)

    # Save hemi vector
    if mask.type == 'HEMI':
        src = get_mask_source(mask)
        save_hemi_props(mask, src)

    yp.halt_reconnect = True

    # Standard bump map is easier to convert
    fine_bump_channels = [ch for ch in yp.channels if ch.enable_smooth_bump]
    for ch in fine_bump_channels:
        ch.enable_smooth_bump = False

    # Disable transition will also helps
    transition_channels = [ch for ch in layer.channels if ch.enable_transition_bump]
    for ch in transition_channels:
        ch.enable_transition_bump = False

    # Current source
    tree = get_mask_tree(mask)
    source = get_mask_source(mask)

    # Save source to cache if it's not image, vertex color, or background
    if is_mask_type_cacheable(mask.type, mask.modifier_type):
        setattr(mask, get_mask_cache_name(mask.type, mask.modifier_type), source.name)
        # Remove uv input link
        if any(source.inputs) and any(source.inputs[0].links):
            tree.links.remove(source.inputs[0].links[0])
        source.label = ''
    else:
        # Remember values by disabling then enabling the mask again
        if mask.enable:
            mask.enable = False
            mask.enable = True

        remove_node(tree, mask, 'source', remove_data=remove_data)

    # Disable modifier tree
    #if is_mask_type_cacheable(mask.type, mask.modifier_type) and is_mask_type_cacheable(new_type, modifier_type):
    #    Modifier.disable_modifiers_tree(mask)

    # Try to get available cache
    cache = None
    if is_mask_type_cacheable(new_type, modifier_type) and mask.type != new_type:
        cache = tree.nodes.get(getattr(mask, get_mask_cache_name(new_type, modifier_type)))

    if cache:
        mask.source = cache.name
        setattr(mask, get_mask_cache_name(new_type, modifier_type), '')
        cache.label = 'Source'

    else:

        if new_type == 'MODIFIER':
            source = setup_modifier_mask_source(tree, mask, modifier_type)
        elif new_type != 'BACKFACE': source = new_node(tree, mask, 'source', layer_node_bl_idnames[new_type], 'Source')

        if new_type == 'IMAGE':
            image = bpy.data.images.get(item_name)
            source.image = image
            if hasattr(source, 'color_space'):
                source.color_space = 'NONE'
            if image.colorspace_settings.name != get_noncolor_name() and not image.is_dirty:
                image.colorspace_settings.name = get_noncolor_name()

        elif new_type == 'VCOL':
            set_source_vcol_name(source, item_name)

        elif new_type == 'HEMI':
            source.node_tree = get_node_tree_lib(lib.HEMI)
            duplicate_lib_node_tree(source)
            load_hemi_props(mask, source)

        elif new_type == 'COLOR_ID':
            mat = get_active_material()
            objs = get_all_objects_with_same_materials(mat)
            check_colorid_vcol(objs, set_as_active=True)
            setup_color_id_source(mask, source)

        elif new_type == 'OBJECT_INDEX':
            setup_object_idx_source(mask, source)

        elif new_type == 'EDGE_DETECT':
            setup_edge_detect_source(mask, source)

        elif new_type == 'AO':
            enable_eevee_ao()

    # Change mask type
    ori_type = mask.type
    mask.type = new_type

    # Change mask modifier type
    if mask.type == 'MODIFIER':
        mask.modifier_type = modifier_type

    # Set up mapping
    mapping = tree.nodes.get(mask.mapping)
    if is_mapping_possible(new_type):
        if not mapping:
            mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')
    else:
        remove_node(tree, mask, 'mapping')

    # Update mask name
    image = None
    if mask.type == 'IMAGE':
        # Rename mask with image name
        source = get_mask_source(mask)
        if source and source.image:
            image = source.image
            yp.halt_update = True
            if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                new_name = 'Mask (' + layer.name + ')'

                # Set back the mapping
                if image.yia.is_image_atlas:
                    segment = image.yia.segments.get(mask.segment_name)
                    ImageAtlas.set_segment_mapping(mask, segment, image)
                else:
                    segment = image.yua.segments.get(mask.segment_name)
                    UDIM.set_udim_segment_mapping(mask, segment, image)

            else: new_name = image.name
            mask.name = get_unique_name(new_name, layer.masks)
            yp.halt_update = False

            # Set interpolation to Cubic if normal/height channel is found
            height_ch = get_height_channel(mask)
            if height_ch and height_ch.enable:
                source.interpolation = 'Cubic'

    elif mask.type == 'VCOL':
        # Rename mask with vcol name
        source = get_mask_source(mask)
        if source: mask.name = get_unique_name(source.attribute_name, layer.masks)

        # Set active vertex color
        set_active_vertex_color_by_name(bpy.context.object, source.attribute_name)

    elif mask.type == 'MODIFIER':
        # Rename mask with modifier types
        mask.name = get_unique_name(MaskModifier.mask_modifier_type_labels[mask.modifier_type], layer.masks)

    elif ori_type in {'IMAGE', 'VCOL'}:
        # Rename mask with texture types
        mask.name = get_unique_name(mask_type_labels[mask.type], layer.masks)

    elif mask_type_labels[ori_type] in mask.name:  
        # Rename texture types with another texture types
        mask.name = get_unique_name(mask.name.replace(mask_type_labels[ori_type], mask_type_labels[mask.type]), layer.masks)

    # Enable modifiers tree if generated texture is used
    #if mask.type not in {'IMAGE', 'VCOL', 'BACKGROUND'}:
    #    Modifier.enable_modifiers_tree(mask)
    #Modifier.check_modifiers_trees(mask)

    # Set default UV name when necessary
    if is_mapping_possible(mask.type) and mask.uv_name == '':
        obj = bpy.context.object
        if obj and obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            yp.halt_update = True
            mask.uv_name = get_default_uv_name(obj, yp)
            yp.halt_update = False

    # Always remove baked mask when changing type
    if mask.use_baked:
        mask.use_baked = False
        remove_node(tree, mask, 'baked_source')

    # Update group ios
    check_all_layer_channel_io_and_nodes(layer, tree)

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

    # Check children which need rearrange
    #for i in child_ids:
        #lay = yp.layers[i]
    #for lay in yp.layers:
    #    check_all_layer_channel_io_and_nodes(lay)
    #    reconnect_layer_nodes(lay)
    #    rearrange_layer_nodes(lay)

    for lay in yp.layers:
        check_all_layer_channel_io_and_nodes(lay)
        reconnect_layer_nodes(lay)
        rearrange_layer_nodes(lay)

    #reconnect_layer_nodes(layer)
    #rearrange_layer_nodes(layer)

    #if mask.type in {'BACKGROUND', 'GROUP'} or ori_type == 'GROUP':
    reconnect_yp_nodes(mask.id_data)
    rearrange_yp_nodes(mask.id_data)

    # Update UI
    bpy.context.window_manager.ypui.need_update = True
    mask.expand_source = mask.type not in {'IMAGE'} or (image != None and image.y_bake_info.is_baked and not image.y_bake_info.is_baked_channel)

class YNewLayerMask(bpy.types.Operator):
    bl_idname = "wm.y_new_layer_mask"
    bl_label = "New Layer Mask"
    bl_description = "New Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
        name = 'Mask Type',
        items = mask_type_items,
        default = 'IMAGE'
    )

    modifier_type = EnumProperty(
        name = 'Mask Modifier Type',
        items = MaskModifier.mask_modifier_type_items,
        default = 'INVERT'
    )

    width = IntProperty(name='Width', default=1024, min=1, max=16384)
    height = IntProperty(name='Height', default=1024, min=1, max=16384)
    
    interpolation = EnumProperty(
        name = 'Image Interpolation Type',
        description = 'image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 3 if is_bl_newer_than(2, 90) else None,
    )

    color_option = EnumProperty(
        name = 'Color Option',
        description = 'Color Option',
        items = (
            ('WHITE', 'White (Full Opacity)', ''),
            ('BLACK', 'Black (Full Transparency)', ''),
        ),
        default='WHITE'
    )

    color_id = FloatVectorProperty(
        name = 'Color ID',
        size = 3,
        subtype = 'COLOR',
        default=(1.0, 0.0, 1.0), min=0.0, max=1.0,
    )

    vcol_fill = BoolProperty(
        name = 'Fill Selected Geometry with Vertex Color / Color ID',
        description = 'Fill selected geometry with vertex color / color ID',
        default = True
    )

    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
        name = 'Mask Coordinate Type',
        description = 'Mask Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV'
    )

    uv_name = StringProperty(default='', update=update_new_mask_uv_map)
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    use_udim = BoolProperty(
        name = 'Use UDIM Tiles',
        description = 'Use UDIM Tiles',
        default = False
    )

    use_image_atlas = BoolProperty(
        name = 'Use Image Atlas',
        description = 'Use Image Atlas',
        default = False
    )

    # For fake lighting
    hemi_space = EnumProperty(
        name = 'Fake Lighting Space',
        description = 'Fake lighting space',
        items = hemi_space_items,
        default = 'WORLD'
    )

    hemi_use_prev_normal = BoolProperty(
        name = 'Use previous Normal',
        description = 'Take previous Normal into the account',
        default = True
    )

    # For object index
    object_index = IntProperty(
        name = 'Object Index',
        description = 'Object Pass Index',
        default=0, min=0
    )

    edge_detect_radius = FloatProperty(
        name = 'Detect Mask Radius',
        description = 'Edge detect radius',
        default=0.05, min=0.0, max=10.0
    )

    ao_distance = FloatProperty(
        name = 'Ambient Occlusion Distance',
        description = 'Ambient occlusion distance',
        default=1.0, min=0.0, max=10.0
    )

    vcol_data_type = EnumProperty(
        name = 'Vertex Color Data Type',
        description = 'Vertex color data type',
        items = vcol_data_type_items,
        default = 'BYTE_COLOR'
    )

    vcol_domain = EnumProperty(
        name = 'Vertex Color Domain',
        description = 'Vertex color domain',
        items = vcol_domain_items,
        default = 'CORNER'
    )
    
    image_resolution = EnumProperty(
        name = 'Image Resolution',
        items = image_resolution_items,
        default = '1024'
    )
    
    use_custom_resolution = BoolProperty(
        name = 'Custom Resolution',
        default = False,
        description = 'Use custom Resolution to adjust the width and height individually'
    )

    @classmethod
    def poll(cls, context):
        return True

    @classmethod
    def description(self, context, properties):
        return get_operator_description(self)

    def get_to_be_cleared_image_atlas(self, context, yp):
        if self.type == 'IMAGE' and self.use_image_atlas:
            return ImageAtlas.check_need_of_erasing_segments(yp, self.color_option, self.width, self.height, self.hdr)

        return None

    def invoke(self, context, event):

        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        obj = context.object
        layer = get_active_layer(yp)

        self.auto_cancel = False
        if not layer:
            self.auto_cancel = True
            return self.execute(context)

        yp = layer.id_data.yp
        ypup = get_user_preferences()

        self.name = get_new_mask_name(obj, layer, self.type, self.modifier_type)

        # Use user preference default image size
        if ypup.default_image_resolution == 'CUSTOM':
            self.use_custom_resolution = True
            self.width = self.height = ypup.default_new_image_size
        elif ypup.default_image_resolution != 'DEFAULT':
            self.image_resolution = ypup.default_image_resolution

        if self.type == 'COLOR_ID':
            # Check if color id already being used
            while True:
                # Use color id tolerance value as lowest value to avoid pure black color
                self.color_id = (random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0))
                if not is_colorid_already_being_used(yp, self.color_id): break

        # Disable use previous normal for edge detect since it has very little effect
        if self.type == 'EDGE_DETECT':
            self.hemi_use_prev_normal = False

        # Make sure decal is off when adding non mappable mask
        if not is_mapping_possible(self.type) and self.texcoord_type == 'Decal':
            self.texcoord_type = 'UV'

        if obj.type != 'MESH':
            self.texcoord_type = 'Generated'
        elif len(obj.data.uv_layers) > 0:

            self.uv_name = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # The default blend type for mask is multiply
        if self.type in {'MODIFIER'}:
            self.blend_type = 'MIX'
        else:
            self.blend_type = 'MULTIPLY'

        # Check if there's height channel and use cubic interpolation if there is one
        height_ch = get_height_channel(layer)
        if height_ch and height_ch.enable and self.type == 'IMAGE':
            self.interpolation = 'Cubic'
        elif layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image: self.interpolation = source.interpolation

        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        ypup = get_user_preferences()

        if not self.use_custom_resolution:
            self.height = self.width = int(self.image_resolution)

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = get_active_layer(yp)

        row = split_layout(self.layout, 0.4)

        col = row.column(align=False)
        col.label(text='Name:')
        if self.type == 'IMAGE' and self.use_custom_resolution == False:
            col.label(text='')
            col.label(text='Resolution:')
        elif self.type == 'IMAGE' and self.use_custom_resolution == True:
            col.label(text='')
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type == 'IMAGE':
            col.label(text='Interpolation:')

        if self.type in {'VCOL', 'IMAGE'}:
            col.label(text='Color:')

        if self.type == 'COLOR_ID':
            col.label(text='Color ID:')
            if obj.mode == 'EDIT':
                col.label(text='')

        if self.type == 'VCOL':
            if is_bl_newer_than(3, 2):
                col.label(text='Domain:')
                col.label(text='Data Type:')
            if obj.mode == 'EDIT' and self.color_option == 'BLACK':
                col.label(text='')

        if self.type == 'HEMI':
            col.label(text='Space:')

        if self.type == 'EDGE_DETECT':
            col.label(text='Radius:')

        if self.type == 'AO':
            col.label(text='AO Distance:')

        if self.type in {'HEMI', 'EDGE_DETECT', 'AO'}:
            col.label(text='')

        if self.type == 'IMAGE':
            col.label(text='')

        if self.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER', 'AO'}:
            col.label(text='Vector:')
            if self.type == 'IMAGE':
                if UDIM.is_udim_supported():
                    col.label(text='')
                col.label(text='')

        if self.type == 'OBJECT_INDEX':
            col.label(text='Object Index')

        col.label(text='Blend:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'IMAGE' and self.use_custom_resolution == False:
            crow = col.row(align=True)
            crow.prop(self, 'use_custom_resolution')
            crow = col.row(align=True)
            crow.prop(self, 'image_resolution', expand= True,)
        elif self.type == 'IMAGE' and self.use_custom_resolution == True:
            crow = col.row(align=True)
            crow.prop(self, 'use_custom_resolution')
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type == 'IMAGE':
            col.prop(self, 'interpolation', text='')

        if self.type in {'VCOL', 'IMAGE'}:
            col.prop(self, 'color_option', text='')

        if self.type == 'COLOR_ID':
            col.prop(self, 'color_id', text='')
            if obj.mode == 'EDIT':
                col.prop(self, 'vcol_fill', text='Fill Selected Faces')

        if self.type == 'HEMI':
            col.prop(self, 'hemi_space', text='')

        if self.type == 'EDGE_DETECT':
            col.prop(self, 'edge_detect_radius', text='')

        if self.type == 'AO':
            col.prop(self, 'ao_distance', text='')

        if self.type in {'HEMI', 'EDGE_DETECT', 'AO'}:
            col.prop(self, 'hemi_use_prev_normal')

        if self.type == 'VCOL':
            if is_bl_newer_than(3, 2):
                crow = col.row(align=True)
                crow.prop(self, 'vcol_domain', expand=True)
                crow = col.row(align=True)
                crow.prop(self, 'vcol_data_type', expand=True)

            if obj.mode == 'EDIT' and self.color_option == 'BLACK':
                col.prop(self, 'vcol_fill', text='Fill Selected Faces')

        if self.type == 'IMAGE':
            col.prop(self, 'hdr')

        if self.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER', 'AO'}:
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                crow.prop_search(self, "uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
                if self.type == 'IMAGE':
                    if UDIM.is_udim_supported():
                        col.prop(self, 'use_udim')
                    ccol = col.column()
                    ccol.prop(self, 'use_image_atlas')

        if self.get_to_be_cleared_image_atlas(context, yp):
            col = self.layout.column(align=True)
            col.label(text='INFO: An unused atlas segment can be used.', icon='ERROR')
            col.label(text='It will take a couple seconds to clear.')
        
        if self.type == 'OBJECT_INDEX':
            col.prop(self, 'object_index', text='')

        col.prop(self, 'blend_type', text='')

    def execute(self, context):
        if hasattr(self, 'auto_cancel') and self.auto_cancel: return {'CANCELLED'}

        obj = context.object
        mat = obj.active_material
        ypui = context.window_manager.ypui
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = get_active_layer(yp)

        # Check if object is not a mesh
        if self.type == 'VCOL' and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color mask only works with mesh object!")
            return {'CANCELLED'}

        if not is_bl_newer_than(3, 3) and self.type == 'VCOL' and len(get_vertex_color_names(obj)) >= 8:
            self.report({'ERROR'}, "Mesh can only use 8 vertex colors!")
            return {'CANCELLED'}

        # Clearing unused image atlas segments
        img_atlas = self.get_to_be_cleared_image_atlas(context, yp)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        # Check if layer with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in get_vertex_color_names(obj) if i == self.name]
        else: same_name = [m for m in layer.masks if m.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
                return {'CANCELLED'}
            elif self.type == 'VCOL':
                self.report({'ERROR'}, "Vertex Color named '" + self.name +"' is already available!")
                return {'CANCELLED'}
            elif self.options.is_repeat:
                # Remove the mask before re-adding it on operator repeat
                remove_mask(layer, same_name[0], obj)
            else:
                self.report({'ERROR'}, "Mask named '" + self.name +"' is already available!")
                return {'CANCELLED'}

        alpha = False
        img = None
        vcol = None
        segment = None

        # New image
        if self.type == 'IMAGE':

            if self.color_option == 'WHITE':
                color = (1, 1, 1, 1)
            elif self.color_option == 'BLACK':
                color = (0, 0, 0, 1)

            if self.use_udim:
                objs = get_all_objects_with_same_materials(mat)
                tilenums = UDIM.get_tile_numbers(objs, self.uv_name)

            if self.use_image_atlas:
                if self.use_udim:
                    segment = UDIM.get_set_udim_atlas_segment(tilenums, self.width, self.height, color, get_noncolor_name(), self.hdr, yp)
                else:
                    segment = ImageAtlas.get_set_image_atlas_segment(
                        self.width, self.height, self.color_option, self.hdr, yp=yp
                    )
                img = segment.id_data
            else:

                if self.use_udim:
                    img = bpy.data.images.new(
                        name=self.name, width=self.width, height=self.height, 
                        alpha=alpha, float_buffer=self.hdr, tiled=True
                    )

                    # Fill tiles
                    for tilenum in tilenums:
                        UDIM.fill_tile(img, tilenum, color, self.width, self.height)
                    UDIM.initial_pack_udim(img, color)

                else:
                    img = bpy.data.images.new(
                        name=self.name, width=self.width, height=self.height,
                        alpha=alpha, float_buffer=self.hdr
                    )

                img.generated_color = color
                if hasattr(img, 'use_alpha'):
                    img.use_alpha = False

            if img.colorspace_settings.name != get_noncolor_name() and not img.is_dirty:
                img.colorspace_settings.name = get_noncolor_name()

        # New vertex color
        elif self.type in {'VCOL', 'COLOR_ID'}:

            objs = [obj] if obj.type == 'MESH' else []
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            if self.type == 'VCOL':

                for o in objs:
                    if self.name not in get_vertex_colors(o):
                        if not is_bl_newer_than(3, 3) and len(get_vertex_colors(o)) >= 8: continue
                        vcol = new_vertex_color(o, self.name, self.vcol_data_type, self.vcol_domain)
                        if self.color_option == 'WHITE':
                            set_obj_vertex_colors(o, vcol.name, (1.0, 1.0, 1.0, 1.0))
                        elif self.color_option == 'BLACK':
                            set_obj_vertex_colors(o, vcol.name, (0.0, 0.0, 0.0, 1.0))
                        set_active_vertex_color(o, vcol)

                # Fill selected geometry if in edit mode
                if self.vcol_fill and bpy.context.mode == 'EDIT_MESH' and self.color_option == 'BLACK':
                    bpy.ops.mesh.y_vcol_fill(color_option='WHITE')

            elif self.type == 'COLOR_ID':
                check_colorid_vcol(objs, set_as_active=True)

                # Fill selected geometry if in edit mode
                if self.vcol_fill and bpy.context.mode == 'EDIT_MESH':
                    bpy.ops.mesh.y_vcol_fill_face_custom(color=(self.color_id[0], self.color_id[1], self.color_id[2], 1.0))

        # Voronoi and noise mask will use grayscale value by default
        source_input = 'RGB' if self.type not in {'VORONOI', 'NOISE'} else 'ALPHA'

        # Add new mask
        mask = add_new_mask(
            layer, self.name, self.type, self.texcoord_type, self.uv_name, img, vcol, segment, self.object_index, self.blend_type, 
            self.hemi_space, self.hemi_use_prev_normal, self.color_id, source_input=source_input, edge_detect_radius=self.edge_detect_radius,
            modifier_type=self.modifier_type, interpolation=self.interpolation, ao_distance=self.ao_distance
        )

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL', 'COLOR_ID'}:
            mask.active_edit = True

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(layer.id_data)
        rearrange_yp_nodes(layer.id_data)

        # Update UI
        ypui.layer_ui.expand_masks = True
        if self.type not in {'IMAGE', 'VCOL', 'BACKFACE'}:
            mask.expand_content = True
            mask.expand_source = True
        ypui.need_update = True

        return {'FINISHED'}

class YOpenImageAsMask(bpy.types.Operator, ImportHelper):
    """Open Image as Mask"""
    bl_idname = "wm.y_open_image_as_mask"
    bl_label = "Open Image as Mask"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files = CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory = StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    display_type = EnumProperty(
        items = (
            ('FILE_DEFAULTDISPLAY', 'Default', ''),
            ('FILE_SHORTDISLPAY', 'Short List', ''),
            ('FILE_LONGDISPLAY', 'Long List', ''),
            ('FILE_IMGDISPLAY', 'Thumbnails', '')
        ),
        default = 'FILE_IMGDISPLAY',
        options = {'HIDDEN', 'SKIP_SAVE'}
    )

    relative = BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    interpolation = EnumProperty(
        name = 'Image Interpolation Type',
        description = 'image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    texcoord_type = EnumProperty(
        name = 'Mask Coordinate Type',
        description = 'Mask Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV'
    )

    uv_map = StringProperty(default='')
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 3 if is_bl_newer_than(2, 90) else None,
    )

    source_input = EnumProperty(
        name = 'Source Input',
        description = 'Source data for mask input',
        items = (
            ('RGB', 'Color', ''),
            ('ALPHA', 'Alpha', '')
        ),
        default = 'RGB'
    )

    use_udim_detecting = BoolProperty(
        name = 'Detect UDIMs',
        description = 'Detect selected UDIM files and load all matching tiles.',
        default = True
    )

    file_browser_filepath = StringProperty(default='')

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        node = get_active_ypaint_node()
        return node and len(node.node_tree.yp.layers) > 0

    @classmethod
    def description(self, context, properties):
        return get_operator_description(self)

    def invoke(self, context, event):
        obj = context.object
        if hasattr(context, 'layer'):
            self.layer = context.layer
            yp = self.layer.id_data.yp
        else:
            node = get_active_ypaint_node()
            yp = node.node_tree.yp
            self.layer = yp.layers[yp.active_layer_index]

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:

            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # The default blend type for mask is multiply
        if len(self.layer.masks) == 0:
            self.blend_type = 'MULTIPLY'

        # Default source input is always color for now
        self.source_input = 'RGB'

        # Check if there's height channel and use cubic interpolation if there is one
        height_ch = get_height_channel(self.layer)
        if height_ch and height_ch.enable:
            self.interpolation = 'Cubic'
        elif self.layer.type == 'IMAGE':
            source = get_layer_source(self.layer)
            if source and source.image: self.interpolation = source.interpolation

        if self.file_browser_filepath != '':
            if get_user_preferences().skip_property_popups and not event.shift:
                return self.execute(context)
            return context.window_manager.invoke_props_dialog(self)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        row = self.layout.row()

        col = row.column()
        if self.file_browser_filepath != '':
            col.label(text='Image:')
        col.label(text='Interpolation:')
        col.label(text='Vector:')
        if len(self.layer.masks) > 0:
            col.label(text='Blend:')

        col.label(text='Image Channel:')

        col = row.column()
        if self.file_browser_filepath != '':
            col.label(text=os.path.basename(self.file_browser_filepath), icon='IMAGE_DATA')
        col.prop(self, 'interpolation', text='')
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if len(self.layer.masks) > 0:
            col.prop(self, 'blend_type', text='')

        crow = col.row(align=True)
        crow.prop(self, 'source_input', expand=True)

        layout = col if self.file_browser_filepath != '' else self.layout

        layout.prop(self, 'relative')

        if UDIM.is_udim_supported():
            layout.prop(self, 'use_udim_detecting')

    def execute(self, context):
        T = time.time()
        if not hasattr(self, 'layer'): return {'CANCELLED'}

        layer = self.layer
        yp = layer.id_data.yp
        wm = context.window_manager
        ypui = wm.ypui
        obj = context.object

        if self.file_browser_filepath == '':
            import_list, directory = self.generate_paths()
        else:
            if not os.path.isfile(self.file_browser_filepath):
                self.report({'ERROR'}, "There's no image with address '" + self.file_browser_filepath + "'!")
                return {'CANCELLED'}
            import_list = [os.path.basename(self.file_browser_filepath)]
            directory = os.path.dirname(self.file_browser_filepath)

        if not UDIM.is_udim_supported():
            images = tuple(load_image(path, directory) for path in import_list)
        else:
            ori_ui_type = bpy.context.area.type
            bpy.context.area.type = 'IMAGE_EDITOR'
            images = []
            for path in import_list:
                bpy.ops.image.open(
                    filepath=directory + os.sep + path, directory=directory, 
                    relative_path=self.relative, use_udim_detecting=self.use_udim_detecting
                )
                image = bpy.context.space_data.image
                if image not in images:
                    images.append(image)
            bpy.context.area.type = ori_ui_type

        for image in images:
            if self.relative and bpy.data.filepath != '':
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            if image.colorspace_settings.name != get_noncolor_name() and not image.is_dirty:
                image.colorspace_settings.name = get_noncolor_name()

            # Add new mask
            mask = add_new_mask(
                layer, image.name, 'IMAGE', self.texcoord_type, self.uv_map, image, None, 
                blend_type=self.blend_type, source_input=self.source_input,
                interpolation = self.interpolation
            )

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(layer.id_data)
        rearrange_yp_nodes(layer.id_data)

        # Update UI
        wm.ypui.need_update = True
        wm.ypui.layer_ui.expand_masks = True
        mask.expand_content = True
        mask.expand_vector = True

        print('INFO: Image(s) opened as mask(s) in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

''' Check if data is used as layer, if so, source input will change to ALPHA '''
def update_available_data_name_as_mask(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp

    if self.type == 'IMAGE':
        for layer in yp.layers:
            if layer.type == 'IMAGE':
                source = get_layer_source(layer)
                if source.image and source.image.name == self.image_name:
                    self.source_input = 'ALPHA'
                    return

    elif self.type == 'VCOL' and is_bl_newer_than(2, 92):
        for layer in yp.layers:
            if layer.type == 'VCOL':
                source = get_layer_source(layer)
                if source.attribute_name == self.vcol_name:
                    self.source_input = 'ALPHA'
                    return

    self.source_input = 'RGB'

class YOpenAvailableDataAsMask(bpy.types.Operator):
    bl_idname = "wm.y_open_available_data_as_mask"
    bl_label = "Open available data as Layer Mask"
    bl_description = "Open available data as Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}
    
    type = EnumProperty(
        name = 'Layer Type',
        items = (
            ('IMAGE', 'Image', ''),
            ('VCOL', 'Vertex Color', '')
        ),
        default = 'IMAGE'
    )

    interpolation = EnumProperty(
        name = 'Image Interpolation Type',
        description = 'image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    texcoord_type = EnumProperty(
        name = 'Mask Coordinate Type',
        description = 'Mask Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV'
    )

    source_input = EnumProperty(
        name = 'Source Input',
        description = 'Source data for mask input',
        items = (
            ('RGB', 'Color', ''),
            ('ALPHA', 'Alpha', '')
        ),
        default = 'RGB'
    )

    uv_map = StringProperty(default='')
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    image_name = StringProperty(name="Image", update=update_available_data_name_as_mask)
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name = StringProperty(name="Vertex Color", update=update_available_data_name_as_mask)
    vcol_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 3 if is_bl_newer_than(2, 90) else None,
    )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = get_active_layer(yp)

        self.auto_cancel = False
        if not layer:
            self.auto_cancel = True
            return self.execute(context)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Set the default source input first
        self.source_input = 'RGB'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:

            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        if self.type == 'IMAGE':

            layer_image = None
            if layer.type == 'IMAGE':
                source = get_layer_source(layer)
                layer_image = source.image

            mask_images = []
            for mask in layer.masks:
                if mask.type == 'IMAGE':
                    source = get_mask_source(mask)
                    if source.image:
                        mask_images.append(source.image)

            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            baked_channel_images = get_all_baked_channel_images(layer.id_data)
            for img in imgs:
                if is_image_available_to_open(img) and img not in baked_channel_images and img != layer_image and img not in mask_images:
                    self.image_coll.add().name = img.name

            # Make sure default image is available in the collection and update the source input based on the default name
            if self.image_name not in self.image_coll:
                self.image_name = ''
            else: self.image_name = self.image_name

            # Check if there's height channel and use cubic interpolation if there is one
            height_ch = get_height_channel(layer)
            if height_ch and height_ch.enable:
                self.interpolation = 'Cubic'
            elif layer.type == 'IMAGE':
                source = get_layer_source(layer)
                if source and source.image: self.interpolation = source.interpolation

        elif self.type == 'VCOL':

            layer_vcol_name = None
            if layer.type == 'VCOL':
                source = get_layer_source(layer)
                layer_vcol_name = source.attribute_name

            mask_vcol_names = []
            for mask in layer.masks:
                if mask.type == 'VCOL':
                    source = get_mask_source(mask)
                    mask_vcol_names.append(source.attribute_name)

            self.vcol_coll.clear()
            for vcol_name in get_vertex_color_names(obj):
                if vcol_name != layer_vcol_name and vcol_name not in mask_vcol_names:
                    self.vcol_coll.add().name = vcol_name

            # Make sure default vcol is available in the collection and update the source input based on the default name
            if self.vcol_name not in self.vcol_coll:
                self.vcol_name = ''
            else: self.vcol_name = self.vcol_name

        # The default blend type for mask is multiply
        if len(layer.masks) == 0:
            self.blend_type = 'MULTIPLY'

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = get_active_layer(yp)

        if self.type == 'IMAGE':
            self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        elif self.type == 'VCOL':
            self.layout.prop_search(self, "vcol_name", self, "vcol_coll", icon='GROUP_VCOL')

        row = self.layout.row()

        col = row.column()
        if self.type == 'IMAGE':
            col.label(text='Interpolation:')
            col.label(text='Vector:')

        if len(layer.masks) > 0:
            col.label(text='Blend:')

        if self.type == 'IMAGE':
            col.label(text='Image Channel:')
        elif self.type == 'VCOL' and is_bl_newer_than(2, 92):
            col.label(text='Vertex Color Data:')

        col = row.column()

        if self.type == 'IMAGE':
            col.prop(self, 'interpolation', text='')
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if len(layer.masks) > 0:
            col.prop(self, 'blend_type', text='')

        if is_bl_newer_than(2, 92) or self.type != 'VCOL':
            crow = col.row(align=True)
            crow.prop(self, 'source_input', expand=True)

    def execute(self, context):
        if self.auto_cancel: return {'CANCELLED'}

        obj = context.object
        mat = obj.active_material

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = get_active_layer(yp)
        ypui = context.window_manager.ypui

        if self.type == 'IMAGE' and self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}
        elif self.type == 'VCOL' and self.vcol_name == '':
            self.report({'ERROR'}, "No vertex color selected!")
            return {'CANCELLED'}

        image = None
        vcol = None
        if self.type == 'IMAGE':
            image = bpy.data.images.get(self.image_name)
            name = image.name

            if self.source_input == 'RGB' and image.colorspace_settings.name != get_noncolor_name() and not image.is_dirty:
                image.colorspace_settings.name = get_noncolor_name()
        elif self.type == 'VCOL':
            name = self.vcol_name

            objs = [obj] if obj.type == 'MESH' else []
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            for o in objs:
                if self.vcol_name not in get_vertex_colors(o):
                    if not is_bl_newer_than(3, 3) and len(get_vertex_colors(o)) >= 8: continue
                    data_type, domain = get_vcol_data_type_and_domain_by_name(o, self.vcol_name, objs)
                    other_v = new_vertex_color(o, self.vcol_name, data_type, domain)
                    set_obj_vertex_colors(o, other_v.name, (1.0, 1.0, 1.0, 1.0))
                    set_active_vertex_color(o, other_v)

        # Add new mask
        mask = add_new_mask(
            layer, name, self.type, self.texcoord_type, self.uv_map, image, vcol, 
            blend_type=self.blend_type, source_input=self.source_input,
            interpolation = self.interpolation
        )

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'} and self.source_input == 'RGB':
            mask.active_edit = True

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(layer.id_data)
        rearrange_yp_nodes(layer.id_data)

        # Make sure all layers which used the opened image is using correct linear color
        if self.type == 'IMAGE':
            check_yp_linear_nodes(yp)

        ypui.layer_ui.expand_masks = True
        ypui.need_update = True
        if self.texcoord_type == 'Decal':
            mask.expand_content = True
            mask.expand_vector = True

        return {'FINISHED'}

class YMoveLayerMask(bpy.types.Operator):
    bl_idname = "wm.y_move_layer_mask"
    bl_label = "Move Layer Mask"
    bl_description = "Move layer mask"
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
        return hasattr(context, 'mask') and hasattr(context, 'layer')

    def execute(self, context):
        ypui = context.window_manager.ypui
        mask = context.mask
        layer = context.layer

        num_masks = len(layer.masks)
        if num_masks < 2: return {'CANCELLED'}

        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        index = int(m.group(2))

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_masks-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Remove input props first
        check_layer_tree_ios(layer, remove_props=True)

        # Swap masks
        layer.masks.move(index, new_index)
        swap_mask_fcurves(layer, index, new_index)

        # Dealing with transition bump
        tree = get_tree(layer)
        check_mask_mix_nodes(layer, tree)
        check_mask_source_tree(layer) #, bump_ch)
        #check_mask_image_linear_node(mask)

        # Create input props again
        check_layer_tree_ios(layer)

        # Swap UI expand content
        props = [
            'expand_content',
            'expand_channels',
            'expand_source',
            'expand_vector'
        ]

        for p in props:
            neighbor_prop = getattr(ypui.layer_ui.masks[new_index], p)
            prop = getattr(ypui.layer_ui.masks[index], p)
            setattr(ypui.layer_ui.masks[new_index], p, prop)
            setattr(ypui.layer_ui.masks[index], p, neighbor_prop)

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        return {'FINISHED'}

class YRemoveLayerMask(bpy.types.Operator):
    bl_idname = "wm.y_remove_layer_mask"
    bl_label = "Remove Layer Mask"
    bl_description = "Remove Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        layer = self.layer = context.layer
        mask = self.mask = context.mask

        # Blender 2.7x has no global undo between modes
        self.legacy_on_non_object_mode = not is_bl_newer_than(2, 80) and context.object.mode != 'OBJECT'

        # Check for any dirty images
        self.any_dirty_images = False
        source = get_mask_source(mask)
        image = source.image if mask.type == 'IMAGE' else None
        baked_source = get_mask_source(mask, get_baked=True)

        if (image and image.is_dirty) or (baked_source and baked_source.image and baked_source.image.is_dirty):
            self.any_dirty_images = True

        if self.any_dirty_images or self.legacy_on_non_object_mode:
            return context.window_manager.invoke_props_dialog(self, width=300)

        return self.execute(context)

    def draw(self, context):
        col = self.layout.column(align=True)
        if self.legacy_on_non_object_mode:
            col.label(text='You cannot UNDO this operation in this mode.', icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')
        else:
            col.label(text="Unsaved data will be LOST if you UNDO this operation.", icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')

    def execute(self, context):
        mask = self.mask
        layer = self.layer
        tree = get_tree(layer)
        obj = context.object
        mat = obj.active_material
        yp = layer.id_data.yp

        mask_type = mask.type

        # Remove input props first
        check_layer_tree_ios(layer, remove_props=True)

        remove_mask(layer, mask, obj)

        # Create input props again
        check_all_layer_channel_io_and_nodes(layer, tree)

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(layer.id_data)
        rearrange_yp_nodes(layer.id_data)

        # Seach for active edit mask
        found_active_edit = False
        for m in layer.masks:
            if m.active_edit:
                found_active_edit = True
                break

        # Use layer image as active image if active edit mask not found
        if not found_active_edit:
            #if layer.type == 'IMAGE':
            #    source = get_layer_source(layer, tree)
            #    update_image_editor_image(context, source.image)
            #else:
            #    update_image_editor_image(context, None)
            yp.active_layer_index = yp.active_layer_index

        if mask_type == 'COLOR_ID':

            # Check if color id vcol need to be removed or not
            objs = get_all_objects_with_same_materials(mat)
            if not is_colorid_vcol_still_being_used(objs):
                for o in objs:
                    ovcols = get_vertex_colors(o)
                    vcol = ovcols.get(COLOR_ID_VCOL_NAME)
                    if vcol: ovcols.remove(vcol)

        # Refresh viewport and image editor
        for area in bpy.context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

class YReplaceMaskType(bpy.types.Operator):
    bl_idname = "wm.y_replace_mask_type"
    bl_label = "Replace Mask Type"
    bl_description = "Replace Mask Type"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Layer Type',
        items = mask_type_items,
        default = 'IMAGE'
    )

    modifier_type = EnumProperty(
        name = 'Mask Modifier Type',
        items = MaskModifier.mask_modifier_type_items,
        default = 'INVERT'
    )

    item_name = StringProperty(name="Item")
    item_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    load_item = BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def invoke(self, context, event):
        obj = context.object
        self.mask = context.mask
        if self.load_item and self.type in {'IMAGE', 'VCOL'}:

            self.item_coll.clear()
            self.item_name = ''

            # Update image names
            if self.type == 'IMAGE':
                baked_channel_images = get_all_baked_channel_images(self.mask.id_data)
                for img in bpy.data.images:
                    if not img.yia.is_image_atlas and not img.yua.is_udim_atlas and img not in baked_channel_images:
                        self.item_coll.add().name = img.name
            else:
                for vcol_name in get_vertex_color_names(obj):
                    if vcol_name not in {COLOR_ID_VCOL_NAME}:
                        self.item_coll.add().name = vcol_name

            return context.window_manager.invoke_props_dialog(self)#, width=400)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout

        split = split_layout(layout, 0.35, align=True)

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
        mask = self.mask
        yp = mask.id_data.yp

        if mask.use_temp_bake:
            self.report({'ERROR'}, "Cannot replace temporarily baked mask!")
            return {'CANCELLED'}

        if self.type == mask.type and self.type not in {'IMAGE', 'VCOL', 'MODIFIER'}: return {'CANCELLED'}

        if self.load_item and self.type in {'VCOL', 'IMAGE'} and self.item_name == '':
            self.report({'ERROR'}, "Form is cannot be empty!")
            return {'CANCELLED'}

        replace_mask_type(self.mask, self.type, self.item_name, modifier_type=self.modifier_type)

        print('INFO: Mask ', mask.name, 'is updated in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

        return {'FINISHED'}

class YFixEdgeDetectAO(bpy.types.Operator):
    """Eevee Ambient Occlusion must be enabled to make edge detect mask to work"""
    bl_idname = "wm.y_fix_edge_detect_ao"
    bl_label = "Fix Edge Detect Mask AO"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')

    def execute(self, context):
        bpy.context.scene.eevee.use_gtao = True
        return {'FINISHED'}

def update_mask_active_edit(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    if self.halt_update: return

    # Only image mask can be edited
    #if self.active_edit and self.type not in {'IMAGE', 'VCOL'}:
    #    self.halt_update = True
    #    self.active_edit = False
    #    self.halt_update = False
    #    return

    yp = self.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer_idx = int(match.group(1))
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))

    # Disable other active edits
    if self.active_edit: 
        yp.halt_update = True
        for c in layer.channels:
            c.active_edit = False
            c.active_edit_1 = False

        for m in layer.masks:
            if m == self: continue
            #m.halt_update = True
            m.active_edit = False
            #m.halt_update = False

        yp.halt_update = False

    # Refresh
    yp.active_layer_index = layer_idx

    # Set active subitem
    ListItem.set_active_entity_item(self)

def update_mask_blur_vector(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self
    tree = get_tree(layer)

    if mask.enable_blur_vector:
        blur_vector = new_node(tree, mask, 'blur_vector', 'ShaderNodeGroup', 'Mask Blur Vector')
        blur_vector.node_tree = get_node_tree_lib(lib.BLUR_VECTOR)
        blur_vector.inputs[0].default_value = mask.blur_vector_factor / 100.0
    else:
        remove_node(tree, mask, 'blur_vector')

    check_layer_tree_ios(layer, tree)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)


def update_mask_use_baked(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self
    tree = get_tree(layer)

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    check_all_layer_channel_io_and_nodes(layer)
    check_start_end_root_ch_nodes(self.id_data)

    # Refresh active image by setting active edit
    if mask.active_edit:
        mask.active_edit = True

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    reconnect_yp_nodes(self.id_data)
    rearrange_yp_nodes(self.id_data)

def update_layer_mask_channel_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    ch = layer.channels[int(match.group(3))]
    tree = get_tree(layer)

    check_mask_mix_nodes(layer, tree, mask, ch)
    check_mask_source_tree(layer)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    #mute = not self.enable or not mask.enable or not layer.enable_masks

    #mix = tree.nodes.get(self.mix)
    #if mix:
    #    #if yp.disable_quick_toggle:
    #    #    mix.mute = mute
    #    #else: mix.mute = False
    #    mix.mute = mute

    #dirs = [d for d in neighbor_directions]
    #dirs.extend(['pure', 'remains', 'normal'])

    #for d in dirs:
    #    mix = tree.nodes.get(getattr(self, 'mix_' + d))
    #    if mix: 
    #        #if yp.disable_quick_toggle:
    #        #    mix.mute = mute
    #        #else: mix.mute = False
    #        mix.mute = mute

def update_layer_mask_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    #check_mask_mix_nodes(layer, tree, self)

    check_uv_nodes(yp)
    check_all_layer_channel_io_and_nodes(layer, tree)
    check_start_end_root_ch_nodes(layer.id_data)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    #for ch in self.channels:
    #    update_layer_mask_channel_enable(ch, context)

    reconnect_yp_nodes(self.id_data)
    rearrange_yp_nodes(self.id_data)

    self.active_edit = self.enable and self.type in {'IMAGE', 'VCOL', 'COLOR_ID'}

    # Update list items
    ListItem.refresh_list_items(yp, repoint_active=True)

def update_enable_layer_masks(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    layer = self
    tree = get_tree(layer)

    #for mask in self.masks:
    #    update_layer_mask_enable(mask, context)
    #check_mask_mix_nodes(self)

    check_uv_nodes(yp)
    check_all_layer_channel_io_and_nodes(layer, tree)
    check_start_end_root_ch_nodes(layer.id_data)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    reconnect_yp_nodes(self.id_data)
    rearrange_yp_nodes(self.id_data)

def update_mask_texcoord_type(self, context, reconnect=True):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))
    mask = self
    tree = get_tree(layer)

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    check_all_layer_channel_io_and_nodes(layer, tree)

    # Set image source projection
    if mask.type == 'IMAGE':
        source = get_mask_source(mask)
        source.projection = 'BOX' if mask.texcoord_type in {'Generated', 'Object'} else 'FLAT'

    if reconnect:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        reconnect_yp_nodes(self.id_data)
        rearrange_yp_nodes(self.id_data)

def update_mask_uv_name(self, context):
    obj = context.object
    yp = self.id_data.yp
    ypui = context.window_manager.ypui
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))
    active_layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)
    mask = self

    if mask.type in {'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'AO'} or mask.texcoord_type != 'UV':
        return

    # Cannot use temp uv as standard uv
    if mask.uv_name in {TEMP_UV, ''}:
        if len(yp.uvs) > 0:
            for uv in yp.uvs:
                mask.uv_name = uv.name
                break
    
    # Update uv layer
    if mask.active_edit and obj.type == 'MESH' and layer == active_layer:

        if mask.segment_name != '':
            refresh_temp_uv(obj, mask)
        else:

            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            uv_layers.active = uv_layers.get(mask.uv_name)

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    check_all_layer_channel_io_and_nodes(layer, tree)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    reconnect_yp_nodes(self.id_data)
    rearrange_yp_nodes(self.id_data)

def update_mask_hemi_space(self, context):
    if self.type != 'HEMI': return

    source = get_mask_source(self)
    trans = source.node_tree.nodes.get('Vector Transform')
    if trans: trans.convert_from = self.hemi_space

def update_mask_hemi_use_prev_normal(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    if self.type == 'EDGE_DETECT':
        source = get_mask_source(self)
        setup_edge_detect_source(self, source)

    check_layer_tree_ios(layer, tree)
    check_layer_bump_process(layer, tree)

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    reconnect_yp_nodes(layer.id_data)

def update_mask_hemi_camera_ray_mask(self, context):
    yp = self.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]

    tree = get_mask_tree(self)
    source = get_mask_source(self)

    if source:

        # Check if source has the inputs, if not reload the node
        if 'Camera Ray Mask' not in source.inputs:
            source = replace_new_node(
                tree, self, 'source', 'ShaderNodeGroup', 'Mask Source', 
                lib.HEMI, force_replace=True
            )
            duplicate_lib_node_tree(source)
            trans = source.node_tree.nodes.get('Vector Transform')
            if trans: trans.convert_from = self.hemi_space

            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)

        source.inputs['Camera Ray Mask'].default_value = 1.0 if self.hemi_camera_ray_mask else 0.0

def update_mask_name(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    src = get_mask_source(self)

    # Also update layer name if mask name is renamed in certain pattern
    m = re.match(r'^Mask\s.*\((.+)\)$', self.name)
    if m:
        old_layer_name = layer.name
        new_layer_name = m.group(1)

        yp.halt_update = True
        layer.name = new_layer_name

        # Also update other mask names
        for mask in layer.masks:
            if mask == self: continue
            mm = re.match(r'^Mask\s.*\((.+)\)$', mask.name)
            if mm:
                mask.name = mask.name.replace(mm.group(1), new_layer_name)

        yp.halt_update = False

    if self.type == 'IMAGE' and self.segment_name != '': return
    change_layer_name(yp, context.object, src, self, layer.masks)

def update_mask_blend_type(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)
    mask = self

    #dirs = [d for d in neighbor_directions]
    #dirs.extend(['pure', 'remains', 'normal'])

    #for c in mask.channels:
    #    mix = tree.nodes.get(c.mix)
    #    if mix: mix.blend_type = mask.blend_type
    #    for d in dirs:
    #        mix = tree.nodes.get(getattr(c, 'mix_' + d))
    #        if mix: mix.blend_type = mask.blend_type

    check_mask_mix_nodes(layer, tree, mask)

    # Reconnect nodes
    reconnect_layer_nodes(layer)

    # Rearrange nodes
    rearrange_layer_nodes(layer)

def update_mask_voronoi_feature(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self

    if mask.type != 'VORONOI': return

    source = get_mask_source(mask)
    source.feature = mask.voronoi_feature

    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

def update_mask_object_index(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    source = get_mask_source(self)
    source.inputs[0].default_value = self.object_index

def update_mask_transform(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    update_mapping(self)

def update_mask_edge_detect_radius(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    mask = self

    source = get_mask_source(mask)
    if source: source.inputs[0].default_value = self.edge_detect_radius

def update_mask_source_input(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]

    mask = self
    tree = get_mask_tree(mask)

    if mask.source_input in {'R', 'G', 'B'}:
        check_new_node(tree, mask, 'separate_color_channels', 'ShaderNodeSeparateXYZ', 'Separate Color')
    else:
        remove_node(tree, mask, 'separate_color_channels')

    # Reconnect nodes
    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

class YLayerMaskChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(
        name = 'Enable Mask Channel',
        description = 'Mask will affect this channel',
        default = True, 
        update = update_layer_mask_channel_enable
    )

    # Multiply between mask channels
    mix = StringProperty(default='')

    # Pure mask without any extra multiplier or uv shift, useful for height process
    mix_pure = StringProperty(default='')

    # Remaining masks after chain
    mix_remains = StringProperty(default='')

    # Normal and height has its own alpha if using group, this one is for normal
    mix_normal = StringProperty(default='')

    # To limit mix value to not go above original channel value, useful for group layer
    mix_limit = StringProperty(default='')
    mix_limit_normal = StringProperty(default='')

    # Bump related
    #mix_n = StringProperty(default='')
    #mix_s = StringProperty(default='')
    #mix_e = StringProperty(default='')
    #mix_w = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)

def update_mask_uniform_scale_enabled(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self

    update_entity_uniform_scale_enabled(mask)

    check_layer_tree_ios(layer)
    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

class YLayerMask(bpy.types.PropertyGroup):

    name = StringProperty(default='', update=update_mask_name)

    halt_update = BoolProperty(default=False)
    
    group_node = StringProperty(default='')

    enable = BoolProperty(
        name = 'Enable Mask', 
        description = 'Enable mask',
        default = True,
        update = update_layer_mask_enable
    )

    active_edit = BoolProperty(
        name = 'Active mask for editing or preview', 
        description = 'Active mask for editing or preview', 
        default = False,
        update = update_mask_active_edit
    )

    source_input = EnumProperty(
        name = 'Mask Source Input',
        description = 'Source input for mask',
        items = entity_input_items,
        update = update_mask_source_input
    )

    #active_vcol_edit = BoolProperty(
    #        name='Active vertex color for editing', 
    #        description='Active vertex color for editing', 
    #        default=False,
    #        update=update_mask_active_vcol_edit)

    type = EnumProperty(
        name = 'Mask Type',
        items = mask_type_items,
        default = 'IMAGE'
    )

    texcoord_type = EnumProperty(
        name = 'Mask Coordinate Type',
        description = 'Mask Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV',
        # Using a lambda because update function is expected to have an arity of 2
        update = lambda self, context:
            update_mask_texcoord_type(self, context)
    )

    original_texcoord = EnumProperty(
        name = 'Original Layer Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV'
    )

    original_image_extension = StringProperty(
        name = 'Original Image Extension Type',
        default = ''
    )

    modifier_type = EnumProperty(
        name = 'Mask Modifier Type',
        items = MaskModifier.mask_modifier_type_items,
        default = 'INVERT'
    )

    hemi_space = EnumProperty(
        name = 'Fake Lighting Space',
        description = 'Fake lighting space',
        items = hemi_space_items,
        default = 'OBJECT',
        update = update_mask_hemi_space
    )

    hemi_camera_ray_mask = BoolProperty(
        name = 'Camera Ray Mask',
        description = "Use Camera Ray value so the back of the mesh won't be affected by fake lighting",
        default = False,
        update = update_mask_hemi_camera_ray_mask
    )

    hemi_use_prev_normal = BoolProperty(
        name = 'Use previous Normal',
        description = 'Take account previous Normal',
        default = False,
        update = update_mask_hemi_use_prev_normal
    )

    uv_name = StringProperty(
        name = 'UV Name',
        description = 'UV Name to use for mask coordinate',
        default = '',
        update = update_mask_uv_name
    )

    baked_uv_name = StringProperty(
        name = 'Baked UV Name',
        description = 'UV Name to use for baked mask coordinate',
        default = ''
    )

    blend_type = EnumProperty(
        name = 'Blend',
        items = mask_blend_type_items,
        default = 3 if is_bl_newer_than(2, 90) else None,
        update = update_mask_blend_type
    )

    intensity_value = FloatProperty(
        name = 'Mask Opacity', 
        description = 'Mask opacity',
        subtype = 'FACTOR',
        default=1.0, min=0.0, max=1.0, precision=3
    )

    # Transform
    translation = FloatVectorProperty(
        name = 'Translation',
        size = 3,
        precision = 3, 
        default = (0.0, 0.0, 0.0),
        update = update_mask_transform
    )

    rotation = FloatVectorProperty(
        name = 'Rotation',
        subtype = 'AXISANGLE',
        size = 3,
        precision = 3,
        unit = 'ROTATION',
        default = (0.0, 0.0, 0.0),
        update = update_mask_transform
    )

    scale = FloatVectorProperty(
        name = 'Scale',
        size = 3,
        precision = 3, 
        default = (1.0, 1.0, 1.0),
        update = update_mask_transform,
    )

    enable_blur_vector = BoolProperty(
        name = 'Enable Blur Vector',
        description = "Enable blur vector",
        default = False,
        update = update_mask_blur_vector
    )

    blur_vector_factor = FloatProperty(
        name = 'Blur Vector Factor', 
        description = 'Mask Intensity Factor',
        default=1.0, min=0.0, max=100.0, precision=3
    )

    decal_distance_value = FloatProperty(
        name = 'Decal Distance',
        description = 'Distance between surface and the decal object',
        min=0.0, max=100.0, default=0.5, precision=3
    )

    color_id = FloatVectorProperty(
        name = 'Color ID',
        size = 3,
        subtype = 'COLOR',
        default=(1.0, 0.0, 1.0), min=0.0, max=1.0,
    )

    use_baked = BoolProperty(
        name = 'Use Baked',
        description = 'Use baked image rather generated mask',
        default = False,
        update = update_mask_use_baked
    )

    segment_name = StringProperty(default='')
    baked_segment_name = StringProperty(default='')

    channels = CollectionProperty(type=YLayerMaskChannel)

    modifiers = CollectionProperty(type=MaskModifier.YMaskModifier)

    # For object index
    object_index = IntProperty(
        name = 'Object Index',
        description = 'Object Pass Index',
        default=0, min=0,
        update = update_mask_object_index
    )

    # For temporary bake
    use_temp_bake = BoolProperty(
        name = 'Use Temporary Bake',
        description = 'Use temporary bake, it can be useful to prevent glitching with cycles',
        default = False,
    )

    original_type = EnumProperty(
        name = 'Original Mask Type',
        items = mask_type_items,
        default = 'IMAGE'
    )

    # For fake lighting

    hemi_vector = FloatVectorProperty(
        name = 'Cache Hemi vector',
        size = 3,
        precision = 3,
        default = (0.0, 0.0, 1.0)
    )

    # For edge detection
    edge_detect_radius = FloatProperty(
        name = 'Edge Detect Radius',
        description = 'Edge detect radius',
        default=0.05, min=0.0, max=10.0,
        update = update_mask_edge_detect_radius
    )

    # For AO
    ao_distance = FloatProperty(
        name = 'Ambient Occlusion Distance',
        description = 'Ambient occlusion distance',
        default=1.0, min=0.0, max=10.0
    )

    # Specific for voronoi
    voronoi_feature = EnumProperty(
        name = 'Voronoi Feature',
        description = 'The voronoi feature that will be used for compute',
        items = voronoi_feature_items,
        default = 'F1',
        update = update_mask_voronoi_feature
    )

    # Nodes
    source = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')

    baked_source = StringProperty(default='')

    # Mask type cache
    cache_brick = StringProperty(default='')
    cache_checker = StringProperty(default='')
    cache_gradient = StringProperty(default='')
    cache_magic = StringProperty(default='')
    cache_musgrave = StringProperty(default='')
    cache_noise = StringProperty(default='')
    cache_gabor = StringProperty(default='')
    cache_voronoi = StringProperty(default='')
    cache_wave = StringProperty(default='')
    cache_color = StringProperty(default='')

    cache_image = StringProperty(default='')
    cache_vcol = StringProperty(default='')
    cache_hemi = StringProperty(default='')

    cache_modifier_ramp = StringProperty(default='')
    cache_modifier_curve = StringProperty(default='')

    uv_map = StringProperty(default='')
    uv_neighbor = StringProperty(default='')
    mapping = StringProperty(default='')
    baked_mapping = StringProperty(default='')
    blur_vector = StringProperty(default='')
    separate_color_channels = StringProperty(default='')

    enable_uniform_scale = BoolProperty(
        name = 'Enable Uniform Scale', 
        description = 'Use the same value for all scale components',
        default = False,
        update = update_mask_uniform_scale_enabled
    )

    uniform_scale_value = FloatProperty(default=1)

    decal_process = StringProperty(default='')
    texcoord = StringProperty(default='')
    decal_alpha = StringProperty(default='')
    decal_alpha_n = StringProperty(default='')
    decal_alpha_s = StringProperty(default='')
    decal_alpha_e = StringProperty(default='')
    decal_alpha_w = StringProperty(default='')

    linear = StringProperty(default='')

    # Only useful for merging mask for now
    mix = StringProperty(default='')

    need_temp_uv_refresh = BoolProperty(default=False)

    tangent = StringProperty(default='')
    bitangent = StringProperty(default='')
    tangent_flip = StringProperty(default='')
    bitangent_flip = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_channels = BoolProperty(default=False)
    expand_source = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)

def register():
    bpy.utils.register_class(YNewLayerMask)
    bpy.utils.register_class(YOpenImageAsMask)
    bpy.utils.register_class(YOpenAvailableDataAsMask)
    bpy.utils.register_class(YMoveLayerMask)
    bpy.utils.register_class(YRemoveLayerMask)
    bpy.utils.register_class(YReplaceMaskType)
    bpy.utils.register_class(YFixEdgeDetectAO)
    bpy.utils.register_class(YLayerMaskChannel)
    bpy.utils.register_class(YLayerMask)

def unregister():
    bpy.utils.unregister_class(YNewLayerMask)
    bpy.utils.unregister_class(YOpenImageAsMask)
    bpy.utils.unregister_class(YOpenAvailableDataAsMask)
    bpy.utils.unregister_class(YMoveLayerMask)
    bpy.utils.unregister_class(YRemoveLayerMask)
    bpy.utils.unregister_class(YReplaceMaskType)
    bpy.utils.unregister_class(YFixEdgeDetectAO)
    bpy.utils.unregister_class(YLayerMaskChannel)
    bpy.utils.unregister_class(YLayerMask)
