bl_info = {
    "name": "Texture Group Node by Ucup",
    "author": "Yusuf Umar",
    "version": (0, 0, 0),
    "blender": (2, 79, 0),
    "location": "Node Editor > Properties > Texture Group",
    "description": "Texture Group Node can be substitute for layer manager within Cycles",
    "wiki_url": "http://twitter.com/ucupumar",
    "category": "Material",
}

import bpy
from bpy.props import *

#channel_template_names = [
#        'Albedo',
#        'Roughness',
#        'Normal',
#        'Alpha',
#        ]
#
#channel_template_props = {
#        # Template     # Type       # DefVal    
#        'Albedo'    : ['RGB',       (1,1,1,1),  ],
#        'Roughness' : ['VALUE',     0.5,        ],
#        'Normal'    : ['VECTOR',    (0,0,1),    ],
#        'Alpha'     : ['VALUE',     0,          ],
#        }
#
#channel_type_label = {
#        'RGB' : 'RGB',
#        'VALUE' : 'Value',
#        'VECTOR' : 'Vector',
#        }

def add_channel_to_tree(group_tree):
    # New channel should be the last item
    channel = group_tree.tg_channels[-1]

    if channel.type == 'RGB':
        socket_type = 'NodeSocketColor'
    elif channel.type == 'VALUE':
        socket_type = 'NodeSocketFloat'
    elif channel.type == 'VECTOR':
        socket_type = 'NodeSocketVector'

    inp = group_tree.inputs.new(socket_type, channel.name)
    out = group_tree.outputs.new(socket_type, channel.name)

    if channel.type == 'VALUE':
        inp.min_value = 0.0
        inp.max_value = 1.0
    elif channel.type == 'VECTOR':
        inp.min_value = -1.0
        inp.max_value = 1.0

def get_active_node():
    obj = bpy.context.object
    if not obj: return None
    mat = obj.active_material
    if not mat or not mat.node_tree: return None
    node = mat.node_tree.nodes.active
    return node

def get_active_texture_group_node():
    node = get_active_node()
    if node.type != 'GROUP' or not node.node_tree or not node.node_tree.tg_props.is_image_slots_group:
        return None
    return node

def create_new_group_tree(mat):

    # Group name is based from the material
    group_name = 'TexGroup ' + mat.name

    # Create new group tree
    group_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group_tree.tg_props.is_image_slots_group = True

    channel = group_tree.tg_channels.add()
    channel.name = 'Color'

    #refresh_group_io(group_tree)
    add_channel_to_tree(group_tree)

    return group_tree

class NewTextureGroupNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_node"
    bl_label = "Add new Texture Group Node"
    bl_description = "Add new texture group node"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def store_mouse_cursor(context, event):
        space = context.space_data
        tree = space.edit_tree

        # convert mouse position to the View2D for later node placement
        if context.region.type == 'WINDOW':
            # convert mouse position to the View2D for later node placement
            space.cursor_location_from_region(
                    event.mouse_region_x, event.mouse_region_y)
        else:
            space.cursor_location = tree.view_center

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree to add nodes to
        return ((space.type == 'NODE_EDITOR') and
                space.edit_tree and not space.edit_tree.library)

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        mat = space.id

        # select only the new node
        for n in tree.nodes:
            n.select = False

        group_tree = create_new_group_tree(mat)
        node = tree.nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree
        node.select = True
        tree.nodes.active = node
        node.location = space.cursor_location
        node.inputs[0].default_value = (1,1,1,1)

        return {'FINISHED'}

    # Default invoke stores the mouse position to place the node correctly
    # and optionally invokes the transform operator
    def invoke(self, context, event):
        self.store_mouse_cursor(context, event)
        result = self.execute(context)

        if 'FINISHED' in result:
            # removes the node again if transform is canceled
            bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')

        return result

class NewTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_channel"
    bl_label = "Add new Texture Group Channel"
    bl_description = "Add new texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    #template_name = EnumProperty(
    #        name = 'Channel Template',
    #        items = (('Albedo', 'Albedo', ''),
    #                 ('Roughness', 'Roughness', ''),
    #                 ('Normal', 'Normal', ''),
    #                 ('Alpha', 'Alpha', ''),
    #                 ('_CUSTOM', 'Custom', ''),
    #                 #('Subsurface', 'Subsurface', ''),
    #                 #('Subsurface Radius', 'Subsurface Radius', ''),
    #                 #('Subsurface Color', 'Subsurface Color', ''),
    #                 #('Metallic', 'Metallic', ''),
    #                 #('Specular', 'Specular', ''),
    #                 #('Specular Tint', 'Specular Tint', ''),
    #                 #('Anisotropic', 'Anisotropic', ''),
    #                 #('Anisotropic Rotation', 'Anisotropic Rotation', ''),
    #                 #('Sheen', 'Sheen', ''),
    #                 #('Sheen Tint', 'Sheen Tint', ''),
    #                 #('Clearcoat', 'Clearcoat', ''),
    #                 #('Clearcoat Roughness', 'Clearcoat Roughness', ''),
    #                 #('IOR', 'IOR', ''),
    #                 #('Transmission', 'Transmission', ''),
    #                 #('Clearcoat Normal', 'Clearcoat Normal', ''),
    #                 #('Tangent', 'Tangent', ''),
    #                 ),
    #        default = '_CUSTOM')

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def invoke(self, context, event):
        group_node = get_active_texture_group_node()
        channels = group_node.node_tree.tg_channels

        if self.type == 'RGB':
            self.name = 'Color'
        elif self.type == 'VALUE':
            self.name = 'Value'
        elif self.type == 'VECTOR':
            self.name = 'Normal'

        # Check if name already available on the list
        name_found = [c for c in channels if c.name == self.name]
        if name_found:
            i = 1
            while True:
                new_name = self.name + ' ' + str(i)
                name_found = [c for c in channels if c.name == new_name]
                if not name_found:
                    self.name = new_name
                    break
                i += 1

        #self.template_name = '_CUSTOM'

        #for n in channel_template_names:
        #    same_names = [c for c in channels if c.name == n]
        #    if not same_names:
        #        self.template_name = n
        #        break

        #if self.template_name == '_CUSTOM':
        #    self.name = 'Color'
        #    self.type = 'RGB'

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        #if self.template_name != '_CUSTOM':
        #    self.name = self.template_name
        #    self.type = channel_template_props[self.template_name][0]
        #    print(self)
        #else:
        #    self.name = 'Color'
        #    self.type = 'RGB'
        return True

    def draw(self, context):
        #row = self.layout.row()
        row = self.layout.split(percentage=0.35)
        #row = self.layout.row()
        col = row.column()
        #col.label('Template:')
        col.label('Name:')
        #col.label('Type:')
        col = row.column()
        #col.prop(self, 'template_name', text='')
        #if self.template_name != '_CUSTOM':
        #    col.label(self.template_name)
        #    col.label(channel_type_label[channel_template_props[self.template_name][0]])
        #else:
        col.prop(self, 'name', text='')
        #col.prop(self, 'type', text='')

    def execute(self, context):
        #node = context.active_node
        node = get_active_texture_group_node()
        #if node.type != 'GROUP' or not node.node_tree or not node.node_tree.tg_props.is_image_slots_group:
        if not node:
            self.report({'ERROR'}, "This isn't texture group node!")
            return {'CANCELLED'}

        group_tree = node.node_tree
        channels = group_tree.tg_channels
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Add new channel
        channel = channels.add()
        channel.name = self.name
        channel.type = self.type

        # Add input and output to the tree
        add_channel_to_tree(group_tree)

        last_index = len(group_tree.tg_channels)-1

        # Set default value
        #if self.template_name != '_CUSTOM':
        #    node.inputs[last_index].default_value = channel_template_props[self.template_name][1]
        if self.type == 'RGB':
            node.inputs[last_index].default_value = (1,1,1,1)
        if self.type == 'VALUE':
            node.inputs[last_index].default_value = 0.0
        if self.type == 'VECTOR':
            node.inputs[last_index].default_value = (0,0,1)

        # Change active channel
        group_tree.tg_active_channel = last_index

        return {'FINISHED'}

class MoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_move_texture_group_channel"
    bl_label = "Move Texture Group Channel"
    bl_description = "Move texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg_channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree

        # Get active channel
        index = group_tree.tg_active_channel
        channel = group_tree.tg_channels[index]
        num_chs = len(group_tree.tg_channels)

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_chs-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Move channel
        group_tree.tg_channels.move(index, new_index)

        # Move channel inside tree
        group_tree.inputs.move(index,new_index)
        group_tree.outputs.move(index,new_index)

        # Set active index
        group_tree.tg_active_channel = new_index

        return {'FINISHED'}

class RemoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_group_channel"
    bl_label = "Remove Texture Group Channel"
    bl_description = "Remove texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg_channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree

        # Get active channel
        channel_idx = group_tree.tg_active_channel
        channel = group_tree.tg_channels[channel_idx]
        channel_name = channel.name

        # Remove channel
        group_tree.tg_channels.remove(channel_idx)

        # Remove channel from tree
        #remove_channel_from_tree(group_tree, channel_name)
        group_tree.inputs.remove(group_tree.inputs[channel_idx])
        group_tree.outputs.remove(group_tree.outputs[channel_idx])

        # Set new active index
        if (group_tree.tg_active_channel == len(group_tree.tg_channels) and
            group_tree.tg_active_channel > 0
            ):
            group_tree.tg_active_channel -= 1

        return {'FINISHED'}

class NODE_PT_texture_groups(bpy.types.Panel):
    #bl_space_type = 'VIEW_3D'
    bl_space_type = 'NODE_EDITOR'
    bl_label = "Texture Groups"
    bl_region_type = 'UI'
    #bl_region_type = 'TOOLS'
    #bl_category = "Texture Groups"
#    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        #node = context.active_node
        #return node
        #return (node and node.type == 'GROUP' and 
        #        node.node_tree and node.node_tree.tg_props.is_image_slots_group)
        return True

    def draw(self, context):
        layout = self.layout
        #node = context.active_node
        node = get_active_node()

        if not node:
            layout.label("No node selected!")
            return

        #layout.label("This node (" + node.name + ") isn't texture group node!")
        if node.type != 'GROUP' or not node.node_tree or not node.node_tree.tg_props.is_image_slots_group:
            layout.label("This isn't texture group node!")
            return

        group_tree = node.node_tree
        layout.label('Channel Base Value:', icon='COLOR')
        row = layout.row()
        row.template_list("NODE_UL_y_texture_groups", "", group_tree,
                "tg_channels", group_tree, "tg_active_channel", rows=4, maxrows=5)  
        col = row.column(align=True)
        #col.operator("node.y_add_new_texture_group_channel", icon='ZOOMIN', text='')
        col.operator_menu_enum("node.y_add_new_texture_group_channel", 'type', icon='ZOOMIN', text='')
        col.operator("node.y_remove_texture_group_channel", icon='ZOOMOUT', text='')
        col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_UP').direction = 'UP'
        col.operator("node.y_move_texture_group_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

class NODE_UL_y_texture_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        if not group_node: return
        inputs = group_node.inputs

        row = layout.row()
        row.prop(item, 'name', text='', emboss=False)
        if item.type == 'VALUE':
            row.prop(inputs[index], 'default_value', text='') #, emboss=False)
        elif item.type == 'RGB':
            row.prop(inputs[index], 'default_value', text='', icon='COLOR')
        elif item.type == 'VECTOR':
            row.prop(inputs[index], 'default_value', text='', expand=False)

def menu_func(self, context):
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_texture_group_node', text='Texture Group', icon='NODE')

def update_channel_name(self, context):
    group_tree = self.id_data
    index = [i for i, ch in enumerate(group_tree.tg_channels) if ch == self][0]

    if index < len(group_tree.inputs):
        group_tree.inputs[index].name = self.name
        group_tree.outputs[index].name = self.name

class TextureGroupChannel(bpy.types.PropertyGroup):
    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo',
            update=update_channel_name)

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    is_alpha_channel = BoolProperty(default=False)

class NodeGroupTGProps(bpy.types.PropertyGroup):
    is_image_slots_group = BoolProperty(default=False)

def register():
    bpy.utils.register_module(__name__)
    bpy.types.ShaderNodeTree.tg_props = PointerProperty(type=NodeGroupTGProps)
    bpy.types.ShaderNodeTree.tg_channels = CollectionProperty(type=TextureGroupChannel)
    bpy.types.ShaderNodeTree.tg_active_channel = IntProperty(default=0)

    bpy.types.NODE_MT_add.append(menu_func)

def unregister():
    bpy.types.NODE_MT_add.remove(menu_func)
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
