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
    uv_neighbor = check_new_node(layer_tree, layer, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV')
    if layer.type in {'VCOL', 'GROUP'}:
        uv_neighbor.node_tree = get_node_tree_lib(lib.NEIGHBOR_FAKE)
    else: 
        uv_neighbor.node_tree = lib.get_neighbor_uv_tree(layer.texcoord_type)
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
    blur_found = False
    for i, ch in enumerate(layer.channels):
        if yp.channels[i].type == 'NORMAL' and (ch.normal_map_type == 'FINE_BUMP_MAP' 
                or (ch.enable_transition_bump and ch.transition_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'})):
            fine_bump_found = True
        if hasattr(ch, 'enable_blur') and ch.enable_blur:
            blur_found =True

    if (layer.type != 'VCOL' and layer.source_group == '') or fine_bump_found or blur_found: return

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
    if bump_ch and bump_ch.transition_bump_type == 'BUMP_MAP':
        #return False
        bump_ch = None

    if not bump_ch:
        chs = [c for i,c in enumerate(layer.channels) 
                if c.normal_map_type == 'FINE_BUMP_MAP' and yp.channels[i].type == 'NORMAL']
        if chs: bump_ch = chs[0]

    # Check transition bump chain
    if bump_ch:
        chain = min(bump_ch.transition_bump_chain, len(layer.masks))
        match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        mask_idx = int(match.group(2))
        if mask_idx >= chain:
            return False

    need_reconnect = False

    uv_neighbor = tree.nodes.get(mask.uv_neighbor)
    if not uv_neighbor:
        uv_neighbor = new_node(tree, mask, 'uv_neighbor', 'ShaderNodeGroup', 'Mask UV Neighbor')
        need_reconnect = True

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
            need_reconnect = True

        set_uv_neighbor_resolution(mask, uv_neighbor)

        if different_uv:
            tangent = tree.nodes.get(mask.tangent)
            bitangent = tree.nodes.get(mask.bitangent)

            if not tangent:
                tangent = new_node(tree, mask, 'tangent', 'ShaderNodeNormalMap', 'Mask Tangent')
                tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)
                need_reconnect = True

            if not bitangent:
                bitangent = new_node(tree, mask, 'bitangent', 'ShaderNodeNormalMap', 'Mask Bitangent')
                bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)
                need_reconnect = True

            tangent.uv_map = mask.uv_name
            bitangent.uv_map = mask.uv_name
        else:
            remove_node(tree, mask, 'tangent')
            remove_node(tree, mask, 'bitangent')

    return need_reconnect

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

    remove_node(layer_tree, mask, 'uv_neighbor')

    if reconnect:
        # Reconnect outside nodes
        reconnect_layer_nodes(layer)

        # Rearrange nodes
        rearrange_layer_nodes(layer)

def check_create_bump_base(layer, tree, ch):

    normal_map_type = ch.normal_map_type
    #if layer.type in {'VCOL', 'COLOR'} and ch.normal_map_type == 'FINE_BUMP_MAP':
    #    normal_map_type = 'BUMP_MAP'

    skip = False
    if layer.type in {'BACKGROUND', 'GROUP'}: #or is_valid_to_remove_bump_nodes(layer, ch):
        skip = True

    if not skip and normal_map_type == 'FINE_BUMP_MAP':

        # Delete standard bump base first
        remove_node(tree, ch, 'bump_base')

        for d in neighbor_directions:

            if ch.enable_transition_bump:
                # Mask bump uses hack
                bb = replace_new_node(tree, ch, 'bump_base_' + d, 
                        'ShaderNodeGroup', 'bump_hack_' + d, lib.STRAIGHT_OVER_HACK) 

            else:
                # Check standard bump base
                bb = replace_new_node(tree, ch, 'bump_base_' + d, 'ShaderNodeMixRGB', 'bump_base_' + d)
                #if replaced:
                val = ch.bump_base_value
                bb.inputs[0].default_value = 1.0
                bb.inputs[1].default_value = (val, val, val, 1.0)

    elif not skip and normal_map_type == 'BUMP_MAP':

        # Delete fine bump bump bases first
        for d in neighbor_directions:
            remove_node(tree, ch, 'bump_base_' + d)

        if ch.enable_transition_bump:

            # Mask bump uses hack
            bump_base = replace_new_node(tree, ch, 'bump_base', 
                    'ShaderNodeGroup', 'Bump Hack', lib.STRAIGHT_OVER_HACK)

        else:
            # Check standard bump base
            bump_base = replace_new_node(tree, ch, 'bump_base', 'ShaderNodeMixRGB', 'Bump Base')
            #if replaced:
            val = ch.bump_base_value
            bump_base.inputs[0].default_value = 1.0
            bump_base.inputs[1].default_value = (val, val, val, 1.0)

    else:
        # Delete all bump bases
        remove_node(tree, ch, 'bump_base')
        for d in neighbor_directions:
            remove_node(tree, ch, 'bump_base_' + d)

def check_mask_mix_nodes(layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    trans_bump = get_transition_bump_channel(layer)

    trans_bump_flip = False
    if trans_bump:
        trans_bump_flip = trans_bump.transition_bump_flip or layer.type == 'BACKGROUND'

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

                if ((
                    (not trans_bump and ch.normal_map_type in {'FINE_BUMP_MAP'}) or
                    (trans_bump == ch and ch.transition_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'}) 
                    ) and i < chain):

                    for d in neighbor_directions:
                        mix = tree.nodes.get(getattr(c, 'mix_' + d))

                        if not mix:
                            mix = new_node(tree, c, 'mix_' + d, 'ShaderNodeMixRGB', 'Mask Blend ' + d.upper())
                            mix.blend_type = mask.blend_type
                            mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                            if yp.disable_quick_toggle:
                                mix.mute = mute
                            else: mix.mute = False

                elif i >= chain and not trans_bump_flip and ch.transition_bump_crease:

                    mix_n = tree.nodes.get(c.mix_n)
                    if not mix_n:
                        mix_n = new_node(tree, c, 'mix_n', 'ShaderNodeMixRGB', 'Mask Blend N')
                        mix_n.blend_type = mask.blend_type
                        mix_n.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_n.mute = mute
                        else: mix_n.mute = False

                    for d in ['s', 'e', 'w']:
                        remove_node(tree, c, 'mix_' + d)
                else:
                    for d in neighbor_directions:
                        remove_node(tree, c, 'mix_' + d)

            else: 
                if (trans_bump and i >= chain and (
                    (trans_bump_flip and ch.enable_transition_ramp) or 
                    #(not trans_bump_flip and ch.enable_transition_ramp and ch.transition_ramp_intensity_unlink) or
                    (not trans_bump_flip and ch.enable_transition_ao)
                    )):
                    mix_n = tree.nodes.get(c.mix_n)

                    if not mix_n:
                        mix_n = new_node(tree, c, 'mix_n', 'ShaderNodeMixRGB', 'Mask Blend N')
                        mix_n.blend_type = mask.blend_type
                        mix_n.inputs[0].default_value = 0.0 if mute else mask.intensity_value
                        if yp.disable_quick_toggle:
                            mix_n.mute = mute
                        else: mix_n.mute = False
                else:
                    remove_node(tree, c, 'mix_n')

def check_mask_source_tree(layer): #, ch=None):

    yp = layer.id_data.yp

    # Try to get transition bump
    trans_bump = get_transition_bump_channel(layer)

    # Try to get fine bump if transition bump is not found
    fine_bump = None
    if not trans_bump:
        chs = [c for i,c in enumerate(layer.channels) 
                if c.normal_map_type == 'FINE_BUMP_MAP' and yp.channels[i].type == 'NORMAL']
        if chs: fine_bump = chs[0]

    if trans_bump:
        chain = min(trans_bump.transition_bump_chain, len(layer.masks))
    elif fine_bump:
        chain = min(fine_bump.transition_bump_chain, len(layer.masks))
    else: chain = -1

    for i, mask in enumerate(layer.masks):

        if ((trans_bump and trans_bump.transition_bump_type != 'BUMP_MAP') or fine_bump) and i < chain:
            enable_mask_source_tree(layer, mask)
        else:
            disable_mask_source_tree(layer, mask)


