import bpy
from bpy.props import *
from .common import *
from .node_arrangements import *
from .node_connections import *
from . import layer_common

def sync_bundle_input_layer(layer, node=None, comb=None):
    yp = layer.id_data.yp
    if yp.halt_update: return
    
    if not comb:
        if not node: node = get_active_ypaint_node()
        if not node: return
        # Get combine bundle node
        inp = node.inputs.get(layer.name)
        if not inp or len(inp.links) == 0: return

        comb = inp.links[0].from_node
        if comb.type != 'NodeCombineBundle': return

    if not comb: return

    source = get_layer_source(layer)
    if not source: return


    # Check current used layer channel socket name
    old_sockets = []
    enabled_channels = [ch for i, ch in enumerate(layer.channels) if get_channel_enabled(ch, layer, yp.channels[i])]
    for ch in enabled_channels:
        socket_name = get_channel_input_socket_name(layer, ch, source)
        old_sockets.append(socket_name)

    valid_sockets = []
    for inp in comb.inputs:
        if inp.name == '': continue
        soc = source.outputs.get(inp.name)
        if not soc or soc.type != inp.type:
            # Remove original socket
            if soc:
                item = source.bundle_items.get(soc.name)
                if item: source.bundle_items.remove(item)

        # Skip some socket types
        if inp.type in {'RGBA', 'VALUE', 'VECTOR', 'BOOLEAN', 'INT'}:
            socket_type = layer_common.get_socket_type_from_socket(inp)
            item = source.bundle_items.new(socket_type=socket_type, name=inp.name)
            soc = source.outputs.get(inp.name)
        else:
            soc = None

        if soc != None:
            valid_sockets.append(soc)

    for soc in source.outputs:
        if soc.name == '': continue
        if soc not in valid_sockets:
            item = source.bundle_items.get(soc.name)
            if item: source.bundle_items.remove(item)

    # Compare if the socket names changes
    dirty = False
    for i, ch in enumerate(enabled_channels):
        socket_name = get_channel_input_socket_name(layer, ch, source)
        if socket_name != old_sockets[i]:
            dirty = True
            break

    if dirty:
        reconnect_layer_nodes(layer)

class YFixMissingCombineBundleNode(bpy.types.Operator):
    bl_idname = "wm.y_fix_missing_combine_bundle_node"
    bl_label = "Fix Missing Combine Bundle Node"
    bl_description = "Fix missing combine bundle node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        for layer in yp.layers:
            if layer.type == 'INPUT_BUNDLE':
                layer_common.check_and_connect_combine_bundle_node(mat, node, layer)

        return {'FINISHED'}

class YSyncBundleInputLayer(bpy.types.Operator):
    bl_idname = "wm.y_sync_bundle_input_layer"
    bl_label = "Sync Bundle Input Layer"
    bl_description = "Sync Bundle Input Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return context.object and group_node and len(group_node.node_tree.yp.layers) > 0

    def execute(self, context):
        mat = get_active_material()
        node = get_active_ypaint_node()
        layer = context.layer
        sync_bundle_input_layer(layer, node)
        return {'FINISHED'}

import bpy
from bpy.app.handlers import persistent

def get_layer_from_combine_bundle_node(bund):
    # Check if the combine bundle is connected to yp node
    layer = None
    if bund and len(bund.outputs[0].links) > 0:
        link = bund.outputs[0].links[0]
        if link.to_node.type == 'GROUP' and link.to_node.node_tree.yp.is_ypaint_node:
            yp = link.to_node.node_tree.yp
            layer = yp.layers.get(link.to_socket.name)
            if layer and layer.type != 'INPUT_BUNDLE':
                layer = None

    return layer

def on_node_connections_change(tree):
    # Check the last connection
    try: link = tree.links[-1]
    except: return

    # Check if last link is a connection to combine bundle node
    bund = None
    if link.to_node.type == 'NodeCombineBundle':
        bund = link.to_node
    elif link.from_node.type == 'NodeCombineBundle':
        to_node = link.to_node
        if to_node.type == 'GROUP' and to_node.node_tree and to_node.node_tree.yp.is_ypaint_node:
            bund = link.from_node
    
    # Sync bundle items
    layer = get_layer_from_combine_bundle_node(bund)
    if layer:
        sync_bundle_input_layer(layer, comb=bund)

def on_combine_bundle_items_change(tree):
    active_node = tree.nodes.active
    if active_node.type != 'NodeCombineBundle': return

    # Sync bundle items
    layer = get_layer_from_combine_bundle_node(active_node)
    if layer:
        sync_bundle_input_layer(layer, comb=active_node)

@persistent
def bundle_items_handler(scene, depsgraph):
    obj = bpy.context.object
    if not obj: return
    mat = obj.active_material
    if not mat or not mat.use_nodes or not mat.node_tree: return
    tree = mat.node_tree

    # Get last operator
    ops = bpy.context.window_manager.operators
    last_op = ops[-1] if len(ops) > 0 else None
    
    if last_op:
        # Check last operator
        if last_op.bl_idname == 'NODE_OT_link':
            on_node_connections_change(tree)
        elif last_op.bl_idname in {'NODE_OT_combine_bundle_item_remove', 'NODE_OT_combine_bundle_item_add'}:
            on_combine_bundle_items_change(tree)

classes = (
    YFixMissingCombineBundleNode,
    YSyncBundleInputLayer,
)

def register():
    for cls in classes: bpy.utils.register_class(cls)

    if is_bl_newer_than(5):
        bpy.app.handlers.depsgraph_update_post.append(bundle_items_handler)

def unregister():
    for cls in classes: bpy.utils.unregister_class(cls)

    if is_bl_newer_than(5):
        bpy.app.handlers.depsgraph_update_post.remove(bundle_items_handler)
