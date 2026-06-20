import bpy, time
from .common import *
from bpy.props import *
from .bake_common import *
from . import BakeInfo, BaseOperator

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

    if bt.data_type == 'IMAGE':
        bt_node = tree.nodes.get(bt.baked_node)
        if bt_node and bt_node.image:
            update_image_editor_image(context, bt_node.image)
        else:
            update_image_editor_image(context, None)

def update_bake_target_height_normalize(self, context):
    if not self.height_normalize:
        self.hdr = True

class YBakeTargetChannel(bpy.types.PropertyGroup):

    channel_name : StringProperty(
        name = 'Channel Source Name',
        description = 'Channel source name for bake target',
        default = ''
    )

    # TODO: Option to use entire luminosity value rather than using only one subchannel
    subchannel_index : EnumProperty(
        name = 'Subchannel',
        description = 'Channel source RGBA index',
        items = rgba_items,
        default = '0'
    )

    default_value : FloatProperty(
        name = 'Default Value',
        description = 'Channel default value',
        subtype = 'FACTOR',
        default = 0.0, min=0.0, max=1.0
    )

    normal_type : EnumProperty(
        name = 'Normal Channel Type',
        description = 'Normal channel source type',
        items = normal_type_items,
        default = 'COMBINED'
    )

    invert_value : BoolProperty(
        name = 'Invert Value',
        description = 'Invert value',
        default = False
    )

class YBakeTarget(bpy.types.PropertyGroup, BaseBakeProps, BakeInfo.BaseBakeInfoProps):
    name : StringProperty(
        name = 'Bake Target Name',
        description = 'Name of bake target name',
        default = ''
    )

    data_type : EnumProperty(
        name = 'Bake Target Data Type',
        description = 'Bake target data type',
        items = (
            ('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
            ('VCOL', get_vertex_color_label(), '', 'GROUP_VCOL', 1),
        ),
        default = 'IMAGE'
    )

    # Channel specific settings
    height_normalize : BoolProperty(
        name = 'Normalize Height',
        description = 'Normalize height channel output',
        default = True,
        update = update_bake_target_height_normalize
    )

    normal_includes_height : BoolProperty(
        name = 'Normal includes Height',
        description = 'Baked normal will includes normal from height',
        default = True
    )

    # Deprecated
    use_float : BoolProperty(default=False)

    uv_map : StringProperty(default='', update=update_bake_uv_map)
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    r : PointerProperty(type=YBakeTargetChannel)
    g : PointerProperty(type=YBakeTargetChannel)
    b : PointerProperty(type=YBakeTargetChannel)
    a : PointerProperty(type=YBakeTargetChannel)

    # Nodes
    image_node : StringProperty(default='') # Deprecated
    image_node_outside : StringProperty(default='')# Deprecated

    baked_node : StringProperty(default='')
    baked_node_outside : StringProperty(default='')

    normal_prep : StringProperty(default='')
    normal_process : StringProperty(default='')

    # UI
    expand_content : BoolProperty(default=False)
    expand_r : BoolProperty(default=False)
    expand_g : BoolProperty(default=False)
    expand_b : BoolProperty(default=False)
    expand_a : BoolProperty(default=False)

def get_channel_idx_that_has_no_bake_target_yet(yp, data_type):

    # Check for channel that has no bake target yet
    channel_names = [c.name for c in yp.channels]
    for bt in yp.bake_targets:
        if bt.data_type != data_type: continue
        for letter in rgba_letters:
            btc = getattr(bt, letter)
            if btc.channel_name in channel_names:
                channel_names.remove(btc.channel_name)

    # Use the channel that has no bake target yet
    channel_idx = 0
    if any(channel_names):
        root_ch = yp.channels.get(channel_names[0])
        if root_ch:
            channel_idx = get_channel_index(root_ch)
            channel_idx = str(channel_idx)
    else: channel_idx = '-1'

    return channel_idx

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

    if self.data_type == 'VCOL':
        if is_bl_newer_than(3, 2):
            self.name += ' Attribute'
        else: self.name += ' VCol'

    self.name = get_unique_name(tree_name + suffix, yp.bake_targets)
    if self.data_type == 'IMAGE':
        self.name = get_unique_name(tree_name + suffix, bpy.data.images)

def update_new_bake_target_channel_idx(self, context):
    node = get_active_ypaint_node()
    tree = node.node_tree
    yp = tree.yp

    if self.channel_idx == '-1':
        update_new_bake_target_preset(self, context)
    else:
        try: root_ch = yp.channels[int(self.channel_idx)]
        except: return

        self.name = tree.name.replace(get_addon_title()+' ','')+' '+root_ch.name

        if self.data_type == 'VCOL':
            if is_bl_newer_than(3, 2):
                self.name += ' Attribute'
            else: self.name += ' VCol'

        self.name = get_unique_name(self.name, yp.bake_targets)
        if self.data_type == 'IMAGE':
            self.name = get_unique_name(self.name, bpy.data.images)

def update_new_bake_target_data_type(self, context):
    node = get_active_ypaint_node()
    tree = node.node_tree
    yp = tree.yp

    self.channel_idx = get_channel_idx_that_has_no_bake_target_yet(yp, self.data_type)

def add_new_channel_bake_target(context, channel_name):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp
    bt = yp.bake_targets.add()
    bt.name = "Channel Bake Target " + channel_name
    bt.a.default_value = 1.0

    bt.r.channel_name = channel_name
    bt.g.channel_name = channel_name
    bt.b.channel_name = channel_name

    yp.active_bake_target_index = len(yp.bake_targets)-1

    wm = context.window_manager
    ypui = wm.ypui

    ypui.bake_target_ui.expand_content = True
    ypui.need_update = True

def new_bake_target_channel_items(self, context):
    from . import lib

    items = BaseOperator.channel_items_base(self, context)
    items.append(('-1', 'Custom', '', lib.get_icon('channels'), len(items)))

    return items

class YNewChannelBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_new_channel_bake_target"
    bl_label = "New Channel Bake Target"
    bl_description = "New bake target"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()
    
    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        print("Creating new bake target from channels..."+str(yp.active_channel_index))
        channel = yp.channels[yp.active_channel_index]

        add_new_channel_bake_target(context, channel.name)
        
        # Update panel
        context.area.tag_redraw()
        return {'FINISHED'}

def is_bake_target_using_exact_channel(bt, root_ch):

    matched = True

    for i, letter in enumerate(rgba_letters):
        if letter == 'a': continue
        btc = getattr(bt, letter)
        if btc.channel_name != root_ch.name or (root_ch.type != 'VALUE' and int(btc.subchannel_index) != i):
            matched = False
            break

    return matched

class YNewBakeTarget(bpy.types.Operator):
    bl_idname = "wm.y_new_bake_target"
    bl_label = "New Bake Target"
    bl_description = "New bake target"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(
        name = 'New Bake Target Name',
        description = 'New bake target name',
        default = ''
    )

    channel_idx : EnumProperty(
        name = 'Channel',
        description = 'Channel of new layer, can be changed later',
        items = new_bake_target_channel_items,
        update = update_new_bake_target_channel_idx
    )

    preset : EnumProperty(
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

    hdr : BoolProperty(
        name = '32-bit Float',
        description = 'Use 32-bit float image',
        default = False
    )

    data_type : EnumProperty(
        name = 'Bake Target Data Type',
        description = 'Bake target data type',
        items = (
            ('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
            ('VCOL', get_vertex_color_label(), '', 'GROUP_VCOL', 1),
        ),
        default = 'IMAGE',
        update = update_new_bake_target_data_type
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        # Get channel index that has no bake target yet
        self.channel_idx = get_channel_idx_that_has_no_bake_target_yet(yp, self.data_type)

        # Update name for the first time
        if self.channel_idx == '-1':
            update_new_bake_target_preset(self, context)
        else: update_new_bake_target_channel_idx(self, context)

        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        row = split_layout(self.layout, 0.3)

        col = row.column(align=False)
        col.label(text='Name:')
        col.label(text='Type:')

        col.label(text='Channel:')
        if self.channel_idx == '-1':
            col.label(text='Preset:')

        if self.data_type == 'IMAGE':
            col.separator()
            col.label(text='')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        rrow = col.row(align=True)
        rrow.prop(self, 'data_type', expand=True) #, text='')

        col.prop(self, 'channel_idx', text='')
        if self.channel_idx == '-1':
            col.prop(self, 'preset', text='')

        if self.data_type == 'IMAGE':
            col.separator()
            col.prop(self, 'hdr')

        # Check for the already available bake target
        if not self.channel_idx == '-1':
            try: root_ch = yp.channels[int(self.channel_idx)]
            except: root_ch = None

            if root_ch:
                bt_found = False

                for bt in yp.bake_targets:
                    if bt.data_type != self.data_type: continue
                    if is_bake_target_using_exact_channel(bt, root_ch):
                        bt_found = True
                        break

                if bt_found:
                    self.layout.label(text=root_ch.name+' channel bake target already exists!', icon='ERROR')

    def execute(self, context):
        wm = context.window_manager
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypui = wm.ypui

        root_ch = None
        if not self.channel_idx == '-1':
            try: root_ch = yp.channels[int(self.channel_idx)]
            except: return {'CANCELLED'}

        bt = yp.bake_targets.add()
        bt.name = self.name
        bt.hdr = self.hdr
        bt.a.default_value = 1.0
        bt.data_type = self.data_type

        bt.uv_map = get_active_render_uv(context.object)

        # Set some default values
        bt.fxaa = True
        bt.denoise = False

        if root_ch:
            for i, letter in enumerate(rgba_letters):
                if letter == 'a': continue
                btc = getattr(bt, letter)
                if btc: 
                    btc.channel_name = root_ch.name
                    if root_ch.type != 'VALUE':
                        btc.subchannel_index = str(i)
        else:
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
                    if ch.special_channel_type == 'NORMAL':
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
        remove_node(tree, bt, 'baked_node')

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
        cbt.hdr = bt.hdr
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

    paste_as_new : BoolProperty(
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
            
        bt.hdr = cbt.hdr
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
    bpy.utils.register_class(YNewChannelBakeTarget)

def unregister():
    bpy.utils.unregister_class(YNewBakeTarget)
    bpy.utils.unregister_class(YRemoveBakeTarget)
    bpy.utils.unregister_class(YBakeTargetChannel)
    bpy.utils.unregister_class(YBakeTarget)
    bpy.utils.unregister_class(YCopyBakeTarget)
    bpy.utils.unregister_class(YPasteBakeTarget)
    bpy.utils.unregister_class(YNewChannelBakeTarget)
