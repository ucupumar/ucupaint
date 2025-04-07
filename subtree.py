import bpy, re
from . import lib, Modifier, MaskModifier
from .common import *
from .node_arrangements import *
from .node_connections import *

def check_layer_divider_alpha(layer, tree=None):
    if not tree: tree = get_source_tree(layer)

    if layer.divide_rgb_by_alpha and layer.type in {'IMAGE', 'VCOL'}:
        divider_alpha = check_new_mix_node(tree, layer, 'divider_alpha', 'Spread Fix')
        divider_alpha.blend_type = 'DIVIDE'
        divider_alpha.inputs[0].default_value = 1.0
        set_mix_clamp(divider_alpha, True)
    else:
        remove_node(tree, layer, 'divider_alpha')

def check_entity_image_flip_y(entity):
    yp = entity.id_data.yp

    m1 = re.match(r'yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m1:
        layer = entity
        tree = get_source_tree(layer)
        flip_y_needed = layer.image_flip_y and layer.type == 'IMAGE'

    elif m2:
        layer = yp.layers[int(m2.group(1))]
        ch = entity
        tree = get_tree(layer)
        flip_y_needed = ch.image_flip_y and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'} and ch.override_1 and ch.override_1_type == 'IMAGE'
    else:
        return None

    if flip_y_needed:
        flip_y = check_new_node(tree, entity, 'flip_y', 'ShaderNodeGroup', 'Flip Y')
        flip_y.node_tree = lib.get_node_tree_lib(lib.FLIP_Y)
    else:
        remove_node(tree, entity, 'flip_y')

    return layer

def move_mod_group(layer, from_tree, to_tree):
    mod_group = from_tree.nodes.get(layer.mod_group)
    if mod_group:
        mod_tree = mod_group.node_tree
        remove_node(from_tree, layer, 'mod_group', remove_data=False)
        remove_node(from_tree, layer, 'mod_group_1', remove_data=False)

        mod_group = new_node(to_tree, layer, 'mod_group', 'ShaderNodeGroup', 'mod_group')
        mod_group.node_tree = mod_tree
        mod_group_1 = new_node(to_tree, layer, 'mod_group_1', 'ShaderNodeGroup', 'mod_group_1')
        mod_group_1.node_tree = mod_tree

def refresh_source_tree_ios(source_tree, layer_type):

    # Create input and outputs
    inp = get_tree_input_by_name(source_tree, 'Vector')
    if not inp: new_tree_input(source_tree, 'Vector', 'NodeSocketVector')

    out = get_tree_output_by_name(source_tree, 'Color')
    if not out: new_tree_output(source_tree, 'Color', 'NodeSocketColor')

    out = get_tree_output_by_name(source_tree, 'Alpha')
    if not out: new_tree_output(source_tree, 'Alpha', 'NodeSocketFloat')

    col1 = get_tree_output_by_name(source_tree, 'Color 1')
    alp1 = get_tree_output_by_name(source_tree, 'Alpha 1')

    if layer_type not in {'IMAGE', 'MUSGRAVE'}:

        if not col1: col1 = new_tree_output(source_tree, 'Color 1', 'NodeSocketColor')
        if not alp1: alp1 = new_tree_output(source_tree, 'Alpha 1', 'NodeSocketFloat')

    else:
        if col1: remove_tree_output(source_tree, col1)
        if alp1: remove_tree_output(source_tree, alp1)

def enable_channel_source_tree(layer, root_ch, ch, rearrange = False):
    #if not ch.override: return

    if ch.source_group != '': return

    layer_tree = get_tree(layer)

    if ch.override_type not in {'VCOL', 'HEMI', 'DEFAULT'}:

        # Get current source for reference
        source_ref = layer_tree.nodes.get(ch.source)
        linear_ref = layer_tree.nodes.get(ch.linear)

        if not source_ref: return

        # Create source tree
        source_tree = bpy.data.node_groups.new(LAYERGROUP_PREFIX + root_ch.name + ' Source', 'ShaderNodeTree')

        create_essential_nodes(source_tree, True)

        refresh_source_tree_ios(source_tree, ch.override_type)

        # Copy source from reference
        source = new_node(source_tree, ch, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Copy linear node from reference
        if linear_ref:
            linear = new_node(source_tree, ch, 'linear', linear_ref.bl_idname)
            copy_node_props(linear_ref, linear)

        # Create source node group
        source_group = new_node(layer_tree, ch, 'source_group', 'ShaderNodeGroup', 'source_group')
        source_n = new_node(layer_tree, ch, 'source_n', 'ShaderNodeGroup', 'source_n')
        source_s = new_node(layer_tree, ch, 'source_s', 'ShaderNodeGroup', 'source_s')
        source_e = new_node(layer_tree, ch, 'source_e', 'ShaderNodeGroup', 'source_e')
        source_w = new_node(layer_tree, ch, 'source_w', 'ShaderNodeGroup', 'source_w')

        source_group.node_tree = source_tree
        source_n.node_tree = source_tree
        source_s.node_tree = source_tree
        source_e.node_tree = source_tree
        source_w.node_tree = source_tree

        layer_tree.nodes.remove(source_ref)
        if linear_ref: layer_tree.nodes.remove(linear_ref)

    # Create uv neighbor
    if ch.override_type in {'VCOL', 'HEMI'}:
        uv_neighbor = replace_new_node(
            layer_tree, ch, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
            lib.NEIGHBOR_FAKE, hard_replace=True
        )
    #else: 
    elif ch.override_type not in {'DEFAULT'}: 
        uv_neighbor = replace_new_node(
            layer_tree, ch, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
            lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), hard_replace=True
        )
        set_uv_neighbor_resolution(ch, uv_neighbor)

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def enable_layer_source_tree(layer, rearrange=False):

    # Check if source tree is already available
    if layer.type in {'BACKGROUND', 'COLOR'}: return
    if layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT'} and layer.source_group != '': return

    layer_tree = get_tree(layer)

    if layer.type not in {'VCOL', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT'}:
        # Get current source for reference
        source_ref = layer_tree.nodes.get(layer.source)
        linear_ref = layer_tree.nodes.get(layer.linear)
        flip_y_ref = layer_tree.nodes.get(layer.flip_y)
        divider_alpha_ref = layer_tree.nodes.get(layer.divider_alpha)

        # Create source tree
        source_tree = bpy.data.node_groups.new(LAYERGROUP_PREFIX + layer.name + ' Source', 'ShaderNodeTree')

        create_essential_nodes(source_tree, True)

        refresh_source_tree_ios(source_tree, layer.type)

        # Copy source from reference
        source = new_node(source_tree, layer, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        if linear_ref:
            linear = new_node(source_tree, layer, 'linear', linear_ref.bl_idname)
            copy_node_props(linear_ref, linear)

        if flip_y_ref:
            flip_y = new_node(source_tree, layer, 'flip_y', flip_y_ref.bl_idname)
            copy_node_props(flip_y_ref, flip_y)

        if divider_alpha_ref:
            divider_alpha = new_node(source_tree, layer, 'divider_alpha', divider_alpha_ref.bl_idname)
            copy_node_props(divider_alpha_ref, divider_alpha)

        # Create source node group
        source_group = new_node(layer_tree, layer, 'source_group', 'ShaderNodeGroup', 'source_group')
        source_n = new_node(layer_tree, layer, 'source_n', 'ShaderNodeGroup', 'source_n')
        source_s = new_node(layer_tree, layer, 'source_s', 'ShaderNodeGroup', 'source_s')
        source_e = new_node(layer_tree, layer, 'source_e', 'ShaderNodeGroup', 'source_e')
        source_w = new_node(layer_tree, layer, 'source_w', 'ShaderNodeGroup', 'source_w')

        source_group.node_tree = source_tree
        source_n.node_tree = source_tree
        source_s.node_tree = source_tree
        source_e.node_tree = source_tree
        source_w.node_tree = source_tree

        # Remove previous source
        layer_tree.nodes.remove(source_ref)
        if linear_ref: layer_tree.nodes.remove(linear_ref)
        if flip_y_ref: layer_tree.nodes.remove(flip_y_ref)
        if divider_alpha_ref: layer_tree.nodes.remove(divider_alpha_ref)
    
        # Bring modifiers to source tree
        if layer.type in {'IMAGE', 'MUSGRAVE'}:
            for mod in layer.modifiers:
                Modifier.check_modifier_nodes(mod, source_tree, layer_tree)
        else:
            move_mod_group(layer, layer_tree, source_tree)

    # Create uv neighbor
    if layer.type in {'VCOL', 'HEMI', 'EDGE_DETECT'}:
        uv_neighbor = replace_new_node(
            layer_tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
            lib.NEIGHBOR_FAKE, hard_replace=True
        )
        if layer.type == 'VCOL':
            uv_neighbor_1 = replace_new_node(
                layer_tree, layer, 'uv_neighbor_1', 'ShaderNodeGroup', 'Neighbor UV 1', 
                lib.NEIGHBOR_FAKE, hard_replace=True
            )
    elif layer.type not in {'GROUP', 'OBJECT_INDEX', 'BACKFACE'}: 
        uv_neighbor = replace_new_node(
            layer_tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
            lib.get_neighbor_uv_tree_name(layer.texcoord_type, entity=layer), hard_replace=True
        )
        set_uv_neighbor_resolution(layer, uv_neighbor)

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def disable_channel_source_tree(layer, root_ch, ch, rearrange=True, force=False):
    yp = layer.id_data.yp

    # Check if fine bump map is used on some of layer channels
    if not force:
        smooth_bump_ch = None
        for i, root_ch in enumerate(yp.channels):
            if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and get_channel_enabled(layer.channels[i], layer, root_ch):
                smooth_bump_ch = root_ch

        if (ch.override_type not in {'DEFAULT'} and ch.source_group == '') or (not ch.override and smooth_bump_ch):
            return

    layer_tree = get_tree(layer)
    if not layer_tree: return

    #if ch.override_type not in {'DEFAULT'}:
    source_group = layer_tree.nodes.get(ch.source_group)
    if source_group:
        source_ref = source_group.node_tree.nodes.get(ch.source)
        linear_ref = source_group.node_tree.nodes.get(ch.linear)

        # Create new source
        source = new_node(layer_tree, ch, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Create new linear
        if linear_ref:
            linear = new_node(layer_tree, ch, 'linear', linear_ref.bl_idname)
            copy_node_props(linear_ref, linear)

    # Remove previous source
    remove_node(layer_tree, ch, 'source_group')
    remove_node(layer_tree, ch, 'source_n')
    remove_node(layer_tree, ch, 'source_s')
    remove_node(layer_tree, ch, 'source_e')
    remove_node(layer_tree, ch, 'source_w')

    remove_node(layer_tree, ch, 'uv_neighbor')
    #remove_node(layer_tree, ch, 'uv_neighbor_1')

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def disable_layer_source_tree(layer, rearrange=True, force=False):

    yp = layer.id_data.yp

    # Check if fine bump map is used on some of layer channels
    if not force:
        smooth_bump_ch = None
        for i, root_ch in enumerate(yp.channels):
            if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and get_channel_enabled(layer.channels[i], layer, root_ch) and is_height_process_needed(layer):
                smooth_bump_ch = root_ch

        if (layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT'} and layer.source_group == '') or smooth_bump_ch:
            return

    layer_tree = get_tree(layer)

    if force or layer.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT'}:
        source_group = layer_tree.nodes.get(layer.source_group)
        if source_group:
            source_ref = source_group.node_tree.nodes.get(layer.source)
            linear_ref = source_group.node_tree.nodes.get(layer.linear)
            flip_y_ref = source_group.node_tree.nodes.get(layer.flip_y)
            divider_alpha_ref = source_group.node_tree.nodes.get(layer.divider_alpha)

            # Create new source
            source = new_node(layer_tree, layer, 'source', source_ref.bl_idname)
            copy_node_props(source_ref, source)

            if linear_ref:
                linear = new_node(layer_tree, layer, 'linear', linear_ref.bl_idname)
                copy_node_props(linear_ref, linear)

            if flip_y_ref:
                flip_y = new_node(layer_tree, layer, 'flip_y', flip_y_ref.bl_idname)
                copy_node_props(flip_y_ref, flip_y)

            if divider_alpha_ref:
                divider_alpha = new_node(layer_tree, layer, 'divider_alpha', divider_alpha_ref.bl_idname)
                copy_node_props(divider_alpha_ref, divider_alpha)

            # Bring back layer modifier to original tree
            if layer.type in {'IMAGE', 'MUSGRAVE'}:
                for mod in layer.modifiers:
                    Modifier.check_modifier_nodes(mod, layer_tree, source_group.node_tree)
            else:
                move_mod_group(layer, source_group.node_tree, layer_tree)

            # Remove previous source
            remove_node(layer_tree, layer, 'source_group')
            remove_node(layer_tree, layer, 'source_n')
            remove_node(layer_tree, layer, 'source_s')
            remove_node(layer_tree, layer, 'source_e')
            remove_node(layer_tree, layer, 'source_w')

    remove_node(layer_tree, layer, 'uv_neighbor')
    remove_node(layer_tree, layer, 'uv_neighbor_1')

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def check_layer_bump_process(layer, tree=None):

    ypup = get_user_preferences()
    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    height_root_ch = get_root_height_channel(yp)

    # Check if previous normal is needed
    need_prev_normal = check_need_prev_normal(layer)

    dirty = False

    if need_prev_normal and get_layer_enabled(layer):
        if height_root_ch.enable_subdiv_setup: # and ypup.eevee_next_displacement:
            lib_name = lib.SUBDIV_ON_NORMAL
        elif height_root_ch.enable_smooth_bump:
            lib_name = lib.FINE_BUMP_PROCESS
        else: lib_name = lib.BUMP_PROCESS

        bump_process, dirty = replace_new_node(
            tree, layer, 'bump_process', 'ShaderNodeGroup', 'Bump Process',
            lib_name, return_status=True, hard_replace=True
        )

        #update_layer_bump_process_max_height(height_root_ch, layer, tree)
    else:
        dirty = remove_node(tree, layer, 'bump_process')

    return dirty

def check_mask_uv_neighbor(tree, layer, mask, mask_idx=-1):

    yp = layer.id_data.yp

    # Check if smooth bump channel is available
    smooth_bump_ch = get_smooth_bump_channel(layer)

    # Get channel that write height
    write_height_ch = get_write_height_normal_channel(layer)

    # Get mask index
    if mask_idx == -1:
        match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        mask_idx = int(match.group(2))

    # Get chain
    chain = get_bump_chain(layer)

    if smooth_bump_ch and get_channel_enabled(smooth_bump_ch) and get_mask_enabled(mask) and (
        (write_height_ch or mask_idx < chain) and 
        (mask.use_baked or (mask.type not in {'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'MODIFIER', 'EDGE_DETECT', 'HEMI', 'VCOL'} and mask.texcoord_type != 'Layer'))
        ):

        #if not mask.use_baked and mask.type in {'VCOL', 'HEMI', 'EDGE_DETECT'}:
        #    lib_name = lib.NEIGHBOR_FAKE
        #else: 
        lib_name = lib.get_neighbor_uv_tree_name(mask.texcoord_type, entity=mask)

        uv_neighbor, dirty = replace_new_node(
            tree, mask, 'uv_neighbor', 
            'ShaderNodeGroup', 'UV Neighbor', lib_name,
            return_status=True, hard_replace=True
        )

        set_uv_neighbor_resolution(mask, uv_neighbor)

        return dirty

    else:
        return remove_node(tree, mask, 'uv_neighbor')

    return False

def enable_mask_source_tree(layer, mask, reconnect = False):

    # Check if source tree is already available
    #if (mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT'}) and mask.group_node != '': return

    layer_tree = get_tree(layer)

    # Create uv neighbor
    #check_mask_uv_neighbor(layer_tree, layer, mask)

    if mask.group_node == '' and (mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT'}):
        # Get current source for reference
        source_ref = layer_tree.nodes.get(mask.source)
        baked_source_ref = layer_tree.nodes.get(mask.baked_source)
        linear_ref = layer_tree.nodes.get(mask.linear)

        # Create mask tree
        mask_tree = bpy.data.node_groups.new(MASKGROUP_PREFIX + mask.name, 'ShaderNodeTree')

        # Create input and outputs
        if mask.type == 'MODIFIER':
            new_tree_input(mask_tree, 'Value', 'NodeSocketFloat')
        else: new_tree_input(mask_tree, 'Vector', 'NodeSocketVector')
        new_tree_output(mask_tree, 'Value', 'NodeSocketFloat')

        create_essential_nodes(mask_tree)

        # Copy nodes from reference
        source = new_node(mask_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        if baked_source_ref:
            baked_source = new_node(mask_tree, mask, 'baked_source', baked_source_ref.bl_idname)
            copy_node_props(baked_source_ref, baked_source)

        if linear_ref:
            linear = new_node(mask_tree, mask, 'linear', linear_ref.bl_idname)
            copy_node_props(linear_ref, linear)

        # Create source node group
        group_node = new_node(layer_tree, mask, 'group_node', 'ShaderNodeGroup', 'source_group')
        source_n = new_node(layer_tree, mask, 'source_n', 'ShaderNodeGroup', 'source_n')
        source_s = new_node(layer_tree, mask, 'source_s', 'ShaderNodeGroup', 'source_s')
        source_e = new_node(layer_tree, mask, 'source_e', 'ShaderNodeGroup', 'source_e')
        source_w = new_node(layer_tree, mask, 'source_w', 'ShaderNodeGroup', 'source_w')

        group_node.node_tree = mask_tree
        source_n.node_tree = mask_tree
        source_s.node_tree = mask_tree
        source_e.node_tree = mask_tree
        source_w.node_tree = mask_tree

        for mod in mask.modifiers:
            MaskModifier.add_modifier_nodes(mod, mask_tree, layer_tree)

        # Remove previous nodes
        layer_tree.nodes.remove(source_ref)
        if baked_source_ref: layer_tree.nodes.remove(baked_source_ref)
        if linear_ref: layer_tree.nodes.remove(linear_ref)

    if reconnect:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def disable_mask_source_tree(layer, mask, reconnect=False):

    # Check if source tree is already gone
    #if mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE'} and mask.group_node == '': return

    layer_tree = get_tree(layer)

    if mask.group_node != '': #and (mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE'}):

        mask_tree = get_mask_tree(mask)

        source_ref = mask_tree.nodes.get(mask.source)
        baked_source_ref = mask_tree.nodes.get(mask.baked_source)
        linear_ref = mask_tree.nodes.get(mask.linear)
        group_node = layer_tree.nodes.get(mask.group_node)

        # Create new nodes
        source = new_node(layer_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        if baked_source_ref:
            baked_source = new_node(layer_tree, mask, 'baked_source', baked_source_ref.bl_idname)
            copy_node_props(baked_source_ref, baked_source)

        if linear_ref:
            linear = new_node(layer_tree, mask, 'linear', linear_ref.bl_idname)
            copy_node_props(linear_ref, linear)

        for mod in mask.modifiers:
            MaskModifier.add_modifier_nodes(mod, layer_tree, mask_tree)

        # Remove previous source
        remove_node(layer_tree, mask, 'group_node')
        remove_node(layer_tree, mask, 'source_n')
        remove_node(layer_tree, mask, 'source_s')
        remove_node(layer_tree, mask, 'source_e')
        remove_node(layer_tree, mask, 'source_w')
        remove_node(layer_tree, mask, 'tangent')
        remove_node(layer_tree, mask, 'bitangent')
        remove_node(layer_tree, mask, 'tangent_flip')
        remove_node(layer_tree, mask, 'bitangent_flip')

    #remove_node(layer_tree, mask, 'uv_neighbor')

    if reconnect:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def check_create_height_pack(layer, tree, height_root_ch, height_ch):

    channel_enabled = get_channel_enabled(height_ch, layer, height_root_ch)
    need_reconnect = False
    
    # Height unpack for group layer
    #if channel_enabled and height_root_ch.enable_smooth_bump and layer.type == 'GROUP':

    #    height_group_unpack, dirty = replace_new_node(tree, height_ch, 'height_group_unpack', 
    #            'ShaderNodeGroup', 'Unpack Height Group', lib.UNPACK_ONSEW, return_status=True)
    #    if dirty: need_reconnect = True
    #    height_alpha_group_unpack, dirty = replace_new_node(tree, height_ch, 'height_alpha_group_unpack', 
    #            'ShaderNodeGroup', 'Pack Height Alpha Group', lib.UNPACK_ONSEW, return_status=True)
    #    if dirty: need_reconnect = True
    #else:
    if remove_node(tree, height_ch, 'height_group_unpack'): need_reconnect = True
    if remove_node(tree, height_ch, 'height_alpha_group_unpack'): need_reconnect = True

    return need_reconnect

def check_create_spread_alpha(layer, tree, root_ch, ch):

    channel_enabled = get_channel_enabled(ch, layer, root_ch)
    need_reconnect = False

    # NOTE: Remove spread alpha node entirely (at least for now), since it provides almost nothing in most situations
    if False and channel_enabled and layer.type == 'IMAGE' and ch.normal_map_type != 'NORMAL_MAP': # and ch.enable_transition_bump:
        if root_ch.enable_smooth_bump:
            spread_alpha, dirty = replace_new_node(tree, ch, 'spread_alpha', 
                    'ShaderNodeGroup', 'Spread Alpha Hack', lib.SPREAD_ALPHA_SMOOTH, hard_replace=True, return_status=True)
        else:
            spread_alpha, dirty = replace_new_node(tree, ch, 'spread_alpha', 
                    'ShaderNodeGroup', 'Spread Alpha Hack', lib.SPREAD_ALPHA, hard_replace=True, return_status=True)
        if dirty: need_reconnect = True
    else:
        if remove_node(tree, ch, 'spread_alpha'): need_reconnect = True

    return need_reconnect

def check_mask_mix_nodes(layer, tree=None, specific_mask=None, specific_ch=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)
    if not tree: return False

    need_reconnect = False

    trans_bump = get_transition_bump_channel(layer)
    trans_bump_flip = trans_bump.transition_bump_flip if trans_bump else False

    height_process_needed = is_height_process_needed(layer)

    chain = get_bump_chain(layer)

    for i, mask in enumerate(layer.masks):
        if specific_mask and mask != specific_mask: continue

        for j, c in enumerate(mask.channels):

            ch = layer.channels[j]
            root_ch = yp.channels[j]
            channel_enabled = is_blend_node_needed(ch, layer, root_ch)
            write_height = get_write_height(ch)

            if specific_ch and ch != specific_ch: continue

            if not channel_enabled or not layer.enable_masks or not mask.enable or not c.enable:
                if remove_node(tree, c, 'mix'): need_reconnect = True
                if remove_node(tree, c, 'mix_remains'): need_reconnect = True
                if remove_node(tree, c, 'mix_limit'): need_reconnect = True
                if remove_node(tree, c, 'mix_limit_normal'): need_reconnect = True
                if root_ch.type == 'NORMAL':
                    if remove_node(tree, c, 'mix_pure'): need_reconnect = True
                    if remove_node(tree, c, 'mix_normal'): need_reconnect = True
                continue

            if (root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and height_process_needed and
                (write_height or (not write_height and i < chain))
                ):
                mix = tree.nodes.get(c.mix)
                if mix and (mix.type != 'GROUP' or not mix.name.endswith(mask.blend_type)):
                    if remove_node(tree, c, 'mix'): need_reconnect = True
                    mix = None
                if not mix:
                    need_reconnect = True
                    mix = new_node(tree, c, 'mix', 'ShaderNodeGroup', 'Mask Blend')
                    mix.node_tree = lib.get_smooth_mix_node(mask.blend_type, layer.type)
                    set_default_value(mix, 0, mask.intensity_value)
            else:
                mix = tree.nodes.get(c.mix)
                if mix and mix.type not in {'MIX_RGB', 'MIX'}:
                    if remove_node(tree, c, 'mix'): need_reconnect = True
                    mix = None
                if not mix:
                    need_reconnect = True
                    mix = new_mix_node(tree, c, 'mix', 'Mask Blend')
                    mix.inputs[0].default_value = mask.intensity_value
                if mix.blend_type != mask.blend_type:
                    mix.blend_type = mask.blend_type
                # Use clamp to keep value between 0.0 to 1.0
                if mask.blend_type not in {'MIX', 'MULTIPLY'}: 
                    set_mix_clamp(mix, True)

            if root_ch.type == 'NORMAL':

                if i >= chain and trans_bump and ch == trans_bump:
                    mix_pure = tree.nodes.get(c.mix_pure)
                    if not mix_pure:
                        need_reconnect = True
                        mix_pure = new_mix_node(tree, c, 'mix_pure', 'Mask Blend Pure')
                        if mix_pure.blend_type != mask.blend_type:
                            mix_pure.blend_type = mask.blend_type
                        # Use clamp to keep value between 0.0 to 1.0
                        set_mix_clamp(mix_pure, True)
                        mix_pure.inputs[0].default_value = mask.intensity_value

                else:
                    if remove_node(tree, c, 'mix_pure'): need_reconnect = True

                if i >= chain and (
                    (trans_bump and ch == trans_bump and ch.transition_bump_crease) or
                    (not trans_bump)
                    ):
                    mix_remains = tree.nodes.get(c.mix_remains)
                    if not mix_remains:
                        need_reconnect = True
                        mix_remains = new_mix_node(tree, c, 'mix_remains', 'Mask Blend Remaining')
                        mix_remains.inputs[0].default_value = mask.intensity_value
                    if mix_remains.blend_type != mask.blend_type:
                        mix_remains.blend_type = mask.blend_type
                    # Use clamp to keep value between 0.0 to 1.0
                    if mask.blend_type not in {'MIX', 'MULTIPLY'}: 
                        set_mix_clamp(mix_remains, True)
                else:
                    if remove_node(tree, c, 'mix_remains'): need_reconnect = True

                if layer.type == 'GROUP' and is_layer_using_normal_map(layer):
                    mix_normal = tree.nodes.get(c.mix_normal)
                    if not mix_normal:
                        need_reconnect = True
                        mix_normal = new_mix_node(tree, c, 'mix_normal', 'Mask Normal')
                        mix_normal.inputs[0].default_value = mask.intensity_value
                    if mix_normal.blend_type != mask.blend_type:
                        mix_normal.blend_type = mask.blend_type
                    # Use clamp to keep value between 0.0 to 1.0
                    if mask.blend_type not in {'MIX', 'MULTIPLY'}: 
                        set_mix_clamp(mix_normal, True)
                else:
                    if remove_node(tree, c, 'mix_normal'): need_reconnect = True

            else: 
                if (trans_bump and i >= chain and (
                    (trans_bump_flip and ch.enable_transition_ramp) or 
                    (not trans_bump_flip and ch.enable_transition_ao)
                    )):
                    mix_remains = tree.nodes.get(c.mix_remains)

                    if not mix_remains:
                        need_reconnect = True
                        mix_remains = new_mix_node(tree, c, 'mix_remains', 'Mask Blend n')
                        mix_remains.inputs[0].default_value = mask.intensity_value

                    if mix_remains.blend_type != mask.blend_type:
                        mix_remains.blend_type = mask.blend_type
                    # Use clamp to keep value between 0.0 to 1.0
                    if mask.blend_type not in {'MIX', 'MULTIPLY'}: 
                        set_mix_clamp(mix_remains, True)
                else:
                    if remove_node(tree, c, 'mix_remains'): need_reconnect = True

            if layer.type == 'GROUP' and mask.blend_type in limited_mask_blend_types:

                if root_ch.type != 'NORMAL' or not root_ch.enable_smooth_bump and height_process_needed:
                    mix_limit = tree.nodes.get(c.mix_limit)
                    if not mix_limit:
                        need_reconnect = True
                        mix_limit = new_node(tree, c, 'mix_limit', 'ShaderNodeMath', root_ch.name + ' Mask Limit')
                    mix_limit.operation = 'MINIMUM'
                    mix_limit.use_clamp = True
                else:
                    if remove_node(tree, c, 'mix_limit'): need_reconnect = True

                if root_ch.type == 'NORMAL':
                    mix_limit_normal = tree.nodes.get(c.mix_limit_normal)
                    if not mix_limit_normal:
                        need_reconnect = True
                        mix_limit_normal = new_node(tree, c, 'mix_limit_normal', 'ShaderNodeMath', root_ch.name + ' Mask Limit Normal')
                    mix_limit_normal.operation = 'MINIMUM'
                    mix_limit_normal.use_clamp = True
            else:
                if remove_node(tree, c, 'mix_limit'): need_reconnect = True
                if remove_node(tree, c, 'mix_limit_normal'): need_reconnect = True

    return need_reconnect

def check_mask_source_tree(layer, specific_mask=None): #, ch=None):

    #print("Checking mask source tree. Layer: " + layer.name + ' Specific Mask: ' + str(specific_mask))

    yp = layer.id_data.yp

    smooth_bump_ch = get_smooth_bump_channel(layer)
    write_height_ch = get_write_height_normal_channel(layer)
    chain = get_bump_chain(layer)
    ch_idx = get_layer_channel_index(layer, smooth_bump_ch)
    tree = get_tree(layer)

    height_process_needed = is_height_process_needed(layer)

    for i, mask in enumerate(layer.masks):
        if specific_mask and specific_mask != mask: continue

        if smooth_bump_ch and get_channel_enabled(smooth_bump_ch, layer, yp.channels[ch_idx]) and get_mask_enabled(mask) and (
                mask.channels[ch_idx].enable and height_process_needed and (write_height_ch or i < chain) and
                (mask.use_baked or mask.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT'})
                ): 
            enable_mask_source_tree(layer, mask)
        else:
            disable_mask_source_tree(layer, mask)

        check_mask_uv_neighbor(tree, layer, mask)

def remove_tangent_sign_vcol(obj, uv_name):
    mat = obj.active_material

    objs = []
    if obj.type == 'MESH':
        objs.append(obj)

    if mat.users > 1:
        for ob in get_scene_objects():
            if ob.type != 'MESH': continue
            if mat.name in ob.data.materials and ob not in objs:
                objs.append(ob)

    for ob in objs:
        vcols = get_vertex_colors(ob)
        vcol = vcols.get(TANGENT_SIGN_PREFIX + uv_name)
        if vcol: vcol = vcols.remove(vcol)

def recover_tangent_sign_process(ori_obj, ori_mode, ori_selects):

    # Recover selected and active objects
    bpy.ops.object.select_all(action='DESELECT')
    for o in ori_selects:
        if is_bl_newer_than(2, 80): o.select_set(True)
        else: o.select = True

    if is_bl_newer_than(2, 80): bpy.context.view_layer.objects.active = ori_obj
    else: bpy.context.scene.objects.active = ori_obj

    # Back to original mode
    if ori_mode != ori_obj.mode:
        bpy.ops.object.mode_set(mode=ori_mode)

def actual_refresh_tangent_sign_vcol(obj, uv_name):

    if obj.type != 'MESH': return None

    # Cannot do this in edit mode
    ori_obj = bpy.context.object
    ori_mode = ori_obj.mode
    if ori_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Select only relevant object
    ori_selects = [o for o in bpy.context.selected_objects]
    bpy.ops.object.select_all(action='DESELECT')

    if is_bl_newer_than(2, 80): 
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    else: 
        obj.select = True
        bpy.context.scene.objects.active = obj

    # Set vertex color of bitangent sign
    uv_layers = get_uv_layers(obj)

    uv_layer = uv_layers.get(uv_name)
    if uv_layer:

        # Set uv as active
        ori_layer_name = uv_layers.active.name
        uv_layers.active = uv_layer

        # Get vertex color
        vcols = get_vertex_colors(obj)
        vcol = vcols.get(TANGENT_SIGN_PREFIX + uv_name)
        if not vcol:
            try: 
                vcol = new_vertex_color(obj, TANGENT_SIGN_PREFIX + uv_name)
            except: 
                recover_tangent_sign_process(ori_obj, ori_mode, ori_selects)
                return None

            # Set default color to be white
            if is_bl_newer_than(2, 80):
                for d in vcol.data: 
                    d.color = (1.0, 1.0, 1.0, 1.0)
            else: 
                for d in vcol.data: 
                    d.color = (1.0, 1.0, 1.0)

        # Use try except because ngon can cause error 
        try:
            # Calc tangents
            obj.data.calc_tangents()

            # Get vcol again after calculate tangent to prevent error
            vcol = vcols.get(TANGENT_SIGN_PREFIX + uv_name)

            # Set tangent sign to vertex color
            i = 0
            for poly in obj.data.polygons:
                for idx in poly.loop_indices:
                    vert = obj.data.loops[idx]
                    bs = max(vert.bitangent_sign, 0.0)
                    # Invert bitangent sign so the default value is 0.0 rather than 1.0
                    bs = 1.0 - bs
                    if is_bl_newer_than(2, 80):
                        vcol.data[i].color = (bs, bs, bs, 1.0)
                    else: vcol.data[i].color = (bs, bs, bs)
                    i += 1

        # If using ngon, need a temporary mesh
        except:

            # Remember selection
            if is_bl_newer_than(2, 80):
                ori_select = [o for o in bpy.context.view_layer.objects if o.select_get()]
            else: ori_select = [o for o in bpy.context.scene.objects if o.select]

            # If object has multi users, get all related objects
            related_objs = []
            if obj.data.users > 1:
                for o in get_scene_objects():
                    if o.data == obj.data and o != obj:
                        related_objs.append(o)

                # Make object data single user
                obj.data = obj.data.copy()

            temp_ob = obj.copy()
            temp_ob.data = obj.data.copy()
            temp_ob.name = '___TEMP__'

            if is_bl_newer_than(2, 80):
                bpy.context.scene.collection.objects.link(temp_ob)
                bpy.context.view_layer.objects.active = temp_ob
            else: 
                bpy.context.scene.objects.link(temp_ob)
                bpy.context.scene.objects.active = temp_ob

            # Triangulate ngon faces on temp object
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_mode(type="FACE")
            bpy.ops.mesh.select_face_by_sides(number=4, type='GREATER')
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.mesh.tris_convert_to_quads()
            bpy.ops.object.mode_set(mode='OBJECT')

            # Remove all modifiers on temp object
            for mod in temp_ob.modifiers:
                bpy.ops.object.modifier_remove(modifier=mod.name)

            # Calc tangents
            temp_ob.data.calc_tangents()

            # Set tangent sign to vertex color
            tvcols = get_vertex_colors(temp_ob)
            temp_vcol = tvcols.get(TANGENT_SIGN_PREFIX + uv_name)
            i = 0
            for poly in temp_ob.data.polygons:
                for idx in poly.loop_indices:
                    vert = temp_ob.data.loops[idx]
                    bs = max(vert.bitangent_sign, 0.0)
                    # Invert bitangent sign so the default value is 0.0 rather than 1.0
                    bs = 1.0 - bs
                    if is_bl_newer_than(2, 80):
                        temp_vcol.data[i].color = (bs, bs, bs, 1.0)
                    else: temp_vcol.data[i].color = (bs, bs, bs)
                    i += 1

            # Set active object back to the original mesh
            if is_bl_newer_than(2, 80):
                bpy.context.view_layer.objects.active = obj
            else: bpy.context.scene.objects.active = obj

            # Number of original modifiers
            num_mods = len(obj.modifiers)

            # Remember original enabled modifiers
            ori_show_render_mods = []
            ori_show_viewport_mods = []
            for m in obj.modifiers:
                ori_show_viewport_mods.append(m.show_viewport)
                ori_show_render_mods.append(m.show_render)
                m.show_viewport = False
                m.show_render = False
            
            # Add data transfer to original object
            mod_name = 'Transferz'
            mod = obj.modifiers.new(mod_name, 'DATA_TRANSFER')

            # Move data transfer modifier to the top
            #for i in range(len(obj.modifiers)-1):
            for i in range(num_mods):
                bpy.ops.object.modifier_move_up(modifier=mod_name)
                
            # Set transfer object
            mod.object = temp_ob
            mod.use_loop_data = True
            mod.data_types_loops = {'VCOL'}
            
            # Apply modifier
            bpy.ops.object.modifier_apply(modifier=mod_name)

            # Recover original enabled modifiers
            for i, m in enumerate(obj.modifiers):
                if ori_show_viewport_mods[i]:
                    m.show_viewport = ori_show_viewport_mods[i]
                if ori_show_render_mods[i]:
                    m.show_render = ori_show_render_mods[i]

            # Delete temp object
            remove_mesh_obj(temp_ob)

            # Set back original select
            for o in ori_select:
                if is_bl_newer_than(2, 80):
                    o.select_set(True)
                else: o.select = True

            # Bring object data to related objects
            if related_objs:
                ori_mesh = related_objs[0].data
                ori_name = ori_mesh.name
                for o in related_objs:
                    o.data = obj.data

                remove_datablock(bpy.data.meshes, ori_mesh)
                o.data.name = ori_name

        # Recover active uv
        set_active_uv_layer(obj, ori_layer_name)

        # Recovers
        recover_tangent_sign_process(ori_obj, ori_mode, ori_selects)

        # Get vcol again to make sure the data is consistent
        vcols = get_vertex_colors(obj)
        vcol = vcols.get(TANGENT_SIGN_PREFIX + uv_name)

        return vcol

    # Recovers
    recover_tangent_sign_process(ori_obj, ori_mode, ori_selects)

    return None

def refresh_tangent_sign_vcol(obj, uv_name):

    vcol = actual_refresh_tangent_sign_vcol(obj, uv_name)

    mat = obj.active_material

    # Flag for already processed mesh
    meshes_done = [obj.data]

    obs = get_all_objects_with_same_materials(mat)
    for ob in obs:
        if ob != obj and ob.data not in meshes_done:
            other_v = actual_refresh_tangent_sign_vcol(ob, uv_name)
            meshes_done.append(ob.data)

    return vcol

def update_enable_tangent_sign_hacks(self, context):
    node = get_active_ypaint_node()
    tree = node.node_tree
    yp = tree.yp
    #ypui = context.window_manager.ypui
    ypui = self
    obj = context.object

    for uv in yp.uvs:
        tangent_process = tree.nodes.get(uv.tangent_process)
        if tangent_process:
            tsign = tangent_process.node_tree.nodes.get('_tangent_sign')
            if is_tangent_sign_hacks_needed(yp):
                vcol = refresh_tangent_sign_vcol(obj, uv.name)
                if vcol: tsign.attribute_name = vcol.name
            else:
                tsign.attribute_name = ''
                remove_tangent_sign_vcol(obj, uv.name)

def check_actual_uv_nodes(yp, uv, obj):

    tree = yp.id_data

    if is_any_entity_using_uv(yp, uv.name):
        uv_map = tree.nodes.get(uv.uv_map)
        if not uv_map:
            uv_map = new_node(tree, uv, 'uv_map', 'ShaderNodeUVMap', uv.name)
            uv_map.uv_map = uv.name
    else:
        remove_node(tree, uv, 'uv_map')

    if is_tangent_process_needed(yp, uv.name):
        tangent_process = tree.nodes.get(uv.tangent_process)

        if not tangent_process:
            # Create tangent process which output both tangent and bitangent
            tangent_process = new_node(tree, uv, 'tangent_process', 'ShaderNodeGroup', uv.name + ' Tangent Process')
            if is_bl_newer_than(3):
                tangent_process.node_tree = get_node_tree_lib(lib.TANGENT_PROCESS_300)
            elif is_bl_newer_than(2, 80):
                tangent_process.node_tree = get_node_tree_lib(lib.TANGENT_PROCESS)
            else: tangent_process.node_tree = get_node_tree_lib(lib.TANGENT_PROCESS_LEGACY)
            duplicate_lib_node_tree(tangent_process)

            tangent_process.inputs['Backface Always Up'].default_value = 1.0 if yp.enable_backface_always_up else 0.0

            # Set values inside tangent process
            tp_nodes = tangent_process.node_tree.nodes
            node = tp_nodes.get('_tangent')
            if node: node.uv_map = uv.name
            node = tp_nodes.get('_tangent_from_norm')
            if node: node.uv_map = uv.name
            node = tp_nodes.get('_bitangent_from_norm')
            if node: node.uv_map = uv.name

            if is_tangent_sign_hacks_needed(yp):
                #tangent_process.inputs['Blender 2.8 Cycles Hack'].default_value = 1.0
                node = tp_nodes.get('_tangent_sign')

                vcol = refresh_tangent_sign_vcol(obj, uv.name)
                if vcol: node.attribute_name = vcol.name
            #else:
            #    tangent_process.inputs['Blender 2.8 Cycles Hack'].default_value = 0.0
    else:
        remove_node(tree, uv, 'tangent_process')

def check_parallax_process_outputs(parallax, uv_name, remove=False):

    outp = get_tree_output_by_name(parallax.node_tree, uv_name)
    if remove and outp:
        remove_tree_output(parallax.node_tree, outp)
    elif not remove and not outp:
        outp = new_tree_output(parallax.node_tree, uv_name, 'NodeSocketVector')

def check_parallax_mix(tree, uv, baked=False, remove=False):

    if baked: parallax_mix = tree.nodes.get(uv.baked_parallax_mix)
    else: parallax_mix = tree.nodes.get(uv.parallax_mix)

    if remove and parallax_mix:
        if baked: remove_node(tree, uv, 'baked_parallax_mix')
        else: remove_node(tree, uv, 'parallax_mix')
        #tree.nodes.remove(parallax_mix)
    elif not remove and not parallax_mix:
        if baked: 
            parallax_mix = new_mix_node(tree, uv, 'baked_parallax_mix', uv.name + ' Final Mix')
        else: 
            parallax_mix = new_mix_node(tree, uv, 'parallax_mix', uv.name + ' Final Mix')

def check_non_uv_parallax_mix(tree, texcoord_name, remove=False):

    parallax_mix = tree.nodes.get(PARALLAX_MIX_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name)

    if remove and parallax_mix:
        tree.nodes.remove(parallax_mix)
    elif not remove and not parallax_mix:
        parallax_mix = simple_new_mix_node(tree)
        parallax_mix.name = PARALLAX_MIX_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name
        parallax_mix.label = texcoord_name + ' Final Mix'

def check_start_delta_uv_inputs(tree, uv_name, remove=False):

    start_uv_name = uv_name + START_UV
    delta_uv_name = uv_name + DELTA_UV

    start = get_tree_input_by_name(tree, start_uv_name)
    if remove and start:
        remove_tree_input(tree, start)
    elif not remove and not start:
        new_tree_input(tree, start_uv_name, 'NodeSocketVector')

    delta = get_tree_input_by_name(tree, delta_uv_name)
    if remove and delta:
        remove_tree_input(tree, delta)
    elif not remove and not delta:
        new_tree_input(tree, delta_uv_name, 'NodeSocketVector')

def check_current_uv_outputs(tree, uv_name, remove=False):
    current_uv_name = uv_name + CURRENT_UV

    #current = tree.outputs.get(current_uv_name)
    current = get_tree_output_by_name(tree, current_uv_name)
    if remove and current:
        #tree.outputs.remove(current)
        remove_tree_output(tree, current)
    elif not remove and not current:
        #tree.outputs.new('NodeSocketVector', current_uv_name)
        new_tree_output(tree, current_uv_name, 'NodeSocketVector')

def check_current_uv_inputs(tree, uv_name, remove=False):
    current_uv_name = uv_name + CURRENT_UV

    current = get_tree_input_by_name(tree, current_uv_name)
    if remove and current:
        remove_tree_input(tree, current)
    elif not remove and not current:
        new_tree_input(tree, current_uv_name, 'NodeSocketVector')

def check_iterate_current_uv_mix(tree, uv, baked=False, remove=False):

    if baked: current_uv_mix = tree.nodes.get(uv.baked_parallax_current_uv_mix)
    else: current_uv_mix = tree.nodes.get(uv.parallax_current_uv_mix)

    if remove and current_uv_mix:
        if baked: remove_node(tree, uv, 'baked_parallax_current_uv_mix')
        else: remove_node(tree, uv, 'parallax_current_uv_mix')
    elif not remove and not current_uv_mix:
        if baked: 
            current_uv_mix = new_mix_node(tree, uv, 'baked_parallax_current_uv_mix', uv.name + CURRENT_UV)
        else: 
            current_uv_mix = new_mix_node(tree, uv, 'parallax_current_uv_mix', uv.name + CURRENT_UV)

def check_non_uv_iterate_current_mix(tree, texcoord_name, remove=False):

    current_mix = tree.nodes.get(PARALLAX_CURRENT_MIX_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name)

    if remove and current_mix:
        tree.nodes.remove(current_mix)
    elif not remove and not current_mix:
        current_mix = simple_new_mix_node(tree)
        current_mix.name = PARALLAX_CURRENT_MIX_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name
        current_mix.label = texcoord_name + ' Current Mix'

def check_depth_source_calculation(tree, uv, baked=False, remove=False):

    if baked: delta_uv = tree.nodes.get(uv.baked_parallax_delta_uv)
    else: delta_uv = tree.nodes.get(uv.parallax_delta_uv)

    if remove and delta_uv:
        if baked: remove_node(tree, uv, 'baked_parallax_delta_uv')
        else: remove_node(tree, uv, 'parallax_delta_uv')
        #tree.nodes.remove(delta_uv)
    elif not remove and not delta_uv:
        if baked: 
            delta_uv = new_mix_node(tree, uv, 'baked_parallax_delta_uv', uv.name + DELTA_UV)
        else: 
            delta_uv = new_mix_node(tree, uv, 'parallax_delta_uv', uv.name + DELTA_UV)
        delta_uv.inputs[0].default_value = 1.0
        delta_uv.blend_type = 'MULTIPLY'

    if baked: current_uv = tree.nodes.get(uv.baked_parallax_current_uv)
    else: current_uv = tree.nodes.get(uv.parallax_current_uv)

    if remove and current_uv:
        if baked: remove_node(tree, uv, 'baked_parallax_current_uv')
        else: remove_node(tree, uv, 'parallax_current_uv')
        #tree.nodes.remove(current_uv)
    elif not remove and not current_uv:
        if baked: current_uv = new_node(tree, uv, 'baked_parallax_current_uv', 'ShaderNodeVectorMath', uv.name + CURRENT_UV)
        else: current_uv = new_node(tree, uv, 'parallax_current_uv', 'ShaderNodeVectorMath', uv.name + CURRENT_UV)
        current_uv.operation = 'SUBTRACT'

def check_non_uv_depth_source_calculation(tree, texcoord_name, remove=False):

    delta = tree.nodes.get(PARALLAX_DELTA_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name)

    if remove and delta:
        tree.nodes.remove(delta)
    elif not remove and not delta:
        delta = simple_new_mix_node(tree)
        delta.name = PARALLAX_DELTA_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name
        delta.label = texcoord_name + ' Delta'
        delta.inputs[0].default_value = 1.0
        delta.blend_type = 'MULTIPLY'

    current = tree.nodes.get(PARALLAX_CURRENT_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name)

    if remove and current:
        tree.nodes.remove(current)
    elif not remove and not current:
        current = tree.nodes.new('ShaderNodeVectorMath')
        current.name = PARALLAX_CURRENT_PREFIX + TEXCOORD_IO_PREFIX + texcoord_name
        current.label = texcoord_name + ' Current'
        current.operation = 'SUBTRACT'

def refresh_parallax_depth_source_layers(yp, parallax): #, disp_ch):

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    for layer in yp.layers:
        node = tree.nodes.get(layer.depth_group_node)
        if not node:
            n = yp.id_data.nodes.get(layer.group_node)
            node = new_node(tree, layer, 'depth_group_node', 'ShaderNodeGroup', layer.name)
            node.node_tree = n.node_tree

def refresh_parallax_depth_img(yp, parallax, disp_img): #, disp_ch):

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    height_map = tree.nodes.get(HEIGHT_MAP)
    if not height_map:
        height_map = tree.nodes.new('ShaderNodeTexImage')
        height_map.name = HEIGHT_MAP
        if hasattr(height_map, 'color_space'):
            height_map.color_space = 'NONE'

    height_map.image = disp_img

def check_parallax_prep_nodes(yp, unused_uvs=[], unused_texcoords=[], baked=False):

    tree = yp.id_data

    # Standard height channel is same as parallax channel (for now?)
    height_ch = get_root_height_channel(yp)
    if not height_ch: return

    if baked: num_of_layers = int(height_ch.baked_parallax_num_of_layers)
    else: num_of_layers = int(height_ch.parallax_num_of_layers)

    max_height = get_displacement_max_height(height_ch)

    # Create parallax preparations for uvs
    for uv in yp.uvs:
        if uv in unused_uvs: continue
        if not is_parallax_enabled(height_ch):
            remove_node(tree, uv, 'parallax_prep')
        else:
            parallax_prep = tree.nodes.get(uv.parallax_prep)
            if not parallax_prep:
                parallax_prep = new_node(
                    tree, uv, 'parallax_prep', 'ShaderNodeGroup', 
                    uv.name + ' Parallax Preparation'
                )
                parallax_prep.node_tree = get_node_tree_lib(lib.PARALLAX_OCCLUSION_PREP)

            #parallax_prep.inputs['depth_scale'].default_value = height_ch.displacement_height_ratio
            parallax_prep.inputs['depth_scale'].default_value = max_height * height_ch.parallax_height_tweak
            parallax_prep.inputs['ref_plane'].default_value = height_ch.parallax_ref_plane
            parallax_prep.inputs['Rim Hack'].default_value = 1.0 if height_ch.parallax_rim_hack else 0.0
            parallax_prep.inputs['Rim Hack Hardness'].default_value = height_ch.parallax_rim_hack_hardness
            parallax_prep.inputs['layer_depth'].default_value = 1.0 / num_of_layers

    # Create parallax preparations for texcoords other than UV
    for tc in texcoord_lists:

        parallax_prep = tree.nodes.get(tc + PARALLAX_PREP_SUFFIX)

        if tc not in unused_texcoords and is_parallax_enabled(height_ch):

            if not parallax_prep:
                parallax_prep = tree.nodes.new('ShaderNodeGroup')
                if tc in {'Generated', 'Normal', 'Object'}:
                    parallax_prep.node_tree = lib.get_node_tree_lib(lib.PARALLAX_OCCLUSION_PREP_OBJECT)
                elif tc in {'Camera', 'Window', 'Reflection'}: 
                    parallax_prep.node_tree = lib.get_node_tree_lib(lib.PARALLAX_OCCLUSION_PREP_CAMERA)
                else:
                    parallax_prep.node_tree = lib.get_node_tree_lib(lib.PARALLAX_OCCLUSION_PREP)
                parallax_prep.name = parallax_prep.label = tc + PARALLAX_PREP_SUFFIX

            parallax_prep.inputs['depth_scale'].default_value = max_height * height_ch.parallax_height_tweak
            parallax_prep.inputs['ref_plane'].default_value = height_ch.parallax_ref_plane
            parallax_prep.inputs['Rim Hack'].default_value = 1.0 if height_ch.parallax_rim_hack else 0.0
            parallax_prep.inputs['Rim Hack Hardness'].default_value = height_ch.parallax_rim_hack_hardness
            parallax_prep.inputs['layer_depth'].default_value = 1.0 / num_of_layers

        elif parallax_prep:
            tree.nodes.remove(parallax_prep)

def clear_parallax_node_data(yp, parallax, baked=False):

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
    iterate = parallax_loop.node_tree.nodes.get('_iterate')

    # Remove iterate depth
    counter = 0
    while True:
        it = parallax_loop.node_tree.nodes.get('_iterate_depth_' + str(counter))

        if it and it.node_tree:
            remove_datablock(bpy.data.node_groups, it.node_tree, user=it, user_prop='node_tree')
        else: break

        counter += 1

    # Remove node trees
    remove_datablock(bpy.data.node_groups, iterate.node_tree, user=iterate, user_prop='node_tree')
    remove_datablock(bpy.data.node_groups, parallax_loop.node_tree, user=parallax_loop, user_prop='node_tree')
    remove_datablock(bpy.data.node_groups, depth_source_0.node_tree, user=depth_source_0, user_prop='node_tree')

    # Clear parallax uv node names
    for uv in yp.uvs:
        if not baked:
            uv.parallax_current_uv_mix = ''
            uv.parallax_current_uv = ''
            uv.parallax_delta_uv = ''
            uv.parallax_mix = ''
        else:
            uv.baked_parallax_current_uv_mix = ''
            uv.baked_parallax_current_uv = ''
            uv.baked_parallax_delta_uv = ''
            uv.baked_parallax_mix = ''

    # Clear parallax layer node names
    if not baked:
        for layer in yp.layers:
            layer.depth_group_node = ''

def check_adaptive_subdiv_nodes(yp, height_ch, baked=False):

    if baked and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
        pass
    else:
        pass

def check_parallax_node(yp, height_ch, unused_uvs=[], unused_texcoords=[], baked=False):

    tree = yp.id_data

    if baked: num_of_layers = int(height_ch.baked_parallax_num_of_layers)
    else: num_of_layers = int(height_ch.parallax_num_of_layers)

    # Get parallax node
    node_name = BAKED_PARALLAX if baked else PARALLAX
    parallax = tree.nodes.get(node_name)
    baked_parallax_filter = tree.nodes.get(BAKED_PARALLAX_FILTER)

    if (
            not is_parallax_enabled(height_ch) or 
            (baked and not yp.use_baked) or (not baked and yp.use_baked) or
            (yp.use_baked and height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive)
        ):
        if parallax:
            clear_parallax_node_data(yp, parallax, baked)
            simple_remove_node(tree, parallax, True)
            if baked_parallax_filter: simple_remove_node(tree, baked_parallax_filter, True)
        return

    # Displacement image needed for baked parallax
    disp_img = None
    if baked:
        baked_disp = tree.nodes.get(height_ch.baked_disp)
        if baked_disp:
            disp_img = baked_disp.image
        else:
            return

    # Create parallax node
    if not parallax:
        parallax = tree.nodes.new('ShaderNodeGroup')
        parallax.name = node_name

        parallax.label = 'Parallax Occlusion Mapping'
        if baked: parallax.label = 'Baked ' + parallax.label

        parallax.node_tree = get_node_tree_lib(lib.PARALLAX_OCCLUSION_PROC)
        duplicate_lib_node_tree(parallax)

        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
        depth_source_0.node_tree.name += '_Copy'
        
        parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
        duplicate_lib_node_tree(parallax_loop)

        #iterate = parallax_loop.node_tree.nodes.get('_iterate_0')
        iterate = parallax_loop.node_tree.nodes.get('_iterate')
        duplicate_lib_node_tree(iterate)

    # Check baked parallax filter
    if baked and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
        if not baked_parallax_filter:
            baked_parallax_filter = tree.nodes.new('ShaderNodeGroup')
            baked_parallax_filter.name = BAKED_PARALLAX_FILTER
            if is_bl_newer_than(2, 80):
                baked_parallax_filter.node_tree = get_node_tree_lib(lib.ENGINE_FILTER)
            else: baked_parallax_filter.node_tree = get_node_tree_lib(lib.ENGINE_FILTER_LEGACY)
            baked_parallax_filter.label = 'Baked Parallax Filter'
    elif baked_parallax_filter:
        simple_remove_node(tree, baked_parallax_filter, True)

    parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')

    parallax.inputs['layer_depth'].default_value = 1.0 / num_of_layers

    if baked:
        refresh_parallax_depth_img(yp, parallax, disp_img)
    else: refresh_parallax_depth_source_layers(yp, parallax)

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
    #iterate = parallax_loop.node_tree.nodes.get('_iterate_0')
    iterate = parallax_loop.node_tree.nodes.get('_iterate')
    #iterate_group_0 = parallax_loop.node_tree.nodes.get('_iterate_group_0')

    # Create IO and nodes for UV
    for uv in yp.uvs:

        if (baked and yp.baked_uv_name != uv.name) or uv in unused_uvs:

            # Delete other uv io
            check_parallax_process_outputs(parallax, uv.name, remove=True)
            check_start_delta_uv_inputs(parallax.node_tree, uv.name, remove=True)
            check_parallax_mix(parallax.node_tree, uv, baked, remove=True)

            check_start_delta_uv_inputs(depth_source_0.node_tree, uv.name, remove=True)
            check_current_uv_outputs(depth_source_0.node_tree, uv.name, remove=True)
            check_depth_source_calculation(depth_source_0.node_tree, uv, baked, remove=True)

            check_start_delta_uv_inputs(parallax_loop.node_tree, uv.name, remove=True)
            check_current_uv_outputs(parallax_loop.node_tree, uv.name, remove=True)
            check_current_uv_inputs(parallax_loop.node_tree, uv.name, remove=True)

            check_start_delta_uv_inputs(iterate.node_tree, uv.name, remove=True)
            check_current_uv_outputs(iterate.node_tree, uv.name, remove=True)
            check_current_uv_inputs(iterate.node_tree, uv.name, remove=True)
            check_iterate_current_uv_mix(iterate.node_tree, uv, baked, remove=True)

            #check_start_delta_uv_inputs(iterate_group_0.node_tree, uv.name, remove=True)
            #check_current_uv_outputs(iterate_group_0.node_tree, uv.name, remove=True)
            #check_current_uv_inputs(iterate_group_0.node_tree, uv.name, remove=True)

            continue

        check_parallax_process_outputs(parallax, uv.name)
        check_start_delta_uv_inputs(parallax.node_tree, uv.name)
        check_parallax_mix(parallax.node_tree, uv, baked)

        check_start_delta_uv_inputs(depth_source_0.node_tree, uv.name)
        check_current_uv_outputs(depth_source_0.node_tree, uv.name)
        check_depth_source_calculation(depth_source_0.node_tree, uv, baked)

        check_start_delta_uv_inputs(parallax_loop.node_tree, uv.name)
        check_current_uv_outputs(parallax_loop.node_tree, uv.name)
        check_current_uv_inputs(parallax_loop.node_tree, uv.name)

        check_start_delta_uv_inputs(iterate.node_tree, uv.name)
        check_current_uv_outputs(iterate.node_tree, uv.name)
        check_current_uv_inputs(iterate.node_tree, uv.name)
        check_iterate_current_uv_mix(iterate.node_tree, uv, baked)

        #check_start_delta_uv_inputs(iterate_group_0.node_tree, uv.name)
        #check_current_uv_outputs(iterate_group_0.node_tree, uv.name)
        #check_current_uv_inputs(iterate_group_0.node_tree, uv.name)

    # Baked parallax occlusion doesn't have to deal with non uv texture coordinates
    if not baked:

        # Create IO and nodes for Non-UV Texture Coordinates
        for tc in texcoord_lists:

            # Delete unused non UV io and nodes
            if tc in unused_texcoords:
                check_parallax_process_outputs(parallax, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_start_delta_uv_inputs(parallax.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_non_uv_parallax_mix(parallax.node_tree, tc, remove=True)

                check_start_delta_uv_inputs(depth_source_0.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_current_uv_outputs(depth_source_0.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_non_uv_depth_source_calculation(depth_source_0.node_tree, tc, remove=True)

                check_start_delta_uv_inputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_current_uv_outputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_current_uv_inputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)

                check_start_delta_uv_inputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_current_uv_outputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_current_uv_inputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                check_non_uv_iterate_current_mix(iterate.node_tree, tc, remove=True)

                #check_start_delta_uv_inputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                #check_current_uv_outputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)
                #check_current_uv_inputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc, remove=True)

                continue

            check_parallax_process_outputs(parallax, TEXCOORD_IO_PREFIX + tc)
            check_start_delta_uv_inputs(parallax.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_non_uv_parallax_mix(parallax.node_tree, tc)

            check_start_delta_uv_inputs(depth_source_0.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_current_uv_outputs(depth_source_0.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_non_uv_depth_source_calculation(depth_source_0.node_tree, tc)

            check_start_delta_uv_inputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_current_uv_outputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_current_uv_inputs(parallax_loop.node_tree, TEXCOORD_IO_PREFIX + tc)

            check_start_delta_uv_inputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_current_uv_outputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_current_uv_inputs(iterate.node_tree, TEXCOORD_IO_PREFIX + tc)
            check_non_uv_iterate_current_mix(iterate.node_tree, tc)

            #check_start_delta_uv_inputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc)
            #check_current_uv_outputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc)
            #check_current_uv_inputs(iterate_group_0.node_tree, TEXCOORD_IO_PREFIX + tc)

    #create_delete_iterate_nodes(parallax_loop.node_tree, num_of_layers)
    #create_delete_iterate_nodes_(parallax_loop.node_tree, num_of_layers)
    create_delete_iterate_nodes__(parallax_loop.node_tree, num_of_layers)
    #update_displacement_height_ratio(height_ch)

def remove_uv_nodes(uv, obj):
    tree = uv.id_data
    yp = tree.yp

    remove_node(tree, uv, 'uv_map')
    remove_node(tree, uv, 'tangent_process')
    remove_node(tree, uv, 'tangent')
    remove_node(tree, uv, 'tangent_flip')
    remove_node(tree, uv, 'bitangent')
    remove_node(tree, uv, 'bitangent_flip')
    remove_node(tree, uv, 'parallax_prep')

    remove_tangent_sign_vcol(obj, uv.name)

    #yp.uvs.remove(uv)

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

def check_uv_nodes(yp, generate_missings=False):

    # Check for UV needed
    uv_names = []

    # Get active object
    obj = bpy.context.object
    mat = get_active_material()

    dirty = False

    # Get baked uv name
    if yp.baked_uv_name != '':
        uv = yp.uvs.get(yp.baked_uv_name)
        if not uv:
            dirty = True
            uv = yp.uvs.add()
            uv.name = yp.baked_uv_name

        if uv.name not in uv_names: 
            uv_names.append(uv.name)

    # Get height channel
    height_ch = get_root_height_channel(yp)

    if height_ch:

        # Set height channel main uv if its still empty
        if height_ch.main_uv == '':
            uv_layers = get_uv_layers(obj)
            if uv_layers and len(uv_layers) > 0:
                height_ch.main_uv = uv_layers[0].name
                check_uvmap_on_other_objects_with_same_mat(mat, height_ch.main_uv)

        uv = yp.uvs.get(height_ch.main_uv)
        if not uv: 
            dirty = True
            uv = yp.uvs.add()
            uv.name = height_ch.main_uv

        if uv.name not in uv_names: 
            uv_names.append(height_ch.main_uv)

    # Collect uv names from layers
    for layer in yp.layers:
        if layer.texcoord_type == 'UV' and layer.uv_name != '':
            uv = yp.uvs.get(layer.uv_name)
            if not uv: 
                dirty = True
                uv = yp.uvs.add()
                uv.name = layer.uv_name

            if uv.name not in uv_names: 
                uv_names.append(uv.name)

        for mask in layer.masks:
            if mask.texcoord_type == 'UV' and mask.uv_name != '':
                uv = yp.uvs.get(mask.uv_name)
                if not uv: 
                    dirty = True
                    uv = yp.uvs.add()
                    uv.name = mask.uv_name

                if uv.name not in uv_names: 
                    uv_names.append(uv.name)

    # Get unused uv objects
    unused_uvs = []
    unused_ids = []
    for i, uv in reversed(list(enumerate(yp.uvs))):
        if uv.name not in uv_names:
            unused_uvs.append(uv)
            unused_ids.append(i)

    # Check non uv texcoords
    used_texcoords = []
    for layer in yp.layers:
        if layer.texcoord_type != 'UV' and layer.texcoord_type not in used_texcoords:
            used_texcoords.append(layer.texcoord_type)

        for mask in layer.masks:
            if mask.texcoord_type != 'UV' and mask.texcoord_type not in used_texcoords:
                used_texcoords.append(mask.texcoord_type)

    # Check for unused texcoords
    unused_texcoords = []
    for tc in texcoord_lists:
        if tc not in used_texcoords:
            unused_texcoords.append(tc)

    # Check parallax preparation nodes
    check_parallax_prep_nodes(yp, unused_uvs, unused_texcoords, baked=yp.use_baked)

    if height_ch: 

        # Check standard parallax
        check_parallax_node(yp, height_ch, unused_uvs, unused_texcoords)

        # Check baked parallax
        check_parallax_node(yp, height_ch, unused_uvs, baked=True)

        # Update max height to parallax nodes
        update_displacement_height_ratio(height_ch)

    # Remove unused uv objects
    for i in unused_ids:
        uv = yp.uvs[i]
        remove_uv_nodes(uv, obj)
        dirty = True
        yp.uvs.remove(i)

    # Check actual uv nodes
    for uv in yp.uvs:
        check_actual_uv_nodes(yp, uv, obj)

    # Generate missing uvs for some objects
    if generate_missings:

        objs = []
        if obj.type == 'MESH':
            objs.append(obj)

        if mat.users > 1:
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if mat.name in ob.data.materials and ob not in objs:
                    objs.append(ob)

        for ob in objs:
            uvls = get_uv_layers(ob)
            for uv in yp.uvs:
                if uv.name not in uvls:
                    uvl = uvls.new(name=uv.name)
                    uvls.active = uvl

    return dirty

def remove_layer_normal_channel_nodes(root_ch, layer, ch, tree=None):

    if not tree: tree = get_tree(layer)

    # Remove neighbor related nodes
    if root_ch.enable_smooth_bump:
        disable_layer_source_tree(layer, False)
        Modifier.disable_modifiers_tree(ch)

        if ch.override and ch.override_type != 'DEFAULT':
            disable_channel_source_tree(layer, root_ch, ch, False)

    remove_node(tree, ch, 'spread_alpha')

    remove_node(tree, ch, 'tb_distance_flipper')
    remove_node(tree, ch, 'tb_delta_calc')
    remove_node(tree, ch, 'bump_distance_ignorer')

    remove_node(tree, ch, 'height_proc')
    remove_node(tree, ch, 'height_blend')

    remove_node(tree, ch, 'normal_map_proc')
    remove_node(tree, ch, 'normal_proc')
    remove_node(tree, ch, 'normal_flip')

    remove_node(tree, ch, 'max_height_calc')

def check_channel_normal_map_nodes(tree, layer, root_ch, ch, need_reconnect=False):

    #print("Checking channel normal map nodes. Layer: " + layer.name + ' Channel: ' + root_ch.name)

    yp = layer.id_data.yp

    # Check mask mix nodes
    if check_mask_mix_nodes(layer, tree): need_reconnect = True

    # Only normal channel will continue proceed with this function
    if root_ch.type != 'NORMAL': return need_reconnect

    channel_enabled = get_channel_enabled(ch, layer, root_ch)
    height_process_needed = is_height_process_needed(layer)
    write_height = get_write_height(ch)

    # Check mask source tree
    check_mask_source_tree(layer) #, ch)

    # Check height pack/unpack
    if check_create_height_pack(layer, tree, root_ch, ch): need_reconnect = True

    # Check spread alpha if its needed
    if check_create_spread_alpha(layer, tree, root_ch, ch): need_reconnect = True

    # Dealing with neighbor related nodes
    if channel_enabled and root_ch.enable_smooth_bump and height_process_needed:
        enable_layer_source_tree(layer)
    else: 
        disable_layer_source_tree(layer, False)
        Modifier.disable_modifiers_tree(ch)

        #if ch.override and ch.override_type != 'DEFAULT':
        #    disable_channel_source_tree(layer, root_ch, ch, False)

    # Dealing with channel override
    if channel_enabled and ch.override and root_ch.enable_smooth_bump and ch.override_type != 'DEFAULT' and ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} and height_process_needed:
        enable_channel_source_tree(layer, root_ch, ch)
    else:
        disable_channel_source_tree(layer, root_ch, ch, False)

    if channel_enabled:

        # Check modifier trees
        Modifier.check_modifiers_trees(ch)

        max_height = get_displacement_max_height(root_ch, layer)
        update_displacement_height_ratio(root_ch)

    if channel_enabled and height_process_needed:

        # Bump distance ignorer
        if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} and not is_bump_distance_relevant(layer, ch):
            bump_distance_ignorer, dirty = check_new_node(
                tree, ch, 'bump_distance_ignorer', 'ShaderNodeMath',
                'Bump Distance Ignorer', True
            )
            if dirty: need_reconnect = True
            bump_distance_ignorer.operation = 'MULTIPLY'
            bump_distance_ignorer.inputs[1].default_value = 0.0
        else:
            if remove_node(tree, ch, 'bump_distance_ignorer'): need_reconnect = True

        # Transition bump flipper
        if ch.enable_transition_bump and ch.transition_bump_flip:
            tb_distance_flipper, dirty = check_new_node(
                tree, ch, 'tb_distance_flipper', 'ShaderNodeMath',
                'Transition Bump Distance Flipper', True
            )
            if dirty: need_reconnect = True
            tb_distance_flipper.operation = 'MULTIPLY'
            tb_distance_flipper.inputs[1].default_value = -1.0
        else:
            if remove_node(tree, ch, 'tb_distance_flipper'): need_reconnect = True

        # Delta calculation node
        if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} and ch.enable_transition_bump:
            tb_delta_calc, dirty = check_new_node(
                tree, ch, 'tb_delta_calc', 'ShaderNodeGroup',
                'Transition Bump Delta Calculation', True
            )
            if dirty: need_reconnect = True
            tb_delta_calc.node_tree = get_node_tree_lib(lib.TB_DELTA_CALC)
        else:
            if remove_node(tree, ch, 'tb_delta_calc'): need_reconnect = True

        # Max Height calculation node
        if ch.enable_transition_bump:
            if ch.transition_bump_crease and not ch.transition_bump_flip:
                if ch.normal_blend_type == 'OVERLAY':
                    lib_name = lib.CH_MAX_HEIGHT_TBC_ADD_CALC
                else: lib_name = lib.CH_MAX_HEIGHT_TBC_CALC
            else:
                if ch.normal_blend_type == 'OVERLAY':
                    lib_name = lib.CH_MAX_HEIGHT_TB_ADD_CALC
                else: lib_name = lib.CH_MAX_HEIGHT_TB_CALC
        else:
            lib_name = lib.CH_MAX_HEIGHT_CALC

        if ch.write_height:
            max_height_calc, need_reconnect = replace_new_node(
                tree, ch, 'max_height_calc', 'ShaderNodeGroup', 'Max Height Calculation', 
                lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
            )

            inp = max_height_calc.inputs.get('Is Flipped')
            if inp: inp.default_value = 1.0 if ch.enable_transition_bump and ch.transition_bump_flip else 0.0
        else:
            if remove_node(tree, ch, 'max_height_calc'): need_reconnect = True

        # Height Process
        if ch.normal_map_type == 'NORMAL_MAP':
            if root_ch.enable_smooth_bump:
                if ch.enable_transition_bump:
                    if ch.transition_bump_crease and not ch.transition_bump_flip:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP_CREASE
                    else: 
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP
                else: 
                    lib_name = lib.HEIGHT_PROCESS_SMOOTH_NORMAL_MAP

            else: 
                if ch.enable_transition_bump:
                    if ch.transition_bump_crease and not ch.transition_bump_flip:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_CREASE
                    else: 
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_NORMAL_MAP
                else: 
                    lib_name = lib.HEIGHT_PROCESS_NORMAL_MAP
        else:
            if root_ch.enable_smooth_bump:
                if ch.enable_transition_bump:
                    if ch.transition_bump_crease and not ch.transition_bump_flip:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_SMOOTH_CREASE
                    elif ch.transition_bump_chain == 0:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_SMOOTH_ZERO_CHAIN
                    else:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_SMOOTH
                else:
                    lib_name = lib.HEIGHT_PROCESS_SMOOTH
            else: 
                if ch.enable_transition_bump:
                    if ch.transition_bump_crease and not ch.transition_bump_flip:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION_CREASE
                    else:
                        lib_name = lib.HEIGHT_PROCESS_TRANSITION
                else:
                    lib_name = lib.HEIGHT_PROCESS

            # Group lib
            if layer.type == 'GROUP':
                lib_name += ' Group'

        height_proc, need_reconnect = replace_new_node(
            tree, ch, 'height_proc', 'ShaderNodeGroup', 'Height Process', 
            lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
        )

        if ch.normal_map_type == 'NORMAL_MAP':
            if ch.enable_transition_bump:
                set_default_value(height_proc, 'Bump Height', get_transition_bump_max_distance(ch))
            else: 
                set_default_value(height_proc, 'Bump Height', ch.normal_bump_distance)
        else:
            if layer.type != 'GROUP':
                set_default_value(height_proc, 'Value Max Height', get_layer_channel_bump_distance(layer, ch))
            if ch.enable_transition_bump:
                set_default_value(height_proc, 'Delta', get_transition_disp_delta(layer, ch))
                set_default_value(height_proc, 'Transition Max Height', get_transition_bump_max_distance(ch))

        set_default_value(height_proc, 'Intensity', ch.intensity_value)

        if ch.enable_transition_bump and channel_enabled and ch.transition_bump_crease and not ch.transition_bump_flip:
            set_default_value(height_proc, 'Crease Factor', ch.transition_bump_crease_factor)
            set_default_value(height_proc, 'Crease Power', ch.transition_bump_crease_power)

            if not write_height and not root_ch.enable_smooth_bump:
                set_default_value(height_proc, 'Remaining Filter', 1.0)
            else: set_default_value(height_proc, 'Remaining Filter', 0.0)

        # Height Blend

        if ch.normal_blend_type in {'MIX', 'OVERLAY'}:

            if ch.normal_blend_type == 'MIX':

                if layer.parent_idx != -1 or (is_normal_height_input_connected(root_ch) and root_ch.enable_smooth_bump):
                    if root_ch.enable_smooth_bump:
                        lib_name = lib.STRAIGHT_OVER_HEIGHT_MIX_SMOOTH
                    else: lib_name = lib.STRAIGHT_OVER_HEIGHT_MIX

                    height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                        lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
                    )

                    if write_height:
                        height_blend.inputs['Divide'].default_value = 1.0
                    else: height_blend.inputs['Divide'].default_value = 0.0
                else:
                    if root_ch.enable_smooth_bump:
                        height_blend, need_reconnect = replace_new_node(
                            tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                            lib.HEIGHT_MIX_SMOOTH, return_status=True, hard_replace=True, dirty=need_reconnect
                        )
                    else:
                        height_blend, need_reconnect = replace_new_mix_node(
                            tree, ch, 'height_blend', 'Height Blend', 
                            return_status=True, dirty=need_reconnect
                        )

                        height_blend.blend_type = 'MIX'

            elif ch.normal_blend_type == 'OVERLAY':

                if layer.parent_idx != -1 or (is_normal_height_input_connected(root_ch) and root_ch.enable_smooth_bump):
                    if root_ch.enable_smooth_bump:
                        lib_name = lib.STRAIGHT_OVER_HEIGHT_ADD_SMOOTH
                    else: lib_name = lib.STRAIGHT_OVER_HEIGHT_ADD

                    height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                        lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
                    )

                    if write_height:
                        height_blend.inputs['Divide'].default_value = 1.0
                    else: height_blend.inputs['Divide'].default_value = 0.0
                else:
                    if root_ch.enable_smooth_bump:
                        height_blend, need_reconnect = replace_new_node(
                            tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                            lib.HEIGHT_ADD_SMOOTH, return_status=True, hard_replace=True, dirty=need_reconnect
                        )
                    else:
                        height_blend, need_reconnect = replace_new_mix_node(
                            tree, ch, 'height_blend', 'Height Blend', 
                            return_status=True, dirty=need_reconnect
                        )

                        height_blend.blend_type = 'ADD'

        else:

            if layer.parent_idx != -1 or (is_normal_height_input_connected(root_ch) and root_ch.enable_smooth_bump):
                if root_ch.enable_smooth_bump:
                    lib_name = lib.STRAIGHT_OVER_HEIGHT_COMPARE_SMOOTH
                else: lib_name = lib.STRAIGHT_OVER_HEIGHT_COMPARE
            else:
                if root_ch.enable_smooth_bump:
                    lib_name = lib.HEIGHT_COMPARE_SMOOTH
                else: lib_name = lib.HEIGHT_COMPARE

            height_blend, need_reconnect = replace_new_node(
                tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
            )
    else:
        if remove_node(tree, ch, 'height_proc'): need_reconnect = True
        if remove_node(tree, ch, 'height_blend'): need_reconnect = True
        if remove_node(tree, ch, 'bump_distance_ignorer'): need_reconnect = True
        if remove_node(tree, ch, 'tb_distance_flipper'): need_reconnect = True
        if remove_node(tree, ch, 'tb_delta_calc'): need_reconnect = True
        if remove_node(tree, ch, 'max_height_calc'): need_reconnect = True

    # Normal Process
    if channel_enabled and is_normal_process_needed(layer):

        lib_name = ''

        if layer.type == 'GROUP':
            if root_ch.enable_smooth_bump:
                lib_name = lib.GROUP_BUMP_2_NORMAL_SMOOTH
            else: lib_name = lib.GROUP_BUMP_2_NORMAL

        elif ch.normal_map_type == 'NORMAL_MAP':
            if ch.enable_transition_bump:
                if root_ch.enable_smooth_bump:
                    lib_name = lib.BUMP_2_NORMAL_SMOOTH
                else: lib_name = lib.BUMP_2_NORMAL
            elif is_parallax_enabled(root_ch):
                lib_name = lib.NORMAL_MAP

        elif ch.normal_map_type == 'BUMP_MAP':
            if root_ch.enable_smooth_bump:
                lib_name = lib.BUMP_2_NORMAL_SMOOTH
            else: lib_name = lib.BUMP_2_NORMAL

        elif ch.normal_map_type == 'BUMP_NORMAL_MAP':
            if not ch.write_height:
                if root_ch.enable_smooth_bump:
                    lib_name = lib.BUMP_2_NORMAL_SMOOTH
                else: lib_name = lib.BUMP_2_NORMAL
            elif is_parallax_enabled(root_ch):
                lib_name = lib.NORMAL_MAP

        # Normal map
        if ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
            normal_map_proc, need_reconnect = check_new_node(tree, ch, 'normal_map_proc', 'ShaderNodeNormalMap', 'Normal Map Process', True)
            normal_map_proc.uv_map = layer.uv_name
            normal_map_proc.space = ch.normal_space
        else:
            if remove_node(tree, ch, 'normal_map_proc'): need_reconnect = True

        # Normal from bump
        if lib_name != '':
            normal_proc, need_reconnect = replace_new_node(
                tree, ch, 'normal_proc', 'ShaderNodeGroup', 'Bump to Normal', 
                lib_name, return_status=True, hard_replace=True, dirty=need_reconnect
            )

            if 'Max Height' in normal_proc.inputs:
                normal_proc.inputs['Max Height'].default_value = max_height
            if root_ch.enable_smooth_bump:
                if 'Bump Height Scale' in normal_proc.inputs:
                    normal_proc.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

            if 'Intensity' in normal_proc.inputs:
                normal_proc.inputs['Intensity'].default_value = ch.intensity_value

            if 'Strength' in normal_proc.inputs:
                normal_proc.inputs['Strength'].default_value = ch.normal_strength

        else:
            if remove_node(tree, ch, 'normal_proc'): need_reconnect = True

        # NOTE: Normal flip node is kinda unecessary since non smooth bump don't support backface up for now
        # Normal flip
        if False and not root_ch.enable_smooth_bump and not write_height:
            if is_bl_newer_than(2, 80): lib_name = lib.FLIP_BACKFACE_BUMP
            else: lib_name = lib.FLIP_BACKFACE_BUMP_LEGACY

            normal_flip = replace_new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 
                    'Normal Backface Flip', lib_name)

            set_bump_backface_flip(normal_flip, yp.enable_backface_always_up)
        else:
            if remove_node(tree, ch, 'normal_flip'): need_reconnect = True
    else:
        if remove_node(tree, ch, 'normal_map_proc'): need_reconnect = True
        if remove_node(tree, ch, 'normal_proc'): need_reconnect = True
        if remove_node(tree, ch, 'normal_flip'): need_reconnect = True

    if channel_enabled and ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':

        if ch.vdisp_enable_flip_yz:
            vdisp_flip_yz, dirty = check_new_node(tree, ch, 'vdisp_flip_yz', 'ShaderNodeGroup', 'Flip Y/Z', True)
            vdisp_flip_yz.node_tree = lib.get_node_tree_lib(lib.FLIP_YZ)
            if dirty: need_reconnect = True
        else:
            if remove_node(tree, ch, 'vdisp_flip_yz'): need_reconnect = True

        vdisp_proc, need_reconnect = replace_new_mix_node(
            tree, ch, 'vdisp_proc', 'Vector Displacement Process',
            return_status=True, hard_replace=True, dirty=need_reconnect
        )
        vdisp_proc.blend_type = 'MULTIPLY'
        vdisp_proc.inputs[0].default_value = 1.0
    else:
        if remove_node(tree, ch, 'vdisp_proc'): need_reconnect = True
        if remove_node(tree, ch, 'vdisp_flip_yz'): need_reconnect = True

    return need_reconnect

def remove_layer_channel_nodes(layer, ch, tree=None):
    if not tree: tree = get_tree(layer)

    remove_node(tree, ch, 'intensity')
    remove_node(tree, ch, 'blend')
    remove_node(tree, ch, 'extra_alpha')

def update_preview_mix(ch, preview):
    if preview.type != 'GROUP': return
    # Set channel layer blending
    mix = preview.node_tree.nodes.get('Mix')
    if mix and mix.blend_type != ch.blend_type:
        mix.blend_type = ch.blend_type

def check_override_1_layer_channel_nodes(root_ch, layer, ch):

    yp = layer.id_data.yp
    layer_tree = get_tree(layer)

    # Current source
    source = layer_tree.nodes.get(ch.source_1)

    prev_type = ''

    # Source 1 will only use default value or image for now
    if source:
        if source.bl_idname == 'ShaderNodeRGB':
            prev_type = 'DEFAULT'
        else: prev_type = 'IMAGE'

        if prev_type != ch.override_1_type or not ch.override_1:

            # Save source to cache if it's not default
            if prev_type != 'DEFAULT':

                ch.cache_1_image = source.name
                # Remove uv input link
                if any(source.inputs) and any(source.inputs[0].links):
                    layer_tree.links.remove(source.inputs[0].links[0])
                source.label = ''
                ch.source_1 = ''

    # Try to get channel source
    if ch.override_1 and ch.override_1_type != 'DEFAULT':
        source_label = root_ch.name + ' Override 1 : ' + ch.override_1_type

        cache = layer_tree.nodes.get(ch.cache_1_image)
        if cache:
            # Delete non cached source
            if prev_type == 'DEFAULT':
                remove_node(layer_tree, ch, 'source_1')

            ch.source_1 = cache.name
            ch.cache_1_image = ''

            cache.label = source_label
        else:
            source = replace_new_node(layer_tree, ch, 'source_1', 'ShaderNodeTexImage', source_label)

    else:
        remove_node(layer_tree, ch, 'source_1')

    # Update linear stuff
    check_layer_channel_linear_node(ch, layer, root_ch, reconnect=True)

def check_override_layer_channel_nodes(root_ch, layer, ch):

    yp = layer.id_data.yp
    layer_tree = get_tree(layer)

    channel_enabled = get_channel_enabled(ch, layer, root_ch)

    # Disable source tree first to avoid error
    if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and channel_enabled:
        disable_channel_source_tree(layer, root_ch, ch, rearrange=False, force=True)
        Modifier.disable_modifiers_tree(ch)

    # Current source
    source = layer_tree.nodes.get(ch.source)

    prev_type = ''

    if source:
        if source.bl_idname in {'ShaderNodeRGB', 'ShaderNodeValue'}:
            prev_type = 'DEFAULT'
        elif source.bl_idname == get_vcol_bl_idname():
            prev_type = 'VCOL'
        else: prev_type = source.bl_idname.replace('ShaderNodeTex', '').upper()

        #print('Prev Type:', prev_type)
        if prev_type != ch.override_type or not ch.override:

            # Save source to cache if it's not default
            if prev_type != 'DEFAULT':

                setattr(ch, 'cache_' + prev_type.lower(), source.name)
                # Remove uv input link
                #if ch.source_group == '' and 
                if any(source.inputs) and any(source.inputs[0].links):
                    layer_tree.links.remove(source.inputs[0].links[0])
                source.label = ''
                ch.source = ''

    # Try to get channel source
    if ch.override and ch.override_type != 'DEFAULT':
        source_label = root_ch.name + ' Override : ' + ch.override_type

        src_tree = get_channel_source_tree(ch, layer)

        cache = layer_tree.nodes.get(getattr(ch, 'cache_' + ch.override_type.lower()))
        if cache:
            # Delete non cached source
            if prev_type == 'DEFAULT':
                remove_node(layer_tree, ch, 'source')

            ch.source = cache.name
            setattr(ch, 'cache_' + ch.override_type.lower(), '')

            cache.label = source_label
        else:
            if ch.override_type == 'VCOL':
                source = replace_new_node(src_tree, ch, 'source', get_vcol_bl_idname(), source_label)
            else:
                source = replace_new_node(src_tree, ch, 'source', 'ShaderNodeTex' + ch.override_type.capitalize(), source_label)

    else:
        remove_node(layer_tree, ch, 'source')

    # Update linear stuff
    check_layer_channel_linear_node(ch, layer, root_ch, reconnect=True)

    # Enable source tree back again
    if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and channel_enabled and ch.override:
        enable_channel_source_tree(layer, root_ch, ch)
        Modifier.enable_modifiers_tree(ch)

def check_blend_type_nodes(root_ch, layer, ch):

    #print("Checking blend type nodes. Layer: " + layer.name + ' Channel: ' + root_ch.name)

    yp = layer.id_data.yp
    tree = get_tree(layer)
    nodes = tree.nodes
    blend = nodes.get(ch.blend)

    need_reconnect = False

    # Update normal map nodes
    need_reconnect = check_channel_normal_map_nodes(tree, layer, root_ch, ch, need_reconnect)

    # Extra alpha
    need_reconnect = check_extra_alpha(layer, need_reconnect)

    has_parent = layer.parent_idx != -1

    # Check if channel is enabled
    channel_enabled = is_blend_node_needed(ch, layer, root_ch)

    # Background layer always using mix blend type
    if layer.type == 'BACKGROUND':
        blend_type = 'MIX'
    else: blend_type = ch.blend_type

    # Layer intensity nodes
    if channel_enabled:
        layer_intensity = tree.nodes.get(ch.layer_intensity)
        if not layer_intensity:
            layer_intensity = new_node(tree, ch, 'layer_intensity', 'ShaderNodeMath', 'Layer Opacity')
            layer_intensity.operation = 'MULTIPLY'
    else:
        if remove_node(tree, ch, 'layer_intensity'): need_reconnect = True

    if root_ch.type in {'RGB', 'VALUE'}:
        if channel_enabled:
            if root_ch.type == 'RGB':
                if (has_parent or is_channel_alpha_enabled(root_ch)) and blend_type == 'MIX':

                    if (
                            layer.type == 'BACKGROUND' and not 
                            (ch.enable_transition_ramp and ch.transition_ramp_intensity_unlink 
                                and ch.transition_ramp_blend_type == 'MIX') and not 
                            (ch.enable_transition_ramp and layer.parent_idx != -1 and ch.transition_ramp_blend_type == 'MIX')
                        ):
                        blend, need_reconnect = replace_new_node(
                            tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG,
                            return_status=True, hard_replace=True, dirty=need_reconnect
                        )

                    else: 
                        blend, need_reconnect = replace_new_node(
                            tree, ch, 'blend',  'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER, 
                            return_status=True, hard_replace=True, dirty=need_reconnect
                        )

                else:
                    blend, need_reconnect = replace_new_mix_node(
                        tree, ch, 'blend', 'Blend',
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )
            elif root_ch.type == 'VALUE':

                if (has_parent or is_channel_alpha_enabled(root_ch)) and blend_type == 'MIX':
                    if layer.type == 'BACKGROUND':
                        blend, need_reconnect = replace_new_node(
                            tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_BW, 
                            return_status=True, hard_replace=True, dirty=need_reconnect
                        )
                    else:
                        blend, need_reconnect = replace_new_node(
                            tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BW, 
                            return_status=True, hard_replace=True, dirty=need_reconnect
                        )
                else:

                    blend, need_reconnect = replace_new_mix_node(
                        tree, ch, 'blend', 'Blend',
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )

            if blend.type in {'MIX_RGB', 'MIX'} and blend.blend_type != blend_type:
                blend.blend_type = blend_type

            if blend.type == 'GROUP' and 'Clamp' in blend.inputs:
                blend.inputs['Clamp'].default_value = 1.0 if ch.use_clamp else 0.0
            else: set_mix_clamp(blend, ch.use_clamp)

            # Intensity nodes
            intensity = tree.nodes.get(ch.intensity)
            if not intensity:
                intensity = new_node(tree, ch, 'intensity', 'ShaderNodeMath', 'Channel Opacity')
                intensity.operation = 'MULTIPLY'

            # Channel intensity
            #intensity.inputs[1].default_value = ch.intensity_value

        else:
            if remove_node(tree, ch, 'blend'): need_reconnect = True
            if remove_node(tree, ch, 'intensity'): need_reconnect = True
            if remove_node(tree, ch, 'extra_alpha'): need_reconnect = True

    elif root_ch.type == 'NORMAL':

        if channel_enabled and (is_layer_using_normal_map(layer) or is_channel_alpha_enabled(root_ch)):

            #if has_parent and ch.normal_blend_type == 'MIX':
            if (has_parent or is_channel_alpha_enabled(root_ch)) and ch.normal_blend_type in {'MIX', 'COMPARE'}:
                if layer.type == 'BACKGROUND':
                    blend, need_reconnect = replace_new_node(
                        tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_VEC, 
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )
                else:
                    blend, need_reconnect = replace_new_node(
                        tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_VEC, 
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )

            elif ch.normal_blend_type == 'OVERLAY':
                if has_parent:
                    blend, need_reconnect = replace_new_node(
                        tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.OVERLAY_NORMAL_STRAIGHT_OVER, 
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )
                else:
                    blend, need_reconnect = replace_new_node(
                        tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.OVERLAY_NORMAL, 
                        return_status=True, hard_replace=True, dirty=need_reconnect
                    )

            elif ch.normal_blend_type in {'MIX', 'COMPARE'}:
                blend, need_reconnect = replace_new_node(
                    tree, ch, 'blend', 'ShaderNodeGroup', 'Blend', lib.VECTOR_MIX, 
                    return_status=True, hard_replace=True, dirty=need_reconnect
                )

        elif channel_enabled and ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':

            blend, need_reconnect = replace_new_mix_node(
                tree, ch, 'blend', 'Blend',
                return_status=True, hard_replace=True, dirty=need_reconnect
            )
            blend.blend_type = 'ADD' if ch.normal_blend_type == 'OVERLAY' else 'MIX'

        else:
            if remove_node(tree, ch, 'blend'): need_reconnect = True

        if channel_enabled and ((layer.type == 'GROUP' and is_layer_using_normal_map(layer) and not is_normal_process_needed(layer)) or
                (layer.type != 'GROUP' and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP', 'VECTOR_DISPLACEMENT_MAP'} and not ch.enable_transition_bump)
                ):
            # Intensity nodes
            intensity = tree.nodes.get(ch.intensity)
            if not intensity:
                intensity = new_node(tree, ch, 'intensity', 'ShaderNodeMath', 'Channel Intensity')
                intensity.operation = 'MULTIPLY'

            # Channel intensity
            intensity.inputs[1].default_value = ch.intensity_value

        else:
            if remove_node(tree, ch, 'intensity'): need_reconnect = True

    # Update preview mode node
    if yp.layer_preview_mode:
        mat = bpy.context.object.active_material
        preview = mat.node_tree.nodes.get(EMISSION_VIEWER)
        if preview: update_preview_mix(ch, preview)

    return need_reconnect

def check_extra_alpha(layer, need_reconnect=False):

    yp = layer.id_data.yp

    disp_ch = get_height_channel(layer)
    if not disp_ch: return

    tree = get_tree(layer)

    for i, ch in enumerate(layer.channels):
        if disp_ch == ch: continue

        root_ch = yp.channels[i]
        channel_enabled = is_blend_node_needed(ch, layer, root_ch)

        extra_alpha = tree.nodes.get(ch.extra_alpha)

        if channel_enabled and disp_ch.enable and disp_ch.normal_blend_type == 'COMPARE':

            if not extra_alpha:
                extra_alpha = new_node(tree, ch, 'extra_alpha', 'ShaderNodeMath', 'Extra Alpha')
                extra_alpha.operation = 'MULTIPLY'
                need_reconnect = True

        elif extra_alpha:
            remove_node(tree, ch, 'extra_alpha')
            need_reconnect = True

    return need_reconnect

def check_layer_channel_linear_node(ch, layer=None, root_ch=None, reconnect=False):

    yp = ch.id_data.yp

    if not layer or not root_ch:
        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        layer = yp.layers[int(match.group(1))]
        root_ch = yp.channels[int(match.group(2))]

    source_tree = get_channel_source_tree(ch, layer)

    image = None
    source = None
    if ch.override and ch.override_type == 'IMAGE':
        source = source_tree.nodes.get(ch.source)
        if source: image = source.image
    elif layer.type == 'IMAGE':
        source = get_layer_source(layer)
        if source: image = source.image

    channel_enabled = get_channel_enabled(ch, layer, root_ch)

    if channel_enabled and ((
            not yp.use_linear_blending 
            and ch.override 
            and (
                (image and is_image_source_srgb(image, source, root_ch)) or 
                (
                    ch.override_type not in {'IMAGE'}
                    and root_ch.type != 'NORMAL' 
                    and root_ch.colorspace == 'SRGB' 
                ))
        ) or (
            not yp.use_linear_blending
            and not ch.override 
            and root_ch.type != 'NORMAL' 
            and root_ch.colorspace == 'SRGB' 
            and (
                (not ch.gamma_space and ch.layer_input == 'RGB' and layer.type not in {'IMAGE', 'BACKGROUND', 'GROUP'})
                or (layer.type == 'IMAGE' and image.is_float and image.colorspace_settings.name != get_srgb_name()) # Float images need to converted to linear for some reason in Blender
                )
        ) or (
            yp.use_linear_blending
            and not ch.override_1
            and root_ch.type == 'NORMAL'
            and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}
            and source and source.image and not source.image.is_float #and is_image_source_srgb(image, source) # NOTE: No need for channel linear if the image is float
        )):
        if root_ch.type == 'VALUE':
            linear = replace_new_node(source_tree, ch, 'linear', 'ShaderNodeMath', 'Linear')
            linear.operation = 'POWER'
        else: linear = replace_new_node(source_tree, ch, 'linear', 'ShaderNodeGamma', 'Linear')

        linear.inputs[1].default_value = 1.0 / GAMMA

    elif channel_enabled and (
            yp.use_linear_blending
            and root_ch.type != 'NORMAL' 
            and root_ch.colorspace == 'SRGB' 
            and (
                (ch.gamma_space and ch.layer_input == 'RGB' and layer.type not in {'IMAGE', 'BACKGROUND', 'GROUP'})
                #or (layer.type == 'IMAGE' and image.is_float and image.colorspace_settings.name == get_srgb_name()) 
                )
        ):
        if root_ch.type == 'VALUE':
            linear = replace_new_node(source_tree, ch, 'linear', 'ShaderNodeMath', 'Linear')
            linear.operation = 'POWER'
        else: linear = replace_new_node(source_tree, ch, 'linear', 'ShaderNodeGamma', 'Linear')

        linear.inputs[1].default_value = GAMMA

    else:
        remove_node(source_tree, ch, 'linear')

    image_1 = None
    layer_tree = get_tree(layer)
    if ch.override_1 and ch.override_1_type == 'IMAGE':
        source_1 = layer_tree.nodes.get(ch.source_1)
        if source_1: image_1 = source_1.image

    if channel_enabled and ch.override_1 and image_1 and is_image_source_srgb(image_1, source_1):
        linear_1 = replace_new_node(layer_tree, ch, 'linear_1', 'ShaderNodeGamma', 'Linear 1')
        linear_1.inputs[1].default_value = 1.0 / GAMMA
    else:
        remove_node(layer_tree, ch, 'linear_1')

    if reconnect:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

    return image

def check_layer_image_linear_node(layer, source_tree=None):

    yp = layer.id_data.yp

    if not source_tree: source_tree = get_source_tree(layer)

    if get_layer_enabled(layer) and layer.type == 'IMAGE':

        source = source_tree.nodes.get(layer.source)
        image = source.image
        if not image: return

        # Create linear if image type is srgb or float image
        if is_image_source_srgb(image, source) and (not yp.use_linear_blending or (yp.use_linear_blending and image.is_float)):
            linear = source_tree.nodes.get(layer.linear)
            if not linear:
                linear = new_node(source_tree, layer, 'linear', 'ShaderNodeGamma', 'Linear')
                linear.inputs[1].default_value = 1.0 / GAMMA

            return

        elif yp.use_linear_blending and not image.is_float and not is_image_source_srgb(image, source):
            linear = source_tree.nodes.get(layer.linear)
            if not linear:
                linear = new_node(source_tree, layer, 'linear', 'ShaderNodeGamma', 'Linear')
                linear.inputs[1].default_value = GAMMA

            return

    # Delete linear
    remove_node(source_tree, layer, 'linear')

def check_mask_image_linear_node(mask, mask_tree=None):

    if not mask_tree: mask_tree = get_mask_tree(mask)

    if get_mask_enabled(mask) and mask.type == 'IMAGE':

        source = mask_tree.nodes.get(mask.source)
        image = source.image

        if not image: return

        # Create linear if image type is srgb
        if is_image_source_srgb(image, source):
            linear = mask_tree.nodes.get(mask.linear)
            if not linear:
                linear = new_node(mask_tree, mask, 'linear', 'ShaderNodeGamma', 'Linear')
                linear.inputs[1].default_value = 1.0 / GAMMA

            return

    # Delete linear
    remove_node(mask_tree, mask, 'linear')

def check_yp_linear_nodes(yp, specific_layer=None, reconnect=True):
    for layer in yp.layers:
        if specific_layer and layer != specific_layer: continue
        image_found = False
        if layer.type == 'IMAGE':
            check_layer_image_linear_node(layer)
            image_found = True
        for ch in layer.channels:
            #if ch.override_type == 'IMAGE' or ch.override_1_type == 'IMAGE':
            if check_layer_channel_linear_node(ch):
                image_found = True
        for mask in layer.masks:
            if mask.type == 'IMAGE':
                check_mask_image_linear_node(mask)
                image_found = True

        #if image_found and reconnect:
        if reconnect:
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)
