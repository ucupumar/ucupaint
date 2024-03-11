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
        ('OVERLAY_ONLY', 'Normal Overlay Only', ''),
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

    channel_name : StringProperty(
            name = 'Channel Source Name',
            description = 'Channel source name for bake target',
            default = '')

    subchannel_index : EnumProperty(
            name = 'Subchannel',
            description = 'Channel source RGBA index',
            items = rgba_items,
            default= '0')

    default_value : FloatProperty(
            name = 'Default Value',
            description = 'Channel default value',
            subtype = 'FACTOR',
            default = 0.0, min=0.0, max=1.0)

    normal_type : EnumProperty(
            name = 'Normal Channel Type',
            description = 'Normal channel source type',
            items = normal_type_items,
            default='COMBINED')

    flip_value : BoolProperty(
            name = 'Flip G',
            description = 'Flip G value so normal is compatible with DirectX application',
            default = False)

class YBakeTarget(bpy.types.PropertyGroup):
    name : StringProperty(
            name='Bake Target Name',
            description='Name of bake target name',
            default='')

    data_type : EnumProperty(
            name = 'Bake Target Data Type',
            description = 'Bake target data type',
            items = (
                ('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
                ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1),
                ),
            default='IMAGE')

    r : PointerProperty(type=YBakeTargetChannel)
    g : PointerProperty(type=YBakeTargetChannel)
    b : PointerProperty(type=YBakeTargetChannel)
    a : PointerProperty(type=YBakeTargetChannel)

    # Nodes
    image_node : StringProperty(default='')
    image_node_outside : StringProperty(default='')

    # UI
    expand_content : BoolProperty(default=True)
    expand_r : BoolProperty(default=True)
    expand_g : BoolProperty(default=True)
    expand_b : BoolProperty(default=True)
    expand_a : BoolProperty(default=True)

class YNewBakeTarget(bpy.types.Operator):
    bl_idname = "node.y_new_bake_target"
    bl_label = "New Bake Target"
    bl_description = "New bake target"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(
            name = 'New Bake Target Name',
            description = 'New bake target name',
            default='')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        tree_name = tree.name.replace(get_addon_title() + ' ', '')
        self.name = get_unique_name(tree_name + ' Bake Target', yp.bake_targets)
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):

        row = split_layout(self.layout, 0.3)

        col = row.column(align=False)
        col.label(text='Name:')
        col = row.column(align=False)
        col.prop(self, 'name', text='')

    def execute(self, context):
        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypui = wm.ypui

        bt = yp.bake_targets.add()
        bt.name = self.name
        bt.a.default_value = 1.0

        yp.active_bake_target_index = len(yp.bake_targets)-1

        ypui.bake_target_ui.expand_content = True
        ypui.need_update = True
        #wm.yptimer.time = str(time.time())
        
        # Update panel
        context.area.tag_redraw()

        return {'FINISHED'}

class YRemoveBakeTarget(bpy.types.Operator):
    bl_idname = "node.y_remove_bake_target"
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

def register():
    bpy.utils.register_class(YNewBakeTarget)
    bpy.utils.register_class(YRemoveBakeTarget)
    bpy.utils.register_class(YBakeTargetChannel)
    bpy.utils.register_class(YBakeTarget)

def unregister():
    bpy.utils.unregister_class(YNewBakeTarget)
    bpy.utils.unregister_class(YRemoveBakeTarget)
    bpy.utils.unregister_class(YBakeTargetChannel)
    bpy.utils.unregister_class(YBakeTarget)
