import bpy
from bpy.props import *
from .common import *

def refresh_list_items(yp):
    yp.list_items.clear()

    for i, layer in enumerate(yp.layers):
        item = yp.list_items.add()
        item.type = 'LAYER'
        item.index = i
        item.layer_index = i

        if layer.expand_subitems:
            for j, mask in enumerate(layer.masks):
                item = yp.list_items.add()
                item.type = 'MASK'
                item.index = j
                item.layer_index = i

class YListItem(bpy.types.PropertyGroup):
    type : EnumProperty(
        name = 'Item Type',
        items = (
            ('LAYER', 'Layer', ''),
            ('CHANNEL_OVERRIDE', 'Channel Override', ''),
            ('MASK', 'Mask', '')
        ),
        default = 'LAYER'
    )

    layer_index : IntProperty(default=0)
    index : IntProperty(default=0)

    expand_subitems : BoolProperty(
        name = 'Expand Subitems',
        description = 'Expand subitems',
        default = True
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
    refresh_list_items(yp)

def register():
    bpy.utils.register_class(YListItem)
    bpy.utils.register_class(YRefreshListItems)
    bpy.utils.register_class(YToggleItemDropdown)

def unregister():
    bpy.utils.unregister_class(YListItem)
    bpy.utils.unregister_class(YRefreshListItems)
    bpy.utils.unregister_class(YToggleItemDropdown)
