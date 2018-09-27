import bpy
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

def enable_tex_source_tree(tex, rearrange=True):

    # Check if source tree is already available
    if tex.type != 'VCOL' and tex.source_group != '': return

    tex_tree = get_tree(tex)

    if tex.type != 'VCOL':
        # Get current source for reference
        source_ref = tex_tree.nodes.get(tex.source)

        # Create source tree
        source_tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex.name + ' Source', 'ShaderNodeTree')

        # Create input and outputs
        source_tree.inputs.new('NodeSocketVector', 'Vector')
        source_tree.outputs.new('NodeSocketColor', 'Color')
        source_tree.outputs.new('NodeSocketFloat', 'Alpha')

        #source_tree.outputs.new('NodeSocketFloat', 'Factor')

        start = source_tree.nodes.new('NodeGroupInput')
        start.name = SOURCE_TREE_START
        end = source_tree.nodes.new('NodeGroupOutput')
        end.name = SOURCE_TREE_END

        if tex.type != 'IMAGE':
            source_tree.outputs.new('NodeSocketColor', 'Color 1')
            source_tree.outputs.new('NodeSocketFloat', 'Alpha 1')

            solid = source_tree.nodes.new('ShaderNodeValue')
            solid.outputs[0].default_value = 1.0
            solid.name = SOURCE_SOLID_VALUE

        # Copy source from reference
        source = new_node(source_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Connect internal nodes
        #source_tree.links.new(start.outputs[0], source.inputs[0])
        #source_tree.links.new(source.outputs[0], end.inputs[0])

        # Non image texture use solid alpha
        #if tex.type != 'IMAGE':
        #    solid_alpha = source_tree.nodes.new('ShaderNodeValue')
        #    solid_alpha.outputs[0].default_value = 1.0
        #    source_tree.links.new(solid_alpha.outputs[0], end.inputs[1])
        #else:
        #source_tree.links.new(source.outputs[1], end.inputs[1])

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

        # Create new source
        source = new_node(tex_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

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

def check_create_bump_base(tree, ch):

    if ch.normal_map_type == 'FINE_BUMP_MAP':

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

    elif ch.normal_map_type == 'BUMP_MAP':

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

