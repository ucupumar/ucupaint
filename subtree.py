import bpy
from .common import *
from .node_arrangements import *
from .node_connections import *

def enable_tex_source_tree(tex):
    if not tex.source_tree:
        source_ref = tex.tree.nodes.get(tex.source)

        # Create source tree
        source_tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex.name + 'Source', 'ShaderNodeTree')
        tex.source_tree = source_tree

        # Create input and outputs
        source_tree.inputs.new('NodeSocketVector', 'Vector')
        source_tree.outputs.new('NodeSocketColor', 'Color')
        source_tree.outputs.new('NodeSocketFloat', 'Alpha')

        start = source_tree.nodes.new('NodeGroupInput')
        end = source_tree.nodes.new('NodeGroupOutput')

        # Copy source from reference
        source = source_tree.nodes.new(source_ref.bl_idname)
        copy_node_props(source_ref, source)
        tex.source = source.name

        # Connect internal nodes
        source_tree.links.new(start.outputs[0], source.inputs[0])
        source_tree.links.new(source.outputs[0], end.inputs[0])
        source_tree.links.new(source.outputs[1], end.inputs[1])

        # Create source node group
        source_group = tex.tree.nodes.new('ShaderNodeGroup')
        source_group.node_tree = source_tree
        tex.source_group = source_group.name

        # Remove previous source
        tex.tree.nodes.remove(source_ref)

        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

def disable_tex_source_tree(tex):
    if tex.source_tree:

        source_ref = tex.source_tree.nodes.get(tex.source)
        source_group = tex.tree.nodes.get(tex.source_group)

        # Create new source
        source = tex.tree.nodes.new(source_ref.bl_idname)
        copy_node_props(source_ref, source)
        tex.source = source.name

        # Remove previous source
        tex.tree.nodes.remove(source_group)
        bpy.data.node_groups.remove(tex.source_tree)
        tex.source_tree = None

        # Reconnect outside nodes
        reconnect_tex_nodes(tex)

        # Rearrange nodes
        rearrange_tex_nodes(tex)

