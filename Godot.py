import shutil
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

    

    script_template = '''
shader_type spatial;
{0}vec4 layer(vec4 foreground, vec4 background) {{
    return foreground * foreground.a + background * (1.0 - foreground.a);
}}

void fragment() {{ 
{1}
    ALBEDO = mix_all.rgb;
}}

'''

    script_vars = '''
uniform sampler2D {0};
uniform vec2 {1} = vec2({2},{3});
'''
    script_mask_vars = "uniform sampler2D {0};"
    
    script_fragment_var = '''
    vec2 scaled_uv_{0} = UV * {1};
    vec4 albedo_{0} = texture({2}, scaled_uv_{0});'''

    script_mask_fragment_var = '''
    vec4 mask_{0} = texture({1}, UV);
    albedo_{0}.a = mask_{0}.r;
'''

    script_layer_combine_0 = '''

    vec4 mix_all = layer(albedo_0, albedo_1);'''

    script_layer_combine_next = '''
    mix_all = layer(mix_all, albedo_{0});
'''
  #vec4 albedo = texture({1}, scaled_uv_{0});
    
    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        
        index = 0
        layer:Layer.YLayer

        global_vars = ""
        fragment_vars = ""
        combine_content = ""

        # get directory of filepath
        my_directory = os.path.dirname(self.filepath)
        if not os.path.exists(my_directory):
            os.makedirs(my_directory)
        
        for layer in yp.layers:
            if layer.enable:
                mapping = get_layer_mapping(layer)

                layer_var = "layer_"+str(index)

                scale_var = layer_var + "_scale"

                print("pos", mapping.inputs[1].default_value)
                print("rot", mapping.inputs[2].default_value)
                print("scl", mapping.inputs[3].default_value)

                skala = mapping.inputs[3].default_value
                global_vars += self.script_vars.format(layer_var, scale_var, skala.x, skala.y)
                fragment_vars += self.script_fragment_var.format(index, scale_var, layer_var)

                source = get_layer_source(layer)

                image_path = source.image.filepath_from_user()

                # copy to directory 
                print("copy ", image_path, " to ", my_directory)
                shutil.copy(image_path, my_directory)

                print("filepath ", index, " = ",source.image.filepath_from_user())
                print("rawpath ", index, " = ",source.image.filepath)
                print("path user ", index, " = ",source.image.filepath_raw)
                # if source == 'FILE':
                # else:
                #     print("layer ", index, " = ",source)
                    
                for idx, msk in enumerate(layer.masks):
                    mask_var = layer_var + "_mask_" + str(idx)
                    # mask_scale_var = mask_var + "_scale_"+str(idx)
                    global_vars += self.script_mask_vars.format(mask_var)
                    fragment_vars += self.script_mask_fragment_var.format(index, mask_var)

                global_vars += "\n"

                if index == 1:
                    combine_content += self.script_layer_combine_0
                elif index > 1:
                    combine_content += self.script_layer_combine_next.format(index)
                    
                index += 1

        fragment_vars += combine_content

        content_shader = self.script_template.format(global_vars, fragment_vars)

        # content_shader += self.script_fragment.format(fragment_vars, "coba")
        print(content_shader)

        file = open(self.filepath, "w")
        file.write(content_shader)
        file.close()

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

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