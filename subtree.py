import bpy
from . import lib
from .common import *
from .node_arrangements import *
from .node_connections import *

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
        start.name = TREE_START
        end = source_tree.nodes.new('NodeGroupOutput')
        end.name = TREE_END

        # Copy source from reference
        source = new_node(source_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Connect internal nodes
        source_tree.links.new(start.outputs[0], source.inputs[0])
        source_tree.links.new(source.outputs[0], end.inputs[0])

        # Non image texture use solid alpha
        #if tex.type != 'IMAGE':
        #    solid_alpha = source_tree.nodes.new('ShaderNodeValue')
        #    solid_alpha.outputs[0].default_value = 1.0
        #    source_tree.links.new(solid_alpha.outputs[0], end.inputs[1])
        #else:
        source_tree.links.new(source.outputs[1], end.inputs[1])

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
                or (ch.enable_mask_bump and ch.mask_bump_type == 'FINE_BUMP_MAP')):
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

