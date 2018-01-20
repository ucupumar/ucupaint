import bpy

class YRefreshImage(bpy.types.Operator):
    bl_idname = "node.y_reload_image"
    bl_label = "Reload Image"
    bl_description = 'Reload Image'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):
        # Reload image
        context.image.reload()

        # Refresh viewport and image editor
        for area in context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

class YPackImage(bpy.types.Operator):
    bl_idname = "node.y_pack_image"
    bl_label = "Pack Image"
    bl_description = 'Pack Image'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):
        context.image.pack(as_png=True)
        return {'FINISHED'}

class YSaveImage(bpy.types.Operator):
    bl_idname = "node.y_save_image"
    bl_label = "Save Image"
    bl_description = 'Save Image'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and context.image.filepath != ''

    def execute(self, context):
        context.image.save()
        return {'FINISHED'}
