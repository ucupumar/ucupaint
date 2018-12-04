import bpy

class YBakeChannels(bpy.types.Operator):
    """Bake Channels"""
    bl_idname = "node.y_bake_channels"
    bl_label = "Bake channels to image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        return {'FINISHED'}

def register():
    bpy.utils.register_class(YBakeChannels)

def unregister():
    bpy.utils.unregister_class(YBakeChannels)
