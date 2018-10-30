import bpy, re
from . import lib, Modifier
from .common import *
from .node_arrangements import *
from .node_connections import *

def move_mod_group(tex, from_tree, to_tree):
    mod_group = from_tree.nodes.get(tex.mod_group)
    if mod_group:
        mod_tree = mod_group.node_tree
        remove_node(from_tree, tex, 'mod_group', remove_data=False)
        remove_node(from_tree, tex, 'mod_group_1', remove_data=False)

        mod_group = new_node(to_tree, tex, 'mod_group', 'ShaderNodeGroup', 'mod_group')
        mod_group.node_tree = mod_tree
        mod_group_1 = new_node(to_tree, tex, 'mod_group_1', 'ShaderNodeGroup', 'mod_group_1')
        mod_group_1.node_tree = mod_tree

def refresh_source_tree_ios(source_tree, tex_type):

    # Create input and outputs
    inp = source_tree.inputs.get('Vector')
    if not inp: source_tree.inputs.new('NodeSocketVector', 'Vector')

    out = source_tree.outputs.get('Color')
    if not out: source_tree.outputs.new('NodeSocketColor', 'Color')

    out = source_tree.outputs.get('Alpha')
    if not out: source_tree.outputs.new('NodeSocketFloat', 'Alpha')

    col1 = source_tree.outputs.get('Color 1')
    alp1 = source_tree.outputs.get('Alpha 1')
    solid = source_tree.nodes.get(SOURCE_SOLID_VALUE)

    if tex_type != 'IMAGE':

        if not col1: col1 = source_tree.outputs.new('NodeSocketColor', 'Color 1')
        if not alp1: alp1 = source_tree.outputs.new('NodeSocketFloat', 'Alpha 1')

        if not solid:
            solid = source_tree.nodes.new('ShaderNodeValue')
            solid.outputs[0].default_value = 1.0
            solid.name = SOURCE_SOLID_VALUE
    else:
        if col1: source_tree.outputs.remove(col1)
        if alp1: source_tree.outputs.remove(alp1)
        if solid: source_tree.nodes.remove(solid)

def enable_tex_source_tree(tex, rearrange=False):

    # Check if source tree is already available
    if tex.type != 'VCOL' and tex.source_group != '': return
    if tex.type in {'BACKGROUND', 'COLOR'}: return

    tex_tree = get_tree(tex)

    if tex.type != 'VCOL':
        # Get current source for reference
        source_ref = tex_tree.nodes.get(tex.source)
        mapping_ref = tex_tree.nodes.get(tex.mapping)

        # Create source tree
        source_tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex.name + ' Source', 'ShaderNodeTree')

        #source_tree.outputs.new('NodeSocketFloat', 'Factor')

        start = source_tree.nodes.new('NodeGroupInput')
        start.name = SOURCE_TREE_START
        end = source_tree.nodes.new('NodeGroupOutput')
        end.name = SOURCE_TREE_END

        refresh_source_tree_ios(source_tree, tex.type)

        # Copy source from reference
        source = new_node(source_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(source_tree, tex, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

        # Create source node group
        source_group = new_node(tex_tree, tex, 'source_group', 'ShaderNodeGroup', 'source_group')
        source_n = new_node(tex_tree, tex, 'source_n', 'ShaderNodeGroup', 'source_n')
        source_s = new_node(tex_tree, tex, 'source_s', 'ShaderNodeGroup', 'source_s')
        source_e = new_node(tex_tree, tex, 'source_e', 'ShaderNodeGroup', 'source_e')
        source_w = new_node(tex_tree, tex, 'source_w', 'ShaderNodeGroup', 'source_w')

        source_group.node_tree = source_tree
        source_n.node_tree = source_tree
        source_s.node_tree = source_tree
        source_e.node_tree = source_tree
        source_w.node_tree = source_tree

        # Remove previous source
        tex_tree.nodes.remove(source_ref)
        if mapping_ref: tex_tree.nodes.remove(mapping_ref)
    
        # Bring modifiers to source tree
        if tex.type == 'IMAGE':
            for mod in tex.modifiers:
                Modifier.add_modifier_nodes(mod, source_tree, tex_tree)
        else:
            move_mod_group(tex, tex_tree, source_tree)

    # Create uv neighbor
    uv_neighbor = check_new_node(tex_tree, tex, 'uv_neighbor', 'ShaderNodeGroup', 'Neighbor UV')
    if tex.type == 'VCOL':
        uv_neighbor.node_tree = lib.get_node_tree_lib(lib.NEIGHBOR_FAKE)
    else: 
        uv_neighbor.node_tree = lib.get_neighbor_uv_tree(tex.texcoord_type)

        if BLENDER_28_GROUP_INPUT_HACK:
            duplicate_lib_node_tree(uv_neighbor)

        if tex.type == 'IMAGE' and source.image:
            uv_neighbor.inputs[1].default_value = source.image.size[0]
            uv_neighbor.inputs[2].default_value = source.image.size[1]
        else:
            uv_neighbor.inputs[1].default_value = 1000
            uv_neighbor.inputs[2].default_value = 1000

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(uv_neighbor, 'ResX')
            match_group_input(uv_neighbor, 'ResY')

    if rearrange:
        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def disable_tex_source_tree(tex, rearrange=True):

    #if tex.type == 'VCOL': return

    tl = tex.id_data.tl

    # Check if fine bump map is used on some of texture channels
    fine_bump_found = False
    blur_found = False
    for i, ch in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and (ch.normal_map_type == 'FINE_BUMP_MAP' 
                or (ch.enable_mask_bump and ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'})):
            fine_bump_found = True
        if hasattr(ch, 'enable_blur') and ch.enable_blur:
            blur_found =True

    if (tex.type != 'VCOL' and tex.source_group == '') or fine_bump_found or blur_found: return

    tex_tree = get_tree(tex)

    if tex.type != 'VCOL':
        source_group = tex_tree.nodes.get(tex.source_group)
        source_ref = source_group.node_tree.nodes.get(tex.source)
        mapping_ref = source_group.node_tree.nodes.get(tex.mapping)

        # Create new source
        source = new_node(tex_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)
        mapping = new_node(tex_tree, tex, 'mapping', 'ShaderNodeMapping')
        if mapping_ref: copy_node_props(mapping_ref, mapping)

        # Bring back layer modifier to original tree
        if tex.type == 'IMAGE':
            for mod in tex.modifiers:
                Modifier.add_modifier_nodes(mod, tex_tree, source_group.node_tree)
        else:
            move_mod_group(tex, source_group.node_tree, tex_tree)

        # Remove previous source
        remove_node(tex_tree, tex, 'source_group')
        remove_node(tex_tree, tex, 'source_n')
        remove_node(tex_tree, tex, 'source_s')
        remove_node(tex_tree, tex, 'source_e')
        remove_node(tex_tree, tex, 'source_w')

    remove_node(tex_tree, tex, 'uv_neighbor')

    if rearrange:
        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def set_mask_uv_neighbor(tree, tex, mask):

    # NOTE: Checking transition bump everytime this function called is not that tidy
    # Check if transition bump channel is available
    bump_ch = get_transition_bump_channel(tex)
    if not bump_ch or bump_ch.mask_bump_type == 'BUMP_MAP':
        return False

    # Check transition bump chain
    if bump_ch:
        chain = min(bump_ch.mask_bump_chain, len(tex.masks))
        match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        mask_idx = int(match.group(2))
        if mask_idx >= chain:
            return False

    need_reconnect = False

    uv_neighbor = tree.nodes.get(mask.uv_neighbor)
    if not uv_neighbor:
        uv_neighbor = new_node(tree, mask, 'uv_neighbor', 'ShaderNodeGroup', 'Mask UV Neighbor')
        need_reconnect = True

    if mask.type == 'VCOL':
        uv_neighbor.node_tree = lib.get_node_tree_lib(lib.NEIGHBOR_FAKE)
    else:

        different_uv = mask.texcoord_type == 'UV' and tex.uv_name != mask.uv_name

        # Check number of input
        prev_num_inputs = len(uv_neighbor.inputs)

        # If hack is active, remove old tree first
        if BLENDER_28_GROUP_INPUT_HACK and uv_neighbor.node_tree:
            bpy.data.node_groups.remove(uv_neighbor.node_tree)

        # Get new uv neighbor tree
        uv_neighbor.node_tree = lib.get_neighbor_uv_tree(mask.texcoord_type, different_uv)

        # Check current number of input
        cur_num_inputs = len(uv_neighbor.inputs)

        # Need reconnect of number of inputs different
        if prev_num_inputs != cur_num_inputs:
            need_reconnect = True

        if mask.type == 'IMAGE':
            src = get_mask_source(mask)
            uv_neighbor.inputs[1].default_value = src.image.size[0]
            uv_neighbor.inputs[2].default_value = src.image.size[1]
        else:
            uv_neighbor.inputs[1].default_value = 1000
            uv_neighbor.inputs[2].default_value = 1000

        if BLENDER_28_GROUP_INPUT_HACK:
            duplicate_lib_node_tree(uv_neighbor)

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

def enable_mask_source_tree(tex, mask, reconnect = False):

    # Check if source tree is already available
    if mask.type != 'VCOL' and mask.group_node != '': return

    tex_tree = get_tree(tex)

    if mask.type != 'VCOL':
        # Get current source for reference
        source_ref = tex_tree.nodes.get(mask.source)

        # Create mask tree
        mask_tree = bpy.data.node_groups.new(MASKGROUP_PREFIX + mask.name, 'ShaderNodeTree')

        # Create input and outputs
        mask_tree.inputs.new('NodeSocketVector', 'Vector')
        #mask_tree.outputs.new('NodeSocketColor', 'Color')
        mask_tree.outputs.new('NodeSocketFloat', 'Value')

        start = mask_tree.nodes.new('NodeGroupInput')
        start.name = MASK_TREE_START
        end = mask_tree.nodes.new('NodeGroupOutput')
        end.name = MASK_TREE_END

        # Copy nodes from reference
        source = new_node(mask_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Create source node group
        group_node = new_node(tex_tree, mask, 'group_node', 'ShaderNodeGroup', 'source_group')
        source_n = new_node(tex_tree, mask, 'source_n', 'ShaderNodeGroup', 'source_n')
        source_s = new_node(tex_tree, mask, 'source_s', 'ShaderNodeGroup', 'source_s')
        source_e = new_node(tex_tree, mask, 'source_e', 'ShaderNodeGroup', 'source_e')
        source_w = new_node(tex_tree, mask, 'source_w', 'ShaderNodeGroup', 'source_w')

        group_node.node_tree = mask_tree
        source_n.node_tree = mask_tree
        source_s.node_tree = mask_tree
        source_e.node_tree = mask_tree
        source_w.node_tree = mask_tree

        # Remove previous nodes
        tex_tree.nodes.remove(source_ref)

    # Create uv neighbor
    set_mask_uv_neighbor(tex_tree, tex, mask)

    if reconnect:
        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def disable_mask_source_tree(tex, mask, reconnect=False):

    # Check if source tree is already gone
    if mask.type != 'VCOL' and mask.group_node == '': return

    tex_tree = get_tree(tex)

    if mask.type != 'VCOL':

        mask_tree = get_mask_tree(mask)

        source_ref = mask_tree.nodes.get(mask.source)
        group_node = tex_tree.nodes.get(mask.group_node)

        # Create new nodes
        source = new_node(tex_tree, mask, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Remove previous source
        remove_node(tex_tree, mask, 'group_node')
        remove_node(tex_tree, mask, 'source_n')
        remove_node(tex_tree, mask, 'source_s')
        remove_node(tex_tree, mask, 'source_e')
        remove_node(tex_tree, mask, 'source_w')
        remove_node(tex_tree, mask, 'tangent')
        remove_node(tex_tree, mask, 'bitangent')

    remove_node(tex_tree, mask, 'uv_neighbor')

    if reconnect:
        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def check_create_bump_base(tex, tree, ch):

    normal_map_type = ch.normal_map_type
    if tex.type in {'VCOL', 'COLOR'} and ch.normal_map_type == 'FINE_BUMP_MAP':
        normal_map_type = 'BUMP_MAP'

    if tex.type not in 'BACKGROUND' and normal_map_type == 'FINE_BUMP_MAP':

        # Delete standard bump base first
        remove_node(tree, ch, 'bump_base')

        for d in neighbor_directions:

            if ch.enable_mask_bump:
                # Mask bump uses hack
                bb, replaced = replace_new_node(tree, ch, 'bump_base_' + d, 'ShaderNodeGroup', 'bump_hack_' + d, True)
                if replaced:
                    bb.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_HACK)

            else:
                # Check standard bump base
                bb, replaced = replace_new_node(tree, ch, 'bump_base_' + d, 'ShaderNodeMixRGB', 'bump_base_' + d, True)
                if replaced:
                    val = ch.bump_base_value
                    bb.inputs[0].default_value = 1.0
                    bb.inputs[1].default_value = (val, val, val, 1.0)

    elif tex.type != 'BACKGROUND' and normal_map_type == 'BUMP_MAP':

        # Delete fine bump bump bases first
        for d in neighbor_directions:
            remove_node(tree, ch, 'bump_base_' + d)

        if ch.enable_mask_bump:

            # Mask bump uses hack
            bump_base, replaced = replace_new_node(tree, ch, 'bump_base', 'ShaderNodeGroup', 'Bump Hack', True)
            if replaced:
                bump_base.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER_HACK)

        else:
            # Check standard bump base
            bump_base, replaced = replace_new_node(tree, ch, 'bump_base', 'ShaderNodeMixRGB', 'Bump Base', True)
            if replaced:
                val = ch.bump_base_value
                bump_base.inputs[0].default_value = 1.0
                bump_base.inputs[1].default_value = (val, val, val, 1.0)

    else:
        # Delete all bump bases
        remove_node(tree, ch, 'bump_base')
        for d in neighbor_directions:
            remove_node(tree, ch, 'bump_base_' + d)

def set_mask_multiply_nodes(tex, tree=None, bump_ch=None):

    tl = tex.id_data.tl
    if not tree: tree = get_tree(tex)
    if not bump_ch: bump_ch = get_transition_bump_channel(tex)

    chain = -1
    flip_bump = False
    if bump_ch:
        chain = min(bump_ch.mask_bump_chain, len(tex.masks))
        flip_bump = bump_ch.mask_bump_flip or tex.type == 'BACKGROUND'

    for i, mask in enumerate(tex.masks):
        for j, c in enumerate(mask.channels):

            multiply = tree.nodes.get(c.multiply)
            if not multiply:
                multiply = new_node(tree, c, 'multiply', 'ShaderNodeMath', 'Mask Multiply')
                multiply.operation = 'MULTIPLY'
                multiply.mute = not c.enable or not mask.enable or not tex.enable_masks

            ch = tex.channels[j]
            root_ch = tl.channels[j]

            if root_ch.type == 'NORMAL':

                if bump_ch == ch and ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'} and i < chain:
                    for d in neighbor_directions:
                        mul = tree.nodes.get(getattr(c, 'multiply_' + d))
                        if not mul:
                            mul = new_node(tree, c, 'multiply_' + d, 'ShaderNodeMath', 'mul_' + d)
                            mul.operation = 'MULTIPLY'
                            mul.mute = not c.enable or not mask.enable or not tex.enable_masks
                else:
                    for d in neighbor_directions:
                        remove_node(tree, c, 'multiply_' + d)

            else: 
                if (bump_ch and i >= chain and (
                    (flip_bump and ch.enable_mask_ramp) or (not flip_bump and ch.enable_transition_ao)
                    )):
                    multiply_n = tree.nodes.get(c.multiply_n)
                    if not multiply_n:
                        multiply_n = new_node(tree, c, 'multiply_n', 'ShaderNodeMath', 'mul_extra')
                        multiply_n.operation = 'MULTIPLY'
                        multiply_n.mute = not c.enable or not mask.enable or not tex.enable_masks
                else:
                    remove_node(tree, c, 'multiply_n')

