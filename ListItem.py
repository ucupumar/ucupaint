import bpy
from bpy.props import *
from .common import *

def refresh_list_items(yp, repoint_active=False):
    # Get current active item and its parent
    active_item_name = ''
    active_item_type = ''
    if repoint_active and yp.active_item_index < len(yp.list_items):
        item = yp.list_items[yp.active_item_index]

        if item.type in {'LAYER', 'MASK'}:
            active_item_name = item.name
            active_item_type = item.type

    # Reset list
    yp.list_items.clear()

    new_active_index = -1
    for i, layer in enumerate(yp.layers):
        item = yp.list_items.add()
        item.type = 'LAYER'
        item.index = i
        item.name = layer.name

        layer_item_index = len(yp.list_items)-1

        if active_item_name == layer.name and active_item_type == 'LAYER':
            new_active_index = layer_item_index

        for j, mask in enumerate(layer.masks):

            if layer.expand_subitems:
                item = yp.list_items.add()
                item.type = 'MASK'
                item.index = j
                item.parent_index = i
                item.parent_name = layer.name
                item.name = mask.name

                if (
                    (repoint_active and yp.active_layer_index == i and mask.active_edit) or # Select mask with active edit after expand subitems
                    (active_item_name == mask.name and active_item_type == 'MASK') # Select correct mask after other layer uncollapsing
                ):
                    new_active_index = len(yp.list_items)-1

            elif active_item_name == mask.name and active_item_type == 'MASK':
                new_active_index = layer_item_index
    
    # Set new active index
    if new_active_index != -1:
        yp.active_item_index = new_active_index

class YListItem(bpy.types.PropertyGroup):

    name : StringProperty(default='')
    index : IntProperty(default=0)

    parent_name : StringProperty(default='')
    parent_index : IntProperty(default=-1)

    type : EnumProperty(
        name = 'Item Type',
        items = (
            ('LAYER', 'Layer', ''),
            ('CHANNEL_OVERRIDE', 'Channel Override', ''),
            ('MASK', 'Mask', '')
        ),
        default = 'LAYER'
    )

class YRefreshListItems(bpy.types.Operator):
    bl_idname = "node.y_refresh_list_items"
    bl_label = "Refresh List Items"
    bl_description = "Refresh List Items"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        refresh_list_items(yp)

        return {'FINISHED'}

def update_expand_subitems(self, context):
    yp = self.id_data.yp
    refresh_list_items(yp, repoint_active=True)

def update_list_item_index(self, context):
    yp = self.id_data.yp

    if yp.active_item_index >= len(yp.list_items): return
    
    item = yp.list_items[yp.active_item_index]

    layer_index = -1
    if item.type == 'LAYER':
        layer_index = item.index
    elif item.type == 'MASK':
        layer_index = item.parent_index
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if item.index < len(layer.masks):
                mask = layer.masks[item.index]
                mask.active_edit = True

    if layer_index != -1 and layer_index < len(yp.layers):
        yp.active_layer_index = layer_index

def register():
    bpy.utils.register_class(YListItem)
    bpy.utils.register_class(YRefreshListItems)

def unregister():
    bpy.utils.unregister_class(YListItem)
    bpy.utils.unregister_class(YRefreshListItems)
