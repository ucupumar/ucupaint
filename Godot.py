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

    

    script_top = '''
shader_type spatial;

'''
    script_vars = '''
uniform sampler2D {0};
uniform vec2 {1} = vec2({2},{3});
'''
    script_mask_vars = "uniform sampler2D {0};"
    script_method = '''

void fragment() {{
    vec2 scaled_uv = UV * {}0;
    vec4 albedo = texture({}0, scaled_uv);
    
    ALBEDO = albedo.rgb;
}}
''' 
    
    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        

        content_shader = self.script_top
        
        index = 0
        layer:Layer.YLayer

        for layer in yp.layers:
            if layer.enable:
                mapping = get_layer_mapping(layer)

                layer_var = "layer_"+str(index)

                scale_var = layer_var + "_scale"

                print("pos", mapping.inputs[1].default_value)
                print("rot", mapping.inputs[2].default_value)
                print("scl", mapping.inputs[3].default_value)

                skala = mapping.inputs[3].default_value
                content_shader += self.script_vars.format(layer_var, scale_var, skala.x, skala.y)

                mask_var = layer_var + "_mask"
                for idx, msk in enumerate(layer.masks):
                    mask_scale_var = mask_var + "_scale_"+str(idx)
                    content_shader += self.script_mask_vars.format(mask_scale_var)
                index += 1

        content_shader += self.script_method.format(scale_var, layer_var)
        print(content_shader)
        return {'FINISHED'}

#     def invoke(self, context, event):
#         context.window_manager.fileselect_add(self)
#         return {'RUNNING_MODAL'}

#     def execute(self, context:bpy.context):
#         print("Exporting to godot >> "+self.filepath)
#         content_shader = '''
# shader_type spatial;

# void fragment() {
#     ALBEDO = vec3(1.0);
#     }
#     '''
    
#         file = open(self.filepath, "w")
#         file.write(content_shader)
#         file.close()

#         return {'FINISHED'}

classes = [ExportShader]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    

if __name__ == "__main__":
    register()