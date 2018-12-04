import bpy
from bpy.props import *
from .common import *

class YBakeChannels(bpy.types.Operator):
    """Bake Channels to Image(s)"""
    bl_idname = "node.y_bake_channels"
    bl_label = "Bake channels to Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):

        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        for ch in yp.channels:
            print(ch.name)

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YBakeChannels)

def unregister():
    bpy.utils.unregister_class(YBakeChannels)
