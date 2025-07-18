import bpy
from .common import *
from bpy.props import *

rgba_items = (
    ('0', 'R', ''),
    ('1', 'G', ''),
    ('2', 'B', ''),
    ('3', 'A', ''),
)

normal_type_items = (
    ('COMBINED', 'Combined Normal', ''),
    ('DISPLACEMENT', 'Displacement', ''),
    ('OVERLAY_ONLY', 'Normal Without Bump', ''),
    ('VECTOR_DISPLACEMENT', 'Vector Displacement', ''),
)

def update_active_bake_target_index(self, context):
    yp = self
    tree = self.id_data
    try: bt = yp.bake_targets[yp.active_bake_target_index]
    except: return

    bt_node = tree.nodes.get(bt.image_node)
    if bt_node and bt_node.image:
        update_image_editor_image(context, bt_node.image)
    else:
        update_image_editor_image(context, None)

class YBakeTargetChannel(bpy.types.PropertyGroup):

    channel_name = StringProperty(
        name = 'Channel Source Name',
        description = 'Channel source name for bake target',
        default = ''
    )

    subchannel_index = EnumProperty(
        name = 'Subchannel',
        description = 'Channel source RGBA index',
        items = rgba_items,
        default = '0'
    )

    default_value = FloatProperty(
        name = 'Default Value',
        description = 'Channel default value',
        subtype = 'FACTOR',
        default = 0.0, min=0.0, max=1.0
    )

    normal_type = EnumProperty(
        name = 'Normal Channel Type',
        description = 'Normal channel source type',
        items = normal_type_items,
        default = 'COMBINED'
    )

    invert_value = BoolProperty(
        name = 'Invert Value',
        description = 'Invert value',
        default = False
    )

class YBakeTarget(bpy.types.PropertyGroup):
    name = StringProperty(
        name = 'Bake Target Name',
        description = 'Name of bake target name',
        default = ''
    )

    data_type = EnumProperty(
        name = 'Bake Target Data Type',
        description = 'Bake target data type',
        items = (
            ('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
            ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1),
        ),
        default = 'IMAGE'
    )

    use_float = BoolProperty(
        name = '32-bit Image',
        description = 'Use 32-bit float image',
        default = False
    )

    r = PointerProperty(type=YBakeTargetChannel)
    g = PointerProperty(type=YBakeTargetChannel)
    b = PointerProperty(type=YBakeTargetChannel)
    a = PointerProperty(type=YBakeTargetChannel)

    # Nodes
    image_node = StringProperty(default='')
    image_node_outside = StringProperty(default='')

    # UI
    expand_content = BoolProperty(default=True)
    expand_r = BoolProperty(default=False)
    expand_g = BoolProperty(default=False)
    expand_b = BoolProperty(default=False)
    expand_a = BoolProperty(default=False)

def update_new_bake_target_preset(self, context):
    node = get_active_ypaint_node()
    tree = node.node_tree
    yp = tree.yp

    tree_name = tree.name.replace(get_addon_title() + ' ', '')
    if self.preset == 'BLANK':
        suffix = ' Bake Target'
    elif self.preset == 'ORM':
        suffix = ' ORM'
    elif self.preset == 'DX_NORMAL':
        suffix = ' Normal DirectX'

    #self.name = get_unique_name(tree_name + suffix, yp.bake_targets)
    self.name = get_unique_name(tree_name + suffix, bpy.data.images)

class YNewBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_new_bake_target"
    bl_label = "New Bake Target"
    bl_description = "New bake target"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
        name = 'New Bake Target Name',
        description = 'New bake target name',
        default = ''
    )

    preset = EnumProperty(
        name = 'Bake Target Preset',
        description = 'Customm bake target preset',
        items = (
            ('BLANK', 'Blank', ''),
            ('ORM', 'GLTF ORM', ''),
            ('DX_NORMAL', 'DirectX Normal', ''),
        ),
        default = 'BLANK',
        update = update_new_bake_target_preset
    )

    use_float = BoolProperty(
        name = '32-bit Float',
        description = 'Use 32-bit float image',
        default = False
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        tree_name = tree.name.replace(get_addon_title() + ' ', '')
        #self.name = get_unique_name(tree_name + ' Bake Target', yp.bake_targets)
        self.name = get_unique_name(tree_name + ' Bake Target', bpy.data.images)
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):

        row = split_layout(self.layout, 0.3)

        col = row.column(align=False)
        col.label(text='Name:')
        col.label(text='Preset:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        col.prop(self, 'preset', text='')
        col.prop(self, 'use_float')

    def execute(self, context):
        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypui = wm.ypui

        bt = yp.bake_targets.add()
        bt.name = self.name
        bt.use_float = self.use_float
        bt.a.default_value = 1.0

        if self.preset == 'ORM':
            for ch in yp.channels:
                if ch.name in {'Ambient Occlusion', 'AO'}:
                    bt.r.channel_name = ch.name
                elif ch.name in {'Roughness', 'R'}:
                    bt.g.channel_name = ch.name
                elif ch.name in {'Metallic', 'Metalness', 'M'}:
                    bt.b.channel_name = ch.name
                bt.r.default_value = 1.0

        elif self.preset == 'DX_NORMAL':
            for ch in yp.channels:
                if ch.type == 'NORMAL':
                    bt.r.channel_name = ch.name
                    bt.g.channel_name = ch.name
                    bt.b.channel_name = ch.name

                    bt.r.subchannel_index = '0'
                    bt.g.subchannel_index = '1'
                    bt.b.subchannel_index = '2'

                    bt.g.invert_value = True

        yp.active_bake_target_index = len(yp.bake_targets)-1

        ypui.bake_target_ui.expand_content = True
        ypui.need_update = True
        #wm.yptimer.time = str(time.time())
        
        # Update panel
        context.area.tag_redraw()

        return {'FINISHED'}

class YRemoveBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_remove_bake_target"
    bl_label = "Remove Bake Target"
    bl_description = "Remove bake target"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        wm = context.window_manager
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        try: bt = yp.bake_targets[yp.active_bake_target_index]
        except: return {'CANCELLED'}

        # Remove related nodes
        remove_node(tree, bt, 'image_node')

        # Remove bake target
        yp.bake_targets.remove(yp.active_bake_target_index)

        if len(yp.bake_targets) > 0:
            yp.active_bake_target_index = len(yp.bake_targets)-1

        # Update panel
        context.area.tag_redraw()

        return {'FINISHED'}

class YCopyBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_copy_bake_target"
    bl_label = "Copy Bake Target"
    bl_description = "Copy Bake Target"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        node = get_active_ypaint_node()
        if not node: return False

        group_tree = node.node_tree
        yp = group_tree.yp
        
        return context.object and len(yp.bake_targets) > 0 and yp.active_bake_target_index >= 0 

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        wmp = context.window_manager.ypprops

        bt = yp.bake_targets[yp.active_bake_target_index]

        wmp.clipboard_bake_target.clear()
        cbt = wmp.clipboard_bake_target.add()

        cbt.name = bt.name
        cbt.use_float = bt.use_float
        cbt.data_type = bt.data_type
        
        cbt.r.channel_name = bt.r.channel_name
        cbt.r.subchannel_index = bt.r.subchannel_index
        cbt.r.default_value = bt.r.default_value
        cbt.r.normal_type = bt.r.normal_type
        cbt.r.invert_value = bt.r.invert_value

        cbt.g.channel_name = bt.g.channel_name
        cbt.g.subchannel_index = bt.g.subchannel_index
        cbt.g.default_value = bt.g.default_value
        cbt.g.normal_type = bt.g.normal_type
        cbt.g.invert_value = bt.g.invert_value

        cbt.b.channel_name = bt.b.channel_name
        cbt.b.subchannel_index = bt.b.subchannel_index
        cbt.b.default_value = bt.b.default_value
        cbt.b.normal_type = bt.b.normal_type
        cbt.b.invert_value = bt.b.invert_value

        cbt.a.channel_name = bt.a.channel_name
        cbt.a.subchannel_index = bt.a.subchannel_index
        cbt.a.default_value = bt.a.default_value
        cbt.a.normal_type = bt.a.normal_type
        cbt.a.invert_value = bt.a.invert_value

        return {'FINISHED'}

class YPasteBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_paste_bake_target"
    bl_label = "Paste Bake Target As New"
    bl_description = "Paste Bake Target"
    bl_options = {'UNDO'}

    paste_as_new = BoolProperty(
        name = 'Paste As New Bake Target',
        default = True
    )

    @classmethod
    def poll(cls, context):
        node = get_active_ypaint_node()

        wmp = context.window_manager.ypprops
        has_clipboard = len(wmp.clipboard_bake_target) > 0

        return context.object and node and has_clipboard

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        wmp = context.window_manager.ypprops

        if not self.paste_as_new and (yp.active_bake_target_index < 0 or yp.active_bake_target_index >= len(yp.bake_targets) or len(yp.bake_targets) == 0):
            self.report({'ERROR'}, "Cannot paste values, no bake target selected")
            return {'CANCELLED'}

        cbt = wmp.clipboard_bake_target[0]

        if self.paste_as_new:
            name = get_unique_name(cbt.name, yp.bake_targets)
            bt = yp.bake_targets.add()
            bt.name = name
        else:
            bt = yp.bake_targets[yp.active_bake_target_index]
            
        bt.use_float = cbt.use_float
        bt.data_type = cbt.data_type
        
        bt.r.channel_name = cbt.r.channel_name
        bt.r.subchannel_index = cbt.r.subchannel_index
        bt.r.default_value = cbt.r.default_value
        bt.r.normal_type = cbt.r.normal_type
        bt.r.invert_value = cbt.r.invert_value

        bt.g.channel_name = cbt.g.channel_name
        bt.g.subchannel_index = cbt.g.subchannel_index
        bt.g.default_value = cbt.g.default_value
        bt.g.normal_type = cbt.g.normal_type
        bt.g.invert_value = cbt.g.invert_value

        bt.b.channel_name = cbt.b.channel_name
        bt.b.subchannel_index = cbt.b.subchannel_index
        bt.b.default_value = cbt.b.default_value
        bt.b.normal_type = cbt.b.normal_type
        bt.b.invert_value = cbt.b.invert_value

        bt.a.channel_name = cbt.a.channel_name
        bt.a.subchannel_index = cbt.a.subchannel_index
        bt.a.default_value = cbt.a.default_value
        bt.a.normal_type = cbt.a.normal_type
        bt.a.invert_value = cbt.a.invert_value

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YNewBakeTarget)
    bpy.utils.register_class(YRemoveBakeTarget)
    bpy.utils.register_class(YBakeTargetChannel)
    bpy.utils.register_class(YBakeTarget)
    bpy.utils.register_class(YCopyBakeTarget)
    bpy.utils.register_class(YPasteBakeTarget)
    
def unregister():
    bpy.utils.unregister_class(YNewBakeTarget)
    bpy.utils.unregister_class(YRemoveBakeTarget)
    bpy.utils.unregister_class(YBakeTargetChannel)
    bpy.utils.unregister_class(YBakeTarget)
    bpy.utils.unregister_class(YCopyBakeTarget)
    bpy.utils.unregister_class(YPasteBakeTarget)
