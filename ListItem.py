import bpy, re
from bpy.props import *
from .common import *

def get_layer_item_index(layer):
    yp = layer.id_data.yp

    layer_index = get_layer_index(layer)
    for i, item in enumerate(yp.list_items):
        if item.index == layer_index and item.type == 'LAYER':
            return i

    return -1

def get_collapsed_parent_item_index(layer):
    yp = layer.id_data.yp

    collapsed_parent = None
    for idx in reversed(get_list_of_parent_ids(layer)):
        parent = yp.layers[idx]
        if not parent.expand_subitems:
            collapsed_parent = parent
            break

    if collapsed_parent:
        return get_layer_item_index(collapsed_parent)
    
    return -1

def refresh_list_items(yp, repoint_active=False):
    # Get current active item and its parent
    active_item_name = ''
    active_item_type = ''
    active_item_is_second_member = False
    active_collapsed_parent_item_index = -1
    if repoint_active:

        # If layer index is out of bound, point to last layer
        if yp.active_layer_index >= len(yp.layers) and len(yp.layers) != 0:
            layer = yp.layers[len(yp.layers)-1]

            if not layer.expand_subitems or not yp.enable_expandable_subitems:
                active_item_name = layer.name
                active_item_type = 'LAYER'
                active_collapsed_parent_item_index = get_collapsed_parent_item_index(layer)

            elif layer.expand_subitems and yp.enable_expandable_subitems:
                for mask in layer.masks:
                    if mask.active_edit:
                        active_item_name = mask.name
                        active_item_type = 'MASK'

                for i, ch in enumerate(layer.channels):
                    if not ch.enable: continue
                    root_ch = yp.channels[i]
                    if ch.override and ch.override_type in {'IMAGE', 'VCOL'} and ch.active_edit:
                        active_item_name = layer.name + ' ' + root_ch.name
                        active_item_type = 'CHANNEL_OVERRIDE'

                    if root_ch.type == 'NORMAL' and ch.override_1 and ch.override_1_type == 'IMAGE' and ch.active_edit_1:
                        active_item_name = layer.name + ' ' + root_ch.name + ' 1'
                        active_item_type = 'CHANNEL_OVERRIDE'
                        active_item_is_second_member = True

        # Get current item
        elif yp.active_item_index < len(yp.list_items):
            item = yp.list_items[yp.active_item_index]

            # Get corresponding layer
            layer_index = item.index if item.type == 'LAYER' else item.parent_index
            if layer_index < len(yp.layers):
                layer = yp.layers[layer_index]

                # Get collapsed parent item index
                active_collapsed_parent_item_index = get_collapsed_parent_item_index(layer)

                # Get current active item
                active_item_name = item.name
                active_item_type = item.type
                active_item_is_second_member = item.is_second_member

    # Reset list
    yp.list_items.clear()

    new_active_index = -1
    for i, layer in enumerate(yp.layers):

        # Check if layer is collapsed
        collapsed_parent_item_index = get_collapsed_parent_item_index(layer)
        if collapsed_parent_item_index != -1:
            if collapsed_parent_item_index == active_collapsed_parent_item_index:
                new_active_index = collapsed_parent_item_index
        else:

            item = yp.list_items.add()
            item.type = 'LAYER'
            item.index = i
            item.name = layer.name
            item.parent_index = layer.parent_idx

            layer_item_index = len(yp.list_items)-1

            if active_item_name == layer.name and active_item_type == 'LAYER':
                new_active_index = layer_item_index

            color_ch, alpha_ch = get_layer_color_alpha_ch_pairs(layer)

            for j, ch in enumerate(layer.channels):

                root_ch = yp.channels[j]

                # Channel Override
                if (layer.expand_subitems and 
                    (root_ch.type != 'NORMAL' or ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}) and 
                    (ch.override and ch.override_type in {'IMAGE', 'VCOL'}) and
                    (ch.enable or (ch == alpha_ch and color_ch.enable)) and
                    yp.enable_expandable_subitems
                    ):
                    item = yp.list_items.add()
                    item.type = 'CHANNEL_OVERRIDE'
                    item.index = j
                    item.parent_index = i
                    item.parent_name = layer.name
                    item.name = layer.name + ' ' + root_ch.name

                    if (
                        # Select channel with active edit after expand subitems
                        (repoint_active and yp.active_layer_index == i and ch.active_edit) or 

                        # Select correct mask after other layer uncollapsing
                        (active_item_name == item.name and active_item_type == 'CHANNEL_OVERRIDE' and not active_item_is_second_member)
                    ):
                        new_active_index = len(yp.list_items)-1

                elif active_item_name == layer.name + ' ' + root_ch.name and active_item_type == 'CHANNEL_OVERRIDE':
                    new_active_index = layer_item_index

                # Channel Override 1 / Normal
                if (layer.expand_subitems and 
                    (root_ch.type == 'NORMAL' and ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}) and 
                    (ch.override_1 and ch.override_1_type in {'IMAGE', 'VCOL'}) and
                    ch.enable and
                    yp.enable_expandable_subitems
                    ):
                    item = yp.list_items.add()
                    item.type = 'CHANNEL_OVERRIDE'
                    item.index = j
                    item.parent_index = i
                    item.parent_name = layer.name
                    item.name = layer.name + ' ' + root_ch.name + ' 1'
                    item.is_second_member = True

                    if (
                        # Select channel with active edit after expand subitems
                        (repoint_active and yp.active_layer_index == i and ch.active_edit_1) or 

                        # Select correct mask after other layer uncollapsing
                        (active_item_name == item.name and active_item_type == 'CHANNEL_OVERRIDE' and active_item_is_second_member)
                    ):
                        new_active_index = len(yp.list_items)-1

                elif active_item_name == layer.name + ' ' + root_ch.name + ' 1' and active_item_type == 'CHANNEL_OVERRIDE':
                    new_active_index = layer_item_index

            # Masks
            for j, mask in enumerate(layer.masks):

                if layer.expand_subitems and mask.enable and yp.enable_expandable_subitems:
                    item = yp.list_items.add()
                    item.type = 'MASK'
                    item.index = j
                    item.parent_index = i
                    item.parent_name = layer.name
                    item.name = mask.name

                    if (
                        # Select mask with active edit after expand subitems
                        (repoint_active and yp.active_layer_index == i and mask.active_edit) or 

                        # Select correct mask after other layer uncollapsing
                        (active_item_name == mask.name and active_item_type == 'MASK')
                    ):
                        new_active_index = len(yp.list_items)-1

                elif active_item_name == mask.name and active_item_type == 'MASK':
                    new_active_index = layer_item_index

    # If there's no new active index, set it active layer
    if new_active_index == -1 and yp.active_layer_index < len(yp.layers):
        new_active_index = get_layer_item_index(yp.layers[yp.active_layer_index])

    # Set new active index
    if new_active_index != -1:
        yp.active_item_index = new_active_index

class YListItem(bpy.types.PropertyGroup):

    name : StringProperty(default='')
    index : IntProperty(default=0)

    parent_name : StringProperty(default='')
    parent_index : IntProperty(default=-1)

    # To mark normal override
    is_second_member : BoolProperty(default=False)

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
    bl_idname = "wm.y_refresh_list_items"
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
    if yp.halt_update: return

    if yp.active_item_index >= len(yp.list_items): return
    
    item = yp.list_items[yp.active_item_index]

    layer_index = -1
    if item.type == 'LAYER':
        layer_index = item.index

        # Disable active edit on masks and overrides if layer is expanded
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if layer.expand_subitems and layer.type in {'IMAGE', 'VCOL'}:
                for mask in layer.masks:
                    if mask.active_edit: mask.active_edit = False
                for ch in layer.channels:
                    if ch.active_edit: ch.active_edit = False
                    if ch.active_edit_1: ch.active_edit_1 = False

    elif item.type == 'MASK':
        layer_index = item.parent_index
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if item.index < len(layer.masks):
                mask = layer.masks[item.index]
                mask.active_edit = True

    elif item.type == 'CHANNEL_OVERRIDE':
        layer_index = item.parent_index
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if item.index < len(layer.channels):
                ch = layer.channels[item.index]
                if not item.is_second_member:
                    ch.active_edit = True
                else: ch.active_edit_1 = True

    if layer_index != -1 and layer_index < len(yp.layers): # and yp.active_layer_index != layer_index:
        yp.active_layer_index = layer_index

def get_active_item_entity(yp):
    if yp.active_item_index >= len(yp.list_items) or len(yp.list_items) == 0:
        return None

    item = yp.list_items[yp.active_item_index]

    if item.type == 'LAYER':
        layer_index = item.index
        if layer_index < len(yp.layers):
            return yp.layers[layer_index]

    elif item.type == 'MASK':
        layer_index = item.parent_index
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if item.index < len(layer.masks):
                return layer.masks[item.index]

    elif item.type == 'CHANNEL_OVERRIDE':
        layer_index = item.parent_index
        if layer_index < len(yp.layers):
            layer = yp.layers[layer_index]
            if item.index < len(layer.channels):
                return layer.channels[item.index]

    return None

def set_active_entity_item(entity):
    yp = entity.id_data.yp

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    ch = None
    mask = None
    root_ch = None
    appendix = ''
    repoint_to_layer = False
    if m1: 
        layer = yp.layers[int(m1.group(1))]
    elif m2: 
        layer = yp.layers[int(m2.group(1))]
        ch = layer.channels[int(m2.group(2))]
        root_ch = yp.channels[int(m2.group(2))]

        if not yp.enable_expandable_subitems or not layer.expand_subitems or (not ch.active_edit_1 and not ch.active_edit):
            repoint_to_layer = True

        if ch.active_edit_1:
            appendix = ' 1'

    elif m3: 
        layer = yp.layers[int(m3.group(1))]
        mask = layer.masks[int(m3.group(2))]

        if not yp.enable_expandable_subitems or not layer.expand_subitems or not mask.active_edit:
            repoint_to_layer = True

    else: return

    ori_halt_update = yp.halt_update
    if not yp.halt_update:
        yp.halt_update = True

    for i, item in enumerate(yp.list_items):
        if (
            ((m1 or repoint_to_layer) and item.type == 'LAYER' and item.name == layer.name) or
            (m2 and item.type == 'CHANNEL_OVERRIDE' and item.name == layer.name + ' ' + root_ch.name + appendix) or
            (m3 and item.type == 'MASK' and item.name == mask.name)
        ):
            if yp.active_item_index != i:
                yp.active_item_index = i
            break

    if not ori_halt_update:
        yp.halt_update = False

def register():
    bpy.utils.register_class(YListItem)
    bpy.utils.register_class(YRefreshListItems)

def unregister():
    bpy.utils.unregister_class(YListItem)
    bpy.utils.unregister_class(YRefreshListItems)
