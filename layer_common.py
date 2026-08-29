import bpy
from .common import *
from .node_arrangements import *
from .node_connections import *
from . import ListItem, subtree, input_outputs, mask_common, lib, UDIM, ImageAtlas, Decal, modifier_common

def get_normal_map_type_items(self, context):
    items = []

    if is_bl_newer_than(2, 80):
        items.append(('BUMP_MAP', 'Bump Map', ''))
        items.append(('NORMAL_MAP', 'Normal Map', ''))
        items.append(('BUMP_NORMAL_MAP', 'Bump + Normal Map', ''))
        items.append(('VECTOR_DISPLACEMENT_MAP', 'Vector Displacement Map', ''))
    else: 
        items.append(('BUMP_MAP', 'Bump Map', '', 'MATCAP_09', 0))
        items.append(('NORMAL_MAP', 'Normal Map', '', 'MATCAP_23', 1))
        items.append(('BUMP_NORMAL_MAP', 'Bump + Normal Map', '', 'MATCAP_23', 2))
        items.append(('VECTOR_DISPLACEMENT_MAP', 'Vector Displacement Map', '', 'MATCAP_23', 3))

    return items

def check_layer_source(layer, tree=None, image=None, vcol=None, setup_edge_detect=True):
    if tree == None or layer.source_group != '': tree = get_source_tree(layer)

    # Add source
    if layer.type == 'VCOL':
        source, dirty = check_new_node(tree, layer, 'source', get_vcol_bl_idname(), 'Source', True)
    else: source, dirty = check_new_node(tree, layer, 'source', layer_node_bl_idnames[layer.type], 'Source', True)

    if dirty:
        if layer.type == 'IMAGE':
            # Always set non color to image node because of linear pipeline
            #if hasattr(source, 'color_space'):
            #    source.color_space = 'NONE'

            # Add default image if it's image layer
            if not image: image = bpy.data.images.new(layer.name)

            # Set image to source
            source.image = image

        elif layer.type == 'VCOL':
            if vcol: set_source_vcol_name(source, vcol.name)
            else: set_source_vcol_name(source, layer.name)

        elif layer.type == 'HEMI':
            source.node_tree = get_node_tree_lib(lib.HEMI)
            duplicate_lib_node_tree(source)
            load_hemi_props(layer, source)

        elif layer.type == 'EDGE_DETECT':
            if setup_edge_detect:
                lib.setup_edge_detect_source(layer, source)

        elif layer.type == 'AO':
            enable_eevee_ao()

    return source

def check_layer_projection_blends(layer):

    if layer.type == 'IMAGE':
        source = get_layer_source(layer)
        if hasattr(source, 'projection_blend'):
            source.projection_blend = layer.projection_blend

    for ch in layer.channels:
        if ch.override and ch.override_type == 'IMAGE':
            source = get_channel_source(ch, layer)
            if hasattr(source, 'projection_blend'):
                source.projection_blend = layer.projection_blend

        if ch.override_1 and ch.override_1_type == 'IMAGE':
            source = get_channel_source_1(ch, layer)
            if hasattr(source, 'projection_blend'):
                source.projection_blend = layer.projection_blend

def check_layer_projections(layer):
    # Set image source projection
    if layer.type == 'IMAGE':
        source = get_layer_source(layer)
        source.projection = 'BOX' if layer.texcoord_type in {'Generated', 'Object'} else 'FLAT'

    # Set channel override images
    for ch in layer.channels:
        if ch.override and ch.override_type == 'IMAGE':
            source = get_channel_source(ch, layer)
            source.projection = 'BOX' if layer.texcoord_type in {'Generated', 'Object'} else 'FLAT'

        if ch.override_1 and ch.override_1_type == 'IMAGE':
            source = get_channel_source_1(ch, layer)
            source.projection = 'BOX' if layer.texcoord_type in {'Generated', 'Object'} else 'FLAT'

    # Check projection blends
    check_layer_projection_blends(layer)

def get_socket_type_from_socket(soc):
    return soc.type if soc.type != 'VALUE' else 'FLOAT'

def create_new_combine_bundle_node(mat, yp_node, layer, source=None):
    yp = yp_node.node_tree.yp

    comb = mat.node_tree.nodes.new('NodeCombineBundle')
    comb.label = layer.name
    comb.location.x = yp_node.location.x #- 180
    comb.location.y = yp_node.location.y - yp_node.dimensions.y - 40

    # NOTE: Node connection can trigger sync, since it's not necessary right now, so enable halt update
    ori_halt_update = yp.halt_update
    yp.halt_update = True
    mat.node_tree.links.new(comb.outputs[0], yp_node.inputs[layer.name])
    yp.halt_update = ori_halt_update

    # Copy items from source
    if source and source.type == 'NodeSeparateBundle':
        for outp in source.outputs:
            if outp.name == '': continue
            socket_type = get_socket_type_from_socket(outp)
            soc = comb.bundle_items.new(socket_type=socket_type, name=outp.name)

def check_and_connect_combine_bundle_node(mat, yp_node, layer):
    inp = yp_node.inputs.get(layer.name)
    if inp and len(inp.links) == 0:
        comb = None
        combs = [n for n in mat.node_tree.nodes if n.label == layer.name]
        for c in combs:
            if c and c.type == 'NodeCombineBundle' and len(c.outputs[0].links) == 0:
                comb = c
        if comb == None: 
            source = get_layer_source(layer)
            comb = create_new_combine_bundle_node(mat, yp_node, layer, source=source)

        if comb:
            mat.node_tree.links.new(comb.outputs[0], inp)

def add_new_layer(
        group_tree, layer_name, layer_type, channel_idx, 
        blend_type, normal_blend_type, normal_map_type, 
        texcoord_type, uv_name='', image=None, vcol=None, segment=None,
        solid_color=(1, 1, 1),
        add_mask=False, mask_type='IMAGE', mask_image=None, mask_segment=None, mask_image_filepath='', mask_relative=True,
        mask_texcoord_type='UV', mask_color='BLACK', mask_use_hdr=False, 
        mask_uv_name='', mask_width=1024, mask_height=1024, use_image_atlas_for_mask=False,
        hemi_space='WORLD', hemi_use_prev_normal=True,
        mask_color_id=(1, 0, 1), mask_vcol_fill=True,
        mask_vcol_data_type='BYTE_COLOR', mask_vcol_domain='CORNER',
        use_divider_alpha=False, use_udim_for_mask=False,
        interpolation='Linear', mask_interpolation='Linear', mask_edge_detect_radius=0.05, mask_edge_detect_method='CROSS',
        normal_space = 'TANGENT', edge_detect_radius=0.05, edge_detect_method='CROSS', mask_use_prev_normal=True,
        ao_distance=1.0, height_blend_type='MIX',
        enable=True,
        use_designated_idx = False, designated_index = -1, designated_parent_idx = -1,
        add_modifier=False, modifier_type='RGB_CURVE',
    ):

    yp = group_tree.yp
    ypup = get_user_preferences()
    obj = bpy.context.object
    mat = obj.active_material

    # Halt rearrangements and reconnections until all nodes already created
    yp.halt_reconnect = True
    #yp.halt_update = True

    # Get parent and index dict
    parent_dict = get_parent_dict(yp)
    index_dict = get_index_dict(yp)

    parent_layer = None
    active_layer_is_group = False
    if use_designated_idx:
        # Use designated parent if it's set
        if designated_parent_idx != -1:
            try: parent_layer = yp.layers[designated_parent_idx]
            except: parent_layer = None
    else:
        # Get active layer
        try: active_layer = yp.layers[yp.active_layer_index]
        except: active_layer = None

        # Get a possible parent layer group
        if active_layer:
            if active_layer.type == 'GROUP':
                parent_layer = active_layer
                active_layer_is_group = True
            elif active_layer.parent_idx != -1:
                parent_layer = yp.layers[active_layer.parent_idx]

    # Get parent index
    if parent_layer != None: 
        parent_idx = get_layer_index(parent_layer)
        has_parent = True
    else: 
        parent_idx = -1
        has_parent = False

    # Add layer to group
    layer = yp.layers.add()
    layer.type = layer_type
    layer.enable = enable

    # Set layer name
    if layer_type == 'INPUT_BUNDLE':
        layer_name = get_unique_name(layer_name, get_tree_inputs(yp.id_data))
    layer.name = get_unique_name(layer_name, yp.layers)
    layer.original_name = layer.name

    # Set default uv name if it's an empty string
    if uv_name == '':
        uv_name = get_default_uv_name()

    layer.uv_name = uv_name
    check_uvmap_on_other_objects_with_same_mat(mat, uv_name)

    if segment:
        layer.segment_name = segment.name

    if image:
        layer.image_name = image.name

    # Move new layer to current index
    last_index = len(yp.layers)-1

    if use_designated_idx and designated_index != -1:
        # Use designated index if it's set
        index = designated_index
    else:
        if active_layer_is_group:
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

    # Uniform Scale
    if is_bl_newer_than(2, 81) and is_layer_using_vector(layer):
        layer.enable_uniform_scale = ypup.enable_uniform_uv_scale_by_default

    # Add source
    source = check_layer_source(layer, tree, image, vcol, setup_edge_detect=False)

    # Set some props
    if layer_type == 'IMAGE':
        # Set interpolation
        source.interpolation = interpolation

    elif layer_type == 'COLOR':
        col = (solid_color[0], solid_color[1], solid_color[2], 1.0)
        source.outputs[0].default_value = col

    elif layer_type == 'HEMI':
        layer.hemi_space = hemi_space
        layer.hemi_use_prev_normal = hemi_use_prev_normal

    elif layer_type == 'EDGE_DETECT':
        layer.hemi_use_prev_normal = hemi_use_prev_normal
        # Edge detect setup happens here
        lib.setup_edge_detect_source(layer, source, edge_detect_radius, edge_detect_method)

    elif layer_type == 'AO':
        layer.hemi_use_prev_normal = hemi_use_prev_normal
        layer.ao_distance = ao_distance

    # Add texcoord node
    #texcoord = new_node(tree, layer, 'texcoord', 'NodeGroupInput', 'TexCoord Inputs')

    # Add mapping node
    if is_mapping_possible(layer.type):
        mapping = new_node(tree, layer, 'mapping', 'ShaderNodeMapping', 'Mapping')
        mapping.vector_type = 'POINT' #if segment else 'TEXTURE'

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
        ignore_image_names = True if mask_segment else False
        mask_name = mask_common.get_new_mask_name(obj, layer, mask_type, ignore_images=ignore_image_names)
        mask_vcol_name = ''

        if not mask_image and mask_type == 'IMAGE':
            if not mask_image_filepath:
                color = (0, 0, 0, 0)
                if mask_color == 'WHITE':
                    color = (1, 1, 1, 1)
                elif mask_color == 'BLACK':
                    color = (0, 0, 0, 1)

                if use_udim_for_mask:
                    objs = get_all_objects_with_same_materials(mat)
                    tilenums = UDIM.get_tile_numbers(objs, mask_uv_name)

                if use_image_atlas_for_mask:
                    if use_udim_for_mask:
                        mask_segment = UDIM.get_set_udim_atlas_segment(
                            tilenums, mask_width, mask_height, color,
                            colorspace=get_noncolor_name(), hdr=mask_use_hdr, yp=yp
                        )
                    else:
                        mask_segment = ImageAtlas.get_set_image_atlas_segment(
                            mask_width, mask_height, mask_color, mask_use_hdr, yp=yp
                        )
                    mask_image = mask_segment.id_data
                else:
                    if use_udim_for_mask:
                        mask_image = bpy.data.images.new(
                            mask_name, width=mask_width, height=mask_height,
                            alpha=False, float_buffer=mask_use_hdr, tiled=True
                        )

                        # Fill tiles
                        for tilenum in tilenums:
                            UDIM.fill_tile(mask_image, tilenum, color, mask_width, mask_height)
                        UDIM.initial_pack_udim(mask_image, color)

                    else:
                        mask_image = bpy.data.images.new(
                            mask_name, width=mask_width, height=mask_height,
                            alpha=False, float_buffer=mask_use_hdr
                        )

                    mask_image.generated_color = color
                    if hasattr(mask_image, 'use_alpha'):
                        mask_image.use_alpha = False
            else:
                if not os.path.isfile(mask_image_filepath):
                    print("There's no image with address '" + mask_image_filepath + "'!")
                    return {'CANCELLED'}

                path = os.path.basename(mask_image_filepath)
                directory = os.path.dirname(mask_image_filepath)

                mask_image = load_image(path, directory)

                if mask_relative and bpy.data.filepath != '':
                    try: mask_image.filepath = bpy.path.relpath(mask_image.filepath)
                    except: pass

            if mask_image.colorspace_settings.name != get_noncolor_name() and not mask_image.is_dirty:
                mask_image.colorspace_settings.name = get_noncolor_name()

        # New vertex color
        elif mask_type in {'VCOL', 'COLOR_ID'}:
            objs = [obj] if obj.type == 'MESH' else []
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            if mask_type == 'VCOL':

                for o in objs:
                    if mask_name not in get_vertex_colors(o):
                        if not is_bl_newer_than(3, 3) and len(get_vertex_colors(o)) >= 8: continue

                        color = ()
                        if mask_color == 'WHITE': color = (1.0, 1.0, 1.0, 1.0) 
                        elif mask_color == 'BLACK': color = (0.0, 0.0, 0.0, 1.0)

                        mask_vcol = new_vertex_color(o, mask_name, mask_vcol_data_type, mask_vcol_domain, color_fill=color)
                        set_active_vertex_color(o, mask_vcol)
                        mask_vcol_name = mask_vcol.name

                # Fill selected geometry if in edit mode
                if mask_vcol_fill and bpy.context.mode == 'EDIT_MESH':
                    bpy.ops.mesh.y_vcol_fill(color_option='WHITE')

            elif mask_type == 'COLOR_ID':
                check_colorid_vcol(objs, set_as_active=True)

                # Fill selected geometry if in edit mode
                if mask_vcol_fill and bpy.context.mode == 'EDIT_MESH':
                    bpy.ops.mesh.y_vcol_fill_face_custom(color=(mask_color_id[0], mask_color_id[1], mask_color_id[2], 1.0))

        mask = mask_common.add_new_mask(
            layer, mask_name, mask_type, mask_texcoord_type, mask_uv_name, 
            image=mask_image, vcol_name=mask_vcol_name, segment=mask_segment,
            interpolation = mask_interpolation,
            color_id = mask_color_id,
            edge_detect_radius = mask_edge_detect_radius,
            edge_detect_method = mask_edge_detect_method,
            hemi_use_prev_normal = mask_use_prev_normal
        )
        mask.active_edit = True

    # Fill channel layer props
    shortcut_created = False
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        # Set some props to selected channel
        if layer.type in {'GROUP', 'BACKGROUND'} or channel_idx == i or channel_idx == -1:
            ch.enable = True
            if root_ch.special_type == 'NORMAL':
                ch.normal_blend_type = normal_blend_type
                ch.normal_space = normal_space
            if root_ch.special_type == 'HEIGHT':
                ch.height_blend_type = height_blend_type
            else:
                ch.blend_type = blend_type
        else: 
            ch.enable = False

        if root_ch.special_type == 'NORMAL':
            # Set default override color for normal
            ch.override_color = (0.5, 0.5, 1.0)

        if root_ch.special_type == 'VDISP':
            # Flip YZ is no longer enabled by default for faster calculation
            ch.vdisp_enable_flip_yz = False

        # Set linear node of layer channel
        subtree.check_layer_channel_linear_node(ch, layer, root_ch)

    # Add modifier
    if add_modifier:
        modifier_common.add_new_modifier(layer, modifier_type)

    # Check uv maps
    subtree.check_uv_nodes(yp)

    # Check image projections
    check_layer_projections(layer)

    # Check and create layer channel nodes
    #input_outputs.check_all_layer_channel_io_and_nodes(layer, tree) #, has_parent=has_parent)

    # Refresh paint image by updating the index
    yp.active_layer_index = index

    # Unhalt rearrangements and reconnections since all nodes already created
    yp.halt_reconnect = False
    #yp.halt_update = False

    # Check layer IO
    input_outputs.check_all_layer_channel_io_and_nodes(layer, tree)
    input_outputs.check_start_end_root_ch_nodes(group_tree)

    if layer.type == 'INPUT_BUNDLE':
        # Create node input
        input_outputs.check_all_channel_ios(yp, reconnect=False, specific_layer=layer)

        # Add source socket items based on channels
        source = get_layer_source(layer)
        for i, c in enumerate(yp.channels):
            socket_type = 'FLOAT'
            if c.type == 'RGB':
                socket_type = 'RGBA'
            elif c.type == 'VECTOR':
                socket_type = 'VECTOR'
            outp = source.bundle_items.new(socket_type=socket_type, name=c.name)

            # NOTE: Only first channel is used for now
            if i == 0:
                break

        # Create combine bundle node
        yp_nodes = [n for n in mat.node_tree.nodes if n.type == 'GROUP' and n.node_tree==group_tree]
        comb = None
        if yp_nodes:
            yp_node = yp_nodes[0]
            comb = create_new_combine_bundle_node(mat, yp_node, layer, source=source)

    # Rearrange node inside layers
    reconnect_layer_nodes(layer)
    rearrange_layer_nodes(layer)

    # Make sure new parent subitems is expanded
    if layer.parent_idx != -1:
        parent = yp.layers[layer.parent_idx]
        if not parent.expand_subitems:
            parent.expand_subitems = True

    # Update list items
    ListItem.refresh_list_items(yp)

    return layer

def replace_layer_type(layer, new_type, item_name='', remove_data=False):

    yp = layer.id_data.yp

    # Remember parents
    parent_dict = get_parent_dict(yp)
    child_ids = []

    # If layer type is group, get children and repoint child parents
    if layer.type == 'GROUP':
        # Get children and repoint child parents
        child_ids = get_list_of_direct_child_ids(layer)
        for i in child_ids:
            parent_dict[yp.layers[i].name] = parent_dict[layer.name]

    # Check if layer is using image atlas
    if layer.type == 'IMAGE' and layer.segment_name != '':

        # Replace to non atlas image will remove the segment
        if new_type == 'IMAGE':
            src = get_layer_source(layer)
            if src.image.yia.is_image_atlas:
                segment = src.image.yia.segments.get(layer.segment_name)
                segment.unused = True
            elif src.image.yua.is_udim_atlas:
                UDIM.remove_udim_atlas_segment_by_name(src.image, layer.segment_name, yp=yp)

            # Set segment name to empty
            layer.segment_name = ''

        # Reset mapping
        clear_mapping(layer)

    # Save hemi vector
    if layer.type == 'HEMI':
        src = get_layer_source(layer)
        save_hemi_props(layer, src)

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
    tree = get_tree(layer)
    source_tree = get_source_tree(layer)
    source = source_tree.nodes.get(layer.source)

    # Save source to cache
    if layer.type not in {'BACKGROUND', 'GROUP', 'HEMI', 'EDGE_DETECT', 'AO', 'PREV_LAYERS'} and layer.type != new_type:
        setattr(layer, 'cache_' + layer.type.lower(), source.name)
        # Remove uv input link
        if any(source.inputs) and any(source.inputs[0].links):
            tree.links.remove(source.inputs[0].links[0])
        source.label = ''
    else:
        remove_node(source_tree, layer, 'source', remove_data=remove_data)

    # Try to get available cache
    cache = None
    if new_type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'GROUP', 'HEMI', 'EDGE_DETECT', 'AO', 'PREV_LAYERS'} or (new_type in {'IMAGE', 'VCOL'} and item_name == ''):
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

            check_layer_projections(layer)

            if layer.texcoord_type == 'Decal':
                source.extension = 'CLIP'

        elif new_type == 'VCOL':
            set_source_vcol_name(source, item_name)
        elif new_type == 'HEMI':
            source.node_tree = get_node_tree_lib(lib.HEMI)
            duplicate_lib_node_tree(source)

            load_hemi_props(layer, source)

        elif new_type == 'EDGE_DETECT':
            lib.setup_edge_detect_source(layer, source)

        elif new_type == 'AO':
            enable_eevee_ao()

    # Change layer type
    ori_type = layer.type
    layer.type = new_type

    # Check modifiers tree
    modifier_common.check_layer_modifier_tree(layer)

    # Always remove baked layer when changing type
    if layer.use_baked:
        layer.use_baked = False
        remove_node(tree, layer, 'baked_source')

    # Update group ios
    input_outputs.check_all_layer_channel_io_and_nodes(layer, tree)
    if layer.type == 'BACKGROUND':
        # Remove bump and its base
        for ch in layer.channels:
            #remove_node(tree, ch, 'bump_base')
            #remove_node(tree, ch, 'bump')
            remove_node(tree, ch, 'normal_process')

    # Update linear stuff
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        subtree.check_layer_channel_linear_node(ch, layer, root_ch)

    # Back to use fine bump if conversion happen
    for ch in fine_bump_channels:
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
    subtree.check_uv_nodes(yp)

    # Update layer name
    image = None
    if layer.type == 'IMAGE':
        # Rename layer with image name
        source = get_layer_source(layer)
        if source and source.image:
            image = source.image
            yp.halt_update = True
            if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                mat = get_active_material()
                new_name = mat.name if mat else 'Image'
                new_name += DEFAULT_NEW_IMG_SUFFIX

                # Set back the mapping
                if image.yia.is_image_atlas:
                    segment = image.yia.segments.get(layer.segment_name)
                    ImageAtlas.set_segment_mapping(layer, segment, image)
                else:
                    segment = image.yua.segments.get(layer.segment_name)
                    UDIM.set_udim_segment_mapping(layer, segment, image)

            else: new_name = image.name
            layer.name = get_unique_name(new_name, yp.layers)
            yp.halt_update = False

            # Set interpolation to Cubic if normal/height channel is found
            height_ch = get_height_channel(layer)
            if height_ch and height_ch.enable:
                source.interpolation = 'Cubic'

    elif layer.type == 'VCOL':
        # Rename layer with vcol name
        source = get_layer_source(layer)
        if source: layer.name = get_unique_name(source.attribute_name, yp.layers)

        # Set active vertex color
        set_active_vertex_color_by_name(bpy.context.object, source.attribute_name)

    elif ori_type in {'IMAGE', 'VCOL'}:
        # Rename layer with texture types
        layer.name = get_unique_name(layer_type_labels[layer.type], yp.layers)

    elif layer_type_labels[ori_type] in layer.name:  
        # Rename texture types with another texture types
        layer.name = get_unique_name(layer.name.replace(layer_type_labels[ori_type], layer_type_labels[layer.type]), yp.layers)

    # Refresh colorspace
    for root_ch in yp.channels:
        if root_ch.type == 'RGB':
            root_ch.colorspace = root_ch.colorspace

    # Check children which need rearrange
    for lay in yp.layers:
        input_outputs.check_all_layer_channel_io_and_nodes(lay)
        reconnect_layer_nodes(lay)
        rearrange_layer_nodes(lay)

    if layer.type in {'BACKGROUND', 'GROUP'} or ori_type == 'GROUP':
        reconnect_yp_nodes(layer.id_data)
        rearrange_yp_nodes(layer.id_data)

    # Reconnect combine bundle
    if layer.type == 'INPUT_BUNDLE':
        mats = get_all_materials_with_yp_nodes(specific_yp=yp)
        for mat in mats:
            yp_nodes = get_nodes_using_yp(mat, yp)
            for yp_node in yp_nodes:
                check_and_connect_combine_bundle_node(mat, yp_node, layer)

    # Update UI
    bpy.context.window_manager.ypui.need_update = True
    layer.expand_source = layer.type not in {'IMAGE', 'VCOL'} or (image != None and image.y_bake_info.is_baked and not image.y_bake_info.is_baked_channel)

def remove_layer(yp, index, remove_on_disk=False):
    group_tree = yp.id_data
    obj = bpy.context.object
    layer = yp.layers[index]
    layer_tree = get_tree(layer)
    mat = obj.active_material
    wm = bpy.context.window_manager

    # Dealing with decal object
    Decal.remove_decal_object(layer_tree, layer)

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
    remove_node(source_tree, layer, 'source', remove_on_disk=remove_on_disk)

    # Remove combine bundle node
    if layer.type == 'INPUT_BUNDLE':
        yp_nodes = [n for n in mat.node_tree.nodes if n.type == 'GROUP' and n.node_tree==group_tree]
        if yp_nodes:
            yp_node = yp_nodes[0]
            inp = yp_node.inputs.get(layer.name)
            if inp and len(inp.links) > 0:
                n = inp.links[0].from_node
                if n and n.type == 'NodeCombineBundle':
                    simple_remove_node(mat.node_tree, n)

    # Remove input layer socket
    if layer.type.startswith('INPUT_'):
        inp = get_tree_input_by_name(group_tree, layer.name)
        if inp: remove_tree_input(group_tree, inp)

    # Remove baked source
    baked_source = get_layer_source(layer, get_baked=True)
    if baked_source:
        remove_node(source_tree, layer, 'baked_source', remove_on_disk=remove_on_disk)

    # Remove channel source
    for ch in layer.channels:
        src = get_channel_source(ch)
        if src and src.type == 'TEX_IMAGE' and src.image:
            ch_tree = get_channel_source_tree(ch, layer)
            remove_node(ch_tree, ch, 'source', remove_on_disk=remove_on_disk)

        src = get_channel_source_1(ch)
        if src and src.type == 'TEX_IMAGE' and src.image:
            remove_node(layer_tree, ch, 'source_1', remove_on_disk=remove_on_disk)

    # Remove Mask source
    for mask in layer.masks:

        # Dealing with decal object
        Decal.remove_decal_object(layer_tree, mask)

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
        remove_node(mask_tree, mask, 'source', remove_on_disk=remove_on_disk)

        # Remove baked source
        baked_source = get_mask_source(mask, get_baked=True)
        if baked_source:
            remove_node(mask_tree, mask, 'baked_source', remove_on_disk=remove_on_disk)

    # Remove node group and layer tree
    if layer_tree: 
        layer_node = group_tree.nodes.get(layer.group_node)
        remove_datablock(bpy.data.node_groups, layer_tree, user=layer_node, user_prop='node_tree')
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

    # Reset UI
    wm.ypui.layer_ui.expand_content = False
    wm.ypui.layer_ui.expand_source = False
    wm.ypui.layer_ui.expand_channels = False
    wm.ypui.layer_ui.expand_masks = False
    wm.ypui.layer_ui.expand_vector = False
    for i, ch in enumerate(layer.channels):
        wm.ypui.layer_ui.channels[i].expand_content = False
    wm.ypui.need_update = True

    # Delete the layer
    yp.layers.remove(index)

def update_driver_targets(obj, target_map):
    # Update driver target object references based on a given object map.
    for fcurve in obj.animation_data.drivers if obj.animation_data else []:
        for var in fcurve.driver.variables:
            for target in var.targets:
                if target.id in target_map:
                    target.id = target_map[target.id]

def duplicate_decal_empty_reference(texcoord_name, ttree, set_new_decal_position, duplicated_empties):
    texcoord = ttree.nodes.get(texcoord_name)
    if not texcoord or not hasattr(texcoord, 'object') or not texcoord.object:
        return

    original_empty = texcoord.object

    if set_new_decal_position:
        texcoord.object = Decal.create_decal_empty()
    else:
        if original_empty in duplicated_empties:
            new_empty = duplicated_empties[original_empty]
        else:
            nname = get_unique_name(original_empty.name, bpy.data.objects)
            custom_collection = (
                original_empty.users_collection[0]
                if is_bl_newer_than(2, 80) and len(original_empty.users_collection) > 0
                else None
            )
            new_empty = original_empty.copy()
            new_empty.name = nname
            link_object(bpy.context.scene, new_empty, custom_collection)

            duplicated_empties[original_empty] = new_empty

            # Update drivers on the new empty to point to any other duplicated empties
            update_driver_targets(new_empty, duplicated_empties)

        texcoord.object = new_empty

def duplicate_layer_modifier_tree(layer, tree):
    mod_tree = None
    for mg in layer.mod_groups:
        mod_group = tree.nodes.get(mg.name)
        if mod_group:
            if not mod_tree:
                mod_group.node_tree = mod_group.node_tree.copy()
                mod_tree = mod_group.node_tree
            else:
                mod_group.node_tree = mod_tree

def duplicate_layer_nodes_and_images(tree, specific_layers=[], packed_duplicate=True, duplicate_blank=False, ondisk_duplicate=False, set_new_decal_position=False):

    yp = tree.yp
    ypup = get_user_preferences()

    img_users = []
    img_nodes = []
    imgs = []

    vcol_users = []
    vcol_user_types = []
    vcol_nodes = []
    vcol_names = []
    duplicated_empties = {}
    for layer in yp.layers:
        if specific_layers and layer not in specific_layers: continue

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
            duplicate_layer_modifier_tree(layer, source_group.node_tree)

        else:
            source = ttree.nodes.get(layer.source)

            # Duplicate layer modifier groups
            duplicate_layer_modifier_tree(layer, ttree)

        # Decal object duplicate
        if layer.texcoord_type == 'Decal':
            duplicate_decal_empty_reference(layer.texcoord, ttree, set_new_decal_position, duplicated_empties)

        # Duplicate baked layer image
        baked_layer_source = get_layer_source(layer, get_baked=True)
        if baked_layer_source:
            img = baked_layer_source.image
            if img:
                img_users.append(layer)
                img_nodes.append(baked_layer_source)
                imgs.append(img)

        # Duplicate layer source
        if layer.type == 'IMAGE':
            img = source.image
            if img:
                img_users.append(layer)
                img_nodes.append(source)
                imgs.append(img)

        elif layer.type == 'VCOL':
            vcol_name = source.attribute_name
            if vcol_name != '':
                vcol_users.append(layer)
                vcol_user_types.append('LAYER')
                vcol_nodes.append(source)
                vcol_names.append(vcol_name)

        elif layer.type == 'HEMI':
            duplicate_lib_node_tree(source)

        # Duplicate override channel
        for ch in layer.channels:
            if ch.override:
                ch_source = get_channel_source(ch, layer)

                if ch.override_type == 'IMAGE':
                    img = ch_source.image
                    if img:
                        img_users.append(ch)
                        img_nodes.append(ch_source)
                        imgs.append(img)

                elif ch.override_type == 'VCOL':
                    vcol_name = ch_source.attribute_name
                    if vcol_name != '':
                        vcol_users.append(ch)
                        vcol_user_types.append('CHANNEL')
                        vcol_nodes.append(ch_source)
                        vcol_names.append(vcol_name)

            if ch.override_1 and ch.override_1_type == 'IMAGE':
                ch_source = get_channel_source_1(ch, layer)
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
            # Decal object duplicate
            if mask.texcoord_type == 'Decal':
                duplicate_decal_empty_reference(mask.texcoord, ttree, set_new_decal_position, duplicated_empties)
    
            # Duplicate baked mask image
            baked_mask_source = get_mask_source(mask, get_baked=True)
            if baked_mask_source:
                img = baked_mask_source.image
                if img:
                    img_users.append(mask)
                    img_nodes.append(baked_mask_source)
                    imgs.append(img)

            # Duplicate mask source
            if mask.type == 'IMAGE':
                img = mask_source.image
                if img:
                    img_users.append(mask)
                    img_nodes.append(mask_source)
                    imgs.append(img)
            elif mask.type == 'VCOL':
                vcol_name = mask_source.attribute_name
                if vcol_name != '':
                    vcol_users.append(mask)
                    vcol_user_types.append('MASK')
                    vcol_nodes.append(mask_source)
                    vcol_names.append(vcol_name)
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

    # Copy vertex color on layer and masks
    objs = get_all_objects_with_same_materials(get_active_material())
    for i, vcol_name in enumerate(vcol_names):

        # Get all available vcol names across all objects
        all_vcol_names = []
        for obj in objs:
            vcols = get_vertex_colors(obj)
            for vcol in vcols:
                if vcol.name not in all_vcol_names:
                    all_vcol_names.append(vcol.name)
        
        # Get new name based on already available vcol names
        new_vcol_name = get_unique_name(vcol_name, all_vcol_names)

        # Duplicate vertex color
        for obj in objs:
            vcols = get_vertex_colors(obj)
            if vcol_name in vcols:
                vcol = vcols.get(vcol_name)

                if vcol_user_types[i] == 'LAYER':
                    color = (0.0, 0.0, 0.0, 0.0)
                else: color = (0.0, 0.0, 0.0, 1.0)

                new_vcol = new_vertex_color(obj, new_vcol_name, vcol.data_type, vcol.domain, color_fill=color)

                if not duplicate_blank:
                    copy_vertex_color_data(obj, vcol_name, new_vcol_name)

        # Set new vertex color to node and user
        vcol_nodes[i].attribute_name = new_vcol_name
        yp.halt_update = True
        vcol_users[i].name = new_vcol_name
        yp.halt_update = False

    # Make all images single user
    #if packed_duplicate:

    already_copied_ids = []
    copied_image_atlas = {}

    # Copy image on layer and masks
    for i, img in enumerate(imgs):

        # Check if it's an ondisk image
        if not img.packed_file and img.filepath != '':
            if not ondisk_duplicate:
                continue
        # Or packed image
        elif not packed_duplicate:
            continue

        if img.yia.is_image_atlas:
            segment = img.yia.segments.get(img_users[i].segment_name)
            new_segment = None

            # Create new segment based on previous one
            if duplicate_blank:
                new_segment = ImageAtlas.get_set_image_atlas_segment(segment.width, segment.height,
                        img.yia.color, img.is_float, yp=yp)

            # If using different image atlas per yp, just copy the image (unless specific layer is on)
            elif ypup.unique_image_atlas_per_yp and not specific_layers:
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
            if duplicate_blank:
                new_segment = UDIM.get_set_udim_atlas_segment(
                    tilenums, color=img.yui.base_color,
                    colorspace = img.colorspace_settings.name,
                    hdr=img.is_float, yp=yp,
                    source_image=img, source_tilenums=segment_tilenums,
                    copy_only_size = True
                )

            # If using different image atlas per yp, just copy the image (unless specific layer is on)
            elif not specific_layers:
                if img.name not in copied_image_atlas:
                    copied_image_atlas[img.name] = duplicate_image(img)
                img_nodes[i].image = copied_image_atlas[img.name]

            else:
                new_segment = UDIM.get_set_udim_atlas_segment(
                    tilenums, color=img.yui.base_color, 
                    colorspace = img.colorspace_settings.name,
                    hdr=img.is_float, yp=yp, 
                    source_image=img, source_tilenums=segment_tilenums
                )

            if new_segment:

                img_users[i].segment_name = new_segment.name

                # Change image if different image is returned
                if new_segment.id_data != img:
                    img_nodes[i].image = new_segment.id_data

                # Update layer transform
                update_mapping(img_users[i])

        elif i not in already_copied_ids:
            # Copy image if not atlas
            if duplicate_blank:

                if hasattr(img, 'use_alpha'):
                    alpha = img.use_alpha
                else: alpha = True

                # Mask will have alpha filled
                m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', img_users[i].path_from_id())
                if m: 
                    mask_idx = int(m.group(2))
                    mask = img_users[i]

                    color = get_image_mask_base_color(mask, img, mask_idx)
                else: color = (0, 0, 0, 0)

                img_name = get_unique_name(img.name, bpy.data.images)

                if img.source == 'TILED':
                    img_nodes[i].image = img.copy()
                    img_nodes[i].image.name = img_name
                    UDIM.fill_tiles(img_nodes[i].image, color)
                    UDIM.initial_pack_udim(img_nodes[i].image, color)
                else:
                    img_nodes[i].image = bpy.data.images.new(
                        img_name, width=img.size[0], height=img.size[1],
                        alpha=alpha, float_buffer=img.is_float
                    )
                    img_nodes[i].image.generated_color = color

                img_nodes[i].image.colorspace_settings.name = img.colorspace_settings.name

            else:
                img_nodes[i].image = duplicate_image(img)

            # Check other nodes using the same image
            for j, imgg in enumerate(imgs):
                if j != i and imgg == img:
                    img_nodes[j].image = img_nodes[i].image
                    already_copied_ids.append(j)

