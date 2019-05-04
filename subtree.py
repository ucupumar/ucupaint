import bpy, re
from . import lib, Modifier, MaskModifier
from .common import *
from .node_arrangements import *
from .node_connections import *

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
    inp = source_tree.inputs.get('Vector')
    if not inp: source_tree.inputs.new('NodeSocketVector', 'Vector')

    out = source_tree.outputs.get('Color')
    if not out: source_tree.outputs.new('NodeSocketColor', 'Color')

    out = source_tree.outputs.get('Alpha')
    if not out: source_tree.outputs.new('NodeSocketFloat', 'Alpha')

    col1 = source_tree.outputs.get('Color 1')
    alp1 = source_tree.outputs.get('Alpha 1')
    #solid = source_tree.nodes.get(ONE_VALUE)

    if layer_type != 'IMAGE':

        if not col1: col1 = source_tree.outputs.new('NodeSocketColor', 'Color 1')
        if not alp1: alp1 = source_tree.outputs.new('NodeSocketFloat', 'Alpha 1')

        #if not solid:
        #    solid = source_tree.nodes.new('ShaderNodeValue')
        #    solid.outputs[0].default_value = 1.0
        #    solid.name = ONE_VALUE
    else:
        if col1: source_tree.outputs.remove(col1)
        if alp1: source_tree.outputs.remove(alp1)
        #if solid: source_tree.nodes.remove(solid)

def enable_layer_source_tree(layer, rearrange=False):

    # Check if source tree is already available
    #if layer.type in {'BACKGROUND', 'COLOR', 'GROUP'}: return
    if layer.type in {'BACKGROUND', 'COLOR'}: return
    if layer.type != 'VCOL' and layer.source_group != '': return

    layer_tree = get_tree(layer)

    if layer.type not in {'VCOL', 'GROUP'}:
        # Get current source for reference
        source_ref = layer_tree.nodes.get(layer.source)
        mapping_ref = layer_tree.nodes.get(layer.mapping)

        # Create source tree
        source_tree = bpy.data.node_groups.new(LAYERGROUP_PREFIX + layer.name + ' Source', 'ShaderNodeTree')

        #source_tree.outputs.new('NodeSocketFloat', 'Factor')

        create_essential_nodes(source_tree, True)

        refresh_source_tree_ios(source_tree, layer.type)

        # Copy source from reference
        source = new_node(source_tree, layer, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(source_tree, layer, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

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
        if mapping_ref: layer_tree.nodes.remove(mapping_ref)
    
        # Bring modifiers to source tree
        if layer.type == 'IMAGE':
            for mod in layer.modifiers:
                Modifier.add_modifier_nodes(mod, source_tree, layer_tree)
        else:
            move_mod_group(layer, layer_tree, source_tree)

    # Create uv neighbor
    #if layer.type in {'VCOL', 'GROUP'}:
    if layer.type in {'VCOL'}:
        uv_neighbor = replace_new_node(layer_tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                lib.NEIGHBOR_FAKE, hard_replace=True)
    #else: 
    elif layer.type != 'GROUP': 
        uv_neighbor = replace_new_node(layer_tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV', 
                lib.get_neighbor_uv_tree_name(layer.texcoord_type), hard_replace=True)
        set_uv_neighbor_resolution(layer, uv_neighbor)

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def disable_layer_source_tree(layer, rearrange=True):

    #if layer.type == 'VCOL': return

    yp = layer.id_data.yp

    # Check if fine bump map is used on some of layer channels
    fine_bump_found = False
    #blur_found = False
    #for i, ch in enumerate(layer.channels):
    #    if yp.channels[i].type == 'NORMAL' and (ch.normal_map_type == 'FINE_BUMP_MAP' 
    #            or (ch.enable_transition_bump and ch.transition_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'})):
    #        fine_bump_found = True
    #    #if hasattr(ch, 'enable_blur') and ch.enable_blur:
    #    #    blur_found =True
    for root_ch in yp.channels:
        if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
            fine_bump_found = True

    if (layer.type != 'VCOL' and layer.source_group == '') or fine_bump_found: return #or blur_found: return

    layer_tree = get_tree(layer)

    if layer.type != 'VCOL':
        source_group = layer_tree.nodes.get(layer.source_group)
        source_ref = source_group.node_tree.nodes.get(layer.source)
        mapping_ref = source_group.node_tree.nodes.get(layer.mapping)

        # Create new source
        source = new_node(layer_tree, layer, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(layer_tree, layer, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

        # Bring back layer modifier to original tree
        if layer.type == 'IMAGE':
            for mod in layer.modifiers:
                Modifier.add_modifier_nodes(mod, layer_tree, source_group.node_tree)
        else:
            move_mod_group(layer, source_group.node_tree, layer_tree)

        # Remove previous source
        remove_node(layer_tree, layer, 'source_group')
        remove_node(layer_tree, layer, 'source_n')
        remove_node(layer_tree, layer, 'source_s')
        remove_node(layer_tree, layer, 'source_e')
        remove_node(layer_tree, layer, 'source_w')

    remove_node(layer_tree, layer, 'uv_neighbor')

    if rearrange:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def set_mask_uv_neighbor(tree, layer, mask):

    yp = layer.id_data.yp

    # NOTE: Checking transition bump everytime this function called is not that tidy
    # Check if transition bump channel is available
    bump_ch = get_transition_bump_channel(layer)
    #if bump_ch and bump_ch.transition_bump_type == 'BUMP_MAP':
    #    #return False
    #    bump_ch = None

    smooth_chs = get_smooth_bump_channels(layer)

    if not bump_ch:
        bump_ch = smooth_chs[0]

    # Check transition bump chain
    if not any(smooth_chs) and bump_ch:
        match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        mask_idx = int(match.group(2))

        chain = get_bump_chain(layer, bump_ch)
        if mask_idx >= chain:
            return False

    dirty = False

    uv_neighbor = tree.nodes.get(mask.uv_neighbor)
    if not uv_neighbor:
        uv_neighbor = new_node(tree, mask, 'uv_neighbor', 'ShaderNodeGroup', 'Mask UV Neighbor')
        dirty = True

    if mask.type == 'VCOL':
        uv_neighbor.node_tree = get_node_tree_lib(lib.NEIGHBOR_FAKE)
    else:

        different_uv = mask.texcoord_type == 'UV' and layer.uv_name != mask.uv_name

        # Check number of input
        prev_num_inputs = len(uv_neighbor.inputs)

        # Get new uv neighbor tree
        uv_neighbor.node_tree = lib.get_neighbor_uv_tree(mask.texcoord_type, different_uv)

        # Check current number of input
        cur_num_inputs = len(uv_neighbor.inputs)

        # Need reconnect of number of inputs different
        if prev_num_inputs != cur_num_inputs:
            dirty = True

        set_uv_neighbor_resolution(mask, uv_neighbor)

        #if different_uv:
        #    tangent = tree.nodes.get(mask.tangent)
        #    tangent_flip = tree.nodes.get(mask.tangent_flip)
        #    bitangent = tree.nodes.get(mask.bitangent)
        #    bitangent_flip = tree.nodes.get(mask.bitangent_flip)

        #    if not tangent:
        #        tangent = new_node(tree, mask, 'tangent', 'ShaderNodeNormalMap', 'Tangent')
        #        tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)
        #        dirty = True

        #    if not tangent_flip:
        #        tangent_flip = new_node(tree, mask, 'tangent_flip', 'ShaderNodeGroup', 'Tangent Backface Flip')
        #        tangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_TANGENT)

        #        set_tangent_backface_flip(tangent_flip, yp.flip_backface)

        #    if not bitangent:
        #        bitangent = new_node(tree, mask, 'bitangent', 'ShaderNodeNormalMap', 'Bitangent')
        #        bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)
        #        dirty = True

        #    if not bitangent_flip:
        #        bitangent_flip = new_node(tree, mask, 'bitangent_flip', 'ShaderNodeGroup', 'Bitangent Backface Flip')
        #        bitangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_BITANGENT)

        #        set_bitangent_backface_flip(bitangent_flip, yp.flip_backface)

        #    tangent.uv_map = mask.uv_name
        #    bitangent.uv_map = mask.uv_name
        #else:
        #    remove_node(tree, mask, 'tangent')
        #    remove_node(tree, mask, 'bitangent')
        #    remove_node(tree, mask, 'tangent_flip')
        #    remove_node(tree, mask, 'bitangent_flip')

    return dirty

def enable_mask_source_tree(layer, mask, reconnect = False):

    # Check if source tree is already available
    if mask.type != 'VCOL' and mask.group_node != '': return

    layer_tree = get_tree(layer)

    if mask.type != 'VCOL':
        # Get current source for reference
        source_ref = layer_tree.nodes.get(mask.source)
        mapping_ref = layer_tree.nodes.get(mask.mapping)

        # Create mask tree
        mask_tree = bpy.data.node_groups.new(MASKGROUP_PREFIX + mask.name, 'ShaderNodeTree')

        # Create input and outputs
        mask_tree.inputs.new('NodeSocketVector', 'Vector')
        #mask_tree.outputs.new('NodeSocketColor', 'Color')
        mask_tree.outputs.new('NodeSocketFloat', 'Value')

        create_essential_nodes(mask_tree)
        #start = mask_tree.nodes.new('NodeGroupInput')
        #start.name = TREE_START
        #end = mask_tree.nodes.new('NodeGroupOutput')
        #end.name = TREE_END

        # Copy nodes from reference
        source = new_node(mask_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(mask_tree, mask, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

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
        if mapping_ref: layer_tree.nodes.remove(mapping_ref)

    # Create uv neighbor
    set_mask_uv_neighbor(layer_tree, layer, mask)

    if reconnect:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def disable_mask_source_tree(layer, mask, reconnect=False):

    # Check if source tree is already gone
    if mask.type != 'VCOL' and mask.group_node == '': return

    layer_tree = get_tree(layer)

    if mask.type != 'VCOL':

        mask_tree = get_mask_tree(mask)

        source_ref = mask_tree.nodes.get(mask.source)
        mapping_ref = mask_tree.nodes.get(mask.mapping)
        group_node = layer_tree.nodes.get(mask.group_node)

        # Create new nodes
        source = new_node(layer_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(layer_tree, mask, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

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

    remove_node(layer_tree, mask, 'uv_neighbor')

    if reconnect:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def check_create_spread_alpha(layer, tree, root_ch, ch):

    skip = False
    if layer.type in {'BACKGROUND', 'GROUP'}: #or is_valid_to_remove_bump_nodes(layer, ch):
        skip = True

    if not skip and ch.normal_map_type != 'NORMAL_MAP': # and ch.enable_transition_bump:
        spread_alpha = replace_new_node(tree, ch, 'spread_alpha', 
                'ShaderNodeGroup', 'Spread Alpha Hack', lib.SPREAD_ALPHA)
    else:
        remove_node(tree, ch, 'spread_alpha')

    if not skip and root_ch.enable_smooth_bump and ch.normal_map_type != 'NORMAL_MAP': # and ch.enable_transition_bump:
        for d in neighbor_directions:
            bb = replace_new_node(tree, ch, 'spread_alpha_' + d, 
                    'ShaderNodeGroup', 'Spread Alpha ' + d, lib.SPREAD_ALPHA) 
    else:
        for d in neighbor_directions:
            remove_node(tree, ch, 'spread_alpha_' + d)

    #remove_node(tree, ch, 'bump_base')
    #for d in neighbor_directions:
    #    remove_node(tree, ch, 'bump_base_' + d)

def save_transition_bump_falloff_cache(tree, ch):
    tb_falloff = tree.nodes.get(ch.tb_falloff)

    if (
            (ch.transition_bump_falloff_type != 'CURVE' or not ch.transition_bump_falloff or 
                not ch.enable_transition_bump or not ch.enable) and 
            check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE)):
        cache = tree.nodes.get(ch.cache_falloff_curve)
        if not cache:
            cache = new_node(tree, ch, 'cache_falloff_curve', 'ShaderNodeRGBCurve', 'Falloff Curve Cache')
        curve_ref = tb_falloff.node_tree.nodes.get('_curve')
        copy_node_props(curve_ref, cache)

def check_transition_bump_falloff(layer, tree, trans_bump, trans_bump_flip):

    yp = layer.id_data.yp

    # Transition bump falloff
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        if ch != trans_bump: continue

        save_transition_bump_falloff_cache(tree, ch)

        if ch.transition_bump_falloff:

            # Emulated curve without actual curve
            if ch.transition_bump_falloff_type == 'EMULATED_CURVE':
                tb_falloff = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                        lib.EMULATED_CURVE, hard_replace=True)
                tb_falloff.inputs[1].default_value = get_transition_bump_falloff_emulated_curve_value(ch)

            elif ch.transition_bump_falloff_type == 'CURVE':
                tb_falloff = tree.nodes.get(ch.tb_falloff)
                if not check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE):

                    # Check cached curve
                    cache = tree.nodes.get(ch.cache_falloff_curve)

                    tb_falloff = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                            lib.FALLOFF_CURVE, hard_replace=True)
                    duplicate_lib_node_tree(tb_falloff)

                    if cache:
                        curve = tb_falloff.node_tree.nodes.get('_curve')
                        copy_node_props(cache, curve)
                        remove_node(tree, ch, 'cache_falloff_curve')

                inv0 = tb_falloff.node_tree.nodes.get('_inverse_0')
                inv1 = tb_falloff.node_tree.nodes.get('_inverse_1')
                inv0.mute = not ch.transition_bump_flip
                inv1.mute = not ch.transition_bump_flip

        else:
            remove_node(tree, ch, 'tb_falloff')

        if ch.transition_bump_falloff and root_ch.enable_smooth_bump:
            for d in neighbor_directions:

                if ch.transition_bump_falloff_type == 'EMULATED_CURVE':
                    tbf = replace_new_node(tree, ch, 'tb_falloff_' + d, 'ShaderNodeGroup', 'Falloff ' + d, 
                            lib.EMULATED_CURVE, hard_replace=True)
                    tbf.inputs[1].default_value = get_transition_bump_falloff_emulated_curve_value(ch)

                elif ch.transition_bump_falloff_type == 'CURVE':
                    tbf = replace_new_node(tree, ch, 'tb_falloff_' + d, 'ShaderNodeGroup', 'Falloff ' + d, 
                            tb_falloff.node_tree.name, hard_replace=True)
        else:
            for d in neighbor_directions:
                remove_node(tree, ch, 'tb_falloff_' + d)

def check_mask_mix_nodes(layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    trans_bump = get_transition_bump_channel(layer)

    trans_bump_flip = False
    if trans_bump:
        trans_bump_flip = trans_bump.transition_bump_flip #or layer.type == 'BACKGROUND'

        # Update transition bump falloff
        check_transition_bump_falloff(layer, tree, trans_bump, trans_bump_flip)

    for i, mask in enumerate(layer.masks):
        for j, c in enumerate(mask.channels):

            ch = layer.channels[j]
            root_ch = yp.channels[j]

            mute = not c.enable or not mask.enable or not layer.enable_masks

            if root_ch.type == 'NORMAL' and not trans_bump:
                chain = min(ch.transition_bump_chain, len(layer.masks))
            elif trans_bump:
                chain = min(trans_bump.transition_bump_chain, len(layer.masks))
            else: chain = -1

            mix = tree.nodes.get(c.mix)
            if not mix:
                mix = new_node(tree, c, 'mix', 'ShaderNodeMixRGB', 'Mask Blend')
                mix.blend_type = mask.blend_type
                mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                if yp.disable_quick_toggle:
                    mix.mute = mute
                else: mix.mute = False

            if root_ch.type == 'NORMAL':

                if i >= chain and trans_bump and ch == trans_bump:
                    mix_pure = tree.nodes.get(c.mix_pure)
                    if not mix_pure:
                        mix_pure = new_node(tree, c, 'mix_pure', 'ShaderNodeMixRGB', 'Mask Blend Pure')
                        mix_pure.blend_type = mask.blend_type
                        mix_pure.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_pure.mute = mute
                        else: mix_pure.mute = False

                else:
                    remove_node(tree, c, 'mix_pure')

                if i >= chain and (
                    #(trans_bump and ch == trans_bump and ch.transition_bump_crease and not ch.write_height) or
                    (trans_bump and ch == trans_bump and ch.transition_bump_crease) or
                    (not trans_bump)
                    ):
                    mix_remains = tree.nodes.get(c.mix_remains)
                    if not mix_remains:
                        mix_remains = new_node(tree, c, 'mix_remains', 'ShaderNodeMixRGB', 'Mask Blend Remaining')
                        mix_remains.blend_type = mask.blend_type
                        mix_remains.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_remains.mute = mute
                        else: mix_remains.mute = False
                else:
                    remove_node(tree, c, 'mix_remains')

                if (
                    #(not trans_bump and ch.normal_map_type in {'FINE_BUMP_MAP'}) or
                    #(trans_bump == ch and ch.transition_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}) 
                    #ch.normal_map_type == 'FINE_BUMP_MAP' and
                    root_ch.enable_smooth_bump and
                    (ch.write_height or (not ch.write_height and i < chain))
                    #) and i < chain):
                    ):

                    for d in neighbor_directions:
                        mix = tree.nodes.get(getattr(c, 'mix_' + d))

                        if not mix:
                            mix = new_node(tree, c, 'mix_' + d, 'ShaderNodeMixRGB', 'Mask Blend ' + d)
                            mix.blend_type = mask.blend_type
                            mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                            if yp.disable_quick_toggle:
                                mix.mute = mute
                            else: mix.mute = False

                #elif i >= chain and (
                #        (not trans_bump_flip and ch.transition_bump_crease) #or 
                #        #ch.normal_map_type == 'BUMP_MAP'
                #        ):

                #    mix_n = tree.nodes.get(c.mix_n)
                #    if not mix_n:
                #        mix_n = new_node(tree, c, 'mix_n', 'ShaderNodeMixRGB', 'Mask Blend n')
                #        mix_n.blend_type = mask.blend_type
                #        mix_n.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                #        if yp.disable_quick_toggle:
                #            mix_n.mute = mute
                #        else: mix_n.mute = False

                #    for d in ['s', 'e', 'w']:
                #        remove_node(tree, c, 'mix_' + d)
                else:
                    for d in neighbor_directions:
                        remove_node(tree, c, 'mix_' + d)

                if layer.type == 'GROUP':
                    mix_normal = tree.nodes.get(c.mix_normal)
                    if not mix_normal:
                        mix_normal = new_node(tree, c, 'mix_normal', 'ShaderNodeMixRGB', 'Mask Normal')
                        mix_normal.blend_type = mask.blend_type
                        mix_normal.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_normal.mute = mute
                        else: mix_normal.mute = False
                else:
                    remove_node(tree, c, 'mix_normal')

            else: 
                if (trans_bump and i >= chain and (
                    (trans_bump_flip and ch.enable_transition_ramp) or 
                    #(not trans_bump_flip and ch.enable_transition_ramp and ch.transition_ramp_intensity_unlink) or
                    (not trans_bump_flip and ch.enable_transition_ao)
                    )):
                    mix_n = tree.nodes.get(c.mix_n)

                    if not mix_n:
                        mix_n = new_node(tree, c, 'mix_n', 'ShaderNodeMixRGB', 'Mask Blend n')
                        mix_n.blend_type = mask.blend_type
                        mix_n.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_n.mute = mute
                        else: mix_n.mute = False
                else:
                    remove_node(tree, c, 'mix_n')

def check_mask_source_tree(layer): #, ch=None):

    yp = layer.id_data.yp

    smooth_bump_chs = get_smooth_bump_channels(layer)
    write_height_chs = get_write_height_normal_channels(layer)

    if any(smooth_bump_chs):
        chain = get_bump_chain(layer)
    else: chain = -1

    for i, mask in enumerate(layer.masks):
        if any(smooth_bump_chs) and (any(write_height_chs) or i < chain):
            enable_mask_source_tree(layer, mask)
        else:
            disable_mask_source_tree(layer, mask)

    ## Try to get transition bump
    #trans_bump = get_transition_bump_channel(layer)

    ## Try to get fine bump if transition bump is not found
    #fine_bump = None
    #if not trans_bump:
    #    chs = [c for i,c in enumerate(layer.channels) 
    #            if c.normal_map_type == 'FINE_BUMP_MAP' and yp.channels[i].type == 'NORMAL']
    #    if chs: fine_bump = chs[0]

    #if trans_bump:
    #    chain = min(trans_bump.transition_bump_chain, len(layer.masks))
    #elif fine_bump:
    #    chain = min(fine_bump.transition_bump_chain, len(layer.masks))
    #else: chain = -1

    #for i, mask in enumerate(layer.masks):

    #    if (
    #        (trans_bump and trans_bump.write_height) or
    #        (fine_bump and fine_bump.write_height) or
    #        (((trans_bump and trans_bump.transition_bump_type != 'BUMP_MAP') or fine_bump) and i < chain)

    #        ):
    #        enable_mask_source_tree(layer, mask)
    #    else:
    #        disable_mask_source_tree(layer, mask)

def create_uv_nodes(yp, uv_name):

    tree = yp.id_data

    uv = yp.uvs.add()
    uv.name = uv_name

    uv_map = new_node(tree, uv, 'uv_map', 'ShaderNodeUVMap', uv_name)
    uv_map.uv_map = uv_name

    tangent = new_node(tree, uv, 'tangent', 'ShaderNodeNormalMap', uv_name + ' Tangent')
    tangent.uv_map = uv_name
    tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)

    bitangent = new_node(tree, uv, 'bitangent', 'ShaderNodeNormalMap', uv_name + ' Bitangent')
    bitangent.uv_map = uv_name
    bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)

    tangent_flip = new_node(tree, uv, 'tangent_flip', 'ShaderNodeGroup', 
            uv_name + ' Tangent Backface Flip')
    tangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_TANGENT)

    set_tangent_backface_flip(tangent_flip, yp.flip_backface)

    bitangent_flip = new_node(tree, uv, 'bitangent_flip', 'ShaderNodeGroup', 
            uv_name + ' Bitangent Backface Flip')
    bitangent_flip.node_tree = get_node_tree_lib(lib.FLIP_BACKFACE_BITANGENT)

    set_bitangent_backface_flip(bitangent_flip, yp.flip_backface)

def check_parallax_process_outputs(yp, parallax):

    tree = yp.id_data

    for uv in yp.uvs:
        
        outp = parallax.node_tree.outputs.get(uv.name)
        if not outp:
            outp = parallax.node_tree.outputs.new('NodeSocketVector', uv.name)

def check_parallax_mix(tree, uv):

    parallax_mix = tree.nodes.get(uv.parallax_mix)

    if not parallax_mix:
        parallax_mix = new_node(tree, uv, 'parallax_mix', 'ShaderNodeMixRGB', uv.name + ' Final Mix')

def check_start_delta_uv_inputs(tree, uv_name):

    start_uv_name = uv_name + START_UV
    delta_uv_name = uv_name + DELTA_UV

    start = tree.inputs.get(start_uv_name)
    if not start:
        tree.inputs.new('NodeSocketVector', start_uv_name)

    delta = tree.inputs.get(delta_uv_name)
    if not delta:
        tree.inputs.new('NodeSocketVector', delta_uv_name)

def check_current_uv_outputs(tree, uv_name):
    current_uv_name = uv_name + CURRENT_UV

    current = tree.outputs.get(current_uv_name)
    if not current:
        tree.outputs.new('NodeSocketVector', current_uv_name)

def check_current_uv_inputs(tree, uv_name):
    current_uv_name = uv_name + CURRENT_UV

    current = tree.inputs.get(current_uv_name)
    if not current:
        tree.inputs.new('NodeSocketVector', current_uv_name)

def check_iterate_current_uv_mix(tree, uv):

    current_uv_mix = check_new_node(tree, uv, 'parallax_current_uv_mix', 'ShaderNodeMixRGB', 
                    uv.name + CURRENT_UV)

def check_depth_source_calculation(tree, uv):

    delta_uv = tree.nodes.get(uv.parallax_delta_uv)

    if not delta_uv:
        delta_uv = new_node(tree, uv, 'parallax_delta_uv', 'ShaderNodeMixRGB', uv.name + DELTA_UV)
        delta_uv.inputs[0].default_value = 1.0
        delta_uv.blend_type = 'MULTIPLY'

    current_uv = tree.nodes.get(uv.parallax_current_uv)

    if not current_uv:
        current_uv = new_node(tree, uv, 'parallax_current_uv', 'ShaderNodeVectorMath', uv.name + CURRENT_UV)
        current_uv.operation = 'SUBTRACT'

def refresh_parallax_depth_source_layers(yp): #, disp_ch):

    parallax = yp.id_data.nodes.get(PARALLAX)
    if not parallax: return

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    for layer in yp.layers:
        node = tree.nodes.get(layer.depth_group_node)
        if not node:
            n = yp.id_data.nodes.get(layer.group_node)
            node = new_node(tree, layer, 'depth_group_node', 'ShaderNodeGroup', layer.name)
            node.node_tree = n.node_tree

def check_parallax_node(yp, disp_ch): #, uv):

    tree = yp.id_data

    parallax = tree.nodes.get(PARALLAX)

    if not parallax:
        parallax = tree.nodes.new('ShaderNodeGroup')
        parallax.name = PARALLAX
        parallax.label = 'Parallax Occlusion Mapping'
        parallax.node_tree = get_node_tree_lib(lib.PARALLAX_OCCLUSION_PROC)

        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
        depth_source_0.node_tree.name += '_Copy'
        
        parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
        duplicate_lib_node_tree(parallax_loop)

        iterate_0 = parallax_loop.node_tree.nodes.get('_iterate_0')
        duplicate_lib_node_tree(iterate_0)

    parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')

    create_delete_iterate_nodes(parallax_loop.node_tree, disp_ch.parallax_num_of_layers)

    parallax.inputs['layer_depth'].default_value = 1.0 / disp_ch.parallax_num_of_layers

    check_parallax_process_outputs(yp, parallax)
    refresh_parallax_depth_source_layers(yp)

    for uv in yp.uvs:

        parallax_prep = tree.nodes.get(uv.parallax_prep)

        if not parallax_prep:
            parallax_prep = new_node(tree, uv, 'parallax_prep', 'ShaderNodeGroup', 
                    uv.name + ' Parallax Preparation')
            parallax_prep.node_tree = get_node_tree_lib(lib.PARALLAX_OCCLUSION_PREP)

        parallax_prep.inputs['depth_scale'].default_value = disp_ch.displacement_height_ratio
        parallax_prep.inputs['ref_plane'].default_value = disp_ch.displacement_ref_plane
        parallax_prep.inputs['Rim Hack'].default_value = 1.0 if disp_ch.parallax_rim_hack else 0.0
        parallax_prep.inputs['Rim Hack Hardness'].default_value = disp_ch.parallax_rim_hack_hardness
        parallax_prep.inputs['layer_depth'].default_value = 1.0 / disp_ch.parallax_num_of_layers

        check_start_delta_uv_inputs(parallax.node_tree, uv.name)
        check_parallax_mix(parallax.node_tree, uv)

        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
        check_start_delta_uv_inputs(depth_source_0.node_tree, uv.name)
        check_current_uv_outputs(depth_source_0.node_tree, uv.name)
        check_depth_source_calculation(depth_source_0.node_tree, uv)

        parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
        check_start_delta_uv_inputs(parallax_loop.node_tree, uv.name)
        check_current_uv_outputs(parallax_loop.node_tree, uv.name)
        check_current_uv_inputs(parallax_loop.node_tree, uv.name)

        iterate_0 = parallax_loop.node_tree.nodes.get('_iterate_0')
        check_start_delta_uv_inputs(iterate_0.node_tree, uv.name)
        check_current_uv_outputs(iterate_0.node_tree, uv.name)
        check_current_uv_inputs(iterate_0.node_tree, uv.name)
        check_iterate_current_uv_mix(iterate_0.node_tree, uv)

    #parallax = tree.nodes.get(uv.parallax)

    #if not parallax:
    #    parallax = new_node(tree, uv, 'parallax', 'ShaderNodeGroup', 
    #            uv.name + ' Parallax')
    #    parallax.node_tree = get_node_tree_lib(lib.PARALLAX_OCCLUSION)
    #    duplicate_lib_node_tree(parallax)

    #parallax.inputs['depth_scale'].default_value = disp_ch.displacement_height_ratio
    #parallax.inputs['ref_plane'].default_value = disp_ch.displacement_ref_plane
    #parallax.inputs['Rim Hack'].default_value = 1.0 if disp_ch.parallax_rim_hack else 0.0
    #parallax.inputs['Rim Hack Hardness'].default_value = disp_ch.parallax_rim_hack_hardness

    ## Search for displacement image
    #baked_disp = tree.nodes.get(disp_ch.baked_disp)
    #if baked_disp and baked_disp.image:
    #    set_parallax_node(yp, parallax, baked_disp.image)

def remove_uv_nodes(uv):
    tree = uv.id_data
    yp = tree.yp

    remove_node(tree, uv, 'uv_map')
    remove_node(tree, uv, 'tangent')
    remove_node(tree, uv, 'tangent_flip')
    remove_node(tree, uv, 'bitangent')
    remove_node(tree, uv, 'bitangent_flip')

    #yp.uvs.remove(uv)

def check_uv_nodes(yp):

    uv_names = []

    # Check for UV needed

    dirty = False

    if yp.baked_uv_name != '':
        uv = yp.uvs.get(yp.baked_uv_name)
        if not uv: 
            dirty = True
            create_uv_nodes(yp, yp.baked_uv_name)
        uv_names.append(yp.baked_uv_name)

    for layer in yp.layers:

        #if layer.texcoord_type == 'UV':
        uv = yp.uvs.get(layer.uv_name)
        if not uv: 
            dirty = True
            create_uv_nodes(yp, layer.uv_name)
        if layer.uv_name not in uv_names: uv_names.append(layer.uv_name)

        for mask in layer.masks:
            if mask.texcoord_type == 'UV':
                uv = yp.uvs.get(mask.uv_name)
                if not uv: 
                    dirty = True
                    create_uv_nodes(yp, mask.uv_name)
                if mask.uv_name not in uv_names: uv_names.append(mask.uv_name)

    # Check for displacement channel
    #if uv_names:
    #disp_ch = None
    #for ch in yp.channels:
    #    if ch.type == 'NORMAL' and ch.enable_parallax:
    #        disp_ch = ch
    #        break

    disp_ch = get_displacement_channel(yp)

    if disp_ch:
        #if yp.baked_uv_name != '':
        #    uv = yp.uvs.get(yp.baked_uv_name)
        #elif uv_names:
        #    uv = yp.uvs.get(uv_names[0])
        #else: uv = None
        #uv = get_parallax_uv(yp, disp_ch)

        #if uv:
        check_parallax_node(yp, disp_ch)

    # Remove unused uv objects
    for i, uv in reversed(list(enumerate(yp.uvs))):
        if uv.name not in uv_names:
            remove_uv_nodes(uv)
            dirty = True
            yp.uvs.remove(i)

    return dirty

def create_input(tree, name, socket_type, valid_inputs, index, 
        dirty = False, min_value=None, max_value=None, default_value=None):

    inp = tree.inputs.get(name)
    if not inp:
        inp = tree.inputs.new(socket_type, name)
        if min_value != None: inp.min_value = min_value
        if max_value != None: inp.max_value = max_value
        if default_value != None: inp.default_value = default_value
        dirty = True
    valid_inputs.append(inp)
    fix_io_index(inp, tree.inputs, index)

    return dirty

def create_output(tree, name, socket_type, valid_outputs, index, dirty=False):

    outp = tree.outputs.get(name)
    if not outp:
        outp = tree.outputs.new(socket_type, name)
        dirty = True
    valid_outputs.append(outp)
    fix_io_index(outp, tree.outputs, index)

    return dirty

def check_layer_tree_ios(layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    dirty = False

    index = 0
    valid_inputs = []
    valid_outputs = []

    has_parent = layer.parent_idx != -1
    
    # Tree input and outputs
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]

        dirty = create_input(tree, root_ch.name, channel_socket_input_bl_idnames[root_ch.type], 
                valid_inputs, index, dirty)

        dirty = create_output(tree, root_ch.name, channel_socket_output_bl_idnames[root_ch.type], 
                valid_outputs, index, dirty)

        index += 1

        # Alpha IO
        if (root_ch.type == 'RGB' and root_ch.enable_alpha) or has_parent:

            name = root_ch.name + io_suffix['ALPHA']

            dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
            dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, index, dirty)

            index += 1

        # Displacement IO
        if root_ch.type == 'NORMAL': # and root_ch.enable_parallax:

            name = root_ch.name + io_suffix['HEIGHT']

            dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
            dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, index, dirty)

            index += 1

            if has_parent:

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']

                dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
                dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, index, dirty)

                index += 1


            if root_ch.enable_smooth_bump:

                for d in neighbor_directions:
                    name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d

                    dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
                    dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, index, dirty)

                    index += 1

                    if has_parent:
                        name = root_ch.name + io_suffix['ALPHA'] + ' ' + d

                        dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
                        dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, index, dirty)

                        index += 1

    # Tree background inputs
    if layer.type in {'BACKGROUND', 'GROUP'}:

        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]

            name = root_ch.name + io_suffix[layer.type]
            dirty = create_input(tree, name, channel_socket_input_bl_idnames[root_ch.type],
                    valid_inputs, index, dirty)
            index += 1

            # Alpha Input
            if root_ch.enable_alpha or layer.type == 'GROUP':

                name = root_ch.name + io_suffix['ALPHA'] + io_suffix[layer.type]
                dirty = create_input(tree, name, 'NodeSocketFloatFactor',
                        valid_inputs, index, dirty)
                index += 1

            # Displacement Input
            #if root_ch.enable_parallax:
            if root_ch.type == 'NORMAL':

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix[layer.type]
                dirty = create_input(tree, name, 'NodeSocketFloat',
                        valid_inputs, index, dirty)
                index += 1

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix[layer.type]
                dirty = create_input(tree, name, 'NodeSocketFloat',
                        valid_inputs, index, dirty)
                index += 1

                if root_ch.enable_smooth_bump:

                    for d in neighbor_directions:
                        name = root_ch.name + io_suffix['HEIGHT'] + ' ' + d + io_suffix[layer.type]

                        dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, index, dirty)
                        index += 1

                        name = (root_ch.name + 
                                #io_suffix['HEIGHT'] + ' ' + 
                                io_suffix['ALPHA'] + ' ' + 
                                d + io_suffix[layer.type])

                        dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, index, dirty)
                        index += 1

    uv_names = [layer.uv_name]

    # Texcoord IO
    name = layer.uv_name + io_suffix['UV']
    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
    index += 1

    name = layer.uv_name + io_suffix['TANGENT']
    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
    index += 1

    name = layer.uv_name + io_suffix['BITANGENT']
    dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
    index += 1

    texcoords = ['UV']
    if layer.texcoord_type != 'UV':
        name = io_names[layer.texcoord_type]
        dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
        index += 1
        texcoords.append(layer.texcoord_type)

    for mask in layer.masks:
        if mask.texcoord_type == 'UV' and mask.uv_name not in uv_names:
            name = mask.uv_name + io_suffix['UV']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
            index += 1

            name = mask.uv_name + io_suffix['TANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
            index += 1

            name = mask.uv_name + io_suffix['BITANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
            index += 1

            uv_names.append(mask.uv_name)

        elif mask.texcoord_type not in texcoords:
            name = io_names[mask.texcoord_type]
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, index, dirty)
            index += 1
            texcoords.append(mask.texcoord_type)

    # Check for invalid io
    for inp in tree.inputs:
        if inp not in valid_inputs:
            tree.inputs.remove(inp)

    for outp in tree.outputs:
        if outp not in valid_outputs:
            tree.outputs.remove(outp)

    return dirty

def update_disp_scale_node(tree, root_ch, ch):

    #if ch.enable_transition_bump:
    #    disp_scale, need_reconnect = replace_new_node(tree, ch, 'disp_scale', 
    #            'ShaderNodeGroup', 'Displacement Scale', lib.HEIGHT_SCALE_TRANS_BUMP, 
    #            return_status = True, hard_replace=True)

    #    disp_scale.inputs['Delta'].default_value = get_transition_disp_delta(ch)
    #    disp_scale.inputs['RGB Max Height'].default_value = ch.bump_distance
    #    disp_scale.inputs['Alpha Max Height'].default_value = get_transition_bump_max_distance(ch)
    #    disp_scale.inputs['Total Max Height'].default_value = get_layer_channel_max_height(layer, ch)

    #else:
    #    disp_scale, need_reconnect = replace_new_node(tree, ch, 'disp_scale', 
    #            'ShaderNodeGroup', 'Displacement Scale', lib.HEIGHT_SCALE, 
    #            return_status = True, hard_replace=True)

    #    disp_scale.inputs['Scale'].default_value = ch.bump_distance #/ max_height

    max_height = get_displacement_max_height(root_ch)
    root_ch.displacement_height_ratio = max_height

def check_channel_normal_map_nodes(tree, layer, root_ch, ch, need_reconnect=False):

    #print("Checking channel normal map nodes. Layer: " + layer.name + ' Channel: ' + root_ch.name)

    yp = layer.id_data.yp
    #if yp.halt_update: return

    if root_ch.type != 'NORMAL': return False
    #if layer.type in {'BACKGROUND', 'GROUP'}: return False
    #if layer.type in {'BACKGROUND'}: return False

    mute = not layer.enable or not ch.enable

    #max_height = get_layer_channel_max_height(layer, ch)
    max_height = get_displacement_max_height(root_ch, layer)

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
            lib_name, return_status = True, hard_replace=True, replaced=need_reconnect)

    if ch.normal_map_type == 'NORMAL_MAP':
        if ch.enable_transition_bump:
            height_proc.inputs['Bump Height'].default_value = get_transition_bump_max_distance(ch)
        else: height_proc.inputs['Bump Height'].default_value = ch.bump_distance
    else:
        if layer.type != 'GROUP':
            height_proc.inputs['Value Max Height'].default_value = ch.bump_distance
        if ch.enable_transition_bump:
            height_proc.inputs['Delta'].default_value = get_transition_disp_delta(layer, ch)
            height_proc.inputs['Transition Max Height'].default_value = get_transition_bump_max_distance(ch)

    height_proc.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    if ch.enable_transition_bump and ch.enable and ch.transition_bump_crease and not ch.transition_bump_flip:
        height_proc.inputs['Crease Factor'].default_value = ch.transition_bump_crease_factor
        height_proc.inputs['Crease Power'].default_value = ch.transition_bump_crease_power

        if not ch.write_height and not root_ch.enable_smooth_bump:
            height_proc.inputs['Remaining Filter'].default_value = 1.0
        else: height_proc.inputs['Remaining Filter'].default_value = 0.0

    # Height Blend

    if ch.normal_blend_type in {'MIX', 'OVERLAY'}:

        if ch.normal_blend_type == 'MIX':

            if layer.parent_idx != -1:
                height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                        lib.STRAIGHT_OVER_HEIGHT_MIX, return_status=True, hard_replace=True, replaced=need_reconnect)
                if ch.write_height:
                    height_blend.inputs['Divide'].default_value = 1.0
                else: height_blend.inputs['Divide'].default_value = 0.0
            else:

                height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeMixRGB', 'Height Blend', 
                        return_status=True, replaced=need_reconnect) #, hard_replace=True)

                height_blend.blend_type = 'MIX'

        elif ch.normal_blend_type == 'OVERLAY':

            if layer.parent_idx != -1:
                height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                        lib.STRAIGHT_OVER_HEIGHT_ADD, return_status=True, hard_replace=True, replaced=need_reconnect)
                if ch.write_height:
                    height_blend.inputs['Divide'].default_value = 1.0
                else: height_blend.inputs['Divide'].default_value = 0.0
            else:
                height_blend, need_reconnect = replace_new_node(
                        tree, ch, 'height_blend', 'ShaderNodeMixRGB', 'Height Blend', 
                        return_status=True, replaced=need_reconnect) #, hard_replace=True)

                height_blend.blend_type = 'ADD'

        if root_ch.enable_smooth_bump:
            for d in neighbor_directions:


                if ch.normal_blend_type == 'MIX':

                    if layer.parent_idx != -1:
                        hb, need_reconnect = replace_new_node(
                                tree, ch, 'height_blend_' + d, 'ShaderNodeGroup', 'Height Blend', 
                                lib.STRAIGHT_OVER_HEIGHT_MIX, return_status=True, hard_replace=True, replaced=need_reconnect)
                        if ch.write_height:
                            hb.inputs['Divide'].default_value = 1.0
                        else: hb.inputs['Divide'].default_value = 0.0
                    else:

                        hb, need_reconnect = replace_new_node(
                            tree, ch, 'height_blend_' + d, 'ShaderNodeMixRGB', 'Height Blend', 
                            return_status=True, replaced=need_reconnect) #, hard_replace=True)

                        hb.blend_type = 'MIX'

                elif ch.normal_blend_type == 'OVERLAY':

                    if layer.parent_idx != -1:
                        hb, need_reconnect = replace_new_node(
                                tree, ch, 'height_blend_' + d, 'ShaderNodeGroup', 'Height Blend', 
                                lib.STRAIGHT_OVER_HEIGHT_ADD, return_status=True, hard_replace=True, replaced=need_reconnect)
                        if ch.write_height:
                            hb.inputs['Divide'].default_value = 1.0
                        else: hb.inputs['Divide'].default_value = 0.0
                    else:

                        hb, need_reconnect = replace_new_node(
                            tree, ch, 'height_blend_' + d, 'ShaderNodeMixRGB', 'Height Blend', 
                            return_status=True, replaced=need_reconnect) #, hard_replace=True)

                        hb.blend_type = 'ADD'

    else:

        height_blend, need_reconnect = replace_new_node(
                tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
                lib.HEIGHT_COMPARE, return_status=True, hard_replace=True, replaced=need_reconnect)

        if root_ch.enable_smooth_bump:
            for d in neighbor_directions:
                hb, need_reconnect = replace_new_node(
                    tree, ch, 'height_blend_' + d, 'ShaderNodeGroup', 'Height Blend', 
                    lib.HEIGHT_COMPARE, return_status=True, hard_replace=True, replaced=need_reconnect)

    if not root_ch.enable_smooth_bump:
        for d in neighbor_directions:
            remove_node(tree, ch, 'normal_flip_' + d)

    #if root_ch.enable_smooth_bump:
    #    if ch.normal_blend_type == 'MIX':
    #        lib_name = lib.HEIGHT_MIX_SMOOTH
    #    elif ch.normal_blend_type == 'OVERLAY':
    #        lib_name = lib.HEIGHT_ADD_SMOOTH
    #    else:
    #        lib_name = lib.HEIGHT_COMPARE_SMOOTH

    #    height_blend, need_reconnect = replace_new_node(
    #            tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
    #            lib_name, return_status = True, hard_replace=True)
    #else:
    #    if ch.normal_blend_type == 'MIX':
    #        height_blend, need_reconnect = replace_new_node(
    #                tree, ch, 'height_blend', 'ShaderNodeMixRGB', 'Height Blend', 
    #                return_status = True, hard_replace=True)
    #        height_blend.blend_type = 'MIX'
    #    elif ch.normal_blend_type == 'OVERLAY':
    #        height_blend, need_reconnect = replace_new_node(
    #                tree, ch, 'height_blend', 'ShaderNodeMixRGB', 'Height Blend', 
    #                return_status = True, hard_replace=True)
    #        height_blend.blend_type = 'ADD'
    #    else:
    #        height_blend, need_reconnect = replace_new_node(
    #                tree, ch, 'height_blend', 'ShaderNodeGroup', 'Height Blend', 
    #                lib.HEIGHT_COMPARE, return_status = True, hard_replace=True)

    # Normal Process
    if ch.normal_map_type == 'NORMAL_MAP':
        if root_ch.enable_smooth_bump:
            if ch.enable_transition_bump:
                lib_name = lib.NORMAL_MAP_PROCESS_SMOOTH_TRANSITION
            else:
                lib_name = lib.NORMAL_MAP_PROCESS_SMOOTH
        else:
            if ch.enable_transition_bump:
                lib_name = lib.NORMAL_MAP_PROCESS_TRANSITION
            else:
                lib_name = lib.NORMAL_MAP_PROCESS
    else:
        if root_ch.enable_smooth_bump:
            lib_name = lib.NORMAL_PROCESS_SMOOTH
        else:
            lib_name = lib.NORMAL_PROCESS

        if layer.type == 'GROUP':
            lib_name += ' Group'

    normal_proc, need_reconnect = replace_new_node(
            tree, ch, 'normal_proc', 'ShaderNodeGroup', 'Normal Process', 
            lib_name, return_status = True, hard_replace=True, replaced=need_reconnect)

    normal_proc.inputs['Max Height'].default_value = max_height
    if root_ch.enable_smooth_bump:
        normal_proc.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

    if 'Intensity' in normal_proc.inputs:
        normal_proc.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    # Normal flip
    if ch.normal_map_type == 'NORMAL_MAP' or root_ch.enable_smooth_bump:
        remove_node(tree, ch, 'normal_flip')
    else:
        normal_flip = replace_new_node(tree, ch, 'normal_flip', 'ShaderNodeGroup', 
                'Normal Backface Flip', lib.FLIP_BACKFACE_BUMP)

        set_bump_backface_flip(normal_flip, yp.flip_backface)

    # Remove deprecated nodes
    remove_node(tree, ch, 'normal_process')
    remove_node(tree, ch, 'height_process')

    # Remove neighbor related nodes
    if root_ch.enable_smooth_bump:
        enable_layer_source_tree(layer)
        Modifier.enable_modifiers_tree(ch)
    else:
        disable_layer_source_tree(layer, False)
        Modifier.disable_modifiers_tree(ch, False)

    # Check spread alpha if its needed
    check_create_spread_alpha(layer, tree, root_ch, ch)

    # Check mask multiplies
    check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    check_mask_source_tree(layer) #, ch)

    #print(need_reconnect)

    return need_reconnect

def get_fine_bump_distance(distance):
    scale = 200
    #if layer.type == 'IMAGE':
    #    source = get_layer_source(layer)
    #    image = source.image
    #    if image: scale = image.size[0] / 10

    #return -1.0 * distance * scale
    return distance * scale

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
        normal_blend_type = 'MIX'
    else: 
        blend_type = ch.blend_type
        normal_blend_type = ch.normal_blend_type

    if root_ch.type == 'RGB':

        if (has_parent or root_ch.enable_alpha) and blend_type == 'MIX':

            if (layer.type == 'BACKGROUND' and not 
                    (ch.enable_transition_ramp and ch.transition_ramp_intensity_unlink 
                        and ch.transition_ramp_blend_type == 'MIX') and not 
                    (ch.enable_transition_ramp and layer.parent_idx != -1 and ch.transition_ramp_blend_type == 'MIX')
                    ):
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG, return_status = True, 
                        hard_replace=True, replaced=need_reconnect)

            else: 
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)

        else:
            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeMixRGB', 'Blend', return_status = True, hard_replace=True, replaced=need_reconnect)

            #if blend.blend_type != blend_type:
            #    blend.blend_type = blend_type

    elif root_ch.type == 'NORMAL':

        if has_parent and normal_blend_type == 'MIX':
            if layer.type == 'BACKGROUND':
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_VEC, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)
            else:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_VEC, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)

        elif normal_blend_type == 'OVERLAY':
            if has_parent:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.OVERLAY_NORMAL_STRAIGHT_OVER, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)
            else:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.OVERLAY_NORMAL, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)

        elif normal_blend_type == 'MIX':
            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeGroup', 'Blend', lib.VECTOR_MIX, 
                    return_status = True, hard_replace=True, replaced=need_reconnect)

        #blend_height = tree.nodes.get(ch.blend_height)
        #if not blend_height:
        #    blend_height = new_node(tree, ch, 'blend_height', 'ShaderNodeMixRGB', 'Height Blend')

        #if ch.normal_blend_type == 'MIX': blend_height.blend_type = 'MIX'
        #elif ch.normal_blend_type == 'OVERLAY': blend_height.blend_type = 'ADD'

        #intensity_height = tree.nodes.get(ch.intensity_height)
        #if not intensity_height:
        #    intensity_height = new_node(tree, ch, 'intensity_height', 'ShaderNodeMath', 'Height Intensity')
        #    intensity_height.operation = 'MULTIPLY'

        #if root_ch.enable_smooth_bump:
        #    for d in neighbor_directions:

        #        # Blend height
        #        bh = tree.nodes.get(getattr(ch, 'blend_height_' + d))
        #        if not bh:
        #            bh = new_node(tree, ch, 'blend_height_' + d, 'ShaderNodeMixRGB', 'Height Blend ' + d)
        #        if ch.normal_blend_type == 'MIX': bh.blend_type = 'MIX'
        #        elif ch.normal_blend_type == 'OVERLAY': bh.blend_type = 'ADD'

        #        # Intensity
        #        inten = tree.nodes.get(getattr(ch, 'intensity_height_' + d))
        #        if not inten:
        #            bh = new_node(tree, ch, 'intensity_height_' + d, 'ShaderNodeMath', 'Height Intensity ' + d)
        #            bh.operation = 'MULTIPLY'

        #else:
        #    for d in neighbor_directions:
        #        remove_node(tree, ch, 'blend_height_' + d)
        #        remove_node(tree, ch, 'intensity_height_' + d)

        #disp_ch = get_displacement_channel(yp)

        update_disp_scale_node(tree, root_ch, ch)

        #if not root_ch.enable_parallax:
        #    remove_node(tree, ch, 'height_blend')

        #if root_ch == disp_ch:
            #ch_index = get_channel_index(root_ch)

            #height_blend = tree.nodes.get(ch.height_blend)
            #disp_scale = tree.nodes.get(ch.disp_scale)

            #max_height = get_displacement_max_height(root_ch)
            #root_ch.displacement_height_ratio = max_height

            # Displacement blend node
            #if not height_blend:
            #    height_blend = new_node(tree, ch, 'height_blend', 'ShaderNodeMixRGB', 'Height Blend')

            #if ch.normal_blend_type == 'MIX':
            #    #height_blend.blend_type = 'MIX'
            #    height_blend, need_reconnect = replace_new_node(tree, ch, 'height_blend', 
            #            'ShaderNodeGroup', 'Displacement Blend', lib.DISP_MIX, 
            #            return_status = True, hard_replace=True)
            #elif ch.normal_blend_type == 'OVERLAY':
            #    #height_blend.blend_type = 'ADD'
            #    height_blend, need_reconnect = replace_new_node(tree, ch, 'height_blend', 
            #            'ShaderNodeGroup', 'Displacement Blend', lib.DISP_OVERLAY, 
            #            return_status = True, hard_replace=True)

            #if ch.normal_blend_type == 'MIX':
            #    height_blend.blend_type = 'MIX'
            #elif ch.normal_blend_type == 'OVERLAY':
            #    height_blend.blend_type = 'ADD'

            #if max_height > 0.0:
            #for l in yp.layers:
                #ttree = get_tree(l)
                #print(l.name)
                #c = l.channels[ch_index]
            #height_blend = tree.nodes.get(ch.height_blend)
            #if height_blend:
            #    height_blend.inputs['Scale'].default_value = ch.bump_distance #/ max_height

            #if not disp_scale:
            #    disp_scale = new_node(tree, ch, 'disp_scale', 'ShaderNodeGroup', 'Displacement Scale')
            #    disp_scale.node_tree = get_node_tree_lib(lib.HEIGHT_SCALE)

            #if ch.enable_transition_bump:
            #    disp_scale, need_reconnect = replace_new_node(tree, ch, 'disp_scale', 
            #            'ShaderNodeGroup', 'Displacement Scale', lib.HEIGHT_SCALE_TRANS_BUMP, 
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
            #update_disp_scale_node(tree, root_ch, ch)

        #else:
        #    remove_node(tree, ch, 'height_blend')
        #    remove_node(tree, ch, 'disp_scale')

        if root_ch.enable_smooth_bump:
            pass

            #for d in neighbor_directions:
            #    hb = tree.nodes.get(getattr(ch, 'height_blend_' + d))
            #    if not hb:
            #        hb = new_node(tree, ch, 'height_blend_' + d, 'ShaderNodeMixRGB', 'Height Blend')

            #    if ch.normal_blend_type == 'MIX':
            #        hb.blend_type = 'MIX'
            #    elif ch.normal_blend_type == 'OVERLAY':
            #        hb.blend_type = 'ADD'
        else:
            for d in neighbor_directions:
                remove_node(tree, ch, 'height_blend_' + d)

        #print(need_reconnect)

        # Update normal map nodes
        need_reconnect = check_channel_normal_map_nodes(tree, layer, root_ch, ch, need_reconnect)

        #print(need_reconnect)

    elif root_ch.type == 'VALUE':

        if has_parent and blend_type == 'MIX':
            if layer.type == 'BACKGROUND':
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BG_BW, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)
            else:
                blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                        'ShaderNodeGroup', 'Blend', lib.STRAIGHT_OVER_BW, 
                        return_status = True, hard_replace=True, replaced=need_reconnect)
        else:

            blend, need_reconnect = replace_new_node(tree, ch, 'blend', 
                    'ShaderNodeMixRGB', 'Blend', return_status = True, hard_replace=True, replaced=need_reconnect)

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
    if root_ch.type == 'NORMAL':
        remove_node(tree, ch, 'intensity')
    else:
        intensity = tree.nodes.get(ch.intensity)
        if not intensity:
            intensity = new_node(tree, ch, 'intensity', 'ShaderNodeMath', 'Intensity')
            intensity.operation = 'MULTIPLY'

        # Channel mute
        intensity.inputs[1].default_value = 0.0 if mute else ch.intensity_value

    #if root_ch.type == 'NORMAL':
    #    height_process = tree.nodes.get(ch.height_process)
    #    if height_process:
    #        height_process.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    #    normal_process = tree.nodes.get(ch.normal_process)
    #    if normal_process and 'Intensity' in normal_process.inputs:
    #        normal_process.inputs['Intensity'].default_value = 0.0 if mute else ch.intensity_value

    return need_reconnect

