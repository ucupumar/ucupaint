import bpy
from .common import *
from .node_arrangements import *
from .node_connections import *

def enable_tex_source_tree(tex):

    # Check if source tree is already available
    if tex.source_group != '': return

    tex_tree = get_tree(tex)

    # Get current source for reference
    source_ref = tex_tree.nodes.get(tex.source)

    # Create source tree
    source_tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex.name + ' Source', 'ShaderNodeTree')

    # Create input and outputs
    source_tree.inputs.new('NodeSocketVector', 'Vector')
    source_tree.outputs.new('NodeSocketColor', 'Color')
    source_tree.outputs.new('NodeSocketFloat', 'Alpha')

    start = source_tree.nodes.new('NodeGroupInput')
    end = source_tree.nodes.new('NodeGroupOutput')

    # Copy source from reference
    source = new_node(source_tree, tex, 'source', source_ref.bl_idname)
    copy_node_props(source_ref, source)

    # Connect internal nodes
    source_tree.links.new(start.outputs[0], source.inputs[0])
    source_tree.links.new(source.outputs[0], end.inputs[0])
    source_tree.links.new(source.outputs[1], end.inputs[1])

    # Create source node group
    source_group = new_node(tex_tree, tex, 'source_group', 'ShaderNodeGroup')
    source_group.node_tree = source_tree

    # Remove previous source
    tex_tree.nodes.remove(source_ref)

    # Reconnect outside nodes
    reconnect_tex_nodes(tex)

    # Rearrange nodes
    rearrange_tex_nodes(tex)

def disable_tex_source_tree(tex):
    tl = tex.id_data.tl

    # Check if fine bump map is used on some of texture channels
    fine_bump_found = False
    blur_found = False
    for i, ch in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and ch.normal_map_type == 'FINE_BUMP_MAP':
            fine_bump_found = True
        if hasattr(ch, 'enable_blur') and ch.enable_blur:
            blur_found =True

    if tex.source_group != '' and not fine_bump_found and not blur_found:
        
        tex_tree = get_tree(tex)

        source_group = tex_tree.nodes.get(tex.source_group)
        source_ref = source_group.node_tree.nodes.get(tex.source)

        # Create new source
        source = new_node(tex_tree, tex, 'source', source_ref.bl_idname)
        copy_node_props(source_ref, source)

        # Remove previous source
        bpy.data.node_groups.remove(source_group.node_tree)
        tex_tree.nodes.remove(source_group)
        tex.source_group = ''

        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

