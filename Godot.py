from bpy.types import Context
from .common import * 
from .preferences import * 
from . import lib, Layer
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

import bpy

# export shader, choose location, save file
class ExportShader(Operator):
    """Export to godot shader"""

    bl_label = "Export Shader"
    bl_idname = "godot.export"

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context:bpy.context):
        print("Exporting to godot >> "+self.filepath)
        content_shader = '''
shader_type spatial;

void fragment() {
    ALBEDO = vec3(1.0);
    }
    '''
        

        file = open(self.filepath, "w")
        file.write(content_shader)
        file.close()

        return {'FINISHED'}

classes = [ExportShader]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    

if __name__ == "__main__":
    register()